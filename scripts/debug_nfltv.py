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

    # 2) Cartes de diffusion : éléments porteurs de data-schedule-type
    log("\n===== CARTES data-schedule-type (fenêtre HTML, 8 premières) =====")
    idxs = [m.start() for m in re.finditer(r"data-schedule-type=", body)]
    log(f"{len(idxs)} occurrences de data-schedule-type")
    for k, i in enumerate(idxs[:12]):
        frag = body[i:i + 3500]
        stype = (re.match(r'data-schedule-type="([^"]*)"', body[i:i + 40]) or [None, "?"])[1]
        classes = sorted(set(re.findall(r'class="(schedule-item__[a-z-]+)', frag)))
        # heure dans <time ...>HH:MM</time> ou attribut datetime
        t = re.search(r"<time[^>]*>(.*?)</time>", frag, re.S)
        dtime = re.search(r'datetime="([^"]+)"', frag)
        log(f"--- carte #{k}  type={stype} ---")
        log("  time:", clean(t.group(1)) if t else "?", "| datetime:", dtime.group(1) if dtime else "?")
        log("  classes:", " ".join(classes)[:200])
        log("  TEXTE:", clean(frag)[:260])

    # 2b) Marqueurs de date/jour (pour repérer « le jour »)
    log("\n===== MARQUEURS DATE (data-date / entêtes jour) =====")
    for m in re.finditer(r"data-(?:date|day|schedule-date)[^=]*=\"([^\"]{0,40})\"", body):
        log("  attr:", m.group(0)[:80])
    for m in list(re.finditer(r">(?:Aujourd|Demain|lundi|mardi|mercredi|jeudi|vendredi|"
                              r"samedi|dimanche)[^<]{0,40}<", body, re.I))[:12]:
        log("  jour:", clean(m.group(0))[:60])

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
