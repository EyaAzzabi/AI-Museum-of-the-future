# Data Sources — AI Museum of the Future

Ce document explique chaque source de données utilisée dans le projet :
d'où viennent les données, ce qu'elles contiennent, comment elles sont
collectées, et pourquoi elles ont été choisies pour représenter notre époque.

---

## Vue d'ensemble

```
Notre époque (2020s)
        │
        ├── Actualités & événements   → GDELT
        ├── Images & médias           → Wikimedia Commons
        ├── Science & recherche       → arXiv
        ├── Statistiques publiques    → World Bank Open Data
        ├── Tendances culturelles     → Wikipedia Pageviews
        └── Contexte historique       → Wikipedia REST + Wikidata SPARQL
                                              │
                                       data/raw/  (brut)
                                              │
                                       process_raw.py
                                              │
                                       data/processed/ (normalisé)
                                              │
                                       RAG → Agents → Exposition
```

---

## 1. GDELT — Actualités & Événements

**Script :** `data/fetch_gdelt.py`  
**Fichiers produits :** `data/raw/gdelt_lang_<code>_<date>.json`, `data/raw/gdelt_country_<code>_<date>.json`  
**Clé API requise :** Aucune  

### Qu'est-ce que GDELT ?

GDELT (Global Database of Events, Language, and Tone) est l'une des plus
grandes bases de données d'événements mondiaux. Elle surveille en temps réel
des milliers de médias dans plus de 100 langues et extrait les articles,
événements, et leur tonalité émotionnelle.

### Ce que l'on collecte

