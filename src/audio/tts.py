"""Synthèse vocale à moteurs en cascade (EF-34).

Ordre d'essai, du plus naturel au plus fiable :
1. edge-tts (voix Microsoft Henri, masculine, naturelle, sans clé).
2. gTTS (voix Google Traduction, naturelle mais plate).
3. Piper (local, open-source, sans quota, jamais bloqué) — filet de sécurité.

Chaque moteur qui échoue bascule automatiquement sur le suivant : jamais de
brief sans audio. Conversion/recollage via ffmpeg (imageio-ffmpeg, portable).
"""
from __future__ import annotations

import asyncio
import os
import random
import subprocess
import urllib.request

# Voix edge-tts (Microsoft, gratuite, sans clé). Henri = masculine française.
# Configurable via EDGE_VOICE (ex. fr-FR-DeniseNeural, fr-FR-RemyMultilingualNeural…).
EDGE_VOICE = os.environ.get("EDGE_VOICE", "fr-FR-HenriNeural")

# Voix Piper (repli fiable). On garde uniquement une voix medium naturelle
# (siwis, féminine) : les voix « low » (gilles) sonnent robotiques/saccadées.
PIPER_VOICES = ["fr_FR-siwis-medium"]
PIPER_DIR = os.path.join(os.path.expanduser("~"), ".cache", "piper")
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/"


# ------------------------------------------------------------------ edge ----
def _edge(text: str, out_path: str, voice: str, timeout: int = 180) -> None:
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


# ------------------------------------------------------- Google Cloud TTS ----
def _split_for_tts(text: str, limit: int = 4500) -> list[str]:
    """Découpe le texte en morceaux ≤ `limit` octets sur les sauts de ligne
    (Google Cloud TTS accepte 5000 octets max par requête)."""
    morceaux: list[str] = []
    cur = ""
    for ligne in text.split("\n"):
        cand = f"{cur}\n{ligne}" if cur else ligne
        if len(cand.encode("utf-8")) > limit and cur:
            morceaux.append(cur)
            cur = ligne
        else:
            cur = cand
    if cur:
        morceaux.append(cur)
    return morceaux


def _google_cloud(text: str, out_path: str, timeout: int = 60) -> dict:
    """Voix Google Cloud « Neural2 » (dynamique, expressive). Authentifiée par
    clé API (secret GOOGLE_TTS_API_KEY). Découpe + recolle les morceaux via ffmpeg.
    Gratuit dans le quota mensuel (1 M caractères Neural2)."""
    import base64
    import shutil
    import tempfile

    key = os.environ.get("GOOGLE_TTS_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_TTS_API_KEY absent")
    import requests  # dépendance déjà présente (collecte)

    voice = os.environ.get("GOOGLE_TTS_VOICE", "fr-FR-Neural2-A")
    tmp = tempfile.mkdtemp(prefix="gctts_")
    parts: list[str] = []
    try:
        for i, morceau in enumerate(_split_for_tts(text)):
            r = requests.post(
                "https://texttospeech.googleapis.com/v1/text:synthesize",
                params={"key": key},
                json={
                    "input": {"text": morceau},
                    "voice": {"languageCode": "fr-FR", "name": voice},
                    "audioConfig": {"audioEncoding": "MP3", "sampleRateHertz": 24000},
                },
                timeout=timeout,
            )
            r.raise_for_status()
            audio = base64.b64decode(r.json()["audioContent"])
            p = os.path.join(tmp, f"part_{i:03d}.mp3")
            with open(p, "wb") as f:
                f.write(audio)
            parts.append(p)
        if not parts:
            raise RuntimeError("aucun audio produit")
        if len(parts) == 1:
            shutil.move(parts[0], out_path)
        else:  # recollage sans réencodage
            liste = os.path.join(tmp, "list.txt")
            with open(liste, "w", encoding="utf-8") as f:
                for p in parts:
                    f.write(f"file '{p}'\n")
            subprocess.run([_ffmpeg(), "-y", "-f", "concat", "-safe", "0",
                            "-i", liste, "-c", "copy", out_path], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"moteur": "Google Cloud TTS", "voix": voice}


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
    # 1) edge-tts (voix Microsoft Henri, naturelle) — délai généreux (brief long)
    try:
        _edge(text, out_path, EDGE_VOICE)
        if os.path.getsize(out_path) > 1000:
            return {"moteur": "edge-tts", "voix": EDGE_VOICE}
    except Exception as e:  # noqa: BLE001
        print(f"  edge-tts indisponible ({e!r}) → essai gTTS")
    # 2) gTTS (voix Google Traduction, naturelle mais plate)
    try:
        info = _gtts(text, out_path)
        if os.path.getsize(out_path) > 1000:
            return info
    except Exception as e:  # noqa: BLE001
        print(f"  gTTS indisponible ({e!r}) → repli Piper")
    # 3) repli Piper (local, fiable)
    return _piper(text, out_path)
