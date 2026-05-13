"""Render the Indexer brand mark to PNG + Windows ICO.

Uses Pillow directly (no SVG dependency) — keeps the brand authoritative in
code rather than in a binary file. Run before packaging:

    pip install pillow
    python scripts/make_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parents[1] / "src" / "indexer" / "assets"
NAVY = (31, 58, 95)
GOLD = (183, 121, 31)
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 256.0

    def rect(x, y, w, h, fill, radius=0):
        d.rounded_rectangle(
            (x * s, y * s, (x + w) * s, (y + h) * s),
            radius=radius * s, fill=fill,
        )

    # Background tile
    rect(0, 0, 256, 256, NAVY, radius=48)

    # Stacked pages
    rect(64, 56, 112, 144, (248, 250, 252, 90), radius=6)
    rect(76, 68, 112, 144, (248, 250, 252, 153), radius=6)
    rect(88, 80, 112, 144, WHITE, radius=6)

    # Index lines on top page
    rect(104, 104, 80, 6, NAVY, radius=3)
    rect(104, 124, 64, 4, MUTED, radius=2)
    rect(104, 138, 72, 4, MUTED, radius=2)
    rect(104, 152, 56, 4, MUTED, radius=2)
    rect(104, 166, 68, 4, MUTED, radius=2)

    # Gold bookmark
    pts = [(180 * s, 56 * s), (208 * s, 56 * s), (208 * s, 112 * s),
           (194 * s, 100 * s), (180 * s, 112 * s)]
    d.polygon(pts, fill=GOLD)
    return img


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    layers = [render(s) for s in sizes]
    # Save flagship PNG (256)
    layers[-1].save(ASSETS / "icon.png", format="PNG")
    # Save multi-resolution ICO for Windows
    layers[-1].save(
        ASSETS / "icon.ico", format="ICO",
        sizes=[(s, s) for s in sizes],
    )
    print(f"Wrote icon.png + icon.ico to {ASSETS}")


if __name__ == "__main__":
    main()
