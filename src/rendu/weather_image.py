"""Génère le bloc météo en PNG (charte noir & doré), qualité widget (EF-17g).

Rendu à 2x puis réduit (anticrénelage). Icônes dessinées en primitives Pillow
(pas d'emoji couleur, non portables). Aucune police externe indispensable :
on s'appuie sur DejaVu, présent partout.
"""
from __future__ import annotations

import datetime as dt
import math
import os

from PIL import Image, ImageDraw, ImageFont

from src.collecte.meteo import icon_for, label_for

# --- Palette (identique à la maquette validée) ---
INK = (13, 13, 15)
PANEL = (22, 22, 27)
PANEL2 = (28, 28, 34)
LINE = (44, 44, 52)
GOLD = (201, 162, 75)
GOLD_HI = (231, 205, 134)
GOLD_DEEP = (143, 111, 44)
PAPER = (241, 237, 228)
MUTED = (164, 159, 147)
STEEL = (140, 178, 214)   # précipitations
CRIT = (207, 107, 92)
SUN = (255, 200, 51)      # vrai jaune soleil
SUN_EDGE = (243, 176, 26)
CLOUD = (214, 219, 228)   # nuage clair (blanc cassé bleuté)
CLOUD_SH = (176, 184, 199)  # ombre basse du nuage

SS = 2  # supersampling
W, H = 760, 468

FONT_DIR_DEJAVU = "/usr/share/fonts/truetype/dejavu"


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR_DEJAVU, name), size * SS)


def _px(v: int) -> int:
    return v * SS


# ---------------------------------------------------------------- icônes ----
# Toutes les icônes tiennent dans une boîte de côté ~= `size`, centrée en
# (cx, cy). Les rayons du soleil sont proportionnels au rayon pour NE JAMAIS
# déborder au-delà de la boîte (donc jamais sur le texte au-dessus).

def _sun(d, cx, cy, r, col=SUN, rays=True):
    if rays:
        lw = max(2, int(r * 0.30))
        inner = r + max(2 * SS, int(r * 0.30))
        outer = r + max(5 * SS, int(r * 0.75))
        for k in range(8):
            a = k * math.pi / 4
            x1, y1 = cx + math.cos(a) * inner, cy + math.sin(a) * inner
            x2, y2 = cx + math.cos(a) * outer, cy + math.sin(a) * outer
            d.line([(x1, y1), (x2, y2)], fill=col, width=lw)
            d.ellipse([x2 - lw / 2, y2 - lw / 2, x2 + lw / 2, y2 + lw / 2], fill=col)  # bout arrondi
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col, outline=SUN_EDGE, width=max(1, SS))


