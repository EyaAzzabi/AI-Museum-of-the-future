"""
Sociologist Agent Tools — AI Museum of the Future
===================================================
Author  : EyaRachdi
Branch  : EyaRachdi_sociologistAgent
Purpose : Tools used by the SociologistAgent to query the RAG knowledge base,
          filter evidence by social themes, and compute basic statistics.

Tools available:
    1. retrieve_social_evidence   — query Supabase vector store by social theme
    2. filter_by_theme            — filter already-retrieved chunks by theme keywords
    3. filter_by_source           — filter chunks by data source
    4. compute_theme_coverage     — count how many chunks cover each social theme
    5. extract_dates              — extract date range from a list of chunks
    6. format_chunks_for_prompt   — format chunks into clean text for LLM injection
    7. score_evidence_relevance   — score each chunk's relevance to a social query
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class EvidenceBundle:
    """A filtered, scored bundle of evidence chunks ready for the LLM."""
    query: str
    theme: str
    chunks: list[Any]
    theme_coverage: dict[str, int] = field(default_factory=dict)
    date_range: tuple[str, str] = ("", "")
    total_retrieved: int = 0
    sources_used: list[str] = field(default_factory=list)


# ── Social theme keywords ─────────────────────────────────────────────────────
# Used to classify chunks by social theme automatically

SOCIAL_THEME_KEYWORDS: dict[str, list[str]] = {
    "politics_civic": [
        "election", "vote", "constitution", "president", "government", "parlement",
        "démocratie", "politique", "saied", "parti", "loi", "liberté", "droits",
        "manifestation", "protest", "civil society", "NGO"
    ],
    "economy_inequality": [
        "chômage", "unemployment", "inflation", "pauvreté", "poverty", "salaire",
        "wage", "FMI", "IMF", "dette", "debt", "crise", "crisis", "économie",
        "economy", "inégalité", "inequality", "PIB", "GDP"
    ],
    "gender_women": [
        "femme", "woman", "women", "genre", "gender", "égalité", "equality",
        "violence", "droits des femmes", "women rights", "féminisme", "feminism",
        "mariage", "marriage", "harcèlement", "harassment"
    ],
    "youth_education": [
        "jeunesse", "youth", "jeune", "young", "étudiant", "student", "université",
        "education", "école", "school", "formation", "diplôme", "chômage jeunes",
        "youth unemployment", "avenir", "future"
    ],
    "migration_diaspora": [
        "migration", "émigration", "immigré", "immigrant", "diaspora", "expatrié",
        "boat", "bateau", "frontière", "border", "Europe", "refuge", "asile",
        "harraga", "irregular migration"
    ],
    "culture_identity": [
        "culture", "identité", "identity", "patrimoine", "heritage", "tradition",
        "musique", "music", "cinéma", "cinema", "art", "festival", "langue",
        "language", "arabe", "arabic", "berbère", "amazigh"
    ],
    "religion_secularism": [
        "islam", "religion", "mosquée", "mosque", "imam", "ramadan", "laïcité",
        "secularism", "sharia", "islamiste", "islamist", "modéré", "moderate",
        "liberté de culte", "freedom of religion"
    ],
    "environment_urban": [
        "environnement", "environment", "eau", "water", "sécheresse", "drought",
        "pollution", "climat", "climate", "urbanisation", "ville", "city",
        "rural", "agriculture", "énergie", "energy"
    ],
    "health_wellbeing": [
        "santé", "health", "covid", "pandémie", "pandemic", "hôpital", "hospital",
        "médecin", "doctor", "vaccin", "vaccine", "mental health", "bien-être",
        "wellbeing", "maladie", "disease"
    ],
    "digital_social_media": [
        "digital", "numérique", "internet", "réseaux sociaux", "social media",
        "facebook", "twitter", "tiktok", "youtube", "smartphone", "application",
        "technologie", "technology", "startup", "innovation"
    ],
}

# ── Tool 1 — Retrieve social evidence from RAG ────────────────────────────────

def retrieve_social_evidence(
    retriever: Any,
    theme: str,
    top_k: int = 10,
) -> list[Any]:
    """
    Query the Supabase vector store for chunks related to a social theme.

    Parameters
    ----------
    retriever : Retriever instance from rag/vector_store/retriever.py
    theme     : Social theme to query (e.g. "gender_women", "economy_inequality")
    top_k     : Number of chunks to retrieve

    Returns
    -------
    List of RetrievalResult objects
    """
    if retriever is None:
        return []

    # Build a natural-language query from the theme keywords
    keywords = SOCIAL_THEME_KEYWORDS.get(theme, [theme])
    query = f"Tunisia {theme.replace('_', ' ')} society 2020 2026 {' '.join(keywords[:5])}"

    try:
        retriever.match_count = top_k
        results = retriever.retrieve(query=query, rerank=False)
        return results
    except Exception as e:
        print(f"[sociologist_tools] retrieve_social_evidence failed for theme '{theme}': {e}")
        return []


# ── Tool 2 — Filter chunks by theme keywords ─────────────────────────────────

def filter_by_theme(
    chunks: list[Any],
    theme: str,
    min_keyword_matches: int = 1,
) -> list[Any]:
    """
    Filter a list of chunks to keep only those relevant to a social theme.

    Parameters
    ----------
    chunks               : List of RetrievalResult or Chunk objects
    theme                : Theme key from SOCIAL_THEME_KEYWORDS
    min_keyword_matches  : Minimum number of keywords that must appear in content

    Returns
    -------
    Filtered list of chunks
    """
    keywords = SOCIAL_THEME_KEYWORDS.get(theme, [])
    if not keywords:
        return chunks

    filtered = []
    for chunk in chunks:
        content = getattr(chunk, "content", str(chunk)).lower()
        matches = sum(1 for kw in keywords if kw.lower() in content)
        if matches >= min_keyword_matches:
            filtered.append(chunk)

    return filtered


# ── Tool 3 — Filter chunks by source ─────────────────────────────────────────

def filter_by_source(
    chunks: list[Any],
    sources: list[str],
) -> list[Any]:
    """
    Keep only chunks from specified sources.

    Parameters
    ----------
    chunks  : List of RetrievalResult objects
    sources : List of source names e.g. ["gdelt", "wikipedia", "youtube"]

    Returns
    -------
    Filtered list
    """
    sources_lower = [s.lower() for s in sources]
    filtered = []
    for chunk in chunks:
        meta = getattr(chunk, "metadata", {}) or {}
        source = meta.get("source", "").lower()
        if source in sources_lower:
            filtered.append(chunk)
    return filtered


# ── Tool 4 — Compute theme coverage ──────────────────────────────────────────

def compute_theme_coverage(chunks: list[Any]) -> dict[str, int]:
    """
    Count how many chunks relate to each social theme.

    Parameters
    ----------
    chunks : List of RetrievalResult or Chunk objects

    Returns
    -------
    Dict mapping theme name → count of matching chunks
    """
    coverage: Counter = Counter()

    for chunk in chunks:
        content = getattr(chunk, "content", str(chunk)).lower()
        for theme, keywords in SOCIAL_THEME_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw.lower() in content)
            if matches >= 1:
                coverage[theme] += 1

    return dict(coverage.most_common())


# ── Tool 5 — Extract date range ───────────────────────────────────────────────

def extract_dates(chunks: list[Any]) -> tuple[str, str]:
    """
    Extract the earliest and latest dates from a list of chunks.

    Returns
    -------
    Tuple (earliest_date, latest_date) as ISO strings, or ("", "") if none found
    """
    dates = []
    date_pattern = re.compile(r"\b(20[12][0-9])[/-]?(0[1-9]|1[0-2])?[/-]?([0-3][0-9])?\b")

    for chunk in chunks:
        # Check metadata first
        meta = getattr(chunk, "metadata", {}) or {}
        date_val = meta.get("date") or meta.get("published_at") or ""
        if date_val:
            match = date_pattern.match(str(date_val))
            if match:
                dates.append(str(date_val)[:10])

        # Also scan content for years
        content = getattr(chunk, "content", "")
        for match in date_pattern.finditer(content):
            year = match.group(1)
            if 2020 <= int(year) <= 2026:
                dates.append(year)

    if not dates:
        return ("", "")

    dates_sorted = sorted(set(dates))
    return (dates_sorted[0], dates_sorted[-1])


# ── Tool 6 — Format chunks for prompt ────────────────────────────────────────

def format_chunks_for_prompt(
    chunks: list[Any],
    max_chars_per_chunk: int = 500,
    max_total_chars: int = 8000,
) -> str:
    """
    Format a list of chunks into clean text for LLM prompt injection.
    Truncates to stay within token limits.

    Parameters
    ----------
    chunks             : List of RetrievalResult or Chunk objects
    max_chars_per_chunk: Max characters per chunk (truncated with ellipsis)
    max_total_chars    : Max total characters in output

    Returns
    -------
    Formatted string ready for {chunks} placeholder in prompt
    """
    if not chunks:
        return "(No evidence available for this query)"

    lines = []
    total_chars = 0

    for i, chunk in enumerate(chunks, start=1):
        content = getattr(chunk, "content", str(chunk))
        meta    = getattr(chunk, "metadata", {}) or {}
        source  = meta.get("source", "unknown")
        category = meta.get("category", "")
        similarity = getattr(chunk, "similarity", None)

        # Truncate content if needed
        if len(content) > max_chars_per_chunk:
            content = content[:max_chars_per_chunk] + "..."

        chunk_id = getattr(chunk, "chunk_id", "") or getattr(chunk, "document_id", "")

        sim_str = f" [similarity: {similarity:.2f}]" if similarity is not None else ""
        header = f"[{i}] ID: {chunk_id} | Source: {source} | Category: {category}{sim_str}"
        block = f"{header}\n{content}\n"

        if total_chars + len(block) > max_total_chars:
            lines.append(f"[{i}] ... (truncated — {len(chunks) - i + 1} more chunks not shown)")
            break

        lines.append(block)
        total_chars += len(block)

    return "\n".join(lines)


# ── Tool 7 — Score evidence relevance ────────────────────────────────────────

def score_evidence_relevance(
    chunks: list[Any],
    social_themes: list[str],
) -> list[tuple[Any, float]]:
    """
    Score each chunk's relevance to a set of social themes.
    Combines vector similarity score with keyword match count.

    Parameters
    ----------
    chunks        : List of RetrievalResult objects
    social_themes : List of theme keys to score against

    Returns
    -------
    List of (chunk, score) tuples sorted by score descending
    """
    scored = []
    all_keywords = []
    for theme in social_themes:
        all_keywords.extend(SOCIAL_THEME_KEYWORDS.get(theme, []))

    for chunk in chunks:
        content  = getattr(chunk, "content", str(chunk)).lower()
        sim      = getattr(chunk, "similarity", 0.5)

        # Keyword match score (0 to 1)
        matches  = sum(1 for kw in all_keywords if kw.lower() in content)
        kw_score = min(matches / max(len(all_keywords), 1), 1.0)

        # Combined score: 70% vector similarity + 30% keyword match
        combined = 0.7 * sim + 0.3 * kw_score
        scored.append((chunk, round(combined, 4)))

    return sorted(scored, key=lambda x: x[1], reverse=True)


# ── Tool 8 — Build evidence bundle ───────────────────────────────────────────

def build_evidence_bundle(
    retriever: Any,
    themes: list[str],
    top_k_per_theme: int = 5,
) -> EvidenceBundle:
    """
    High-level tool: retrieves and assembles evidence for multiple themes.
    Combines retrieval + deduplication + scoring into one call.

    Parameters
    ----------
    retriever        : Retriever instance
    themes           : List of social theme keys to retrieve
    top_k_per_theme  : How many chunks to retrieve per theme

    Returns
    -------
    EvidenceBundle ready for the SociologistAgent
    """
    all_chunks = []
    seen_ids: set[str] = set()

    for theme in themes:
        results = retrieve_social_evidence(retriever, theme, top_k=top_k_per_theme)
        for r in results:
            cid = getattr(r, "chunk_id", "") or getattr(r, "document_id", "")
            if cid not in seen_ids:
                seen_ids.add(cid)
                all_chunks.append(r)

    # Score and sort
    scored = score_evidence_relevance(all_chunks, themes)
    ranked_chunks = [chunk for chunk, _ in scored]

    # Compute stats
    coverage   = compute_theme_coverage(ranked_chunks)
    date_range = extract_dates(ranked_chunks)
    sources    = list({
        getattr(c, "metadata", {}).get("source", "unknown")
        for c in ranked_chunks
    })

    query_str = " + ".join(themes)

    return EvidenceBundle(
        query=query_str,
        theme=", ".join(themes),
        chunks=ranked_chunks,
        theme_coverage=coverage,
        date_range=date_range,
        total_retrieved=len(ranked_chunks),
        sources_used=sources,
    )
