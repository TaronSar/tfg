"""Build the ProtoNet identity dataset from full-frame images using YOLOX.

Takes raw full-frame images (organized by identity folder or a flat detection
dataset), runs Embention's YOLOX-tiny ONNX model, and saves the best UAV crop
per image to the identity-organized structure that ProtoNet training expects.

Input layout (two modes):

  MODE A — already organized by identity (e.g. Anti-UAV sequences):
    raw/
      train/
        identity_A/  frame_001.jpg ...
        identity_B/  ...
      val/
        identity_X/  ...

  MODE B — flat folder with annotations (YOLO .txt format), one identity:
    raw/  frame_001.jpg  frame_001.txt  ...

Output (same in both modes):
    data/
      train/
        identity_A/  crop_0001.jpg ...
      val/
        identity_X/  ...

Usage:
    # Mode A - identity folders, use YOLOX to crop each frame
    python -m src.uavid.preprocessing.yolox_crops \
        --model yolox_tiny.onnx --raw_root raw/ --out_root data/

    # Mode A - identity folders, use YOLO .txt annotations instead of running YOLOX
    python -m src.uavid.preprocessing.yolox_crops \
        --use_annotations --raw_root raw/ --out_root data/

    # Mode B - flat folder, YOLOX auto-detects, single identity name
    python -m src.uavid.preprocessing.yolox_crops \
        --model yolox_tiny.onnx --flat raw/ --identity my_uav --split train --out_root data/

    # Just visualize detections without saving
    python -m src.uavid.preprocessing.yolox_crops \
        --model yolox_tiny.onnx --raw_root raw/ --out_root data/ --preview

Crop quality:
    --pad 0.15          15% padding around the tight bbox (default)
    --min_px 15         discard crops smaller than 15px on any side
    --conf 0.25         YOLOX confidence threshold
    --iou 0.45          NMS IoU threshold
    --max_crops N       optional max crops to save per identity
"""

import argparse
from pathlib import Path

import cv2
import numpy as np

from src.uavid.common.constants import IMG_EXTS


