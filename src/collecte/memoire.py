"""Mémoire anti-répétition sur 7 jours glissants (EF-11).

Stockée dans data/history.json (versionné, 0 €, exportable — ENF-07).
Chaque sujet PUBLIÉ est identifié par son URL. Avant sélection, on écarte les
URL déjà vues ; après publication, on mémorise les sujets retenus.
"""
from __future__ import annotations

import datetime as dt
import json
import os

RETENTION_DAYS = 7


def load(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def prune(history: list[dict], today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    limit = today - dt.timedelta(days=RETENTION_DAYS)
    kept = []
    for h in history:
        try:
            d = dt.date.fromisoformat(h.get("date", ""))
        except ValueError:
            continue
        if d >= limit:
            kept.append(h)
    return kept


def seen_urls(history: list[dict]) -> set[str]:
    return {h.get("url") for h in history if h.get("url")}


def filter_new(items: list[dict], history: list[dict]) -> list[dict]:
    """Retire les items dont l'URL a déjà été traitée récemment."""
    seen = seen_urls(history)
    return [it for it in items if it.get("url") not in seen]


def remember(history: list[dict], published: list[dict],
             today: dt.date | None = None) -> list[dict]:
    """Ajoute les sujets publiés à l'historique et renvoie l'historique élagué."""
    today = today or dt.date.today()
    for it in published:
        if not it.get("url"):
            continue
        history.append({
            "url": it["url"],
            "title": it.get("title", ""),
            "rubrique": it.get("rubrique", ""),
            "date": today.isoformat(),
        })
    return prune(history, today)


def save(path: str, history: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
