"""DEBUG temporaire : cible les VRAIES tables de classement (L1 + NFL). Logs."""
from __future__ import annotations

import html
import re

import requests

UA = {"User-Agent": "DailyBriefBot/1.0 (debug)"}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _fetch_html(lang: str, page: str) -> str:
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params={
        "action": "parse", "page": page, "prop": "text",
        "format": "json", "formatversion": 2, "redirects": 1,
    }, headers=UA, timeout=25)
    d = r.json()
    return d["parse"]["text"] if "parse" in d else ""


def show(lang: str, page: str, need: tuple[str, ...], nrows: int = 6) -> None:
    print(f"\n===== {lang}:{page} =====")
    html_txt = _fetch_html(lang, page)
    if not html_txt:
        print("  introuvable")
        return
    for i, tb in enumerate(re.findall(r"<table[^>]*>.*?</table>", html_txt, re.S)):
        rows = re.findall(r"<tr[^>]*>.*?</tr>", tb, re.S)
        if not rows:
            continue
        header = " ".join(_clean(c) for c in
                          re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rows[0], re.S)).lower()
        if all(n in header for n in need):
            print(f"  --- table #{i} ({len(rows)} lignes) header: {header[:90]}")
            for tr in rows[1:nrows]:
                cells = [_clean(c) for c in
                         re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
                print("     ", [c[:20] for c in cells][:11])
            return
    print("  (aucune table ne matche", need, ")")


# L1 : vraie table de classement = header contenant Pts et J (matchs joués)
show("fr", "Championnat de France de football 2026-2027", ("pts", "j"))
# NFL : classement AFC Nord dans l'article de la saison des Steelers
show("en", "2026 Pittsburgh Steelers season", ("w", "l", "t"))
show("en", "2026 Pittsburgh Steelers season", ("pct",))
