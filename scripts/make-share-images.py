"""Generate the PNG icons and the link-preview image (assets/share.png).

Run after changing the brand:  python scripts/make-share-images.py
Needs Pillow and the Segoe UI fonts that ship with Windows.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "assets"
BLUE, ORANGE, PEACH = "#2a78d6", "#eb6834", "#ffd4c2"
INK, MUTED, SURFACE, SOFT = "#0b0b0b", "#52514e", "#fcfcfb", "#f0efeb"
FONTS = Path("C:/Windows/Fonts")


def font(bold, size):
    return ImageFont.truetype(str(FONTS / ("segoeuib.ttf" if bold else "segoeui.ttf")), size)


def draw_icon(d, x, y, s):
    """Same shapes as assets/icon.svg (64-unit grid), at (x, y) with size s."""
    k = s / 64
    p = lambda pts: [(x + px * k, y + py * k) for px, py in pts]
    d.rounded_rectangle([x, y, x + s, y + s], radius=14 * k, fill=BLUE)
    d.polygon(p([(22, 11), (33, 25), (26, 25), (26, 52), (18, 52), (18, 25), (11, 25)]), fill="#fff")
    d.polygon(p([(42, 53), (31, 39), (38, 39), (38, 12), (46, 12), (46, 39), (53, 39)]), fill=PEACH)


def icon(size, name):
    # Draw large and downsample for smooth edges.
    big = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    draw_icon(ImageDraw.Draw(big), 0, 0, size * 4)
    big.resize((size, size), Image.LANCZOS).save(ASSETS / name)


def share_image():
    W, H, S = 1200, 630, 2
    img = Image.new("RGB", (W * S, H * S), SURFACE)
    d = ImageDraw.Draw(img)
    m = 80 * S

    draw_icon(d, m, 78 * S, 76 * S)
    d.text((m + 100 * S, 82 * S), "Sri Lanka Bank Rates", font=font(True, 58 * S), fill=INK)
    d.text((m, 200 * S), "Compare today's exchange rates", font=font(True, 40 * S), fill=INK)
    d.text((m, 252 * S), "from 11 banks, side by side with the Central Bank.", font=font(False, 32 * S), fill=MUTED)

    # Currency chips
    cx = m
    for code in ("USD", "GBP", "AUD", "SGD"):
        w = d.textlength(code, font=font(True, 30 * S)) + 44 * S
        d.rounded_rectangle([cx, 330 * S, cx + w, 386 * S], radius=12 * S, fill="#e6f0fc")
        d.text((cx + 22 * S, 336 * S), code, font=font(True, 30 * S), fill=BLUE)
        cx += w + 14 * S
    d.text((cx + 6 * S, 338 * S), "to LKR", font=font(False, 30 * S), fill=MUTED)

    # Illustrative buy-sell range rows (shape only, no real numbers)
    rows = [(0.10, 0.80), (0.16, 0.76), (0.06, 0.86), (0.20, 0.90), (0.12, 0.70)]
    x0, x1, y = m, W * S - m, 440 * S
    for a, b in rows:
        ya = y + 6 * S
        d.rounded_rectangle([x0 + a * (x1 - x0), ya - 4 * S, x0 + b * (x1 - x0), ya + 4 * S], radius=4 * S, fill="#e2e1dc")
        for t, c in ((a, BLUE), (b, ORANGE)):
            cx_ = x0 + t * (x1 - x0)
            d.ellipse([cx_ - 11 * S, ya - 11 * S, cx_ + 11 * S, ya + 11 * S], fill=c, outline=SURFACE, width=4 * S)
        y += 30 * S

    d.rectangle([0, (H - 8) * S, W * S, H * S], fill=BLUE)
    img.resize((W, H), Image.LANCZOS).save(ASSETS / "share.png", optimize=True)


if __name__ == "__main__":
    icon(32, "icon-32.png")
    icon(180, "icon-180.png")
    share_image()
    print("wrote icon-32.png, icon-180.png, share.png")
