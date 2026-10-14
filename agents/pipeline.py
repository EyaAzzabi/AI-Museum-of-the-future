"""Exhibition pipeline.

  specialists (parallel, each: input chunks + its own search)
      -> peer review (agreements, tensions, weak findings)
      -> curator (cited narratives)
      -> fact-check (narratives vs. cited evidence; one curator rewrite if needed)

With a ``recorder`` (agents.run_log.RunRecorder) every step is saved to
runs/<run_id>/run.json.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any

from agents.base_agent import InsightObject
from agents.curator import CuratorAgent, ExhibitionSynthesis
from agents.shared_context import SharedContext, compute_cross_references, evidence_of


def _build_specialist_agents(openai_client: Any, retriever: Any = None, recorder: Any = None):
    from agents.culture_art import CultureArtAgent
    from agents.historian import HistorianAgent
    from agents.sociologist import SociologistAgent
    from agents.technology import TechnologyAgent
    from agents.visual import VisualAgent

    agents = {
        "historian": HistorianAgent(openai_client),
        "sociologist": SociologistAgent(openai_client),
        "technology": TechnologyAgent(openai_client),
        "culture_art": CultureArtAgent(openai_client),
        "visual": VisualAgent(openai_client),
    }
    # Every specialist searches the knowledge base with its own queries.
    for agent in agents.values():
        agent.retriever = retriever
        agent.recorder = recorder
    return agents


def run_pipeline(
    chunks: list[Any],
    openai_client: Any,
    timeout_secs: int = 120,
    retriever: Any = None,
    recorder: Any = None,
    review: bool = True,
    fact_check: bool = True,
) -> ExhibitionSynthesis:
    """Fan out to the specialist agents and then synthesize an exhibition.

    ``chunks`` are shared evidence given to every specialist. With a
    ``retriever`` (HybridRetriever, or a plain Retriever) each specialist also
    searches the knowledge base itself; ``chunks`` may then be empty.
    """
    started = time.monotonic()
    agents = _build_specialist_agents(openai_client, retriever, recorder)
    insights: dict[str, InsightObject] = {}

    try:
        # Agents run in parallel, so they share one deadline rather than each
        # getting a 1/N slice of it (which cut off the slower HyDE sociologist).
        deadline = time.monotonic() + timeout_secs
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            futures = {executor.submit(agent.run, chunks): name for name, agent in agents.items()}
            for future, name in futures.items():
                try:
                    result = future.result(timeout=max(0.1, deadline - time.monotonic()))
                    insights[name] = result
                except Exception as exc:  # pragma: no cover - pipeline resiliency
                    logging.warning("[error] %s: %r", name, exc)
                    _record(recorder, "agent_error", agent=name, error=repr(exc))
                    insights[name] = InsightObject(
                        agent=name,
                        perspective="",
                        key_findings=[],
                        selected_artifacts=[],
                    )
        _timing(recorder, "specialists", started)

        shared_context = SharedContext(
            insights=insights,
            cross_references=compute_cross_references(insights),
        )
        if review and openai_client is not None:
            shared_context.review = _peer_review(openai_client, insights, recorder)

        t = time.monotonic()
        curator = CuratorAgent(openai_client)
        curator.recorder = recorder
        try:
            synthesis = curator.run(shared_context)
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"Curator failed to synthesize exhibition: {exc}") from exc
        _timing(recorder, "curator", t)

        if fact_check and openai_client is not None:
            synthesis = _fact_check(openai_client, curator, shared_context, synthesis, recorder)
        _record(recorder, "result", exhibition=synthesis)
        return synthesis
    finally:
        _timing(recorder, "total", started)
        if recorder is not None:
            path = recorder.save()
            logging.info("Run saved to %s", path)


def _peer_review(openai_client: Any, insights: dict[str, InsightObject], recorder: Any) -> dict:
    from agents.reviewer import EMPTY_REVIEW, PeerReviewAgent

    t = time.monotonic()
    reviewer = PeerReviewAgent(openai_client)
    reviewer.recorder = recorder
    try:
        return reviewer.review(insights)
    except Exception as exc:  # noqa: BLE001 - the exhibition can be written without a review
        logging.warning("Peer review failed: %r", exc)
        return dict(EMPTY_REVIEW)
    finally:
        _timing(recorder, "review", t)


def _fact_check(openai_client, curator, shared_context, synthesis, recorder) -> ExhibitionSynthesis:
    """Check narratives against their evidence; on unsupported claims, let the curator rewrite once."""
    from agents.fact_checker import FactCheckAgent, feedback_for

    t = time.monotonic()
    checker = FactCheckAgent(openai_client)
    checker.recorder = recorder
    evidence = evidence_of(shared_context.insights)
    try:
        verdicts = checker.check(synthesis.sections, evidence)
        feedback = feedback_for(verdicts)
        if feedback:
            logging.info("Fact-check found unsupported claims; asking the curator for a rewrite.")
            try:
                rewritten = curator.run(shared_context, feedback=feedback)
                verdicts = checker.check(rewritten.sections, evidence)
                synthesis = rewritten
            except Exception as exc:  # noqa: BLE001 - keep the first version, with its verdicts
                logging.warning("Curator rewrite after fact-check failed: %r", exc)
        synthesis.fact_check = verdicts
    except Exception as exc:  # noqa: BLE001 - an unchecked exhibition is still returned
        logging.warning("Fact-check failed: %r", exc)
    _timing(recorder, "fact_check", t)
    return synthesis


def _record(recorder: Any, kind: str, **data: Any) -> None:
    if recorder is not None:
        recorder.record(kind, **data)


def _timing(recorder: Any, stage: str, since: float) -> None:
    if recorder is not None:
        recorder.timing(stage, time.monotonic() - since)
