"""Rédige le brief écrit à partir de data/collected.json → data/brief.json.

Nécessite un secret LLM (MISTRAL_API_KEY). Applique la mémoire anti-répétition
(sujets des 7 derniers jours passés en « déjà traités »).

Usage : python -m scripts.build_redaction
"""
from __future__ import annotations

import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

from src.collecte import memoire, sports
from src.redaction import redacteur

def _match_sujet(m: dict | None, equipe: str) -> dict:
    """Construit un sujet déterministe pour le prochain match (aucune invention)."""
    if not m:
        return {"title": f"{equipe} — prochain match",
                "bullets": ["Information indisponible ce matin."], "sources": []}
    bullets = [f"Adversaire : {m['adversaire']} ({m['domicile']})"]
    if m.get("competition"):
        bullets.append(f"Compétition : {m['competition']}")
    bullets.append(f"Date : {m['date_txt']} (heure de Paris)")
    if m.get("stade"):
        bullets.append(f"Stade : {m['stade']}")
    bullets.append(f"Diffusion : {m['diffusion'] or 'à confirmer'}")
    sources = []
    if m.get("source_url"):
        sources.append({"name": m.get("source_name", "Source"), "url": m["source_url"]})
    return {"title": f"Prochain match : {equipe} {m['domicile']} contre {m['adversaire']}",
            "bullets": bullets, "sources": sources}


def build_sport_rubriques() -> list[dict]:
    steelers = _match_sujet(sports.steelers_next(), "les Steelers")
    psg = _match_sujet(sports.psg_next(), "le PSG")
    return [
        {"label": "Sport — Pittsburgh Steelers", "sujets": [steelers]},
        {"label": "Sport — PSG", "sujets": [psg]},
    ]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTED = os.path.join(ROOT, "data", "collected.json")
HISTORY = os.path.join(ROOT, "data", "history.json")
OUT = os.path.join(ROOT, "data", "brief.json")

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def date_str(d: dt.date) -> str:
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}".capitalize()


def estimate_read_minutes(rubriques: list[dict]) -> int:
    words = 0
    for r in rubriques:
        for s in r.get("sujets", []):
            words += len(s.get("title", "").split())
            for b in s.get("bullets", []):
                words += len(b.split())
    return max(2, round(words / 200))


def main() -> int:
    with open(COLLECTED, encoding="utf-8") as f:
        collected = json.load(f)

    history = memoire.prune(memoire.load(HISTORY))
    deja = [h.get("title", "") for h in history]

    rubriques = redacteur.rediger(collected, deja)

    # Mémoriser les sujets publiés (avec URL) pour l'anti-répétition (EF-11)
    published = []
    for r in rubriques:
        for s in r.get("sujets", []):
            for src in s.get("sources", []):
                published.append({"url": src["url"], "title": s.get("title", ""),
                                  "rubrique": r.get("label", "")})
    today = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
    memoire.save(HISTORY, memoire.remember(history, published, today))

    # Sports en déterministe (ajoutés après la mémoire : on veut toujours le prochain match)
    rubriques = rubriques + build_sport_rubriques()

    brief = {
        "date_str": date_str(today),
        "audio_minutes": 11,
        "read_minutes": estimate_read_minutes(rubriques),
        "rubriques": rubriques,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)

    n = sum(len(r.get("sujets", [])) for r in rubriques)
    print(f"✓ {OUT}  ({n} sujets rédigés, lecture ~{brief['read_minutes']} min)")
    for r in rubriques:
        note = "" if r.get("sujets") else f"  ({r.get('note', 'vide')})"
        print(f"  · {r['label']:42s} {len(r.get('sujets', [])):2d}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
