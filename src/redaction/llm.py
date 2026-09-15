"""Couche d'abstraction LLM (parade R-01 / ENF-07).

Un seul point d'entrée `chat()` ; le fournisseur est choisi par la variable
d'environnement LLM_PROVIDER (défaut : mistral). Pour changer de fournisseur,
il suffit d'ajouter une fonction `_backend()` et une entrée dans BACKENDS —
le reste du code (rédacteur) n'a rien à changer.
"""
from __future__ import annotations

import os
import time

import requests

TIMEOUT = 90
RETRIES = 4                       # réessais sur limite de débit / indisponibilité
BACKOFF = [4, 10, 20, 40]        # secondes (palier gratuit : limites basses)


class LLMError(Exception):
    pass


def _mistral(system: str, user: str, *, temperature: float, max_tokens: int,
             json_mode: bool) -> str:
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise LLMError("MISTRAL_API_KEY manquant")
    # ministral-8b : 625 000 jetons/min (vs 20 000 pour small/medium) → pas de 429
    model = os.environ.get("MISTRAL_MODEL", "ministral-8b-2512")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    for attempt in range(RETRIES + 1):
        r = requests.post("https://api.mistral.ai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {key}"},
                          json=payload, timeout=TIMEOUT)
        if r.status_code < 400:
            return r.json()["choices"][0]["message"]["content"]
        # 429 = limite de débit, 5xx = indisponibilité → on réessaie
        if r.status_code in (429, 500, 502, 503) and attempt < RETRIES:
            wait = BACKOFF[min(attempt, len(BACKOFF) - 1)]
            print(f"  Mistral {r.status_code} → nouvel essai dans {wait}s "
                  f"({attempt + 1}/{RETRIES})")
            time.sleep(wait)
            continue
        raise LLMError(f"Mistral {r.status_code}: {r.text[:200]}")


BACKENDS = {"mistral": _mistral}


def chat(system: str, user: str, *, temperature: float = 0.2,
         max_tokens: int = 4000, json_mode: bool = True) -> str:
    provider = os.environ.get("LLM_PROVIDER", "mistral")
    backend = BACKENDS.get(provider)
    if backend is None:
        raise LLMError(f"Fournisseur LLM inconnu : {provider}")
    return backend(system, user, temperature=temperature,
                   max_tokens=max_tokens, json_mode=json_mode)