def _moon(d, cx, cy, r, col=(245, 240, 220)):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    off = int(r * 0.65)
    d.ellipse([cx - r + off, cy - r - off // 2, cx + r + off, cy + r - off // 2], fill=INK)


def _cloud(d, cx, cy, w, fill=CLOUD):
    """Nuage tout en rondeurs (silhouette pleine, sans contour dur)."""
    r = max(4 * SS, w // 4)
    # petite ombre basse pour le relief
    d.ellipse([cx - w // 2, cy + r // 2, cx + w // 2, cy + r + r // 3], fill=CLOUD_SH)
    bumps = [
        (cx - w // 2, cy - r // 3, cx - w // 2 + int(r * 1.9), cy + r + r // 3),
        (cx - int(r * 1.2), cy - int(r * 1.6), cx + int(r * 1.2), cy + r),
        (cx + w // 2 - int(r * 1.9), cy - r // 3, cx + w // 2, cy + r + r // 3),
    ]
    d.rectangle([cx - w // 2 + r // 2, cy, cx + w // 2 - r // 2, cy + r + r // 4], fill=fill)
    for b in bumps:
        d.ellipse(b, fill=fill)


def _drops(d, cx, cy, n=3, col=STEEL):
    span = (n - 1) * 7 * SS
    for k in range(n):
        x = cx - span // 2 + k * 7 * SS
        d.ellipse([x - 2 * SS, cy, x + 2 * SS, cy + 7 * SS], fill=col)          # goutte
        d.polygon([(x - 2 * SS, cy + 2 * SS), (x + 2 * SS, cy + 2 * SS), (x, cy - 3 * SS)], fill=col)


def _flakes(d, cx, cy, n=3, col=(245, 248, 252)):
    span = (n - 1) * 8 * SS
    for k in range(n):
        x = cx - span // 2 + k * 8 * SS
        d.ellipse([x - 2 * SS, cy - 2 * SS, x + 2 * SS, cy + 2 * SS], fill=col)


def _bolt(d, cx, cy, col=SUN):
    s = 5 * SS
    pts = [(cx, cy - 2 * s), (cx - s, cy + s), (cx, cy + s),
           (cx - s // 2, cy + 3 * s), (cx + s, cy - s // 2), (cx, cy - s // 2)]
    d.polygon(pts, fill=col)


def draw_icon(d, key, cx, cy, size, is_night=False):
    """Dessine une icône météo centrée en (cx, cy), gabarit ~ size px (échelle SS déjà appliquée)."""
    r = size // 3
    if key in ("clear", "mostly_clear"):
        (_moon if is_night else _sun)(d, cx, cy, int(r * 0.9))
    elif key == "partly":
        off = int(r * 0.75)
        if is_night:
            _moon(d, cx - off, cy - off, int(r * 0.75))
        else:
            _sun(d, cx - off, cy - off, int(r * 0.68))
        _cloud(d, cx + 3 * SS, cy + 5 * SS, size - 8 * SS)
    elif key == "overcast":
        _cloud(d, cx, cy, size - 6 * SS)
    elif key == "fog":
        _cloud(d, cx, cy - 5 * SS, size - 10 * SS)
        lw = max(2, 2 * SS)
        for k in range(3):
            yy = cy + 7 * SS + k * 5 * SS
            d.line([(cx - size // 4, yy), (cx + size // 4, yy)], fill=CLOUD_SH, width=lw)
    elif key in ("rain", "drizzle"):
        _cloud(d, cx, cy - 6 * SS, size - 8 * SS)
        _drops(d, cx, cy + 9 * SS, n=3 if key == "rain" else 2)
    elif key == "snow":
        _cloud(d, cx, cy - 6 * SS, size - 8 * SS)
        _flakes(d, cx, cy + 10 * SS, n=3)
    elif key == "thunder":
        _cloud(d, cx, cy - 6 * SS, size - 8 * SS)
        _bolt(d, cx, cy + 10 * SS)
    else:
        _cloud(d, cx, cy, size - 6 * SS)


# ---------------------------------------------------------------- texte ----
def _text(d, xy, s, font, fill, anchor="la", tracking=0):
    if tracking and len(s) > 1:
        x, y = xy
        for ch in s:
            d.text((x, y), ch, font=font, fill=fill, anchor="l" + anchor[1])
            x += d.textlength(ch, font=font) + tracking * SS
        return
    d.text(xy, s, font=font, fill=fill, anchor=anchor)


# ---------------------------------------------------------------- rendu ----
def render(data: dict, out_path: str, place: str = "Loulans-Verchamp",
           vigilance: dict | None = None, date: dt.date | None = None) -> str:
    date = date or dt.date.today()
    cur, steps, days = data["current"], data["steps"], data["days"]

    img = Image.new("RGB", (_px(W), _px(H)), INK)
    d = ImageDraw.Draw(img)

    f_eyebrow = _font("DejaVuSans-Bold.ttf", 11)
    f_place = _font("DejaVuSerif-Bold.ttf", 30)
    f_date = _font("DejaVuSans.ttf", 13)
    f_cond = _font("DejaVuSerif.ttf", 15)
    f_temp = _font("DejaVuSerif-Bold.ttf", 64)
    f_deg = _font("DejaVuSans.ttf", 15)
    f_sec = _font("DejaVuSans-Bold.ttf", 11)
    f_hh = _font("DejaVuSans.ttf", 12)
    f_val = _font("DejaVuSans-Bold.ttf", 16)
    f_small = _font("DejaVuSans.ttf", 11)
    f_day = _font("DejaVuSans-Bold.ttf", 12)

    # cadre
    d.rectangle([1 * SS, 1 * SS, _px(W) - 2 * SS, _px(H) - 2 * SS], outline=GOLD_DEEP, width=SS)

    M = _px(30)
    # --- en-tête ---
    _text(d, (M, _px(26)), "MÉTÉO — AUJOURD'HUI", f_eyebrow, GOLD, tracking=3)
    _text(d, (M, _px(42)), place, f_place, PAPER)
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    date_str = f"{jours[date.weekday()]} {date.day} {mois[date.month - 1]} {date.year}"
    _text(d, (M, _px(84)), date_str.capitalize(), f_date, MUTED)
    _text(d, (M, _px(104)), label_for(cur["code"]), f_cond, MUTED)

    # température + icône (à droite)
    right = _px(W) - M
    temp_str = f"{cur['temp']}°"
    _text(d, (right, _px(52)), temp_str, f_temp, GOLD_HI, anchor="ra")
    tw = d.textlength(temp_str, font=f_temp)
    draw_icon(d, icon_for(cur["code"]), int(right - tw - _px(48)), _px(74),
              _px(56), is_night=cur["is_night"])
    _text(d, (right, _px(120)),
          f"Ressenti {cur['feels']}°   ·   {cur['tmin']}° / {cur['tmax']}°   ·   pluie {cur['precip_prob']} %",
          f_small, MUTED, anchor="ra")

    y = _px(150)
    # --- vigilance (si active) ---
    if vigilance and vigilance.get("level", "vert") != "vert":
        colmap = {"jaune": GOLD, "orange": (216, 140, 60), "rouge": CRIT}
        c = colmap.get(vigilance["level"], GOLD)
        d.rounded_rectangle([M, y, right, y + _px(30)], radius=_px(6),
                            fill=PANEL2, outline=c, width=SS)
        d.ellipse([M + _px(12), y + _px(11), M + _px(20), y + _px(19)], fill=c)
        _text(d, (M + _px(30), y + _px(8)),
              f"Vigilance {vigilance['level']} — Haute-Saône : {vigilance.get('label','')}",
              f_val, PAPER)
        y += _px(44)

    def hr(yy):
        d.line([(M, yy), (right, yy)], fill=LINE, width=SS)

    hr(y)
    y += _px(14)
    _text(d, (M, y), "AUJOURD'HUI — PAR TRANCHES DE 2 H", f_sec, GOLD, tracking=2)
    y += _px(24)

    # --- tranches 2 h ---
    n = len(steps)
    colw = (right - M) / n
    row_top = y
    for i, s in enumerate(steps):
        cx = int(M + colw * i + colw / 2)
        if i > 0:
            d.line([(int(M + colw * i), row_top + _px(2)),
                    (int(M + colw * i), row_top + _px(104))], fill=LINE, width=1)
        _text(d, (cx, row_top), s["hh"], f_hh, MUTED, anchor="ma")
        # icône bien en dessous du libellé horaire (aucun recouvrement)
        draw_icon(d, icon_for(s["code"]), cx, row_top + _px(42),
                  _px(26), is_night=s["is_night"])
        _text(d, (cx, row_top + _px(62)), f"{s['temp']}°", f_val, GOLD_HI, anchor="ma")
        pr = f"{s['precip']:.1f}".rstrip("0").rstrip(".")
        _text(d, (cx, row_top + _px(82)),
              (f"{pr} mm" if s["precip"] > 0 else "—"), f_small,
              STEEL if s["precip"] > 0 else MUTED, anchor="ma")
        _text(d, (cx, row_top + _px(96)), f"{s['wind']} km/h", f_small, MUTED, anchor="ma")

    y = row_top + _px(120)
    hr(y)
    y += _px(14)
    _text(d, (M, y), "PROCHAINS JOURS", f_sec, GOLD, tracking=2)
    y += _px(24)

    # --- J+1 .. J+6 ---
    nd = len(days)
    colw = (right - M) / nd
    for i, dd in enumerate(days):
        cx = int(M + colw * i + colw / 2)
        if i > 0:
            d.line([(int(M + colw * i), y), (int(M + colw * i), y + _px(78))], fill=LINE, width=1)
        _text(d, (cx, y), dd["name"], f_day, GOLD, anchor="ma")
        draw_icon(d, icon_for(dd["code"]), cx, y + _px(40), _px(26))
        _text(d, (cx, y + _px(60)), f"{dd['tmax']}°", f_val, PAPER, anchor="ma")
        _text(d, (cx + d.textlength(f"{dd['tmax']}°", font=f_val) // 2 + _px(6), y + _px(62)),
              f"{dd['tmin']}°", f_small, MUTED, anchor="la")

    # --- pied ---
    src = data.get("source", "Open-Meteo")
    _text(d, (M, _px(H) - _px(22)),
          f"Source prévision : {src}  ·  Vigilance : Météo-France",
          f_small, MUTED)

    img = img.resize((W, H), Image.LANCZOS)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG")
    return out_path
