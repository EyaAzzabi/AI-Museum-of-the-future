# V5.3 — Reprendre après une limite de quota

Chaque lot dont le format a été validé est sauvegardé localement après sa réponse.
La même question avec les mêmes textes, modèle, endpoint et instructions réutilise
ces lots pendant 24 heures, même si un appel ultérieur échoue. Les citations
sauvegardées sont vérifiées à nouveau avant utilisation. La démo affiche la
progression sur stderr ; le JSON final reste sur stdout.

Cette version ne contourne pas le quota du fournisseur. Après une erreur 429,
attendre le renouvellement de la limite indiquée par le fournisseur avant de
relancer la même commande. Un quota journalier épuisé peut durer plus longtemps
qu'une limite par minute. Aucune relance automatique n'est ajoutée.

Les cinq lots de l'essai réalisé AVANT l'installation de cette version ne peuvent
pas être récupérés. Seuls les prochains essais sauvegarderont leur progression.
Si la rédaction finale échoue après la sélection, les lots de sélection sont
également réutilisables lors de la prochaine tentative.

Les checkpoints contiennent les décisions du modèle (dont certaines citations),
pas de clés API, dans data/processed/culture_reranker_cache. Ce répertoire est
exclu du suivi Git par le .gitignore existant. Il peut être supprimé pour repartir
sans cache. Le cache ne réutilise pas un lot lorsque ses paramètres ou textes
changent. Les fichiers expirés sont ignorés, sans suppression automatique.
Les avertissements de citations invérifiables de V5.2 restent visibles.

Installation : copier le contenu du ZIP dans AI-Museum-Sarah-Git et remplacer
les fichiers existants. Conserver le .env local.

Validation : 75 tests ciblés réussis, dont reprise après HTTP 429, invalidation
après changement de question/source, expiration et rejet des réponses mal formées.
Appels LLM simulés dans les tests ; résultat réel encore à vérifier sur le poste
configuré. Cette version réduit les appels répétés, pas les appels du premier essai.
