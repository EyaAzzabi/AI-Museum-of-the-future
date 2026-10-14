# Mise à jour v4 — recherche ciblée par pays et classement hybride

## Installer dans ton projet existant

Copier le contenu du ZIP dans AI-Museum-Sarah-Git en fusionnant les dossiers
et remplaçant les fichiers concernés. Conserver .env, .venv et le cache du
modèle : aucun de ces éléments n'est inclus dans le complément.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/rag/test_culture_country_first.py tests/agents/test_culture_scope.py -q
.\.venv\Scripts\python.exe demo_culture_art.py "Joe Luciano Tunisian rock music and freedom of expression" --country Tunisia --top-k 5
```

29 tests ciblés doivent passer. Relancer ensuite la question générale pour
comparer avec v3 :

```powershell
.\.venv\Scripts\python.exe demo_culture_art.py "contemporary art and cultural identity in Tunisia" --top-k 5
```

## Pourquoi cette amélioration ?

Le CSV de Sarah contient une source sur un artiste tunisien liée au rock et à
la liberté d'expression. La RPC ne la retournait pas, même avec son nom dans
la requête. Ce constat établit un échec de récupération de la source connue,
mais ne suffit pas à prouver la cause exacte dans les embeddings ou l'index.

## Deux chemins, fusionnés sans doublons

1. La RPC match_chunks et le filtre de pays v3 restent en place.
2. Une lecture directe cible les mentions du pays dans content et les metadata
   country/country_code. Elle lit par pages de 200, au plus 2000 candidats.
   La relation document_id permet de récupérer titre, URL et date de documents.
   Python compare chaque vecteur stocké au vecteur de la question par cosinus.

Le score lexical est la fraction des mots significatifs de la question présents
dans le titre ou le passage. Le classement utilise :

    hybrid_score = 0.7 * cosine_similarity + 0.3 * lexical_coverage

Ces coefficients sont une heuristique de départ, pas des paramètres appris
ou une performance validée. Aucun artiste n'est codé en dur dans le produit.
Le nom Joe Luciano apparaît dans les tests/documentation du cas réel fourni.

similarity reste un cosinus ; hybrid_score est séparé dans metadata. Aucun de
ces scores n'est une probabilité de vérité. Le LLM et ses règles v3 restent
inchangés et peuvent s'abstenir sur des sources hors sujet.

## Les nouveaux diagnostics

- candidate_count/rejected_country_count concernent la RPC initiale seulement.
- country_rows_scanned compte les lignes du chemin ciblé.
- country_candidates_count compte les passages dans le scope avec un vecteur exploitable.
- country_vectors_skipped compte les vecteurs absents, invalides, nuls ou incompatibles.
- country_scan_reached_cap indique une lecture arrêtée au plafond.
- returned_count compte les résultats finaux après fusion et classement.
- metadata.title/url/published_at fournit la provenance quand elle est disponible.

Les vecteurs ne sont pas affichés ni transmis au LLM. Aucune modification de
Supabase, de son schéma ou de ses fonctions SQL n'est requise.

## Limites

Les mentions de pays peuvent être incidentes. Une référence uniquement
implicite, ou présente seulement dans un titre sans mention dans les chunks
ou metadata, peut manquer. Les listes de pays et documents hors domaine
observés dans le CSV nécessitent aussi un nettoyage du corpus.

Le cosinus est calculé exactement pour les vecteurs lus ; cela ne certifie
pas leur provenance, leur qualité ni l'exhaustivité du corpus. Les sources
avec vecteur invalide sont ignorées et comptées. Si le plafond est atteint,
la recherche ciblée n'est pas exhaustive. Ce chemin transfère les vecteurs
vers Python ; à grande échelle, préférer une RPC de filtrage avant ranking.

Les tests simulent clients et vecteurs. Aucune connexion privée ou nouvelle
génération LLM réelle n'a été testée ici ; vérifier la sortie live sur ton PC.

## Git après validation

Vérifier que la branche affichée est sarah/culture-art-agent :

```powershell
git branch --show-current
```

Puis :

```powershell
git add rag/vector_store/culture_retrieval.py tests/agents/test_culture_scope.py tests/rag/test_culture_country_first.py UPDATE_V4.md docs/VALIDATION_V4.md
git commit -m "Improve CultureArt retrieval with country-first hybrid candidates"
git push
```

Documentation primaire de l'API utilisée :
https://supabase.com/docs/reference/python/or
https://supabase.com/docs/reference/python/range
