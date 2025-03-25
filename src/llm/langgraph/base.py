"""
The base class to initiate some basic functionalities
for langgraph
"""

from datetime import datetime
import json
from typing import Literal
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph

from src.llm.models import ModelRouter
from src.llm.langgraph.routing import State


class LangGraphQuery:
    """Abstract class for RAG query. has standard method to save/retrieve/clear chat history"""

    graph = None
    workflow = StateGraph(State)

    def __init__(self):
        self.chat_history: dict[str, list[Literal[AIMessage, HumanMessage]]] = {}

        self.templates = {}
        self.tool_usage = {
            "successful_requests": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0,
        }

        self.workflow = StateGraph(State)
        self.model_router = ModelRouter()

    def get_llm_model(self, model_type: str = None, temperature: float = 0.8):
        """Get LLM model"""
        return self.model_router.get_model(
            model_type=model_type, temperature=temperature
        )

    def create_empty_history(self, chat_id: str):
        """Reset chat history"""
        if chat_id not in self.chat_history:
            self.chat_history[chat_id] = []

    def save_chat_history(
        self, chat_id: str, chat_msgs: list[Literal[AIMessage, HumanMessage]]
    ):
        """save chat history to list"""

        self.create_empty_history(chat_id=chat_id)
        self.chat_history[chat_id] += chat_msgs

    def get_chat_history(self, chat_id):
        """Get chat history"""
        return self.chat_history.get(chat_id, [])

    def clear_chat_history(self, chat_id):
        """Empty chat history"""
        self.chat_history[chat_id] = []

    def accumulate_tool_usage(self, usage: dict[str, int]):
        """Accumulate usage stats for tools"""
        for key in self.tool_usage:
            self.tool_usage[key] += usage.get(key, 0)

    def check_usage(self) -> dict[str, int]:
        """Check usage"""
        model_usages = self.model_router.check_usage()
        total_usage = self.tool_usage
        for key in self.tool_usage:
            total_usage[key] += model_usages.get(key, 0)

        return total_usage

    def generate_response(self, query_text: str, chat_id: str):
        """Generate response by running the required steps"""

        init_query = HumanMessage(
            content=query_text, additional_kwargs={"sender": "requestor"}
        )
        chat_data = [init_query]
        response = ""
        for event in self.graph.stream(
            {"messages": self.get_chat_history(chat_id) + [init_query]},
            {
                "recursion_limit": 150,
                "configurable": {
                    # Checkpoints are accessed by thread_id
                    "thread_id": chat_id,
                },
            },
        ):
            for value in event.values():
                last_msg = value["messages"][-1]
                last_msg.additional_kwargs = {
                    **last_msg.additional_kwargs,
                    "timestamp": datetime.now().isoformat(),
                }
                chat_data.append(last_msg)

                if isinstance(last_msg, ToolMessage):
                    if last_msg.content.startswith("{"):
                        try:
                            tool_content = json.loads(last_msg.content)
                            # get usage data if available
                            usage = tool_content.get("usage", {})
                            self.accumulate_tool_usage(usage=usage)
                        except ValueError:
                            print("json load error")

                response = last_msg.content

        # save chat history
        self.save_chat_history(chat_id=chat_id, chat_msgs=chat_data)

        return response
