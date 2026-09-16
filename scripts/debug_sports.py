"""DEBUG temporaire : exécute les parseurs de classement réels et écrit leurs
résultats dans public/_sport_debug.txt (récupérable via la branche). Permet de
valider L1 / AFC Nord / adversaires / infos sans consommer un run complet.
À SUPPRIMER une fois validé.
"""
from __future__ import annotations

import datetime as dt
import os

from src.collecte import sports

lines: list[str] = []


def log(*a) -> None:
    lines.append(" ".join(str(x) for x in a))


today = dt.date.today()

log("===== Ligue 1 (classement général) =====")
l1 = sports.l1_standings(today)
log(f"{len(l1)} équipes")
for r in l1[:6]:
    log(f"  {r['rang']:>2} {r['equipe']:<26} {r['pts']} pts  J{r['j']}")
psg = sports._standing_of(l1, "Paris Saint-Germain")
log(f"  PSG → {psg}")

log("\n===== AFC Nord (page Steelers) =====")
nfc = sports.nfl_division_standings("2026 Pittsburgh Steelers season")
for r in nfc:
    log(f"  {r['rang']} {r['equipe']:<24} {r['w']}-{r['l']}-{r['t']}")

log("\n===== Prochain match Steelers =====")
sm = sports.steelers_next()
log(f"  {sm}")
log("  contexte :")
log(f"  {sports.steelers_context(sm, today)}")

log("\n===== Prochain match PSG =====")
pm = sports.psg_next()
log(f"  {pm}")
log("  contexte :")
log(f"  {sports.psg_context(pm, today)}")

log("\n===== UCL PSG (best-effort) =====")
log(f"  {sports.ucl_standing_psg(today)}")

log("\n===== Infos équipe Steelers =====")
log(f"  {sports.team_info('Pittsburgh Steelers')}")

log("\n===== Infos club L1 adversaire (page championnat) =====")
log(f"  OM  → {sports.l1_club_info(today, 'Olympique de Marseille')}")
log(f"  Lens→ {sports.l1_club_info(today, 'RC Lens')}")

os.makedirs("public", exist_ok=True)
with open("public/_sport_debug.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("→ public/_sport_debug.txt écrit (", len(lines), "lignes )")
