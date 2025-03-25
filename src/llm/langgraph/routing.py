"""
Standardized routing functions and
building blocks for the Langgraph
"""

import json
import os
from pathlib import Path

from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda, Runnable, RunnableConfig
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.misc.beautified_logging import BeautifiedLogging

cwd = os.getcwd()

logging = BeautifiedLogging()


class State(TypedDict):
    """
    Message state for the langgraph
    """

    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    sender: str


class LangGraphAssistant:
    """
    This file contains building blocks for agents
    """

    def __init__(self, runnable: Runnable, name: str) -> str:
        self.runnable = runnable
        self.name = name

        self.log_mapper = {
            "Supervisor": "USER",
            "Tool": "TOOL",
            "Senior Reconciliation Agent": "RECONCILIATION_AGENT",
            "Invoice Data Engineer": "INVOICE_DATA_ENGINEER",
            "Email Data Engineer": "EMAIL_DATA_ENGINEER",
        }

    def __get_role(self, message: BaseMessage):
        """Get role to parse as chat history"""
        if isinstance(message, HumanMessage):
            return "Requestor"

        if isinstance(message, ToolMessage):
            return message.name.replace("_", " ").title()

        if isinstance(message, AIMessage):
            sender = message.additional_kwargs["sender"]
            return sender.replace("_", " ").title()

        return ""

    def __log_msg(self, message: BaseMessage):
        if not message.content:
            return

        role = self.__get_role(message)
        logging.info(self.log_mapper[role], message.content)

    def __parse_chat_history(self, messages: Annotated[list, add_messages]) -> dict:
        """Parse the messages in a format that the standard prompt template used"""

        invoke_data = {}
        chat_history = ""
        for message in messages:
            # define the role
            role = self.__get_role(message)

            content = message.content
            # skip if content is empty or role is empty
            if (content == "") | (role == ""):
                continue

            if isinstance(message, ToolMessage):
                if message.content.startswith("{"):
                    try:
                        tool_content = json.loads(message.content)
                        content = tool_content.get("content", "")
                    except ValueError:
                        print("json load error")

            chat_history += f"{role}: {content}\n"
            invoke_data["input"] = f"{role}: {content}\n"

            if isinstance(message, HumanMessage):
                invoke_data["customer_query"] = content

        invoke_data["chat_history"] = chat_history
        invoke_data["messages"] = messages

        return invoke_data

    def __call__(self, state: State, config: RunnableConfig):
        """When the data is redirected from another agent"""
        while True:
            parsed_info = self.__parse_chat_history(state["messages"])
            # invoke AI
            result = self.runnable.invoke(parsed_info)

            # handle sql agent executor results
            if isinstance(result, dict):
                output = result.get("output", "")
                result = AIMessage(output)

            result.additional_kwargs["sender"] = self.name
            self.__log_msg(result)

            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [
                    HumanMessage("Respond with a real output.")
                ]
                state = {**state, "messages": messages}
            else:
                break

        return {"messages": state["messages"] + [result], "sender": self.name}


def handle_tool_error(state) -> dict:
    """Handle tool error"""
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    """When tool returns an error"""
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )
