# Validation de la livraison — 13 octobre 2026

## Reproduit ici

- python -m pytest tests -q : **276 passed**, 14,86 secondes sur le dernier run.
- python demo_culture_art.py --offline : contrat correct et référence inventée
  rejetée, sans appel Supabase/LLM.
- Compilation Python des agents, du RAG et des trois nouveaux scripts réussie.

La suite inclut les tests existants et les nouveaux contrôles CultureArt,
Gemini/RPC/dimensions et API Flask avec test_client. Les frontières Supabase
et LLM sont simulées. Le modèle fastembed réel n'a pas été téléchargé ni évalué ;
son interface est testée avec un modèle fictif.

## À vérifier avec l'équipe

Le .env récemment reçu par Sarah n'est pas accessible ici. Contenu, droits,
index, RPC et modèle d'embeddings Supabase restent à confirmer. Les appels
LLM réels, l'évaluation avant/après, l'import/exécution n8n, le réseau vers
le backend et l'intégration vision/Curator n'ont pas été exécutés ici.
Aucune métrique réelle de retrieval ou qualité des réponses n'est inventée.

## Périmètre

Le projet complet évite les imports manquants du complément précédent.
Les collecteurs, dashboard, workflow initial et autres spécialistes sont
conservés. Leurs anomalies sont documentées, pas toutes corrigées.
La livraison traite CultureArt et son exécution indépendante.

Modifications : agents/culture_art.py, prompts/culture_art.md, .env.example,
README.md. Ajouts : prompt v1, script de démonstration, backend HTTP,
évaluateur de prompts, dépendances minimales, adaptateur de recherche,
fixture synthétique, template n8n, tests ciblés et guides.

Nouvelle copie de travail ; aucun commit/push, changement Supabase ou
activation n8n. Aucune clé privée incluse dans le ZIP livré.

## Mise à jour v3 après le premier essai live de Sarah

- Suite complète : **292 passed**, dernier run 21,58 secondes.
- 16 nouveaux tests : scope FR/EN/AR, comparaison multi-pays, conflit pays,
  pays éditeur vs pays sujet, titres hors Tunisie, requête transmise au prompt,
  citations de findings, overfetch/filtrage et compteurs, statut et validation API.
- Mode offline v3 exécuté et imports réussis ; LLM simulé explicitement.
- Le cas réel fourni par Sarah est utilisé pour une régression locale sur les
  titres hors pays ; aucun appel privé Supabase ou LLM réel reproduit ici.
- Les conclusions prudentes demandées par le prompt restent à évaluer lors
  d'un nouvel appel live. Les filtres de pays et citations ne prouvent pas
  automatiquement la pertinence thématique ou le support factuel.
