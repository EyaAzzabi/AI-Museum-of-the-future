"""
HyDE Retriever — Hypothetical Document Embedding
==================================================
Author  : EyaRachdi
Branch  : EyaRachdi_sociologistAgent

Advanced RAG pipeline for the Sociologist Agent:

    Step 1 — Query Expansion
        Expand the original query with sociological synonyms and related terms
        to improve recall.

    Step 2 — HyDE (Hypothetical Document Embedding)
        Ask the LLM to generate a hypothetical document that WOULD answer
        the query. Embed this document and search for similar real chunks.
        This bridges the vocabulary gap between the query and the corpus.

    Step 3 — Vector Retrieval
        Search Supabase vector store using the HyDE embedding (top-k=10).

    Step 4 — Reranking
        Score and filter results by thematic relevance using keyword matching.

    Step 5 — Deduplication & return

Why HyDE for sociology?
    Sociological queries are abstract ("social inequality", "gender dynamics")
    but the corpus contains concrete text ("40% youth unemployment", "domestic
    violence rose 30%"). HyDE generates a hypothetical document that uses the
    same concrete language as the corpus, dramatically improving retrieval.

Reference: Gao et al. (2022) "Precise Zero-Shot Dense Retrieval without
    Relevance Labels" — https://arxiv.org/abs/2212.10496
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Sociological query expansion map ─────────────────────────────────────────
# Maps abstract sociological concepts to concrete search terms
QUERY_EXPANSION_MAP: dict[str, list[str]] = {
    "politics_civic": [
        "Kais Saied parliament suspension constitution elections democracy Tunisia",
        "political crisis civil rights freedom press protest civic society",
    ],
    "economy_inequality": [
        "unemployment inflation poverty GDP crisis IMF debt Tunisia economy",
        "youth unemployment rural urban divide inequality wages salaries",
    ],
    "gender_women": [
        "women rights domestic violence gender equality feminist Tunisia",
        "violence femmes droits egalite harcelement lockdown pandemic",
    ],
    "youth_education": [
        "youth unemployment education university students future Tunisia",
        "jeunesse chomage diplome formation avenir espoir desespoir",
    ],
    "migration_diaspora": [
        "harraga irregular migration Mediterranean Europe asylum Tunisia",
        "emigration diaspora boat crossing border death sea",
    ],
    "culture_identity": [
        "culture identity heritage music cinema festival Carthage Tunisia",
        "patrimoine identite arabe berbere amazigh tradition religion",
    ],
    "digital_social_media": [
        "TikTok Facebook social media internet digital Tunisia youth",
        "reseaux sociaux numerique startup innovation technologie",
    ],
    "environment_urban": [
        "water scarcity drought climate change pollution Tunisia environment",
        "eau secheresse changement climatique energie solaire desert",
    ],
    "health_wellbeing": [
        "COVID pandemic health hospital doctor vaccine mental health Tunisia",
        "sante pandemie confinement lockdown bien-etre maladie",
    ],
    "religion_secularism": [
        "Islam mosque secularism religion freedom Tunisia society",
        "islamisme laicite ramadan identite religieuse liberte culte",
    ],
}


# ── HyDE prompt templates ─────────────────────────────────────────────────────

HYDE_SYSTEM_PROMPT = """You are a Tunisian sociologist writing a brief factual passage 
about contemporary Tunisian society (2020-2026). 
Write as if you are describing real documented evidence — use specific numbers, 
events, and concrete details when possible.
Keep your response to 3-5 sentences maximum.
Do NOT use JSON — write plain prose."""

HYDE_USER_TEMPLATE = """Write a short factual passage about the following aspect of 
Tunisian society between 2020 and 2026:

Topic: {topic}

