"""LLM provider settings for the agents.

Any OpenAI-compatible endpoint works. The default is Groq, which has a free
tier (https://console.groq.com/keys). To use another free provider, set
LLM_BASE_URL / LLM_MODEL, for example:

  Google Gemini  https://generativelanguage.googleapis.com/v1beta/openai/  gemini-2.0-flash
  OpenRouter     https://openrouter.ai/api/v1                              meta-llama/llama-3.3-70b-instruct:free
"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_VISION_MODEL = "qwen/qwen3.8-27b"  # multimodal; gpt-oss is text-only


def get_model(env_var: str = "LLM_MODEL") -> str:
    return os.getenv(env_var) or os.getenv("LLM_MODEL") or DEFAULT_MODEL


def get_vision_model() -> str:
    return os.getenv("VISION_MODEL") or DEFAULT_VISION_MODEL


def build_llm_client() -> Any:
    """Build an OpenAI-SDK client pointed at the configured provider."""
    from openai import OpenAI

    api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("Set LLM_API_KEY (or GROQ_API_KEY) in .env to call the agents.")
    return OpenAI(api_key=api_key, base_url=os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL)
