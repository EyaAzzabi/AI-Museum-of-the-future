"""Pull structured entity data (categories, type facts) from DBpedia into data/raw/dbpedia/.

Keyless. DBpedia extracts structured facts from Wikipedia and is hosted
independently (dbpedia.org), so it's usable as a Wikidata/Wikipedia
replacement on networks where wikimedia.org domains are blocked.

NOTE: dbo:abstract / rdfs:comment are NOT present on dbpedia.org's live
endpoint for the entities tested here (confirmed via direct SPARQL query,
not just a parsing gap) — DBpedia's abstract extraction appears to have
been deprecated/removed upstream. This only yields structured categories,
not prose text. For descriptive historical narrative, rely on Internet
Archive item descriptions and Met Museum culture/period fields instead
until Wikipedia access itself is restored.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "dbpedia"

ABSTRACT_PRED = "http://dbpedia.org/ontology/abstract"
LABEL_PRED = "http://www.w3.org/2000/01/rdf-schema#label"
SUBJECT_PRED = "http://purl.org/dc/terms/subject"
THUMBNAIL_PRED = "http://dbpedia.org/ontology/thumbnail"

# Palestine explicitly included as its own entity (State_of_Palestine is the
# substantive DBpedia resource; plain "Palestine" resolves to a thin
# disambiguation-style page), not folded into a generic "Middle East" bucket.
ENTITIES = [
    "State_of_Palestine",
    "Egypt",
    "Tunisia",
    "Morocco",
    "Saudi_Arabia",
    "Jordan",
    "India",
    "China",
    "Brazil",
    "France",
]


def get_english_value(prop_list, key="value"):
    if not prop_list:
        return None
    for item in prop_list:
        if item.get("lang") == "en":
            return item.get(key)
    return prop_list[0].get(key)


def fetch_entity(entity: str, retries: int = 4) -> dict:
    url = f"https://dbpedia.org/data/{entity}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-museum-of-the-future/0.1"})

    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read())
                break
        except Exception as e:
            last_err = e
            time.sleep(10)
    else:
        raise last_err

    resource_uri = f"http://dbpedia.org/resource/{entity}"
    props = data.get(resource_uri, {})

    subjects = [
        s.get("value", "").rsplit("Category:", 1)[-1].replace("_", " ")
        for s in props.get(SUBJECT_PRED, [])
    ]
    abstract = get_english_value(props.get(ABSTRACT_PRED))

    return {
        "entity": entity,
        "label": get_english_value(props.get(LABEL_PRED)),
        "abstract": abstract,  # usually null — see module docstring
        "thumbnail": (props.get(THUMBNAIL_PRED) or [{}])[0].get("value"),
        "categories": subjects,
        "source": "dbpedia",
        "url": f"https://dbpedia.org/page/{entity}",
    }


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for entity in ENTITIES:
        try:
            record = fetch_entity(entity)
        except Exception as e:
            print(f"[dbpedia] FAILED entity={entity!r}: {e}")
            continue
        fname = f"{entity.lower()}.json"
        out_path = RAW_DIR / fname
        out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        has_abstract = bool(record.get("abstract"))
        print(f"[dbpedia] entity={entity!r} -> abstract={'yes' if has_abstract else 'MISSING'} -> {out_path}")
        manifest.append({"entity": entity, "has_abstract": has_abstract, "file": fname})
        time.sleep(1)

    (RAW_DIR / "_manifest.json").write_text(
        json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "entities": manifest}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
