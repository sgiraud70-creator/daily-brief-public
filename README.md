# daily-brief-public

Dépôt public de **publication d'un briefing audio quotidien**.

## Contenu du dépôt

| Fichier | Description |
|---|---|
| `brief.mp3` | Le briefing audio le plus récent (MP3, mono, 48 kbps, 24 kHz). Ce fichier est **écrasé** à chaque nouvelle publication : le dépôt ne conserve pas d'archive, seul le dernier brief est disponible en l'état. Les versions antérieures restent accessibles via l'historique Git. |
| `README.md` | Ce document. |

## Fonctionnement

Un processus automatisé publie régulièrement une nouvelle version de `brief.mp3`
via des commits `chore: publish daily brief audio` signés par
`github-actions[bot]`. La cadence observée est d'environ **une à deux publications
par jour**.

> ℹ️ Le code qui **génère** et **pousse** le briefing (script, workflow GitHub
> Actions, source des contenus) ne se trouve pas dans ce dépôt. Celui-ci ne sert
> qu'à **héberger et diffuser** le fichier audio résultant.

## Récupérer le brief

Cloner le dépôt :

```bash
git clone https://github.com/sgiraud70-creator/daily-brief-public.git
```

Ou télécharger directement le dernier fichier :

```bash
curl -L -o brief.mp3 \
  https://raw.githubusercontent.com/sgiraud70-creator/daily-brief-public/main/brief.mp3
```

## Consulter un brief antérieur

Comme `brief.mp3` est écrasé à chaque publication, on retrouve une version passée
par l'historique Git :

```bash
# Lister les publications
git log --oneline -- brief.mp3

# Restaurer le fichier tel qu'il était à un commit donné
git checkout <hash_du_commit> -- brief.mp3
```
