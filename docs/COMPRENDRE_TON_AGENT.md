# Comprendre ton agent, du sujet d'exposition à la réponse

## Un exemple concret

Le visiteur demande : « L'art numérique et l'identité culturelle en Tunisie ».
Cette question ne contient pas les sources. La recherche doit les retrouver
avant que ton agent puisse rédiger une analyse fiable.

| Objet | Exemple | À quoi il sert |
|---|---|---|
| Document | Article sur une exposition | Source complète |
| Chunk | Paragraphe de cet article | Unité récupérée par le RAG |
| Embedding | Liste de 384 ou 1536 nombres | Représentation pour la similarité |
| chunk_id | UUID du passage | Référence précise de la preuve |
| metadata | Source, catégorie, titre si présents | Provenance et filtres |
| InsightObject | Perspective, findings, IDs | Contribution standard envoyée au Curator |

Supabase n'est pas ton modèle IA. C'est la base qui conserve les documents,
passages, vecteurs et metadata. Le modèle d'embeddings effectue la représentation.
Le LLM effectue l'analyse et la rédaction. n8n déclenche et relie les opérations.

## Ce que ton agent doit apporter

Repérer la signification culturelle : identité, mémoire collective, esthétique,
patrimoine, symboles, pratiques artistiques ou médiatiques. Exemple :
- Observation : l'extrait décrit une exposition d'œuvres numériques à Tunis.
- Interprétation : ces œuvres pourraient illustrer une section sur l'identité
  exprimée par les médias numériques.
- Hypothèse future : une piste de réflexion sur la conservation de ces formes,
  annoncée comme hypothèse, et non comme événement établi.

Une source locale ne prouve pas une tendance mondiale. Un lien vers une image
ne permet pas d'affirmer sa couleur ou sa composition. Pour cela, il faut une
observation de l'agent vision liée à la même source.

## Le code agents/culture_art.py, bloc par bloc

### Les imports

- future annotations : facilite les annotations de types sans les résoudre
  immédiatement ; ce n'est pas un traitement IA.
- json : transforme les preuves Python en texte JSON lisible par le LLM.
- Mapping : accepte les chunks dictionnaires, notamment ceux d'un appel HTTP.
- Path : construit le chemin du prompt sans dépendre du dossier du terminal.
- Any : certains objets de clients et chunks ont des formes différentes.
- BaseAgent : classe commune qui fournit les appels LLM et la lecture du prompt.
- InsightObject : dataclass commune représentant la réponse d'un spécialiste.

### class CultureArtAgent(BaseAgent)

L'héritage signifie que CultureArtAgent réutilise les méthodes communes de
BaseAgent. Tu spécialises le contenu et les vérifications sans refaire la
connexion au fournisseur pour chaque membre du groupe.

### __init__(openai_client, prompt_path=None)

openai_client désigne un client compatible avec le SDK OpenAI. Dans votre
projet, il peut être connecté à Groq : ce nom ne veut pas dire que vous payez
l'API OpenAI. prompt_path permet d'essayer une autre version de prompt.

Path(__file__).resolve().parents[1] retrouve la racine depuis ce fichier,
puis /prompts/culture_art.md donne le prompt par défaut. super().__init__
enregistre le client et le chemin dans la classe parent.

### _load_prompt_template()

Charge le fichier via BaseAgent, puis retire l'en-tête de version avant la
ligne --- pour envoyer seulement les instructions actives au modèle.
L'historique reste visible dans le fichier pour le professeur.

### _evidence(chunk)

Uniformise un dictionnaire ou un objet RetrievalResult. La fonction interne
read utilise chunk.get pour un dictionnaire ou getattr pour un objet.
Elle produit quatre champs : chunk_id, document_id, content et metadata.

Le chunk_id vient d'abord de chunk_id, sinon id, sinon document_id pour les
objets anciens. Les vrais RetrievalResult ont un chunk_id ; préfère ce format.
Le fallback document_id ne distingue pas plusieurs morceaux d'un même document.

Pourquoi inclure l'ID dans le prompt ? Le modèle ne peut pas citer correctement
un identifiant que le code ne lui a jamais montré. C'était le défaut du renderer
textuel initial. Les metadata ne sont pas inventées : l'agent transmet ce qu'il
reçoit réellement.

### _strings(value)

Vérifie que la réponse est bien une liste. Conserve seulement les chaînes non
vides, supprime les espaces aux extrémités et les doublons en gardant l'ordre.
Sans ce contrôle, parcourir une chaîne comme "art-1" produirait cinq caractères
au lieu d'une liste de références.

### run(chunks)

