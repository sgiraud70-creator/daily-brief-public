"""Collecte sportive déterministe (sans LLM) : prochain match Steelers et PSG.

Source : TheSportsDB (API gratuite, non bloquée en datacenter — contrairement à
ESPN qui renvoie 403 depuis les IP GitHub). On ne fabrique JAMAIS d'information :
la diffusion TV n'est indiquée que si l'API la fournit, sinon « à confirmer ».
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import requests

TIMEOUT = 25
PARIS = ZoneInfo("Europe/Paris")
UA = {"User-Agent": "DailyBriefBot/1.0"}
BASE = "https://www.thesportsdb.com/api/v1/json/3"   # clé de test gratuite

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def _team_id(nom: str) -> str | None:
    r = requests.get(f"{BASE}/searchteams.php", params={"t": nom},
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    teams = r.json().get("teams") or []
    return teams[0].get("idTeam") if teams else None


def _fr_datetime(e: dict) -> str:
    ts = e.get("strTimestamp")
    if ts:
        try:
            d = dt.datetime.fromisoformat(ts.replace("Z", "")).replace(
                tzinfo=dt.timezone.utc).astimezone(PARIS)
            return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} à {d.hour:02d}h{d.minute:02d}"
        except ValueError:
            pass
    # à défaut : date seule
    de = e.get("dateEvent")
    if de:
        try:
            d = dt.date.fromisoformat(de)
            return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"
        except ValueError:
            pass
    return "date à confirmer"


def _next_event(idteam: str, mon_equipe: str) -> dict | None:
    r = requests.get(f"{BASE}/eventsnext.php", params={"id": idteam},
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    events = r.json().get("events") or []
    if not events:
        return None
    e = events[0]  # déjà trié : prochain match
    home = e.get("strHomeTeam") or ""
    away = e.get("strAwayTeam") or ""
    is_home = mon_equipe.lower() in home.lower()
    tv = (e.get("strTVStation") or "").strip()
    return {
        "adversaire": (away if is_home else home) or "à préciser",
        "domicile": "à domicile" if is_home else "à l'extérieur",
        "competition": (e.get("strLeague") or "").strip(),
        "date_txt": _fr_datetime(e),
        "stade": (e.get("strVenue") or "").strip(),
        "diffusion": tv or None,
    }


def _next(nom: str, mon_equipe: str) -> dict | None:
    idteam = _team_id(nom)
    if not idteam:
        return None
    return _next_event(idteam, mon_equipe)


def steelers_next() -> dict | None:
    try:
        return _next("Pittsburgh Steelers", "Steelers")
    except Exception as e:  # noqa: BLE001
        print(f"⚠ Steelers TheSportsDB: {e!r}")
        return None


def psg_next() -> dict | None:
    try:
        return _next("Paris Saint-Germain", "Paris")
    except Exception as e:  # noqa: BLE001
        print(f"⚠ PSG TheSportsDB: {e!r}")
        return None
