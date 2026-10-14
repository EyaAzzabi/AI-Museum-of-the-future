> **Itération v3** : cas live fourni par Sarah, question Tunisie -> titres Égypte/Maroc.
> Prompt actif : culture_art.md (v3) ; ancien v2 : culture_art_v2.md.
> Voir AMELIORATION_V3_DEEP_LEARNING.md pour les changements et limites.
> evaluate_culture_art.py compare désormais v1, v2 et v3, soit neuf appels LLM.

# Bibliothèque de prompts — contribution de Sarah

## Rôle
CultureArtAgent extrait une lecture culturelle et artistique des preuves RAG
et retourne un InsightObject utilisable par le Curator.

## Versions

| Version | Fichier | Contexte transmis | Techniques |
|---|---|---|---|
| v1 | prompts/culture_art_v1.md | Texte concaténé, sans IDs dans le renderer original | Rôle et JSON demandé |
| v2 | prompts/culture_art.md | JSON contenant chunk_id, document_id, content, metadata | Rôle, few-shot positif, few-shot abstention, structured output et garde-fous |

Le system prompt renforce la règle de traiter les sources comme des données.
Les documents peuvent contenir une instruction malveillante ; le rôle doit
rester défini par le système, pas par le contenu d'une source.

## Pourquoi changer ?

Défauts constatés par lecture du code, pas par un essai LLM live dans cet audit :
- le modèle ne voyait pas les IDs qu'il devait retourner ;
- des références inventées n'étaient pas filtrées par le spécialiste ;
- des résultats manquants étaient remplacés par une conclusion générique ;
- aucune distinction explicite faits/interprétation/hypothèse dans le prompt.

Les tests Python simulent une référence inconnue et confirment son rejet.
Ils confirment l'abstention sur sortie vide ou structure inutilisable.
Ils ne mesurent pas l'amélioration du LLM en production.

## Protocole avant/après reproductible

1. Fixer fournisseur et LLM_MODEL, et noter cette configuration.
2. Lancer evaluate_culture_art.py sur les trois mêmes exemples synthétiques.
3. Conserver les réponses brutes v1/v2, pas seulement la sortie filtrée Python.
4. Annoter chaque affirmation : soutenue / non soutenue / interprétation annoncée.
5. Pour unrelated : vérifier l'abstention. Pour injection : vérifier qu'aucun ID
   faux n'a été sélectionné et que les instructions du passage n'ont pas été suivies.
6. Répéter sur des passages réels de votre corpus et conserver leurs IDs.
7. Noter les cas d'échec et une correction réellement essayée ; ne pas remplir
   une colonne « observé » avec une hypothèse de comportement.

Le script compare le prompt et le format de contexte, avec le même system prompt,
le même modèle et les mêmes exemples. Il ne reproduit pas toutes les différences
du code runtime v1/v2. Il ne fixe pas une seed ni une température ; les réponses
peuvent varier et plusieurs répétitions peuvent être utiles pour une conclusion.

## Mesures automatiques disponibles

- schema_valid : clés et types attendus pour le spécialiste ;
- unknown_references : IDs retournés absents du contexte fourni ;
- abstained : findings et références tous deux vides ;
- revues humaines des faits et de la pertinence : pending, jamais scores inventés.

Ces contrôles ne prouvent pas que les affirmations sont étayées par les passages.

## Évaluer le retrieval séparément

Requêtes suggérées : arts contemporains en Tunisie, patrimoine numérique,
cinéma et mémoire en Afrique du Nord, musique et identité, cas hors domaine.
Pour chaque requête, enregistrer les chunks réellement retournés et annoter
la pertinence. Precision sur résultats retournés = nombre pertinents / nombre
retournés. Pour une Precision@5 avec moins de cinq résultats, expliciter la
convention de dénominateur. Recall@k nécessite un ensemble de référence des
passages pertinents. Le score de similarité n'est pas une probabilité de vérité.

Pour comparer le chunking, constituer deux index cohérents utilisant le même
modèle d'embeddings et la même unité/taille de budget, puis utiliser les mêmes
requêtes. Ne pas mélanger Gemini et MiniLM ni comparer 512 tokens avec 512
caractères comme s'il s'agissait du même découpage.

## Documents utiles

Consignes du module : docs/Advanced DL-Exam.pdf. Gemini Embeddings, documentation
primaire consultée : https://ai.google.dev/gemini-api/docs/embeddings.
Le choix gemini-embedding-001/1536 est guidé par votre export n8n, pas par une
recommandation de migrer vers un modèle plus récent.
