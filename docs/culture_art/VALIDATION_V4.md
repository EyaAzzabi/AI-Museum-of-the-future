# Validation v4 — 13 octobre 2026

- Suite complète : **305 passed**, dernier run 23,31 secondes.
- Suite ciblée pays + nouvelle recherche : **29 passed**.
- Compilation Python du module et des nouveaux tests réussie.
- Tests ajoutés : cosinus, invalidité/dimension des vecteurs, provenance,
  filtre lexical de pays, erreurs de lecture explicites, mots arbitraires,
  récupération d'une source absente de la RPC et compteurs.

Les clients et vecteurs sont simulés. Le CSV et les sorties live de Sarah
servent au diagnostic, mais les appels réels ne sont pas reproduits ici.
La pertinence sur le corpus, les embeddings de la source connue, les droits
SELECT/jointure et la qualité de génération restent à vérifier sur son PC.
