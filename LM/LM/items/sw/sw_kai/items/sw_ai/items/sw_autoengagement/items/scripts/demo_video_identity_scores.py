import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.uavid.common.constants import IMG_EXTS
from src.uavid.common.transforms import build_transform
from src.uavid.dataset import load_image
from src.uavid.model import ProtoNetEncoder

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}


def image_paths(path):
    root = Path(path)
    if root.is_file():
        return [root] if root.suffix.lower() in IMG_EXTS else []
    return sorted(file for file in root.rglob("*") if file.suffix.lower() in IMG_EXTS)


def load_model(checkpoint, device):
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
    embed_dim = ckpt.get("embed_dim", 128)
    image_size = ckpt.get("image_size", 224)
    normalize = ckpt.get("l2_normalize", True)
    metric = ckpt.get("metric", "euclidean")
    model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=False, l2_normalize=normalize)
    model.load_state_dict(ckpt["model"])
    model.eval().to(device)
    return model, image_size, normalize, metric, ckpt


def extract_video_frames(video_path, out_dir, every_sec, max_frames):
    try:
        import cv2
    except ImportError as exc:
        raise SystemExit("OpenCV is required for video extraction. Install opencv-python in the venv.") from exc

    video_path = Path(video_path)
    if not video_path.exists():
        raise SystemExit(f"Video not found: {video_path}")
    if video_path.suffix.lower() not in VIDEO_EXTS:
        print(f"Warning: video extension {video_path.suffix} is not in {sorted(VIDEO_EXTS)}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("frame_*.jpg"):
        old.unlink()

    cap = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
    if not cap.isOpened():
        cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    stride = max(1, int(round(fps * every_sec)))
    frame_idx = 0
    saved = 0
    frame_paths = []

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % stride == 0:
            out_path = out_dir / f"frame_{saved:05d}.jpg"
            cv2.imwrite(str(out_path), frame)
            frame_paths.append(out_path)
            saved += 1
            if max_frames and saved >= max_frames:
                break
        frame_idx += 1

    cap.release()
    if not frame_paths:
        raise SystemExit(f"No frames extracted from {video_path}")
    return frame_paths, fps, stride


@torch.no_grad()
def embed_paths(model, paths, transform, device, batch_size):
    batches = []
    for start in range(0, len(paths), batch_size):
        chunk = paths[start:start + batch_size]
        batch = torch.stack([load_image(path, transform) for path in chunk]).to(device)
        batches.append(model(batch))
    return torch.cat(batches, dim=0)


def make_proto(embeddings, normalize):
    if normalize:
        embeddings = F.normalize(embeddings, p=2, dim=-1)
        return F.normalize(embeddings.mean(dim=0), p=2, dim=0)
    return embeddings.mean(dim=0)


def score_against_proto(query_embeddings, proto, normalize, metric="euclidean"):
    if normalize:
        query_embeddings = F.normalize(query_embeddings, p=2, dim=-1)
        proto = F.normalize(proto, p=2, dim=0)
    if metric == "cosine":
        return (query_embeddings @ proto).detach().cpu().numpy().astype(np.float32)
    # euclidean: negative squared L2 distance (higher = more similar)
    return (-((query_embeddings - proto) ** 2).sum(dim=-1)).detach().cpu().numpy().astype(np.float32)


def topk_mean(scores, top_k):
    k = min(max(1, top_k), len(scores))
    return float(np.sort(scores)[-k:].mean())


def candidate_identity_dirs(root, include_negatives):
    dirs = sorted(path for path in Path(root).iterdir() if path.is_dir())
    if include_negatives:
        return dirs
    return [path for path in dirs if not path.name.lower().startswith("neg_")]


def support_candidates(path):
    root = Path(path)
    subdirs = sorted(item for item in root.iterdir() if item.is_dir()) if root.is_dir() else []
    candidates = []
    for subdir in subdirs:
        paths = image_paths(subdir)
        if paths:
            candidates.append((subdir.name, subdir, paths))
    if candidates:
        return candidates
    paths = image_paths(root)
    if paths:
        return [(root.name, root, paths)]
    return []


@torch.no_grad()
def main():
    parser = argparse.ArgumentParser(
        description="Score a query UAV video against uploaded support images and dataset identities."
    )
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--support", required=True, nargs="+",
                        help="One or more folders with support images (one folder per UAV identity).")
    parser.add_argument("--video", default=None, help="Query video of the UAV flying.")
    parser.add_argument("--query_frames", default=None,
                        help="Folder with already-extracted query frames. If set, --video is not required.")
    parser.add_argument("--data_root", default="data/uav_dataset_color_mild_clean")
    parser.add_argument("--identity_split", default="train", help="Dataset split whose identities should be scored.")
    parser.add_argument("--include_negatives", action="store_true", help="Also score neg_* identities from the split.")
    parser.add_argument("--every_sec", type=float, default=0.5, help="Extract one frame every N seconds.")
    parser.add_argument("--max_frames", type=int, default=60)
    parser.add_argument("--frame_dir", default="data/demo/video_query_frames")
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--k_support", type=int, default=0,
                        help="Max support images per candidate used to build the "
                             "prototype (0 = use all).")
    parser.add_argument("--top_k_frames", type=int, default=5)
    parser.add_argument("--out_csv", default="csvs/demo_video_identity_scores.csv")
    parser.add_argument("--out_frame_csv", default="csvs/demo_video_frame_scores.csv")
    parser.add_argument("--no_dataset_identities", action="store_true",
                        help="Only score the uploaded support candidates, not train/val dataset identities.")
    parser.add_argument("--metric", default="euclidean", choices=["euclidean", "cosine"],
                        help="Similarity metric: euclidean (neg squared L2) or cosine. Default: euclidean.")
    parser.add_argument("--mlflow_tracking_uri", default=None,
                        help="MLflow tracking URI. If omitted, reads from configs/setup.yaml.")
    args = parser.parse_args()

    if not args.video and not args.query_frames:
        raise SystemExit("Provide either --video or --query_frames.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, image_size, normalize, metric, ckpt = load_model(args.checkpoint, device)
    transform = build_transform(image_size, train=False)

    support_sets = []
    for sup_path in args.support:
        support_sets.extend(support_candidates(sup_path))
    if not support_sets:
        raise SystemExit(f"No support images found in {args.support}")

    fps, stride = None, None
    if args.query_frames:
        frame_paths = image_paths(args.query_frames)
        if not frame_paths:
            raise SystemExit(f"No query frames found in {args.query_frames}")
        if args.max_frames:
            frame_paths = frame_paths[:args.max_frames]
    else:
        frame_paths, fps, stride = extract_video_frames(args.video, args.frame_dir, args.every_sec, args.max_frames)
    query_embeddings = embed_paths(model, frame_paths, transform, device, args.batch_size)

    candidates = []
    for name, source, paths in support_sets:
        if args.k_support > 0:
            paths = paths[:args.k_support]
        embeddings = embed_paths(model, paths, transform, device, args.batch_size)
        candidates.append({
            "name": name,
            "source": str(source),
            "paths": paths,
            "prototype": make_proto(embeddings, normalize),
        })

    if not args.no_dataset_identities:
        split_root = Path(args.data_root) / args.identity_split
        if not split_root.exists():
            raise SystemExit(f"Identity split not found: {split_root}")

        for ident_dir in candidate_identity_dirs(split_root, args.include_negatives):
            paths = image_paths(ident_dir)
            if len(paths) < 2:
                continue
            if args.k_support > 0:
                paths = paths[:args.k_support]
            embeddings = embed_paths(model, paths, transform, device, args.batch_size)
            candidates.append({
                "name": ident_dir.name,
                "source": str(ident_dir),
                "paths": paths,
                "prototype": make_proto(embeddings, normalize),
            })

    rows = []
    frame_rows = []
    for candidate in candidates:
        scores = score_against_proto(query_embeddings, candidate["prototype"], normalize, args.metric)
        row = {
            "identity": candidate["name"],
            "source": candidate["source"],
            "support_images": len(candidate["paths"]),
            "query_frames": len(frame_paths),
            "mean_score": float(scores.mean()),
            "max_score": float(scores.max()),
            "topk_frame_mean": topk_mean(scores, args.top_k_frames),
            "min_score": float(scores.min()),
        }
        rows.append(row)
        for frame_path, score in zip(frame_paths, scores):
            frame_rows.append({
                "identity": candidate["name"],
                "frame": str(frame_path),
                "score": float(score),
            })

    rows.sort(key=lambda item: item["topk_frame_mean"], reverse=True)

    # Assign verdict: top-ranked identity is CONFIRMED, all others are IMPOSTOR.
    best_score = rows[0]["topk_frame_mean"]
    for i, row in enumerate(rows):
        row["verdict"] = "CONFIRMED" if i == 0 else "IMPOSTOR"

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["verdict"] + [k for k in rows[0].keys() if k != "verdict"]
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    out_frame_csv = Path(args.out_frame_csv)
    out_frame_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_frame_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["identity", "frame", "score"])
        writer.writeheader()
        writer.writerows(frame_rows)

    score_name = args.metric
    print(f"Loaded {args.checkpoint} (epoch {ckpt.get('epoch')}, val_acc {ckpt.get('val_acc')})")
    print(f"Device: {device} | score: {score_name} | higher is better")
    print(f"Support candidates: {len(support_sets)} from {', '.join(args.support)}")
    if args.query_frames:
        print(f"Query frames: {len(frame_paths)} from {args.query_frames}")
    else:
        print(f"Video frames: {len(frame_paths)} from {args.video} (fps={fps:.2f}, stride={stride} frames)")
    print(f"Scored candidates: {len(rows)} ({args.identity_split}, include_negatives={args.include_negatives})")
    print(f"\n{'rank':>4} {'identity':<48} {'verdict':<10} {'support':>7} {'mean':>8} {'max':>8} {'topk':>8}")
    for rank, row in enumerate(rows[:25], start=1):
        print(
            f"{rank:>4} {row['identity']:<48} {row['verdict']:<10} {row['support_images']:>7} "
            f"{row['mean_score']:>8.4f} {row['max_score']:>8.4f} {row['topk_frame_mean']:>8.4f}"
        )
    print(f"\nBest match: {rows[0]['identity']} ({rows[0]['topk_frame_mean']:.4f})")
    print(f"Saved summary scores -> {out_csv}")
    print(f"Saved per-frame scores -> {out_frame_csv}")
    print(f"Extracted frames -> {Path(args.frame_dir)}")

    # --- MLflow logging ---
    try:
        import mlflow
        import yaml
        cfg_path = Path(__file__).parent.parent / "configs" / "setup.yaml"
        cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
        uri = args.mlflow_tracking_uri or cfg.get("mlflow", {}).get("tracking_uri", "http://192.168.2.1:5000")
        exp = cfg.get("mlflow", {}).get("experiment_name", "uav_few_shot_identification")
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(exp)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_name = Path(args.video).stem if args.video else "query_frames"
        support_name = "_vs_".join(Path(s).name for s in args.support)
        with mlflow.start_run(run_name=f"demo_{support_name}_{video_name}_{ts}"):
            mlflow.log_params({
                "checkpoint": args.checkpoint,
                "support": ", ".join(args.support),
                "video": args.video or args.query_frames,
                "metric": args.metric,
                "n_query_frames": len(frame_paths),
                "n_support_candidates": len(support_sets),
                "top_k_frames": args.top_k_frames,
            })
            for row in rows:
                import re
                safe = re.sub(r"[^a-zA-Z0-9]", "_", row["identity"]).strip("_")
                mlflow.log_metrics({
                    f"{safe}_mean": row["mean_score"],
                    f"{safe}_max": row["max_score"],
                    f"{safe}_topk": row["topk_frame_mean"],
                })
                mlflow.set_tag(f"verdict_{safe}", row["verdict"])
            # Human-readable verdict summary as a tag
            summary_parts = [f"{r['identity']}: {r['verdict']} (topk={r['topk_frame_mean']:.4f})" for r in rows]
            mlflow.set_tag("verdict_summary", " | ".join(summary_parts))
            mlflow.set_tag("best_match", rows[0]["identity"])
            mlflow.log_artifact(str(out_csv), artifact_path="demo")
            mlflow.log_artifact(str(out_frame_csv), artifact_path="demo")
        print(f"MLflow run logged to {uri}")
    except Exception as exc:
        print(f"MLflow logging skipped: {exc}")


if __name__ == "__main__":
    main()
