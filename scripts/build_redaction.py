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

from src.collecte import fete, memoire, sports
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


def build_fete_rubrique() -> dict | None:
    """Rubrique déterministe « Fête du jour » (source Nominis, aucune invention)."""
    f = fete.fete_du_jour()
    if not f:
        return None
    return {"label": "Fête du jour", "sujets": [{
        "title": f"Aujourd'hui, on souhaite la fête : {f['nom']}",
        "bullets": [],
        "sources": [{"name": f["source_name"], "url": f["source_url"]}],
    }]}


def build_sport_rubriques() -> list[dict]:
    # Steelers : prochain match + classement AFC Nord + classement adversaire
    # + 3 infos sur l'équipe. Tout est déterministe (aucune invention).
    sm = sports.steelers_next()
    steelers = _match_sujet(sm, "les Steelers")
    sctx = sports.steelers_context(sm)
    if sctx.get("mon_rang"):
        steelers["bullets"].append(f"Classement : {sctx['mon_rang']}")
    if sctx.get("adv_rang"):
        steelers["bullets"].append(f"Adversaire au classement : {sctx['adv_rang']}")
    if sctx.get("infos"):
        steelers["bullets"].append("Les Steelers — " + " · ".join(sctx["infos"]["infos"]))

    # PSG : prochain match + classement Ligue 1 + Ligue des champions (si en lice)
    # + classement de l'adversaire + 3 infos sur l'adversaire.
    pm = sports.psg_next()
    psg = _match_sujet(pm, "le PSG")
    pctx = sports.psg_context(pm)
    if pctx.get("l1"):
        psg["bullets"].append(f"Classement : {pctx['l1']}")
    if pctx.get("ucl"):
        psg["bullets"].append(f"Ligue des champions : {pctx['ucl']}")
    if pctx.get("adv_rang"):
        psg["bullets"].append(f"Adversaire au classement : {pctx['adv_rang']}")
    if pctx.get("adv_infos"):
        ai = pctx["adv_infos"]
        psg["bullets"].append(f"{ai['nom']} — " + " · ".join(ai["infos"]))

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

    # Fête du jour en tête (déterministe) + sports en fin (toujours le prochain match)
    fete_rub = build_fete_rubrique()
    rubriques = ([fete_rub] if fete_rub else []) + rubriques + build_sport_rubriques()

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
