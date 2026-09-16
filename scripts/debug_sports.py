"""DEBUG temporaire : dumpe l'en-tête et la 1re ligne de CHAQUE table des
articles Wikipédia visés, dans public/_sport_debug.txt (récupérable via la
branche). Une seule exécution révèle toutes les structures. À retirer ensuite.
"""
from __future__ import annotations

import html
import os
import re

import requests

UA = {"User-Agent": "DailyBriefBot/1.0 (debug)"}
lines: list[str] = []


def log(*a) -> None:
    lines.append(" ".join(str(x) for x in a))


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _cells(tr: str) -> list[str]:
    return [_clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]


def _html(lang: str, page: str) -> str:
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params={
        "action": "parse", "page": page, "prop": "text",
        "format": "json", "formatversion": 2, "redirects": 1,
    }, headers=UA, timeout=25)
    d = r.json()
    return d["parse"]["text"] if "parse" in d else ""


def dump_all(lang: str, page: str) -> None:
    log(f"\n########## {lang}:{page} ##########")
    h = _html(lang, page)
    if not h:
        log("  INTROUVABLE")
        return
    for i, tb in enumerate(re.findall(r"<table[^>]*>.*?</table>", h, re.S)):
        rows = re.findall(r"<tr[^>]*>.*?</tr>", tb, re.S)
        if len(rows) < 3:
            continue
        klass = (re.match(r"<table[^>]*class=\"([^\"]*)\"", tb) or [None, ""])[1]
        # en-tête = concat des 2 premières lignes (les tables sportives ont
        # souvent une ligne titre puis une ligne de colonnes)
        head = " ".join(_cells(rows[0]) + _cells(rows[1]))
        log(f"  --- table #{i}  ({len(rows)} lignes, class={klass[:30]}) ---")
        log(f"      HEAD: {head[:160]}")
        for tr in rows[1:5]:
            log("      ROW:", " | ".join(c[:16] for c in _cells(tr))[:150])


dump_all("fr", "Championnat de France de football 2026-2027")
dump_all("en", "2026 Pittsburgh Steelers season")

os.makedirs("public", exist_ok=True)
with open("public/_sport_debug.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("→ public/_sport_debug.txt écrit (", len(lines), "lignes )")
