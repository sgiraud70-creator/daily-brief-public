"""Couche d'abstraction LLM (parade R-01 / ENF-07).

Un seul point d'entrée `chat()` ; le fournisseur est choisi par la variable
d'environnement LLM_PROVIDER (défaut : mistral). Pour changer de fournisseur,
il suffit d'ajouter une fonction `_backend()` et une entrée dans BACKENDS —
le reste du code (rédacteur) n'a rien à changer.
"""
from __future__ import annotations

import os

import requests

TIMEOUT = 90


class LLMError(Exception):
    pass


def _mistral(system: str, user: str, *, temperature: float, max_tokens: int,
             json_mode: bool) -> str:
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise LLMError("MISTRAL_API_KEY manquant")
    model = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    r = requests.post("https://api.mistral.ai/v1/chat/completions",
                      headers={"Authorization": f"Bearer {key}"},
                      json=payload, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise LLMError(f"Mistral {r.status_code}: {r.text[:200]}")
    return r.json()["choices"][0]["message"]["content"]


BACKENDS = {"mistral": _mistral}


def chat(system: str, user: str, *, temperature: float = 0.2,
         max_tokens: int = 4000, json_mode: bool = True) -> str:
    provider = os.environ.get("LLM_PROVIDER", "mistral")
    backend = BACKENDS.get(provider)
    if backend is None:
        raise LLMError(f"Fournisseur LLM inconnu : {provider}")
    return backend(system, user, temperature=temperature,
                   max_tokens=max_tokens, json_mode=json_mode)
