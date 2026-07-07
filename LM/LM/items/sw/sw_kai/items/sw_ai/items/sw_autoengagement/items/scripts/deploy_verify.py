"""deploy_verify.py — End-to-end identity verification (the working demo).

This is the deployed runtime in one command. For every frame it answers a
single binary question: does the detected UAV match the enrolled target?

    raw frame --[YOLOX detect+crop]--> crop --[ProtoNet embed]-->
    cosine score vs enrolled gallery --[threshold]--> MATCH / UNKNOWN

Input can be a video file (.mp4/.avi/.mov/...) or a folder of frame images.
Output: a per-frame CSV, an optional annotated overlay, and an overall verdict.

Usage:
    # video in, verdict out
    python scripts/deploy_verify.py \
        --model "C:/path/yolox_tiny_airborne_v2_qat.onnx" \
        --checkpoint checkpoints_yolox_crops_mixed_domain/best.pth \
        --gallery galleries/vector_uav.npy \
        --threshold 0.30 \
        --input data/demo/target_flight.mp4 \
        --out_csv csvs/deploy_run.csv \
        --save_overlay out/overlay

    # folder of frames in
    python scripts/deploy_verify.py ... --input data/demo/camera_video_fragmentation_preview
"""

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.uavid.common.constants import IMG_EXTS  # noqa: E402
from src.uavid.inference import Verifier  # noqa: E402
from crop_from_yolox import YOLOXDetector, best_crop_from_frame  # noqa: E402

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}


