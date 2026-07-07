"""experiment_yolox_classify.py — Standalone YOLOX detect + classify experiment.

This is an EXPERIMENT, not part of the ProtoNet deployment pipeline. It answers a
single question: given some images and/or a video, does the airborne YOLOX model
correctly detect, crop, and *classify* the object (e.g. drone / helicopter /
bird / airplane)?

Unlike scripts/crop_from_yolox.py (which only keeps the best crop and throws the
class label away), this script keeps every detection, reports its class id +
confidence, draws annotated overlays, and saves per-detection crops.

The airborne YOLOX ONNX model exports two outputs:
    dets   : (1, N, 5)  -> x1, y1, x2, y2, score   (already NMS-ed, model space)
    labels : (1, N)     -> class id per detection

The bundled dataset.yaml only ships generic placeholder names
(category_1..category_4), so the real semantic class names are NOT known from the
model files. Pass them yourself once you know the mapping, e.g.:

    --class_names "drone,helicopter,bird,airplane"

Preprocessing matches the model's param.yaml: resize-with-pad to 960x960, padding
at the top-left CORNER, pad colour 114, BGR->RGB, no normalization.

Usage:
    python scripts/experiment_yolox_classify.py \
        --input data/experiment_classification_drone_images \
        --out out/experiment_yolox_classify \
        --conf 0.25

`--input` may be a single image, a single video, or a folder containing any mix
of images and videos. Video frames are sampled every --every_sec seconds.
"""

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

DEFAULT_MODEL = (
    r"C:\Users\tsa3\Downloads\yolox_tiny_airborne_v2_qat"
    r"\yolox_tiny_airborne_v2_qat.onnx\model\yolox_tiny_airborne_v2_qat.onnx"
)

# Distinct BGR colours for up to a handful of classes.
PALETTE = [
    (0, 0, 255), (0, 255, 0), (255, 128, 0), (0, 255, 255),
    (255, 0, 255), (255, 255, 0), (128, 0, 255), (0, 128, 255),
]


# ─── YOLOX pre/post-processing (corner letterbox, matches param.yaml) ─────────

def letterbox_corner(img: np.ndarray, target: int):
    """Resize keeping aspect ratio, pad to the bottom/right (image at top-left)."""
    h, w = img.shape[:2]
    scale = target / max(h, w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((target, target, 3), 114, dtype=np.uint8)
    canvas[:nh, :nw] = resized
    return canvas, scale


def preprocess(img_bgr: np.ndarray, input_size: int):
    lb, scale = letterbox_corner(img_bgr, input_size)
    x = lb[:, :, ::-1].astype(np.float32)        # BGR -> RGB, no normalization
    x = np.transpose(x, (2, 0, 1))[None]         # NCHW
    return x, scale


def decode(dets: np.ndarray, labels: np.ndarray, scale: float,
           conf_thr: float, orig_h: int, orig_w: int):
    """Map model-space (dets, labels) back to original image coords."""
    dets = np.asarray(dets)
    labels = np.asarray(labels)
    if dets.ndim == 3:
        dets = dets[0]
    if labels.ndim == 2:
        labels = labels[0]
    if dets.size == 0:
        return []

    boxes = dets[:, :4].astype(np.float32).copy()
    scores = dets[:, 4].astype(np.float32)

    keep = scores > conf_thr
    boxes, scores, labels = boxes[keep], scores[keep], labels[keep]
    if boxes.shape[0] == 0:
        return []

    # Corner padding -> just undo the scale.
    boxes /= scale
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, orig_w)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, orig_h)

    out = []
    for box, score, label in zip(boxes, scores, labels):
        out.append((box, float(score), int(label)))
    out.sort(key=lambda d: -d[1])
    return out


