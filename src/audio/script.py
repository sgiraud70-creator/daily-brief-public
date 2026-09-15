"""Construit le SCRIPT ORAL du brief (sortie distincte du HTML, EF-31).

Adapté à l'écoute : pas d'URL, pas de tableau ni de série horaire lus
littéralement, transitions parlées entre rubriques. Météo résumée en trois
moments (matin / après-midi / soirée) + vigilance (EF-17f).
"""
from __future__ import annotations

from src.collecte.meteo import label_for


def _moment(steps: list[dict], heures: list[int]) -> tuple[str, int] | None:
    sel = [s for s in steps if int(str(s["hh"]).rstrip("h")) in heures]
    if not sel:
        return None
    mid = sel[len(sel) // 2]
    return label_for(mid["code"]).lower(), mid["temp"]


def weather_paragraph(weather: dict) -> str:
    place = weather.get("place", "votre commune")
    steps = weather.get("steps", [])
    parts = [f"Côté météo à {place}."]
    for nom, heures in [("Ce matin", [7, 9, 11]),
                        ("Cet après-midi", [13, 15, 17]),
                        ("Ce soir", [19, 21, 23])]:
        m = _moment(steps, heures)
        if m:
            parts.append(f"{nom}, {m[0]}, environ {m[1]} degrés.")
    vig = weather.get("vigilance")
    if vig and vig.get("level", "vert") != "vert":
        parts.append(f"Attention, vigilance {vig['level']} en Haute-Saône.")
    return " ".join(parts)


def build_script(brief: dict, weather: dict | None) -> str:
    lignes = [f"Bonjour, voici votre brief du {brief.get('date_str', 'jour')}."]
    if weather:
        lignes.append(weather_paragraph(weather))

    for r in brief.get("rubriques", []):
        sujets = r.get("sujets", [])
        if not sujets:
            continue  # à l'oral, on passe les rubriques vides
        lignes.append(f"Rubrique {r['label']}.")
        for s in sujets:
            titre = s.get("title", "").rstrip(".")
            lignes.append(f"{titre}.")
            for b in s.get("bullets", []):
                lignes.append(b if b.endswith(".") else b + ".")

    lignes.append("C'était votre brief du matin. Très bonne journée.")
    # une phrase par ligne = pauses naturelles à la lecture
    return "\n".join(lignes)
