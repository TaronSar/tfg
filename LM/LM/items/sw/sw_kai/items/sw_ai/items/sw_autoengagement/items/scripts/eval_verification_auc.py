"""CLI: per-identity verification AUC scoreboard with bootstrap CIs and EER.

Scores each enrolled identity's prototype against genuine queries (same
identity) and impostor queries (all other identities), then reports:

- Per-identity AUC with 95% percentile bootstrap confidence intervals.
- Per-identity EER (Equal Error Rate).
- Global (pooled) AUC + CI + EER.

Gallery/enrollment images stay clean; query images can be optionally degraded
to the operational 46-143 px sensor envelope (``--degrade_p 1.0``).

This is the Phase-0 measurement anchor — run once on the best existing
checkpoint before any model changes, then compare every subsequent phase
against the saved CSV.

Usage::

    # Operational baseline (degraded queries):
    PYTHONPATH=. uv run python scripts/eval_verification_auc.py \\
        --checkpoint models/02_dinov2_vits14_enrollment/best.pth \\
        --data_root  /mnt/Pool_IA/.../uav_dataset_yolox_crops \\
        --k_shot 5 --out_csv data/eval_04/verification_auc.csv

    # Clean queries (upper bound):
    PYTHONPATH=. uv run python scripts/eval_verification_auc.py \\
        --checkpoint models/02_dinov2_vits14_enrollment/best.pth \\
        --data_root  /mnt/Pool_IA/.../uav_dataset_yolox_crops \\
        --k_shot 5 --degrade_p 0.0 --out_csv data/eval_04/verification_auc_clean.csv

Notes:
    Identities with fewer images than ``k_shot + 1`` (same-split mode) are
    skipped and listed so you know which need more frames.  Wide CIs indicate
    too few genuine samples.
"""
from __future__ import annotations

import csv
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

import fire
import numpy as np
import torch
import torch.nn.functional as F
from loguru import logger

from src.uavid.common.config_loader import load_mlflow_config
from src.uavid.common.transforms import build_transform
from src.uavid.dataset import IdentityIndex, load_image
from src.uavid.model import BACKBONE_NORM, attention_prototype, build_encoder

