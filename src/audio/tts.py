"""Synthèse vocale à double moteur (EF-34).

Moteur principal : edge-tts (voix françaises, gratuit). Voix tirée au hasard
chaque jour (choix utilisateur). Repli : Piper (local, sans quota) — activé si
edge-tts échoue (R-02 : erreurs 403 constatées). Piper nécessite un modèle de
voix ; s'il est absent, on lève une erreur claire (à compléter au maillon Piper).
"""
from __future__ import annotations

import asyncio
import os
import random

# Voix FR de qualité (tirage aléatoire quotidien)
VOICES = [
    "fr-FR-DeniseNeural",
    "fr-FR-HenriNeural",
    "fr-FR-EloiseNeural",
    "fr-FR-RemyMultilingualNeural",
    "fr-FR-VivienneMultilingualNeural",
]


def _edge(text: str, out_path: str, voice: str) -> None:
    import edge_tts

    async def _run() -> None:
        await edge_tts.Communicate(text, voice).save(out_path)

    asyncio.run(_run())


def synth(text: str, out_path: str) -> dict:
    """Génère le MP3. Renvoie {moteur, voix}. Lève si tous les moteurs échouent."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    voice = random.choice(VOICES)
    # edge-tts, avec quelques essais (R-02)
    last = None
    for attempt in range(3):
        try:
            _edge(text, out_path, voice)
            if os.path.getsize(out_path) > 1000:
                return {"moteur": "edge-tts", "voix": voice}
        except Exception as e:  # noqa: BLE001
            last = e
    # repli Piper (à compléter : nécessite un modèle de voix installé)
    try:
        return _piper(text, out_path)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Échec TTS (edge: {last!r} ; piper: {e!r})")


def _piper(text: str, out_path: str) -> dict:
    """Repli Piper — nécessite le binaire piper et un modèle fr. À finaliser."""
    raise NotImplementedError("Repli Piper non encore installé")
