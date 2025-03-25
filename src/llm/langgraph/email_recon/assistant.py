"""
For the automated end to end invoice processing
"""

import os
import json

from langchain.agents import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities.sql_database import SQLDatabase
from langgraph.graph import StateGraph, START, END

from src.llm.agents.email_agent.tools import ocr_tool
from src.llm.langgraph.base import LangGraphQuery
from src.llm.langgraph.routing import State, create_tool_node_with_fallback
from src.llm.langgraph.email_recon.builder import (
    EmailReconAssistant,
    finance_clerk_router,
    db_agent_router,
    update_db_agent_router,
    reconciliation_agent_router,
)

cwd = os.getcwd()


class EmailReconInvoicingAssistant(LangGraphQuery):
    """
    Invoicing assistant
    """

    def __init__(
        self,
        supervisor_model: str = None,
        sql_model: str = None,
        finance_clerk_model: str = None,
        vision_model: str = None,
        transaction_db_path: str = "",
    ):
        super().__init__()

        self.supervisor_model = supervisor_model
        self.sql_model = sql_model
        self.finance_clerk_model = finance_clerk_model
        self.vision_model = vision_model

        self.transaction_db = SQLDatabase.from_uri(f"sqlite:///{transaction_db_path}")

        self.__compile_graph()

    def __create_asst_agent(self) -> AgentExecutor:
        """create the main assistant interacting with the user"""

        assistant_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You're an Senior reconciliation agent working in the finance department.
                    
                    You are in charge of processing the data that sent to you, and to match the
                    invoice data to the amount in the database.

                    If the email and OCR does not contain any information regarding invoices,
                    respond with "NA" with the reason

                    Prefix "QUERY invoice ID:" and the invoice ID in your response to request for the invoices
                    in our transaction database from the data engineer to check if the
                    invoice amount matches the database and the email.

                    Once all the data are complete the invoice amount matches between the
                    database and the email, prefix your response with "UPDATE" and
                    the full email details to request the data engineer to update
                    the reconciliation status.

                    If the invoice is not in the database or the invoice amount does not match,
                    or any errors are encountered, respond with "ERROR" with the reason
                    
                    Chat history:
                    {chat_history}

                    Do not prefix multiple requests in a single response

                    Kindly do not assume
                    """,
                )
            ]
        )

        return (
            assistant_prompt
            | self.get_llm_model(model_type=self.supervisor_model)["model"]
        )

    def __create_db_agent(self) -> AgentExecutor:
        """Creates the db agent executor for the langgraph"""

        data_engineer_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You are an Data Engineer working at the finance department.
                    You have access the transaction database
                    
                    Your job is to query the database using SQL
                    and find the appropriate invoice to be reconciled and
                    pass the details to the Senior reconciliation agent as
                    requested

                    Be precise in your SQL query and use the invoice ID as a parameter
                    whenever possible.
                
                    Do not add any formatting to the data
                    """,
                ),
                MessagesPlaceholder("agent_scratchpad"),
                (
                    "assistant",
                    """
                    {input}
                    """,
                ),
            ]
        )

        llm_model = self.get_llm_model(model_type=self.sql_model, temperature=0.4)

        agent_executor = create_sql_agent(
            llm=llm_model["model"],
            db=self.transaction_db,
            verbose=True,
            agent_type=(
                "openai-tools" if llm_model["provider"] == "openai" else "tool-calling"
            ),
            prompt=data_engineer_prompt,
        )

        return agent_executor

    def __create_db_update_agent(self) -> AgentExecutor:
        """Creates the db agent executor for the langgraph"""

        data_engineer_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You are an Data Engineer working at the finance department.

                    Your job is to update invoice data in the database

                    When requested by the reconciliation agent, update the reconciled and
                    email_details columns accordingly inside the database and prefix your response
                    with "DONE" when that is completed

                    Be precise in your SQL query
                
                    Do not add any formatting to the data
                    """,
                ),
                MessagesPlaceholder("agent_scratchpad"),
                (
                    "assistant",
                    """
                    {input}
                    """,
                ),
            ]
        )

        llm_model = self.get_llm_model(model_type=self.sql_model, temperature=0.4)

        agent_executor = create_sql_agent(
            llm=llm_model["model"],
            db=self.transaction_db,
            verbose=True,
            agent_type=(
                "openai-tools" if llm_model["provider"] == "openai" else "tool-calling"
            ),
            prompt=data_engineer_prompt,
        )

        return agent_executor

    def __create_finance_clerk(self):
        admin_clerk_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You are an Admin Clerk working in a finance department

                    Your role is to use the OCR tool to perform OCR on the attachments
                    given by the email data engineer to retrieve the appropriate data
                    for reconciliation

                    Respond with "NO ATTACHMENTS" if there are not attachments

                    Request:
                    {input}

                    Kindly do not assume
                    """,
                )
            ]
        )
        return admin_clerk_prompt | self.get_llm_model(
            temperature=0, model_type=self.finance_clerk_model
        )["model"].bind_tools([ocr_tool])

    def __compile_graph(self):
        """Create graphlang"""

        # add nodes and edges for admin clerk
        finance_clerk = self.__create_finance_clerk()
        self.workflow.add_node(
            "finance_clerk", EmailReconAssistant(finance_clerk, "finance_clerk")
        )
        self.workflow.add_conditional_edges(
            "finance_clerk",
            finance_clerk_router,
            {
                "senior_reconciliation_agent": "senior_reconciliation_agent",
                "call_ocr_tool": "call_ocr_tool",
            },
        )

        # add tools
        self.workflow.add_node(
            "call_ocr_tool", create_tool_node_with_fallback([ocr_tool])
        )

        # tool called should always route back to email data engineer for processing
        self.workflow.add_conditional_edges(
            "call_ocr_tool",
            lambda x: x["sender"],
            {"finance_clerk": "senior_reconciliation_agent"},
        )

        # add nodes and edges for the supervisor asst
        reconciliation_agent = self.__create_asst_agent()
        self.workflow.add_node(
            "senior_reconciliation_agent",
            EmailReconAssistant(reconciliation_agent, "senior_reconciliation_agent"),
        )
        self.workflow.add_conditional_edges(
            "senior_reconciliation_agent",
            reconciliation_agent_router,
            {
                "end": END,
                "invoice_data_engineer": "invoice_data_engineer",
                "invoice_update_data_engineer": "invoice_update_data_engineer",
            },
        )

        # add nodes and edges for data engineer
        data_engineer = self.__create_db_agent()
        self.workflow.add_node(
            "invoice_data_engineer",
            EmailReconAssistant(data_engineer, "invoice_data_engineer"),
        )
        self.workflow.add_conditional_edges(
            "invoice_data_engineer",
            db_agent_router,
            {"senior_reconciliation_agent": "senior_reconciliation_agent"},
        )

        # add nodes and edges for data engineer
        update_data_engineer = self.__create_db_update_agent()
        self.workflow.add_node(
            "invoice_update_data_engineer",
            EmailReconAssistant(update_data_engineer, "invoice_update_data_engineer"),
        )
        self.workflow.add_conditional_edges(
            "invoice_update_data_engineer",
            update_db_agent_router,
            {"senior_reconciliation_agent": "senior_reconciliation_agent", "end": END},
        )

        # add tools
        self.workflow.add_edge(START, "finance_clerk")
        self.graph = self.workflow.compile()
