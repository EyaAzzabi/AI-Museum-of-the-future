# CultureArt v3 : comprendre l'amélioration en Deep Learning

## Le résultat réel qui a déclenché cette itération

Sarah a lancé "contemporary art and cultural identity in Tunisia". Supabase a
retourné cinq titres : arts/patrimoine égyptiens et patrimoine marocain à Baku.
L'agent a rédigé une perspective sur l'Égypte et au-delà, marquée "supported".
La connexion fonctionnait, mais la contrainte géographique n'était pas respectée.
Certains titres ont également donné lieu à des interprétations trop affirmatives.

Ce constat vient de la sortie live fournie par Sarah, pas d'une reproduction
locale contre sa Supabase. Aucun accès privé n'est inclus dans la livraison.

## 1. Où est le Deep Learning dans ce système ?

| Composant | Nature | Rôle |
|---|---|---|
| MiniLM multilingue | Réseau neuronal Transformer préentraîné | Encoder les textes pour la similarité |
| LLM configurable | Modèle neuronal de génération, architecture exacte dépendant du modèle choisi | Produire une analyse à partir du prompt et des sources |
| Cosine similarity/pgvector | Calcul/index de recherche | Comparer les vecteurs et récupérer une shortlist |
| Filtre de pays et contrôle d'IDs | Règles déterministes Python | Appliquer des contraintes explicites |
| Supabase | Base de données | Stocker et restituer les données |
| n8n | Orchestration | Déclencher et raccorder les appels |

Une application de Deep Learning n'exige pas que chaque opération soit un
réseau neuronal. Une règle géographique explicite peut être appliquée en Python
pendant que le réseau traite la proximité sémantique des textes.

## 2. Le modèle d'embeddings, de l'entrée aux 384 nombres

MiniLM est utilisé comme sentence embedding model. Les étapes conceptuelles :

1. Tokenisation : le texte est découpé en tokens, souvent des sous-mots.
2. Embeddings de tokens et positions : représentation vectorielle initiale.
3. Couches Transformer : les représentations deviennent contextuelles grâce
   à l'attention et aux blocs de transformation neuronaux.
4. Pooling : agrégation des représentations de tokens en une représentation
   de phrase/passage. La fiche de ce modèle indique mean pooling avec masque.
5. Sortie : un vecteur dense de 384 valeurs.

Les 384 coordonnées ne correspondent pas chacune à un concept humain nommé.
Ce ne sont pas 384 mots ou 384 catégories. C'est une représentation distribuée,
apprise à partir des données d'entraînement du modèle.

Pour une requête q et un passage d :

    u = encoder(q), v = encoder(d)
    cosine(u,v) = (u·v) / (||u|| ||v||)

Le produit scalaire compare leur direction après division par leurs normes.
Le cosinus mathématique est entre -1 et 1 ; le Retriever du projet borne la
valeur exposée entre 0 et 1. Un score de 0,745 n'est pas une probabilité de 74,5 %
de vérité, ni une garantie que le pays, la date ou la modalité sont respectés.

## 3. Pourquoi l'anglais peut retrouver de l'arabe

Le modèle est multilingue. Ses représentations visent à rapprocher des textes
sémantiquement similaires, y compris dans des langues différentes. "Contemporary
art" et "الفنون المعاصرة" peuvent donc être proches sans partager les mêmes
caractères. Cette capacité est utile ; la récupération de titres arabes n'est
pas en soi un défaut. Le décalage Égypte/Tunisie est le problème de scope.

La recherche sémantique optimise une proximité globale. La présence de "Tunisia"
dans la requête ne garantit pas que chaque meilleur résultat mentionne ce pays.
Le système doit appliquer explicitement les contraintes qui sont obligatoires.

## 4. L'attention, intuitivement

Dans un Transformer, chaque token est transformé en représentations Query,
Key et Value par des projections apprises. L'attention compare les Queries
aux Keys et pondère les Values pour produire une représentation contextuelle :

    Attention(Q,K,V) = softmax(QKᵀ / sqrt(d_k)) V

Plusieurs têtes et couches permettent d'exploiter différentes relations.
Cela ne donne pas une garantie symbolique du type "tout résultat doit concerner
la Tunisie". La contrainte produit doit être appliquée au niveau du pipeline.

Attention : Query dans cette équation désigne une représentation interne d'un
token ; ce n'est pas exactement la requête d'exposition envoyée par l'utilisateur.

## 5. Le LLM a une autre tâche

L'encodeur produit un vecteur. Le LLM produit une séquence de texte.
Pour un générateur autorégressif, chaque token est conditionné par le contexte
et les tokens déjà produits. Le contexte comprend le rôle, la question, les
règles et les passages sélectionnés. Cette génération peut produire des phrases
plausibles qui dépassent les faits présents dans un titre.

Le LLM ne lit pas automatiquement toute la Supabase. Il reçoit uniquement les
sources incluses dans son prompt. Jusqu'à v2, ton agent recevait ces sources,
mais pas le sujet original. La version v3 lui transmet les deux.

## 6. Amélioration de la recherche

Avant : récupérer les cinq passages les plus proches, indépendamment du pays.
Après pour une requête mono-pays reconnue :

