from ..llm_client import GeminiClient
from ..prompt_loader import load_prompt


class Agent:
    def __init__(self, client: GeminiClient, prompt_name: str):
        self._client = client
        self._prompt_name = prompt_name
        self._system_prompt: str | None = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = load_prompt(self._prompt_name)
        return self._system_prompt