1. Convertit les passages en preuves structurées.
2. Ignore les éléments sans référence ou contenu exploitable.
3. Si rien ne reste, retourne un InsightObject vide sans appel LLM.
4. Définit le rôle dans le system prompt et rappelle que les documents sont des
   données, jamais des instructions à suivre.
5. Sérialise les preuves en JSON, charge le prompt et remplace {chunks}.
6. Appelle _call_llm, méthode héritée de BaseAgent.
7. Construit l'ensemble des références autorisées à partir des entrées.
8. Ne garde que les selected_artifacts présents dans cet ensemble.
9. Nettoie les findings et vérifie perspective, findings et références.
10. Si le résultat est incomplet, s'abstient. Sinon, retourne InsightObject.

L'appel LLM est la partie probabiliste. La vérification d'appartenance des IDs
est une règle déterministe Python. Les deux sont complémentaires.

### _insufficient()

Retourne agent="culture_art", perspective="", key_findings=[],
selected_artifacts=[]. L'ensemble vide permet au Curator existant de reconnaître
une perspective manquante. Le script/API expose en plus status=insufficient_evidence.
Il peut s'agir d'absence de preuves ou d'une réponse modèle inutilisable ;
ces deux causes ne sont pas distinguées par le contrat partagé actuel.

## À quoi ressemble une sortie

```json
{
  "agent": "culture_art",
  "perspective": "Digital art and local identity in Tunis.",
  "key_findings": [
    "Observation: the exhibition explores identity through digital artworks [art-1]."
  ],
  "selected_artifacts": ["art-1"]
}
```

Cet exemple est illustratif, pas extrait de votre Supabase. Le Curator reçoit
cette contribution avec celles des autres membres. Il peut rapprocher la même
source utilisée par deux spécialistes et construire un récit cohérent.

## Le nouveau chemin de recherche

culture_retrieval.py a été ajouté pour ton test standalone sans changer le
Retriever général de l'équipe.

- build_supabase_client lit URL et clé dans .env et crée le client.
- diagnose_supabase lit les comptes et un échantillon, sans retourner les vecteurs.
- vector_dimension lit la taille d'un vecteur liste ou chaîne JSON.
- embed_query utilise le backend explicitement configuré. Le chemin Gemini
  reprend gemini-embedding-001 et 1536 du workflow, avec RETRIEVAL_QUERY.
- retrieve_culture vérifie la requête et top_k, compare la dimension d'un
  échantillon, vectorise, appelle match_chunks, convertit et trie les résultats.
- Une erreur réseau/RPC déclenche une erreur explicite. Elle n'est pas présentée
  comme une recherche réussie sans données.

La dimension d'un échantillon ne garantit pas l'homogénéité de toute la base,
ni son modèle d'origine. C'est pourquoi le guide propose aussi du SQL en
lecture seule et une confirmation auprès de la personne qui a indexé les données.

## Qu'est-ce que le prompt v2 améliore ?

Il donne une spécialité claire, un format de sortie, une règle de citation,
un exemple pertinent et un exemple d'abstention. Il distingue les faits des
interprétations et n'encourage pas des généralités non documentées.

Il ne suffit pas de dire « n'hallucine pas ». L'identification des preuves,
les contrôles Python, les essais adversariaux et une évaluation humaine restent
nécessaires. Ne présente pas le filtre d'IDs comme une preuve d'exactitude totale.

## Pourquoi il y a plusieurs modes dans demo_culture_art.py

| Mode | Supabase | Vrai LLM | Utilité |
|---|---|---|---|
| --offline | Non | Non | Comprendre et vérifier les imports/contrat |
| --diagnose | Oui, lecture seule | Non | Vérifier base, permissions et dimensions |
| --fixture | Non | Oui | Vérifier fournisseur, prompt et sortie |
| requête live | Oui, lecture seule | Oui | Tester ton agent sur les vraies données |

Séparer ces modes aide à localiser l'erreur. Si fixture fonctionne mais live
échoue, ce n'est probablement pas le même problème qu'un mauvais accès au LLM.

## Ce que tu peux défendre à l'oral

« Je développe le spécialiste CultureArt. Il utilise les passages récupérés
par le RAG pour identifier des pratiques artistiques et leur sens culturel.
J'ai conservé le contrat partagé avec le Curator, ajouté les références dans
le contexte, contrôlé les IDs retournés et prévu une abstention. J'ai séparé
le diagnostic de Supabase, la génération sur fixture et l'essai sur corpus réel,
car un test simulé ne prouve pas la qualité du retrieval live. »

Pour dire que le prompt v2 est meilleur, montre les résultats réellement
obtenus avec evaluate_culture_art.py et tes annotations. Pour dire que le RAG
est performant, annote des passages pertinents et calcule une métrique réelle.
