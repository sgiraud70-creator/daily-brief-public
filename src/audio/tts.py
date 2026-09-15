"""Synthèse vocale à double moteur (EF-34).

- Moteur principal : edge-tts (voix FR variées). Souvent bloqué depuis une IP de
  datacenter (R-02) → essai court, puis bascule.
- Repli : Piper (local, open-source, sans quota, jamais bloqué). Voix FR tirée
  au hasard chaque jour ; modèle téléchargé depuis HuggingFace si absent.
- Conversion WAV→MP3 via ffmpeg fourni par imageio-ffmpeg (aucune install système).
"""
from __future__ import annotations

import asyncio
import os
import random
import subprocess
import urllib.request

# Voix edge-tts (utilisées quand le service répond)
EDGE_VOICES = [
    "fr-FR-DeniseNeural", "fr-FR-HenriNeural", "fr-FR-EloiseNeural",
    "fr-FR-RemyMultilingualNeural", "fr-FR-VivienneMultilingualNeural",
]

# Voix Piper (repli fiable). On garde uniquement une voix medium naturelle
# (siwis, féminine) : les voix « low » (gilles) sonnent robotiques/saccadées.
PIPER_VOICES = ["fr_FR-siwis-medium"]
PIPER_DIR = os.path.join(os.path.expanduser("~"), ".cache", "piper")
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/"


# ------------------------------------------------------------------ edge ----
def _edge(text: str, out_path: str, voice: str, timeout: int = 8) -> None:
    import edge_tts

    async def _run() -> None:
        await asyncio.wait_for(edge_tts.Communicate(text, voice).save(out_path),
                               timeout=timeout)

    asyncio.run(_run())


# ----------------------------------------------------------------- piper ----
def _voice_urls(voice: str) -> tuple[str, str]:
    _, name, quality = voice.split("-")            # fr_FR-siwis-medium
    base = f"{HF}{name}/{quality}/{voice}"
    return base + ".onnx", base + ".onnx.json"


def _ensure_piper_voice(voice: str) -> str:
    os.makedirs(PIPER_DIR, exist_ok=True)
    onnx = os.path.join(PIPER_DIR, f"{voice}.onnx")
    url_onnx, url_cfg = _voice_urls(voice)
    for path, url in [(onnx, url_onnx), (onnx + ".json", url_cfg)]:
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            urllib.request.urlretrieve(url, path)
    return onnx


def prefetch_voices() -> None:
    """Pré-télécharge toutes les voix Piper dans PIPER_DIR (pour le cache CI).

    Idempotent : ne retélécharge pas une voix déjà présente. Une voix qui
    échoue n'interrompt pas les autres (le repli au runtime gère le reste).
    """
    for voice in PIPER_VOICES:
        try:
            _ensure_piper_voice(voice)
            print(f"  ✓ voix Piper prête : {voice}")
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠ voix Piper {voice} indisponible : {e!r}")


def _gtts(text: str, out_path: str, timeout: int = 90) -> dict:
    """Voix Google (naturelle). Appelle translate.google.com → peut être bloqué
    en datacenter. Garde-temps : si ça n'aboutit pas, on lève et on bascule."""
    import concurrent.futures

    from gtts import gTTS

    tld = os.environ.get("GTTS_TLD", "fr")   # "fr" = France, "ca" = Canada

    def _run() -> None:
        gTTS(text=text, lang="fr", tld=tld).save(out_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        ex.submit(_run).result(timeout=timeout)
    return {"moteur": "gTTS", "voix": "google-fr"}


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _piper(text: str, out_path: str) -> dict:
    voice = random.choice(PIPER_VOICES)
    onnx = _ensure_piper_voice(voice)
    wav = out_path[:-4] + ".wav" if out_path.endswith(".mp3") else out_path + ".wav"
    try:
        subprocess.run(["piper", "-m", onnx, "-f", wav],
                       input=text.encode("utf-8"), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([_ffmpeg(), "-y", "-i", wav, "-ac", "1", "-ar", "24000",
                        "-b:a", "48k", out_path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        if os.path.exists(wav):
            os.remove(wav)
    return {"moteur": "piper", "voix": voice}


# ------------------------------------------------------------------ api ----
def synth(text: str, out_path: str) -> dict:
    """Génère le MP3. Renvoie {moteur, voix}. Lève si tous les moteurs échouent."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # 0) gTTS (voix Google, plus naturelle) — peut être bloqué en datacenter
    try:
        info = _gtts(text, out_path)
        if os.path.getsize(out_path) > 1000:
            return info
    except Exception as e:  # noqa: BLE001
        print(f"  gTTS indisponible ({e!r}) → essai edge-tts")
    # 1) edge-tts (essai court : souvent bloqué en datacenter)
    try:
        _edge(text, out_path, random.choice(EDGE_VOICES), timeout=8)
        if os.path.getsize(out_path) > 1000:
            return {"moteur": "edge-tts", "voix": "fr-FR"}
    except Exception as e:  # noqa: BLE001
        print(f"  edge-tts indisponible ({e!r}) → repli Piper")
    # 2) repli Piper (fiable)
    return _piper(text, out_path)
