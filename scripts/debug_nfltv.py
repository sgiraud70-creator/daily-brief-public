"""DEBUG temporaire : capture la structure de la page NFL de tv-sports.fr pour
concevoir un parseur (diffusions TV du jour). Écrit dans public/_nfltv_debug.txt.
À SUPPRIMER ensuite.
"""
from __future__ import annotations

import html
import os
import re

import requests

URL = "https://tv-sports.fr/football-americain/nfl"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")}
lines: list[str] = []


def log(*a) -> None:
    lines.append(" ".join(str(x) for x in a))


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


try:
    r = requests.get(URL, headers=UA, timeout=25)
    log(f"HTTP {r.status_code}  {len(r.content)} octets  ct={r.headers.get('content-type','')}")
    body = r.text
except Exception as e:  # noqa: BLE001
    log(f"ERREUR fetch : {e!r}")
    body = ""

if body:
    # 1) Texte lisible complet (pour voir les matchs/chaînes/heures du jour)
    txt = clean(body)
    log("\n===== TEXTE (0-6000) =====")
    log(txt[:6000])

    # 2) Blocs HTML contenant une heure (hh h mm / hh:mm) : révèle la structure
    log("\n===== BLOCS AVEC HEURE (HTML brut, 10 premiers) =====")
    heure = re.compile(r"\d{1,2}\s?[h:]\s?\d{2}")
    blocs = re.findall(r"<(?:li|tr|article|div)[^>]*>.*?</(?:li|tr|article|div)>", body, re.S)
    n = 0
    for b in blocs:
        if heure.search(clean(b)) and len(b) < 1400:
            log(f"--- bloc #{n} ---")
            log(b.strip()[:1200])
            n += 1
            if n >= 10:
                break

    # 3) Noms de chaînes repérés (pour connaître le vocabulaire)
    log("\n===== CHAÎNES REPÉRÉES =====")
    chaines = re.findall(r"(beIN\s?Sports?[^<\s]*|L['’]Équipe|DAZN|RMC\s?Sport[^<\s]*|"
                         r"Canal\+[^<\s]*|NFL\s?Game\s?Pass|Free)", body, re.I)
    from collections import Counter
    for name, c in Counter(clean(x) for x in chaines).most_common(20):
        log(f"  {c:>3}×  {name}")

os.makedirs("public", exist_ok=True)
with open("public/_nfltv_debug.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("→ public/_nfltv_debug.txt écrit (", len(lines), "lignes )")