class YOLOXDetector:
    def __init__(self, onnx_path: str, input_size: int | None,
                 conf: float, iou: float):
        import onnxruntime as ort
        providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                     if "CUDAExecutionProvider" in ort.get_available_providers()
                     else ["CPUExecutionProvider"])
        self.sess = ort.InferenceSession(onnx_path, providers=providers)
        self.input_name = self.sess.get_inputs()[0].name
        self.input_size = input_size or self._infer_input_size()
        self.conf = conf
        print(f"Loaded YOLOX from {onnx_path}")
        print(f"  input_size={self.input_size} | providers={self.sess.get_providers()}")

    def _infer_input_size(self) -> int:
        shape = self.sess.get_inputs()[0].shape
        if len(shape) >= 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
            if shape[2] == shape[3]:
                return shape[2]
        print("  Could not infer square input size; defaulting to 960")
        return 960

    def detect(self, img_bgr: np.ndarray):
        h, w = img_bgr.shape[:2]
        x, scale = preprocess(img_bgr, self.input_size)
        outs = self.sess.run(None, {self.input_name: x})
        dets = outs[0]
        labels = outs[1] if len(outs) > 1 else np.zeros((1, np.asarray(dets).shape[1]))
        return decode(dets, labels, scale, self.conf, h, w)


# ─── Drawing / saving ────────────────────────────────────────────────────────

def class_name(label: int, names: list[str] | None) -> str:
    if names and 0 <= label < len(names):
        return names[label]
    # Fall back to the model's generic placeholder naming (1-indexed categories).
    return f"category_{label + 1}"


