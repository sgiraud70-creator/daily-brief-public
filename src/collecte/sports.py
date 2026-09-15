"""Collecte sportive déterministe (sans LLM) : prochain match Steelers et PSG.

Source : API publique ESPN. On ne fabrique JAMAIS d'information : la diffusion
TV n'est indiquée que si ESPN la fournit, sinon « à confirmer » (exigence du
cahier des charges).
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import requests

TIMEOUT = 25
PARIS = ZoneInfo("Europe/Paris")
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]

NFL_STEELERS = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/pit/schedule"
# PSG : id ESPN 160 ; le calendrier renvoie les événements toutes compétitions
PSG = "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/teams/160/schedule"


def _fr_datetime(iso: str) -> tuple[str, dt.datetime]:
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(PARIS)
    txt = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} à {d.hour:02d}h{d.minute:02d}"
    return txt, d


def _next_event(events: list[dict]) -> dict | None:
    now = dt.datetime.now(dt.timezone.utc)
    futurs = []
    for e in events:
        iso = e.get("date")
        if not iso:
            continue
        try:
            when = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            continue
        state = (e.get("competitions", [{}])[0].get("status", {})
                 .get("type", {}).get("state"))
        if when >= now or state == "pre":
            futurs.append((when, e))
    if not futurs:
        return None
    futurs.sort(key=lambda x: x[0])
    return futurs[0][1]


def _parse(events: list[dict], team_name: str) -> dict | None:
    e = _next_event(events)
    if not e:
        return None
    comp = e.get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    me = next((c for c in competitors if team_name.lower() in
               c.get("team", {}).get("displayName", "").lower()), None)
    opp = next((c for c in competitors if c is not me), None)
    home_away = "à domicile" if (me or {}).get("homeAway") == "home" else "à l'extérieur"
    date_txt, _ = _fr_datetime(e["date"])
    # diffusion : uniquement si fournie
    diffs = []
    for b in comp.get("broadcasts", []) or []:
        diffs += b.get("names", []) or []
    for b in comp.get("geoBroadcasts", []) or []:
        nm = b.get("media", {}).get("shortName")
        if nm:
            diffs.append(nm)
    return {
        "adversaire": (opp or {}).get("team", {}).get("displayName", "à préciser"),
        "domicile": home_away,
        "competition": (e.get("season", {}).get("slug") or comp.get("type", {}).get("text")
                        or e.get("shortName") or ""),
        "date_txt": date_txt,
        "stade": comp.get("venue", {}).get("fullName", ""),
        "diffusion": ", ".join(dict.fromkeys(diffs)) if diffs else None,
    }


def _fetch(url: str) -> list[dict]:
    r = requests.get(url, timeout=TIMEOUT,
                     headers={"User-Agent": "DailyBriefBot/1.0"})
    r.raise_for_status()
    return r.json().get("events", []) or []


def steelers_next() -> dict | None:
    try:
        return _parse(_fetch(NFL_STEELERS), "Steelers")
    except Exception:
        return None


def psg_next() -> dict | None:
    try:
        return _parse(_fetch(PSG), "Paris Saint-Germain")
    except Exception:
        return None
