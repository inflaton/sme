"""
For the automated end to end invoice processing
Without usage of SQL agents for better stability
"""

import os

from langchain.agents import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities.sql_database import SQLDatabase
from langgraph.graph import START, END

from src.llm.agents.email_agent.tools import ocr_tool
from src.llm.agents.sql_agent.tools import invoice_db_query_tool, invoice_db_update_tool
from src.llm.langgraph.base import LangGraphQuery
from src.llm.langgraph.routing import State, create_tool_node_with_fallback
from src.llm.langgraph.tool_based_recon.builder import (
    EmailReconAssistant,
    finance_clerk_router,
    db_agent_router,
    update_db_agent_router,
    reconciliation_agent_router,
)


cwd = os.getcwd()


class ToolBasedEmailReconInvoicingAssistant(LangGraphQuery):
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

                    If the email and OCR data does not contain any information related to invoices,
                    respond with "NA" and the reason.

                    Prefix "QUERY" and the invoice ID in your response to request for the invoices
                    in our transaction database from the data engineer to check if the
                    invoice amount matches the database and the email.

                    Once all the data are complete and the invoice amount matches between the
                    database and the email, prefix your response with "UPDATE" and
                    the full email details to request the data engineer to update
                    the reconciliation status

                    If the invoice is not in the database or the invoice amount does not match,
                    or any errors are encountered, respond with "ERROR" and the reason
                    
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
                    You have access the invoice database
                    
                    Your job is to query the database using the invoice_db_query_tool provided
                    by passing the invoice ID as a parameter

                    If the invoice ID is not provided, prefix your response with
                    "ASK" to request for the invoice ID

                    When the tool returns a response, prefix your response
                    with "DONE" when that is completed or "ERROR" when the tool returns
                    an error

                    Request:
                    {input}

                    Kindly do not assume
                    """,
                )
            ]
        )
        return data_engineer_prompt | self.get_llm_model(
            temperature=0.4, model_type=self.sql_model
        )["model"].bind_tools([invoice_db_query_tool])

    def __create_db_update_agent(self) -> AgentExecutor:
        """Creates the db agent executor for the langgraph"""

        data_engineer_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You are an Data Engineer working at the finance department.

                    When requested by the reconciliation agent,
                    update invoice data in the database using the
                    transaction_db_update_tool by passing in the invoice_id
                    and the email_details as the parameter.

                    Request:
                    {input}

                    Kindly do not assume
                    """,
                )
            ]
        )
        return data_engineer_prompt | self.get_llm_model(
            temperature=0.4, model_type=self.sql_model
        )["model"].bind_tools([invoice_db_update_tool])

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
                    {chat_history}

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
                "call_ocr_tool": "call_ocr_tool",
                "senior_reconciliation_agent": "senior_reconciliation_agent",
            },
        )

        # add ocr tool
        self.workflow.add_node(
            "call_ocr_tool", create_tool_node_with_fallback([ocr_tool])
        )
        # OCR results will be passed to the reconciliation agent
        self.workflow.add_conditional_edges(
            "call_ocr_tool",
            lambda x: x["sender"],
            {"finance_clerk": "senior_reconciliation_agent"},
        )

        # add nodes and edges for supervisor agent
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
            {
                "senior_reconciliation_agent": "senior_reconciliation_agent",
                "call_invoice_db_query_tool": "call_invoice_db_query_tool",
            },
        )
        self.workflow.add_node(
            "call_invoice_db_query_tool",
            create_tool_node_with_fallback([invoice_db_query_tool]),
        )
        # transaction query results will be passed to the reconciliation agent directly
        self.workflow.add_conditional_edges(
            "call_invoice_db_query_tool",
            lambda x: x["sender"],
            {"invoice_data_engineer": "senior_reconciliation_agent"},
        )

        # add nodes and edges for data engineer for invoice updates
        update_data_engineer = self.__create_db_update_agent()
        self.workflow.add_node(
            "invoice_update_data_engineer",
            EmailReconAssistant(update_data_engineer, "invoice_update_data_engineer"),
        )
        self.workflow.add_conditional_edges(
            "invoice_update_data_engineer",
            update_db_agent_router,
            {
                "senior_reconciliation_agent": "senior_reconciliation_agent",
                "call_invoice_db_update_tool": "call_invoice_db_update_tool",
            },
        )
        self.workflow.add_node(
            "call_invoice_db_update_tool",
            create_tool_node_with_fallback([invoice_db_update_tool]),
        )
        # end when the db is updated
        self.workflow.add_conditional_edges(
            "call_invoice_db_update_tool",
            lambda x: x["sender"],
            {"invoice_update_data_engineer": END},
        )

        # add tools
        self.workflow.add_edge(START, "finance_clerk")
        self.graph = self.workflow.compile()