- récupérer jusqu'à dix fois top_k candidats, plafonnés à 100 ;
- conserver les passages contenant une mention reconnue du pays, de certaines
  variantes linguistiques, ou une metadata explicite country/country_code ;
- trier par similarité et retourner jusqu'à top_k passages restants ;
- afficher les nombres de candidats, rejets géographiques et passages retenus.

La sourcecountry d'un média n'est pas utilisée : un journal tunisien peut
parler d'une exposition en Égypte. Le pays de l'éditeur n'est pas forcément
le pays de l'événement.

Les 36 pays de data/regions.py sont reconnus par leur nom anglais ; quelques
pays ont aussi des variantes FR/AR. La Tunisie inclut Tunis et des adjectifs.
Une requête comparative avec plusieurs pays reconnus n'est pas réduite
arbitrairement à un seul pays. --country peut préciser un scope mono-pays.
Un conflit entre --country et une requête explicitement différente est rejeté.

Limites : ce filtre peut accepter une mention incidente ou manquer une
référence implicite à un lieu. Il opère sur une shortlist, pas sur tous les
7296 passages de la base. Une liste vide ne prouve pas une absence dans le corpus.
Il faut mesurer le compromis précision/rappel, puis enrichir les metadata de
pays et la couverture du corpus si nécessaire.

## 7. Amélioration de l'agent et du prompt

run(chunks, query=..., country=...) transmet la question et réapplique le filtre
pour protéger aussi les appels directs. Si aucun passage n'est dans le scope,
il s'abstient sans appeler le LLM.

Le prompt v3 distingue :
- Observation : le titre annonce explicitement un débat sur l'art numérique.
- Tentative interpretation : ce débat pourrait introduire une question pour
  l'exposition ; ce n'est pas une tendance démontrée.

Un débat sur une influence n'établit pas cette influence. Des activités
annoncées ne prouvent ni leur impact, ni leur succès. Les titres ne permettent
pas d'inventer des motifs antiques ou des formes artistiques non mentionnées.

Pour les nouveaux appels avec query/country, Python exige une citation [id]
dans chaque finding. Les références doivent appartenir aux selected_artifacts
validés. Les findings sans citation ou contenant une citation inconnue sont
écartés, puis les IDs non utilisés sont supprimés.

Compatibilité : run(chunks) continue d'accepter le contrat historique du pipeline
de l'équipe. Ce chemin ne dispose toujours pas de la requête et n'applique pas
le contrôle de citations renforcé. Pour bénéficier entièrement de v3 dans la
synthèse globale, l'équipe doit transmettre la requête originale aux spécialistes.

Le statut de la démonstration/API devient references_validated, avec warnings
et limitations. Il ne signifie pas que les faits ou la pertinence sémantique
ont été certifiés. Le système ne calcule pas une confiance factuelle calibrée.

## 8. Nous n'avons pas réentraîné le modèle

Le modèle d'embeddings et le LLM restent préentraînés. L'exécution utilise leur
inférence. Aucun backpropagation, calcul de loss ou mise à jour des poids n'est
réalisé dans cette amélioration. Changer les prompts ou ajouter un filtre ne
constitue pas un fine-tuning.

Cela correspond aux exigences du projet : justifier le corpus, la recherche,
les agents, les prompts, la multimodalité et l'automatisation. Si l'équipe envisage
un fine-tuning plus tard, il faut d'abord un jeu annoté, une séparation train/test
et une mesure d'amélioration ; le bug observé ne justifie pas à lui seul un tel coût.

## 9. Évaluer avant/après

La requête de Sarah est un cas d'échec réel v2. Les tests v3 reproduisent les
passages reçus et contrôlent l'abstention hors pays, mais simulent le LLM.
Ils ne prouvent pas la qualité du prompt sur un vrai appel.

Après remplacement des fichiers, relancer la même requête avec top_k=5.
Noter : nombre de candidats, rejets, passages retenus, adéquation pays,
pertinence art/identité, citations et affirmations au-delà des sources.

Mesures possibles :
- précision pays parmi les résultats retournés ;
- précision thématique annotée humainement ;
- proportion de findings avec références valides ;
- proportion d'affirmations réellement soutenues par les sources ;
- abstention appropriée sur cas hors domaine ou sources insuffisantes.

Un taux parfait de références valides ne prouve pas un taux parfait de faits
corrects. Si aucun passage n'est retourné, ne déclarer pas la précision égale à 100 %.

## 10. Point à vérifier ensuite sur le chunking

La fiche Sentence Transformers annonce max_seq_length=128 pour ce modèle,
alors que votre chunker Python annonce 512 tokens tiktoken. Les tokenizers ne
sont pas identiques et le runtime fastembed peut avoir sa propre configuration.
Vérifier la longueur effectivement encodée/tronquée avant toute réindexation.
Ne pas modifier le chunking sans réencoder les documents de manière cohérente.

## Sources primaires consultées

- Fiche officielle du modèle : https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- Sentence-BERT : https://arxiv.org/abs/1908.10084
- Attention Is All You Need : https://arxiv.org/abs/1706.03762
