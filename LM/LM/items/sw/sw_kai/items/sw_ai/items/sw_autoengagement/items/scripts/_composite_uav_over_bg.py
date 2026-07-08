"""Internal helper: composite a rendered UAV PNG (with alpha) over a background image.

Behavior:
- Background keeps original quality.
- UAV can be resized smaller and positioned in top 25% with random x/y offsets.
- Blur is applied only to UAV layer.

Usage:
    python _composite_uav_over_bg.py <uav_png> <bg_path> <out_jpg> \
        <width> <height> [jpeg_quality] [seed] [uav_scale]
"""

import random
import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


def fit_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    w, h = img.size
    scale = max(width / w, height / h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - width) // 2
    top = (nh - height) // 2
    return img.crop((left, top, left + width, top + height))


def transform_uav_layer(
    uav: Image.Image, out_w: int, out_h: int, uav_scale: float
) -> tuple[Image.Image, tuple[int, int]]:
    """Resize UAV and place it in top 15% with random x/y offsets."""
    uav_scale = max(0.1, min(1.5, float(uav_scale)))
    uw, uh = uav.size
    nw = max(1, int(uw * uav_scale))
    nh = max(1, int(uh * uav_scale))
    uav = uav.resize((nw, nh), Image.Resampling.LANCZOS)

    # Horizontal variation around center.
    cx = out_w // 2 + random.randint(int(-0.18 * out_w), int(0.18 * out_w))

    # Vertical variation constrained to top 15% of the output image.
    cy_min = int(0.04 * out_h)
    cy_max = int(0.15 * out_h)
    cy = random.randint(cy_min, cy_max)

    x = cx - nw // 2
    y = cy - nh // 2

    # Keep UAV fully in-frame.
    x = max(0, min(out_w - nw, x))
    y = max(0, min(out_h - nh, y))
    return uav, (x, y)


def blur_uav_only(uav: Image.Image) -> Image.Image:
    """Apply stronger blur and slight tonal variation only to the UAV layer."""
    rgb = uav.convert("RGB")
    rgb = rgb.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.6, 1.8)))
    rgb = ImageEnhance.Brightness(rgb).enhance(random.uniform(0.94, 1.06))
    rgb = ImageEnhance.Contrast(rgb).enhance(random.uniform(0.96, 1.10))
    alpha = uav.split()[-1]
    return Image.merge("RGBA", (*rgb.split(), alpha))


def main():
    if len(sys.argv) < 6:
        print(
            "Usage: _composite_uav_over_bg.py <uav_png> <bg_path> <out_jpg> "
            "<width> <height> [quality] [seed]"
        )
        sys.exit(1)

    uav_png = sys.argv[1]
    bg_path = sys.argv[2]
    out_jpg = sys.argv[3]
    width = int(sys.argv[4])
    height = int(sys.argv[5])
    quality = int(sys.argv[6]) if len(sys.argv) > 6 else 95
    seed = int(sys.argv[7]) if len(sys.argv) > 7 else None
    uav_scale = float(sys.argv[8]) if len(sys.argv) > 8 else 0.45

    if seed is not None:
        random.seed(seed)

    bg = Image.open(bg_path).convert("RGB")
    bg = fit_cover(bg, width, height)

    uav = Image.open(uav_png).convert("RGBA")
    if uav.size != (width, height):
        uav = uav.resize((width, height), Image.Resampling.LANCZOS)

    uav, pos = transform_uav_layer(uav, width, height, uav_scale)
    uav = blur_uav_only(uav)

    canvas = bg.convert("RGBA")
    canvas.alpha_composite(uav, pos)
    result = canvas.convert("RGB")

    Path(out_jpg).parent.mkdir(parents=True, exist_ok=True)
    result.save(out_jpg, format="JPEG", quality=quality)


if __name__ == "__main__":
    main()
