from typing import Any, Dict, List, Optional, Protocol


class BaseLLMClient(Protocol):
    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str: ...