def letterbox(img: np.ndarray, target: int = 640):
    """Resize with padding (letterbox) to a square target size.

    Args:
        img: Input BGR image.
        target: Output side length in pixels (default 640).

    Returns:
        Tuple ``(canvas, scale, pad_top, pad_left)`` where ``canvas`` is the
        padded image, ``scale`` is the resize factor, and the pad offsets give
        the position of the original content inside the canvas.
    """
    h, w = img.shape[:2]
    scale = target / max(h, w)
    nh, nw = int(h * scale), int(w * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((target, target, 3), 114, dtype=np.uint8)
    pad_top = (target - nh) // 2
    pad_left = (target - nw) // 2
    canvas[pad_top : pad_top + nh, pad_left : pad_left + nw] = resized
    return canvas, scale, pad_top, pad_left


def preprocess(img_bgr: np.ndarray, input_size: int = 640) -> tuple:
    """Letterbox and convert a BGR image to a NCHW float32 tensor for YOLOX.

    Args:
        img_bgr: Input BGR image (uint8 HxWx3).
        input_size: Model input resolution (square, default 640).

    Returns:
        Tuple ``(x, scale, pad_top, pad_left)`` ready for ONNX inference.
    """
    lb, scale, pt, pl = letterbox(img_bgr, input_size)
    x = lb[:, :, ::-1].astype(np.float32)  # BGR->RGB, no normalization (YOLOX style)
    x = np.transpose(x, (2, 0, 1))[None]  # NCHW
    return x, scale, pt, pl


def nms(boxes, scores, iou_thr):
    """Greedy IoU-based non-maximum suppression.

    Args:
        boxes: Bounding boxes, shape ``(N, 4)`` in ``x1,y1,x2,y2`` format.
        scores: Confidence scores, shape ``(N,)``.
        iou_thr: IoU threshold above which overlapping boxes are suppressed.

    Returns:
        List of kept indices in descending score order.
    """
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        w = np.maximum(0, xx2 - xx1)
        h = np.maximum(0, yy2 - yy1)
        inter = w * h
        area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        union = area[i] + area[order[1:]] - inter
        iou = inter / (union + 1e-6)
        order = order[1:][iou < iou_thr]
    return keep


def postprocess(
    output: np.ndarray,
    scale: float,
    pad_top: int,
    pad_left: int,
    conf_thr: float,
    iou_thr: float,
    orig_h: int,
    orig_w: int,
    input_size: int = 640,
):
    """Decode YOLOX raw output to bounding boxes in original image coordinates.

    Args:
        output: Raw ONNX session output (list/array from ``sess.run``).
        scale: Letterbox resize factor returned by ``preprocess``.
        pad_top: Top padding offset returned by ``preprocess``.
        pad_left: Left padding offset returned by ``preprocess``.
        conf_thr: Confidence threshold; detections below it are discarded.
        iou_thr: IoU threshold for NMS.
        orig_h: Original image height in pixels.
        orig_w: Original image width in pixels.
        input_size: Model input resolution used during preprocessing.

    Returns:
        List of ``(box, score)`` tuples where ``box`` is a length-4 array
        ``[x1, y1, x2, y2]`` in original image pixel coordinates.
    """
    if isinstance(output, (list, tuple)):
        dets = np.asarray(output[0])
        if dets.ndim == 3:
            dets = dets[0]
        if dets.ndim == 2 and dets.shape[1] == 5:
            boxes = dets[:, :4]
            scores = dets[:, 4]
            mask = scores > conf_thr
            if not mask.any():
                return []
            boxes = boxes[mask]
            scores = scores[mask]
            boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_left) / scale
            boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_top) / scale
            boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, orig_w)
            boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, orig_h)
            keep = nms(boxes, scores, iou_thr)
            return [(boxes[k], scores[k]) for k in keep]
        output = output[0]

    pred = output[0]  # (num_anchors, 5+num_classes) — YOLOX decodes in model
    obj_score = pred[:, 4]
    cls_score = pred[:, 5:].max(axis=1)
    score = obj_score * cls_score
    mask = score > conf_thr
    if not mask.any():
        return []
    boxes_cxcywh = pred[mask, :4]
    scores = score[mask]
    # cx,cy,w,h in letterboxed coords -> x1,y1,x2,y2
    cx, cy, bw, bh = (boxes_cxcywh[:, i] for i in range(4))
    x1 = cx - bw / 2
    y1 = cy - bh / 2
    x2 = cx + bw / 2
    y2 = cy + bh / 2
    # Remove letterbox padding, then undo scale
    x1 = (x1 - pad_left) / scale
    x2 = (x2 - pad_left) / scale
    y1 = (y1 - pad_top) / scale
    y2 = (y2 - pad_top) / scale
    x1 = np.clip(x1, 0, orig_w)
    x2 = np.clip(x2, 0, orig_w)
    y1 = np.clip(y1, 0, orig_h)
    y2 = np.clip(y2, 0, orig_h)
    boxes = np.stack([x1, y1, x2, y2], axis=1)
    keep = nms(boxes, scores, iou_thr)
    return [(boxes[k], scores[k]) for k in keep]


