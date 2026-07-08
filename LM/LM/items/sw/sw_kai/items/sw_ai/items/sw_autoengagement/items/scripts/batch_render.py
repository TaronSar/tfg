#!/usr/bin/env python3
"""batch_render.py — Run render_uav.py over multiple downloaded .glb models.

USAGE:
    python scripts/batch_render.py \
        --models_dir ~/Downloads/uav_models/ \
        --output_dir ~/uav_dataset/ \
        --blender /path/to/blender \
        --train_ratio 0.75

MODELS DIR layout — one subfolder per identity:
    uav_models/
        mq1_predator/     model.glb
        tb2_bayraktar/    model.glb
        mq9_reaper/       model.glb
        global_hawk/      model.glb
        hermes_450/       model.glb
        wing_loong/       model.glb
        bird_eagle/       model.glb    ← hard negative
        bird_seagull/     model.glb    ← hard negative
        cessna_172/       model.glb    ← hard negative (small plane)
        neg_tree/         model.glb    ← train-only negative; no val/enrollment

OUTPUT:
    ~/uav_dataset/
        train/
            mq1_predator/       operational renders only, small/far/sky
            tb2_bayraktar/
            neg_tree/           operational train-only negative
            ...
        val/
            global_hawk/        operational renders only, identities never in train
            hermes_450/
            ...
        enrollment/
            mq1_predator/       close-up renders for all models; not used by training
            tb2_bayraktar/
            global_hawk/
            hermes_450/
            ...
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path


def find_model_file(folder: Path):
    for ext in [".glb", ".gltf", ".fbx", ".obj"]:
        for f in folder.rglob(f"*{ext}"):
            return f
    return None


def is_negative(identity_dir: Path) -> bool:
    return identity_dir.name.lower().startswith("neg_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--models_dir", required=True, help="Root folder with one subfolder per UAV identity."
    )
    ap.add_argument(
        "--output_dir", required=True, help="Where to save the dataset (train/ val/ enrollment/)."
    )
    ap.add_argument(
        "--blender",
        default="blender",
        help="Path to Blender executable (default: 'blender' if in PATH).",
    )
    ap.add_argument(
        "--script", default=None, help="Path to render_uav.py. Default: same folder as this script."
    )
    ap.add_argument(
        "--train_ratio",
        type=float,
        default=0.75,
        help="Fraction of identities to put in train (rest go to val).",
    )
    ap.add_argument(
        "--samples",
        type=int,
        default=8,
        help="Cycles render samples per image (8=fast preview, 32-64=higher quality).",
    )
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--azimuths", type=int, default=8)
    ap.add_argument(
        "--elevations",
        type=float,
        nargs="+",
        default=[-65, -45, -25, -10],
        help="Camera elevation angles to pass to render_uav.py.",
    )
    ap.add_argument(
        "--realistic",
        action="store_true",
        help="Enable randomized camera/lighting/exposure rendering in render_uav.py.",
    )
    ap.add_argument(
        "--colorize",
        choices=["none", "operational", "all"],
        default="operational",
        help="Override UAV materials with contrast-preserving colors during rendering.",
    )
    ap.add_argument(
        "--variants",
        type=int,
        default=1,
        help="Randomized render variants per pose/sky when --realistic is enabled.",
    )
    ap.add_argument(
        "--sky_count",
        type=int,
        default=3,
        help="Use only the first N sky presets in render_uav.py.",
    )
    ap.add_argument(
        "--postprocess_realistic",
        action="store_true",
        help="After rendering, create a camera-degraded dataset with make_realistic_synthetic.py.",
    )
    ap.add_argument(
        "--postprocess_profile",
        choices=["mild", "balanced", "aggressive"],
        default="mild",
        help="Strength of camera degradation. mild preserves silhouettes best.",
    )
    ap.add_argument(
        "--realistic_output_dir",
        default=None,
        help="Output root for the postprocessed realistic dataset.",
    )
    ap.add_argument(
        "--train_variants", type=int, default=1, help="Postprocess variants per train image."
    )
    ap.add_argument(
        "--val_variants", type=int, default=1, help="Postprocess variants per val image."
    )
    ap.add_argument(
        "--enrollment_variants",
        type=int,
        default=1,
        help="Postprocess variants per enrollment image.",
    )
    ap.add_argument("--skip_enrollment", action="store_true")
    ap.add_argument(
        "--operational_distance_mult",
        type=float,
        default=None,
        help="Override render_uav.py operational camera distance multiplier.",
    )
    ap.add_argument(
        "--operational_focal_mm",
        type=float,
        default=None,
        help="Override render_uav.py operational focal length.",
    )
    ap.add_argument(
        "--operational_distance_jitter",
        type=float,
        nargs=2,
        default=None,
        metavar=("MIN", "MAX"),
        help="Override render_uav.py operational distance jitter multipliers.",
    )
    ap.add_argument(
        "--operational_focal_jitter",
        type=float,
        nargs=2,
        default=None,
        metavar=("MIN", "MAX"),
        help="Override render_uav.py operational focal jitter multipliers.",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--manifest_out",
        default=None,
        help="If set, write a DVC dataset manifest JSON to this path after rendering.",
    )

    args = ap.parse_args()
    random.seed(args.seed)

    script = str(Path(args.script or Path(__file__).parent / "render_uav.py").resolve())
    if not os.path.exists(script):
        raise FileNotFoundError(f"render_uav.py not found at {script}")

    models_dir = Path(args.models_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    # Discover identities
    identities = sorted(
        [d for d in models_dir.iterdir() if d.is_dir() and find_model_file(d) is not None]
    )

    if not identities:
        raise RuntimeError(
            f"No model files found under {models_dir}. "
            f"Expected subfolders with .glb/.gltf/.fbx/.obj files."
        )

    negatives = [d for d in identities if is_negative(d)]
    positives = [d for d in identities if not is_negative(d)]

    if len(positives) < 2:
        raise RuntimeError(
            "Need at least 2 positive model identities to create disjoint train and val splits. "
            "Folders named neg_* are train-only negatives and do not count for validation."
        )

    # Train/val split by positive model identity. Keep at least one positive in each split.
    random.shuffle(positives)
    n_train = int(len(positives) * args.train_ratio)
    n_train = min(max(1, n_train), len(positives) - 1)
    train_pos_ids = positives[:n_train]
    val_ids = positives[n_train:]
    train_ids = train_pos_ids + negatives

    print(f"Found {len(identities)} identities")
    print(f"Positive ({len(positives)}): {[d.name for d in positives]}")
    print(f"Negative train-only ({len(negatives)}): {[d.name for d in negatives]}")
    print(f"Train ({len(train_ids)}): {[d.name for d in train_ids]}")
    print(f"Val   ({len(val_ids)}):   {[d.name for d in val_ids]}")
    print()

    manifest = {
        "train": [d.name for d in train_ids],
        "train_positives": [d.name for d in train_pos_ids],
        "train_negatives": [d.name for d in negatives],
        "val": [d.name for d in val_ids],
        "enrollment": [] if args.skip_enrollment else [d.name for d in positives],
        "note": (
            "neg_* folders are train-only operational negatives: no val split and no enrollment. "
            "Positive folders are split into train/val and enrollment is rendered "
            "for all positives."
        ),
    }

    failures = []

    def render(identity_dir: Path, split: str, skip_enrollment: bool = False) -> None:
        model_file = find_model_file(identity_dir)
        name = identity_dir.name
        out = str((output_dir / split).resolve())

        cmd = [
            args.blender,
            "--background",
            "--python-exit-code",
            "1",
            "--python",
            script,
            "--",
            "--model",
            str(model_file.resolve()),
            "--name",
            name,
            "--output",
            out,
            "--samples",
            str(args.samples),
            "--width",
            str(args.width),
            "--height",
            str(args.height),
            "--azimuths",
            str(args.azimuths),
        ]
        if args.elevations:
            cmd.append("--elevations")
            cmd.extend(str(v) for v in args.elevations)
        if args.realistic:
            cmd.extend(["--realistic", "--variants", str(args.variants)])
        if args.colorize != "operational":
            cmd.extend(["--colorize", args.colorize])
        if args.sky_count:
            cmd.extend(["--sky_count", str(args.sky_count)])
        if args.skip_enrollment or skip_enrollment:
            cmd.append("--skip_enrollment")
        if args.operational_distance_mult is not None:
            cmd.extend(["--operational_distance_mult", str(args.operational_distance_mult)])
        if args.operational_focal_mm is not None:
            cmd.extend(["--operational_focal_mm", str(args.operational_focal_mm)])
        if args.operational_distance_jitter is not None:
            cmd.append("--operational_distance_jitter")
            cmd.extend(str(v) for v in args.operational_distance_jitter)
        if args.operational_focal_jitter is not None:
            cmd.append("--operational_focal_jitter")
            cmd.extend(str(v) for v in args.operational_focal_jitter)

        print(f"{'─' * 60}")
        suffix = " (no enrollment)" if skip_enrollment else ""
        print(f"Rendering: {name}  →  {split}/operational/{name}/{suffix}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'─' * 60}")

        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"  WARNING: Blender exited with code {result.returncode} for {name}")
            failures.append((name, result.returncode))
        else:
            print(f"  ✓ {name} done")

    for ident in train_pos_ids:
        render(ident, "train")

    for ident in negatives:
        render(ident, "train", skip_enrollment=True)

    for ident in val_ids:
        render(ident, "val")

    if failures:
        failed = ", ".join(f"{name} (exit {code})" for name, code in failures)
        raise RuntimeError(f"Rendering failed for: {failed}")

    # Reorganize: move operational/ subfolder up to match ProtoNet's expected layout
    # ProtoNet expects: data/train/<identity>/*.jpg  (not data/train/operational/<identity>/)
    print(f"\n{'=' * 60}")
    print("Reorganizing folder structure for ProtoNet...")

    for split in ["train", "val"]:
        op_dir = output_dir / split / "operational"
        if op_dir.exists():
            for ident_dir in op_dir.iterdir():
                if ident_dir.is_dir():
                    dest = output_dir / split / ident_dir.name
                    if not dest.exists():
                        shutil.move(str(ident_dir), str(dest))
                    else:
                        for path in ident_dir.iterdir():
                            target = dest / path.name
                            if target.exists():
                                if path.is_file():
                                    path.unlink()
                                continue
                            shutil.move(str(path), str(target))
                        try:
                            ident_dir.rmdir()
                        except OSError:
                            pass
            # Remove now-empty operational/ folder
            try:
                op_dir.rmdir()
            except OSError:
                pass

    (output_dir / "split_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"Done. Dataset at: {output_dir}")
    print(f"Split manifest: {output_dir / 'split_manifest.json'}")

    if args.postprocess_realistic:
        post_script = Path(__file__).parent / "make_realistic_synthetic.py"
        realistic_output = Path(args.realistic_output_dir or f"{output_dir}_realistic").resolve()
        cmd = [
            sys.executable,
            str(post_script),
            "--input",
            str(output_dir),
            "--output",
            str(realistic_output),
            "--train_variants",
            str(args.train_variants),
            "--val_variants",
            str(args.val_variants),
            "--enrollment_variants",
            str(args.enrollment_variants),
            "--profile",
            args.postprocess_profile,
            "--seed",
            str(args.seed),
        ]
        print("\nCreating realistic camera-degraded dataset:")
        print(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Realistic postprocess failed with exit code {result.returncode}")
        print(f"Realistic dataset at: {realistic_output}")
    print("\nRun audit:")
    print(f"  python scripts/audit_dataset.py --data_root {output_dir} --show_sizes")

    if args.manifest_out:
        from src.uavid.preprocessing.manifest import write_manifest

        write_manifest(output_dir, args.manifest_out)
        print(f"DVC manifest -> {args.manifest_out}")


if __name__ == "__main__":
    main()
