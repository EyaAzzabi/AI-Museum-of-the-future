"""Shared region/language coverage so data-source fetch scripts don't default to US/Europe-only results.

Every fetch script should iterate over LANGUAGES and/or REGIONS explicitly
rather than relying on a source API's default (unfiltered) query, which
tends to skew English/US/UK-heavy.
"""

# Wikipedia/Wikidata language editions and GDELT sourcelang filters.
# Chosen to span major world regions, not just Anglophone/European ones.
LANGUAGES = {
    "en": "English",
    "ar": "Arabic",
    "fr": "French",
    "es": "Spanish",
    "zh": "Chinese",
    "hi": "Hindi",
    "pt": "Portuguese",
    "ru": "Russian",
}

# Arab League member states (ISO 3166-1 alpha-2), for GDELT sourcecountry
# filters, World Bank/UNESCO country queries, and Wikimedia Commons category
# searches. Explicit inclusion is the point: without this, "global" queries
# on most of these APIs return mostly US/European results by default.
ARAB_WORLD_COUNTRIES = {
    "DZ": "Algeria",
    "BH": "Bahrain",
    "KM": "Comoros",
    "DJ": "Djibouti",
    "EG": "Egypt",
    "IQ": "Iraq",
    "JO": "Jordan",
    "KW": "Kuwait",
    "LB": "Lebanon",
    "LY": "Libya",
    "MR": "Mauritania",
    "MA": "Morocco",
    "OM": "Oman",
    "PS": "Palestine",
    "QA": "Qatar",
    "SA": "Saudi Arabia",
    "SO": "Somalia",
    "SD": "Sudan",
    "SY": "Syria",
    "TN": "Tunisia",
    "AE": "United Arab Emirates",
    "YE": "Yemen",
}

# A broader set of countries for general global balance (one or two major
# countries per continent/region beyond the Arab world and the default
# US/UK/Western-Europe skew).
OTHER_GLOBAL_COUNTRIES = {
    "US": "United States",
    "GB": "United Kingdom",
    "FR": "France",
    "DE": "Germany",
    "CN": "China",
    "IN": "India",
    "BR": "Brazil",
    "NG": "Nigeria",
    "ZA": "South Africa",
    "JP": "Japan",
    "RU": "Russia",
    "MX": "Mexico",
    "ID": "Indonesia",
    "AU": "Australia",
}

ALL_COUNTRIES = {**ARAB_WORLD_COUNTRIES, **OTHER_GLOBAL_COUNTRIES}
