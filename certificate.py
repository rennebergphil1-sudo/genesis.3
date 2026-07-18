"""
Generiert ein Bild-Zertifikat für jeden erstellten Server - ein echtes PNG,
kein Text-Embed. Cyberpunk-Look, passend zur Genesis-Marke (Cyan/Violett,
dunkler Hintergrund, JetBrains Mono).

Läuft komplett lokal mit Pillow, kein externer Dienst nötig.
"""

import io
import os
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

WIDTH, HEIGHT = 900, 500

# Farben, identisch zur restlichen Genesis-Marke
BG = (10, 14, 20)
SURFACE = (19, 24, 34)
BORDER = (35, 42, 58)
CYAN = (45, 212, 238)
VIOLET = (155, 107, 255)
TEXT = (228, 232, 241)
TEXT_DIM = (125, 134, 153)
GOLD = (251, 191, 36)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(ASSETS_DIR, name)
    return ImageFont.truetype(path, size)


def _strip_emoji_prefix(text: str) -> str:
    """Entfernt ein führendes Emoji + Leerzeichen (z.B. '🔥 A-TIER' -> 'A-TIER'),
    da JetBrains Mono keine Emoji-Glyphen rendern kann und sonst leere Kästchen
    im Bild erscheinen würden."""
    parts = text.split(" ", 1)
    if len(parts) == 2 and not parts[0][0].isalnum():
        return parts[1]
    return text


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _draw_gradient_text(draw: ImageDraw.ImageDraw, xy, text, font, c1, c2):
    """Zeichnet Text mit einem horizontalen Farbverlauf, indem er auf eine
    Maske gerendert und mit einem Verlaufsbild kombiniert wird."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    mask = Image.new("L", (w + 4, h + 20), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.text((-bbox[0] + 2, -bbox[1] + 2), text, font=font, fill=255)

    gradient = Image.new("RGB", (w + 4, h + 20), c1)
    for x in range(w + 4):
        t = x / max(w + 3, 1)
        ImageDraw.Draw(gradient).line([(x, 0), (x, h + 20)], fill=_lerp_color(c1, c2, t))

    base = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    base.paste(gradient, (0, 0), mask)
    return base, xy


def build_certificate(
    guild_name: str,
    tier_label: str,
    level_title: str,
    level_number: int,
    counts: dict,
    critical: bool = False,
) -> io.BytesIO:
    """Baut das Zertifikat-Bild und gibt es als PNG-Bytes (BytesIO) zurück."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # Dezente Glow-Kreise im Hintergrund, ähnlich der Webseite
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([-150, -150, 350, 350], fill=(*CYAN, 28))
    glow_draw.ellipse([WIDTH - 350, HEIGHT - 250, WIDTH + 150, HEIGHT + 150], fill=(*VIOLET, 26))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img.paste(glow, (0, 0), glow)
    draw = ImageDraw.Draw(img)

    # Äußerer Rahmen (Kartenoptik)
    border_color = GOLD if critical else BORDER
    draw.rounded_rectangle([16, 16, WIDTH - 16, HEIGHT - 16], radius=18, outline=border_color, width=3)

    # Kopfzeile
    small = _font("JetBrainsMono-Regular.ttf", 16)
    draw.text((48, 44), "> genesis.certificate", font=small, fill=CYAN)

    title_font = _font("JetBrainsMono-Bold.ttf", 34)
    title_layer, pos = _draw_gradient_text(
        draw, (48, 72), "GENESIS ERSCHAFFUNG", title_font, CYAN, VIOLET
    )
    img.paste(title_layer, pos, title_layer)
    draw = ImageDraw.Draw(img)

    # Servername
    name_font = _font("JetBrainsMono-Bold.ttf", 26)
    server_label = guild_name if len(guild_name) <= 30 else guild_name[:27] + "..."
    draw.text((48, 130), server_label, font=name_font, fill=TEXT)

    # Tier-Badge
    tier_font = _font("JetBrainsMono-Bold.ttf", 22)
    badge_color = GOLD if critical else VIOLET
    clean_tier = _strip_emoji_prefix(tier_label)
    draw.rounded_rectangle([48, 178, 48 + 420, 220], radius=10, fill=SURFACE, outline=badge_color, width=2)
    draw.text((66, 188), clean_tier, font=tier_font, fill=badge_color)

    # Statistik-Boxen
    stats = [
        ("KATEGORIEN", str(counts.get("categories", 0))),
        ("KANÄLE", str(counts.get("channels", 0))),
        ("ROLLEN", str(counts.get("roles", 0))),
    ]
    box_w = 260
    stat_font_label = _font("JetBrainsMono-Regular.ttf", 14)
    stat_font_value = _font("JetBrainsMono-Bold.ttf", 40)
    for i, (label, value) in enumerate(stats):
        x = 48 + i * (box_w + 15)
        y = 250
        draw.rounded_rectangle([x, y, x + box_w, y + 110], radius=12, fill=SURFACE, outline=BORDER, width=1)
        draw.text((x + 20, y + 16), label, font=stat_font_label, fill=TEXT_DIM)
        draw.text((x + 20, y + 42), value, font=stat_font_value, fill=CYAN)

    # Level-Zeile
    level_font = _font("JetBrainsMono-Regular.ttf", 16)
    draw.text(
        (48, 385),
        f"Server-Level {level_number} — {_strip_emoji_prefix(level_title)}",
        font=level_font, fill=TEXT_DIM,
    )

    # Footer
    footer_font = _font("JetBrainsMono-Regular.ttf", 13)
    timestamp = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    draw.text((48, HEIGHT - 44), f"Genesis · Phil7442 × Developer Studio · {timestamp}", font=footer_font, fill=TEXT_DIM)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
