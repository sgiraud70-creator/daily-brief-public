"""Collecte météo — déterministe, sans LLM.

Prévision horaire + journalière : Open-Meteo (gratuit, sans clé).
Vigilance : Météo-France (obligatoire pour la vigilance, EF-17). Le token
Météo-France étant à durée de vie courte (EF-17a), il est régénéré à chaque
exécution depuis l'Application ID stocké en secret ; en l'absence de secret
(ex. environnement de dev), la vigilance est simplement absente (dégradé propre).

Ce module NE dépend PAS de Météo-France pour la prévision horaire (EF-17b) :
Open-Meteo l'assure, MET Norway sert de repli.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional
from zoneinfo import ZoneInfo

import requests

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 25

# --- Correspondance des codes météo WMO -> (clé d'icône, libellé français) ---
WMO = {
    0: ("clear", "Ciel dégagé"),
    1: ("mostly_clear", "Plutôt dégagé"),
    2: ("partly", "Partiellement nuageux"),
    3: ("overcast", "Couvert"),
    45: ("fog", "Brouillard"),
    48: ("fog", "Brouillard givrant"),
    51: ("drizzle", "Bruine légère"),
    53: ("drizzle", "Bruine"),
    55: ("drizzle", "Bruine dense"),
    56: ("drizzle", "Bruine verglaçante"),
    57: ("drizzle", "Bruine verglaçante"),
    61: ("rain", "Pluie faible"),
    63: ("rain", "Pluie"),
    65: ("rain", "Pluie forte"),
    66: ("rain", "Pluie verglaçante"),
    67: ("rain", "Pluie verglaçante"),
    71: ("snow", "Neige faible"),
    73: ("snow", "Neige"),
    75: ("snow", "Neige forte"),
    77: ("snow", "Grains de neige"),
    80: ("rain", "Averses"),
    81: ("rain", "Averses"),
    82: ("rain", "Averses fortes"),
    85: ("snow", "Averses de neige"),
    86: ("snow", "Averses de neige"),
    95: ("thunder", "Orages"),
    96: ("thunder", "Orages grêleux"),
    99: ("thunder", "Orages violents"),
}

DAYS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


def label_for(code: int) -> str:
    return WMO.get(int(code), ("overcast", "Variable"))[1]


def icon_for(code: int) -> str:
    return WMO.get(int(code), ("overcast", "Variable"))[0]


def _is_night(hour: int) -> bool:
    return hour < 7 or hour >= 21


def get_weather(lat: float, lon: float, tz: str = "Europe/Paris") -> dict:
    """Renvoie une structure météo normalisée à partir d'Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": tz,
        "forecast_days": 7,
        "hourly": "temperature_2m,precipitation,weather_code,wind_speed_10m",
        "daily": ("weather_code,temperature_2m_max,temperature_2m_min,"
                  "precipitation_sum,precipitation_probability_max,wind_speed_10m_max"),
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
    }
    r = requests.get(OPEN_METEO, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return normalize(r.json(), tz)


def normalize(raw: dict, tz: str) -> dict:
    hourly = raw["hourly"]
    daily = raw["daily"]
    cur = raw.get("current", {})
    times = [dt.datetime.fromisoformat(t) for t in hourly["time"]]
    today = times[0].date()

    # Tranches de 2 h sur la journée en cours : 07,09,...,23 h (EF-17c)
    steps = []
    wanted = [7, 9, 11, 13, 15, 17, 19, 21, 23]
    for i, t in enumerate(times):
        if t.date() != today or t.hour not in wanted:
            continue
        # précipitations cumulées sur la fenêtre de 2 h
        precip = hourly["precipitation"][i]
        if i + 1 < len(times) and times[i + 1].date() == today:
            precip += hourly["precipitation"][i + 1]
        steps.append({
            "hh": f"{t.hour:02d}h",
            "code": int(hourly["weather_code"][i]),
            "is_night": _is_night(t.hour),
            "temp": round(hourly["temperature_2m"][i]),
            "precip": round(precip, 1),
            "wind": round(hourly["wind_speed_10m"][i]),
        })

    # Jours J+1 .. J+6 (EF-17d)
    days = []
    for j in range(1, 7):
        d = dt.date.fromisoformat(daily["time"][j])
        days.append({
            "name": DAYS_FR[d.weekday()],
            "code": int(daily["weather_code"][j]),
            "tmax": round(daily["temperature_2m_max"][j]),
            "tmin": round(daily["temperature_2m_min"][j]),
        })

    # Nuit calculée en heure LOCALE (Paris), pas en heure du serveur (UTC)
    local_hour = dt.datetime.now(ZoneInfo(tz)).hour
    current = {
        "temp": round(cur.get("temperature_2m", daily["temperature_2m_max"][0])),
        "feels": round(cur.get("apparent_temperature", cur.get("temperature_2m", 0))),
        "code": int(cur.get("weather_code", daily["weather_code"][0])),
        "is_night": _is_night(local_hour),
        "tmax": round(daily["temperature_2m_max"][0]),
        "tmin": round(daily["temperature_2m_min"][0]),
        "precip_prob": int(daily.get("precipitation_probability_max", [0])[0] or 0),
        "wind": round(daily["wind_speed_10m_max"][0]),
    }
    return {"current": current, "steps": steps, "days": days, "source": "Open-Meteo"}


_VIG_COULEURS = {1: "vert", 2: "jaune", 3: "orange", 4: "rouge"}
_VIG_PHENO = {
    "1": "vent violent", "2": "pluie-inondation", "3": "orages", "4": "crues",
    "5": "neige-verglas", "6": "canicule", "7": "grand froid",
    "8": "avalanches", "9": "vagues-submersion",
}


def get_vigilance(departement: str = "70", app_id: Optional[str] = None) -> Optional[dict]:
    """Vigilance Météo-France (dép. 70). Régénère un token OAuth depuis
    l'Application ID (EF-17a). Sans secret, renvoie None (dégradé propre)."""
    if not app_id:
        return None
    url = ("https://public-api.meteofrance.fr/public/DPVigilance/v1/"
           "cartevigilance/encours")

    def _fetch(bearer: str):
        return requests.get(url, headers={"Authorization": f"Bearer {bearer}"},
                            timeout=REQUEST_TIMEOUT)

    try:
        # 1) le secret est peut-être déjà un token d'accès → Bearer direct
        v = _fetch(app_id)
        if v.status_code in (401, 403):
            # 2) sinon, le secret est un « Application ID » → échange OAuth
            tok = requests.post(
                "https://portail-api.meteofrance.fr/token",
                headers={"Authorization": f"Basic {app_id}"},
                data={"grant_type": "client_credentials"},
                timeout=REQUEST_TIMEOUT,
            )
            tok.raise_for_status()
            v = _fetch(tok.json()["access_token"])
        v.raise_for_status()
        payload = v.json()
        try:  # DEBUG temporaire : dump pour caler la structure réelle
            import json as _json
            with open("public/_vigilance_debug.json", "w", encoding="utf-8") as _f:
                _json.dump(payload, _f, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            pass
        return _parse_vigilance(payload, departement)
    except Exception as e:  # noqa: BLE001
        print(f"⚠ vigilance Météo-France : {e!r}")
        return None


def _parse_vigilance(payload: dict, departement: str) -> Optional[dict]:
    """Extrait la vigilance du jour (échéance J) pour le département.
    Renvoie {level, phenomenes} si jaune ou plus, sinon None (vert = pas d'alerte).
    """
    try:
        periods = payload["product"]["periods"]
    except (KeyError, TypeError):
        return None
    per = next((p for p in periods
                if str(p.get("echeance", "")).upper() in ("J", "0")), None)
    per = per or (periods[0] if periods else None)
    if not per:
        return None
    domains = (per.get("timelaps") or {}).get("domain_ids") or []
    dom = next((d for d in domains
                if str(d.get("domain_id")) == str(departement)), None)
    if not dom:
        return None
    try:
        color = int(dom.get("max_color_id") or 1)
    except (TypeError, ValueError):
        color = 1
    if color < 2:
        return None  # vert : pas d'alerte
    phenos = []
    for it in dom.get("phenomenon_items") or []:
        try:
            c = int(it.get("phenomenon_max_color_id") or 1)
        except (TypeError, ValueError):
            c = 1
        if c >= 2:
            phenos.append(_VIG_PHENO.get(str(it.get("phenomenon_id")), "phénomène"))
    niveau = _VIG_COULEURS.get(color, "?")
    print(f"  → vigilance dép.{departement} : {niveau} {phenos}")
    return {"level": niveau, "phenomenes": phenos}


# --- Données d'exemple (pour le rendu hors-ligne / dev, réseau externe bloqué) ---
def sample_data() -> dict:
    steps = [
        {"hh": "07h", "code": 45, "is_night": False, "temp": 13, "precip": 0.0, "wind": 6},
        {"hh": "09h", "code": 2, "is_night": False, "temp": 16, "precip": 0.0, "wind": 9},
        {"hh": "11h", "code": 1, "is_night": False, "temp": 20, "precip": 0.0, "wind": 11},
        {"hh": "13h", "code": 0, "is_night": False, "temp": 23, "precip": 0.0, "wind": 12},
        {"hh": "15h", "code": 2, "is_night": False, "temp": 24, "precip": 0.0, "wind": 14},
        {"hh": "17h", "code": 61, "is_night": False, "temp": 22, "precip": 1.2, "wind": 15},
        {"hh": "19h", "code": 80, "is_night": False, "temp": 19, "precip": 2.4, "wind": 13},
        {"hh": "21h", "code": 3, "is_night": True, "temp": 17, "precip": 0.2, "wind": 9},
        {"hh": "23h", "code": 0, "is_night": True, "temp": 15, "precip": 0.0, "wind": 7},
    ]
    days = [
        {"name": "Mar", "code": 2, "tmax": 24, "tmin": 13},
        {"name": "Mer", "code": 61, "tmax": 21, "tmin": 14},
        {"name": "Jeu", "code": 80, "tmax": 19, "tmin": 12},
        {"name": "Ven", "code": 3, "tmax": 20, "tmin": 11},
        {"name": "Sam", "code": 0, "tmax": 23, "tmin": 10},
        {"name": "Dim", "code": 1, "tmax": 25, "tmin": 12},
    ]
    current = {"temp": 21, "feels": 20, "code": 2, "is_night": False,
               "tmax": 24, "tmin": 13, "precip_prob": 40, "wind": 12}
    return {"current": current, "steps": steps, "days": days, "source": "Exemple"}
