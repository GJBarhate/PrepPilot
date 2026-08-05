import os

MODEL_NAME = "gemini-3.5-flash-lite"

MAX_KEYS = 6
KEY_ENV_PREFIX = "GEMINI_API_KEY_"

MIN_TURNS = 5
MAX_TURNS = 7

DIFFICULTY_MIN = 1
DIFFICULTY_MAX = 5
DIFFICULTY_START = 3

TEMPERATURE_QUESTION = 0.8
TEMPERATURE_JUDGMENT = 0.2
TEMPERATURE_COACH = 0.5

RATE_LIMIT_COOLDOWN_SECONDS = 60


def load_api_keys() -> list[str]:
    keys = []
    for i in range(1, MAX_KEYS + 1):
        val = os.getenv(f"{KEY_ENV_PREFIX}{i}", "").strip()
        if val:
            keys.append(val)
    if not keys:
        raise RuntimeError(
            "No Gemini API keys found. Copy .env.example to .env and fill in "
            "at least GEMINI_API_KEY_1. See README for details."
        )
    return keys
