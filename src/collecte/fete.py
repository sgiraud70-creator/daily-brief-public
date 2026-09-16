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


def _extract_prenoms(page: str) -> list[str]:
    """Prénoms vedettes du jour = liens /contenus/prenom/ID/Nom.html marqués
    « list-group-item » (les dérivés, eux, sont en class="sexe0")."""
    from urllib.parse import unquote
    bruts = re.findall(
        r'href="/contenus/prenom/\d+/([^."]+)\.html"\s+class="list-group-item',
        page)
    prenoms: list[str] = []
    for b in bruts:
        nom = unquote(b).replace("-", " ").strip()
        if nom and nom not in prenoms:
            prenoms.append(nom)
    return prenoms


def _joindre(prenoms: list[str]) -> str:
    if len(prenoms) == 1:
        return prenoms[0]
    return ", ".join(prenoms[:-1]) + " et " + prenoms[-1]


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

    prenoms = _extract_prenoms(page)
    print(f"  → Fête du jour : prénoms vedettes = {prenoms}")
    if not prenoms:
        return None
    return {"nom": _joindre(prenoms), "source_name": "Nominis", "source_url": used}
