"""Deterministic tools of the Technology agent (no LLM call, unit-tested).

  classify_domain     which technology domain a chunk is about (keyword taxonomy)
  evidence_kind       research paper / news / archive ... (what a source can prove)
  diversify           domain-balanced selection of the evidence sent to the model
  coverage_summary    per-domain evidence counts, injected into the prompt
  ungrounded_numbers  figures in a finding that its cited sources do not contain
"""
from __future__ import annotations

import re
from collections import Counter, OrderedDict
from typing import Any

from agents.base_agent import CITATION, EVIDENCE_CHARS, as_result

OTHER = "other"

# Terms match at word boundaries with an optional plural ("vaccine" -> "vaccines").
# Arabic and French terms cover the GDELT headlines of the corpus.
TECH_DOMAINS: "OrderedDict[str, tuple[str, ...]]" = OrderedDict([
    ("ai_computing", (
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "large language model", "llm", "chatgpt", "generative", "robot", "automation",
        "automated", "computer vision", "algorithm", "intelligence artificielle", "algorithme", "الاصطناعي",
    )),
    ("digital_connectivity", (
        "internet", "broadband", "5g", "mobile phone", "smartphone", "social media",
        "digital", "online", "e-government", "fintech", "e-commerce", "mobile payment",
        "startup", "start-up", "platform", "numérique", "réseaux sociaux", "téléphonie",
        "الرقمي", "الرقمية", "الإنترنت", "التواصل الاجتماعي",
    )),
    ("cybersecurity", (
        "cybersecurity", "cyber", "cyberattack", "hacker", "ransomware", "data protection",
        "privacy", "surveillance", "cybersécurité", "cyberattaque", "données personnelles", "السيبراني",
    )),
    ("energy_climate", (
        "solar", "renewable", "wind power", "wind farm", "photovoltaic", "electricity",
        "battery", "batteries", "electric vehicle", "hydrogen", "power grid", "energy transition",
        "desalination", "énergie", "énergétique", "électricité", "électrique", "solaire", "renouvelable",
        "dessalement", "الطاقة", "الشمسية", "الكهرباء",
    )),
    ("health_biotech", (
        "vaccine", "mrna", "biotechnology", "genome", "genetic", "gene", "crispr",
        "telemedicine", "medical device", "diagnostic", "vaccin", "génétique", "télémédecine", "لقاح", "جينية",
    )),
    ("space", (
        "space exploration", "spacecraft", "space agency", "satellite", "rocket", "nasa",
        "lunar", "orbit", "telescope", "astronaut", "spatiale", "fusée", "الفضاء",
    )),
])

DOMAIN_LABELS = {
    "ai_computing": "AI & computing",
    "digital_connectivity": "digital life & connectivity",
    "cybersecurity": "cybersecurity & privacy",
    "energy_climate": "energy & climate tech",
    "health_biotech": "health & biotech",
    "space": "space",
    OTHER: "outside technology",
}

_PATTERNS = {
    domain: [re.compile(rf"(?<!\w){re.escape(term)}(?:s|es)?(?!\w)", re.IGNORECASE) for term in terms]
    for domain, terms in TECH_DOMAINS.items()
}
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _text_of(result: Any) -> str:
    return f"{result.metadata.get('title') or ''} {result.content or ''}"


def _domain_scores(chunk: Any) -> dict[str, int]:
    text = _text_of(as_result(chunk))
    return {d: sum(1 for p in patterns if p.search(text)) for d, patterns in _PATTERNS.items()}


def classify_domain(chunk: Any) -> str:
    """Domain with the most distinct term hits; ties go to the first domain of TECH_DOMAINS."""
    scores = _domain_scores(chunk)
    best = max(scores, key=lambda d: scores[d])
    return best if scores[best] else OTHER


def mentioned_domains(chunk: Any) -> list[str]:
    """Every technology domain with at least one term in the chunk (its main domain included)."""
    return [d for d, score in _domain_scores(chunk).items() if score]


