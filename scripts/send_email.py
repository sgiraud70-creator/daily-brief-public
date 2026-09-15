"""Envoie l'e-mail du jour (public/email.html) via Gmail SMTP.

Nécessite les secrets GMAIL_USER, GMAIL_APP_PASSWORD, MAIL_TO. En leur absence,
le script ne fait rien (sortie 0) : pratique pour les tests sans envoi réel.

Usage : python -m scripts.send_email
"""
from __future__ import annotations

import json
import os

from src.envoi import mailer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMAIL = os.path.join(ROOT, "public", "email.html")
BRIEF = os.path.join(ROOT, "data", "brief.json")


def main() -> int:
    user = os.environ.get("GMAIL_USER")
    pwd = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("MAIL_TO") or user
    if not (user and pwd and to):
        print("→ secrets Gmail absents (GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO) — envoi ignoré.")
        return 0
    if not os.path.exists(EMAIL):
        print("⚠ public/email.html absent — rien à envoyer.")
        return 1

    with open(EMAIL, encoding="utf-8") as f:
        html = f.read()
    date_str = "aujourd'hui"
    if os.path.exists(BRIEF):
        try:
            date_str = json.load(open(BRIEF, encoding="utf-8")).get("date_str", date_str)
        except Exception:
            pass

    mailer.send_html(f"Le Brief — {date_str}", html, user=user, password=pwd, to=to)
    print(f"✓ e-mail envoyé à {to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
