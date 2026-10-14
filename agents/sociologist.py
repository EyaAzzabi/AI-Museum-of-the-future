"""
Sociologist Agent — AI Museum of the Future
=============================================
Author  : EyaRachdi
Branch  : EyaRachdi_sociologistAgent
Model   : configured via agents/llm_config.py (LLM_MODEL)
Purpose : Analyze contemporary Tunisian society (2020-2026) through a sociological
          lens, identify social patterns, and produce structured insights for the
          museum exhibition.

Workflow (7 steps):
    1. Define objective & load prompt
    2. Choose LLM model
    3. Retrieve knowledge from RAG (Supabase)
    4. Define tools & actions
    5. Design workflow & instructions (Chain of Thought)
    6. Validate & self-check output
    7. Return structured InsightObject

Prompt Engineering techniques used:
    - Role prompting     : Dr. Amira persona
    - Chain of Thought   : 5-step reasoning before output
    - Few-shot examples  : Embedded in system prompt
    - Structured output  : Strict JSON schema
    - Self-consistency   : Agent validates its own output
    - Context injection  : RAG chunks injected into user prompt
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject
from agents.sociologist_tools import (
    SOCIAL_THEME_KEYWORDS,
    EvidenceBundle,
    build_evidence_bundle,
    compute_theme_coverage,
    extract_dates,
    filter_by_theme,
    format_chunks_for_prompt,
    score_evidence_relevance,
)
from rag.hyde_retriever import HyDERetriever

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

MAX_RETRIES    = 3                   # Retries on LLM failure
MIN_FINDINGS   = 3                   # Minimum findings required
MIN_CONFIDENCE = 0.4                 # Minimum confidence score to accept output

# Core social themes to always analyze for Tunisia
CORE_THEMES = [
    "politics_civic",
    "economy_inequality",
    "gender_women",
    "youth_education",
    "migration_diaspora",
    "culture_identity",
    "digital_social_media",
]

# ── Few-shot example for prompt engineering ───────────────────────────────────

FEW_SHOT_EXAMPLE = """
EXAMPLE of a good sociological finding (for reference):
---
Finding: "The 2021 constitutional crisis accelerated Tunisia's shift from participatory
democracy toward centralized executive power, mirroring social fatigue with post-2011
political fragmentation — a pattern sociologists call 'democratic backsliding under
popular pressure'."

