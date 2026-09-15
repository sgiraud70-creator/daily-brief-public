"""Fête du jour (prénom à souhaiter) — source française nominis.cef.fr.

Déterministe (EF-18) : on lit la source, on n'invente jamais. Nominis (Église
catholique de France) est la référence des calendriers français pour « le saint
/ prénom du jour ». On tente plusieurs points d'entrée par robustesse.
"""
from __future__ import annotations

import feedparser
import requests

UA = {"User-Agent": "DailyBriefBot/1.0 (brief quotidien personnel)"}
TIMEOUT = 20
# Points d'entrée candidats (le premier qui renvoie des entrées gagne)
CANDIDATS = [
    "https://nominis.cef.fr/rss/nominis.xml",
    "https://nominis.cef.fr/rss/",
]
SOURCE_URL = "https://nominis.cef.fr/"


def _fetch(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        print(f"  nominis {url} → HTTP {r.status_code} ({len(r.content)} o)")
        r.raise_for_status()
        return r.content
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ nominis {url}: {e!r}")
        return None


def fete_du_jour() -> dict | None:
    contenu = None
    for url in CANDIDATS:
        contenu = _fetch(url)
        if contenu:
            break
    if not contenu:
        return None

    # DEBUG temporaire : dump pour analyser le format réel hors-ligne
    try:
        with open("public/_fete_debug.xml", "wb") as f:
            f.write(contenu)
    except Exception:  # noqa: BLE001
        pass

    d = feedparser.parse(contenu)
    titres = [(e.get("title") or "").strip() for e in d.entries]
    print(f"  nominis : {len(d.entries)} entrées ; titres={titres[:8]}")
    if not titres:
        return None

    nom = titres[0]  # à ajuster selon le format réel observé
    return {"nom": nom, "source_name": "Nominis", "source_url": SOURCE_URL}
