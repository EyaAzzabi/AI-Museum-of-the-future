# Validation V5 — 13 octobre 2026

- Suite complète : **320 tests réussis** (21,54 s), dont 15 nouveaux tests.
- Après ajout du délai réseau, de la limite de requête et du script d'évaluation :
  nouveaux tests réexécutés, compilation Python et démo offline réussies.
- `git diff --check` : aucune erreur d'espacement.
- Les appels Supabase/LLM sont simulés dans les tests automatiques.
- Aucun fine-tuning, aucune modification des données Supabase.
- Aucun résultat réel V5 ni gain de précision annoncé : exécuter
  `evaluate_culture_live.py --live` sur le poste configuré, puis examiner les sources.

Les tests couvrent notamment la récupération d'un candidat classé 79e avant
sélection, l'absence d'appel sur une liste vide, le budget et les troncatures,
les IDs inventés/dupliqués, les notes invalides, les citations inventées,
l'ordre des résultats et l'absence de fuite du message privé d'une erreur SDK.
Ils valident les contrats du programme ; le classement sémantique réel reste
un jugement du modèle à mesurer avec des sources annotées.