def evidence_kind(chunk: Any) -> str:
    """What kind of source this is, which bounds what it can support."""
    meta = as_result(chunk).metadata or {}
    source = str(meta.get("source") or "").lower()
    category = str(meta.get("category") or "").lower()
    if source == "arxiv" or category == "science":
        return "research paper"
    if category == "statistics" or source == "worldbank":
        return "indicator"
    if category == "news" or source == "gdelt":
        return "news"
    if source == "internet_archive" or category == "history":
        return "archive"
    if source == "wikipedia":
        return "encyclopedia"
    return category or "document"


def diversify(evidence: list, limit: int) -> list:
    """Round-robin over domains (in order of first appearance, "other" last), and over
    source kinds inside a domain, so that one domain or one source type cannot fill
    the whole context. Relevance order is kept inside each (domain, kind) group."""
    groups: "OrderedDict[str, OrderedDict[str, list]]" = OrderedDict()
    for chunk in evidence:
        groups.setdefault(classify_domain(chunk), OrderedDict()).setdefault(evidence_kind(chunk), []).append(chunk)
    if OTHER in groups:
        groups.move_to_end(OTHER)

    def by_kind(kinds: "OrderedDict[str, list]"):
        queues = [list(q) for q in kinds.values()]
        while any(queues):
            for queue in queues:
                if queue:
                    yield queue.pop(0)

    streams = [by_kind(kinds) for kinds in groups.values()]
    selected: list = []
    while streams and len(selected) < limit:
        for stream in list(streams):
            item = next(stream, None)
            if item is None:
                streams.remove(stream)
            elif len(selected) < limit:
                selected.append(item)
    return selected


def coverage_summary(evidence: list) -> str:
    """One line per domain, e.g. "- AI & computing: 4 (3 research paper, 1 news)".

    Each item counts under its main domain only; a domain with no item of its own
    but mentioned by items of other domains says so, so that it is not read as a gap.
    """
    per_domain: dict[str, Counter] = {d: Counter() for d in list(TECH_DOMAINS) + [OTHER]}
    also: dict[str, Counter] = {d: Counter() for d in TECH_DOMAINS}
    for chunk in evidence:
        main = classify_domain(chunk)
        per_domain[main][evidence_kind(chunk)] += 1
        for domain in mentioned_domains(chunk):
            if domain != main:
                also[domain][DOMAIN_LABELS[main]] += 1
    lines = []
    for domain, kinds in per_domain.items():
        total = sum(kinds.values())
        if domain == OTHER and not total:
            continue
        if total:
            detail = f" ({', '.join(f'{n} {k}' for k, n in kinds.most_common())})"
        elif also.get(domain):
            n = sum(also[domain].values())
            detail = (f" as main domain; also in {n} item{'s' if n > 1 else ''} counted under "
                      f"{', '.join(also[domain])} - not a gap")
        else:
            detail = " - no evidence"
        lines.append(f"- {DOMAIN_LABELS[domain]}: {total}{detail}")
    return "\n".join(lines)


def _numbers(text: str) -> set[str]:
    found = set()
    for raw in _NUMBER.findall(text or ""):
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw):
            raw = raw.replace(",", "")
        found.add(raw.replace(",", "."))
    return found


def grounding_text(chunk: Any) -> str:
    """What the model saw for a chunk: its year, title and the truncated text."""
    result = as_result(chunk)
    meta = result.metadata or {}
    return f"{meta.get('year') or ''} {meta.get('title') or ''} {result.content[:EVIDENCE_CHARS]}"


def ungrounded_numbers(finding: str, sources: list[str]) -> list[str]:
    """Figures of two or more digits in ``finding`` (citations excluded) absent from every source."""
    allowed = set().union(*(_numbers(s) for s in sources)) if sources else set()
    claimed = _numbers(CITATION.sub(" ", finding))
    return sorted(n for n in claimed if len(re.sub(r"\D", "", n)) >= 2 and n not in allowed)
