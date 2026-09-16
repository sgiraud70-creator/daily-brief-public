"""DEBUG temporaire : structure des classements Wikipédia (L1 + NFL) et fiche
équipe TheSportsDB. Affiche des extraits dans les logs. À retirer ensuite.
"""
from __future__ import annotations

import html
import re

import requests

UA = {"User-Agent": "DailyBriefBot/1.0 (debug)"}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def wiki_tables(lang: str, page: str, motscle: tuple[str, ...]) -> None:
    print(f"\n===== {lang}.wikipedia : {page} =====")
    try:
        r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params={
            "action": "parse", "page": page, "prop": "text",
            "format": "json", "formatversion": 2, "redirects": 1,
        }, headers=UA, timeout=25)
        data = r.json()
    except Exception as e:  # noqa: BLE001
        print("  ERREUR", repr(e))
        return
    if "parse" not in data:
        print("  article introuvable :", data.get("error"))
        return
    html_txt = data["parse"]["text"]
    tables = re.findall(r"<table[^>]*>.*?</table>", html_txt, re.S)
    print(f"  {len(tables)} tables")
    for i, tb in enumerate(tables):
        txt = _clean(tb)[:200].lower()
        if any(m in txt for m in motscle):
            rows = re.findall(r"<tr[^>]*>.*?</tr>", tb, re.S)
            print(f"  --- table #{i} (candidate classement, {len(rows)} lignes) ---")
            for tr in rows[:4]:
                cells = [_clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
                print("     ", [c[:22] for c in cells if c][:9])
            break


# Ligue 1
wiki_tables("fr", "Championnat de France de football 2026-2027",
            ("pts", "points", "classement", "j g n p"))
# NFL (classements par division)
wiki_tables("en", "2026 NFL season", ("afc north", "w l t", "pct", "division"))

# Fiche équipe TheSportsDB (infos) — Steelers
try:
    t = requests.get("https://www.thesportsdb.com/api/v1/json/3/lookupteam.php",
                     params={"id": "134925"}, headers=UA, timeout=25).json()["teams"][0]
    print("\n===== Steelers infos =====")
    print("  stade:", t.get("strStadium"), "| ville:", t.get("strLocation"),
          "| créé:", t.get("intFormedYear"))
except Exception as e:  # noqa: BLE001
    print("team ERREUR", repr(e))
