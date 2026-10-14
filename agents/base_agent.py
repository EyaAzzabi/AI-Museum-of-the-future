"""Shared design for every agent of the museum.

A specialist only declares *what* it looks at (name, focus, search queries,
prompt); BaseAgent does the rest the same way for all of them:

  gather_evidence   input chunks + the agent's own hybrid search
  format_evidence   "[chunk_id] (year · source/category · title) text"
  _call_llm         JSON call with retries, optional disk cache, run recording
  finalize          per-finding citation check -> InsightObject, or abstain

Citation rule (applies to every specialist): each key finding must contain at
least one ``[chunk_id]`` and every ID it cites must be in the evidence it was
given; other findings are dropped. If nothing
cited remains, the agent abstains (empty InsightObject) and the curator lists
the perspective as missing, instead of filling the gap with generic text.
LLM/provider errors are raised so the pipeline records them the same way.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from abc import ABC
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from agents.llm_config import get_model

logger = logging.getLogger(__name__)

CITATION = re.compile(r"\[([^\[\]]+)\]")
RETRYABLE_ERRORS = ("503", "429", "high demand", "UNAVAILABLE", "quota", "json_validate_failed")
EVIDENCE_CHARS = 700


@dataclass
class InsightObject:
    agent: str
    perspective: str
    key_findings: list[str]
    selected_artifacts: list[str]
    # Cited chunk ID -> {"content", "title", "source", "category", "year", "url"}.
    # Lets the reviewer, the curator and the fact-checker read what was cited.
    evidence: dict[str, dict] = field(default_factory=dict)


def chunk_id_of(chunk: Any) -> str:
    def read(name: str) -> Any:
        return chunk.get(name) if isinstance(chunk, Mapping) else getattr(chunk, name, None)

    return str(read("chunk_id") or read("id") or read("document_id") or "")


def as_result(chunk: Any):
    """Normalise a RetrievalResult, dict or object into a RetrievalResult."""
    from rag.vector_store.retriever import RetrievalResult

    if isinstance(chunk, RetrievalResult):
        return chunk

    def read(name: str, default: Any = None) -> Any:
        return chunk.get(name, default) if isinstance(chunk, Mapping) else getattr(chunk, name, default)

    if isinstance(chunk, str):
        return RetrievalResult(chunk_id="", document_id="", content=chunk)
    metadata = read("metadata") or {}
    return RetrievalResult(
        chunk_id=chunk_id_of(chunk),
        document_id=str(read("document_id") or ""),
        content=str(read("content") or ""),
        metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
        similarity=float(read("similarity") or 0.0),
    )


def citations_in(text: str) -> list[str]:
    """IDs cited in a finding: "[a]", "[a, b]" and "[a; b]" are all accepted."""
    refs: list[str] = []
    for group in CITATION.findall(text):
        refs.extend(part.strip() for part in re.split(r"[;,]", group) if part.strip())
    return refs


class BaseAgent(ABC):
    model_env_var = "LLM_MODEL"
    name = ""                                  # key in the pipeline and InsightObject.agent
    focus = ""                                 # one line: what this specialist looks at
    system_prompt = ""
    search_queries: tuple[str, ...] = ()       # the agent's own retrieval queries
    search_keywords: tuple[str, ...] = ()      # exact names/terms for the keyword channel
    search_categories: tuple[str, ...] | None = None
    search_exclude_categories: tuple[str, ...] = ()
    search_k = 8
    max_evidence = 14

    def __init__(self, openai_client: Any, prompt_path: str | Path):
        self.openai_client = openai_client
        self.prompt_path = Path(prompt_path)
        self.retriever: Any = None             # set by the pipeline (HybridRetriever or Retriever)
        self.recorder: Any = None              # set by the pipeline (agents.run_log.RunRecorder)

    @property
    def model(self) -> str:
        return get_model(self.model_env_var)

    # ── Template method ──────────────────────────────────────────────────────

    def run(self, chunks: Any) -> InsightObject:
        evidence = self.gather_evidence(chunks)
        if not evidence:
            return self.abstain("no evidence")
        user_prompt = self._render_prompt(evidence, self.name, self.system_prompt)
        payload = self._call_llm(self.system_prompt, user_prompt)
        return self.finalize(payload, evidence)

    # ── Evidence ─────────────────────────────────────────────────────────────

    def gather_evidence(self, chunks: Any) -> list:
        """Input chunks first, then the agent's own search results, deduplicated by ID."""
        evidence = [as_result(c) for c in (chunks or []) if chunk_id_of(c) or isinstance(c, str)]
        own = self.search_own_evidence() if self.retriever is not None else []
        seen = {e.chunk_id for e in evidence}
        for result in own:
            if result.chunk_id and result.chunk_id not in seen:
                evidence.append(as_result(result))
                seen.add(result.chunk_id)
        evidence = evidence[: self.max_evidence]
        self._record("evidence", evidence=[
            {"chunk_id": e.chunk_id, "category": e.metadata.get("category"), "year": e.metadata.get("year"),
             "channels": e.metadata.get("channels"), "content": e.content[:200]}
            for e in evidence
        ], own_search=len(own))
        return evidence

    def search_own_evidence(self) -> list:
        if not self.search_queries:
            return []
        search_many = getattr(self.retriever, "search_many", None)
        try:
            if search_many is None:  # plain vector Retriever
                results = []
                for query in self.search_queries:
                    results.extend(self.retriever.retrieve(query))
                return results
            from rag.vector_store.hybrid_retriever import SearchFilters

            base = getattr(self.retriever, "default_filters", None) or SearchFilters()
            filters = replace(
                base,
                categories=self.search_categories or base.categories,
                exclude_categories=tuple(base.exclude_categories) + tuple(self.search_exclude_categories),
            )
            return search_many(
                list(self.search_queries),
                k=self.search_k,
                filters=filters,
                keywords=list(self.search_keywords) or None,
                rerank_query=self.focus or None,
            )
        except Exception as exc:  # noqa: BLE001 - own search is a bonus, never fatal
            logger.warning("[%s] own search failed: %s", self.name, exc)
            return []

    @staticmethod
    def format_evidence(chunk: Any) -> str:
        """One evidence line: ID first so the model can cite it, then provenance, then text."""
        result = as_result(chunk)
        meta = result.metadata or {}
        provenance = " · ".join(str(p) for p in (
            meta.get("year"),
            "/".join(str(x) for x in (meta.get("source"), meta.get("category")) if x),
            (meta.get("title") or "")[:90],
        ) if p)
        content = result.content[:EVIDENCE_CHARS]
        prefix = f"[{result.chunk_id}] " if result.chunk_id else ""
        return f"{prefix}({provenance}) {content}" if provenance else f"{prefix}{content}"

    # ── Output validation ────────────────────────────────────────────────────

    def finalize(self, payload: Any, evidence: list) -> InsightObject:
        by_id = {e.chunk_id: e for e in (as_result(c) for c in evidence) if e.chunk_id}
        if not isinstance(payload, dict):
            return self.abstain("response is not a JSON object")
        perspective = payload.get("perspective")
        raw_findings = payload.get("key_findings")
        if not isinstance(perspective, str) or not perspective.strip():
            return self.abstain("no perspective")
        if not isinstance(raw_findings, list):
            return self.abstain("key_findings is not a list")

        findings: list[str] = []
        cited: list[str] = []
        dropped = 0
        for finding in raw_findings:
            if not isinstance(finding, str) or not finding.strip():
                continue
            # Kept only if it cites something and every citation is real: a claim
            # resting partly on an unknown source is partly unsupported.
            refs = citations_in(finding)
            if not refs or any(r not in by_id for r in refs):
                dropped += 1
                continue
            text = finding.strip()
            if text not in findings:
                findings.append(text)
            cited.extend(r for r in refs if r not in cited)
        if dropped:
            logger.info("[%s] dropped %d finding(s) without a valid [chunk_id] citation", self.name, dropped)
        if not findings:
            return self.abstain("no finding cites the evidence")

        selected = list(cited)
        extra = payload.get("selected_artifacts")
        for item in extra if isinstance(extra, list) else []:
            if isinstance(item, str) and item.strip() in by_id and item.strip() not in selected:
                selected.append(item.strip())
        insight = InsightObject(
            agent=self.name,
            perspective=perspective.strip(),
            key_findings=findings,
            selected_artifacts=selected,
            evidence={cid: self._evidence_entry(by_id[cid]) for cid in selected},
        )
        self._record("insight", insight=insight, dropped_findings=dropped)
        return insight

    @staticmethod
    def _evidence_entry(result: Any) -> dict:
        meta = result.metadata or {}
        return {
            "content": result.content[:EVIDENCE_CHARS],
            "title": meta.get("title"),
            "source": meta.get("source"),
            "category": meta.get("category"),
            "year": meta.get("year"),
            "url": meta.get("url"),
        }

    def abstain(self, reason: str) -> InsightObject:
        logger.info("[%s] abstains: %s", self.name, reason)
        self._record("abstain", reason=reason)
        return InsightObject(agent=self.name, perspective="", key_findings=[], selected_artifacts=[])

    # ── LLM ──────────────────────────────────────────────────────────────────

    def _call_llm(self, system: str, user: str) -> dict:
        if self.openai_client is None:
            raise ValueError("openai_client is required for LLM calls.")

        cached = self._cache_get(system, user)
        if cached is not None:
            self._record("llm_call", model=self.model, cached=True, system=system, user=user, response=cached, seconds=0)
            return cached

        models_to_try = [self.model]
        if "gemini" in self.model.lower():
            for alt in ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-flash-latest"]:
                if alt not in models_to_try:
                    models_to_try.append(alt)

        started = time.monotonic()
        response = None
        last_exc = None
        for m in models_to_try:
            for attempt in range(3):
                try:
                    response = self.openai_client.chat.completions.create(
                        model=m,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    )
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if any(code in str(exc) for code in RETRYABLE_ERRORS):
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    break
            if last_exc is None and response is not None:
                break

        if last_exc is not None:
            self._record("llm_call", model=self.model, system=system, user=user, error=str(last_exc),
                         seconds=round(time.monotonic() - started, 2))
            raise ValueError(f"LLM call failed: {last_exc}") from last_exc

        parsed = self._parse_response(response)
        self._record("llm_call", model=self.model, system=system, user=user, response=parsed,
                     seconds=round(time.monotonic() - started, 2))
        self._cache_put(system, user, parsed)
        return parsed

    @staticmethod
    def _parse_response(response: Any) -> dict:
        if isinstance(response, dict):
            return response
        if hasattr(response, "choices") and response.choices:
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("LLM returned empty content.")
            try:
                parsed = json.loads(content)
            except TypeError:
                parsed = content
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("LLM response was not a JSON object.")
        payload = getattr(response, "model_dump", lambda: getattr(response, "__dict__", None))()
        if isinstance(payload, dict):
            return payload
        raise ValueError("Malformed LLM response.")

    # Opt-in response cache (LLM_CACHE_DIR): identical prompts are answered from
    # disk, which makes evaluation re-runs free and reproducible.
    def _cache_path(self, system: str, user: str) -> Path | None:
        root = os.getenv("LLM_CACHE_DIR")
        if not root:
            return None
        key = hashlib.sha256(f"{self.model}\0{system}\0{user}".encode("utf-8")).hexdigest()
        return Path(root) / f"{key}.json"

    def _cache_get(self, system: str, user: str) -> dict | None:
        path = self._cache_path(system, user)
        if path is None or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _cache_put(self, system: str, user: str, payload: dict) -> None:
        path = self._cache_path(system, user)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _record(self, kind: str, **data: Any) -> None:
        if self.recorder is not None:
            self.recorder.record(kind, agent=self.name or type(self).__name__, **data)

    # ── Prompt ───────────────────────────────────────────────────────────────

    def _load_prompt_template(self) -> str:
        """Prompt file body; a leading "## vN" changelog (up to the first ---) is not sent."""
        if not self.prompt_path.exists():
            return ""
        template = self.prompt_path.read_text(encoding="utf-8")
        if template.lstrip().startswith("## v"):
            _, sep, body = template.partition("\n---\n")
            if sep:
                return body.lstrip()
        return template

    def _render_prompt(self, chunks: Any, agent_name: str, system_prompt: str) -> str:
        template = self._load_prompt_template()
        chunk_text = "\n".join(
            self.format_evidence(chunk) for chunk in chunks
        ) if isinstance(chunks, list) else str(chunks)
        return (template.replace("{chunks}", chunk_text)
                .replace("{agent}", agent_name)
                .replace("{system}", system_prompt))
