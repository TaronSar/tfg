"""Apply real-world backgrounds to rendered UAV dataset identities.

Behavior:
- Input identities from data/uav_dataset_before_bg/operational/<identity>
- Use exactly 30 backgrounds from data/backgrounds/**
- Each identity has 30 renders and receives all 30 backgrounds (one-to-one by index)
- UAV is positioned near the top quarter of the frame with mild random jitter
- Output to data/uav_dataset_after_bg/operational/<identity>

Run:
  python scripts/apply_backgrounds_dataset.py
"""

import argparse
import io
import random
from collections import deque
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
from rembg import new_session, remove


def collect_images(root: Path):
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted([p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts])


def fit_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize/crop image to fully cover the target canvas."""
    w, h = img.size
    scale = max(width / w, height / h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - width) // 2
    top = (nh - height) // 2
    return img.crop((left, top, left + width, top + height))


def keep_largest_alpha_component(alpha_img: Image.Image, threshold: int = 24) -> Image.Image:
    """Remove small disconnected alpha blobs and keep only the main UAV component."""
    w, h = alpha_img.size
    px = alpha_img.load()

    visited = [[False] * w for _ in range(h)]
    largest = []

    for y in range(h):
        for x in range(w):
            if visited[y][x] or px[x, y] <= threshold:
                visited[y][x] = True
                continue

            q = deque([(x, y)])
            visited[y][x] = True
            comp = []

            while q:
                cx, cy = q.popleft()
                comp.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h or visited[ny][nx]:
                        continue
                    visited[ny][nx] = True
                    if px[nx, ny] > threshold:
                        q.append((nx, ny))

            if len(comp) > len(largest):
                largest = comp

    clean = Image.new("L", (w, h), 0)
    clean_px = clean.load()
    for x, y in largest:
        clean_px[x, y] = px[x, y]

    # Light feather after component filtering for natural edges.
    return clean.filter(ImageFilter.GaussianBlur(0.5))


def extract_uav_rgba(path: Path, session):
    with open(path, "rb") as f:
        blob = f.read()
    out = remove(blob, session=session)
    uav = Image.open(io.BytesIO(out)).convert("RGBA")

    # Tighten and smooth alpha edges to reduce halo.
    r, g, b, a = uav.split()
    a = a.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.6))

    # Slightly improve UAV contrast for mixed backgrounds.
    rgb = ImageEnhance.Contrast(Image.merge("RGB", (r, g, b))).enhance(1.05)
    r2, g2, b2 = rgb.split()
    cleaned = keep_largest_alpha_component(a)

    # Easy stain reduction: remove weak alpha haze and zero hidden RGB.
    cleaned = cleaned.point(lambda v: 0 if v < 34 else v)
    p_r = r2.load()
    p_g = g2.load()
    p_b = b2.load()
    p_a = cleaned.load()
    w, h = cleaned.size
    for y in range(h):
        for x in range(w):
            if p_a[x, y] == 0:
                p_r[x, y] = 0
                p_g[x, y] = 0
                p_b[x, y] = 0

    return Image.merge("RGBA", (r2, g2, b2, cleaned))


def apply_alpha_cleanup(
    uav_rgba: Image.Image, alpha_cutoff: int, edge_shrink_px: int
) -> Image.Image:
    """Aggressively clean low-alpha residue and slightly shrink edges to remove stains."""
    r, g, b, a = uav_rgba.split()

    # Optional edge shrink: 1-2 px usually enough to remove residual border haze.
    for _ in range(max(0, edge_shrink_px)):
        a = a.filter(ImageFilter.MinFilter(3))

    # Hard alpha clip to remove weak stain-like residue.
    a = a.point(lambda v: 0 if v < alpha_cutoff else 255)
    a = a.filter(ImageFilter.GaussianBlur(0.35))

    # Remove hidden RGB where alpha is zero.
    p_r = r.load()
    p_g = g.load()
    p_b = b.load()
    p_a = a.load()
    w, h = a.size
    for y in range(h):
        for x in range(w):
            if p_a[x, y] == 0:
                p_r[x, y] = 0
                p_g[x, y] = 0
                p_b[x, y] = 0

    return Image.merge("RGBA", (r, g, b, a))


def composite(
    uav_path: Path,
    bg_path: Path,
    out_path: Path,
    session,
    out_w: int,
    out_h: int,
    uav_scale: float,
    jitter_x_frac: float,
    jitter_y_frac: float,
    alpha_cutoff: int,
    edge_shrink_px: int,
    shadow_strength: float,
):
    bg = Image.open(bg_path).convert("RGB")
    bg = fit_cover(bg, out_w, out_h)

    uav = extract_uav_rgba(uav_path, session)
    uav = apply_alpha_cleanup(
        uav,
        alpha_cutoff=max(0, min(255, alpha_cutoff)),
        edge_shrink_px=max(0, edge_shrink_px),
    )

    uw, uh = uav.size
    target = int(min(out_w, out_h) * uav_scale)
    scale = target / max(uw, uh)
    nw, nh = max(1, int(uw * scale)), max(1, int(uh * scale))
    uav = uav.resize((nw, nh), Image.Resampling.LANCZOS)

    shadow = None
    if shadow_strength > 0:
        # Shadow under UAV, but from a strict mask so residue doesn't cast shadow.
        shadow = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
        alpha = (
            uav.split()[-1]
            .point(lambda v: 255 if v > 120 else 0)
            .filter(ImageFilter.GaussianBlur(5))
        )
        if shadow_strength < 1.0:
            alpha = alpha.point(lambda v: int(v * shadow_strength))
        shadow.putalpha(alpha)
        shadow = shadow.filter(ImageFilter.GaussianBlur(2))

    # Position UAV near top quarter with controlled random jitter.
    jx = int((random.random() - 0.5) * 2.0 * jitter_x_frac * out_w)
    jy = int((random.random() - 0.5) * 2.0 * jitter_y_frac * out_h)
    cx = out_w // 2 + jx
    cy = int(out_h * 0.25) + jy
    cy = max(int(out_h * 0.18), min(int(out_h * 0.33), cy))
    x = cx - (nw // 2)
    y = cy - (nh // 2)

    # Keep the UAV fully in frame.
    x = max(0, min(out_w - nw, x))
    y = max(0, min(out_h - nh, y))

    canvas = bg.convert("RGBA")
    if shadow is not None:
        canvas.alpha_composite(shadow, (x + 5, y + 7))
    canvas.alpha_composite(uav, (x, y))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, quality=95)


def main():
    p = argparse.ArgumentParser(
        description="Apply 30 backgrounds to each 30-image UAV identity folder"
    )
    p.add_argument("--before_root", default="data/uav_dataset_before_bg/operational")
    p.add_argument("--background_root", default="data/backgrounds")
    p.add_argument("--after_root", default="data/uav_dataset_after_bg/operational")
    p.add_argument("--out_width", type=int, default=640)
    p.add_argument("--out_height", type=int, default=640)
    p.add_argument("--uav_scale", type=float, default=0.84)
    p.add_argument(
        "--jitter_x",
        type=float,
        default=0.12,
        help="Horizontal center jitter as fraction of image width",
    )
    p.add_argument(
        "--jitter_y",
        type=float,
        default=0.05,
        help="Vertical center jitter as fraction of image height",
    )
    p.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducible placement jitter"
    )
    p.add_argument(
        "--identities", default="all", help="Comma-separated identities to process or 'all'"
    )
    p.add_argument(
        "--limit", type=int, default=0, help="If >0, process only first N images per identity"
    )
    p.add_argument(
        "--alpha_cutoff",
        type=int,
        default=70,
        help="Alpha threshold for residue removal (higher = cleaner edges)",
    )
    p.add_argument(
        "--edge_shrink", type=int, default=1, help="Edge shrink iterations to remove border haze"
    )
    p.add_argument(
        "--shadow_strength",
        type=float,
        default=0.0,
        help="0 disables shadow; 0.4-0.7 keeps subtle shadow",
    )
    args = p.parse_args()

    before_root = Path(args.before_root)
    after_root = Path(args.after_root)

    backgrounds = collect_images(Path(args.background_root))
    if len(backgrounds) != 30:
        raise RuntimeError(f"Expected exactly 30 backgrounds, found {len(backgrounds)}")

    identity_dirs = sorted([d for d in before_root.iterdir() if d.is_dir()])
    if len(identity_dirs) != 4:
        raise RuntimeError(f"Expected 4 identity folders, found {len(identity_dirs)}")

    if args.identities.strip().lower() != "all":
        selected = {x.strip() for x in args.identities.split(",") if x.strip()}
        identity_dirs = [d for d in identity_dirs if d.name in selected]
        if not identity_dirs:
            raise RuntimeError("No valid identities selected with --identities")

    session = new_session("u2net")
    random.seed(args.seed)

    total = 0
    for identity_dir in identity_dirs:
        uav_images = sorted(
            [
                f
                for f in identity_dir.iterdir()
                if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ]
        )
        if len(uav_images) != 30:
            raise RuntimeError(
                f"Identity '{identity_dir.name}' expected 30 images, found {len(uav_images)}"
            )

        if args.limit > 0:
            uav_images = uav_images[: args.limit]

        for idx, uav_path in enumerate(uav_images):
            bg_path = backgrounds[idx]
            out_path = after_root / identity_dir.name / uav_path.name
            composite(
                uav_path=uav_path,
                bg_path=bg_path,
                out_path=out_path,
                session=session,
                out_w=args.out_width,
                out_h=args.out_height,
                uav_scale=args.uav_scale,
                jitter_x_frac=max(0.0, args.jitter_x),
                jitter_y_frac=max(0.0, args.jitter_y),
                alpha_cutoff=args.alpha_cutoff,
                edge_shrink_px=args.edge_shrink,
                shadow_strength=max(0.0, min(1.0, args.shadow_strength)),
            )
            total += 1
            print(f"[{total:03d}/120] {identity_dir.name} :: {uav_path.name} <- {bg_path.name}")

    print(f"Done. Generated {total} images in {after_root}")


if __name__ == "__main__":
    main()
