"""DEBUG temporaire : explore la structure TheSportsDB (classements + fiches).

Écrit public/_sport_debug.json pour analyse hors-ligne. À retirer ensuite.
"""
from __future__ import annotations

import json
import os

import requests

BASE = "https://www.thesportsdb.com/api/v1/json/3"
UA = {"User-Agent": "DailyBriefBot/1.0 (debug)"}
out: dict = {}


def g(name: str, path: str, **params) -> None:
    try:
        r = requests.get(f"{BASE}/{path}", params=params, headers=UA, timeout=25)
        try:
            j = r.json()
        except Exception:  # noqa: BLE001
            j = {"_raw": r.text[:300]}
        out[name] = {"status": r.status_code, "params": params, "json": j}
        keys = list(j.keys()) if isinstance(j, dict) else type(j).__name__
        print(f"{name}: HTTP {r.status_code} → clés {keys}")
    except Exception as e:  # noqa: BLE001
        out[name] = {"error": repr(e), "params": params}
        print(f"{name}: ERREUR {e!r}")


# NFL : league id 4391 ; essaie plusieurs formats de saison
g("nfl_table_2026", "lookuptable.php", l="4391", s="2026")
g("nfl_table_2026_2027", "lookuptable.php", l="4391", s="2026-2027")
# Ligue 1 : league id 4334
g("l1_table_2026_2027", "lookuptable.php", l="4334", s="2026-2027")
# Fiche équipe : Steelers (id vu précédemment 134925)
g("steelers_team", "lookupteam.php", id="134925")
# Infos ligue (pour vérifier l'id / la saison courante)
g("nfl_league", "lookupleague.php", id="4391")
g("l1_league", "lookupleague.php", id="4334")

os.makedirs("public", exist_ok=True)
with open("public/_sport_debug.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
print("→ public/_sport_debug.json écrit")