try:
    import mlflow
    from dotenv import load_dotenv
    load_dotenv()
    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _roc_auc(genuine: np.ndarray, impostor: np.ndarray) -> float:
    """Compute Wilcoxon-Mann-Whitney AUC without sklearn.

    Args:
        genuine: 1-D array of genuine (positive) scores.
        impostor: 1-D array of impostor (negative) scores.

    Returns:
        AUC in [0, 1].
    """
    n_pos, n_neg = len(genuine), len(impostor)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    scores = np.concatenate([genuine, impostor])
    labels = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])
    order = scores.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    return float((ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _eer(genuine: np.ndarray, impostor: np.ndarray) -> float:
    """Compute Equal Error Rate by linear interpolation at the FAR == FRR crossing.

    Args:
        genuine: 1-D array of genuine scores.
        impostor: 1-D array of impostor scores.

    Returns:
        EER in [0, 1].
    """
    n_pos, n_neg = len(genuine), len(impostor)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    scores = np.concatenate([genuine, impostor])
    labels = np.concatenate([np.ones(n_pos, dtype=bool), np.zeros(n_neg, dtype=bool)])
    order = np.argsort(scores)[::-1]
    sorted_labels = labels[order]
    cum_pos = np.cumsum(sorted_labels).astype(float)
    cum_neg = np.cumsum(~sorted_labels).astype(float)
    fprs = cum_neg / n_neg
    fnrs = 1.0 - cum_pos / n_pos
    diff = fnrs - fprs
    idx = int(np.argmin(np.abs(diff)))
    if idx > 0 and diff[idx - 1] * diff[idx] <= 0.0:
        d0, d1 = float(diff[idx - 1]), float(diff[idx])
        denom = d0 - d1
        if abs(denom) < 1e-12:
            return float((fprs[idx] + fnrs[idx]) / 2)
        t = d0 / denom
        return float(((fprs[idx - 1] + t * (fprs[idx] - fprs[idx - 1])) +
                       (fnrs[idx - 1] + t * (fnrs[idx] - fnrs[idx - 1]))) / 2)
    return float((fprs[idx] + fnrs[idx]) / 2)


def _bootstrap_auc_ci(
    genuine: np.ndarray,
    impostor: np.ndarray,
    n_boot: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    """Compute a 95% percentile bootstrap confidence interval for AUC.

    Args:
        genuine: 1-D array of genuine scores.
        impostor: 1-D array of impostor scores.
        n_boot: Number of bootstrap resamples.
        seed: RNG seed for reproducibility.

    Returns:
        Tuple ``(lower_2.5%, upper_97.5%)`` of the bootstrap distribution.
    """
    n_g, n_i = len(genuine), len(impostor)
    if n_g < 2 or n_i < 2:
        return (0.0, 1.0)
    rng = np.random.default_rng(seed)
    boot = np.empty(n_boot)
    for b in range(n_boot):
        g_s = genuine[rng.integers(0, n_g, size=n_g)]
        i_s = impostor[rng.integers(0, n_i, size=n_i)]
        boot[b] = _roc_auc(g_s, i_s)
    return float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _load_model(checkpoint: str | None, device: str):
    """Load a trained encoder from a checkpoint file.

    Args:
        checkpoint: Path to a ``.pth`` checkpoint.  Pass ``None`` to use
            zero-shot ImageNet features.
        device: PyTorch device string (``"cuda"`` or ``"cpu"``).

    Returns:
        Tuple ``(model, image_size, metric, normalize, backbone)``.
    """
    embed_dim, image_size, metric, normalize, backbone = 128, 224, "euclidean", True, "mobilenetv3"
    if checkpoint:
        ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
        embed_dim  = ckpt.get("embed_dim", 128)
        image_size = ckpt.get("image_size", 224)
        metric     = ckpt.get("metric", "euclidean")
        normalize  = ckpt.get("l2_normalize", True)
        backbone   = ckpt.get("backbone", "mobilenetv3")
        model = build_encoder(backbone, embed_dim=embed_dim,
                              pretrained=False, l2_normalize=normalize)
        model.load_state_dict(ckpt["model"])
        logger.info(f"Loaded  {checkpoint}")
        logger.info(f"        backbone={backbone}  embed_dim={embed_dim}  "
                    f"metric={metric}  normalize={normalize}")
    else:
        model = build_encoder(backbone, embed_dim=embed_dim,
                              pretrained=True, l2_normalize=normalize)
        logger.info("Zero-shot ImageNet features (no checkpoint)")
    model.eval().to(device)
    return model, image_size, metric, normalize, backbone


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@torch.no_grad()
def _embed(model, paths: list, tfm, device: str, batch_size: int = 32) -> torch.Tensor:
    """Embed a list of image paths using the given model.

    Args:
        model: Encoder model (already in eval mode).
        paths: List of ``pathlib.Path`` objects to embed.
        tfm: torchvision transform to apply to each image.
        device: PyTorch device string.
        batch_size: Number of images per forward pass.

    Returns:
        Tensor of shape ``(N, D)`` with L2-normalised embeddings.
    """
    out = []
    for i in range(0, len(paths), batch_size):
        chunk = paths[i:i + batch_size]
        batch = torch.stack([load_image(p, tfm) for p in chunk]).to(device)
        out.append(model(batch))
    return torch.cat(out, dim=0)


@torch.no_grad()
def _compute_scores(
    model,
    enroll_paths: list,
    query_paths: list,
    imp_paths: list,
    gallery_tfm,
    query_tfm,
    device: str,
    metric: str,
    normalize: bool,
    agg: str,
    tau: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Score genuine and impostor queries against an enrolled prototype.

    Args:
        model: Encoder model.
        enroll_paths: Gallery image paths (clean enrollment).
        query_paths: Genuine query paths (potentially degraded).
        imp_paths: Impostor query paths.
        gallery_tfm: Transform for gallery images.
        query_tfm: Transform for query images.
        device: PyTorch device string.
        metric: Distance metric (``"euclidean"`` or ``"cosine"``).
        normalize: Whether embeddings are L2-normalised.
        agg: Prototype aggregation (``"mean"`` or ``"attention"``).
        tau: Attention temperature (used only when ``agg="attention"``).

    Returns:
        Tuple ``(genuine_scores, impostor_scores)`` as float32 numpy arrays.
    """
    gallery = _embed(model, enroll_paths, gallery_tfm, device)
    if normalize:
        gallery = F.normalize(gallery, p=2, dim=-1)
        mean_proto = F.normalize(gallery.mean(dim=0), p=2, dim=0)
    else:
        mean_proto = gallery.mean(dim=0)

    def _score(embs: torch.Tensor) -> list[float]:
        out = []
        for q in embs:
            if agg == "attention" and normalize:
                proto = attention_prototype(q, gallery, tau=tau)
            else:
                proto = mean_proto
            if metric == "cosine" or normalize:
                out.append(float(q @ proto))
            else:
                out.append(-float(((q - proto) ** 2).sum()))
        return out

    genuine  = np.array(_score(_embed(model, query_paths, query_tfm, device)), dtype=np.float32)
    impostor = np.array(_score(_embed(model, imp_paths,   query_tfm, device)), dtype=np.float32)
    return genuine, impostor


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(
    data_root: str,
    checkpoint: str | None = None,
    split: str = "val",
    gallery_split: str | None = None,
    k_shot: int = 5,
    max_queries_per_id: int = 50,
    impostors_per_id: int = 5,
    degrade_p: float = 0.0,
    degrade_min_px: int = 46,
    degrade_max_px: int = 143,
    n_boot: int = 2000,
    agg: str = "mean",
    tau: float = 0.1,
    seed: int = 42,
    out_csv: str | None = None,
    mlflow_tracking: bool = True,
) -> None:
    """Run per-identity verification AUC scoreboard and write results to CSV.

    Args:
        data_root: Dataset root containing the split sub-folders.
        checkpoint: Path to a ``.pth`` checkpoint.  Omit for zero-shot.
        split: Query split (default: ``"val"``).
        gallery_split: Gallery/enrollment split.  Defaults to ``split``.
        k_shot: Gallery views enrolled per identity.
        max_queries_per_id: Cap genuine query images per identity.
        impostors_per_id: Impostor images sampled from each other identity.
        degrade_p: Probability of degrading QUERY images to the operational
            46-143 px envelope.  Gallery images are never degraded.
        degrade_min_px: Degradation shorter-side floor (px).
        degrade_max_px: Degradation shorter-side ceiling (px).
        n_boot: Bootstrap resamples for confidence intervals.
        agg: Prototype aggregation (``"mean"`` or ``"attention"``).
        tau: Attention temperature.
        seed: RNG seed.
        out_csv: Output CSV path.  Defaults to ``data/eval/verification_auc.csv``.
        mlflow_tracking: Log results to MLflow when ``True``.
    """
    import mlflow as _mlflow  # lazy import so absence doesn't break non-mlflow runs

    random.seed(seed)
    np.random.seed(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Device: {device}")

    model, image_size, metric, normalize, backbone = _load_model(checkpoint, device)
    norm_mean, norm_std = BACKBONE_NORM[backbone]

    gallery_tfm = build_transform(image_size, train=False, degrade_p=0.0,
                                  mean=norm_mean, std=norm_std)
    query_tfm   = build_transform(image_size, train=False,
                                  degrade_p=degrade_p,
                                  degrade_min_px=degrade_min_px,
                                  degrade_max_px=degrade_max_px,
                                  mean=norm_mean, std=norm_std)

    data_root_path = Path(data_root)
    query_index  = IdentityIndex(data_root_path / split)
    gsplit       = gallery_split or split
    gallery_index = (query_index if gsplit == split
                     else IdentityIndex(data_root_path / gsplit))
    same_split = gallery_index.root == query_index.root

    logger.info(f"Query   {split}: {query_index.stats()}")
    logger.info(f"Gallery {gsplit}: {'same split' if same_split else gallery_index.stats()}")

    rng = random.Random(seed)
    query_pools   = {n: rng.sample(list(query_index.identities[n]),
                                   len(query_index.identities[n]))
                     for n in query_index.names}
    gallery_pools = {n: rng.sample(list(gallery_index.identities[n]),
                                   len(gallery_index.identities[n]))
                     for n in gallery_index.names}

    genuine_by_id:  dict[str, np.ndarray] = {}
    impostor_by_id: dict[str, np.ndarray] = {}
    skipped: list[str] = []

    for name in query_index.names:
        gallery_paths_all = gallery_pools.get(name)
        if not gallery_paths_all:
            skipped.append(name)
            continue
        if same_split:
            if len(query_pools[name]) <= k_shot:
                skipped.append(name)
                continue
            enroll_paths = query_pools[name][: k_shot]
            query_paths  = query_pools[name][k_shot: k_shot + max_queries_per_id]
        else:
            enroll_paths = (rng.sample(gallery_paths_all, k_shot)
                            if len(gallery_paths_all) >= k_shot
                            else rng.choices(gallery_paths_all, k=k_shot))
            query_paths = query_pools[name][: max_queries_per_id]
            if not query_paths:
                skipped.append(name)
                continue

        imp_paths: list = []
        for other in query_index.names:
            if other == name:
                continue
            imp_paths.extend(rng.sample(query_pools[other],
                                         min(impostors_per_id, len(query_pools[other]))))
        if not imp_paths:
            skipped.append(name)
            continue

        genuine, impostor = _compute_scores(
            model, enroll_paths, query_paths, imp_paths,
            gallery_tfm, query_tfm, device,
            metric, normalize, agg, tau,
        )
        if len(genuine) == 0 or len(impostor) == 0:
            skipped.append(name)
            continue
        genuine_by_id[name]  = genuine
        impostor_by_id[name] = impostor

    if skipped:
        logger.info(f"Skipped {len(skipped)}: {', '.join(sorted(skipped))}")

    if not genuine_by_id:
        logger.error("No identities evaluated.  Check --data_root, --split, --k_shot.")
        return

    # Per-identity stats
    rows: list[dict] = []
    for name in genuine_by_id:
        g, imp = genuine_by_id[name], impostor_by_id[name]
        auc_val = _roc_auc(g, imp)
        eer_val = _eer(g, imp)
        lo, hi  = _bootstrap_auc_ci(g, imp, n_boot=n_boot, seed=seed)
        rows.append({
            "identity":      name,
            "n_genuine":     len(g),
            "n_impostor":    len(imp),
            "auc":           round(auc_val, 4),
            "auc_ci_lo":     round(lo,       4),
            "auc_ci_hi":     round(hi,       4),
            "eer":           round(eer_val,  4),
            "genuine_mean":  round(float(g.mean()),   4),
            "impostor_mean": round(float(imp.mean()), 4),
        })
    rows.sort(key=lambda r: r["auc"])

    # Global stats
    all_g   = np.concatenate(list(genuine_by_id.values()))
    all_imp = np.concatenate(list(impostor_by_id.values()))
    g_auc       = _roc_auc(all_g, all_imp)
    g_eer       = _eer(all_g, all_imp)
    g_lo, g_hi  = _bootstrap_auc_ci(all_g, all_imp, n_boot=n_boot, seed=seed)
    global_row = {
        "identity": "GLOBAL", "n_genuine": len(all_g), "n_impostor": len(all_imp),
        "auc": round(g_auc, 4), "auc_ci_lo": round(g_lo, 4), "auc_ci_hi": round(g_hi, 4),
        "eer": round(g_eer, 4), "genuine_mean": round(float(all_g.mean()), 4),
        "impostor_mean": round(float(all_imp.mean()), 4),
    }

    # Console scoreboard
    hdr = (f"{'Identity':<45} {'n_g':>4} {'n_i':>5}  "
           f"{'AUC':>6}  {'95% CI':^14}  {'EER':>6}")
    logger.info(hdr)
    logger.info("-" * len(hdr))
    for r in rows:
        ci = f"[{r['auc_ci_lo']:.3f}, {r['auc_ci_hi']:.3f}]"
        logger.info(f"{r['identity']:<45} {r['n_genuine']:>4} {r['n_impostor']:>5}  "
                    f"{r['auc']:>6.4f}  {ci:^14}  {r['eer']:>6.4f}")
    logger.info("-" * len(hdr))
    ci = f"[{global_row['auc_ci_lo']:.3f}, {global_row['auc_ci_hi']:.3f}]"
    logger.info(f"{'GLOBAL':<45} {global_row['n_genuine']:>4} {global_row['n_impostor']:>5}  "
                f"{global_row['auc']:>6.4f}  {ci:^14}  {global_row['eer']:>6.4f}")

    # CSV output
    if out_csv:
        csv_path = Path(out_csv)
    else:
        ckpt_stem = Path(checkpoint).parent.name if checkpoint else "zero_shot"
        csv_path = Path("data/eval") / f"{ckpt_stem}_verification_auc.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    all_rows = rows + [global_row]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    logger.info(f"Saved CSV: {csv_path}")

    # Companion meta JSON
    meta = {
        "checkpoint":    checkpoint or "zero_shot",
        "backbone":      backbone,
        "data_root":     str(Path(data_root).resolve()),
        "split":         split,
        "gallery_split": gsplit,
        "k_shot":        k_shot,
        "degrade_p":     degrade_p,
        "degrade_px":    [degrade_min_px, degrade_max_px],
        "agg":           agg,
        "n_boot":        n_boot,
        "seed":          seed,
        "n_identities":  len(rows),
        "skipped":       skipped,
        "global_auc":    global_row["auc"],
        "global_eer":    global_row["eer"],
        "global_auc_ci": [global_row["auc_ci_lo"], global_row["auc_ci_hi"]],
        "run_utc":       datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    meta_path = csv_path.with_suffix(".json")
    with meta_path.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    logger.info(f"Saved meta: {meta_path}")

    # MLflow logging
    if mlflow_tracking and _MLFLOW_AVAILABLE:
        try:
            import mlflow
            cfg = load_mlflow_config()
            tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", cfg.get("tracking_uri"))
            experiment   = os.environ.get("MLFLOW_EXPERIMENT_NAME", cfg.get("experiment_name"))
            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(experiment)
            ckpt_stem = Path(checkpoint).parent.name if checkpoint else "zero_shot"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            with mlflow.start_run(run_name=f"verification_auc_{ckpt_stem}_{ts}"):
                mlflow.log_metric("global_auc", global_row["auc"])
                mlflow.log_metric("global_eer", global_row["eer"])
                mlflow.log_metric("global_auc_ci_lo", global_row["auc_ci_lo"])
                mlflow.log_metric("global_auc_ci_hi", global_row["auc_ci_hi"])
                for r in rows:
                    safe = r["identity"].replace("/", "_")[:40]
                    mlflow.log_metric(f"auc_{safe}", r["auc"])
                mlflow.log_artifact(str(csv_path),  artifact_path="verification_auc")
                mlflow.log_artifact(str(meta_path), artifact_path="verification_auc")
            logger.info(f"MLflow run logged to {tracking_uri}")
        except Exception as exc:
            logger.warning(f"MLflow logging failed: {exc}")


if __name__ == "__main__":
    fire.Fire(main)
