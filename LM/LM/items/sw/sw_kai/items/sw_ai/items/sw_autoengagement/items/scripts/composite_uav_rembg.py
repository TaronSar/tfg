"""Composite rendered UAV images onto random real-world backgrounds using rembg.

Usage examples:
  python scripts/composite_uav_rembg.py --test
  python scripts/composite_uav_rembg.py --count 100 --random_uav
"""

import argparse
import io
import random
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
from rembg import new_session, remove


def collect_images(root: Path):
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts]


def fit_cover(img: Image.Image, size: int) -> Image.Image:
    """Resize/crop image to a square cover of `size` pixels."""
    w, h = img.size
    scale = max(size / w, size / h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - size) // 2
    top = (nh - size) // 2
    return img.crop((left, top, left + size, top + size))


def rgba_from_rembg(path: Path, session):
    """Run rembg and return RGBA PIL image."""
    with open(path, "rb") as f:
        blob = f.read()
    out = remove(blob, session=session)
    return Image.open(io.BytesIO(out)).convert("RGBA")


def composite_one(
    uav_path: Path, bg_path: Path, out_dir: Path, session, out_size=640, uav_scale=0.42, jitter=0.15
):
    bg = Image.open(bg_path).convert("RGB")
    bg = fit_cover(bg, out_size)

    uav_rgba = rgba_from_rembg(uav_path, session)

    # Tighten alpha edges slightly and smooth for cleaner cutout.
    r, g, b, a = uav_rgba.split()
    a = a.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
    uav_rgba = Image.merge("RGBA", (r, g, b, a))

    # Slightly boost contrast on UAV for better visibility in cluttered scenes.
    uav_rgb = ImageEnhance.Contrast(uav_rgba.convert("RGB")).enhance(1.05)
    uav_rgba = Image.merge("RGBA", (*uav_rgb.split(), a))

    uw, uh = uav_rgba.size
    target = int(out_size * uav_scale)
    scale = target / max(uw, uh)
    nw, nh = max(1, int(uw * scale)), max(1, int(uh * scale))
    uav_rgba = uav_rgba.resize((nw, nh), Image.Resampling.LANCZOS)

    # Soft shadow under UAV.
    shadow = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
    alpha = uav_rgba.split()[-1].filter(ImageFilter.GaussianBlur(8))
    shadow.putalpha(alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))

    jx = int((random.random() - 0.5) * jitter * out_size)
    jy = int((random.random() - 0.5) * jitter * out_size)
    x = (out_size - nw) // 2 + jx
    y = (out_size - nh) // 2 + jy

    canvas = bg.convert("RGBA")
    canvas.alpha_composite(shadow, (x + 6, y + 8))
    canvas.alpha_composite(uav_rgba, (x, y))

    out_dir.mkdir(parents=True, exist_ok=True)
    uav_stem = uav_path.stem
    bg_tag = f"{bg_path.parent.name}_{bg_path.stem}"
    out_path = out_dir / f"{uav_stem}__on__{bg_tag}.jpg"
    canvas.convert("RGB").save(out_path, quality=95)
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Composite UAV renders onto random real-world backgrounds"
    )
    parser.add_argument("--uav_root", default="data/uav_dataset_color_mild_clean/enrollment")
    parser.add_argument("--bg_root", default="data/backgrounds")
    parser.add_argument(
        "--bg_image",
        default=None,
        help=(
            "Optional fixed background image path. If set, this background is used for all outputs."
        ),
    )
    parser.add_argument("--out", default="data/composited_rembg")
    parser.add_argument("--test", action="store_true", help="Run one test image")
    parser.add_argument(
        "--count", type=int, default=1, help="Number of outputs (ignored with --test)"
    )
    parser.add_argument(
        "--random_uav", action="store_true", help="Pick UAVs randomly from uav_root"
    )
    parser.add_argument(
        "--uav_image",
        default="data/uav_dataset_color_mild_clean/enrollment/mq-9_reaper/az000_el-45_noon_clear_enrollment_v00.jpg",
    )
    args = parser.parse_args()

    uav_root = Path(args.uav_root)
    bg_root = Path(args.bg_root)
    out_dir = Path(args.out)

    fixed_bg = None
    if args.bg_image:
        fixed_bg = Path(args.bg_image)
        if not fixed_bg.exists():
            raise RuntimeError(f"Background image not found: {fixed_bg}")
    else:
        bg_files = collect_images(bg_root)
        if not bg_files:
            raise RuntimeError(f"No backgrounds found in: {bg_root}")

    session = new_session("u2net")

    if args.test:
        uav_path = Path(args.uav_image)
        if not uav_path.exists():
            raise RuntimeError(f"UAV image not found: {uav_path}")
        bg_path = fixed_bg if fixed_bg else random.choice(bg_files)
        out_path = composite_one(uav_path, bg_path, out_dir, session)
        print(f"Saved test composite: {out_path}")
        return

    uav_files = collect_images(uav_root)
    if not uav_files:
        raise RuntimeError(f"No UAV images found in: {uav_root}")

    for i in range(max(1, args.count)):
        uav_path = random.choice(uav_files) if args.random_uav else uav_files[i % len(uav_files)]
        bg_path = fixed_bg if fixed_bg else random.choice(bg_files)
        out_path = composite_one(uav_path, bg_path, out_dir, session)
        print(f"[{i + 1}/{args.count}] {out_path}")


if __name__ == "__main__":
    main()
