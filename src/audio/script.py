"""Construit le SCRIPT ORAL du brief (sortie distincte du HTML, EF-31).

Adapté à l'écoute : pas d'URL, pas de tableau ni de série horaire lus
littéralement, transitions parlées entre rubriques. Météo résumée en trois
moments (matin / après-midi / soirée) + vigilance (EF-17f).
"""
from __future__ import annotations

import re

from src.collecte.meteo import label_for

# Épellation phonétique des lettres (pour que la voix dise « pé esse gé », pas « pseug »)
_LETTRE = {
    "A": "a", "B": "bé", "C": "cé", "D": "dé", "E": "eu", "F": "effe", "G": "gé",
    "H": "ache", "I": "i", "J": "ji", "K": "ka", "L": "elle", "M": "emme",
    "N": "enne", "O": "o", "P": "pé", "Q": "ku", "R": "erre", "S": "esse",
    "T": "té", "U": "u", "V": "vé", "W": "double vé", "X": "ixe", "Y": "i grec",
    "Z": "zède",
}
# Sigles qui se prononcent comme des mots (ne pas épeler)
_MOTS = {"OTAN", "SIDA", "PACS", "SMIC", "INSEE", "OVNI", "ONU", "UNESCO",
         "RSA", "OPEP", "GAFAM", "RGPD", "AZERTY", "OQTF"}
_SIGLE = re.compile(r"\b(?:[A-ZÀ-Ý]\.?){2,}")


def _epeler(m: re.Match) -> str:
    lettres = re.sub(r"[^A-ZÀ-Ý]", "", m.group(0).upper())
    if lettres in _MOTS:
        return lettres.capitalize() + " "
    return " ".join(_LETTRE.get(c, c) for c in lettres) + " "


def _heure(m: re.Match) -> str:
    """« 20h45 » → « 20 heures 45 » ; « 20h00 »/« 20h » → « 20 heures »."""
    h = int(m.group(1))
    mot = "heure" if h == 1 else "heures"
    mn = m.group(2)
    if not mn or mn == "00":
        return f"{h} {mot}"
    return f"{h} {mot} {int(mn)}"


def speakable(texte: str) -> str:
    """Adapte le texte à l'oral : heures parlées (20h45 → « 20 heures 45 ») et
    sigles épelés (P.S.G → « pé esse gé »)."""
    texte = re.sub(r"\b(\d{1,2})\s*h\s*(\d{2})?\b", _heure, texte)  # heures
    texte = _SIGLE.sub(_epeler, texte)
    texte = re.sub(r"\s+([.,;:!?])", r"\1", texte)   # pas d'espace avant ponctuation
    texte = re.sub(r"[ \t]{2,}", " ", texte)          # espaces multiples
    return texte


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
            # Un sujet = UNE ligne fluide (titre + points), car Piper synthétise
            # ligne par ligne : trop de lignes courtes = lecture hachée.
            titre = s.get("title", "").rstrip(".")
            parts = [f"{titre}."]
            for b in s.get("bullets", []):
                parts.append(b if b.endswith(".") else b + ".")
            lignes.append(" ".join(parts))

    lignes.append("C'était votre brief du matin. Très bonne journée.")
    # sigles épelés + heures parlées ; regroupement en lignes fluides
    return speakable("\n".join(lignes))
