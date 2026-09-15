"""Rédaction du brief à partir des seuls éléments collectés (EF-15/16/18).

Le LLM SÉLECTIONNE et RÉSUME — il ne cherche rien et n'invente rien. Les URL de
sources proviennent exclusivement des items fournis.
"""
from __future__ import annotations

import json
import re

from src.redaction import llm

MAX_ITEMS_IN = 8        # items fournis au modèle par rubrique (limite les jetons)
MAX_SUJETS = 7          # plafond de sélection (A8)
MAX_BULLETS = 5

SYSTEM = """Tu es le rédacteur d'un brief d'actualité quotidien en français, sérieux et factuel.

RÈGLES ABSOLUES :
- Tu travailles UNIQUEMENT à partir des éléments fournis (titre, source, url, résumé). Tu n'ajoutes JAMAIS d'information issue de tes connaissances. Tu n'inventes JAMAIS de fait ni d'URL.
- Chaque source que tu cites doit être l'une des url réellement fournies, telle quelle.
- Pour chaque rubrique, sélectionne AU PLUS 7 sujets, les plus importants et les plus variés. Écarte les doublons et les sujets déjà traités récemment (liste « deja_traites »).
- Pour chaque sujet : un titre court et informatif, puis 4 à 5 tirets factuels (ce qui s'est passé, qui est concerné, les conséquences). Jamais de paragraphe compact. Reste sobre, pas de sensationnalisme.
- Si tu n'es pas sûr d'un fait, tu l'écartes.
- Si une rubrique ne contient aucun élément exploitable, renvoie-la avec "sujets": [] et "note": "source indisponible ce matin" (une ligne, sans développer).

SORTIE : un objet JSON valide, en français, SANS commentaire ni markdown, respectant exactement ce schéma :
{"rubriques":[{"label": "<identique à l'entrée>", "sujets":[{"title":"...", "bullets":["...","..."], "sources":[{"name":"<source fournie>","url":"<url fournie>"}]}], "note":"<optionnel>"}]}
Conserve l'ordre et les libellés des rubriques fournis."""


def _trim_items(items: list[dict]) -> list[dict]:
    out = []
    for it in items[:MAX_ITEMS_IN]:
        out.append({
            "title": it.get("title", ""),
            "source": it.get("source", ""),
            "url": it.get("url", ""),
            "resume": (it.get("summary") or "")[:150],
        })
    return out


def build_user_payload(collected: dict, deja_traites: list[str]) -> str:
    rubriques = [{"label": label, "items": _trim_items(items)}
                 for label, items in collected["rubriques"].items()]
    return json.dumps({"rubriques": rubriques, "deja_traites": deja_traites[:60]},
                      ensure_ascii=False)


def _valid_urls(collected: dict) -> set[str]:
    urls = set()
    for items in collected["rubriques"].values():
        for it in items:
            if it.get("url"):
                urls.add(it["url"])
    return urls


def _loads_lenient(raw: str) -> dict:
    """Parse le JSON ; si la sortie est tronquée, tente de rééquilibrer la fin."""
    start = raw.find("{")
    s = raw[start:] if start >= 0 else raw
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        s = s[:s.rfind("}") + 1] if "}" in s else s
        s += "]" * max(0, s.count("[") - s.count("]"))
        s += "}" * max(0, s.count("{") - s.count("}"))
        return json.loads(s)


def _coerce(raw: str, allowed_urls: set[str]) -> list[dict]:
    """Parse la sortie du modèle, applique les plafonds et retire toute url inventée."""
    data = _loads_lenient(raw)
    rubriques = []
    for r in data.get("rubriques", []):
        sujets = []
        for s in (r.get("sujets") or [])[:MAX_SUJETS]:
            bullets = [b.strip() for b in (s.get("bullets") or []) if b.strip()][:MAX_BULLETS]
            sources = [src for src in (s.get("sources") or [])
                       if src.get("url") in allowed_urls]  # anti-URL inventée (EF-18)
            if not bullets:
                continue
            sujets.append({"title": s.get("title", "").strip(),
                           "bullets": bullets, "sources": sources})
        entry = {"label": r.get("label", ""), "sujets": sujets}
        if not sujets and r.get("note"):
            entry["note"] = str(r["note"])[:120]
        rubriques.append(entry)
    return rubriques


def rediger(collected: dict, deja_traites: list[str] | None = None) -> list[dict]:
    user = build_user_payload(collected, deja_traites or [])
    raw = llm.chat(SYSTEM, user, temperature=0.2, max_tokens=8000, json_mode=True)
    return _coerce(raw, _valid_urls(collected))