The passage should sound like it comes from a real news article, academic paper, 
or Wikipedia entry about Tunisia in this period. Be specific and concrete."""


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class HyDEResult:
    """Result from the HyDE retrieval pipeline."""
    theme: str
    original_query: str
    expanded_query: str
    hypothetical_document: str
    retrieved_chunks: list[Any] = field(default_factory=list)
    total_retrieved: int = 0
    hyde_used: bool = True


# ── HyDE Retriever ────────────────────────────────────────────────────────────

class HyDERetriever:
    """
    Advanced RAG retriever using Hypothetical Document Embedding (HyDE).

    Parameters
    ----------
    retriever    : Standard Retriever instance (from rag/vector_store/retriever.py)
    llm_client   : LLM client for generating hypothetical documents
    embedder     : Local embedder for encoding hypothetical documents
    top_k        : Number of chunks to retrieve per query
    """

    def __init__(
        self,
        retriever: Any,
        llm_client: Any,
        embedder: Any = None,
        top_k: int = 10,
    ):
        self.retriever  = retriever
        self.llm_client = llm_client
        self.embedder   = embedder
        self.top_k      = top_k

    # ── Step 1 — Query Expansion ──────────────────────────────────────────────

    def expand_query(self, theme: str, original_query: str) -> str:
        """
        Expand the original query with sociological synonyms.
        Combines the original query with theme-specific expansion terms.
        """
        expansions = QUERY_EXPANSION_MAP.get(theme, [])
        if not expansions:
            return original_query

        # Take first expansion and combine with original
        expanded = f"{original_query} {expansions[0]}"
        logger.debug("[HyDE] Expanded query: %s", expanded[:100])
        return expanded

    # ── Step 2 — Generate Hypothetical Document ───────────────────────────────

    def generate_hypothetical_doc(self, theme: str, query: str) -> str:
        """
        Ask the LLM to generate a hypothetical document that would answer
        the query. This is the core of HyDE.

        Falls back to the expanded query if LLM fails.
        """
        if self.llm_client is None:
            logger.warning("[HyDE] No LLM client — skipping hypothetical doc generation")
            return query

        topic = f"{theme.replace('_', ' ')} in Tunisia 2020-2026: {query}"

        try:
            from agents.llm_config import get_model
            model = get_model()

            response = self.llm_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": HYDE_SYSTEM_PROMPT},
                    {"role": "user",   "content": HYDE_USER_TEMPLATE.format(topic=topic)},
                ],
                # Reasoning models (the default gpt-oss) spend part of this budget
                # thinking; 200 often left an empty or cut-off passage.
                max_tokens=1000,
                temperature=0.3,  # Low temperature for factual consistency
            )
            hypo_doc = (response.choices[0].message.content or "").strip()
            if not hypo_doc:
                logger.warning("[HyDE] Empty hypothetical doc — using expanded query")
                return query
            logger.info("[HyDE] Generated hypothetical doc (%d chars)", len(hypo_doc))
            return hypo_doc

        except Exception as e:
            logger.warning("[HyDE] Hypothetical doc generation failed: %s — using expanded query", e)
            return query

    # ── Step 3 — Embed Hypothetical Document & Retrieve ───────────────────────

    def retrieve_with_hyde(self, theme: str, query: str, hypo_doc: str | None = None) -> list[Any]:
        """
        Full HyDE retrieval pipeline for a single theme:
        1. Expand query
        2. Generate hypothetical document
        3. Embed hypothetical document
        4. Search vector store with HyDE embedding
        """
        if self.retriever is None:
            return []

        # Step 1 — Expand query
        expanded_query = self.expand_query(theme, query)

        # Step 2 — Generate hypothetical document (unless the caller already did)
        if hypo_doc is None:
            hypo_doc = self.generate_hypothetical_doc(theme, expanded_query)

        # Step 3 — Use hypothetical doc as search query
        # The retriever embeds it and searches Supabase
        try:
            self.retriever.match_count = self.top_k
            results = self.retriever.retrieve(query=hypo_doc, rerank=False)
            if not results and hypo_doc != expanded_query:
                results = self.retriever.retrieve(query=expanded_query, rerank=False)
            logger.info("[HyDE] Retrieved %d chunks for theme '%s'", len(results), theme)
            return results
        except Exception as e:
            logger.warning("[HyDE] Retrieval failed for theme '%s': %s", theme, e)
            # Fallback to standard retrieval with expanded query
            try:
                results = self.retriever.retrieve(query=expanded_query, rerank=False)
                logger.info("[HyDE] Fallback retrieval: %d chunks", len(results))
                return results
            except Exception as e2:
                logger.error("[HyDE] Fallback retrieval also failed: %s", e2)
                return []

    # ── Step 4 — Rerank by thematic relevance ────────────────────────────────

    def rerank_by_theme(
        self,
        chunks: list[Any],
        themes: list[str],
        top_n: int = 15,
    ) -> list[Any]:
        """
        Rerank chunks by keyword relevance to social themes.
        Combines vector similarity score with keyword match score.
        """
        from agents.sociologist_tools import (
            SOCIAL_THEME_KEYWORDS,
            score_evidence_relevance,
        )
        scored = score_evidence_relevance(chunks, themes)
        return [chunk for chunk, _ in scored[:top_n]]

    # ── Main pipeline — retrieve for all themes ───────────────────────────────

    def retrieve_all_themes(
        self,
        themes: list[str],
        top_k_per_theme: int = 5,
    ) -> list[HyDEResult]:
        """
        Run the full HyDE pipeline for all given themes.
        Returns a list of HyDEResult objects, one per theme.
        """
        results = []

        for theme in themes:
            # Build base query from theme name
            base_query = f"Tunisia {theme.replace('_', ' ')} society 2020 2026"

            # Expand query (Step 1)
            expanded = self.expand_query(theme, base_query)

            # Generate hypothetical doc (Step 2)
            hypo_doc = self.generate_hypothetical_doc(theme, expanded)

            # Retrieve (Step 3)
            chunks = self.retrieve_with_hyde(theme, base_query, hypo_doc=hypo_doc)

            results.append(HyDEResult(
                theme=theme,
                original_query=base_query,
                expanded_query=expanded,
                hypothetical_document=hypo_doc,
                retrieved_chunks=chunks,
                total_retrieved=len(chunks),
                hyde_used=True,
            ))

        return results

    # ── Full pipeline for Sociologist Agent ───────────────────────────────────

    def build_enriched_context(
        self,
        themes: list[str],
        top_k_per_theme: int = 5,
    ) -> list[Any]:
        """
        High-level method: runs HyDE for all themes, deduplicates,
        reranks, and returns the final list of chunks for the agent.

        This is the main entry point called by SociologistAgent.
        """
        all_chunks = []
        seen_ids: set[str] = set()

        # Run HyDE for each theme
        hyde_results = self.retrieve_all_themes(themes, top_k_per_theme)

        for hyde_result in hyde_results:
            for chunk in hyde_result.retrieved_chunks:
                cid = getattr(chunk, "chunk_id", "") or getattr(chunk, "document_id", "")
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    all_chunks.append(chunk)

        logger.info("[HyDE] Total unique chunks after deduplication: %d", len(all_chunks))

        # Rerank all chunks across all themes
        if all_chunks:
            all_chunks = self.rerank_by_theme(all_chunks, themes, top_n=20)
            logger.info("[HyDE] After reranking: %d chunks", len(all_chunks))

        return all_chunks