def heatmap_panel(crop_bgr: np.ndarray, cam: np.ndarray, label: str,
                  score: float, verdict: str, alpha: float = 0.45) -> np.ndarray:
    """Build a side-by-side panel: raw crop | Grad-CAM overlay, with a caption.

    The warm (red/yellow) regions of the overlay are the parts of the UAV that
    contributed most to the match score against the enrolled target.
    """
    heat = cv2.applyColorMap((cam * 255).astype(np.uint8), cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(crop_bgr, 1.0 - alpha, heat, alpha, 0.0)

    h = max(crop_bgr.shape[0], 96)
    raw = cv2.resize(crop_bgr, (int(crop_bgr.shape[1] * h / crop_bgr.shape[0]), h))
    ov = cv2.resize(overlay, (int(overlay.shape[1] * h / overlay.shape[0]), h))
    gap = np.full((h, 6, 3), 255, np.uint8)
    body = np.hstack([raw, gap, ov])

    bar = np.full((28, body.shape[1], 3), 30, np.uint8)
    color = (0, 200, 0) if verdict == "MATCH" else (0, 0, 220)
    cv2.putText(bar, f"{label}  {verdict}  score={score:.3f}", (6, 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return np.vstack([bar, body])


def iter_frames(input_path: Path, frame_stride: int, max_frames: int):
    """Yield (frame_id, label, bgr_image) from a video file or image folder."""
    if input_path.is_file() and input_path.suffix.lower() in VIDEO_EXTS:
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise SystemExit(f"Cannot open video {input_path}")
        idx = yielded = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % frame_stride == 0:
                yield idx, f"frame_{idx:06d}", frame
                yielded += 1
                if max_frames and yielded >= max_frames:
                    break
            idx += 1
        cap.release()
    elif input_path.is_dir():
        paths = sorted(f for f in input_path.rglob("*")
                       if f.suffix.lower() in IMG_EXTS)
        for i, p in enumerate(paths[::frame_stride]):
            if max_frames and i >= max_frames:
                break
            img = cv2.imread(str(p))
            if img is not None:
                yield i, p.name, img
    else:
        raise SystemExit(f"--input must be a video file or image folder: {input_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None,
                    help="YOLOX ONNX detector path. Not needed when --save_crops "
                         "points to a folder that already contains extracted crops.")
    ap.add_argument("--input_size", type=int, default=None)
    ap.add_argument("--conf", type=float, default=0.25, help="YOLOX confidence.")
    ap.add_argument("--iou", type=float, default=0.45, help="YOLOX NMS IoU.")
    ap.add_argument("--pad", type=float, default=0.15, help="Crop padding.")
    ap.add_argument("--min_px", type=int, default=15, help="Min crop side (px).")

    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--gallery", required=True)
    ap.add_argument("--threshold", type=float, required=True,
                    help="MATCH if score >= threshold (from calibrate_threshold.py).")

    ap.add_argument("--input", default=None,
                    help="Video file OR folder of frames. Not needed when "
                         "--save_crops points to existing extracted crops.")
    ap.add_argument("--frame_stride", type=int, default=1,
                    help="Process every Nth frame.")
    ap.add_argument("--max_frames", type=int, default=0, help="0 = all.")

    ap.add_argument("--min_votes", type=int, default=3,
                    help="Min MATCH frames to confirm the target overall.")
    ap.add_argument("--min_match_frac", type=float, default=0.25,
                    help="Min MATCH fraction (of detected frames) to confirm.")
    ap.add_argument("--require_median", action="store_true", default=True,
                    help="Also require the median frame score >= threshold "
                         "(robust gate; rejects impostors that only graze the bar). "
                         "On by default.")
    ap.add_argument("--no_require_median", dest="require_median",
                    action="store_false",
                    help="Disable the median-score gate (use the old "
                         "fraction-only rule).")

    ap.add_argument("--out_csv", default=None)
    ap.add_argument("--save_overlay", default=None,
                    help="Folder to write annotated frames (boxes + verdict).")
    ap.add_argument("--save_crops", default=None,
                    help="Folder to write each YOLOX crop extracted from the input "
                         "(filename encodes verdict + score).")
    ap.add_argument("--save_heatmaps", default=None,
                    help="Folder to write Grad-CAM panels for the highest- and "
                         "lowest-scoring detected frames (warm regions = parts of "
                         "the UAV that drove the match to the enrolled target).")
    ap.add_argument("--heatmap_topk", type=int, default=5,
                    help="How many top (and bottom) scoring frames to visualize "
                         "with Grad-CAM heatmaps.")
    args = ap.parse_args()

    vf = Verifier(args.checkpoint, args.gallery)
    print(f"threshold = {args.threshold:.4f}  score = {vf.score_name}")

    overlay_dir = Path(args.save_overlay) if args.save_overlay else None
    crops_dir = Path(args.save_crops) if args.save_crops else None

    # If the crops folder already holds extracted crops, reuse them instead of
    # re-running video extraction + YOLOX detection.
    cached_crops = []
    if crops_dir and crops_dir.exists():
        cached_crops = sorted(f for f in crops_dir.glob("*")
                              if f.suffix.lower() in IMG_EXTS)

    rows = []
    n_total = n_detected = n_match = 0
    # (label, score, verdict, crop_bgr) for detected frames, used to pick the
    # highest/lowest scoring frames for Grad-CAM heatmaps at the end.
    detected_crops = []
    want_heatmaps = bool(args.save_heatmaps) and args.heatmap_topk > 0

    if cached_crops:
        print(f"Reusing {len(cached_crops)} existing crops from {crops_dir} "
              f"(skipping video extraction + YOLOX detection)")
        if overlay_dir:
            print("note: --save_overlay is ignored when reusing cached crops "
                  "(full frames are not available)")
        for p in cached_crops:
            crop = cv2.imread(str(p))
            if crop is None:
                continue
            n_total += 1
            n_detected += 1
            score = float(vf.score(vf.embed_bgr([crop]))[0])
            is_match = score >= args.threshold
            n_match += int(is_match)
            verdict = "MATCH" if is_match else "UNKNOWN"
            crop_px = min(crop.shape[0], crop.shape[1])
            rows.append({"frame": p.stem, "detected": 1, "det_conf": "",
                         "crop_px": crop_px, "score": round(score, 4),
                         "verdict": verdict})
            if want_heatmaps:
                detected_crops.append((p.stem, score, verdict, crop.copy()))
    else:
        if not args.input:
            raise SystemExit("--input is required when no extracted crops are "
                             "cached in --save_crops.")
        if not args.model:
            raise SystemExit("--model is required to run YOLOX detection on "
                             "--input (no cached crops to reuse).")
        detector = YOLOXDetector(args.model, args.input_size, args.conf, args.iou)
        if overlay_dir:
            overlay_dir.mkdir(parents=True, exist_ok=True)
        if crops_dir:
            crops_dir.mkdir(parents=True, exist_ok=True)

        for frame_id, label, frame in iter_frames(
                Path(args.input), max(1, args.frame_stride), args.max_frames):
            n_total += 1
            dets = detector.detect(frame)
            crop, det_conf = best_crop_from_frame(frame, dets, args.pad, args.min_px)

            if crop is None:
                rows.append({"frame": label, "detected": 0, "det_conf": 0.0,
                             "crop_px": 0, "score": "", "verdict": "NO_DETECTION"})
                if overlay_dir:
                    cv2.imwrite(str(overlay_dir / f"{label}.jpg"), frame)
                continue

            n_detected += 1
            score = float(vf.score(vf.embed_bgr([crop]))[0])
            is_match = score >= args.threshold
            n_match += int(is_match)
            verdict = "MATCH" if is_match else "UNKNOWN"
            crop_px = min(crop.shape[0], crop.shape[1])
            rows.append({"frame": label, "detected": 1, "det_conf": round(det_conf, 4),
                         "crop_px": crop_px, "score": round(score, 4), "verdict": verdict})
            if want_heatmaps:
                detected_crops.append((label, score, verdict, crop.copy()))

            if crops_dir:
                cv2.imwrite(str(crops_dir / f"{label}.jpg"), crop,
                            [cv2.IMWRITE_JPEG_QUALITY, 95])

            if overlay_dir:
                box, _ = sorted(dets, key=lambda x: -x[1])[0]
                x1, y1, x2, y2 = [int(v) for v in box]
                color = (0, 200, 0) if is_match else (0, 0, 220)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{verdict} {score:.2f}", (x1, max(15, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                cv2.imwrite(str(overlay_dir / f"{label}.jpg"), frame)

    # ── Summary / overall verdict ────────────────────────────────────────────
    all_scores = np.array([r["score"] for r in rows
                           if isinstance(r["score"], (int, float))], dtype=float)
    median_score = float(np.median(all_scores)) if all_scores.size else 0.0
    match_frac = n_match / n_detected if n_detected else 0.0
    median_ok = (median_score >= args.threshold) if args.require_median else True
    confirmed = (n_match >= args.min_votes and match_frac >= args.min_match_frac
                 and median_ok)
    overall = "TARGET CONFIRMED" if confirmed else "TARGET NOT CONFIRMED"

    rule = (f">= {args.min_votes} matches AND >= {args.min_match_frac*100:.0f}% "
            f"of detected")
    if args.require_median:
        rule += f" AND median >= {args.threshold:.2f}"

    print(f"\n{'='*56}")
    print(f"frames processed : {n_total}")
    print(f"frames w/ detect : {n_detected}")
    print(f"frames >= thresh : {n_match}  ({match_frac*100:.1f}% of detected)")
    print(f"median score     : {median_score:.4f}  (typical frame; robust to outliers)")
    print(f"decision rule    : {rule}")
    print(f"{'='*56}")
    print(f"VERDICT: {overall}")
    print(f"{'='*56}")

    if args.out_csv:
        out = Path(args.out_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nPer-frame results -> {out}")
    if overlay_dir:
        print(f"Annotated frames -> {overlay_dir}")
    if crops_dir:
        print(f"Extracted crops  -> {crops_dir}")

    # ── Grad-CAM heatmaps for the most/least convincing frames ───────────────
    if want_heatmaps:
        if not detected_crops:
            print("\nNo detected frames -> no heatmaps to write.")
        else:
            heat_dir = Path(args.save_heatmaps)
            heat_dir.mkdir(parents=True, exist_ok=True)
            ranked = sorted(detected_crops, key=lambda r: r[1], reverse=True)
            k = min(args.heatmap_topk, len(ranked))
            top = ranked[:k]
            # Bottom-k that don't overlap the top-k.
            bottom = [r for r in ranked[-k:] if r not in top]

            def _dump(items, tag):
                for rank, (label, score, verdict, crop) in enumerate(items, 1):
                    cam, _ = vf.gradcam_bgr(crop)
                    panel = heatmap_panel(crop, cam, label, score, verdict)
                    fname = f"{tag}_{rank:02d}_{label}_score{score:.3f}.jpg"
                    cv2.imwrite(str(heat_dir / fname), panel,
                                [cv2.IMWRITE_JPEG_QUALITY, 95])

            _dump(top, "top")
            _dump(bottom, "low")
            print(f"Grad-CAM heatmaps -> {heat_dir}  "
                  f"({len(top)} top + {len(bottom)} low scoring frames; "
                  f"warm = UAV regions that confirmed the target)")


if __name__ == "__main__":
    main()
