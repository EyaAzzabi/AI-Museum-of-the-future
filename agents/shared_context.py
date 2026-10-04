from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.base_agent import InsightObject


@dataclass
class SharedContext:
    insights: dict[str, InsightObject] = field(default_factory=dict)
    cross_references: list[str] = field(default_factory=list)


def compute_cross_references(insights: dict[str, InsightObject]) -> list[str]:
    counts: dict[str, int] = {}
    for insight in insights.values():
        if not isinstance(insight, InsightObject):
            continue
        for artifact in insight.selected_artifacts:
            counts[artifact] = counts.get(artifact, 0) + 1
    return sorted([artifact for artifact, count in counts.items() if count >= 2])
