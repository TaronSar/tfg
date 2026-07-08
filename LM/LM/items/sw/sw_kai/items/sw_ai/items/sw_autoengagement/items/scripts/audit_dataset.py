"""audit_dataset.py — Inspect your data/ folder before training.

Prints identity counts, images per identity, and crop size distribution
so you know exactly what the ProtoNet will see.

Usage:
    python scripts/audit_dataset.py --data_root data/
    python scripts/audit_dataset.py --data_root data/ --show_sizes  # pixel-size histogram
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def estimate_object_long_side(path: Path) -> int | None:
    """Estimate foreground object size against mostly uniform render backgrounds."""
    try:
        with Image.open(path) as im:
            arr = np.asarray(im.convert("RGB")).astype(np.int16)
    except Exception:
        return None

    h, w = arr.shape[:2]
    margin = max(8, min(h, w) // 32)
    corners = np.concatenate(
        [
            arr[:margin, :margin].reshape(-1, 3),
            arr[:margin, -margin:].reshape(-1, 3),
            arr[-margin:, :margin].reshape(-1, 3),
            arr[-margin:, -margin:].reshape(-1, 3),
        ]
    )
    bg = np.median(corners, axis=0)
    diff = np.abs(arr - bg).sum(axis=2)
    mask = diff > 55
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(max(xs.max() - xs.min() + 1, ys.max() - ys.min() + 1))


def identity_names(split_dir: Path) -> set[str]:
    if not split_dir.exists():
        return set()
    return {p.name for p in split_dir.iterdir() if p.is_dir()}


def positive_names(names: set[str]) -> set[str]:
    return {name for name in names if not name.lower().startswith("neg_")}


def negative_names(names: set[str]) -> set[str]:
    return {name for name in names if name.lower().startswith("neg_")}


def load_manifest(root: Path) -> dict | None:
    path = root / "split_manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"\n  WARNING: could not read split_manifest.json: {exc}")
        return None


def audit_split(split_dir: Path, show_sizes: bool):
    idents = sorted(p for p in split_dir.iterdir() if p.is_dir())
    print(f"\n{'─' * 65}")
    print(f"  Split: {split_dir.name}   ({len(idents)} identities)")
    print(f"{'─' * 65}")
    print(f"  {'Identity':<30} {'imgs':>5}  {'min_px':>7}  {'max_px':>7}")
    print(f"  {'─' * 58}")

    all_counts, all_sizes = [], []
    all_object_sizes = []
    low_identity = []
    suspicious_nested = []

    for ident in idents:
        imgs = sorted(f for f in ident.rglob("*") if f.suffix.lower() in IMG_EXTS)
        count = len(imgs)
        all_counts.append(count)
        sizes = []
        if show_sizes:
            for p in imgs:
                try:
                    w, h = Image.open(p).size
                    sizes.append(min(w, h))
                    all_sizes.append(min(w, h))
                    obj_px = estimate_object_long_side(p)
                    if obj_px is not None:
                        all_object_sizes.append(obj_px)
                except Exception:
                    pass
        flag = " ⚠" if count < 5 else ""
        if count < 5:
            low_identity.append(ident.name)
        nested_operational = ident / "operational"
        if ident.name == "operational" or nested_operational.exists():
            suspicious_nested.append(ident.name)
        sz_str = f"{min(sizes):>7}  {max(sizes):>7}" if sizes else f"{'─':>7}  {'─':>7}"
        print(f"  {ident.name:<30} {count:>5}  {sz_str}{flag}")

    print(f"  {'─' * 58}")
    print(f"  {'TOTAL':<30} {sum(all_counts):>5}")
    print(
        f"  avg per identity: {np.mean(all_counts):.1f} | "
        f"min: {min(all_counts)} | max: {max(all_counts)}"
    )

    if low_identity:
        print("\n  ⚠ Identities with <5 images (may be excluded from episodes):")
        for n in low_identity:
            print(f"    {n}")

    if suspicious_nested:
        print("\n  ⚠ Suspicious nested render folders:")
        for n in suspicious_nested:
            print(f"    {n}")
        print(
            "    Expected layout is split/<identity>/*.jpg, not split/operational/<identity>/*.jpg"
        )

    if show_sizes and all_sizes:
        print("\n  Image canvas shorter side distribution:")
        buckets = [(0, 30), (30, 40), (40, 60), (60, 100), (100, 143), (143, 300), (300, 9999)]
        labels = ["<30px", "30-40px", "40-60px", "60-100px", "100-143px", "143-300px", ">300px"]
        for (lo, hi), label in zip(buckets, labels, strict=False):
            n = sum(1 for s in all_sizes if lo <= s < hi)
            bar = "█" * (n * 30 // max(len(all_sizes), 1))
            print(f"    {label:<28} {n:>5}  {bar}")
        in_crop_env = sum(1 for s in all_sizes if 40 <= s <= 100)
        print("\n  Target YOLOX crop canvas envelope: 40-100px")
        pct = 100 * in_crop_env / len(all_sizes)
        print(f"  Images in crop envelope: {in_crop_env}/{len(all_sizes)} ({pct:.0f}%)")

    if show_sizes and all_object_sizes:
        print("\n  Estimated object long-side distribution:")
        buckets = [(0, 40), (40, 60), (60, 120), (120, 143), (143, 300), (300, 9999)]
        labels = [
            "<40px (too small)",
            "40-60px (far)",
            "60-120px (target)",
            "120-143px",
            "143-300px",
            ">300px (enrollment style)",
        ]
        for (lo, hi), label in zip(buckets, labels, strict=False):
            n = sum(1 for s in all_object_sizes if lo <= s < hi)
            bar = "█" * (n * 30 // max(len(all_object_sizes), 1))
            print(f"    {label:<28} {n:>5}  {bar}")
        print("\n  Target operational object envelope: 60-120px")
        in_env = sum(1 for s in all_object_sizes if 60 <= s <= 120)
        pct = 100 * in_env / len(all_object_sizes)
        print(f"  Objects in envelope: {in_env}/{len(all_object_sizes)} ({pct:.0f}%)")

    return len(idents), sum(all_counts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_root", default="data")
    ap.add_argument(
        "--show_sizes",
        action="store_true",
        help="Load each image and print pixel-size distribution. Slower.",
    )
    args = ap.parse_args()

    root = Path(args.data_root)
    print(f"\n{'═' * 65}")
    print(f"  Dataset audit: {root.resolve()}")
    print(f"{'═' * 65}")

    total_idents = total_imgs = 0
    for split in ["train", "val", "enrollment"]:
        split_dir = root / split
        if not split_dir.exists():
            print(f"  (no {split}/ folder)")
            continue
        ni, im = audit_split(split_dir, args.show_sizes)
        total_idents += ni
        total_imgs += im

    print(f"\n{'═' * 65}")
    print(f"  Split-folder total: {total_idents} identity folders, {total_imgs} images")

    # ProtoNet viability check
    train_dir = root / "train"
    val_dir = root / "val"
    enroll_dir = root / "enrollment"
    train_names = identity_names(train_dir)
    val_names = identity_names(val_dir)
    enroll_names = identity_names(enroll_dir)
    train_idents = len(train_names)
    val_idents = len(val_names)
    unique_names = train_names | val_names | enroll_names
    train_val_overlap = train_names & val_names
    train_enroll_overlap = train_names & enroll_names
    val_enroll_overlap = val_names & enroll_names
    neg_in_val = negative_names(val_names)
    neg_in_enrollment = negative_names(enroll_names)
    expected_enrollment = positive_names(train_names) | positive_names(val_names)
    missing_enrollment = expected_enrollment - enroll_names

    print(f"  Unique identity names across splits: {len(unique_names)}")

    print("\n  ProtoNet viability:")
    checks = [
        (train_idents >= 10, f"train identities >= 10          ({train_idents})"),
        (val_idents >= 5, f"val identities >= 5             ({val_idents})"),
        (train_idents >= 5, f"can run 5-way episodes          ({min(train_idents, 5)}-way)"),
        (val_idents >= 5, f"can run 5-way val episodes      ({min(val_idents, 5)}-way)"),
        (not train_val_overlap, f"train/val identity overlap     ({len(train_val_overlap)})"),
        (not neg_in_val, f"neg_* identities in val         ({len(neg_in_val)})"),
        (not neg_in_enrollment, f"neg_* identities in enrollment  ({len(neg_in_enrollment)})"),
    ]
    for ok, msg in checks:
        print(f"    {'✓' if ok else '✗'} {msg}")

    if train_val_overlap:
        print("\n  DATA LEAKAGE: identities in both train and val:")
        for n in sorted(train_val_overlap):
            print(f"    {n}")

    if neg_in_val or neg_in_enrollment:
        print("\n  NEGATIVE SPLIT ERROR: neg_* identities must be train-only:")
        for n in sorted(neg_in_val):
            print(f"    val/{n}")
        for n in sorted(neg_in_enrollment):
            print(f"    enrollment/{n}")

    if enroll_names:
        print("\n  Enrollment overlap notes:")
        print(f"    train/enrollment overlap: {len(train_enroll_overlap)}")
        print(f"    val/enrollment overlap:   {len(val_enroll_overlap)}")
        coverage = "yes" if not missing_enrollment else "no"
        print(f"    enrollment covers train+val identities: {coverage}")
        print("    This is expected for deployment galleries, but do not use a gallery built")
        print("    from train identities to claim held-out validation performance.")
        if missing_enrollment:
            print("\n  Missing enrollment identities:")
            for n in sorted(missing_enrollment):
                print(f"    {n}")

    manifest = load_manifest(root)
    if manifest:
        print("\n  Manifest consistency:")
        expected = {
            "train": train_names,
            "val": val_names,
            "enrollment": enroll_names,
            "train_negatives": negative_names(train_names),
        }
        for key, actual in expected.items():
            declared = set(manifest.get(key, []))
            extra = actual - declared
            missing = declared - actual
            ok = not extra and not missing
            print(f"    {'✓' if ok else '✗'} {key}")
            if extra:
                print(f"      on disk, not manifest: {sorted(extra)}")
            if missing:
                print(f"      in manifest, not on disk: {sorted(missing)}")
    print(f"{'═' * 65}\n")


if __name__ == "__main__":
    main()
