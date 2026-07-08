"""calibrate_threshold.py - Pick the deployment MATCH threshold from data.

Deployment is a binary question per crop: does this crop match the enrolled
gallery? This tool calibrates the decision threshold using labelled crops:

    positives = crops of the SAME target that was enrolled
    negatives = crops of other UAVs / background (impostors)

It scores every crop against the enrolled prototype, sweeps thresholds, and
reports the operating point that best separates the two sets (Youden's J), plus
the threshold that meets a target false-accept rate if requested.

Usage (from items/)::

    python -m scripts.calibrate_threshold \
        --checkpoint models/best.pth \
        --gallery galleries/vector_uav.npy \
        --pos data/demo/video_vector_uav_cropped \
        --neg data/demo/video_demo_enrollment/impostor \
        --out_csv csvs/threshold_calibration.csv
"""

import argparse
from pathlib import Path

import numpy as np

from src.uavid.common.constants import IMG_EXTS
from src.uavid.inference import Verifier


def list_images(folders: list[str]) -> list[Path]:
    paths: list[Path] = []
    for f in folders:
        p = Path(f)
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            paths.append(p)
        elif p.is_dir():
            paths += sorted(q for q in p.rglob("*") if q.suffix.lower() in IMG_EXTS)
    return paths


def metrics_at(threshold: float, pos: np.ndarray, neg: np.ndarray) -> dict:
    tp = int((pos >= threshold).sum())
    fn = int((pos < threshold).sum())
    fp = int((neg >= threshold).sum())
    tn = int((neg < threshold).sum())
    tpr = tp / max(1, tp + fn)  # recall / detection rate
    fpr = fp / max(1, fp + tn)  # false-accept rate
    acc = (tp + tn) / max(1, tp + fn + fp + tn)
    bal_acc = 0.5 * (tpr + (1 - fpr))
    return {
        "threshold": threshold,
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "tpr": tpr,
        "fpr": fpr,
        "acc": acc,
        "bal_acc": bal_acc,
        "youden": tpr - fpr,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--gallery", required=True)
    ap.add_argument(
        "--pos",
        nargs="+",
        required=True,
        help="Folder(s)/image(s) of the enrolled target (positives).",
    )
    ap.add_argument(
        "--neg",
        nargs="+",
        required=True,
        help="Folder(s)/image(s) of impostors/background (negatives).",
    )
    ap.add_argument(
        "--steps",
        type=int,
        default=200,
        help="Number of thresholds to sweep across the score range.",
    )
    ap.add_argument(
        "--target_far",
        type=float,
        default=None,
        help="If set, also report the lowest threshold with FAR <= this.",
    )
    ap.add_argument("--out_csv", default=None)
    args = ap.parse_args()

    vf = Verifier(args.checkpoint, args.gallery)

    pos_paths = list_images(args.pos)
    neg_paths = list_images(args.neg)
    if not pos_paths:
        raise SystemExit("No positive images found.")
    if not neg_paths:
        raise SystemExit("No negative images found.")

    pos = vf.score(vf.embed_paths(pos_paths))
    neg = vf.score(vf.embed_paths(neg_paths))

    print(
        f"\nscore = {vf.score_name}(crop, enrolled prototype)  | gallery views = {vf.gallery_views}"
    )
    print(
        f"positives ({len(pos)}): mean {pos.mean():.4f}  min {pos.min():.4f}  max {pos.max():.4f}"
    )
    print(
        f"negatives ({len(neg)}): mean {neg.mean():.4f}  min {neg.min():.4f}  max {neg.max():.4f}"
    )

    lo = float(min(pos.min(), neg.min()))
    hi = float(max(pos.max(), neg.max()))
    span = hi - lo if hi > lo else 1.0
    thresholds = np.linspace(lo - 0.01 * span, hi + 0.01 * span, args.steps)
    rows = [metrics_at(float(t), pos, neg) for t in thresholds]

    best = max(rows, key=lambda r: (r["youden"], r["bal_acc"]))
    print("\n-- Recommended operating point (max Youden's J) --")
    print(f"  threshold   = {best['threshold']:.4f}")
    print(f"  detection   = {best['tpr'] * 100:5.1f}%  (TP {best['tp']}/{best['tp'] + best['fn']})")
    print(f"  false-accept= {best['fpr'] * 100:5.1f}%  (FP {best['fp']}/{best['fp'] + best['tn']})")
    print(f"  accuracy    = {best['acc'] * 100:5.1f}%   bal_acc {best['bal_acc'] * 100:5.1f}%")

    if args.target_far is not None:
        ok = [r for r in rows if r["fpr"] <= args.target_far]
        if ok:
            pick = max(ok, key=lambda r: r["tpr"])
            print(f"\n-- Threshold at FAR <= {args.target_far:.2%} --")
            print(f"  threshold   = {pick['threshold']:.4f}")
            print(f"  detection   = {pick['tpr'] * 100:5.1f}%")
            print(f"  false-accept= {pick['fpr'] * 100:5.1f}%")
        else:
            print(f"\nNo threshold reaches FAR <= {args.target_far:.2%}.")

    # Separation summary
    margin = pos.min() - neg.max()
    sep = "clean" if margin > 0 else "overlapping"
    print(f"\nseparation: positives.min - negatives.max = {margin:+.4f}  ({sep})")

    if args.out_csv:
        out = Path(args.out_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        import csv

        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nSweep written -> {out}")


if __name__ == "__main__":
    main()
