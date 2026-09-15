"""Fête du jour — prénom à souhaiter, depuis l'article Wikipédia FR du jour.

Déterministe (EF-18) : on lit la section « Prénoms du jour » de l'article
« <jour> <mois> » (ex. « 15 septembre ») et on en extrait le prénom principal.
Source française, vivante et citable.
"""
from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

import requests

PARIS = ZoneInfo("Europe/Paris")
UA = {"User-Agent": "DailyBriefBot/1.0 (brief quotidien personnel)"}
WIKI = "https://fr.wikipedia.org/w/api.php"
TIMEOUT = 20
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def _article_jour(d: dt.date) -> str:
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {MOIS[d.month - 1]}"


def _premier_prenom(wikitext: str) -> str | None:
    """Extrait le 1er prénom en gras de la section « Prénoms du jour »."""
    m = re.search(r"Prénoms?\s+du\s+jour", wikitext, re.I)
    if not m:
        return None
    bloc = wikitext[m.end():m.end() + 600]
    # « '''[[Roland (prénom)|Roland]]''' » ou « '''Roland''' »
    lien = re.search(r"'''\[\[[^\]|]*\|([^\]]+)\]\]'''", bloc)
    if lien:
        return lien.group(1).strip()
    simple = re.search(r"'''([^']+?)'''", bloc)
    return simple.group(1).strip() if simple else None


def fete_du_jour() -> dict | None:
    today = dt.datetime.now(PARIS).date()
    titre = _article_jour(today)
    try:
        r = requests.get(WIKI, params={
            "action": "parse", "page": titre, "prop": "wikitext",
            "format": "json", "formatversion": 2, "redirects": 1,
        }, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"⚠ Fête du jour Wikipédia [{titre}]: {e!r}")
        return None
    if "error" in data or "parse" not in data:
        print(f"  (article introuvable : {titre!r})")
        return None

    wikitext = data["parse"]["wikitext"]
    try:  # DEBUG temporaire : dump pour analyser le format réel
        with open("public/_fete_debug.txt", "w", encoding="utf-8") as f:
            f.write(wikitext)
    except Exception:  # noqa: BLE001
        pass

    prenom = _premier_prenom(wikitext)
    print(f"  → Fête du jour ({titre}) : prénom = {prenom!r}")
    if not prenom:
        return None
    return {
        "nom": prenom,
        "source_name": "Wikipédia",
        "source_url": "https://fr.wikipedia.org/wiki/" + titre.replace(" ", "_"),
    }