def draw_overlay(img_bgr: np.ndarray, detections, names):
    out = img_bgr.copy()
    for box, score, label in detections:
        x1, y1, x2, y2 = (int(v) for v in box)
        color = PALETTE[label % len(PALETTE)]
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        text = f"{class_name(label, names)} {score:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        ty = max(0, y1 - th - 4)
        cv2.rectangle(out, (x1, ty), (x1 + tw + 4, ty + th + 4), color, -1)
        cv2.putText(out, text, (x1 + 2, ty + th + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return out


def crop_box(img_bgr: np.ndarray, box, pad: float, min_px: int):
    h, w = img_bgr.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    if bw < min_px or bh < min_px:
        return None
    pw, ph = bw * pad, bh * pad
    x1c, y1c = max(0, int(x1 - pw)), max(0, int(y1 - ph))
    x2c, y2c = min(w, int(x2 + pw)), min(h, int(y2 + ph))
    crop = img_bgr[y1c:y2c, x1c:x2c]
    return crop if crop.size else None


# ─── Processing ──────────────────────────────────────────────────────────────

def collect_inputs(input_path: Path):
    """Return (image_paths, video_paths)."""
    if input_path.is_file():
        ext = input_path.suffix.lower()
        if ext in IMG_EXTS:
            return [input_path], []
        if ext in VIDEO_EXTS:
            return [], [input_path]
        return [], []
    images = sorted(f for f in input_path.rglob("*") if f.suffix.lower() in IMG_EXTS)
    videos = sorted(f for f in input_path.rglob("*") if f.suffix.lower() in VIDEO_EXTS)
    return images, videos


def process_frame(name, img, detector, names, args, overlay_dir, crops_dir, writer):
    detections = detector.detect(img)
    overlay = draw_overlay(img, detections, names)
    cv2.imwrite(str(overlay_dir / f"{name}.jpg"), overlay,
                [cv2.IMWRITE_JPEG_QUALITY, 92])

    for di, (box, score, label) in enumerate(detections):
        crop = crop_box(img, box, args.pad, args.min_px)
        crop_rel = ""
        if crop is not None:
            cname = class_name(label, names)
            crop_path = crops_dir / f"{name}_det{di:02d}_{cname}_{score:.2f}.jpg"
            cv2.imwrite(str(crop_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
            crop_rel = crop_path.name
        x1, y1, x2, y2 = (round(float(v), 1) for v in box)
        writer.writerow([name, di, label, class_name(label, names),
                         round(score, 4), x1, y1, x2, y2, crop_rel])
    return len(detections)


def main():
    ap = argparse.ArgumentParser(
        description="Experiment: YOLOX airborne detect + classify on images/video.",
        formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--input", required=True,
                    help="Image, video, or folder containing images and/or videos.")
    ap.add_argument("--out", default="out/experiment_yolox_classify",
                    help="Output directory for overlays, crops, and the CSV.")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="YOLOX ONNX model path.")
    ap.add_argument("--input_size", type=int, default=None,
                    help="Override model input size (inferred from ONNX by default).")
    ap.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    ap.add_argument("--iou", type=float, default=0.45, help="(Unused; model NMS is built in.)")
    ap.add_argument("--class_names", default=None,
                    help="Comma-separated class names to label categories, e.g. "
                         "\"drone,helicopter,bird,airplane\". Order = label id 0..N.")
    ap.add_argument("--every_sec", type=float, default=0.5,
                    help="Sample one video frame every N seconds.")
    ap.add_argument("--max_frames", type=int, default=0,
                    help="Max frames per video (0 = no limit).")
    ap.add_argument("--pad", type=float, default=0.15, help="Crop padding fraction.")
    ap.add_argument("--min_px", type=int, default=10, help="Skip crops smaller than this.")
    args = ap.parse_args()

    names = ([n.strip() for n in args.class_names.split(",")]
             if args.class_names else None)

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    images, videos = collect_inputs(input_path)
    if not images and not videos:
        raise SystemExit(
            f"No images or videos found in {input_path}. "
            f"Supported images: {sorted(IMG_EXTS)}; videos: {sorted(VIDEO_EXTS)}")

    out_dir = Path(args.out)
    overlay_dir = out_dir / "overlays"
    crops_dir = out_dir / "crops"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "detections.csv"

    detector = YOLOXDetector(args.model, args.input_size, args.conf, args.iou)

    print(f"\nImages: {len(images)} | Videos: {len(videos)}")
    print(f"Confidence threshold: {args.conf}")
    if names:
        print(f"Class names: {names}")
    else:
        print("Class names: not provided -> reporting generic category_<id+1>")
    print(f"Output -> {out_dir}\n")

    total_frames = 0
    total_dets = 0
    class_counts: dict[int, int] = {}

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["source", "det_index", "label_id", "class_name",
                         "score", "x1", "y1", "x2", "y2", "crop_file"])

        for img_path in images:
            img = cv2.imread(str(img_path))
            if img is None:
                print(f"  [skip] cannot read {img_path.name}")
                continue
            name = f"img_{img_path.stem}"
            n = process_frame(name, img, detector, names, args,
                              overlay_dir, crops_dir, writer)
            total_frames += 1
            total_dets += n
            print(f"  {img_path.name:<40} detections={n}")

        for vid_path in videos:
            cap = cv2.VideoCapture(str(vid_path), cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap = cv2.VideoCapture(str(vid_path))
            if not cap.isOpened():
                print(f"  [skip] cannot open video {vid_path.name}")
                continue
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            interval = max(1, int(round(fps * args.every_sec)))
            print(f"  video {vid_path.name} | fps={fps:.1f} | "
                  f"sampling every {interval} frames")
            frame_idx = saved = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_idx % interval == 0:
                    name = f"vid_{vid_path.stem}_f{saved:05d}"
                    n = process_frame(name, frame, detector, names, args,
                                      overlay_dir, crops_dir, writer)
                    total_frames += 1
                    total_dets += n
                    saved += 1
                    if args.max_frames and saved >= args.max_frames:
                        break
                frame_idx += 1
            cap.release()
            print(f"    sampled {saved} frames")

    # Tally classes from the CSV we just wrote.
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            lid = int(row["label_id"])
            class_counts[lid] = class_counts.get(lid, 0) + 1

    print(f"\n{'='*60}")
    print(f"Frames processed : {total_frames}")
    print(f"Total detections : {total_dets}")
    if class_counts:
        print("Detections per class:")
        for lid in sorted(class_counts):
            print(f"  label {lid} ({class_name(lid, names)}): {class_counts[lid]}")
    else:
        print("No detections above the confidence threshold.")
    print(f"\nOverlays -> {overlay_dir}")
    print(f"Crops    -> {crops_dir}")
    print(f"CSV      -> {csv_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
