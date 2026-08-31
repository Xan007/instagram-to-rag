import os
from typing import Optional
from config.env import load_runtime_env
from src.llm.base import BaseLLMClient
from src.llm.gemini import GeminiLLMClient
from src.llm.openai_compatible import OpenAICompatibleLLMClient

load_runtime_env()


class LLMClientFactory:
    @staticmethod
    def get_client(stage: str = "rag") -> BaseLLMClient:
        load_runtime_env()
        stage_upper = stage.upper()
        provider = os.getenv(f"{stage_upper}_PROVIDER", os.getenv("LLM_PROVIDER", "gemini")).lower()

        if provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable is not set.")
            default_model = os.getenv(f"{stage_upper}_MODEL", "llama-3.3-70b-versatile")
            return OpenAICompatibleLLMClient(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                default_model=default_model,
            )

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set.")
            default_model = os.getenv(f"{stage_upper}_MODEL", "gpt-4o-mini")
            return OpenAICompatibleLLMClient(
                api_key=api_key,
                default_model=default_model,
            )

        return GeminiLLMClient()
