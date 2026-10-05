"""Shared topic list so fetch scripts cover more than just AI/tech + geopolitics.

Grouped loosely by which specialized agent (per the architecture diagram)
would primarily use each topic, though agents cross-validate on shared
evidence rather than owning a topic exclusively.
"""

TOPICS_BY_AGENT = {
    "science_technology": [
        "artificial intelligence",
        "space exploration",
        "climate change",
        "innovation and startups",
        "biotechnology and health",
        "renewable energy",
    ],
    "culture_media": [
        "cultural heritage",
        "arts and music",
        "fashion",
        "cinema and film",
        "traditional crafts",
        "architecture",
        "literature",
        "dance and performance",
        "food and cuisine",
    ],
    "socio_historical": [
        "social movements",
        "economy",
        "sports",
        "migration and demographics",
        "digital life and social media",
        "gender and equality",
        "conflict and peace",
    ],
}

ALL_TOPICS = [t for topics in TOPICS_BY_AGENT.values() for t in topics]

# Specific major current events that a generic topic wouldn't reliably surface
# on their own — same treatment as the dedicated "Palestine" pull (which is
# handled per-script as a region term). The generic "sports" topic returned
# only 4/100 World Cup mentions despite 2026 being an actual FIFA World Cup
# year; a broad topic word doesn't guarantee coverage of a specific event.
DEDICATED_EVENT_TOPICS = [
    "FIFA World Cup 2026",
]
