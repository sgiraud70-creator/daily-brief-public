"""Fête du jour — prénom à souhaiter, depuis la page « fêtes » de nominis.cef.fr.

Déterministe (EF-18) : on lit la page officielle du jour de Nominis (Église
catholique de France), qui liste « les saints et prénoms chrétiens du jour »,
et on en extrait le prénom principal (« Bonne fête aux … »).
"""
from __future__ import annotations

import datetime as dt
import html
import re
from zoneinfo import ZoneInfo

import requests

PARIS = ZoneInfo("Europe/Paris")
UA = {"User-Agent": "DailyBriefBot/1.0 (brief quotidien personnel)"}
TIMEOUT = 20
MOIS_CAP = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
            "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def _strip_accents(s: str) -> str:
    table = str.maketrans("ÀÂÄÉÈÊËÎÏÔÖÛÜÇàâäéèêëîïôöûüç",
                          "AAAEEEEIIOOUUCaaaeeeeiioouuc")
    return s.translate(table)


def _urls(d: dt.date) -> list[str]:
    mois = MOIS_CAP[d.month - 1]
    base = f"https://nominis.cef.fr/contenus/fetes/{d.day}/{d.month}/{d.year}"
    # Nominis peut utiliser le mois accentué ou non dans le nom de fichier
    variants = {mois, _strip_accents(mois)}
    return [f"{base}/{d.day}-{m}-{d.year}.html" for m in variants]


def _extract_prenom(page: str) -> str | None:
    texte = html.unescape(re.sub(r"<[^>]+>", " ", page))
    texte = re.sub(r"\s+", " ", texte)
    # 1) formulation explicite « Bonne fête aux Roland »
    m = re.search(r"Bonne\s+f[êe]te\s+(?:aux?|à)\s+([A-ZÀ-Ý][\wà-ÿ'-]+)", texte)
    if m:
        return m.group(1).strip()
    # 2) à défaut : « Fête du jour : Roland » / « on fête : Roland »
    m = re.search(r"f[êe]te[^:]{0,20}:\s*([A-ZÀ-Ý][\wà-ÿ'-]+)", texte)
    return m.group(1).strip() if m else None


def fete_du_jour() -> dict | None:
    today = dt.datetime.now(PARIS).date()
    page = None
    used = None
    for url in _urls(today):
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            print(f"  nominis {url} → HTTP {r.status_code} ({len(r.content)} o)")
            if r.status_code == 200 and r.text:
                page, used = r.text, url
                break
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠ nominis {url}: {e!r}")
    if not page:
        return None

    try:  # DEBUG temporaire : dump pour analyser le format réel
        with open("public/_fete_debug.html", "w", encoding="utf-8") as f:
            f.write(page)
    except Exception:  # noqa: BLE001
        pass

    prenom = _extract_prenom(page)
    print(f"  → Fête du jour : prénom = {prenom!r}")
    if not prenom:
        return None
    return {"nom": prenom, "source_name": "Nominis", "source_url": used}
