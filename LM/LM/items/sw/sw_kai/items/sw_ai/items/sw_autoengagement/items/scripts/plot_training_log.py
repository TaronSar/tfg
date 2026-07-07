#!/usr/bin/env python3
"""Plot ProtoNet training curves from a src.train log file.

Usage:
    python scripts/plot_training_log.py --log logs/train_color_mild_clean_15way_krobust_euclidean.log
    python scripts/plot_training_log.py --log logs/train_color_mild_clean_15way_krobust_euclidean.log --out graphs/results.png
"""

import argparse
import csv
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


EPOCH_RE = re.compile(
    r"epoch\s+(?P<epoch>\d+)\s+\|\s+"
    r"loss\s+(?P<loss>[0-9.]+)\s+\|\s+"
    r"train acc\s+(?P<train_acc>[0-9.]+)\s+\|\s+"
    r"val acc\s+(?P<val_acc>[0-9.]+)\s+\|\s+"
    r"(?P<seconds>[0-9.]+)s"
)


def parse_log(path: Path) -> list[dict[str, float]]:
    rows = []
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    else:
        text = data.decode("utf-8", errors="replace")
    for line in text.splitlines():
        match = EPOCH_RE.search(line)
        if not match:
            continue
        rows.append({
            "epoch": int(match.group("epoch")),
            "loss": float(match.group("loss")),
            "train_acc": float(match.group("train_acc")),
            "val_acc": float(match.group("val_acc")),
            "seconds": float(match.group("seconds")),
        })
    return rows


def read_log_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8", errors="replace")


def parse_run_info(path: Path) -> list[str]:
    text = read_log_text(path)
    lines = []
    for line in text.splitlines():
        if line.startswith(("Device:", "Metric:", "Shot-robust training:")):
            lines.append(line)
        if len(lines) >= 6:
            break
    return lines


def image_count(identity_names: list[str], split_dir: Path) -> int:
    total = 0
    for name in identity_names:
        ident_dir = split_dir / name
        if ident_dir.exists():
            total += sum(1 for path in ident_dir.rglob("*") if path.suffix.lower() in IMG_EXTS)
    return total


def load_dataset_info(root: Path | None) -> list[str]:
    if root is None:
        return ["Dataset root: not provided", "Pass --data_root to include image counts"]
    if not root.exists():
        return [f"Dataset root missing: {root}"]

    manifest_path = root / "split_manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except Exception:
            manifest = {}

    train = manifest.get("train", [])
    train_pos = manifest.get("train_positives", [name for name in train if not name.lower().startswith("neg_")])
    train_neg = manifest.get("train_negatives", [name for name in train if name.lower().startswith("neg_")])
    val = manifest.get("val", [])
    enrollment = manifest.get("enrollment", [])

    split_totals = {}
    for split in ["train", "val", "enrollment"]:
        split_dir = root / split
        if not split_dir.exists():
            split_totals[split] = (0, 0)
            continue
        identity_dirs = [path for path in split_dir.iterdir() if path.is_dir()]
        img_total = sum(1 for path in split_dir.rglob("*") if path.suffix.lower() in IMG_EXTS)
        split_totals[split] = (len(identity_dirs), img_total)

    train_pos_imgs = image_count(train_pos, root / "train")
    train_neg_imgs = image_count(train_neg, root / "train")
    val_imgs = image_count(val, root / "val")
    enrollment_imgs = image_count(enrollment, root / "enrollment")
    total_imgs = sum(total for _, total in split_totals.values())
    overlap = len(set(train) & set(val))

    return [
        f"Dataset: {root}",
        f"Train: {split_totals['train'][0]} ids / {split_totals['train'][1]} imgs",
        f"Train positives: {len(train_pos)} ids / {train_pos_imgs} imgs",
        f"Train negatives: {len(train_neg)} ids / {train_neg_imgs} imgs",
        f"Val positives: {len(val)} ids / {val_imgs} imgs",
        f"Enrollment: {len(enrollment)} ids / {enrollment_imgs} imgs",
        f"Total dataset images: {total_imgs}",
        f"Train/val overlap: {overlap}",
    ]


