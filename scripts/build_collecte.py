"""Assemble la collecte d'actualités → data/collected.json.

- Lit les flux (config/sources_rss.yml), agrège et déduplique (src/collecte/rss).
- Écarte les sujets déjà vus sur 7 jours (mémoire anti-répétition, EF-11).
- Écrit data/collected.json (entrée du futur maillon rédaction).

Usage : python -m scripts.build_collecte
"""
from __future__ import annotations

import datetime as dt
import json
import os

import yaml

from src.collecte import rss, memoire

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY = os.path.join(ROOT, "data", "history.json")
OUT = os.path.join(ROOT, "data", "collected.json")


def main() -> int:
    with open(os.path.join(ROOT, "config", "sources_rss.yml"), encoding="utf-8") as f:
        feeds = yaml.safe_load(f)

    result = rss.collect(feeds)

    # Filtre anti-répétition (ne pas reproposer un sujet déjà traité récemment)
    history = memoire.prune(memoire.load(HISTORY))
    total_before = total_after = 0
    for rubrique, items in result["rubriques"].items():
        total_before += len(items)
        result["rubriques"][rubrique] = memoire.filter_new(items, history)
        total_after += len(result["rubriques"][rubrique])

    result["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✓ {OUT}")
    print(f"  candidats : {total_before} collectés → {total_after} après anti-répétition")
    for rubrique, items in result["rubriques"].items():
        print(f"  · {rubrique:42s} {len(items):2d} sujets")
    if result["failures"]:
        print(f"  ⚠ {len(result['failures'])} flux injoignables :")
        for fa in result["failures"]:
            print(f"      - [{fa['rubrique']}] {fa['feed']}  ({fa['error']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