class YOLOXDetector:
    def __init__(
        self, onnx_path: str, input_size: int | None = None, conf: float = 0.25, iou: float = 0.45
    ):
        """Initialise the YOLOX ONNX detector.

        Args:
            onnx_path: Path to the YOLOX ONNX model file.
            input_size: Model input resolution. Inferred from the ONNX graph
                when ``None`` (requires a static spatial shape).
            conf: Confidence score threshold (default 0.25).
            iou: IoU threshold for NMS (default 0.45).
        """
        try:
            import torch  # noqa: F401
        except ImportError:
            pass
        import onnxruntime as ort

        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if "CUDAExecutionProvider" in ort.get_available_providers()
            else ["CPUExecutionProvider"]
        )
        self.sess = ort.InferenceSession(onnx_path, providers=providers)
        self.input_name = self.sess.get_inputs()[0].name
        self.input_size = input_size or self._infer_input_size()
        self.conf = conf
        self.iou = iou
        print(
            f"Loaded YOLOX from {onnx_path} | input_size={self.input_size} | "
            f"providers={self.sess.get_providers()}"
        )

    def _infer_input_size(self) -> int:
        """Read the static spatial input size from the ONNX model graph."""
        shape = self.sess.get_inputs()[0].shape
        if len(shape) >= 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
            if shape[2] == shape[3]:
                return shape[2]
            raise ValueError(f"Expected square YOLOX input, got model shape {shape}")
        print("Could not infer static ONNX input size; using default input_size=640")
        return 640

    def detect(self, img_bgr: np.ndarray):
        """Run YOLOX inference and return detections in original image coordinates.

        Args:
            img_bgr: Input BGR image (uint8 HxWx3).

        Returns:
            List of ``(box, score)`` tuples (see ``postprocess``).
        """
        h, w = img_bgr.shape[:2]
        x, scale, pt, pl = preprocess(img_bgr, self.input_size)
        out = self.sess.run(None, {self.input_name: x})
        return postprocess(out, scale, pt, pl, self.conf, self.iou, h, w, self.input_size)


def extract_crop(
    img_bgr: np.ndarray, box, pad: float = 0.15, min_px: int = 15
) -> np.ndarray | None:
    """Crop a padded bounding-box region from an image.

    Args:
        img_bgr: Source BGR image.
        box: Bounding box ``[x1, y1, x2, y2]`` in pixel coordinates.
        pad: Fractional padding added to each side of the tight bbox.
        min_px: Minimum allowed side length of the tight box; returns ``None``
            if the box is smaller than this on either axis.

    Returns:
        Cropped BGR region, or ``None`` if the box is too small or empty.
    """
    h, w = img_bgr.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    if bw < min_px or bh < min_px:
        return None
    pw, ph = bw * pad, bh * pad
    x1c = max(0, int(x1 - pw))
    y1c = max(0, int(y1 - ph))
    x2c = min(w, int(x2 + pw))
    y2c = min(h, int(y2 + ph))
    crop = img_bgr[y1c:y2c, x1c:x2c]
    if crop.size == 0:
        return None
    return crop


def best_crop_from_frame(img_bgr: np.ndarray, detections: list, pad: float, min_px: int):
    """Return the highest-confidence valid crop from a single frame.

    Iterates detections in descending confidence order and returns the first
    crop that passes the ``min_px`` size filter.

    Args:
        img_bgr: Source BGR image.
        detections: List of ``(box, score)`` tuples from ``YOLOXDetector.detect``.
        pad: Fractional padding passed to ``extract_crop``.
        min_px: Minimum side length threshold passed to ``extract_crop``.

    Returns:
        Tuple ``(crop, score)`` for the best detection, or ``(None, 0.0)`` if
        no detection passes the filter.
    """
    for box, score in sorted(detections, key=lambda x: -x[1]):
        crop = extract_crop(img_bgr, box, pad, min_px)
        if crop is not None:
            return crop, score
    return None, 0.0


def crop_from_annotation(
    img_bgr: np.ndarray, txt_path: Path, pad: float, min_px: int, target_cls=None
):
    """Extract the best crop from YOLO-format annotation labels.

    Args:
        img_bgr: Source BGR image.
        txt_path: Path to the corresponding YOLO ``.txt`` annotation file.
        pad: Fractional padding passed to ``extract_crop``.
        min_px: Minimum side length threshold passed to ``extract_crop``.
        target_cls: If given, only boxes of this class index are used.

    Returns:
        Tuple ``(crop, score)`` for the highest-confidence annotation box,
        or ``(None, 0.0)`` if no valid crop is found.
    """
    h, w = img_bgr.shape[:2]
    crops = []
    for line in txt_path.read_text().strip().splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        cls = int(parts[0])
        if target_cls is not None and cls != target_cls:
            continue
        cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
        x1 = (cx - bw / 2) * w
        y1 = (cy - bh / 2) * h
        x2 = (cx + bw / 2) * w
        y2 = (cy + bh / 2) * h
        conf = float(parts[5]) if len(parts) > 5 else 1.0
        crop = extract_crop(img_bgr, [x1, y1, x2, y2], pad, min_px)
        if crop is not None:
            crops.append((crop, conf))
    if not crops:
        return None, 0.0
    crops.sort(key=lambda x: -x[1])
    return crops[0]