def save_csv(rows: list[dict[str, float]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["epoch", "loss", "train_acc", "val_acc", "seconds"])
        writer.writeheader()
        writer.writerows(rows)


def nice_font(size: int):
    for name in ["arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def map_points(values: list[float], x0: int, y0: int, width: int, height: int,
               value_min: float, value_max: float) -> list[tuple[int, int]]:
    if len(values) == 1:
        return [(x0 + width // 2, y0 + height // 2)]
    span = max(value_max - value_min, 1e-9)
    points = []
    for idx, value in enumerate(values):
        x = x0 + round(idx * width / (len(values) - 1))
        y = y0 + height - round((value - value_min) * height / span)
        points.append((x, y))
    return points


def draw_panel(draw: ImageDraw.ImageDraw, title: str, rows: list[dict[str, float]],
               keys: list[str], labels: list[str], colors: list[tuple[int, int, int]],
               box: tuple[int, int, int, int], y_min: float | None = None,
               y_max: float | None = None) -> None:
    left, top, right, bottom = box
    title_font = nice_font(22)
    label_font = nice_font(15)
    small_font = nice_font(13)
    plot_left, plot_top = left + 72, top + 46
    plot_right, plot_bottom = right - 28, bottom - 48
    plot_width, plot_height = plot_right - plot_left, plot_bottom - plot_top

    values_by_key = [[row[key] for row in rows] for key in keys]
    values = [value for series in values_by_key for value in series]
    value_min = min(values) if y_min is None else y_min
    value_max = max(values) if y_max is None else y_max
    if value_min == value_max:
        value_min -= 0.5
        value_max += 0.5

    draw.rectangle(box, outline=(210, 215, 220), width=1)
    draw.text((left + 18, top + 14), title, fill=(25, 30, 35), font=title_font)
    draw.rectangle((plot_left, plot_top, plot_right, plot_bottom), outline=(60, 65, 70), width=2)

    for i in range(6):
        y = plot_top + round(i * plot_height / 5)
        value = value_max - i * (value_max - value_min) / 5
        draw.line((plot_left, y, plot_right, y), fill=(230, 233, 236), width=1)
        draw.text((left + 14, y - 8), f"{value:.2f}", fill=(80, 85, 90), font=small_font)

    epochs = [row["epoch"] for row in rows]
    for i in range(6):
        x = plot_left + round(i * plot_width / 5)
        idx = round(i * (len(epochs) - 1) / 5)
        draw.line((x, plot_bottom, x, plot_bottom + 5), fill=(60, 65, 70), width=1)
        draw.text((x - 10, plot_bottom + 12), str(epochs[idx]), fill=(80, 85, 90), font=small_font)
    draw.text((plot_left + plot_width // 2 - 24, bottom - 24), "epoch", fill=(80, 85, 90), font=small_font)

    legend_x = right - 260
    legend_y = top + 18
    for label, color in zip(labels, colors):
        draw.line((legend_x, legend_y + 10, legend_x + 30, legend_y + 10), fill=color, width=4)
        draw.text((legend_x + 38, legend_y), label, fill=(35, 40, 45), font=label_font)
        legend_y += 24

    for key, color in zip(keys, colors):
        series = [row[key] for row in rows]
        points = map_points(series, plot_left, plot_top, plot_width, plot_height, value_min, value_max)
        if len(points) > 1:
            draw.line(points, fill=color, width=4, joint="curve")
        for x, y in points:
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=color)


def draw_summary(draw: ImageDraw.ImageDraw, rows: list[dict[str, float]], box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    font = nice_font(18)
    small_font = nice_font(15)
    best = max(rows, key=lambda row: row["val_acc"])
    last = rows[-1]
    best_gap = best["train_acc"] - best["val_acc"]
    last_gap = last["train_acc"] - last["val_acc"]
    max_gap_row = max(rows, key=lambda row: row["train_acc"] - row["val_acc"])
    avg_seconds = sum(row["seconds"] for row in rows) / len(rows)
    total_hours = sum(row["seconds"] for row in rows) / 3600

    lines = [
        f"Epochs: {len(rows)}",
        f"Best val acc: {best['val_acc']:.3f} at epoch {best['epoch']}",
        f"Best-epoch gap: {best_gap:+.3f}",
        f"Last val acc: {last['val_acc']:.3f}",
        f"Last train acc: {last['train_acc']:.3f}",
        f"Last train/val gap: {last_gap:+.3f}",
        f"Max gap: {max_gap_row['train_acc'] - max_gap_row['val_acc']:+.3f} at epoch {max_gap_row['epoch']}",
        f"Last loss: {last['loss']:.4f}",
        f"Avg epoch time: {avg_seconds:.1f}s",
        f"Total train time: {total_hours:.2f}h",
    ]
    draw.rectangle(box, outline=(210, 215, 220), width=1)
    draw.text((left + 18, top + 14), "Summary", fill=(25, 30, 35), font=font)
    y = top + 52
    for line in lines:
        draw.text((left + 18, y), line, fill=(45, 50, 55), font=small_font)
        y += 26


def draw_text_box(draw: ImageDraw.ImageDraw, title: str, lines: list[str],
                  box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    title_font = nice_font(18)
    small_font = nice_font(14)
    draw.rectangle(box, outline=(210, 215, 220), width=1)
    draw.text((left + 18, top + 14), title, fill=(25, 30, 35), font=title_font)
    y = top + 50
    max_chars = max(26, (right - left - 36) // 8)
    for line in lines:
        chunks = [line[i:i + max_chars] for i in range(0, len(line), max_chars)] or [""]
        for chunk in chunks:
            if y + 18 > bottom - 8:
                draw.text((left + 18, y), "...", fill=(45, 50, 55), font=small_font)
                return
            draw.text((left + 18, y), chunk, fill=(45, 50, 55), font=small_font)
            y += 22


def plot(rows: list[dict[str, float]], out_path: Path, title: str,
         run_info: list[str], dataset_info: list[str]) -> None:
    for row in rows:
        row["gap"] = row["train_acc"] - row["val_acc"]

    image = Image.new("RGB", (1500, 1040), (248, 249, 250))
    draw = ImageDraw.Draw(image)
    title_font = nice_font(28)
    draw.text((40, 24), title, fill=(20, 25, 30), font=title_font)

    draw_panel(
        draw, "Accuracy", rows,
        keys=["train_acc", "val_acc"],
        labels=["train acc", "val acc"],
        colors=[(38, 112, 214), (210, 72, 82)],
        box=(40, 78, 920, 410),
        y_min=0.0,
        y_max=1.0,
    )
    draw_panel(
        draw, "Loss", rows,
        keys=["loss"],
        labels=["loss"],
        colors=[(53, 150, 98)],
        box=(40, 450, 920, 730),
    )
    draw_panel(
        draw, "Train/Val Gap", rows,
        keys=["gap"],
        labels=["train acc - val acc"],
        colors=[(130, 82, 170)],
        box=(40, 770, 920, 1010),
    )
    draw_summary(draw, rows, (960, 78, 1460, 390))
    draw_text_box(draw, "Run", run_info, (960, 420, 1460, 610))
    draw_text_box(draw, "Dataset", dataset_info, (960, 640, 1460, 1010))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)


def default_graph_path(log_path: Path) -> Path:
    return Path("graphs") / f"{log_path.stem}_curves.png"


def default_csv_path(log_path: Path) -> Path:
    return Path("csvs") / f"{log_path.stem}_metrics.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="logs/train_color_mild_clean_15way_krobust_euclidean.log",
                        help="Training log produced by src.train.")
    parser.add_argument("--out", default=None,
                        help="PNG path. Default: graphs/<log stem>_curves.png")
    parser.add_argument("--csv", default=None,
                        help="CSV path. Default: csvs/<log stem>_metrics.csv")
    parser.add_argument("--data_root", default=None,
                        help="Optional dataset root. Adds identity/image counts to the graph.")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    rows = parse_log(log_path)
    if not rows:
        raise RuntimeError(f"No epoch lines found in {log_path}")

    out_path = Path(args.out) if args.out else default_graph_path(log_path)
    csv_path = Path(args.csv) if args.csv else default_csv_path(log_path)
    data_root = Path(args.data_root) if args.data_root else None
    save_csv(rows, csv_path)
    plot(rows, out_path, title=log_path.name,
         run_info=parse_run_info(log_path),
         dataset_info=load_dataset_info(data_root))

    best = max(rows, key=lambda row: row["val_acc"])
    print(f"Parsed {len(rows)} epochs from {log_path}")
    print(f"Best val acc: {best['val_acc']:.3f} at epoch {best['epoch']}")
    print(f"Saved graph: {out_path}")
    print(f"Saved CSV:   {csv_path}")


if __name__ == "__main__":
    main()