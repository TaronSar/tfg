"""Move crop images whose shorter side is below a minimum size.

By default this is intended for YOLOX train/val crops only. Enrollment images
are deliberately left untouched because they are the large support-domain views.

Usage:
    python scripts/filter_small_crops.py --data_root data/uav_dataset_yolox_crops --min_px 30 --dry_run
    python scripts/filter_small_crops.py --data_root data/uav_dataset_yolox_crops --min_px 30
"""

import argparse
import shutil
from pathlib import Path

from PIL import Image


IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def crop_shorter_side(path: Path) -> int | None:
    try:
        with Image.open(path) as image:
            return min(image.size)
    except Exception as exc:
        print(f"  [skip] cannot read {path}: {exc}")
        return None


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def filter_split(split_dir: Path, quarantine_root: Path, min_px: int,
                 dry_run: bool) -> tuple[int, int, int]:
    checked = moved = kept = 0
    root = split_dir.parent
    for path in sorted(split_dir.rglob("*")):
        if path.suffix.lower() not in IMG_EXTS:
            continue
        side = crop_shorter_side(path)
        if side is None:
            continue
        checked += 1
        if side >= min_px:
            kept += 1
            continue
        moved += 1
        dest = unique_destination(quarantine_root / path.relative_to(root))
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
    return checked, kept, moved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quarantine train/val crops smaller than a minimum pixel size.")
    parser.add_argument("--data_root", required=True,
                        help="Dataset root containing train/, val/, and optionally enrollment/.")
    parser.add_argument("--min_px", type=int, default=30,
                        help="Minimum allowed shorter-side size in pixels.")
    parser.add_argument("--splits", nargs="+", default=["train", "val"],
                        help="Splits to filter. Defaults to train val.")
    parser.add_argument("--quarantine_root", default=None,
                        help="Destination for removed crops. Defaults to a sibling folder.")
    parser.add_argument("--dry_run", action="store_true",
                        help="Report what would move without changing files.")
    args = parser.parse_args()

    data_root = Path(args.data_root)
    quarantine_root = (Path(args.quarantine_root) if args.quarantine_root else
                       data_root.parent / f"{data_root.name}_removed_lt{args.min_px}")

    print(f"Data root:       {data_root.resolve()}")
    print(f"Minimum crop px: {args.min_px}")
    print(f"Quarantine:      {quarantine_root.resolve()}")
    print(f"Dry run:         {args.dry_run}")

    total_checked = total_kept = total_moved = 0
    for split in args.splits:
        split_dir = data_root / split
        if not split_dir.exists():
            print(f"\n{split}: missing, skipped")
            continue
        checked, kept, moved = filter_split(split_dir, quarantine_root,
                                            args.min_px, args.dry_run)
        total_checked += checked
        total_kept += kept
        total_moved += moved
        action = "would move" if args.dry_run else "moved"
        print(f"\n{split}: checked={checked} kept={kept} {action}={moved}")

    action = "would move" if args.dry_run else "moved"
    print(f"\nTotal: checked={total_checked} kept={total_kept} {action}={total_moved}")


if __name__ == "__main__":
    main()