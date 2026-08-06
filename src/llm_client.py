import json
import time

from google import genai
from google.genai import types

from .config import MODEL_NAME, RATE_LIMIT_COOLDOWN_SECONDS


class GeminiClient:
    def __init__(self, api_keys: list[str]):
        self._clients = [genai.Client(api_key=k) for k in api_keys]
        self._index = 0
        # Keys are benched (not dropped) so they re-enter rotation after cooldown.
        self._benched_until: list[float] = [0.0] * len(api_keys)

    def _next_client(self) -> genai.Client:
        n = len(self._clients)
        now = time.time()

        for _ in range(n):
            idx = self._index % n
            self._index = (self._index + 1) % n
            if self._benched_until[idx] <= now:
                return self._clients[idx]

        earliest = min(self._benched_until)
        wait = earliest - now
        if wait > 0:
            time.sleep(wait)
        return self._next_client()

    def _bench_current(self):
        idx = (self._index - 1) % len(self._clients)
        self._benched_until[idx] = time.time() + RATE_LIMIT_COOLDOWN_SECONDS

    def _is_rate_limit(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return "429" in msg or "resource_exhausted" in msg or "rate" in msg

    def _is_invalid_key(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return "api_key_invalid" in msg or "api key not valid" in msg

    def generate(self, system_prompt: str, user_content: str, temperature: float) -> str:
        max_attempts = 2 * len(self._clients)
        backoff = 1.0

        for attempt in range(max_attempts):
            client = self._next_client()
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=user_content,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                    ),
                )
                return response.text.strip()
            except Exception as e:
                if self._is_rate_limit(e) or self._is_invalid_key(e):
                    self._bench_current()
                    continue
                if "500" in str(e) or "503" in str(e) or "unavailable" in str(e).lower():
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 4.0)
                    continue
                raise RuntimeError(f"Gemini API error (key #{(self._index - 1) % len(self._clients) + 1}): {e}") from e

        raise RuntimeError("All Gemini API keys exhausted after retries.")

    def generate_json(
        self,
        system_prompt: str,
        user_content: str,
        response_schema: dict,
        temperature: float,
    ) -> dict:
        max_attempts = 2 * len(self._clients)
        backoff = 1.0

        for attempt in range(max_attempts):
            client = self._next_client()
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=user_content,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        response_mime_type="application/json",
                        response_schema=response_schema,
                    ),
                )
                text = response.text.strip()
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    repair_response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=f"Fix this invalid JSON and return only valid JSON:\n{text}",
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=response_schema,
                            temperature=0.1,
                        ),
                    )
                    return json.loads(repair_response.text.strip())
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse JSON from Gemini after repair attempt: {e}") from e
            except Exception as e:
                if self._is_rate_limit(e) or self._is_invalid_key(e):
                    self._bench_current()
                    continue
                if "500" in str(e) or "503" in str(e) or "unavailable" in str(e).lower():
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 4.0)
                    continue
                raise RuntimeError(f"Gemini API error (key #{(self._index - 1) % len(self._clients) + 1}): {e}") from e

        raise RuntimeError("All Gemini API keys exhausted after retries.")
