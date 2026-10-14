"""Peer review: the specialists' insights are read side by side before the curator writes.

One LLM call (instead of one critique per specialist, to keep runs fast and
cheap) returns where perspectives agree, where they are in tension, and which
findings are weakly supported by the text they cite. The result is validated
against the real agents, findings and chunk IDs, then handed to the curator
through SharedContext.review.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject

EMPTY_REVIEW = {"agreements": [], "tensions": [], "weak_findings": []}


class PeerReviewAgent(BaseAgent):
    name = "reviewer"
    system_prompt = (
        "You are the peer reviewer of a museum's specialist team. You compare the specialists' "
        "findings with each other and with the evidence they cite. You are precise and fair: "
        "you report real agreements and real tensions, not stylistic differences. Return JSON only."
    )

    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "reviewer.md")

    def review(self, insights: dict[str, InsightObject]) -> dict:
        present = {
            name: insight for name, insight in insights.items()
            if isinstance(insight, InsightObject) and insight.key_findings
        }
        if len(present) < 2:
            return dict(EMPTY_REVIEW)

        quoted = json.dumps({
            name: {
                "perspective": insight.perspective,
                "findings": {str(i): finding for i, finding in enumerate(insight.key_findings)},
                "evidence": {cid: (item.get("content") or "")[:300] for cid, item in insight.evidence.items()},
            }
            for name, insight in present.items()
        }, ensure_ascii=False)
        payload = self._call_llm(self.system_prompt, self._render_prompt(quoted, self.name, self.system_prompt))
        review = self._validate(payload, present)
        self._record("review", review=review)
        return review

    @staticmethod
    def _validate(payload: Any, present: dict[str, InsightObject]) -> dict:
        if not isinstance(payload, dict):
            return dict(EMPTY_REVIEW)
        known_ids = {cid for insight in present.values() for cid in insight.selected_artifacts}

        def links(item: dict, text_key: str) -> dict | None:
            agents = [a for a in item.get("agents") or [] if a in present]
            text = item.get(text_key)
            if len(set(agents)) < 2 or not isinstance(text, str) or not text.strip():
                return None
            artifacts = [a for a in item.get("artifacts") or [] if a in known_ids]
            return {"agents": sorted(set(agents)), text_key: text.strip(), "artifacts": artifacts}

        agreements = [x for x in (links(i, "point") for i in payload.get("agreements") or [] if isinstance(i, dict)) if x]
        tensions = [x for x in (links(i, "issue") for i in payload.get("tensions") or [] if isinstance(i, dict)) if x]
        weak = []
        for item in payload.get("weak_findings") or []:
            if not isinstance(item, dict):
                continue
            agent, index, reason = item.get("agent"), item.get("finding"), item.get("reason")
            try:
                index = int(index)
            except (TypeError, ValueError):
                continue
            if agent in present and 0 <= index < len(present[agent].key_findings) and isinstance(reason, str):
                weak.append({
                    "agent": agent,
                    "finding": index,
                    "text": present[agent].key_findings[index],
                    "reason": reason.strip(),
                })
        return {"agreements": agreements, "tensions": tensions, "weak_findings": weak}
