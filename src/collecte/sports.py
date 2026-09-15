"""Collecte sportive déterministe (sans LLM) : prochain match Steelers et PSG.

- Steelers (NFL, américaine) : TheSportsDB — API gratuite non bloquée en
  datacenter (contrairement à ESPN qui renvoie 403 depuis les IP GitHub).
- PSG : Wikipédia FR (source française, demandée par l'utilisateur) —
  l'article « Saison AAAA-AAAA du Paris Saint-Germain » agrège tout le
  calendrier (Ligue 1, Ligue des champions, Coupe de France) et son accès
  depuis un datacenter est fiable.

On ne fabrique JAMAIS d'information : la diffusion TV n'est indiquée que si la
source la fournit, sinon « à confirmer ».
"""
from __future__ import annotations

import datetime as dt
import re
from html.parser import HTMLParser
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
            return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} à {d.hour:02d}h{d.minute:02d}"
        except ValueError:
            pass
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
_STADE_MOTS = ("stade", "parc des princes", "arena", "stadium", "park",
               "allianz", "san siro", "signal iduna", "wembley")
_DATE_RE = re.compile(
    r"(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|"
    r"septembre|octobre|novembre|décembre)\s+(\d{4})", re.I)
_HEURE_RE = re.compile(r"\b(\d{1,2})\s*[:h]\s*(\d{2})\b")
_NOTE_RE = re.compile(r"\[\d+\]|\[n\s*\d+\]")


def _season_query(today: dt.date) -> str:
    start = today.year if today.month >= 7 else today.year - 1
    return f"Saison {start}-{start + 1} du Paris Saint-Germain"


def _resolve_title(query: str) -> str | None:
    """Trouve le titre exact de l'article via la recherche Wikipédia (robuste
    aux variations « FC » / « Football Club » / tiret spécial)."""
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


class _RowParser(HTMLParser):
    """Extrait chaque ligne de tableau : texte concaténé + titres des liens."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict] = []
        self._in_row = False
        self._text: list[str] = []
        self._links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._in_row, self._text, self._links = True, [], []
        elif tag == "a" and self._in_row:
            d = dict(attrs)
            if d.get("title"):
                self._links.append(d["title"])

    def handle_endtag(self, tag):
        if tag == "tr" and self._in_row:
            self.rows.append({"text": " ".join(self._text),
                              "links": self._links})
            self._in_row = False

    def handle_data(self, data):
        if self._in_row and data.strip():
            self._text.append(data.strip())


def _parse_date(texte: str) -> tuple[dt.date, int | None, int | None] | None:
    m = _DATE_RE.search(texte)
    if not m:
        return None
    try:
        d = dt.date(int(m.group(3)), _MOIS_IDX[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None
    hm = _HEURE_RE.search(texte)
    if hm:
        h, mn = int(hm.group(1)), int(hm.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return d, h, mn
    return d, None, None


def _fr_date(d: dt.date, hh: int | None, mm: int | None) -> str:
    base = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"
    return f"{base} à {hh:02d}h{(mm or 0):02d}" if hh is not None else base


def _competition(texte: str) -> str:
    low = texte.lower()
    for c in _COMPETS:
        if c.lower() in low:
            return c
    return ""


def _opponent(links: list[str]) -> str:
    for t in links:
        low = t.lower()
        if "paris saint-germain" in low or low.startswith("paris sg"):
            continue
        if any(s in low for s in _STADE_MOTS):
            continue
        if any(c.lower() in low for c in _COMPETS):
            continue
        if low.startswith("saison ") or low in _MOIS_IDX:
            continue
        if re.fullmatch(r"\d{4}", t) or "championnat" in low:
            continue
        return _NOTE_RE.sub("", t).strip()
    return "à préciser"


def _venue_home(texte: str, links: list[str]) -> tuple[str, str]:
    """(domicile/extérieur, stade). PSG à domicile ⇒ Parc des Princes."""
    hay = (texte + " " + " ".join(links)).lower()
    stade = ""
    for t in links:
        if any(s in t.lower() for s in _STADE_MOTS):
            stade = _NOTE_RE.sub("", t).strip()
            break
    if "parc des princes" in hay:
        return "à domicile", stade or "Parc des Princes"
    if re.search(r"\bext(?:érieur|\.)\b", hay) or "à l'extérieur" in hay:
        return "à l'extérieur", stade
    if re.search(r"\bdom(?:icile|\.)\b", hay):
        return "à domicile", stade or "Parc des Princes"
    return "lieu à confirmer", stade


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

    html = data["parse"]["text"]
    parser = _RowParser()
    parser.feed(html)

    best: tuple[dt.date, int | None, int | None, dict] | None = None
    futures = 0
    for row in parser.rows:
        parsed = _parse_date(row["text"])
        if not parsed:
            continue
        d, hh, mm = parsed
        if d < today:
            continue  # matchs passés / dates de naissance : ignorés
        futures += 1
        # une ligne de calendrier PSG a au moins un lien vers un club adverse
        if not row["links"]:
            continue
        if best is None or d < best[0] or (d == best[0] and (hh or 0) < (best[1] or 0)):
            best = (d, hh, mm, row)

    if best is None:
        print(f"  (article {title!r} : {len(parser.rows)} lignes, "
              f"{futures} dates futures, aucun match exploitable)")
        return None

    d, hh, mm, row = best
    dom, stade = _venue_home(row["text"], row["links"])
    adversaire = _opponent(row["links"])
    print(f"  → PSG : {adversaire} le {_fr_date(d, hh, mm)} ({dom}) "
          f"[liens: {row['links'][:5]}]")
    return {
        "adversaire": adversaire,
        "domicile": dom,
        "competition": _competition(row["text"]),
        "date_txt": _fr_date(d, hh, mm),
        "stade": stade,
        "diffusion": None,  # Wikipédia ne fournit pas la chaîne TV
        "source_name": "Wikipédia",
        "source_url": "https://fr.wikipedia.org/wiki/" + title.replace(" ", "_"),
    }


def psg_next() -> dict | None:
    today = dt.datetime.now(PARIS).date()
    return _wiki_psg_next(today)
