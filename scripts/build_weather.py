"""Assemble le bloc météo : récupère les données, génère le PNG + le repli HTML.

Usage :
    python -m scripts.build_weather            # tente Open-Meteo, repli exemple
    python -m scripts.build_weather --sample   # force les données d'exemple

Sorties :
    public/weather.png         (image, charte noir & doré)
    public/weather_table.html  (repli tableau, styles inline)
    public/weather_alt.txt     (texte alternatif du PNG)
"""
from __future__ import annotations

import argparse
import os
import sys

import yaml

from src.collecte import meteo
from src.rendu import weather_image, weather_table

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_lieu() -> dict:
    with open(os.path.join(ROOT, "config", "lieu.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="forcer les données d'exemple")
    args = ap.parse_args()

    lieu = load_lieu()
    place = lieu["commune"]

    if args.sample:
        data = meteo.sample_data()
        print("→ données d'EXEMPLE (option --sample)")
    else:
        try:
            data = meteo.get_weather(lieu["latitude"], lieu["longitude"], lieu["timezone"])
            print(f"→ données Open-Meteo pour {place}")
        except Exception as e:  # réseau externe indisponible (ex. dev)
            data = meteo.sample_data()
            print(f"⚠ Open-Meteo injoignable ({e!r}) → repli sur données d'exemple")

    vig = meteo.get_vigilance(lieu["departement"], os.environ.get("METEOFRANCE_APP_ID"))

    out_dir = os.path.join(ROOT, "public")
    png = weather_image.render(data, os.path.join(out_dir, "weather.png"),
                               place=place, vigilance=vig)
    with open(os.path.join(out_dir, "weather_table.html"), "w", encoding="utf-8") as f:
        f.write(weather_table.render_html(data, place, vig))
    alt = weather_table.alt_text(data, place)
    with open(os.path.join(out_dir, "weather_alt.txt"), "w", encoding="utf-8") as f:
        f.write(alt)

    print(f"✓ {png}")
    print(f"✓ repli HTML + texte alternatif")
    print(f"  alt : {alt[:90]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
