r"""CLI: open-set target-vs-impostor evaluation of a trained encoder.

Sweeps a set of k-shot values, writes a results CSV + summary JSON to
``report_dir``, and logs params, metrics and both files as MLflow artifacts
(matching the ``sw_ai_odd`` evaluation convention).

Usage::

    PYTHONPATH=. uv run python scripts/evaluate.py \\
        --checkpoint models/00_train/best.pth \\
        --data_root /mnt/Pool_IA/IA_Dataset/datasets/ \\
            uav-few-shot-identification/uav_dataset_yolox_crops \\
        --gallery_split enrollment --split val --k_shots "1,3,5,10,15" --agg mean
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import fire
import mlflow
import torch
from loguru import logger

from src.uavid.common.config_loader import load_mlflow_config
from src.uavid.common.io import md5_file, run_name
from src.uavid.common.transforms import build_transform
from src.uavid.dataset import IdentityIndex
from src.uavid.eval import evaluate_openset
from src.uavid.model import BACKBONE_NORM, build_encoder

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

_CSV_FIELDS = [
    "k_shot",
    "agg",
    "roc_auc",
    "genuine_mean",
    "impostor_mean",
    "tpr_fpr_1",
    "threshold_fpr_1",
    "tpr_fpr_5",
    "threshold_fpr_5",
    "tpr_fpr_10",
    "threshold_fpr_10",
    "genuine_n",
    "impostor_n",
]


def _flatten_row(res: dict) -> dict:
    """Flatten one ``evaluate_openset`` result into a CSV row."""
    tpr = res["tpr_at_fpr"]
    return {
        "k_shot": res["k_shot"],
        "agg": res["agg"],
        "roc_auc": res["roc_auc"],
        "genuine_mean": res["genuine_mean"],
        "impostor_mean": res["impostor_mean"],
        "tpr_fpr_1": tpr["0.01"]["tpr"],
        "threshold_fpr_1": tpr["0.01"]["threshold"],
        "tpr_fpr_5": tpr["0.05"]["tpr"],
        "threshold_fpr_5": tpr["0.05"]["threshold"],
        "tpr_fpr_10": tpr["0.10"]["tpr"],
        "threshold_fpr_10": tpr["0.10"]["threshold"],
        "genuine_n": res["genuine_n"],
        "impostor_n": res["impostor_n"],
    }


def main(
    data_root: str,
    checkpoint: str | None = None,
    split: str = "val",
    gallery_split: str | None = None,
    k_shots: str = "1,3,5,10,15",
    max_queries_per_id: int = 30,
    agg: str = "mean",
    tau: float = 0.1,
    seed: int = 42,
    report_dir: str = "data/eval",
    exclude_json: str | None = None,
    mlflow_tracking: bool = True,
) -> None:
    """Evaluate over a k-shot sweep; write CSV + JSON and log to MLflow.

    Args:
        data_root: Dataset root (the NAS dataset directory).
        checkpoint: Trained ``.pth`` (None -> zero-shot ImageNet features).
        split: Query split (e.g. ``val``).
        gallery_split: Gallery/enrollment split (defaults to ``split``).
        k_shots: Comma-separated enrollment sizes to sweep.
        max_queries_per_id: Cap on genuine queries scored per identity.
        agg: ``mean`` (deployment default) or ``attention``.
        tau: Attention temperature.
        seed: RNG seed.
        report_dir: Directory for ``openset_results.csv`` + ``openset_summary.json``.
        exclude_json: Optional crop exclusion-list JSON.
        mlflow_tracking: Log the evaluation run to MLflow when True.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    embed_dim, image_size = 128, 224
    metric, normalize = "euclidean", True
    backbone = "mobilenetv3"
    model = build_encoder(backbone, embed_dim=embed_dim, pretrained=True, l2_normalize=normalize)
    if checkpoint:
        ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
        embed_dim = ckpt.get("embed_dim", 128)
        image_size = ckpt.get("image_size", 224)
        metric = ckpt.get("metric", "euclidean")
        normalize = ckpt.get("l2_normalize", True)
        backbone = ckpt.get("backbone", "mobilenetv3")
        model = build_encoder(
            backbone, embed_dim=embed_dim, pretrained=False, l2_normalize=normalize
        )
        model.load_state_dict(ckpt["model"])
        logger.info(
            f"Loaded {checkpoint} | backbone={backbone} metric={metric} normalize={normalize}"
        )
    else:
        logger.info("Zero-shot ImageNet features (no checkpoint)")
    model.eval().to(device)

    excluded: set[str] = set()
    if exclude_json:
        from src.uavid.preprocessing.filter_crops import load_excluded

        excluded = load_excluded(exclude_json)
        logger.info(f"Loaded {len(excluded)} excluded crops from {exclude_json}")
    ex_root = Path(data_root)

    query_index = IdentityIndex(Path(data_root) / split, exclude=excluded, exclude_root=ex_root)
    gsplit = gallery_split or split
    gallery_index = (
        query_index
        if gsplit == split
        else IdentityIndex(Path(data_root) / gsplit, exclude=excluded, exclude_root=ex_root)
    )
    norm_mean, norm_std = BACKBONE_NORM[backbone]
    tfm = build_transform(image_size, train=False, mean=norm_mean, std=norm_std)

    shots: list[int]
    if isinstance(k_shots, (list, tuple)):
        shots = [int(x) for x in k_shots]
    else:
        shots = [int(x) for x in str(k_shots).split(",")]
    rows: list[dict] = []
    full: list[dict] = []
    for k in shots:
        res = evaluate_openset(
            model,
            query_index,
            gallery_index,
            tfm,
            device,
            k_shot=k,
            max_queries_per_id=max_queries_per_id,
            agg=agg,
            tau=tau,
            metric=metric,
            normalize=normalize,
            seed=seed,
        )
        res["split"], res["gallery_split"] = split, gsplit
        full.append(res)
        rows.append(_flatten_row(res))
        logger.info(
            f"k={k:<3} ROC-AUC {res['roc_auc']:.4f} | "
            f"genuine {res['genuine_mean']:.4f} | impostor {res['impostor_mean']:.4f}"
        )

    # --- write CSV + JSON summary ---
    out = Path(report_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "openset_results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    best = max(full, key=lambda r: r["roc_auc"])
    summary = {
        "split": split,
        "gallery_split": gsplit,
        "agg": agg,
        "k_shots": shots,
        "best_k_shot": best["k_shot"],
        "best_roc_auc": best["roc_auc"],
        "per_k": full,
    }
    summary_path = out / "openset_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    logger.info(f"CSV -> {csv_path} | summary -> {summary_path}")

    # --- MLflow run with CSV + JSON artifacts ---
    if not mlflow_tracking:
        return
    cfg = load_mlflow_config()
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", cfg.get("tracking_uri"))
    experiment = os.environ.get("MLFLOW_EXPERIMENT_NAME", cfg.get("experiment_name"))
    try:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)
    except Exception as e:  # network-dependent
        logger.warning(f"MLflow disabled (setup failed): {e}")
        return
    with mlflow.start_run(run_name=run_name("evaluate")):
        params = {
            "split": split,
            "gallery_split": gsplit,
            "agg": agg,
            "k_shots": k_shots,
            "seed": seed,
        }
        if checkpoint and os.path.isfile(checkpoint):
            params["ckpt_md5"] = md5_file(checkpoint)
        mlflow.log_params(params)
        for r in rows:
            k = r["k_shot"]
            mlflow.log_metric("openset/roc_auc", r["roc_auc"], step=k)
            mlflow.log_metric("openset/genuine_mean", r["genuine_mean"], step=k)
            mlflow.log_metric("openset/impostor_mean", r["impostor_mean"], step=k)
            mlflow.log_metric("openset/tpr_fpr_10", r["tpr_fpr_10"], step=k)
        mlflow.log_metrics({"best/roc_auc": best["roc_auc"], "best/k_shot": float(best["k_shot"])})
        mlflow.set_tags({"task": "few_shot_uav_identification", "stage": "evaluate"})
        mlflow.log_artifact(str(csv_path))
        mlflow.log_artifact(str(summary_path))
        logger.info("Logged evaluation params, metrics, CSV + JSON to MLflow.")


if __name__ == "__main__":
    fire.Fire(main)
