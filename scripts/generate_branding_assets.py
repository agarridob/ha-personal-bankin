#!/usr/bin/env python3
"""Generate branding assets from the Personal Bankin source logo.

Derives every icon/logo variant from a single source image
(custom_components/finance_dashboard/brand/logo-source.png):

- icon.png / logo.png            — dark artwork, transparent background
                                   (for light surfaces)
- dark_icon.png / dark_logo.png  — artwork recolored light grey
                                   (for dark surfaces)
- companion add-on icon/logo     — copies of the same variants
- frontend/personal-bankin-logo.png — used by the sidebar panel UI

The source has a near-white solid background; transparency is computed
from luminance so anti-aliased edges stay smooth.

Requires Pillow:  .venv/bin/python scripts/generate_branding_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "custom_components" / "finance_dashboard" / "brand"
FRONTEND_DIR = ROOT / "custom_components" / "finance_dashboard" / "frontend"
COMPANION_DIR = ROOT / "finance_dashboard_companion"

SOURCE = BRAND_DIR / "logo-source.png"
SIZE = 256

# Light-grey artwork color for dark-theme variants
DARK_THEME_FG = (230, 230, 235)


def _to_transparent(img: Image.Image) -> Image.Image:
    """Convert dark-on-light artwork to dark-on-transparent.

    Alpha is derived from luminance: background (lightest) → 0,
    darkest artwork → 255, edges interpolate linearly.
    """
    gray = img.convert("L")
    px = gray.load()
    bg_lum = max(px[0, 0], px[img.width - 1, 0], px[0, img.height - 1])
    fg_lum = min(gray.getextrema()[0], bg_lum - 1)
    span = bg_lum - fg_lum

    rgba = img.convert("RGBA")
    out = rgba.load()
    for y in range(img.height):
        for x in range(img.width):
            alpha = round(255 * (bg_lum - px[x, y]) / span)
            r, g, b, _ = out[x, y]
            out[x, y] = (r, g, b, max(0, min(255, alpha)))
    return rgba


def _recolor(img: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    """Replace artwork color, keeping the alpha channel."""
    solid = Image.new("RGBA", img.size, (*color, 255))
    solid.putalpha(img.getchannel("A"))
    return solid


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source logo not found: {SOURCE}")

    src = Image.open(SOURCE)
    transparent = _to_transparent(src).resize((SIZE, SIZE), Image.LANCZOS)
    dark_variant = _recolor(transparent, DARK_THEME_FG)

    targets = {
        BRAND_DIR / "icon.png": transparent,
        BRAND_DIR / "logo.png": transparent,
        BRAND_DIR / "dark_icon.png": dark_variant,
        BRAND_DIR / "dark_logo.png": dark_variant,
        COMPANION_DIR / "icon.png": transparent,
        COMPANION_DIR / "logo.png": transparent,
        COMPANION_DIR / "dark_icon.png": dark_variant,
        COMPANION_DIR / "dark_logo.png": dark_variant,
        FRONTEND_DIR / "personal-bankin-logo.png": transparent,
    }
    for path, image in targets.items():
        image.save(path, "PNG")
        print(f"  WROTE: {path.relative_to(ROOT)}")

    print(f"\n{len(targets)} asset(s) generated from {SOURCE.name}.")
    print("Remember to run scripts/sync_addon_payload.py afterwards.")


if __name__ == "__main__":
    main()
