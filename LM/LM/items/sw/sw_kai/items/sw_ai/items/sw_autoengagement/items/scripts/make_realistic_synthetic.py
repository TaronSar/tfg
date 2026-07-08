#!/usr/bin/env python3
"""Create real-world camera variants from clean rendered UAV images.

The script preserves the ProtoNet layout:

    input_root/train/<identity>/*.jpg
    input_root/val/<identity>/*.jpg
    input_root/enrollment/<identity>/*.jpg

and writes a new dataset root with noisy, blurry, compressed, off-center,
mid-flight-looking variants. It does not modify the input dataset.
"""

import argparse
import io
import json
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def motion_blur(img: Image.Image, radius: int, horizontal: bool) -> Image.Image:
    radius = max(1, int(radius))
    base = img.convert("RGB")
    acc = np.asarray(base).astype(np.float32)
    samples = 1
    for offset in range(1, radius + 1):
        delta = (offset, 0) if horizontal else (0, offset)
        acc += np.asarray(ImageChops.offset(base, *delta)).astype(np.float32)
        acc += np.asarray(ImageChops.offset(base, -delta[0], -delta[1])).astype(np.float32)
        samples += 2
    return Image.fromarray(np.clip(acc / samples, 0, 255).astype(np.uint8), "RGB")


def jpeg_roundtrip(img: Image.Image, quality: int) -> Image.Image:
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=int(quality), optimize=False)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


def random_crop_jitter(img: Image.Image, strength: float) -> Image.Image:
    w, h = img.size
    zoom = random.uniform(1.0, 1.0 + strength)
    crop_w = max(1, int(w / zoom))
    crop_h = max(1, int(h / zoom))
    max_dx = max(0, w - crop_w)
    max_dy = max(0, h - crop_h)
    left = random.randint(0, max_dx) if max_dx else 0
    top = random.randint(0, max_dy) if max_dy else 0
    return img.crop((left, top, left + crop_w, top + crop_h)).resize(
        (w, h), Image.Resampling.BICUBIC
    )


def add_noise(img: Image.Image, sigma: float) -> Image.Image:
    arr = np.asarray(img).astype(np.float32)
    noise = np.random.normal(0.0, sigma, arr.shape).astype(np.float32)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def add_haze(img: Image.Image, amount: float) -> Image.Image:
    haze_color = np.array([205, 216, 226], dtype=np.float32)
    arr = np.asarray(img).astype(np.float32)
    arr = arr * (1.0 - amount) + haze_color * amount
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def low_res_roundtrip(img: Image.Image, min_side: int, max_side: int) -> Image.Image:
    w, h = img.size
    target = random.randint(min_side, max_side)
    scale = target / max(w, h)
    small = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.BILINEAR)
    return small.resize((w, h), Image.Resampling.BICUBIC)


def degrade(img: Image.Image, split_profile: str, strength: str) -> Image.Image:
    img = img.convert("RGB")
    if split_profile == "enrollment":
        img = random_crop_jitter(img, strength=random.uniform(0.03, 0.10))
        if random.random() < 0.45:
            img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.15, 0.7)))
        img = ImageEnhance.Brightness(img).enhance(random.uniform(0.88, 1.14))
        img = ImageEnhance.Contrast(img).enhance(random.uniform(0.86, 1.18))
        img = ImageEnhance.Color(img).enhance(random.uniform(0.82, 1.18))
        if random.random() < 0.35:
            img = add_noise(img, sigma=random.uniform(1.0, 4.5))
        return jpeg_roundtrip(img, quality=random.randint(72, 96))

    if strength == "aggressive":
        crop_range, low_range, motion_p, motion_r = (0.08, 0.24), (150, 300), 0.55, (1, 4)
        blur_p, blur_r, haze_p, haze_r = 0.50, (0.20, 1.00), 0.45, (0.03, 0.16)
        bright, contrast, color, noise_p, noise_r, jpeg = (
            (0.70, 1.22),
            (0.68, 1.28),
            (0.70, 1.30),
            0.70,
            (1.5, 8.0),
            (50, 92),
        )
    elif strength == "balanced":
        crop_range, low_range, motion_p, motion_r = (0.04, 0.16), (220, 380), 0.35, (1, 2)
        blur_p, blur_r, haze_p, haze_r = 0.35, (0.12, 0.60), 0.25, (0.02, 0.08)
        bright, contrast, color, noise_p, noise_r, jpeg = (
            (0.78, 1.18),
            (0.78, 1.25),
            (0.85, 1.25),
            0.50,
            (1.0, 5.0),
            (65, 95),
        )
    else:
        crop_range, low_range, motion_p, motion_r = (0.01, 0.06), (390, 500), 0.08, (1, 1)
        blur_p, blur_r, haze_p, haze_r = 0.08, (0.05, 0.18), 0.08, (0.005, 0.025)
        bright, contrast, color, noise_p, noise_r, jpeg = (
            (0.90, 1.08),
            (0.96, 1.16),
            (0.95, 1.16),
            0.20,
            (0.4, 1.8),
            (88, 98),
        )

    img = random_crop_jitter(img, strength=random.uniform(*crop_range))
    img = low_res_roundtrip(img, min_side=low_range[0], max_side=low_range[1])
    if random.random() < motion_p:
        img = motion_blur(img, radius=random.randint(*motion_r), horizontal=random.random() < 0.5)
    if random.random() < blur_p:
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(*blur_r)))
    if random.random() < haze_p:
        img = add_haze(img, amount=random.uniform(*haze_r))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(*bright))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(*contrast))
    img = ImageEnhance.Color(img).enhance(random.uniform(*color))
    if random.random() < noise_p:
        img = add_noise(img, sigma=random.uniform(*noise_r))
    return jpeg_roundtrip(img, quality=random.randint(*jpeg))


