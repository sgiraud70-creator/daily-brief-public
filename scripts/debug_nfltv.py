"""DEBUG temporaire : exécute le parseur nfl_tv_today() réel et écrit son
résultat dans public/_nfltv_debug.txt. À SUPPRIMER ensuite.
"""
from __future__ import annotations

import datetime as dt
import os

from src.collecte import sports

lines = ["=== nfl_tv_today() — diffusions NFL du jour ==="]
res = sports.nfl_tv_today(dt.date.today())
lines.append(f"{len(res)} diffusion(s)")
for m in res:
    lines.append(f"  {m['heure']}  {m['match']:<32}  {m['chaine']:<16}  "
                 + ("direct" if m["direct"] else "rediffusion"))

os.makedirs("public", exist_ok=True)
with open("public/_nfltv_debug.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines))
