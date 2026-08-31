import logging
import os
import time
from typing import Dict, List, Optional
from google import genai

logger = logging.getLogger(__name__)

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
]


class GeminiLLMClient:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.client = genai.Client(api_key=key)

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"Instructions:\n{content}\n")
            elif role == "user":
                prompt_parts.append(f"User: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\n")

        full_prompt = "\n".join(prompt_parts).strip()
        models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model] if model else FALLBACK_MODELS

        last_error = None
        for mod in models_to_try:
            for attempt in range(2):
                try:
                    chat = self.client.chats.create(model=mod)
                    response = chat.send_message(full_prompt)
                    return response.text.strip()
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    if "503" in err_str or "UNAVAILABLE" in err_str:
                        logger.info("Gemini model %s 503 unavailable. Trying next model...", mod)
                        break
                    elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        logger.info("Rate limit on %s. Waiting 10s...", mod)
                        time.sleep(10)
                    else:
                        break

        raise RuntimeError(f"All Gemini models failed: {last_error}")
