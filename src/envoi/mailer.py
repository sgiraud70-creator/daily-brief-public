"""Envoi de l'e-mail via SMTP Gmail (mot de passe d'application).

Les identifiants viennent de secrets (jamais en clair) : GMAIL_USER,
GMAIL_APP_PASSWORD, MAIL_TO. Connexion chiffrée SSL sur le port 465.
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate


def send_html(subject: str, html: str, *, user: str, password: str, to: str) -> None:
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("Le Brief", user))
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(user, password)
        s.sendmail(user, [to], msg.as_string())
