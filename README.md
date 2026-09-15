# Le Brief — briefing quotidien automatisé

Génération et envoi automatiques, **chaque matin à 07 h 00 (Europe/Paris)**, d'un
**e-mail HTML** (charte noir & doré, lisible en 3-5 min) et d'une **version audio
MP3** (à écouter). Tout tourne **sur GitHub Actions**, sans ordinateur personnel
allumé, et **à 0 €** (offres gratuites uniquement).

## Principe d'architecture

La **collecte est déterministe** : les informations viennent d'APIs et de flux RSS
(jamais inventées). Le modèle de langage (Mistral) ne fait que **sélectionner,
classer et résumer** les éléments réellement collectés — il n'invente **aucune**
source ni URL. La mémoire anti-répétition évite de reproposer un sujet déjà traité
dans les 7 derniers jours.

## Rubriques

Météo (Loulans-Verchamp) · Actualité locale · France · International · IA &
technologies · Applications / no-code / automatisation · Impression 3D · Vie
pratique · Sport général · Prochain match des Steelers · Prochain match du PSG.

## Structure du dépôt

| Dossier / fichier | Rôle |
|---|---|
| `src/` | Modules : collecte (météo, RSS, sport, mémoire), rédaction (LLM), rendu (image météo, e-mail), audio (TTS), envoi (SMTP). |
| `scripts/` | Étapes exécutables du pipeline (`build_weather`, `build_collecte`, `build_redaction`, `build_email`, `build_audio`, `send_email`). |
| `config/` | Lieu (`lieu.yml`) et sources RSS par rubrique (`sources_rss.yml`). |
| `templates/` | Gabarit d'e-mail Jinja2. |
| `.github/workflows/brief.yml` | Orchestration de production (planification + envoi). |
| `public/` | Sorties publiées : `email.html`, `brief.mp3`, `weather.png`. |
| `data/` | État : `brief.json`, `collected.json`, `history.json` (mémoire), `script_audio.txt`. |

## Fonctionnement (production)

`brief.yml` se déclenche via deux créneaux cron (UTC) encadrant 07 h 00 Paris ; une
étape « gardien » ne laisse passer que l'exécution correspondant à **07 h locales**
(gère le changement d'heure). Chaîne : météo → collecte (RSS + sport) → rédaction
(LLM) → rendu e-mail → audio → publication de `public/` → envoi e-mail.

Un déclenchement **manuel** est possible (onglet *Actions* → *Brief quotidien* →
*Run workflow*) pour un envoi de rattrapage.

## Secrets requis (GitHub Actions)

| Secret | Usage |
|---|---|
| `MISTRAL_API_KEY` | Rédaction (résumé/sélection). |
| `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO` | Envoi SMTP Gmail (mot de passe d'application). |
| `METEOFRANCE_APP_ID` | *Optionnel* — vigilance Météo-France (omise sans lui). |

Sans les secrets Gmail, tout est généré et publié mais **rien n'est envoyé** (repli
propre, sans erreur).

## Récupérer les sorties

```bash
# Dernier audio
curl -L -o brief.mp3 \
  https://raw.githubusercontent.com/sgiraud70-creator/daily-brief-public/main/public/brief.mp3

# Dernier e-mail (HTML)
curl -L -o email.html \
  https://raw.githubusercontent.com/sgiraud70-creator/daily-brief-public/main/public/email.html
```

Ces fichiers sont **écrasés** à chaque publication ; les versions antérieures
restent accessibles via l'historique Git (`git log -- public/brief.mp3`).

## Moteurs & sources principaux

Open-Meteo (météo, sans clé) · Météo-France (vigilance) · flux RSS thématiques et
Google Actualités · Wikipédia FR (calendrier PSG) · TheSportsDB (NFL/Steelers) ·
Mistral (rédaction) · edge-tts avec repli Piper (audio) · SMTP Gmail (envoi).