def iter_images(identity_dir: Path):
    return sorted(p for p in identity_dir.rglob("*") if p.suffix.lower() in IMG_EXTS)


def process_split(input_root: Path, output_root: Path, split: str, variants: int, strength: str):
    split_dir = input_root / split
    if not split_dir.exists():
        return 0
    count = 0
    profile = "enrollment" if split == "enrollment" else "operational"
    identity_dirs = sorted(p for p in split_dir.iterdir() if p.is_dir())
    print(
        f"Processing {split}: {len(identity_dirs)} identities x {variants} variant(s)", flush=True
    )
    for ident_idx, ident_dir in enumerate(identity_dirs, 1):
        out_ident = output_root / split / ident_dir.name
        out_ident.mkdir(parents=True, exist_ok=True)
        sources = iter_images(ident_dir)
        made_for_identity = 0
        for src in sources:
            try:
                base = Image.open(src).convert("RGB")
            except Exception as exc:
                print(f"WARNING: skipping {src}: {exc}")
                continue
            for idx in range(variants):
                dst = out_ident / f"{src.stem}_real{idx:02d}.jpg"
                if dst.exists():
                    continue
                img = degrade(base, profile, strength)
                img.save(dst, format="JPEG", quality=92)
                count += 1
                made_for_identity += 1
        print(
            f"  [{ident_idx}/{len(identity_dirs)}] {split}/{ident_dir.name}: "
            f"created {made_for_identity}",
            flush=True,
        )
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Clean rendered dataset root")
    parser.add_argument("--output", required=True, help="Realistic output dataset root")
    parser.add_argument("--train_variants", type=int, default=3)
    parser.add_argument("--val_variants", type=int, default=2)
    parser.add_argument("--enrollment_variants", type=int, default=1)
    parser.add_argument(
        "--profile",
        choices=["mild", "balanced", "aggressive"],
        default="mild",
        help="Camera degradation strength. Use mild to preserve UAV silhouettes.",
    )
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    input_root = Path(args.input)
    output_root = Path(args.output)
    if not input_root.exists():
        raise FileNotFoundError(input_root)
    output_root.mkdir(parents=True, exist_ok=True)

    manifest = input_root / "split_manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            data["realistic_postprocess"] = {
                "train_variants": args.train_variants,
                "val_variants": args.val_variants,
                "enrollment_variants": args.enrollment_variants,
                "effects": [
                    "crop_jitter",
                    "low_resolution",
                    "motion_blur",
                    "defocus_blur",
                    "haze",
                    "color_jitter",
                    "sensor_noise",
                    "jpeg_artifacts",
                ],
            }
            (output_root / "split_manifest.json").write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception:
            shutil.copy2(manifest, output_root / "split_manifest.json")

    total = 0
    total += process_split(
        input_root, output_root, "train", max(1, args.train_variants), args.profile
    )
    total += process_split(input_root, output_root, "val", max(1, args.val_variants), args.profile)
    total += process_split(
        input_root, output_root, "enrollment", max(1, args.enrollment_variants), args.profile
    )
    print(f"Created {total} realistic images under {output_root}")


if __name__ == "__main__":
    main()
