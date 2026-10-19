# Script démo — AI Museum of the Future (≈ 3–4 min)

Narration française pour la vidéo `AI_Museum_demo.mp4` (voix + sous-titres).

| # | Temps | Écran | Texte narré / sous-titre |
|---|---|---|---|
| 1 | 0:00–0:20 | Titre | Bienvenue dans AI Museum of the Future. Un musée virtuel qui raconte 2020–2026 comme si nous étions en 2126. |
| 2 | 0:20–0:45 | Architecture | Le pipeline collecte des sources publiques, les indexe en RAG hybride, puis cinq agents spécialistes analysent les preuves. |
| 3 | 0:45–1:15 | Agents | Historian, Sociologist, Technology, Culture & Art et Visual travaillent en parallèle, puis revue croisée, curateur et fact-check. |
| 4 | 1:15–1:45 | Multimodal | Le multimodal ne génère pas d’images : il lit les photos du corpus et décrit ce qu’elles montrent vraiment. |
| 5 | 1:45–2:20 | n8n | n8n orchestre le bout en bout : webhook, lancement de l’exposition, attente, puis téléchargement des images des salles — visibles en binaire dans le workflow. |
| 6 | 2:20–3:00 | Visite 3D | La visite immersive place ces images sur les murs des salles. Chaque section du curateur devient une galerie. |
| 7 | 3:00–3:30 | Fin | Résultat : une exposition sourcée, vérifiée, et un musée où l’on voit les archives réelles de notre époque. |

Fichiers générés par `python scripts/make_demo_video.py` :

- `docs/demo/AI_Museum_demo.mp4`
- `docs/demo/AI_Museum_demo.srt`
- `docs/demo/narration.wav` (si TTS disponible)
