"""Generates icon.ico — run once to (re)create the app icon."""
from PIL import Image, ImageDraw, ImageFilter

def draw_pokeball(size: int) -> Image.Image:
    img = ImageDraw.new = None  # unused
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    pad = max(1, size // 18)
    cx = cy = size // 2
    b   = max(1, size // 18)          # border width
    band = max(1, size // 11)         # centre stripe half-height

    BLACK  = (28,  28,  28, 255)
    RED    = (210, 35,  35, 255)
    WHITE  = (245, 245, 245, 255)

    x0, y0 = pad,        pad
    x1, y1 = size-pad-1, size-pad-1

    # ── outer black disc ──────────────────────────────────────────────────
    d.ellipse([x0, y0, x1, y1], fill=BLACK)

    # ── coloured halves ───────────────────────────────────────────────────
    ix0, iy0 = x0+b, y0+b
    ix1, iy1 = x1-b, y1-b
    d.chord([ix0, iy0, ix1, iy1], start=180, end=0,   fill=RED)
    d.chord([ix0, iy0, ix1, iy1], start=0,   end=180, fill=WHITE)

    # ── centre band ───────────────────────────────────────────────────────
    d.rectangle([ix0, cy - band, ix1, cy + band], fill=BLACK)

    # ── centre button ─────────────────────────────────────────────────────
    br = max(3, size // 7)
    d.ellipse([cx-br,   cy-br,   cx+br,   cy+br],   fill=BLACK)
    d.ellipse([cx-br+b, cy-br+b, cx+br-b, cy+br-b], fill=WHITE)

    # ── subtle anti-alias: slight blur then scale ─────────────────────────
    if size >= 64:
        img = img.filter(ImageFilter.SMOOTH)

    return img


if __name__ == "__main__":
    import os
    out = os.path.join(os.path.dirname(__file__), "icon.ico")
    base = draw_pokeball(256)
    base.save(
        out,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Saved: {out}")