- **Titre** de l'article
- **URL** de la source
- **Date** de publication
- **Pays source** et **langue** de publication
- **Image sociale** (photo principale de l'article)
- **Domaine** du média

### Pourquoi cette source ?

> Un musée du futur aurait besoin de savoir **ce dont le monde parlait** au
> jour le jour. GDELT capture exactement ça : le flux d'information mondiale,
> dans toutes les langues, pas seulement en anglais.

- Couvre **plus de 65 pays** et **8 langues** (arabe, français, espagnol, chinois, hindi, portugais, russe, anglais)
- Gratuit, sans inscription, mis à jour toutes les 15 minutes
- Permet de voir quels sujets dominaient l'espace médiatique (IA, guerres, climat, culture…)

### Structure d'un enregistrement brut

```json
{
  "title": "New AI regulation proposed in the EU",
  "url": "https://example.com/article",
  "seendate": "20241015120000",
  "socialimage": "https://example.com/image.jpg",
  "domain": "bbc.com",
  "language": "English",
  "sourcecountry": "GB"
}
```

---

## 2. Wikimedia Commons — Images & Médias

**Script :** `data/fetch_wikimedia.py`  
**Fichiers produits :** `data/raw/wikimedia_<sujet>_<date>.json`  
**Clé API requise :** Aucune  

### Qu'est-ce que Wikimedia Commons ?

Wikimedia Commons est le dépôt multimédia de la Fondation Wikimedia : plus de
100 millions de fichiers (photos, illustrations, vidéos) sous licences libres,
indexés et recherchables via une API publique.

### Ce que l'on collecte

- **URL de l'image** (pleine résolution + miniature 800px)
- **Titre** du fichier
- **Description** textuelle
- **Licence** (CC BY, CC0, domaine public…)
- **Auteur / photographe**
- **Date de création**
- **Dimensions** (largeur × hauteur)

### Pourquoi cette source ?

> Les images sont des artefacts culturels. Un musée sans visuels n'est pas un
> musée. Wikimedia Commons offre des images **libres de droits** représentant
> des sujets contemporains (IA, changement climatique, vie urbaine, art…)
> dans un contexte mondial.

### Sujets interrogés

| Catégorie | Exemples de requêtes |
|---|---|
| Thèmes globaux | artificial intelligence, climate change, renewable energy, space exploration |
| Vie contemporaine | urban life 2020s, social media, pandemic, contemporary art |
| Régions arabes | Egypt culture, Morocco contemporary, Saudi Arabia… |
| Autres régions | China contemporary, Brazil culture, Nigeria… |

### Structure d'un enregistrement brut

```json
{
  "title": "File:AI robot hand.jpg",
  "url": "https://upload.wikimedia.org/wikipedia/commons/...",
  "thumb_url": "https://upload.wikimedia.org/...(800px).jpg",
  "width": 3000,
  "height": 2000,
  "mime": "image/jpeg",
  "description": "A robotic hand performing a precision task",
  "license": "CC BY-SA 4.0",
  "author": "Wikimedia contributor",
  "date_created": "2023-04-12",
  "query": "artificial intelligence"
}
```

---

## 3. arXiv — Science & Recherche

**Script :** `data/fetch_arxiv.py`  
**Fichiers produits :** `data/raw/arxiv_<topic>_<date>.json`  
**Clé API requise :** Aucune  

### Qu'est-ce que arXiv ?

arXiv est le serveur de preprints scientifiques de l'Université Cornell. Il
héberge plus de 2 millions d'articles en physique, mathématiques, informatique,
biologie quantitative, économie et sciences sociales — accessibles librement
via une API XML.

### Ce que l'on collecte

- **Titre** du papier
- **Résumé** (abstract)
- **Auteurs**
- **Date de publication**
- **Catégories** arXiv (cs.AI, physics.clim-dyn, q-bio.GN…)
- **URL** de l'article et du PDF

### Pourquoi cette source ?

> Dans 100 ans, les historiens voudront savoir **sur quoi les scientifiques
> travaillaient**. arXiv capture la frontière de la connaissance : IA, climat,
> génomique, informatique quantique… Ce sont les recherches qui définissent
> notre époque.

### Topics couverts (10 domaines)

| Slug | Sujet interrogé |
|---|---|
| `artificial_intelligence` | Deep learning, réseaux de neurones |
| `climate_change` | Réchauffement, atténuation, adaptation |
| `pandemic_virology` | COVID, épidémiologie, virologie |
| `renewable_energy` | Solaire, éolien, batteries |
| `large_language_models` | GPT, Transformers, LLM |
| `social_media_society` | Désinformation, polarisation |
| `space_exploration` | Mars, Lune, astronomie |
| `biotech_genomics` | CRISPR, biologie synthétique |
| `inequality_economics` | Inégalités, développement |
| `quantum_computing` | Qubits, correction d'erreurs |

### Structure d'un enregistrement brut

```json
{
  "id": "2310.12345",
  "title": "Advances in Large Language Model Alignment",
  "summary": "We present a novel approach to RLHF that...",
  "authors": ["Alice Martin", "Bob Chen"],
  "published": "2024-10-01T00:00:00Z",
  "categories": ["cs.AI", "cs.CL"],
  "url": "http://arxiv.org/abs/2310.12345",
  "pdf_url": "http://arxiv.org/pdf/2310.12345"
}
```

---

## 4. Wikipedia — Tendances & Contexte Historique

**Script :** `data/fetch_wikipedia.py`  
**Fichiers produits :**
- `data/raw/wikipedia_pageviews_<lang>_<date>.json`
- `data/raw/wikipedia_summaries_en_<date>.json`
- `data/raw/wikidata_<query>_<date>.json`

**Clé API requise :** Aucune  

Ce script interroge **trois APIs distinctes** de l'écosystème Wikimedia :

---

### 4a. Wikipedia Pageviews API — Tendances culturelles

**Ce que c'est :** L'API officielle de Wikimedia qui expose les statistiques
de consultation de chaque article Wikipedia, par langue et par jour.

**Ce que l'on collecte :**
- Les **top 50 articles les plus consultés** de la veille
- Par langue : `en`, `ar`, `fr`, `es`, `zh`, `hi`, `pt`, `ru`
- Rang, nombre de vues, langue, date

**Pourquoi ?**

> Ce que les gens cherchent à comprendre révèle ce qui les préoccupe. Un
> article soudainement très consulté = un événement marquant vient de se
> produire. C'est un **thermomètre culturel** en temps réel, et il est
> multilingue — ce qui est essentiel pour ne pas se limiter à la vision
> occidentale anglophone.

**Structure d'un enregistrement :**

```json
{
  "rank": 3,
  "article": "Artificial_intelligence",
  "views": 142000,
  "lang": "en",
  "date": "2024-10-14"
}
```

---

### 4b. Wikipedia REST API — Résumés d'articles

**Ce que c'est :** L'API REST de Wikipedia qui retourne le résumé structuré
d'un article : introduction, description, image principale, URL canonique.

**Ce que l'on collecte :**
- **Top 20 articles** les plus vus (en anglais)
- Résumé textuel (extrait de l'introduction)
- Description courte (type "encyclopédique")
- Miniature de l'article
- ID de la page (stable, utilisable pour déduplication)

**Pourquoi ?**

> Le résumé Wikipedia d'un sujet très consulté = une définition neutre et
> encyclopédique de ce qui compte à notre époque. C'est le texte de référence
> que le RAG utilisera pour ancrer les agents dans des faits vérifiés.

**Structure d'un enregistrement :**

```json
{
  "title": "Artificial intelligence",
  "description": "Intelligence demonstrated by machines",
  "extract": "Artificial intelligence (AI) is intelligence demonstrated by machines...",
  "thumbnail_url": "https://upload.wikimedia.org/...",
  "content_urls": "https://en.wikipedia.org/wiki/Artificial_intelligence",
  "lang": "en",
  "page_id": 1266451
}
```

---

### 4c. Wikidata SPARQL — Faits structurés

**Ce que c'est :** Wikidata est la base de connaissances structurée de
Wikimedia. Son endpoint SPARQL permet d'interroger des millions d'entités
(personnes, organisations, événements) avec des relations typées.

**Ce que l'on collecte (4 requêtes) :**

| Requête | Contenu |
|---|---|
| `contemporary_scientists` | Scientifiques nés après 1970, leur domaine, leurs prix |
| `recent_tech_companies` | Entreprises tech fondées après 2010, par pays |
| `cultural_events_2020s` | Événements culturels depuis 2020, par pays |
| `global_crises` | Crises mondiales depuis 2015 (guerres, catastrophes, pandémies) |

**Pourquoi ?**

> Wikidata offre des **faits vérifiés et structurés** — pas des opinions, pas
> du texte ambigu. Ces données permettront à l'agent Historien et à l'agent
> Sociologue de s'appuyer sur des entités réelles pour contextualiser les
> expositions.

**Structure d'un enregistrement (scientists) :**

```json
{
  "person": "http://www.wikidata.org/entity/Q12345",
  "personLabel": "Yann LeCun",
  "fieldLabel": "artificial intelligence",
  "awardLabel": "Turing Award"
}
```

---

## 5. World Bank Open Data — Statistiques publiques

**Script :** `data/fetch_worldbank.py`  
**Fichier produit :** `data/raw/worldbank_global_<date>.json`  
**Clé API requise :** Aucune

La collecte couvre les pays déjà définis dans `data/regions.py`, dont les 22 pays de la Ligue arabe et la Tunisie, ainsi que 14 pays d'autres régions. Quatre indicateurs annuels sont récupérés de 2015 à l'année courante : population totale, PIB par habitant, usage d'Internet et émissions de CO2 par habitant. Les années sans valeur publiée par la Banque mondiale sont ignorées.

```bash
python data/fetch_all.py --sources worldbank
```

Les observations sont normalisées dans la catégorie `statistics`, avec le pays, l'indicateur, l'année, la valeur et un lien vers l'API source. Cette source complète les actualités et tendances par des mesures comparables; elle ne remplace pas les sources qualitatives.

---

## 6. Schéma normalisé commun (après `process_raw.py`)

Toutes les sources sont transformées en un format unique par `process_raw.py` :

```json
{
  "id":           "identifiant unique (URL, arXiv ID, Wikidata QID…)",
  "source":       "gdelt | wikimedia | arxiv | wikipedia | wikidata",
  "category":     "news | image | science | culture | history",
  "title":        "titre de l'article/papier/image",
  "text":         "corps principal (abstract, résumé, description…)",
  "url":          "lien vers la source originale",
  "image_url":    "URL de l'image associée (ou null)",
  "date":         "date ISO-8601 ou null",
  "lang":         "code langue ISO 639-1 ou null",
  "tags":         ["mot-clé", "catégorie", "pays", "…"],
  "raw_source":   "nom du fichier raw d'origine (traçabilité)",
  "processed_on": "YYYY-MM-DD"
}
```

### Correspondance source → catégorie

| Source | `source` | `category` |
|---|---|---|
| GDELT | `gdelt` | `news` |
| Wikimedia Commons | `wikimedia` | `image` |
| arXiv | `arxiv` | `science` |
| Wikipedia Pageviews | `wikipedia` | `culture` |
| Wikipedia Summaries | `wikipedia` | `history` |
| Wikidata SPARQL | `wikidata` | `history` |

---

## 6. Volume de données estimé par exécution

| Source | Requêtes | Enregistrements estimés |
|---|---|---|
| GDELT | 8 langues + 36 pays = 44 requêtes | ~1 100 articles |
| Wikimedia | 8 topics globaux + 18 régions = 26 requêtes | ~420 images |
| arXiv | 10 topics × 20 papers | ~200 papiers |
| Wikipedia Pageviews | 8 langues × top 50 | ~400 entrées |
| Wikipedia Summaries | top 20 articles | ~20 résumés détaillés |
| Wikidata SPARQL | 4 requêtes × 50 résultats | ~200 entités |
| **Total** | | **~2 300 enregistrements** |

---

## 7. Couverture géographique

La liste des langues et pays est définie dans `data/regions.py`.  
Elle a été construite pour **contrebalancer le biais US/Europe** des APIs par défaut.

### Langues interrogées

| Code | Langue |
|---|---|
| `en` | Anglais |
| `ar` | Arabe |
| `fr` | Français |
| `es` | Espagnol |
| `zh` | Chinois |
| `hi` | Hindi |
| `pt` | Portugais |
| `ru` | Russe |

### Pays explicitement couverts

- **Monde arabe (22 pays)** : Algérie, Arabie Saoudite, Égypte, Maroc, Tunisie, EAU, Irak, Liban, Palestine, Jordanie…
- **Reste du monde (14 pays)** : USA, Royaume-Uni, France, Allemagne, Chine, Inde, Brésil, Nigeria, Afrique du Sud, Japon, Russie, Mexique, Indonésie, Australie

---

## 8. Limitations connues

| Source | Limitation |
|---|---|
| GDELT | Retourne le titre uniquement (pas le texte complet des articles) |
| Wikimedia | Images libres de droits uniquement — certains sujets sous-représentés |
| arXiv | Majorité des papiers en anglais, prédominance de l'Occident et de la Chine |
| Wikipedia Pageviews | Les pages "Main_Page" et "Special:" sont filtrées mais d'autres pages méta peuvent passer |
| Wikidata SPARQL | Requêtes limitées à 50 résultats pour rester dans les timeouts API |

---

*Dernière mise à jour : Semaine 1 — AI Museum of the Future, Esprit 2026-2027*
