> **Mise à jour v3 : lire INSTALLER_V3.md et docs/AMELIORATION_V3_DEEP_LEARNING.md.**
> Le pays est maintenant transmis/filtré et le statut devient references_validated.

# Sarah — commence ici

Ce dossier contient le projet complet que tu as envoyé, avec une implémentation
renforcée de ton agent CultureArtAgent, un diagnostic Supabase et un guide.
Ouvre CE dossier dans VS Code, pas uniquement le sous-dossier agents.

## 1. Comprendre les erreurs de tes captures

Tu avais ouvert Downloads/CultureArtAgent_Sarah : c'était un complément de six
fichiers, pas le projet complet. Le fichier agents/base_agent.py et le modèle
.env.example n'y existaient pas. L'import introuvable et Copy-Item qui échoue
avaient donc la même cause : tu n'étais pas dans le projet complet.

Dans le dossier à ouvrir maintenant, tu dois voir app.py, requirements.txt,
.env.example, agents/base_agent.py et demo_culture_art.py au même niveau.
Le ZIP envoyé avait deux dossiers AI-Museum-of-the-future-main imbriqués.
Le nouveau ZIP contient un seul dossier AI-Museum-Sarah.

## 2. Premier essai : comprendre sans aucune clé

Dans VS Code : Fichier > Ouvrir un dossier > AI-Museum-Sarah.
Terminal > Nouveau terminal. Lance :

```powershell
python demo_culture_art.py --offline
```

Ce mode n'a besoin que de Python. Il utilise deux passages synthétiques et une
réponse LLM simulée. Il montre le contrat de sortie et le rejet d'une référence
inventée. Ce n'est ni une génération IA réelle, ni un test de Supabase.

Résultat attendu : mode=offline_simulation et selected_artifacts=["demo-art-1"].

Si python n'est pas reconnu mais py l'est, utilise py à la place.