Why this is good:
- Names a specific event (2021 constitutional crisis)
- Identifies a social dynamic (democratic backsliding)
- Provides sociological framing (popular pressure)
- Connects micro (public mood) to macro (institutional change)
---
"""

# ── Self-validation schema ────────────────────────────────────────────────────

REQUIRED_OUTPUT_KEYS = {
    "agent", "perspective", "key_findings", "selected_artifacts",
    "themes_detected", "confidence_score"
}


# ── Agent ─────────────────────────────────────────────────────────────────────

class SociologistAgent(BaseAgent):
    """
    Sociologist Agent — analyzes Tunisian society 2020-2026.

    Can operate in two modes:
    - With retriever (full RAG mode): fetches evidence from Supabase
    - Without retriever (direct mode): uses provided chunks directly

    Parameters
    ----------
    openai_client : OpenAI client instance
    retriever     : Optional Retriever instance for RAG queries
    prompt_path   : Optional path to prompt template (defaults to prompts/sociologist.md)
    """

    name = "sociologist"
    focus = "Social transformations, collective behaviour and inequalities of 2020-2026"
    max_evidence = 40  # HyDE context; _prepare_evidence keeps the 20 most relevant

    # ── Step 1 — Define objective ─────────────────────────────────────────────
    AGENT_OBJECTIVE = (
        "Analyze contemporary Tunisian society (2020-2026) to identify key social "
        "transformations, collective behaviors, and cultural dynamics that future "
        "historians would consider significant. Produce structured museum-ready insights."
    )

    def __init__(
        self,
        openai_client: Any,
        retriever: Any = None,
        prompt_path: str | Path | None = None,
    ):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "sociologist.md")

        # Step 4 — Tools & actions
        self.retriever = retriever

        # Same injected client for HyDE and analysis, so the pipeline and tests control it
        self._llm_client = openai_client

        # HyDE Retriever — Advanced RAG (built on first use, see search_own_evidence)
        self._hyde_retriever = HyDERetriever(
            retriever=retriever,
            llm_client=self._llm_client,
            top_k=10,
        ) if retriever is not None else None

        self._tools_available = {
            "rag_retrieval":        retriever is not None,
            "hyde_retrieval":       retriever is not None,
            "query_expansion":      True,
            "theme_filtering":      True,
            "source_filtering":     True,
            "theme_coverage":       True,
            "date_extraction":      True,
            "evidence_scoring":     True,
            "llm_analysis":         self._llm_client is not None,
            "self_validation":      True,
        }

        logger.info("[SociologistAgent] Initialized | Tools: %s", self._tools_available)

    # ── Step 5 — Main workflow ────────────────────────────────────────────────

    def run(self, chunks: list[Any]) -> InsightObject:
        """
        Main workflow — 7-step process from evidence to museum insight.

        Parameters
        ----------
        chunks : List of RetrievalResult or Chunk objects (from RAG or direct input)

        Returns
        -------
        InsightObject with perspective, key_findings, and selected_artifacts
        """
        logger.info("[SociologistAgent] Starting analysis | %d input chunks", len(chunks))

        # ── Step 3a — Input chunks + HyDE retrieval (BaseAgent.gather_evidence) ─
        all_chunks = self.gather_evidence(chunks)
        if not all_chunks:
            return self.abstain("no evidence")

        # ── Step 3b — Score and filter evidence ──────────────────────────────
        all_chunks = self._prepare_evidence(all_chunks)

        # ── Step 5a — Build system prompt (Role + CoT + Few-shot) ────────────
        system_prompt = self._build_system_prompt(all_chunks)

        # ── Step 5b — Build user prompt (Context injection) ──────────────────
        user_prompt = self._build_user_prompt(all_chunks)

        # ── Step 5c — Call LLM with Chain of Thought ─────────────────────────
        payload = self._call_llm_with_retry(system_prompt, user_prompt)

        # ── Step 6 — Validate & self-check output ────────────────────────────
        payload = self._validate_and_fix(payload, all_chunks)

        # ── Step 7 — Return structured InsightObject ─────────────────────────
        return self._build_insight(payload, all_chunks)

    # ── Step 3 — Evidence retrieval & preparation ────────────────────────────

    def search_own_evidence(self) -> list[Any]:
        """The sociologist's own search is HyDE over its core themes."""
        if self._hyde_retriever is None or self._hyde_retriever.retriever is not self.retriever:
            self._hyde_retriever = HyDERetriever(retriever=self.retriever, llm_client=self.openai_client, top_k=10)
        logger.info("[SociologistAgent] RAG retrieval enabled — fetching additional evidence...")
        return self._retrieve_evidence().chunks

    def _retrieve_evidence(self) -> EvidenceBundle:
        """
        Retrieve evidence using HyDE (Advanced RAG) pipeline.
        Falls back to standard retrieval if HyDE fails.
        """
        # Try HyDE first (Advanced RAG)
        if self._hyde_retriever is not None:
            try:
                logger.info("[SociologistAgent] Using HyDE Advanced RAG pipeline...")
                chunks = self._hyde_retriever.build_enriched_context(
                    themes=CORE_THEMES,
                    top_k_per_theme=5,
                )
                if chunks:
                    logger.info("[SociologistAgent] HyDE retrieved %d chunks", len(chunks))
                    return EvidenceBundle(
                        query="HyDE multi-theme",
                        theme=", ".join(CORE_THEMES),
                        chunks=chunks,
                        total_retrieved=len(chunks),
                    )
            except Exception as e:
                logger.warning("[SociologistAgent] HyDE failed: %s — falling back to standard RAG", e)

        # Fallback to standard retrieval
        try:
            return build_evidence_bundle(
                retriever=self.retriever,
                themes=CORE_THEMES,
                top_k_per_theme=5,
            )
        except Exception as e:
            logger.warning("[SociologistAgent] Standard RAG also failed: %s", e)
            return EvidenceBundle(query="", theme="", chunks=[])

    def _prepare_evidence(self, chunks: list[Any]) -> list[Any]:
        """Score, rank, and limit chunks for optimal LLM context."""
        if not chunks:
            return chunks

        # Score by relevance to social themes
        scored = score_evidence_relevance(chunks, CORE_THEMES)

        # Take top 20 most relevant chunks (stays within token limits)
        top_chunks = [chunk for chunk, _ in scored[:20]]

        logger.info("[SociologistAgent] Evidence prepared: %d → %d chunks", len(chunks), len(top_chunks))
        return top_chunks

    # ── Step 5a — System prompt (Role + CoT + Few-shot) ──────────────────────

    def _build_system_prompt(self, chunks: list[Any]) -> str:
        """Build the system prompt with role, CoT instructions, and few-shot example."""

        # Compute stats to inject into system prompt
        coverage   = compute_theme_coverage(chunks)
        date_range = extract_dates(chunks)
        top_themes = list(coverage.keys())[:5] if coverage else ["general"]

        date_str = (
            f"{date_range[0]} to {date_range[1]}"
            if date_range[0] and date_range[1]
            else "2020-2026"
        )

        return f"""You are Dr. Amira, a sociologist specializing in North African societies,\
 assigned to the "AI Museum of the Future" project.

## YOUR OBJECTIVE
{self.AGENT_OBJECTIVE}

## YOUR ANALYTICAL FRAMEWORK — Chain of Thought (follow these steps)
Before producing your final JSON output, reason through these steps internally:

STEP 1 — CLASSIFY: Read all evidence chunks. Which social themes are present?
         Focus especially on: {', '.join(top_themes)}

STEP 2 — IDENTIFY PATTERNS: For each theme found, ask:
         - What is CHANGING in Tunisian society?
         - What TENSIONS or CONTRADICTIONS exist?
         - What would a future historian find SURPRISING about this era?

STEP 3 — SELECT ARTIFACTS: Choose the 2-4 most sociologically significant chunks.
         These should capture what DEFINED Tunisian society in {date_str}.

STEP 4 — FRAME THE ERA: Write a 2-3 sentence sociological framing statement.
         Speak as if addressing a museum visitor 100 years from now.

STEP 5 — FORMULATE FINDINGS: Write 4-6 specific, evidence-grounded findings.
         Each finding must name a specific social dynamic, not a generic observation.

## EXAMPLE OF A GOOD FINDING
{FEW_SHOT_EXAMPLE}

## OUTPUT RULES
- Respond with valid JSON ONLY — no markdown, no explanation outside JSON
- Minimum {MIN_FINDINGS} key_findings required
- Every finding ends with the exact [ID] of the evidence it rests on, e.g. "... [abc-123]".
  Findings without a valid [ID] are discarded.
- confidence_score: float 0.0-1.0 reflecting how well evidence supports your analysis
- If evidence is thin, say so in evidence_gaps
"""

    # ── Step 5b — User prompt (Context injection) ─────────────────────────────

    def _build_user_prompt(self, chunks: list[Any]) -> str:
        """Build user prompt by injecting formatted evidence chunks."""

        # Load and render prompt template
        template = self._load_prompt_template()

        # Format chunks for injection
        formatted_chunks = format_chunks_for_prompt(
            chunks,
            max_chars_per_chunk=400,
            max_total_chars=6000,
        )

        if template:
            # Use template with {chunks} placeholder
            user_prompt = template.replace("{chunks}", formatted_chunks)
            user_prompt = user_prompt.replace("{agent}", "sociologist")
            user_prompt = user_prompt.replace("{system}", self.AGENT_OBJECTIVE)
        else:
            # Fallback if template not found
            user_prompt = f"""Analyze the following evidence about Tunisian society (2020-2026):

---
EVIDENCE:
{formatted_chunks}
---

Produce a structured sociological analysis in the JSON format specified in your instructions.
"""

        return user_prompt

    # ── Step 5c — LLM call with retry ────────────────────────────────────────

    def _call_llm_with_retry(self, system_prompt: str, user_prompt: str) -> dict:
        """Call the LLM through BaseAgent._call_llm, retrying on failure.

        Raises ValueError once all attempts fail, so the pipeline records the
        perspective as missing instead of passing placeholder findings to the curator.
        """
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("[SociologistAgent] LLM call attempt %d/%d", attempt, MAX_RETRIES)
                payload = self._call_llm(system_prompt, user_prompt)
                logger.info("[SociologistAgent] LLM call succeeded on attempt %d", attempt)
                return payload

            except Exception as e:
                last_error = e
                import time
                wait = 2 ** attempt
                logger.warning("[SociologistAgent] LLM attempt %d failed: %s — waiting %ds", attempt, e, wait)
                if attempt < MAX_RETRIES:
                    time.sleep(wait)

        logger.error("[SociologistAgent] All %d LLM attempts failed. Last error: %s", MAX_RETRIES, last_error)
        raise ValueError(f"Sociologist LLM call failed after {MAX_RETRIES} attempts: {last_error}") from last_error

    # ── Step 6 — Self-validation ──────────────────────────────────────────────

    def _validate_and_fix(self, payload: dict, chunks: list[Any]) -> dict:
        """
        Validate LLM output and fix missing/invalid fields.
        This is the self-consistency check.
        """
        if not isinstance(payload, dict):
            logger.warning("[SociologistAgent] Invalid payload type: %s — using fallback", type(payload))
            return self._fallback_payload()

        # Check required keys
        missing = REQUIRED_OUTPUT_KEYS - set(payload.keys())
        if missing:
            logger.warning("[SociologistAgent] Missing keys: %s — adding defaults", missing)
            if "agent" not in payload:
                payload["agent"] = "sociologist"
            if "perspective" not in payload:
                payload["perspective"] = "Social patterns observed in Tunisian society 2020-2026."
            if "key_findings" not in payload:
                payload["key_findings"] = ["Analysis based on available evidence."]
            if "selected_artifacts" not in payload:
                payload["selected_artifacts"] = [
                    getattr(c, "chunk_id", "") or getattr(c, "document_id", "")
                    for c in chunks[:2]
                ]
            if "themes_detected" not in payload:
                payload["themes_detected"] = list(compute_theme_coverage(chunks).keys())[:5]
            if "confidence_score" not in payload:
                payload["confidence_score"] = 0.5

        # Validate findings count. Short output is kept as is: placeholder
        # findings would reach the curator as if they were real analysis.
        findings = payload.get("key_findings", [])
        if len(findings) < MIN_FINDINGS:
            logger.warning(
                "[SociologistAgent] Only %d findings (expected at least %d) — evidence may be thin",
                len(findings), MIN_FINDINGS
            )

        # Validate confidence score
        try:
            confidence = float(payload.get("confidence_score", 0.5))
            payload["confidence_score"] = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            payload["confidence_score"] = 0.5

        # Add metadata
        payload["analyst"]    = "Dr. Amira — Sociologist, AI Museum of the Future"
        payload["era"]        = "Tunisia 2020-2026"
        payload["model_used"] = self.model
        payload["evidence_count"] = len(chunks)

        logger.info(
            "[SociologistAgent] Validation passed | confidence=%.2f | findings=%d",
            payload["confidence_score"], len(payload["key_findings"])
        )

        return payload

    # ── Step 7 — Build InsightObject ──────────────────────────────────────────

    def _build_insight(self, payload: dict, chunks: list[Any]) -> InsightObject:
        """Convert validated payload to InsightObject for the pipeline."""

        findings  = [str(f) for f in payload.get("key_findings", []) if f]
        input_ids = [
            cid for c in chunks
            if (cid := getattr(c, "chunk_id", "") or getattr(c, "document_id", ""))
        ]
        # Keep only artifacts that exist in the evidence (no hallucinated IDs)
        artifacts = [str(a) for a in payload.get("selected_artifacts", []) if str(a) in input_ids]

        # Fallback artifacts from input chunks
        if not artifacts:
            artifacts = input_ids[:2]

        # Analysis metadata goes to the log, not into the exhibition text
        themes   = payload.get("themes_detected", [])
        conf     = payload.get("confidence_score", 0.5)
        evidence = payload.get("evidence_count", len(chunks))

        logger.info(
            "[SociologistAgent] Insight built | %d findings | %d artifacts | themes=%s | evidence=%d chunks | confidence=%.0f%%",
            len(findings), len(artifacts), ", ".join(themes[:3]) if themes else "general", evidence, conf * 100
        )

        # Shared rule: every finding must cite the evidence (BaseAgent.finalize)
        return self.finalize(payload, chunks)

    # ── Fallback ──────────────────────────────────────────────────────────────

    def _fallback_payload(self) -> dict:
        """Return a safe fallback payload when LLM fails completely."""
        return {
            "agent":             "sociologist",
            "analyst":           "Dr. Amira — Sociologist, AI Museum of the Future",
            "era":               "Tunisia 2020-2026",
            "perspective":       "Analysis unavailable due to LLM failure. Evidence collected but not processed.",
            "themes_detected":   [],
            "key_findings":      [
                "LLM analysis failed — raw evidence available in the knowledge base.",
                "Manual review of collected data recommended.",
                "Re-run with a valid LLM_API_KEY to generate full analysis.",
            ],
            "selected_artifacts":  [],
            "artifact_justification": "N/A",
            "confidence_score":   0.0,
            "evidence_gaps":     ["LLM call failed — analysis incomplete"],
            "model_used":        self.model,
        }
