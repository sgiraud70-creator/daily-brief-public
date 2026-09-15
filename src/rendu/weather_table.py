"""Repli du bloc météo en tableau HTML à styles inline (EF-17h/EF-17i).

Sert quand les images sont bloquées par le client mail. Aucun SVG, aucun JS.
Fournit aussi un texte alternatif (attribut alt du PNG).
"""
from __future__ import annotations

from src.collecte.meteo import label_for

GOLD = "#c9a24b"
GOLD_HI = "#e7cd86"
PAPER = "#f1ede4"
MUTED = "#a49f93"
INK = "#0d0d0f"
PANEL = "#16161b"
LINE = "#2c2c34"


def alt_text(data: dict, place: str = "Loulans-Verchamp") -> str:
    c = data["current"]
    parts = [f"Météo {place} : {label_for(c['code']).lower()}, {c['temp']}°",
             f"(ressenti {c['feels']}°, min {c['tmin']}° / max {c['tmax']}°,",
             f"pluie {c['precip_prob']} %, vent {c['wind']} km/h)."]
    if data["steps"]:
        s = data["steps"]
        parts.append("Journée : " + ", ".join(f"{x['hh']} {x['temp']}°" for x in s) + ".")
    return " ".join(parts)


def render_html(data: dict, place: str = "Loulans-Verchamp",
                vigilance: dict | None = None) -> str:
    c = data["current"]
    cell = f"padding:6px 8px;border-bottom:1px solid {LINE};font-family:Arial,sans-serif;"
    th = f"{cell}color:{GOLD};font-size:11px;letter-spacing:.08em;text-transform:uppercase;"

    head = (
        f'<tr><td style="{cell}color:{PAPER};font-size:22px;font-weight:bold">{c["temp"]}°</td>'
        f'<td style="{cell}color:{MUTED};font-size:13px" colspan="7">'
        f'{label_for(c["code"])} · ressenti {c["feels"]}° · {c["tmin"]}°/{c["tmax"]}° · '
        f'pluie {c["precip_prob"]} % · vent {c["wind"]} km/h</td></tr>'
    )

    vig = ""
    if vigilance and vigilance.get("level", "vert") != "vert":
        vcol = {"jaune": GOLD, "orange": "#d88c3c", "rouge": "#cf6b5c"}.get(vigilance["level"], GOLD)
        vig = (f'<tr><td colspan="8" style="{cell}color:{vcol};font-weight:bold">'
               f'⚠ Vigilance {vigilance["level"]} — Haute-Saône : {vigilance.get("label","")}</td></tr>')

    # ligne des tranches 2 h
    hh = "".join(f'<td style="{th}text-align:center">{s["hh"]}</td>' for s in data["steps"])
    tt = "".join(f'<td style="{cell}color:{GOLD_HI};text-align:center;font-weight:bold">{s["temp"]}°</td>'
                 for s in data["steps"])
    pp = "".join(f'<td style="{cell}color:{MUTED};text-align:center;font-size:11px">'
                 f'{(str(s["precip"]).rstrip("0").rstrip(".")+" mm") if s["precip"]>0 else "—"}</td>'
                 for s in data["steps"])

    # jours J+1..J+6
    dn = "".join(f'<td style="{th}text-align:center">{x["name"]}</td>' for x in data["days"])
    dt_ = "".join(f'<td style="{cell}color:{PAPER};text-align:center">'
                  f'{x["tmax"]}°<span style="color:{MUTED}"> / {x["tmin"]}°</span></td>'
                  for x in data["days"])

    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="max-width:760px;background:{PANEL};border:1px solid {LINE};'
        f'border-collapse:collapse">'
        f'<tr><td colspan="8" style="{cell}color:{GOLD};font-size:11px;'
        f'letter-spacing:.1em;text-transform:uppercase">Météo — {place}</td></tr>'
        f'{head}{vig}'
        f'<tr><td colspan="8" style="{th}">Aujourd\'hui (pas de 2 h)</td></tr>'
        f'<tr>{hh}</tr><tr>{tt}</tr><tr>{pp}</tr>'
        f'<tr><td colspan="8" style="{th}">Prochains jours</td></tr>'
        f'<tr>{dn}</tr><tr>{dt_}</tr>'
        f'</table>'
    )