## 3. Installer les dépendances dans un environnement séparé

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-culture-art.txt
```

Cette façon de lancer le Python de .venv ne nécessite pas d'activer les scripts
PowerShell. Dans VS Code : Ctrl+Shift+P > Python: Select Interpreter > choisis
.venv/Scripts/python.exe pour que l'éditeur utilise le même Python.

Le fichier requirements-culture-art.txt suffit pour l'agent et le chemin Gemini.
Le projet global utilise requirements.txt. Si les données ont été indexées avec
MiniLM, ajoute fastembed pour la recherche locale :

```powershell
.\.venv\Scripts\python.exe -m pip install fastembed
```

## 4. La configuration existe-t-elle déjà ?

Le ZIP reçu contient uniquement .env.example avec des valeurs vides. Il ne
contient pas les secrets du projet. C'est normal pour une archive issue de Git.
Les credentials n8n référencés dans le workflow ne configurent pas ton Python.

Si tu as déjà un .env dans ton projet local, conserve-le. Sinon :

```powershell
Copy-Item .env.example .env
```

Dans VS Code, ouvre .env et remplis uniquement les valeurs requises. Une variable
.env est une ligne NOM=valeur : le code Python lit cette valeur au lancement.

| Variable | Utilité | Nécessaire pour |
|---|---|---|
| SUPABASE_URL | Adresse du projet contenant les données | Diagnostic et recherche |
| SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_ANON_KEY | Autorisation d'accès à la base | Diagnostic et recherche |
| LLM_API_KEY ou GROQ_API_KEY | Clé du modèle qui rédige l'analyse | Vraie génération |
| CULTURE_EMBEDDING_BACKEND | gemini ou local, selon l'indexation réellement faite | Recherche |
| GEMINI_API_KEY | Clé de Gemini pour vectoriser ta requête | Recherche si backend=gemini |
| LLM_BASE_URL / LLM_MODEL | Fournisseur et modèle de génération, si différents des valeurs du projet | Selon votre équipe |

Il faut distinguer deux modèles : celui qui transforme une requête en vecteur
et celui qui rédige le texte. Une clé Groq ne remplace pas une clé Gemini.
Une clé anon fonctionne seulement si RLS/permissions autorisent les lectures
et l'appel match_chunks. Une service_role reste dans le backend local, jamais
le JavaScript du navigateur. Ne publie pas .env sur GitHub.

Demande à Eya : « Quelle est la connexion Supabase utilisée et quel modèle a
créé les embeddings actuellement dans chunks : Gemini 1536 ou MiniLM 384 ?
Quel fournisseur/modèle utilisez-vous pour les agents ? »

## 5. Vérifier Supabase avant d'appeler le LLM

Remplis l'URL et la clé Supabase dans .env, enregistre avec Ctrl+S, puis :

```powershell
.\.venv\Scripts\python.exe demo_culture_art.py --diagnose
```

Ce diagnostic lit les nombres de documents/chunks et les dimensions d'un
échantillon de 20 vecteurs, sans les afficher et sans modifier la base.
Il ne nécessite pas LLM_API_KEY ni GEMINI_API_KEY.

- dimensions [1536] : compatible avec la dimension du workflow n8n, mais demande
  confirmation du modèle. Un ancien index OpenAI peut aussi avoir 1536 valeurs.
- dimensions [384] : compatible avec MiniLM dans le code Python, mais confirme
  également le modèle utilisé.
- plusieurs dimensions : corpus hétérogène à investiguer.
- dimensions [] : l'échantillon n'a pas de vecteurs lisibles ; cela ne suffit pas
  à déduire le modèle ou le type de colonne.
- zéro ligne accessible : la base peut être vide OU les droits masquer les lignes.

docs/diagnostic_supabase.sql donne des requêtes en lecture seule pour vérifier
le type déclaré, les dimensions de toutes les lignes, les index et la RPC.
Ne lance pas rag/schema.sql sur la base commune tant que ce point n'est pas résolu.

Si Eya confirme le chemin n8n Gemini :

```dotenv
CULTURE_EMBEDDING_BACKEND=gemini
GEMINI_API_KEY=ta_cle_google_locale
```

Si elle confirme le chemin Python MiniLM :

```dotenv
CULTURE_EMBEDDING_BACKEND=local
```

Ne copie pas les valeurs fictives de ce guide comme de vraies clés.

## 6. Essayer la vraie génération sur un petit exemple

Avec la clé du LLM configurée :

```powershell
.\.venv\Scripts\python.exe demo_culture_art.py --fixture
```

Le texte d'entrée reste synthétique, mais cette fois le modèle est réellement
appelé. Cela teste la clé de génération et ton agent sans dépendre de Supabase.

## 7. Lancer ton agent sur les vraies données

Après le diagnostic et la confirmation du modèle d'embeddings :

```powershell
.\.venv\Scripts\python.exe demo_culture_art.py "contemporary art and cultural identity in Tunisia" --top-k 5
```

Tu verras les passages récupérés, puis la contribution de ton agent. Si les
passages parlent seulement d'IA et de processeurs, change la requête et vérifie
la couverture culturelle du corpus. Un top-k retourne les plus proches ; il
ne garantit pas qu'ils soient assez pertinents. L'abstention est préférable
à une analyse inventée. Le prompt la demande, mais le jugement sémantique du
LLM doit encore être évalué sur vos vraies données.

## 8. Tester et documenter ton travail

```powershell
.\.venv\Scripts\python.exe -m pytest tests/agents/test_culture_art.py tests/agents/test_culture_integration.py -q
.\.venv\Scripts\python.exe evaluate_culture_art.py
```

L'évaluation appelle réellement le modèle six fois : trois cas, deux versions
de prompt. Elle conserve les résultats bruts et mesure seulement le schéma et
les références. Vérifie humainement la pertinence et les faits. Aucune mesure
live n'est pré-remplie dans ce dossier.

## 9. Relier ton agent à n8n quand les appels locaux fonctionnent

```powershell
.\.venv\Scripts\python.exe serve_culture_art.py
```

Le backend écoute localement sur 127.0.0.1:5001. Dans un deuxième terminal :

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5001/api/culture-art" -ContentType "application/json" -Body '{"query":"digital art and cultural heritage","top_k":5}'
```

Le fichier n8n/workflows/CultureArtAgent_Sarah_template.json est un modèle
WebHook > HTTP Python > réponse. Il est inactif et n'a pas été exécuté ici dans
n8n. Configure CULTURE_ART_API_URL dans l'environnement n8n ou remplace l'URL
par l'adresse réellement accessible du backend.

Si n8n est hébergé dans le cloud, 127.0.0.1 désigne son propre serveur, pas ton
PC. S'il tourne dans Docker, le réseau et l'adresse d'écoute du backend doivent
être adaptés par l'équipe. Si CULTURE_API_TOKEN est configuré côté Python,
ajoute Authorization: Bearer <token> au nœud HTTP via un credential privé n8n.

Ce workflow teste ton spécialiste seul. L'intégration complète avec les autres
agents, le Curator et la vision doit encore être raccordée et validée en équipe.

## 10. Lire ensuite

- docs/AUDIT_PROJET_SARAH.md : architecture, fichiers et défauts constatés.
- docs/COMPRENDRE_TON_AGENT.md : explication du code et exemples.
- docs/PROMPT_LIBRARY_CULTURE_ART.md : itération et protocole d'évaluation.
- docs/VALIDATION_SARAH.md : ce qui a été testé, et les limites.
