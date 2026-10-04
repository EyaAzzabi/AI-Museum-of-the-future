from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any

from agents.base_agent import InsightObject
from agents.curator import CuratorAgent, ExhibitionSynthesis
from agents.shared_context import SharedContext, compute_cross_references


def _build_specialist_agents(openai_client: Any):
    from agents.culture_art import CultureArtAgent
    from agents.historian import HistorianAgent
    from agents.sociologist import SociologistAgent
    from agents.technology import TechnologyAgent
    from agents.visual import VisualAgent

    return {
        "historian": HistorianAgent(openai_client),
        "sociologist": SociologistAgent(openai_client),
        "technology": TechnologyAgent(openai_client),
        "culture_art": CultureArtAgent(openai_client),
        "visual": VisualAgent(openai_client),
    }


def run_pipeline(chunks: list[Any], openai_client: Any, timeout_secs: int = 120) -> ExhibitionSynthesis:
    """Fan out to the specialist agents and then synthesize an exhibition."""
    agents = _build_specialist_agents(openai_client)
    insights: dict[str, InsightObject] = {}

    with ThreadPoolExecutor(max_workers=len(agents)) as executor:
        futures = {executor.submit(agent.run, chunks): name for name, agent in agents.items()}
        for future, name in futures.items():
            try:
                result = future.result(timeout=max(0.1, timeout_secs / max(len(futures), 1)))
                insights[name] = result
            except Exception as exc:  # pragma: no cover - pipeline resiliency
                logging.warning("[error] %s: %s", name, exc)
                insights[name] = InsightObject(
                    agent=name,
                    perspective="",
                    key_findings=[],
                    selected_artifacts=[],
                )

    shared_context = SharedContext(
        insights=insights,
        cross_references=compute_cross_references(insights),
    )
    curator = CuratorAgent(openai_client)
    try:
        return curator.run(shared_context)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"Curator failed to synthesize exhibition: {exc}") from exc
