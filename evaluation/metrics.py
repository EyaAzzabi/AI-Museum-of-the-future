"""Quality metrics for retrieval and for saved exhibition runs (pure functions, no I/O)."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

SPECIALISTS = ("historian", "sociologist", "technology", "culture_art", "visual")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return "".join(c for c in text if not unicodedata.combining(c))


def matches_terms(text: str, groups: list[list[str]]) -> bool:
    """True when the text contains at least one term of every group (whole words, accent-insensitive)."""
    norm = _normalize(text)
    return all(
        any(re.search(r"(?<!\w)" + re.escape(_normalize(term)) + r"(?!\w)", norm) for term in group)
        for group in groups
    )


def is_relevant(result: Any, groups: list[list[str]]) -> bool:
    meta = getattr(result, "metadata", None) or {}
    return matches_terms(f"{getattr(result, 'content', '')} {meta.get('title') or ''}", groups)


def retrieval_metrics(results: list[Any], groups: list[list[str]], k: int) -> dict:
    """precision@k, hit@k, reciprocal rank, document diversity and share of statistics rows."""
    top = results[:k]
    flags = [is_relevant(r, groups) for r in top]
    first = next((i for i, f in enumerate(flags) if f), None)
    docs = {getattr(r, "document_id", "") for r in top}
    stats = sum(((getattr(r, "metadata", None) or {}).get("category") == "statistics") for r in top)
    return {
        "precision": sum(flags) / k,
        "hit": 1.0 if first is not None else 0.0,
        "rr": 1.0 / (first + 1) if first is not None else 0.0,
        "diversity": len(docs) / len(top) if top else 0.0,
        "statistics_share": stats / len(top) if top else 0.0,
        "returned": len(top),
    }


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def average(rows: list[dict]) -> dict:
    keys = [k for k in rows[0] if isinstance(rows[0][k], (int, float))] if rows else []
    return {k: round(mean(r[k] for r in rows), 3) for k in keys}


# ── Saved runs (agents/run_log.py) ───────────────────────────────────────────

def run_metrics(run: dict) -> dict:
    """Coverage, citations, review and fact-check figures from a saved run's events."""
    events = run.get("events", [])
    insights = {e["agent"]: e["insight"] for e in events if e["kind"] == "insight"}
    abstained = sorted({e["agent"] for e in events if e["kind"] == "abstain" and e.get("agent") in SPECIALISTS})
    errors = sorted({e["agent"] for e in events if e["kind"] == "agent_error"})
    specialists = {a: i for a, i in insights.items() if a in SPECIALISTS}
    findings = [f for i in specialists.values() for f in i.get("key_findings", [])]
    dropped = sum(e.get("dropped_findings", 0) for e in events if e["kind"] == "insight" and e.get("agent") in SPECIALISTS)
    own_search = [e.get("own_search", 0) for e in events if e["kind"] == "evidence"]

    result = next((e["exhibition"] for e in reversed(events) if e["kind"] == "result"), None) or {}
    verdicts = result.get("fact_check") or []
    checked = [v for v in verdicts if v.get("supported") is not None]
    review = result.get("review") or {}
    calls = [e for e in events if e["kind"] == "llm_call"]

    return {
        "coverage": len(specialists) / len(SPECIALISTS),
        "perspectives_present": sorted(specialists),
        "perspectives_missing": sorted(set(SPECIALISTS) - set(specialists)),
        "abstained": abstained,
        "errors": errors,
        "findings": len(findings),
        "findings_dropped_uncited": dropped,
        "citation_survival": len(findings) / (len(findings) + dropped) if findings or dropped else 0.0,
        "avg_citations_per_finding": mean(len(re.findall(r"\[[^\[\]]+\]", f)) for f in findings),
        "own_search_results_per_agent": mean(own_search),
        "sections": len(result.get("sections") or []),
        "fact_check_supported": (sum(1 for v in checked if v["supported"]) / len(checked)) if checked else None,
        "fact_check_unsupported_claims": sum(len(v.get("unsupported_claims") or []) for v in verdicts),
        "review_agreements": len(review.get("agreements") or []),
        "review_tensions": len(review.get("tensions") or []),
        "review_weak_findings": len(review.get("weak_findings") or []),
        "llm_calls": len(calls),
        "llm_calls_cached": sum(1 for c in calls if c.get("cached")),
        "llm_errors": sum(1 for c in calls if c.get("error")),
        "timings_s": run.get("timings", {}),
    }
