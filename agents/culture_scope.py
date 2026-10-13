"""Explicit geographic constraints; deterministic helpers, not a learned model."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from data.regions import ALL_COUNTRIES

ALIASES = {name: (name,) for name in ALL_COUNTRIES.values()}
ALIASES.update({
    "Tunisia": ("Tunisia", "Tunisie", "Tunis", "Tunisian", "Tunisien", "Tunisienne", "Tunisiens", "Tunisiennes", "تونس", "تونسي", "تونسية", "التونسي", "التونسية"),
    "Egypt": ("Egypt", "Egyptian", "Egypte", "Egyptien", "Egyptienne", "مصر", "المصرية", "المصري"),
    "Morocco": ("Morocco", "Moroccan", "Maroc", "Marocain", "Marocaine", "المغرب", "المغربي", "المغربية"),
    "France": ("France", "French", "Francais", "Francaise", "فرنسا"),
})
CODES = {name: code for code, name in ALL_COUNTRIES.items()}


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text)).casefold()
                   if not unicodedata.combining(c))


def mentions(text: str, country: str) -> bool:
    text = normalize(text)
    return any(re.search(r'(?<!\w)' + re.escape(normalize(alias)) + r'(?!\w)', text)
               for alias in ALIASES[country])


def resolve_country(query: str = "", country: str | None = None) -> str | None:
    inferred = [name for name in ALIASES if mentions(query, name)]
    if country is not None:
        if not isinstance(country, str) or not country.strip():
            raise ValueError("country must be a non-empty country name or ISO code.")
        matches = [name for name in ALIASES if normalize(country) == normalize(CODES[name])
                   or any(normalize(country) == normalize(alias) for alias in ALIASES[name])]
        if len(matches) != 1:
            raise ValueError("Unknown country. Use an English country name covered by data/regions.py, e.g. Tunisia.")
        selected = matches[0]
        if inferred and selected not in inferred:
            raise ValueError("The explicit country conflicts with the country named in the query.")
        return selected
    # Comparative multi-country queries are left to the prompt; no single-country filter.
    return inferred[0] if len(inferred) == 1 else None


def matches_country(chunk, country: str | None) -> bool:
    if country is None:
        return True
    def get(name, default=""):
        return chunk.get(name, default) if isinstance(chunk, Mapping) else getattr(chunk, name, default)
    metadata = get('metadata', {}) or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    # sourcecountry is the publisher's country, not the subject of the article.
    for field in ('country', 'country_name', 'country_code'):
        value = metadata.get(field)
        if value and (normalize(value) == normalize(CODES[country]) or mentions(str(value), country)):
            return True
    return mentions(str(get('content')), country) or mentions(str(metadata.get('title', '')), country)


def evidence_warnings(chunks) -> list[str]:
    contents = [chunk.get('content', '') if isinstance(chunk, Mapping) else getattr(chunk, 'content', '') for chunk in chunks]
    return ['Short excerpts: report only explicit facts; broader interpretation needs fuller sources.'] if any(len(str(c).split()) < 60 for c in contents) else []


def analysis_status(insight, chunks, query: str, country: str | None = None) -> dict:
    scope = resolve_country(query, country)
    return {
        'status': 'references_validated' if insight.selected_artifacts else 'insufficient_evidence',
        'scope_country': scope,
        'warnings': evidence_warnings(chunks),
        'limitations': [
            'References are checked; factual support and topic relevance still require human review.',
            'Country matching uses explicit mentions/metadata and may miss implicit references or accept incidental mentions.',
            'No matching retrieved evidence does not prove that the full corpus has no relevant documents.',
        ],
    }
