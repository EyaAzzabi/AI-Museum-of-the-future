from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


class TechnologyAgent(BaseAgent):
    """Science & technology specialist: innovations, digital life and their effect on society."""

    name = "technology"
    focus = "Technological and scientific change of 2020-2026 and how it reshaped work, society and daily life"
    system_prompt = (
        "You are the Science & Technology specialist of the AI Museum of the Future, "
        "a curator writing 100 years from now. You explain which technologies defined the era "
        "and what they changed for people, using only the supplied evidence. "
        "Distinguish what a source reports from your interpretation. Return JSON only."
    )
    search_queries = (
        "artificial intelligence large language models impact on society and work",
        "digital transformation startups internet social media",
        "renewable energy solar climate technology",
        "space exploration scientific breakthrough",
        "biotechnology vaccines health technology",
    )
    search_keywords = ("artificial intelligence", "startup", "ChatGPT", "solar", "digital")
    search_exclude_categories = ("statistics", "image")

    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "technology.md")
