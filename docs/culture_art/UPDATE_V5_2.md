# V5.2 — Une citation incorrecte ne bloque plus les autres sources

Le message réel indiquait : batch 2/10, Unsupported evidence quote.
Cela établit qu'une citation produite par le modèle n'était pas retrouvée dans
l'extrait fourni ; cela ne permet pas de déterminer si elle était reformulée,
inventée ou simplement espacée autrement.

La correction accepte uniquement des différences d'espacement (espaces,
retours à la ligne, espaces insécables). Les mots, leur ordre et la ponctuation
restent vérifiés. La citation enregistrée est le passage exact du texte source.
Une traduction, une paraphrase ou des points de suspension ajoutés ne passent pas.

Une citation invérifiable entraîne l'exclusion de son candidat, puis l'examen
continue. Les IDs exclus figurent dans retrieval.rerank_quote_rejections et un
avertissement apparaît dans warnings. La couverture peut être incomplète.
Si aucune source n'est acceptée et qu'au moins une citation a échoué, une erreur
explicite subsiste : on ne présente pas cet échec comme une absence de données.
Les erreurs de quota, de JSON et de schéma restent explicites. Aucun appel LLM
supplémentaire n'est ajouté. Une citation textuellement présente ne prouve pas
à elle seule sa pertinence ni toutes les affirmations de la réponse.

Installation : décompresser puis copier tout le contenu dans AI-Museum-Sarah-Git,
en acceptant le remplacement. Ne pas changer .env.

Validation locale : 71 tests ciblés réussis, dont espacement Unicode, rejet des
reformulations, poursuite au lot suivant et transmission des avertissements.
Les réponses LLM sont simulées dans ces tests. Relancer la question réelle pour
vérifier le comportement avec le fournisseur et le corpus de Sarah.
