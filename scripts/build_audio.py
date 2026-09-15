"""Génère la version audio du brief : script oral → MP3 (public/brief.mp3).

Lit data/brief.json et public/weather.json. Écrit data/script_audio.txt et
public/brief.mp3. Usage : python -m scripts.build_audio
"""
from __future__ import annotations

import json
import os

from src.audio import script, tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEF = os.path.join(ROOT, "data", "brief.json")
WEATHER = os.path.join(ROOT, "public", "weather.json")
SCRIPT_OUT = os.path.join(ROOT, "data", "script_audio.txt")
MP3_OUT = os.path.join(ROOT, "public", "brief.mp3")


def _load(path: str):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def main() -> int:
    brief = _load(BRIEF)
    if not brief:
        print("⚠ data/brief.json absent — rien à vocaliser.")
        return 1
    weather = _load(WEATHER)

    texte = script.build_script(brief, weather)
    with open(SCRIPT_OUT, "w", encoding="utf-8") as f:
        f.write(texte)
    mots = len(texte.split())
    print(f"✓ script oral : {SCRIPT_OUT} (~{mots} mots, ~{mots // 150} min à l'oral)")

    info = tts.synth(texte, MP3_OUT)
    ko = os.path.getsize(MP3_OUT) // 1024
    print(f"✓ MP3 : {MP3_OUT} ({ko} Ko) — moteur {info['moteur']}, voix {info['voix']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
