# V5.1 — Identifier l'erreur de sélection

Ce correctif remplace le message d'erreur générique de V5 par un diagnostic
qui indique le lot en échec et la catégorie du problème, sans imprimer les
messages bruts du fournisseur ni les clés. Il ne prétend pas résoudre une
cause qui n'est pas encore connue.

Copier les fichiers de ce ZIP dans AI-Museum-Sarah-Git, accepter le remplacement,
puis relancer exactement la question précédente. Aucun changement du .env.

- LLM_HTTP_429 : limite de débit ou quota ; consulter le fournisseur.
- LLM_HTTP_401/403 : authentification ou accès au modèle.
- LLM_HTTP_400 : requête refusée ; paramètres ou génération JSON possibles.
- LLM_TIMEOUT / LLM_CONNECTION : délai réseau / connexion.
- MODEL_JSON : réponse JSON illisible.
- MODEL_FORMAT : format, identifiants ou citation ne respectant pas le contrat.
- LLM_CLIENT_OR_RESPONSE : autre erreur de configuration ou de réponse.

Le classement et les exigences de preuve sont inchangés. Aucun résultat partiel
n'est présenté comme une sélection complète. Aucun nouvel appel automatique.
Transmettre uniquement le nouveau message de diagnostic pour corriger la cause.