def process_identity_folder(
    img_dir: Path,
    out_dir: Path,
    detector,
    pad: float,
    min_px: int,
    max_crops: int | None,
    use_annotations: bool,
    target_cls,
    preview: bool,
    args,
):
    """Extract and save crops for a single identity folder.

    Args:
        img_dir: Directory of source frames for one identity.
        out_dir: Destination directory; created if it does not exist.
        detector: ``YOLOXDetector`` instance, or ``None`` when
            ``use_annotations`` is ``True``.
        pad: Fractional padding passed to ``extract_crop``.
        min_px: Minimum crop side length; smaller crops are skipped.
        max_crops: Stop after saving this many crops. ``None`` processes all.
        use_annotations: If ``True``, read YOLO ``.txt`` files instead of
            running the detector.
        target_cls: Class index filter for annotation mode.
        preview: If ``True``, display each crop interactively before saving.
        args: Parsed ``argparse.Namespace`` (reserved for future use).

    Returns:
        Tuple ``(saved, skipped)`` counts.
    """
    img_paths = sorted(f for f in img_dir.rglob("*") if f.suffix.lower() in IMG_EXTS)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    skipped = 0

    for img_path in img_paths:
        if max_crops is not None and saved >= max_crops:
            break
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  [skip] cannot read {img_path.name}")
            continue

        if use_annotations:
            txt = img_path.with_suffix(".txt")
            if not txt.exists():
                skipped += 1
                continue
            crop, score = crop_from_annotation(img, txt, pad, min_px, target_cls)
        else:
            dets = detector.detect(img)
            crop, score = best_crop_from_frame(img, dets, pad, min_px)

        if crop is None:
            skipped += 1
            continue

        if preview:
            cv2.imshow("crop", crop)
            key = cv2.waitKey(0)
            if key == ord("q"):
                cv2.destroyAllWindows()
                return saved, skipped

        out_path = out_dir / f"crop_{saved:04d}.jpg"
        cv2.imwrite(str(out_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        saved += 1

    return saved, skipped


def main():
    """CLI entry point for the crop-extraction pipeline."""
    ap = argparse.ArgumentParser(
        description="Build ProtoNet identity dataset from full frames using YOLOX.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Model
    ap.add_argument(
        "--model", default=None, help="Path to YOLOX ONNX model. Omit if --use_annotations."
    )
    ap.add_argument(
        "--input_size",
        type=int,
        default=None,
        help="YOLOX input resolution. Omit to infer it from the ONNX model.",
    )
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.45)

    # Input — mode A (identity folders)
    ap.add_argument(
        "--raw_root", default=None, help="Root with train/val/<identity>/ subfolders (Mode A)."
    )
    # Input — mode B (flat folder, single identity)
    ap.add_argument("--flat", default=None, help="Flat folder of images for one identity (Mode B).")
    ap.add_argument("--identity", default=None, help="Identity name for --flat mode.")
    ap.add_argument(
        "--split",
        default="train",
        choices=["train", "val"],
        help="Which split to place flat-mode crops into.",
    )

    # Annotation mode
    ap.add_argument(
        "--use_annotations",
        action="store_true",
        help="Use YOLO .txt annotations instead of running YOLOX.\n"
        "Expects <image>.txt alongside each image.",
    )
    ap.add_argument(
        "--target_cls",
        type=int,
        default=None,
        help="Only use this class index from annotations (e.g. 0 for drone).",
    )

    # Output
    ap.add_argument(
        "--out_root", default="data", help="Output root (will contain train/ and val/ splits)."
    )

    # Crop settings
    ap.add_argument(
        "--pad",
        type=float,
        default=0.15,
        help="Fractional padding around bbox (0.15 = 15%% each side).",
    )
    ap.add_argument(
        "--min_px",
        type=int,
        default=15,
        help="Discard crops smaller than this on any side (pixels).",
    )
    ap.add_argument(
        "--max_crops",
        type=int,
        default=None,
        help="Optional max crops to save per identity. Omit to process all images.",
    )
    ap.add_argument(
        "--preview",
        action="store_true",
        help="Show each crop before saving. Press any key to continue, Q to quit.",
    )
    ap.add_argument(
        "--copy_enrollment",
        default=None,
        help="If set, copy this enrollment folder into <out_root>/enrollment after cropping.",
    )
    ap.add_argument(
        "--manifest_out",
        default=None,
        help="If set, write a DVC dataset manifest JSON to this path after cropping.",
    )

    args = ap.parse_args()

    if not args.use_annotations and args.model is None:
        ap.error("Provide --model OR --use_annotations")
    if args.raw_root is None and args.flat is None:
        ap.error("Provide --raw_root (Mode A) or --flat + --identity (Mode B)")

    detector = (
        YOLOXDetector(args.model, args.input_size, args.conf, args.iou)
        if not args.use_annotations
        else None
    )

    out_root = Path(args.out_root)
    total_saved = total_skipped = 0

    if args.raw_root:
        raw_root = Path(args.raw_root)
        splits = ["train", "val"]
        for split in splits:
            split_dir = raw_root / split
            if not split_dir.exists():
                continue
            ident_dirs = sorted(p for p in split_dir.iterdir() if p.is_dir())
            print(f"\n{'─' * 50}")
            print(f"Split: {split}  |  {len(ident_dirs)} identities")
            print(f"{'─' * 50}")
            for ident_dir in ident_dirs:
                saved, skipped = process_identity_folder(
                    ident_dir,
                    out_root / split / ident_dir.name,
                    detector,
                    args.pad,
                    args.min_px,
                    args.max_crops,
                    args.use_annotations,
                    args.target_cls,
                    args.preview,
                    args,
                )
                print(f"  {ident_dir.name:<30} saved={saved:3d}  skipped={skipped:3d}")
                total_saved += saved
                total_skipped += skipped

    elif args.flat:
        if not args.identity:
            ap.error("--flat requires --identity")
        flat_dir = Path(args.flat)
        img_paths = sorted(f for f in flat_dir.rglob("*") if f.suffix.lower() in IMG_EXTS)
        out_dir = out_root / args.split / args.identity
        print(f"\nMode B: {len(img_paths)} images -> {out_dir}")
        saved, skipped = process_identity_folder(
            flat_dir,
            out_dir,
            detector,
            args.pad,
            args.min_px,
            args.max_crops,
            args.use_annotations,
            args.target_cls,
            args.preview,
            args,
        )
        total_saved += saved
        total_skipped += skipped
        print(f"  saved={saved}  skipped={skipped}")

    print(f"\n{'=' * 50}")
    print(f"Total: {total_saved} crops saved, {total_skipped} frames skipped")
    print(f"Output -> {out_root}/")
    print("\nData folder is ready for ProtoNet training.")
    print(f"Run: python -m src.train --data_root {out_root} ...")

    if args.copy_enrollment:
        import shutil

        src_enroll = Path(args.copy_enrollment)
        dst_enroll = out_root / "enrollment"
        if src_enroll.exists() and not dst_enroll.exists():
            shutil.copytree(str(src_enroll), str(dst_enroll))
            print(f"Copied enrollment: {src_enroll} -> {dst_enroll}")
        elif dst_enroll.exists():
            print(f"Enrollment already exists, skipping copy: {dst_enroll}")
        else:
            print(f"WARNING: --copy_enrollment source not found: {src_enroll}")

    if args.manifest_out:
        from src.uavid.preprocessing.manifest import write_manifest

        write_manifest(out_root, args.manifest_out)
        print(f"DVC manifest -> {args.manifest_out}")


if __name__ == "__main__":
    main()
