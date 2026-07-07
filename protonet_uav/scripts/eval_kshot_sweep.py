#!/usr/bin/env python3
"""Sweep open-set evaluation over multiple k-shot values.

Usage:
    python scripts/eval_kshot_sweep.py --checkpoint checkpoints/best.pth --data_root data/uav_dataset
    python scripts/eval_kshot_sweep.py --checkpoint checkpoints/best.pth --data_root data/uav_dataset --gallery_split enrollment --split val --k_shots 1 3 5 10 15
"""

import argparse
import csv
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.dataset import IdentityIndex, build_transform  # noqa: E402
from src.eval_openset import embed_paths, roc_auc, tpr_at_fpr  # noqa: E402
from src.model import ProtoNetEncoder, attention_prototype, build_encoder, BACKBONE_NORM  # noqa: E402


def nice_font(size: int):
    for name in ["arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def load_model(checkpoint: str | None, device: str):
    embed_dim, image_size = 128, 224
    metric, normalize = "euclidean", True
    backbone = "mobilenetv3"
    model = build_encoder(backbone, embed_dim=embed_dim, pretrained=True,
                          l2_normalize=normalize)
    label = "zero_shot_imagenet"
    if checkpoint:
        ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
        embed_dim = ckpt.get("embed_dim", 128)
        image_size = ckpt.get("image_size", 224)
        metric = ckpt.get("metric", "euclidean")
        normalize = ckpt.get("l2_normalize", True)
        backbone = ckpt.get("backbone", "mobilenetv3")
        model = build_encoder(backbone, embed_dim=embed_dim, pretrained=False,
                              l2_normalize=normalize)
        model.load_state_dict(ckpt["model"])
        label = Path(checkpoint).parent.name
        print(f"Loaded {checkpoint} | backbone={backbone} metric={metric} normalize={normalize}")
    else:
        print("Zero-shot ImageNet features (no checkpoint)")
    model.eval().to(device)
    return model, image_size, metric, normalize, label, backbone


def shuffled_pools(index: IdentityIndex, rng: random.Random) -> dict[str, list[Path]]:
    pools = {}
    for name in index.names:
        paths = list(index.identities[name])
        rng.shuffle(paths)
        pools[name] = paths
    return pools


@torch.no_grad()
def evaluate_kshot(model, tfm, device, query_index: IdentityIndex, gallery_index: IdentityIndex,
                   k_shot: int, max_queries_per_id: int, agg: str, tau: float,
                   metric: str, normalize: bool, seed: int) -> dict[str, float | int]:
    rng = random.Random(seed + k_shot * 1009)
    query_pools = shuffled_pools(query_index, rng)
    gallery_pools = shuffled_pools(gallery_index, rng)
    same_split = gallery_index.root == query_index.root

    genuine_all, impostor_all = [], []
    skipped_missing_gallery = 0
    skipped_no_queries = 0

    for name in query_index.names:
        query_paths_all = query_pools[name]
        gallery_paths_all = gallery_pools.get(name)
        if not gallery_paths_all:
            skipped_missing_gallery += 1
            continue

        if same_split:
            if len(query_paths_all) <= k_shot:
                skipped_no_queries += 1
                continue
            enroll_paths = query_paths_all[:k_shot]
            query_paths = query_paths_all[k_shot:k_shot + max_queries_per_id]
        else:
            enroll_paths = (rng.sample(gallery_paths_all, k_shot)
                            if len(gallery_paths_all) >= k_shot
                            else rng.choices(gallery_paths_all, k=k_shot))
            query_paths = query_paths_all[:max_queries_per_id]
            if not query_paths:
                skipped_no_queries += 1
                continue

        gallery = embed_paths(model, enroll_paths, tfm, device)
        if normalize:
            gallery = F.normalize(gallery, p=2, dim=-1)
            mean_proto = F.normalize(gallery.mean(dim=0), p=2, dim=0)
        else:
            mean_proto = gallery.mean(dim=0)

        def score(q_emb):
            out = []
            for q in q_emb:
                if agg == "attention" and normalize:
                    proto = attention_prototype(q, gallery, tau=tau)
                else:
                    proto = mean_proto
                if metric == "cosine" or normalize:
                    out.append(float(q @ proto))
                else:
                    out.append(-float(((q - proto) ** 2).sum()))
            return out

        genuine_all += score(embed_paths(model, query_paths, tfm, device))

        imp_paths = []
        for other in query_index.names:
            if other == name:
                continue
            imp_paths += rng.sample(query_pools[other], min(3, len(query_pools[other])))
        impostor_all += score(embed_paths(model, imp_paths, tfm, device))

    genuine = np.array(genuine_all)
    impostor = np.array(impostor_all)
    if len(genuine) == 0 or len(impostor) == 0:
        raise RuntimeError("No scores were produced. Check split/gallery identity overlap.")
    tpr_1, thr_1 = tpr_at_fpr(genuine, impostor, 0.01)
    tpr_5, thr_5 = tpr_at_fpr(genuine, impostor, 0.05)
    tpr_10, thr_10 = tpr_at_fpr(genuine, impostor, 0.10)
    return {
        "k_shot": k_shot,
        "roc_auc": roc_auc(genuine, impostor),
        "tpr_fpr_1": float(tpr_1),
        "threshold_fpr_1": float(thr_1),
        "tpr_fpr_5": float(tpr_5),
        "threshold_fpr_5": float(thr_5),
        "tpr_fpr_10": float(tpr_10),
        "threshold_fpr_10": float(thr_10),
        "genuine_n": len(genuine),
        "genuine_mean": float(genuine.mean()),
        "impostor_n": len(impostor),
        "impostor_mean": float(impostor.mean()),
        "skipped_missing_gallery": skipped_missing_gallery,
        "skipped_no_queries": skipped_no_queries,
    }


def save_csv(rows: list[dict[str, float | int]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def map_points(xs: list[int], ys: list[float], box: tuple[int, int, int, int],
               y_min: float, y_max: float) -> list[tuple[int, int]]:
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    x_min, x_max = min(xs), max(xs)
    x_span = max(x_max - x_min, 1)
    y_span = max(y_max - y_min, 1e-9)
    return [
        (left + round((x - x_min) * width / x_span),
         bottom - round((y - y_min) * height / y_span))
        for x, y in zip(xs, ys)
    ]


def draw_line_chart(draw: ImageDraw.ImageDraw, rows: list[dict[str, float | int]],
                    box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    title_font = nice_font(24)
    label_font = nice_font(15)
    small_font = nice_font(13)
    plot_box = (left + 70, top + 55, right - 30, bottom - 55)
    plot_left, plot_top, plot_right, plot_bottom = plot_box
    draw.rectangle(box, outline=(210, 215, 220), width=1)
    draw.text((left + 18, top + 16), "Open-Set K-Shot Sweep", fill=(25, 30, 35), font=title_font)
    draw.rectangle(plot_box, outline=(60, 65, 70), width=2)

    for idx in range(6):
        y = plot_top + round(idx * (plot_bottom - plot_top) / 5)
        value = 1.0 - idx / 5
        draw.line((plot_left, y, plot_right, y), fill=(230, 233, 236), width=1)
        draw.text((left + 18, y - 8), f"{value:.1f}", fill=(80, 85, 90), font=small_font)

    k_values = [int(row["k_shot"]) for row in rows]
    for k in k_values:
        x = map_points(k_values, [0.0] * len(k_values), plot_box, 0.0, 1.0)[k_values.index(k)][0]
        draw.line((x, plot_bottom, x, plot_bottom + 5), fill=(60, 65, 70), width=1)
        draw.text((x - 10, plot_bottom + 14), str(k), fill=(80, 85, 90), font=small_font)
    draw.text((plot_left + (plot_right - plot_left) // 2 - 24, bottom - 28), "k-shot", fill=(80, 85, 90), font=small_font)

    series = [
        ("ROC-AUC", "roc_auc", (38, 112, 214)),
        ("TPR@1%", "tpr_fpr_1", (210, 72, 82)),
        ("TPR@5%", "tpr_fpr_5", (53, 150, 98)),
        ("TPR@10%", "tpr_fpr_10", (130, 82, 170)),
    ]
    legend_x, legend_y = right - 260, top + 22
    for label, key, color in series:
        draw.line((legend_x, legend_y + 10, legend_x + 30, legend_y + 10), fill=color, width=4)
        draw.text((legend_x + 38, legend_y), label, fill=(35, 40, 45), font=label_font)
        legend_y += 25
        ys = [float(row[key]) for row in rows]
        points = map_points(k_values, ys, plot_box, 0.0, 1.0)
        if len(points) > 1:
            draw.line(points, fill=color, width=4)
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)


def draw_summary(draw: ImageDraw.ImageDraw, rows: list[dict[str, float | int]],
                 args, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    title_font = nice_font(20)
    font = nice_font(15)
    best_auc = max(rows, key=lambda row: float(row["roc_auc"]))
    best_tpr = max(rows, key=lambda row: float(row["tpr_fpr_5"]))
    lines = [
        f"Checkpoint: {Path(args.checkpoint).parent.name if args.checkpoint else 'zero-shot'}",
        f"Data root: {args.data_root}",
        f"Query split: {args.split}",
        f"Gallery split: {args.gallery_split or args.split}",
        f"Agg: {args.agg}",
        f"K values: {', '.join(str(k) for k in args.k_shots)}",
        f"Best ROC-AUC: {float(best_auc['roc_auc']):.4f} at k={best_auc['k_shot']}",
        f"Best TPR@5%: {float(best_tpr['tpr_fpr_5']):.3f} at k={best_tpr['k_shot']}",
    ]
    draw.rectangle(box, outline=(210, 215, 220), width=1)
    draw.text((left + 18, top + 14), "Summary", fill=(25, 30, 35), font=title_font)
    y = top + 52
    max_chars = max(30, (right - left - 36) // 8)
    for line in lines:
        for chunk in [line[i:i + max_chars] for i in range(0, len(line), max_chars)]:
            if y > bottom - 24:
                return
            draw.text((left + 18, y), chunk, fill=(45, 50, 55), font=font)
            y += 24


def draw_means_chart(draw: ImageDraw.ImageDraw, rows: list[dict[str, float | int]],
                     box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    title_font = nice_font(20)
    label_font = nice_font(15)
    small_font = nice_font(13)
    plot_box = (left + 70, top + 48, right - 30, bottom - 48)
    plot_left, plot_top, plot_right, plot_bottom = plot_box
    draw.rectangle(box, outline=(210, 215, 220), width=1)
    draw.text((left + 18, top + 14), "Score Means", fill=(25, 30, 35), font=title_font)
    draw.rectangle(plot_box, outline=(60, 65, 70), width=2)
    values = [float(row["genuine_mean"]) for row in rows] + [float(row["impostor_mean"]) for row in rows]
    y_min, y_max = min(values), max(values)
    if y_min == y_max:
        y_min -= 0.5
        y_max += 0.5
    for idx in range(5):
        y = plot_top + round(idx * (plot_bottom - plot_top) / 4)
        value = y_max - idx * (y_max - y_min) / 4
        draw.line((plot_left, y, plot_right, y), fill=(230, 233, 236), width=1)
        draw.text((left + 10, y - 8), f"{value:.2f}", fill=(80, 85, 90), font=small_font)
    k_values = [int(row["k_shot"]) for row in rows]
    for label, key, color in [("genuine", "genuine_mean", (38, 112, 214)), ("impostor", "impostor_mean", (210, 72, 82))]:
        points = map_points(k_values, [float(row[key]) for row in rows], plot_box, y_min, y_max)
        if len(points) > 1:
            draw.line(points, fill=color, width=4)
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
        legend_y = top + 18 if label == "genuine" else top + 42
        draw.line((right - 190, legend_y + 10, right - 160, legend_y + 10), fill=color, width=4)
        draw.text((right - 152, legend_y), label, fill=(35, 40, 45), font=label_font)


def save_graph(rows: list[dict[str, float | int]], args, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1500, 920), (248, 249, 250))
    draw = ImageDraw.Draw(image)
    draw_line_chart(draw, rows, (40, 40, 960, 560))
    draw_summary(draw, rows, args, (1000, 40, 1460, 560))
    draw_means_chart(draw, rows, (40, 600, 1460, 880))
    image.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--data_root", required=True)
    parser.add_argument("--split", default="val")
    parser.add_argument("--gallery_split", default=None)
    parser.add_argument("--k_shots", nargs="+", type=int, default=[1, 3, 5, 10, 15])
    parser.add_argument("--max_queries_per_id", type=int, default=30)
    parser.add_argument("--agg", choices=["mean", "attention"], default="mean")
    parser.add_argument("--tau", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out_csv", default=None)
    parser.add_argument("--out_graph", default=None)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, image_size, metric, normalize, run_label, backbone = load_model(args.checkpoint, device)
    data_root = Path(args.data_root)
    query_index = IdentityIndex(data_root / args.split)
    gallery_split = args.gallery_split or args.split
    gallery_index = query_index if gallery_split == args.split else IdentityIndex(data_root / gallery_split)
    print(f"query {args.split}: {query_index.stats()}")
    if gallery_index is query_index:
        print(f"gallery {gallery_split}: same split as query")
    else:
        print(f"gallery {gallery_split}: {gallery_index.stats()}")
    print(f"device={device} backbone={backbone} agg={args.agg} k_shots={args.k_shots}\n")

    norm_mean, norm_std = BACKBONE_NORM[backbone]
    tfm = build_transform(image_size, train=False, mean=norm_mean, std=norm_std)
    rows = []
    for k_shot in args.k_shots:
        row = evaluate_kshot(model, tfm, device, query_index, gallery_index, k_shot,
                             args.max_queries_per_id, args.agg, args.tau,
                             metric, normalize, args.seed)
        rows.append(row)
        print(
            f"k={k_shot:>2} | ROC-AUC {row['roc_auc']:.4f} | "
            f"TPR@1% {row['tpr_fpr_1']:.3f} | TPR@5% {row['tpr_fpr_5']:.3f} | "
            f"TPR@10% {row['tpr_fpr_10']:.3f} | "
            f"genuine {row['genuine_mean']:.4f} | impostor {row['impostor_mean']:.4f}"
        )

    split_label = f"{gallery_split}_gallery_{args.split}_query"
    stem = f"{run_label}_{split_label}_{args.agg}_kshot_sweep"
    csv_path = Path(args.out_csv) if args.out_csv else ROOT / "csvs" / f"{stem}.csv"
    graph_path = Path(args.out_graph) if args.out_graph else ROOT / "graphs" / f"{stem}.png"
    save_csv(rows, csv_path)
    save_graph(rows, args, graph_path)
    print(f"\nSaved CSV:   {csv_path}")
    print(f"Saved graph: {graph_path}")


if __name__ == "__main__":
    main()