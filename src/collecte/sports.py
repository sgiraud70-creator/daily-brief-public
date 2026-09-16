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
import unicodedata
from html import unescape
from zoneinfo import ZoneInfo

import requests

TIMEOUT = 25
PARIS = ZoneInfo("Europe/Paris")
UA = {"User-Agent": "DailyBriefBot/1.0 (brief quotidien personnel)"}
BASE = "https://www.thesportsdb.com/api/v1/json/3"   # clé de test gratuite
WIKI = "https://fr.wikipedia.org/w/api.php"
WIKI_EN = "https://en.wikipedia.org/w/api.php"

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


# ─────────────── Fiches d'équipe (3 infos) : TheSportsDB ────────────────────
def team_info(nom: str) -> dict | None:
    """3 informations factuelles sur un club (stade, ville, année de fondation).
    Source TheSportsDB (searchteams). Renvoie None si le club n'est pas trouvé.
    Aucune invention : chaque champ n'est présent que si l'API le fournit."""
    try:
        r = requests.get(f"{BASE}/searchteams.php", params={"t": nom},
                         headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        teams = r.json().get("teams") or []
    except Exception as e:  # noqa: BLE001
        print(f"⚠ team_info [{nom}]: {e!r}")
        return None
    if not teams:
        return None
    # Écarte les équipes secondaires (jeunes, féminines, réserves) qui polluent
    # la recherche, puis prend le meilleur recouvrement de nom avec la requête.
    _BAD = ("youth", "u21", "u19", "u23", "u18", "reserve", "réserve",
            "women", "féminin", "feminin", " ii", " b ")
    cand = [t for t in teams
            if not any(b in f" {(t.get('strTeam') or '').lower()} " for b in _BAD)]
    cand = cand or teams
    cible = set(_norm(nom).split())
    t = max(cand, key=lambda x: len(cible & set(_norm(x.get("strTeam") or "").split())))
    infos: list[str] = []
    stade = (t.get("strStadium") or "").strip()
    ville = (t.get("strLocation") or "").strip()
    annee = (str(t.get("intFormedYear") or "")).strip()
    if stade:
        infos.append(f"Stade : {stade}")
    if ville:
        infos.append(f"Ville : {ville}")
    if re.fullmatch(r"\d{4}", annee) and 1850 <= int(annee) <= dt.date.today().year:
        infos.append(f"Fondé en {annee}")
    if not infos:
        return None
    return {"nom": (t.get("strTeam") or nom).strip(), "infos": infos[:3]}


# ──────────────── Classements : Wikipédia (tables rendues) ──────────────────
def _norm(s: str) -> str:
    """Minuscule sans accents ni ponctuation, pour comparer des noms d'équipes."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


def _wiki_html(title: str, lang: str = "fr") -> str:
    api = WIKI if lang == "fr" else WIKI_EN
    r = requests.get(api, params={
        "action": "parse", "page": title, "prop": "text",
        "format": "json", "formatversion": 2, "redirects": 1,
    }, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    return d["parse"]["text"] if "parse" in d else ""


def _row_cells(tr: str) -> list[str]:
    return [_clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]


def _tables(html: str) -> list[list[list[str]]]:
    """Renvoie chaque table sous forme de liste de lignes (chaque ligne = liste
    de cellules texte)."""
    out = []
    for tb in re.findall(r"<table[^>]*>.*?</table>", html, re.S):
        rows = [_row_cells(tr) for tr in re.findall(r"<tr[^>]*>.*?</tr>", tb, re.S)]
        rows = [r for r in rows if r]
        if len(rows) >= 3:
            out.append(rows)
    return out


def _int(s: str) -> int | None:
    m = re.match(r"-?\d+", s.strip())
    return int(m.group()) if m else None


def _standing_of(table: list[dict], nom: str) -> dict | None:
    """Retrouve la ligne d'une équipe dans un classement (comparaison souple)."""
    if not nom:
        return None
    cible = set(_norm(nom).split())
    cible.discard("fc"); cible.discard("ac"); cible.discard("as"); cible.discard("rc")
    best, best_score = None, 0
    for row in table:
        mots = set(_norm(row["equipe"]).split())
        score = len(cible & mots)
        if score > best_score:
            best, best_score = row, score
    return best if best_score else None


# ---- Ligue 1 : « Championnat de France de football AAAA-AAAA » (fr) ----------
def _l1_page(today: dt.date) -> str:
    start = today.year if today.month >= 7 else today.year - 1
    return f"Championnat de France de football {start}-{start + 1}"


def l1_standings(today: dt.date, html: str | None = None) -> list[dict]:
    """Classement général de Ligue 1 : [{rang, equipe, pts, j}] dans l'ordre.

    Plusieurs tables partagent l'en-tête « Rang Équipe Pts J G N P Bp Bc Diff »
    (général, à domicile, à l'extérieur). Le classement GÉNÉRAL est celui qui
    totalise le plus de matchs joués (domicile + extérieur) : on le sélectionne
    sur la somme des J. Aucune invention : on ne renvoie que ce qui est lu.
    """
    if html is None:
        try:
            html = _wiki_html(_l1_page(today), "fr")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ classement L1 : {e!r}")
            return []
    best, best_total = [], -1
    for rows in _tables(html):
        head = [_norm(c) for c in rows[0]]
        if not ("rang" in head and "pts" in head and "j" in head and "diff" in head):
            continue
        try:
            i_eq = head.index("equipe")
            i_pts = head.index("pts")
            i_j = head.index("j")
        except ValueError:
            continue
        parsed: list[dict] = []
        for r in rows[1:]:
            if len(r) <= max(i_eq, i_pts, i_j) or not re.fullmatch(r"\d{1,2}", r[0]):
                continue
            pts, j = _int(r[i_pts]), _int(r[i_j])
            if pts is None or j is None:
                continue
            parsed.append({"rang": int(r[0]), "equipe": r[i_eq], "pts": pts, "j": j})
        total = sum(p["j"] for p in parsed)
        if parsed and total > best_total:
            best, best_total = parsed, total
    return best


def l1_club_info(today: dt.date, club: str, html: str | None = None) -> dict | None:
    """3 infos sur un club de L1 (stade, capacité, entraîneur), lues dans la
    table « présentation des clubs » de la page du championnat — source française
    fiable, aucune invention. Renvoie None si le club ou la table est introuvable."""
    if not club:
        return None
    if html is None:
        try:
            html = _wiki_html(_l1_page(today), "fr")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ infos club L1 : {e!r}")
            return None
    cible = set(_norm(club).split())
    for rows in _tables(html):
        head = [_norm(c) for c in rows[0]]

        def _col(mot: str) -> int | None:
            return next((i for i, c in enumerate(head) if mot in c), None)

        i_club, i_stade = _col("club"), _col("stade")
        i_cap, i_ent = _col("capacite"), _col("entraineur")
        if i_club is None or i_stade is None:
            continue
        for r in rows[1:]:
            if len(r) <= i_stade:
                continue
            mots = set(_norm(r[i_club]).split())
            if len(cible & mots) < max(1, len(cible) - 1):
                continue
            infos: list[str] = []
            stade = r[i_stade].strip()
            if stade:
                cap = (r[i_cap].strip() if i_cap is not None and len(r) > i_cap else "")
                infos.append(f"Stade : {stade}"
                             + (f" ({cap} places)" if re.search(r"\d", cap) else ""))
            if i_ent is not None and len(r) > i_ent and r[i_ent].strip():
                infos.append(f"Entraîneur : {r[i_ent].strip()}")
            if infos:
                return {"nom": r[i_club].strip(), "infos": infos[:3]}
    return None


# ---- NFL : classement de division sur la page « 2026 X season » (en) ---------
def nfl_division_standings(team_page: str) -> list[dict]:
    """Classement de division NFL : [{rang, equipe, w, l, t}] dans l'ordre.

    Sur une page « AAAA <Équipe> season », la table de division (4 équipes) a
    l'en-tête « W L T PCT DIV CONF PF PA STK » et, contrairement à la table de
    conférence, ne contient ni « Seed » ni colonne « Division ».
    """
    try:
        html = _wiki_html(team_page, "en")
    except Exception as e:  # noqa: BLE001
        print(f"⚠ classement NFL [{team_page}]: {e!r}")
        return []
    for rows in _tables(html):
        head = _norm(" ".join(rows[0] + rows[1]))
        if "pct" not in head or "stk" not in head or "seed" in head:
            continue
        if len(rows) > 8:            # la table de conférence est bien plus longue
            continue
        parsed: list[dict] = []
        for r in rows:
            if len(r) < 4:
                continue
            w, l, t = _int(r[1]), _int(r[2]), _int(r[3])
            equipe = r[0].strip()
            if w is None or l is None or t is None or not equipe:
                continue
            if re.search(r"[A-Za-z]", equipe) and "view" not in _norm(equipe):
                parsed.append({"rang": len(parsed) + 1, "equipe": equipe,
                               "w": w, "l": l, "t": t})
        if len(parsed) >= 3:         # une vraie division = 4 équipes
            return parsed
    return []


# ---- Ligue des champions : phase de ligue (fr), best-effort ------------------
def ucl_standing_psg(today: dt.date) -> dict | None:
    """Rang + points du PSG dans la phase de ligue de la Ligue des champions.
    Best-effort : renvoie None si la table n'est pas trouvée proprement (le PSG
    peut être éliminé, ou la table absente en début de saison)."""
    start = today.year if today.month >= 7 else today.year - 1
    title = f"Ligue des champions de l'UEFA {start}-{start + 1}"
    try:
        html = _wiki_html(title, "fr")
    except Exception as e:  # noqa: BLE001
        print(f"⚠ classement UCL [{title}]: {e!r}")
        return None
    for rows in _tables(html):
        head = [_norm(c) for c in rows[0]]
        if not (("rang" in head or "clas" in " ".join(head)) and "pts" in head):
            continue
        try:
            i_pts = head.index("pts")
        except ValueError:
            continue
        # cellule équipe = 1re cellule alphabétique après le rang
        for r in rows[1:]:
            if len(r) <= i_pts or not re.fullmatch(r"\d{1,3}", r[0]):
                continue
            eq = next((c for c in r[1:i_pts] if re.search(r"[A-Za-z]", c)), "")
            if "paris" in _norm(eq) and "saint" in _norm(eq):
                pts = _int(r[i_pts])
                if pts is not None:
                    return {"rang": int(r[0]), "pts": pts,
                            "source_url": WIKI.replace("/w/api.php", "/wiki/")
                            + title.replace(" ", "_")}
    return None


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
    dif = re.search(anc + r".{0,60}?Diffuseur\s*:?\s*([^\[]+?)\s*"
                    r"(?:\[|Stade|Parc|Arbitrage|Affluence|$)",
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


# ────────────────────── Contexte enrichi (classements) ─────────────────────
def _ord(n: int) -> str:
    return "1er" if n == 1 else f"{n}e"


def _nfl_season_page(team: str, today: dt.date) -> str:
    # La saison NFL démarre en septembre ; en janvier-février on est encore
    # dans la saison de l'année civile précédente.
    year = today.year if today.month >= 3 else today.year - 1
    return f"{year} {team} season"


def _nfl_rang_txt(row: dict) -> str:
    bilan = f"{row['w']}-{row['l']}" + (f"-{row['t']}" if row["t"] else "")
    return f"{_ord(row['rang'])} de l'AFC Nord ({bilan})"


def steelers_context(match: dict | None, today: dt.date | None = None) -> dict:
    """Classement AFC Nord des Steelers, classement du prochain adversaire et
    3 infos sur les Steelers. Chaque champ est None si la source ne le donne pas."""
    today = today or dt.datetime.now(PARIS).date()
    ctx: dict = {"mon_rang": None, "adv_rang": None, "infos": None}
    table = nfl_division_standings(_nfl_season_page("Pittsburgh Steelers", today))
    me = _standing_of(table, "Pittsburgh Steelers")
    if me:
        ctx["mon_rang"] = _nfl_rang_txt(me)
    adv = (match or {}).get("adversaire")
    if adv and adv not in ("à préciser", "à confirmer"):
        adv_table = nfl_division_standings(_nfl_season_page(adv, today))
        arow = _standing_of(adv_table, adv)
        if arow:
            ctx["adv_rang"] = f"{adv} : {_nfl_rang_txt(arow)}"
    ctx["infos"] = team_info("Pittsburgh Steelers")
    return ctx


def psg_context(match: dict | None, today: dt.date | None = None) -> dict:
    """Classement Ligue 1 du PSG, classement Ligue des champions (si encore en
    lice), classement du prochain adversaire (L1) et 3 infos sur l'adversaire."""
    today = today or dt.datetime.now(PARIS).date()
    ctx: dict = {"l1": None, "ucl": None, "adv_rang": None, "adv_infos": None}
    try:
        html = _wiki_html(_l1_page(today), "fr")   # une seule requête, partagée
    except Exception as e:  # noqa: BLE001
        print(f"⚠ page Ligue 1 : {e!r}")
        html = ""
    table = l1_standings(today, html or None)
    me = _standing_of(table, "Paris Saint-Germain")
    if me:
        ctx["l1"] = (f"{_ord(me['rang'])} de Ligue 1 — {me['pts']} pts "
                     f"en {me['j']} match{'s' if me['j'] > 1 else ''}")
    ucl = ucl_standing_psg(today)
    if ucl:
        ctx["ucl"] = f"{_ord(ucl['rang'])} de la phase de ligue ({ucl['pts']} pts)"
    adv = (match or {}).get("adversaire")
    if adv:
        arow = _standing_of(table, adv)
        if arow:
            ctx["adv_rang"] = (f"{adv} : {_ord(arow['rang'])} de Ligue 1 "
                               f"({arow['pts']} pts)")
        # 3 infos sur l'adversaire depuis la page L1 (source française fiable)
        ctx["adv_infos"] = l1_club_info(today, adv, html or None)
    return ctx
