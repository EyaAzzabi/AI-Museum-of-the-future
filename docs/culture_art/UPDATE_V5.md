# Sarah — Culture & Art V5

## Ce qui change

V4 prenait les cinq premiers résultats du score hybride. Les titres de photos et
les nouvelles politiques pouvaient ainsi masquer un artiste présent plus bas.
V5 examine les 80 premiers candidats au maximum, par lots de huit, AVANT de garder
jusqu'à cinq sources. Dans ton dernier essai, 79 candidats étaient disponibles :
ils entrent tous dans ce budget. Si le corpus grandit, `rerank_unreviewed_count`
indiquera combien n'ont pas été examinés. Cela n'est pas une recherche exhaustive.

Le modèle note chaque texte : 0 hors sujet, 1 contexte seul, 2 exemple partiel
utile, 3 réponse directe. Les notes 2 et 3 exigent une citation copiée du contenu.
Ces notes sont des jugements du modèle, pas des probabilités. Le code vérifie les
identifiants, les types, les citations et la couverture du lot. Il ne peut pas
prouver automatiquement que la citation justifie le jugement sémantique.

Les sources acceptées sont triées par note, puis par score hybride. Un seul
extrait par document est conservé afin de diversifier les sources. Le modèle
rédacteur doit attribuer les autobiographies à leur auteur et expliciter les
limites d'un exemple isolé. Le pipeline général historique reste compatible ;
la nouvelle sélection est activée dans la démo CultureArt et son endpoint HTTP.

## Installation Windows

Dans `AI-Museum-Sarah-Git`, après application du patch V5, conserve ton `.env`
local. Aucune nouvelle bibliothèque ni nouveau modèle à télécharger n'est requis
si la V4 et les appels LLM fonctionnaient déjà.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/rag/test_culture_reranker.py tests/rag/test_culture_country_first.py tests/agents/test_culture_scope.py tests/agents/test_culture_integration.py -q
.\.venv\Scripts\python.exe demo_culture_art.py "contemporary art and cultural identity in Tunisia" --country Tunisia --top-k 5
.\.venv\Scripts\python.exe demo_culture_art.py "Joe Luciano Tunisian rock music and freedom of expression" --country Tunisia --top-k 5
```

La recherche utilise jusqu'à dix appels de sélection, puis un appel de rédaction
si une source est retenue. Cela augmente la durée et la consommation de ton
quota LLM. Chaque appel de sélection a un délai réseau de 45 secondes et aucune
relance automatique. Une erreur de quota/JSON est affichée comme une erreur ;
elle n'est pas transformée en absence de sources. Les extraits sont limités à
1600 caractères ; les troncatures apparaissent dans `rerank_decisions`.

Pour comparer au classement précédent, ajoute `--no-rerank` à la commande.
L'endpoint HTTP active toujours la sélection V5. N'envoie pas ce paramètre CLI
à n8n. Les décisions et limites sont incluses dans `retrieval`.

## Évaluation réelle, à exécuter sur ton PC

```powershell
.\.venv\Scripts\python.exe evaluate_culture_live.py --live --output culture_evaluation_v5.json
.\.venv\Scripts\python.exe evaluate_culture_live.py --live --baseline --output culture_evaluation_v4.json
```

Les deux questions sont des cas de régression déjà connus. La présence de la
source Joe Luciano est mesurée dans le classement et dans la réponse. Pour la
question générale, cette source est un exemple possible, pas une réponse complète
ni l'unique source pertinente. Les champs `human_review` doivent être évalués
manuellement en lisant les textes. Ne transforme pas ces deux cas en pourcentage
de réussite général. Pour un vrai benchmark, ajoute des questions inédites,
d'autres pays, des sources hors sujet, et des cas sans preuve, annotés par deux
personnes. Compare précision des sources, couverture et fidélité des affirmations.

## Comprendre le deep learning

1. L'encodeur préentraîné transforme question et passages en vecteurs. La
   similarité mesure leur proximité sémantique, pas la vérité d'une affirmation.
2. Le score V4 mélange cette similarité et une couverture lexicale. La règle
   géographique et les poids 70/30 sont du code, pas un apprentissage.
3. V5 demande au LLM préentraîné de lire question et texte ensemble pour juger
   leur pertinence. C'est un reclassement par LLM pendant l'inférence. Aucun poids
   neuronal n'est mis à jour et aucun entraînement n'a été effectué.
4. Le générateur rédige à partir des extraits retenus : c'est un système RAG.
   Les contrôles de citations encadrent sa réponse sans garantir chaque fait.

Un véritable fine-tuning nécessiterait des couples question/passage annotés,
des exemples négatifs difficiles (politique tunisienne, titres de photos,
mentions géographiques incidentes), des ensembles entraînement/validation/test
séparés par document, une fonction de perte et une mesure sur des questions
jamais utilisées pour entraîner. Nous n'avons pas encore ce jeu annoté. La V5
corrige d'abord le point de sélection identifié, sans prétendre avoir réentraîné
le modèle ni avoir démontré sa qualité en production.

## Importer le commit et pousser sur GitHub

Le commit est fourni en patch Git : l'import avec `git am` recrée le commit dans
ton dépôt Windows. Le commit effectué dans l'espace de travail de l'assistant
n'apparaît pas automatiquement dans ton dossier Windows.

Télécharge `CultureArtAgent-Sarah-V5.patch` dans Téléchargements. Ferme les fichiers
pendant l'import et lance ces commandes dans `AI-Museum-Sarah-Git` :

```powershell
git branch --show-current
git status --short
```

La branche attendue est `sarah/culture-art-agent`. Si la V4 testée n'a pas encore
été commitée, enregistre ses cinq fichiers (aucun fichier `.env`) :

```powershell
git add rag/vector_store/culture_retrieval.py tests/agents/test_culture_scope.py tests/rag/test_culture_country_first.py UPDATE_V4.md docs/VALIDATION_V4.md
git commit -m "Improve CultureArt retrieval with country-first hybrid candidates"
```

Si Git répond `nothing to commit`, cette étape est déjà faite. Ensuite :

```powershell
git am "$env:USERPROFILE\Downloads\CultureArtAgent-Sarah-V5.patch"
.\.venv\Scripts\python.exe -m pytest tests/rag/test_culture_reranker.py tests/rag/test_culture_country_first.py tests/agents/test_culture_scope.py tests/agents/test_culture_integration.py -q
git push -u origin sarah/culture-art-agent
```

Si l'import rencontre un conflit, ne pousse pas. `git am --abort` annule cet
import ; conserve le message d'erreur pour résoudre l'écart avec ta copie.
Le patch requiert la V4, celle dont les 29 tests passaient dans ton terminal.
