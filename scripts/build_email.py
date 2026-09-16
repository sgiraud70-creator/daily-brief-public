"""Rendu de l'e-mail complet « Le Brief » (charte noir & doré).

- Charge le contenu (brief.json ou l'exemple), le texte alternatif météo.
- Rend le gabarit Jinja2, inline les styles avec premailer (EF-21).
- Écrit public/email.html (production : image + MP3 référencés par URL hébergée).

Usage :
    python -m scripts.build_email                 # exemple → public/email.html
    python -m scripts.build_email --brief data/brief.json
    python -m scripts.build_email --preview /tmp/preview.html   # image en data URI
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os

from jinja2 import Environment, FileSystemLoader, select_autoescape
from premailer import Premailer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_MAIN = "https://raw.githubusercontent.com/sgiraud70-creator/daily-brief-public/main/public"
DEFAULT_WEATHER_URL = f"{RAW_MAIN}/weather.png"
DEFAULT_MP3_URL = f"{RAW_MAIN}/brief.mp3"


def read_alt() -> str:
    p = os.path.join(ROOT, "public", "weather_alt.txt")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    return "Bloc météo du jour pour Loulans-Verchamp."


def render(brief: dict, weather_url: str, mp3_url: str) -> str:
    env = Environment(
        loader=FileSystemLoader(os.path.join(ROOT, "templates")),
        autoescape=select_autoescape(["html", "j2"]),
    )
    # URL secrète du bouton « Régénérer » (service serverless, cf. serverless/).
    # Absente → le bouton n'apparaît pas (dégradation propre).
    regen_url = os.environ.get("REGEN_URL", "").strip()
    html = env.get_template("email.html.j2").render(
        weather_url=weather_url, mp3_url=mp3_url, weather_alt=read_alt(),
        regen_url=regen_url, **brief)
    # inline des styles (EF-21) ; on garde @media pour le mobile
    inliner = Premailer(html, keep_style_tags=True, remove_classes=False,
                        cssutils_logging_level=logging.CRITICAL)
    return inliner.transform()


def data_uri_png(path: str) -> str:
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default=os.path.join(ROOT, "data", "brief.sample.json"))
    ap.add_argument("--weather-url", default=DEFAULT_WEATHER_URL)
    ap.add_argument("--mp3-url", default=DEFAULT_MP3_URL)
    ap.add_argument("--out", default=os.path.join(ROOT, "public", "email.html"))
    ap.add_argument("--preview", metavar="PATH",
                    help="écrit un aperçu avec l'image météo en data URI (pour navigateur/artefact)")
    args = ap.parse_args()

    with open(args.brief, encoding="utf-8") as f:
        brief = json.load(f)

    html = render(brief, args.weather_url, args.mp3_url)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ {args.out}  ({len(html) // 1024} Ko)")

    if args.preview:
        png = os.path.join(ROOT, "public", "weather.png")
        preview = render(brief, data_uri_png(png), args.mp3_url)
        with open(args.preview, "w", encoding="utf-8") as f:
            f.write(preview)
        print(f"✓ aperçu (image intégrée) : {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
