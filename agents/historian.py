from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent

HISTORIAN_SYSTEM_PROMPT = (
    "You are the Socio-Historical Agent for the AI Museum of the Future. "
    "You examine contemporary records from the perspective of an archivist and historian "
    "living 100 years in the future (the 22nd century). "
    "Your mission is to identify pivotal contemporary events, contextualize their historical "
    "significance, and evaluate their long-term century-scale impact. "
    "Ground all findings strictly in the provided evidence and cite the [chunk_id] of every claim. "
    "IMPÉRATIF : Rédigez l'intégralité de vos réponses, analyses et conclusions en FRANÇAIS soigné et percutant."
)


class HistorianAgent(BaseAgent):
    """Socio-Historical specialist: key events, their significance and century-scale legacy (in French)."""

    name = "historian"
    focus = "Pivotal political and social events of 2020-2026 and their long-term historical significance"
    system_prompt = HISTORIAN_SYSTEM_PROMPT
    search_queries = (
        "political crisis constitution elections democracy turning point",
        "major events protests reforms of the decade",
        "economic crisis debt inflation social unrest",
        "pandemic COVID-19 lockdown consequences",
    )
    search_exclude_categories = ("image",)

    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "historian.md")
