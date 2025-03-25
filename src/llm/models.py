"""
Standard logic for deciding which model to use
"""

import os
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

# from langchain_community.callbacks.openai_info import OpenAICallbackHandler

from src.llm.info.chatgpt_info import OpenAICallbackHandler
from src.llm.info.ollama_info import OllamaUsageCallbackHandler


class ModelRouter:
    """Model routing class"""

    def __init__(self):
        self.callback_handler = OpenAICallbackHandler()
        self.ollama_callback_handler = OllamaUsageCallbackHandler()

    def __model_router(self, model_type: str = None, base_url: str = None) -> dict:
        """determine the models to use"""
        chat_gpt_model_list = ["gpt-", "o1"]
        llm_model_to_use = (
            model_type if model_type is not None else os.environ.get("MODEL")
        )

        is_gpt_model = (
            len([x for x in chat_gpt_model_list if llm_model_to_use.startswith(x)]) > 0
            or base_url is not None
            and "/v1" in base_url
        )

        return {
            "model": llm_model_to_use,
            "provider": "openai" if is_gpt_model else "ollama",
        }

    def get_model(
        self, model_type: str = None, temperature: float = 0.8, is_vision=False
    ):
        """Get the langchain model"""

        url_key = f"{'VISION_' if is_vision else ''}BASE_URL"
        base_url = os.environ.get(url_key, None)

        model_to_use = self.__model_router(model_type=model_type, base_url=base_url)

        standard_params = {"model": model_to_use["model"], "temperature": temperature}

        if base_url is not None:
            standard_params["base_url"] = base_url

        if model_to_use["provider"] == "openai":
            return {
                "provider": "openai",
                "model": ChatOpenAI(
                    **standard_params, callbacks=[self.callback_handler]
                ),
            }
        return {
            "provider": "ollama",
            "model": ChatOllama(
                **standard_params, callbacks=[self.ollama_callback_handler]
            ),
        }

    def check_usage(self):
        """Gets usage of all llm requests"""
        return {
            "successful_requests": self.callback_handler.successful_requests
            + self.ollama_callback_handler.successful_requests,
            "total_tokens": self.callback_handler.total_tokens
            + self.ollama_callback_handler.total_tokens,
            "prompt_tokens": self.callback_handler.prompt_tokens
            + self.ollama_callback_handler.prompt_tokens,
            "completion_tokens": self.callback_handler.completion_tokens
            + self.ollama_callback_handler.completion_tokens,
            "total_cost": self.callback_handler.total_cost,
        }
