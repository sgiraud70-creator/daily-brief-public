"""Collecte d'actualités par flux RSS (déterministe, sans LLM).

Pour chaque rubrique, agrège plusieurs flux, garde les entrées récentes,
déduplique par URL, et renvoie une liste de candidats. Le LLM (maillon
rédaction) sélectionnera ensuite ≤ 7 sujets par rubrique.

Un flux injoignable est ignoré proprement (EF-06) et consigné dans `failures`.
"""
from __future__ import annotations

import datetime as dt
import time
from urllib.parse import urlparse

import feedparser

# En-tête « navigateur » : certains flux renvoient 403 sans User-Agent.
UA = ("Mozilla/5.0 (compatible; DailyBriefBot/1.0; +https://github.com/"
      "sgiraud70-creator/daily-brief-public)")

MAX_AGE_HOURS = 36          # fraîcheur : on ignore les articles trop vieux
MAX_PER_FEED = 12           # plafond par flux
MAX_PER_RUBRIQUE = 20       # plafond de candidats par rubrique (avant sélection LLM)


def _source_name(url: str) -> str:
    host = urlparse(url).netloc.replace("www.", "")
    return host.split("/")[0]


def _entry_datetime(entry) -> dt.datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return dt.datetime.fromtimestamp(time.mktime(t))
    return None


def fetch_feed(url: str) -> list[dict]:
    parsed = feedparser.parse(url, agent=UA)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(parsed.get("bozo_exception", "flux illisible"))
    is_gnews = "news.google.com" in url
    items = []
    now = dt.datetime.now()
    for e in parsed.entries[:MAX_PER_FEED]:
        link = (e.get("link") or "").strip()
        title = (e.get("title") or "").strip()
        if not link or not title:
            continue
        when = _entry_datetime(e)
        if when and (now - when) > dt.timedelta(hours=MAX_AGE_HOURS):
            continue
        # Google Actualités : le vrai média est en suffixe du titre (« Titre - Le Progrès »)
        if is_gnews and " - " in title:
            title, source = title.rsplit(" - ", 1)
            source = source.strip()
        else:
            source = "Google Actualités" if is_gnews else _source_name(url)
        summary = (e.get("summary") or "").strip()
        items.append({
            "title": title.strip(),
            "url": link,
            "source": source,
            "summary": summary[:400],
            "published": when.isoformat() if when else None,
        })
    return items


def collect(feeds_by_rubrique: dict[str, list[str]]) -> dict:
    rubriques: dict[str, list[dict]] = {}
    failures: list[dict] = []
    for rubrique, feeds in feeds_by_rubrique.items():
        seen: set[str] = set()
        collected: list[dict] = []
        for feed in feeds:
            feed = feed.strip()
            try:
                for it in fetch_feed(feed):
                    if it["url"] in seen:
                        continue
                    seen.add(it["url"])
                    collected.append(it)
            except Exception as e:  # flux mort → ignoré (EF-06)
                failures.append({"rubrique": rubrique, "feed": feed, "error": str(e)[:160]})
        rubriques[rubrique] = collected[:MAX_PER_RUBRIQUE]
    return {"rubriques": rubriques, "failures": failures}
