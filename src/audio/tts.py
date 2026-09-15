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
import subprocess
import urllib.request

# Voix Piper (repli local). Modèle téléchargé depuis HuggingFace si absent.
PIPER_VOICE = "fr_FR-siwis-medium"
PIPER_BASE = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
              "fr/fr_FR/siwis/medium/")
PIPER_DIR = os.path.join(os.path.expanduser("~"), ".cache", "piper")

# Voix FR de qualité (tirage aléatoire quotidien)
VOICES = [
    "fr-FR-DeniseNeural",
    "fr-FR-HenriNeural",
    "fr-FR-EloiseNeural",
    "fr-FR-RemyMultilingualNeural",
    "fr-FR-VivienneMultilingualNeural",
]


def _edge(text: str, out_path: str, voice: str, timeout: int = 120) -> None:
    import edge_tts

    async def _run() -> None:
        # timeout dur : edge-tts peut se bloquer (R-02) — on n'attend jamais indéfiniment
        await asyncio.wait_for(edge_tts.Communicate(text, voice).save(out_path),
                               timeout=timeout)

    asyncio.run(_run())


def synth(text: str, out_path: str) -> dict:
    """Génère le MP3. Renvoie {moteur, voix}. Lève si tous les moteurs échouent."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    voice = random.choice(VOICES)
    # edge-tts (voix variées) — souvent bloqué sur IP datacenter (R-02) :
    # 2 essais courts, puis on bascule vite sur Piper.
    last = None
    for _ in range(2):
        try:
            _edge(text, out_path, voice, timeout=60)
            if os.path.getsize(out_path) > 1000:
                return {"moteur": "edge-tts", "voix": voice}
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  edge-tts indisponible ({e!r}) → repli Piper")
            break
    # repli local Piper (toujours disponible)
    try:
        return _piper(text, out_path)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Échec TTS (edge: {last!r} ; piper: {e!r})")


def _ensure_piper_voice() -> str:
    """Télécharge le modèle de voix Piper si absent ; renvoie le chemin du .onnx."""
    os.makedirs(PIPER_DIR, exist_ok=True)
    onnx = os.path.join(PIPER_DIR, f"{PIPER_VOICE}.onnx")
    cfg = onnx + ".json"
    for path, url in [(onnx, PIPER_BASE + f"{PIPER_VOICE}.onnx"),
                      (cfg, PIPER_BASE + f"{PIPER_VOICE}.onnx.json")]:
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            urllib.request.urlretrieve(url, path)
    return onnx


def _piper(text: str, out_path: str) -> dict:
    """Repli local Piper (sans quota, sans blocage) → WAV puis MP3 via ffmpeg."""
    onnx = _ensure_piper_voice()
    wav = out_path[:-4] + ".wav" if out_path.endswith(".mp3") else out_path + ".wav"
    subprocess.run(["piper", "-m", onnx, "-f", wav],
                   input=text.encode("utf-8"), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-i", wav, "-ac", "1", "-ar", "24000",
                    "-b:a", "48k", out_path], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(wav):
        os.remove(wav)
    return {"moteur": "piper", "voix": PIPER_VOICE}
