"""Collecte sportive déterministe (sans LLM) : prochain match Steelers et PSG.

- Steelers (NFL, américaine) : TheSportsDB — API gratuite non bloquée en
  datacenter (contrairement à ESPN qui renvoie 403 depuis les IP GitHub).
- PSG : Wikipédia FR (source française, demandée par l'utilisateur) —
  l'article « Saison AAAA-AAAA du Paris Saint-Germain » agrège tout le
  calendrier (Ligue 1, Ligue des champions, Coupe de France). On lit le
  tableau récapitulatif : « Compétition Jn <date> Domicile [score] Extérieur ».
  Un match à venir n'a pas de score : « Domicile - Extérieur » (tiret entouré
  d'espaces). L'heure et le diffuseur TV viennent de la fiche détaillée.

On ne fabrique JAMAIS d'information : le diffuseur n'est indiqué que si la
source le fournit, sinon « à confirmer ».
"""
from __future__ import annotations

import datetime as dt
import re
from html import unescape
from zoneinfo import ZoneInfo

import requests

TIMEOUT = 25
PARIS = ZoneInfo("Europe/Paris")
UA = {"User-Agent": "DailyBriefBot/1.0 (brief quotidien personnel)"}
BASE = "https://www.thesportsdb.com/api/v1/json/3"   # clé de test gratuite
WIKI = "https://fr.wikipedia.org/w/api.php"

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]
_MOIS_IDX = {m: i + 1 for i, m in enumerate(MOIS)}


def _fr_date(d: dt.date, hh: int | None, mm: int | None) -> str:
    base = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"
    return f"{base} à {hh:02d}h{(mm or 0):02d}" if hh is not None else base


# ─────────────────────────── Steelers : TheSportsDB ────────────────────────
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
            return _fr_date(d.date(), d.hour, d.minute)
        except ValueError:
            pass
    de = e.get("dateEvent")
    if de:
        try:
            return _fr_date(dt.date.fromisoformat(de), None, None)
        except ValueError:
            pass
    return "date à confirmer"


def _next_event(idteam: str, mon_equipe: str) -> dict | None:
    r = requests.get(f"{BASE}/eventsnext.php", params={"id": idteam},
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    events = r.json().get("events") or []
    if not events:
        print(f"  (aucun match à venir pour id {idteam})")
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
        "source_name": "TheSportsDB",
        "source_url": f"https://www.thesportsdb.com/team/{idteam}",
    }


def _next_multi(noms: list[str], mon_equipe: str) -> dict | None:
    for nom in noms:
        try:
            idteam = _team_id(nom)
            if not idteam:
                continue
            res = _next_event(idteam, mon_equipe)
            if res:
                return res
        except Exception as e:  # noqa: BLE001
            print(f"⚠ {mon_equipe} TheSportsDB [{nom}]: {e!r}")
    return None


def steelers_next() -> dict | None:
    return _next_multi(["Pittsburgh Steelers"], "Steelers")


# ──────────────────────────── PSG : Wikipédia FR ───────────────────────────
_COMPETS = [
    "Ligue des champions", "Ligue 1", "Coupe de France", "Trophée des champions",
    "Supercoupe d'Europe", "Ligue Europa", "Coupe du monde des clubs",
]
_MO = "|".join(MOIS)
_RECAP_DATE = re.compile(rf"(\d{{1,2}})(?:er)?\s+({_MO})\s+(\d{{4}})")


def _season_query(today: dt.date) -> str:
    start = today.year if today.month >= 7 else today.year - 1
    return f"Saison {start}-{start + 1} du Paris Saint-Germain"


def _resolve_title(query: str) -> str | None:
    """Titre exact de l'article via la recherche Wikipédia (robuste aux
    variantes « FC » / « Football Club »)."""
    r = requests.get(WIKI, params={
        "action": "query", "list": "search", "srsearch": query,
        "srlimit": 5, "format": "json", "formatversion": 2,
    }, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    hits = r.json().get("query", {}).get("search", [])
    for h in hits:
        t = h.get("title", "")
        if t.lower().startswith("saison") and "paris saint-germain" in t.lower():
            return t
    return hits[0]["title"] if hits else None


def _competition(texte: str) -> str:
    low = texte.lower()
    for c in _COMPETS:
        if c.lower() in low:
            return c
    return ""


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _wiki_psg_next(today: dt.date) -> dict | None:
    query = _season_query(today)
    try:
        title = _resolve_title(query)
        if not title:
            print(f"  (aucun article trouvé pour {query!r})")
            return None
        r = requests.get(WIKI, params={
            "action": "parse", "page": title, "prop": "text",
            "format": "json", "redirects": 1, "formatversion": 2,
        }, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"⚠ PSG Wikipédia [{query}]: {e!r}")
        return None
    if "error" in data or "parse" not in data:
        print(f"  (article introuvable : {title!r})")
        return None

    raw = data["parse"]["text"]
    best: tuple[dt.date, str, str, str] | None = None
    for tr in re.findall(r"<tr[^>]*>.*?</tr>", raw, re.S):
        t = _clean(tr)
        if "Paris SG" not in t:
            continue
        dm = _RECAP_DATE.search(t)
        if not dm:
            continue
        try:
            d = dt.date(int(dm.group(3)), _MOIS_IDX[dm.group(2)], int(dm.group(1)))
        except (ValueError, KeyError):
            continue
        if d < today:
            continue  # matchs passés
        after = t[dm.end():].strip()
        # match à venir : « Domicile - Extérieur » (tiret espacé, sans score)
        mo = re.match(r"(.+?)\s-\s(.+)$", after)
        if not mo:
            continue
        home = mo.group(1).strip()
        away = re.sub(r"\s+\d+\s*e\b.*$", "", mo.group(2)).strip()
        if best is None or d < best[0]:
            best = (d, home, away, t)

    if best is None:
        print(f"  (aucun match futur PSG repéré dans {title!r})")
        return None

    d, home, away, t = best
    psg_home = "paris" in home.lower()
    adversaire = away if psg_home else home
    domicile = "à domicile" if psg_home else "à l'extérieur"

    # Heure + diffuseur TV depuis la fiche détaillée (ancrée sur jour + date)
    full = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", raw)))
    anc = (rf"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"
           r"\s*(\d{1,2})h(\d{2})")
    hm = re.search(anc, full, re.I)
    hh = int(hm.group(1)) if hm else None
    mm = int(hm.group(2)) if hm else None
    # anc porte déjà 2 groupes (heure, minute) → le diffuseur est le groupe 3
    dif = re.search(anc + r".{0,60}?Diffuseur\s*:?\s*([^\[]+?)\s*(?:\[|Stade|Parc|$)",
                    full, re.I)
    diffusion = dif.group(3).strip() if dif else None

    print(f"  → PSG : {adversaire} le {_fr_date(d, hh, mm)} ({domicile}), "
          f"diffuseur {diffusion or 'à confirmer'}")
    return {
        "adversaire": adversaire,
        "domicile": domicile,
        "competition": _competition(t),
        "date_txt": _fr_date(d, hh, mm),
        "stade": "Parc des Princes" if psg_home else "",
        "diffusion": diffusion,
        "source_name": "Wikipédia",
        "source_url": "https://fr.wikipedia.org/wiki/" + title.replace(" ", "_"),
    }


def psg_next() -> dict | None:
    today = dt.datetime.now(PARIS).date()
    return _wiki_psg_next(today)
