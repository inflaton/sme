"""
Standard routing
"""

from typing import Literal
from langchain_core.runnables import Runnable

from src.misc.beautified_logging import BeautifiedLogging

from src.llm.langgraph.routing import LangGraphAssistant, State


logging = BeautifiedLogging()


class EmailReconAssistant(LangGraphAssistant):
    """
    This file contains building blocks for agents
    """

    def __init__(self, runnable: Runnable, name: str) -> str:
        super().__init__(runnable, name)

        self.log_mapper = {
            "Supervisor": "USER",
            "Tool": "TOOL",
            "Senior Reconciliation Agent": "RECONCILIATION_AGENT",
            "Finance Clerk": "FINANCE_CLERK",
            "Invoice Data Engineer": "INVOICE_DATA_ENGINEER",
            "Invoice Update Data Engineer": "INVOICE_UPDATE_DATA_ENGINEER",
            "Email Data Engineer": "EMAIL_DATA_ENGINEER",
        }


def finance_clerk_router(
    state: State,
) -> Literal["senior_reconciliation_agent", "call_ocr_tool"]:
    """Router for SQL agents"""
    messages = state["messages"]
    last_message = messages[-1]
    if "tool_calls" in last_message.additional_kwargs:
        # The agent is invoking a tool
        return "call_ocr_tool"
    if "NO ATTACHMENTS" in last_message.content:
        # When attachments are empty
        return "senior_reconciliation_agent"
    return "senior_reconciliation_agent"


def db_agent_router(
    state: State,
) -> Literal["senior_reconciliation_agent", "invoice_data_engineer"]:
    """Router for SQL agents"""
    messages = state["messages"]
    last_message = messages[-1]
    if "ERROR" in last_message.content:
        # When the SQL result has error, route back to the sql agent
        return "invoice_data_engineer"
    if "ASK" in last_message.content:
        # the update is done, route back to the reconciliation agent
        return "senior_reconciliation_agent"
    return "senior_reconciliation_agent"


def update_db_agent_router(
    state: State,
) -> Literal["senior_reconciliation_agent", "update_db_agent_router"]:
    """Router for SQL agents"""
    messages = state["messages"]
    last_message = messages[-1]
    if "ERROR" in last_message.content:
        # When the SQL result has error, route back to the sql agent
        return "invoice_update_data_engineer"
    if "DONE" in last_message.content:
        # End the whole convo when the db is updated
        return "end"
    return "senior_reconciliation_agent"


def reconciliation_agent_router(
    state,
) -> Literal[
    "call_tool",
    "finance_clerk",
    "invoice_data_engineer",
    "invoice_update_data_engineer",
    "end",
    "continue",
]:
    """Router for reconciliation agent"""
    messages = state["messages"]
    last_message = messages[-1]
    if "QUERY" in last_message.content:
        # when the asst needs the data from the database
        return "invoice_data_engineer"
    if "UPDATE" in last_message.content:
        # when the asst needs to update the database
        return "invoice_update_data_engineer"
    if "NA" in last_message.content:
        # when email is not about invoices
        return "end"
    if "ERROR" in last_message.content:
        # when data is not found or has errors
        return "end"
    return "end"
