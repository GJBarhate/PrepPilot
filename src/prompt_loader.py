import os
import re

_cache: dict[str, str] = {}

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def load_prompt(name: str) -> str:
    if name in _cache:
        return _cache[name]
    path = os.path.join(_PROMPTS_DIR, f"{name}.md")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    _cache[name] = text
    return text


def render_prompt(template: str, **kwargs) -> str:
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template
