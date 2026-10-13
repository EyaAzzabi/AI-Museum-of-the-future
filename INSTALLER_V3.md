# Installer l'amélioration v3 sans réinstaller le projet

Cette archive contient uniquement les fichiers à ajouter/remplacer dans ton
projet actuel. Ferme le serveur Python si tu l'avais lancé. Copie le CONTENU
de ce complément dans ton dossier qui contient app.py et demo_culture_art.py,
en acceptant la fusion des dossiers et le remplacement des fichiers listés.

Conserve ton .env, ta .venv et le cache du modèle : ils ne sont pas inclus et
n'ont pas besoin d'être recréés. Le backend reste CULTURE_EMBEDDING_BACKEND=local
si la base a bien été indexée avec le modèle MiniLM utilisé par l'équipe.

Depuis le dossier du projet :

```powershell
.\.venv\Scripts\python.exe -m pytest tests/agents/test_culture_scope.py -q
.\.venv\Scripts\python.exe demo_culture_art.py "contemporary art and cultural identity in Tunisia" --top-k 5
```

Le pays est détecté automatiquement pour cette requête. Pour un sujet qui
ne nomme pas le pays, tu peux le préciser :

```powershell
.\.venv\Scripts\python.exe demo_culture_art.py "contemporary art and cultural identity" --country Tunisia --top-k 5
```

Regarde retrieval.candidate_count, rejected_country_count et returned_count.
status=references_validated signifie que les références des findings ont passé
les contrôles Python, pas que leurs affirmations sont automatiquement prouvées.
status=insufficient_evidence est possible si les candidats ne fournissent pas
de données suffisantes ; cela ne certifie pas que la base entière est vide.

Le terminal affiche désormais directement les caractères arabes en UTF-8.
La vérification géographique est un heuristique avec limites, expliquées dans
docs/AMELIORATION_V3_DEEP_LEARNING.md. Aucun changement Supabase n'est requis.

Le complément n'est pas un projet autonome : ouvre toujours ton dossier complet.
