"""Back-fill all historical ProtoNet trainings into MLflow.

The project produced ~12 ``checkpoints_*`` directories before MLflow tracking
was integrated. This script reconstructs each of those runs from:

  * the training log in ``logs/`` (per-epoch loss / train_acc / val_acc),
  * the checkpoint metadata stored inside ``best.pth`` / ``last.pth``,
  * the open-set k-shot sweep CSVs in ``csvs/`` (final evaluation metrics).

Each reconstructed run is created with a back-dated start time (the checkpoint
mtime) using ``MlflowClient`` so the MLflow timeline matches reality. Runs are
tagged with the experiment-narrative stage from the TFG report so the whole
research arc is browsable in the MLflow UI.

Usage (from items/)::

    python -m scripts.backfill_mlflow --source ../../../../../../../protonet_uav
    python -m scripts.backfill_mlflow --source /path/to/protonet_uav --dry-run

The MLflow URI / experiment come from the environment (.env):
    MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv optional; env can be set externally
    pass

from src.uavid.common.log_parser import parse_training_log

# ---------------------------------------------------------------------------
# Curated metadata for each historical checkpoint directory.
# Maps checkpoint dir -> (log file, narrative stage, dataset, notes).
# Stages follow the TFG experimental narrative (report section 6.x / 6.16).
# ---------------------------------------------------------------------------
RUN_REGISTRY: dict[str, dict] = {
    "checkpoints_gpu_clean": {
        "log": "train_gpu_clean_manual.log",
        "stage": "1_clean_renders_baseline",
        "dataset": "uav_dataset (clean renders)",
        "degrade_p": 0.5,
        "notes": "Clean Blender renders, degrade_p=0.5. Q3 ablation (with degradation).",
    },
    "checkpoints_gpu_nodegrade": {
        "log": "train_gpu_nodegrade_manual.log",
        "stage": "1_clean_renders_baseline",
        "dataset": "uav_dataset (clean renders)",
        "degrade_p": 0.0,
        "notes": "Clean renders, degrade_p=0.0. Q3 ablation (no degradation).",
    },
    "checkpoints_gpu": {
        "log": None,
        "stage": "1_clean_renders_baseline",
        "dataset": "uav_dataset (clean renders)",
        "notes": "Early GPU baseline run.",
    },
    "checkpoints": {
        "log": None,
        "stage": "1_clean_renders_baseline",
        "dataset": "uav_dataset (clean renders)",
        "notes": "Initial CPU/smoke baseline.",
    },
    "checkpoints_realistic_50_100": {
        "log": "train_realistic_50_100_log.txt",
        "stage": "2_aggressive_realistic_regression",
        "dataset": "uav_dataset_realistic_50_100_final",
        "degrade_p": 0.0,
        "notes": (
            "Aggressive baked-in augmentation. Regression: embedding collapse "
            "(impostor mean ~doubled)."
        ),
    },
    "checkpoints_color_mild_clean_nodegrade_15way_krobust_euclidean": {
        "log": "train_color_mild_clean_15way_krobust_euclidean.log",
        "stage": "3_color_mild_clean",
        "dataset": "uav_dataset_color_mild_clean",
        "degrade_p": 0.0,
        "notes": "Colour + mild realistic, severity budget. Near-zero train/val gap (0.024).",
    },
    "checkpoints_mixed_domain_enrollment_support_15way": {
        "log": "train_mixed_domain_enrollment_support_15way.log",
        "stage": "4_mixed_domain",
        "dataset": "uav_dataset_color_mild_clean (mixed-domain episodes)",
        "degrade_p": 0.0,
        "notes": (
            "Mixed-domain (enrollment support / operational query). Cross-domain AUC 0.481->0.873."
        ),
    },
    "checkpoints_mixed_domain_extended": {
        "log": "train_mixed_domain_extended.log",
        "stage": "4_mixed_domain_extended",
        "dataset": "uav_dataset_color_mild_clean (mixed-domain episodes)",
        "degrade_p": 0.0,
        "notes": "100-epoch convergence test. Confirmed ceiling; no gain over 50ep.",
    },
    "checkpoints_mixed_domain_real_data": {
        "log": "train_mixed_domain_real_data.log",
        "stage": "5_real_data_integration",
        "dataset": "uav_dataset + real1-5 + Ukraine sequences",
        "degrade_p": 0.0,
        "notes": "Added 9 real fixed-wing identities. Cross-domain AUC 0.873->0.913.",
    },
    "checkpoints_yolox_crops_mixed_domain": {
        "log": "train_yolox_crops.log",
        "stage": "6_yolox_crops_final",
        "dataset": "uav_dataset_yolox_crops",
        "degrade_p": 0.0,
        "notes": (
            "FINAL reference model. YOLOX-crop queries match deployment. Cross-domain AUC 0.955@k5."
        ),
        "final": True,
    },
    "checkpoints_yolox_crops_mixed_domain_real": {
        "log": "train_yolox_crops_mixed_domain_real.txt",
        "stage": "6_yolox_crops_variant",
        "dataset": "uav_dataset_yolox_crops (+real)",
        "degrade_p": 0.0,
        "notes": "YOLOX-crop variant with extra real data.",
    },
    "checkpoints_yolox_crops_mixed_domain_v2": {
        "log": "train_yolox_crops_v2.log",
        "stage": "6_yolox_crops_variant",
        "dataset": "uav_dataset_yolox_crops_removed_lt30",
        "degrade_p": 0.0,
        "notes": "YOLOX-crop v2 (cleanup experiment; demo regression -> rolled back).",
    },
}

# K-shot sweep CSV columns we replay as step-indexed metrics.
_SWEEP_METRIC_COLS = [
    "roc_auc",
    "tpr_fpr_1",
    "tpr_fpr_5",
    "tpr_fpr_10",
    "genuine_mean",
    "impostor_mean",
]


def _load_checkpoint_meta(ckpt_path: Path) -> dict:
    """Read the metadata fields stored inside a .pth checkpoint (no weights kept)."""
    import torch

    try:
        ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    except Exception as e:
        print(f"  ! could not read {ckpt_path.name}: {e}")
        return {}
    if not isinstance(ck, dict):
        return {}
    return {k: v for k, v in ck.items() if k not in {"model", "state_dict", "optimizer"}}


def _find_sweep_csvs(csv_dir: Path, ckpt_name: str) -> list[Path]:
    """Find open-set k-shot sweep CSVs belonging to a checkpoint dir.

    A CSV is assigned to the *longest* matching checkpoint-name prefix, so the
    bare ``checkpoints`` dir does not greedily claim CSVs that actually belong
    to e.g. ``checkpoints_mixed_domain_...``.
    """
    if not csv_dir.is_dir():
        return []
    owned = []
    for csv_path in sorted(csv_dir.glob("*kshot_sweep.csv")):
        stem = csv_path.stem
        candidates = [k for k in RUN_REGISTRY if stem.startswith(k + "_")]
        if not candidates:
            continue
        if max(candidates, key=len) == ckpt_name:
            owned.append(csv_path)
    return owned


def _replay_sweep(client, run_id: str, csv_path: Path) -> None:
    """Log a k-shot sweep CSV as step-indexed MLflow metrics (step = k_shot)."""
    import csv as _csv

    # Prefix groups metrics in the UI, e.g. enrollment_gallery_val_query_mean/roc_auc
    prefix = csv_path.stem.split("_kshot_sweep")[0]
    # Drop the checkpoint-name part of the prefix to keep keys short.
    for known in RUN_REGISTRY:
        if prefix.startswith(known + "_"):
            prefix = prefix[len(known) + 1 :]
            break

    with open(csv_path, newline="") as f:
        for row in _csv.DictReader(f):
            try:
                k = int(float(row["k_shot"]))
            except (KeyError, ValueError):
                continue
            for col in _SWEEP_METRIC_COLS:
                if row.get(col) in (None, ""):
                    continue
                try:
                    client.log_metric(run_id, f"{prefix}/{col}", float(row[col]), step=k)
                except Exception:
                    pass


def backfill(source: Path, dry_run: bool = False, log_checkpoints: bool = True) -> None:
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://192.168.2.1:5000")
    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "uav_few_shot_identification")

    client = None
    exp_id = None
    if dry_run:
        print(f"MLflow: {tracking_uri} / experiment '{experiment_name}'")
        print("(dry-run: nothing will be written to MLflow)\n")
    else:
        import mlflow
        from mlflow.tracking import MlflowClient

        mlflow.set_tracking_uri(tracking_uri)
        client = MlflowClient(tracking_uri)
        print(f"MLflow: {tracking_uri} / experiment '{experiment_name}'")
        exp = client.get_experiment_by_name(experiment_name)
        exp_id = exp.experiment_id if exp else client.create_experiment(experiment_name)

    logs_dir = source / "logs"
    csvs_dir = source / "csvs"

    created = 0
    for ckpt_name, meta in RUN_REGISTRY.items():
        ckpt_dir = source / ckpt_name
        if not ckpt_dir.is_dir():
            print(f"- skip {ckpt_name} (dir not found)")
            continue

        # --- gather params/metrics from log + checkpoint ---
        params: dict = {"stage": meta["stage"], "dataset": meta.get("dataset")}
        if "degrade_p" in meta:
            params["degrade_p"] = meta["degrade_p"]

        tlog = None
        log_name = meta.get("log")
        if log_name and (logs_dir / log_name).is_file():
            tlog = parse_training_log(logs_dir / log_name)
            params.update(tlog.params)

        best_meta = _load_checkpoint_meta(ckpt_dir / "best.pth")
        for key in ("embed_dim", "image_size", "metric", "l2_normalize", "support_split"):
            if key in best_meta and key not in params:
                params[key] = best_meta[key]

        best_val_acc = best_meta.get("val_acc")
        best_epoch = best_meta.get("epoch")
        if best_val_acc is None and tlog:
            best_val_acc = tlog.best_val_acc
            best_epoch = tlog.best_epoch

        start_ms = (
            int((ckpt_dir / "best.pth").stat().st_mtime * 1000)
            if (ckpt_dir / "best.pth").exists()
            else None
        )

        sweeps = _find_sweep_csvs(csvs_dir, ckpt_name)

        n_epochs = len(tlog.epochs) if tlog else 0
        print(f"+ {ckpt_name}")
        print(
            f"    stage={meta['stage']} epochs={n_epochs} "
            f"best_val_acc={best_val_acc} sweeps={len(sweeps)}"
        )

        if dry_run:
            continue

        # --- create the back-dated run ---
        tags = {
            "mlflow.runName": ckpt_name,
            "backfilled": "true",
            "stage": meta["stage"],
            "source_checkpoint_dir": ckpt_name,
            "notes": meta.get("notes", ""),
        }
        if meta.get("final"):
            tags["final_model"] = "true"

        run = client.create_run(exp_id, start_time=start_ms, tags=tags)
        run_id = run.info.run_id

        for k, v in params.items():
            if v is None:
                continue
            try:
                client.log_param(run_id, k, str(v) if isinstance(v, list) else v)
            except Exception:
                pass

        # per-epoch metrics
        if tlog:
            for e in tlog.epochs:
                ts = start_ms + int(e.time_s * 1000) * e.epoch if start_ms else None
                for key, val in (
                    ("loss", e.loss),
                    ("train_acc", e.train_acc),
                    ("val_acc", e.val_acc),
                    ("epoch_time_s", e.time_s),
                ):
                    client.log_metric(run_id, key, val, timestamp=ts, step=e.epoch)
            if tlog.epochs:
                gap = tlog.epochs[-1].train_acc - tlog.epochs[-1].val_acc
                client.log_metric(run_id, "final_train_val_gap", gap)

        if best_val_acc is not None:
            client.log_metric(run_id, "best_val_acc", float(best_val_acc))
        if best_epoch is not None:
            client.log_param(run_id, "best_epoch", int(best_epoch))

        # open-set k-shot sweeps (final evaluation)
        for csv_path in sweeps:
            _replay_sweep(client, run_id, csv_path)

        # checkpoint artifact (best.pth only, for traceability)
        if log_checkpoints and (ckpt_dir / "best.pth").exists():
            try:
                client.log_artifact(run_id, str(ckpt_dir / "best.pth"), artifact_path="checkpoints")
            except Exception as e:
                print(f"    ! artifact upload failed: {e}")

        end_ms = (
            int((ckpt_dir / "last.pth").stat().st_mtime * 1000)
            if (ckpt_dir / "last.pth").exists()
            else None
        )
        client.set_terminated(run_id, status="FINISHED", end_time=end_ms)
        created += 1

    print(f"\nDone. {created} run(s) {'would be ' if dry_run else ''}created.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--source",
        required=True,
        help="Path to the original protonet_uav project (with checkpoints_*/logs/csvs).",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Parse and report only; do not write to MLflow."
    )
    ap.add_argument(
        "--no-checkpoints",
        action="store_true",
        help="Do not upload best.pth as an MLflow artifact.",
    )
    args = ap.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"Source not found: {source}")
    backfill(source, dry_run=args.dry_run, log_checkpoints=not args.no_checkpoints)


if __name__ == "__main__":
    main()
