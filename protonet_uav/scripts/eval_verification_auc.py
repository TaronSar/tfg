#!/usr/bin/env python3
"""Phase 0 scoreboard: per-identity verification AUC + bootstrap CIs + EER.

Scores each enrolled identity's prototype against genuine queries (same
identity) and impostor queries (all other identities), then reports:
  - Per-identity AUC with 95% percentile bootstrap confidence intervals
  - Per-identity EER (Equal Error Rate)
  - Global (pooled) AUC + CI + EER

Query images can optionally be degraded to the operational 46-143 px sensor
envelope (--degrade_p 1.0 = always).  Gallery/enrollment images stay clean.
This simulates measuring performance on the actual sensor output before any
model changes are made — the scoreboard every later phase is judged against.

Usage
-----
    # Baseline: trained checkpoint, fully degraded queries (operational):
    python scripts/eval_verification_auc.py \\
        --checkpoint checkpoints_yolox_crops_mixed_domain_real/best.pth \\
        --data_root  data/uav_dataset_yolox_crops_removed_lt30 \\
        --k_shot 5 --degrade_p 1.0 \\
        --out_csv csvs/phase0_baseline_verification_auc.csv

    # Clean queries (upper bound):
    python scripts/eval_verification_auc.py \\
        --checkpoint checkpoints_yolox_crops_mixed_domain_real/best.pth \\
        --data_root  data/uav_dataset_yolox_crops_removed_lt30 \\
        --k_shot 5 --degrade_p 0.0 \\
        --out_csv csvs/phase0_clean_verification_auc.csv

    # Zero-shot (no checkpoint):
    python scripts/eval_verification_auc.py \\
        --data_root data/uav_dataset_yolox_crops_removed_lt30 \\
        --k_shot 5 --degrade_p 1.0

Notes
-----
- Identities with fewer images than k_shot + 1 (same-split mode) are skipped
  and listed so you know which identities need more query frames.
- Wide CIs (e.g. [0.30, 1.00]) indicate too few genuine samples — collect more
  query frames for those identities before trusting their individual AUC.
- Run ONCE before any model/data changes and save the CSV as the baseline.
"""
import argparse
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.dataset import IdentityIndex, build_transform  # noqa: E402
from src.eval_openset import embed_paths               # noqa: E402
from src.model import build_encoder, BACKBONE_NORM, attention_prototype  # noqa: E402


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _roc_auc(genuine: np.ndarray, impostor: np.ndarray) -> float:
    """Wilcoxon-Mann-Whitney AUC (no sklearn dependency)."""
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
    """EER by linear interpolation at the FPR == FNR crossing point."""
    n_pos, n_neg = len(genuine), len(impostor)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    scores = np.concatenate([genuine, impostor])
    labels = np.concatenate([np.ones(n_pos, dtype=bool), np.zeros(n_neg, dtype=bool)])
    # Sort descending by score (as if lowering the accept threshold)
    order = np.argsort(scores)[::-1]
    sorted_labels = labels[order]
    cum_pos = np.cumsum(sorted_labels).astype(float)
    cum_neg = np.cumsum(~sorted_labels).astype(float)
    fprs = cum_neg / n_neg          # False Accept Rate
    fnrs = 1.0 - cum_pos / n_pos   # False Reject Rate
    diff = fnrs - fprs
    idx = int(np.argmin(np.abs(diff)))
    # Linear interpolation if a sign change bracketed the crossing
    if idx > 0 and diff[idx - 1] * diff[idx] <= 0.0:
        d0, d1 = float(diff[idx - 1]), float(diff[idx])
        denom = d0 - d1
        if abs(denom) < 1e-12:
            return float((fprs[idx] + fnrs[idx]) / 2)
        t = d0 / denom
        fpr_eer = fprs[idx - 1] + t * (fprs[idx] - fprs[idx - 1])
        fnr_eer = fnrs[idx - 1] + t * (fnrs[idx] - fnrs[idx - 1])
        return float((fpr_eer + fnr_eer) / 2)
    return float((fprs[idx] + fnrs[idx]) / 2)


def _bootstrap_auc_ci(
    genuine: np.ndarray,
    impostor: np.ndarray,
    n_boot: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap 95 % CI for AUC.

    Resamples genuine and impostor pools independently with replacement.
    For identities with very few genuine samples the interval will be wide —
    that's the informative result (collect more frames for those identities).
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
    """Returns (model, image_size, metric, normalize, backbone)."""
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
        print(f"Loaded  {checkpoint}")
        print(f"        backbone={backbone}  embed_dim={embed_dim}  "
              f"metric={metric}  normalize={normalize}")
    else:
        model = build_encoder(backbone, embed_dim=embed_dim,
                              pretrained=True, l2_normalize=normalize)
        print("Zero-shot ImageNet features (no checkpoint)")
    model.eval().to(device)
    return model, image_size, metric, normalize, backbone


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

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
    """Embed gallery, score genuine and impostor queries against the prototype.

    Returns (genuine_scores, impostor_scores) as 1-D float32 numpy arrays.
    """
    gallery = embed_paths(model, enroll_paths, gallery_tfm, device)
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

    genuine  = np.array(_score(embed_paths(model, query_paths, query_tfm, device)),
                        dtype=np.float32)
    impostor = np.array(_score(embed_paths(model, imp_paths,   query_tfm, device)),
                        dtype=np.float32)
    return genuine, impostor


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Phase 0: per-identity verification AUC + bootstrap CIs + EER"
    )
    ap.add_argument("--checkpoint", default=None,
                    help="Path to .pth checkpoint.  Omit for zero-shot baseline.")
    ap.add_argument("--data_root", required=True,
                    help="Root containing the split sub-folders.")
    ap.add_argument("--split", default="val",
                    help="Query split (default: val).")
    ap.add_argument("--gallery_split", default=None,
                    help="Gallery/enrollment split.  Default: same as --split.")
    ap.add_argument("--k_shot", type=int, default=5,
                    help="Gallery views enrolled per identity.")
    ap.add_argument("--max_queries_per_id", type=int, default=50,
                    help="Cap genuine query images per identity.")
    ap.add_argument("--impostors_per_id", type=int, default=5,
                    help="Impostor images sampled from each other identity.")
    ap.add_argument("--degrade_p", type=float, default=1.0,
                    help="Probability of degrading QUERY images to the operational "
                         "46-143 px envelope (1.0 = always, 0.0 = clean).  "
                         "Gallery images are never degraded.")
    ap.add_argument("--degrade_min_px", type=int, default=46)
    ap.add_argument("--degrade_max_px", type=int, default=143)
    ap.add_argument("--n_boot", type=int, default=2000,
                    help="Bootstrap resamples for confidence intervals.")
    ap.add_argument("--agg", choices=["mean", "attention"], default="mean")
    ap.add_argument("--tau", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out_csv", default=None,
                    help="CSV output path.  Default: csvs/<stem>_verification_auc.csv")
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model, image_size, metric, normalize, backbone = _load_model(args.checkpoint, device)
    norm_mean, norm_std = BACKBONE_NORM[backbone]

    # Gallery stays clean (controlled enrollment); queries optionally degraded.
    gallery_tfm = build_transform(image_size, train=False, degrade_p=0.0,
                                  mean=norm_mean, std=norm_std)
    query_tfm   = build_transform(image_size, train=False,
                                  degrade_p=args.degrade_p,
                                  degrade_min_px=args.degrade_min_px,
                                  degrade_max_px=args.degrade_max_px,
                                  mean=norm_mean, std=norm_std)

    data_root    = Path(args.data_root)
    query_index  = IdentityIndex(data_root / args.split)
    gallery_split = args.gallery_split or args.split
    gallery_index = (query_index
                     if gallery_split == args.split
                     else IdentityIndex(data_root / gallery_split))
    same_split = gallery_index.root == query_index.root

    print(f"\nQuery   {args.split}: {query_index.stats()}")
    print(f"Gallery {gallery_split}: {'same split' if same_split else gallery_index.stats()}")
    print(f"device={device} | degrade_p={args.degrade_p} "
          f"({args.degrade_min_px}-{args.degrade_max_px} px) | "
          f"k_shot={args.k_shot} | n_boot={args.n_boot}\n")

    rng = random.Random(args.seed)
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
            if len(query_pools[name]) <= args.k_shot:
                skipped.append(name)
                continue
            enroll_paths = query_pools[name][: args.k_shot]
            query_paths  = query_pools[name][args.k_shot:
                                             args.k_shot + args.max_queries_per_id]
        else:
            enroll_paths = (rng.sample(gallery_paths_all, args.k_shot)
                            if len(gallery_paths_all) >= args.k_shot
                            else rng.choices(gallery_paths_all, k=args.k_shot))
            query_paths = query_pools[name][: args.max_queries_per_id]
            if not query_paths:
                skipped.append(name)
                continue

        # Collect impostor images from all other identities
        imp_paths: list = []
        for other in query_index.names:
            if other == name:
                continue
            n_imp = min(args.impostors_per_id, len(query_pools[other]))
            imp_paths.extend(rng.sample(query_pools[other], n_imp))

        if not imp_paths:
            skipped.append(name)
            continue

        genuine, impostor = _compute_scores(
            model, enroll_paths, query_paths, imp_paths,
            gallery_tfm, query_tfm, device,
            metric, normalize, args.agg, args.tau,
        )
        if len(genuine) == 0 or len(impostor) == 0:
            skipped.append(name)
            continue

        genuine_by_id[name]  = genuine
        impostor_by_id[name] = impostor

    if skipped:
        print(f"Skipped {len(skipped)} identities "
              f"(too few images or no gallery): {', '.join(sorted(skipped))}\n")

    if not genuine_by_id:
        print("ERROR: no identities could be evaluated.  "
              "Check --data_root, --split, and --k_shot.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Compute per-identity metrics
    # -----------------------------------------------------------------------
    rows: list[dict] = []
    for name in genuine_by_id:
        g = genuine_by_id[name]
        imp = impostor_by_id[name]
        auc  = _roc_auc(g, imp)
        eer  = _eer(g, imp)
        lo, hi = _bootstrap_auc_ci(g, imp, n_boot=args.n_boot, seed=args.seed)
        rows.append({
            "identity":      name,
            "n_genuine":     len(g),
            "n_impostor":    len(imp),
            "auc":           round(auc,  4),
            "auc_ci_lo":     round(lo,   4),
            "auc_ci_hi":     round(hi,   4),
            "eer":           round(eer,  4),
            "genuine_mean":  round(float(g.mean()),   4),
            "impostor_mean": round(float(imp.mean()), 4),
        })

    # Sort by AUC ascending so weakest identities are most visible
    rows.sort(key=lambda r: r["auc"])

    # -----------------------------------------------------------------------
    # Global (pooled) metrics
    # -----------------------------------------------------------------------
    all_g   = np.concatenate(list(genuine_by_id.values()))
    all_imp = np.concatenate(list(impostor_by_id.values()))
    g_auc        = _roc_auc(all_g, all_imp)
    g_eer        = _eer(all_g, all_imp)
    g_lo, g_hi   = _bootstrap_auc_ci(all_g, all_imp, n_boot=args.n_boot, seed=args.seed)
    global_row = {
        "identity":      "GLOBAL",
        "n_genuine":     len(all_g),
        "n_impostor":    len(all_imp),
        "auc":           round(g_auc, 4),
        "auc_ci_lo":     round(g_lo,  4),
        "auc_ci_hi":     round(g_hi,  4),
        "eer":           round(g_eer, 4),
        "genuine_mean":  round(float(all_g.mean()),   4),
        "impostor_mean": round(float(all_imp.mean()), 4),
    }

    # -----------------------------------------------------------------------
    # Print scoreboard
    # -----------------------------------------------------------------------
    hdr = (f"{'Identity':<45} {'n_g':>4} {'n_i':>5}  "
           f"{'AUC':>6}  {'95% CI':^14}  {'EER':>6}")
    sep = "-" * len(hdr)
    print(hdr)
    print(sep)
    for r in rows:
        ci = f"[{r['auc_ci_lo']:.3f}, {r['auc_ci_hi']:.3f}]"
        print(f"{r['identity']:<45} {r['n_genuine']:>4} {r['n_impostor']:>5}  "
              f"{r['auc']:>6.4f}  {ci:^14}  {r['eer']:>6.4f}")
    print(sep)
    ci = f"[{global_row['auc_ci_lo']:.3f}, {global_row['auc_ci_hi']:.3f}]"
    print(f"{'GLOBAL':<45} {global_row['n_genuine']:>4} {global_row['n_impostor']:>5}  "
          f"{global_row['auc']:>6.4f}  {ci:^14}  {global_row['eer']:>6.4f}")
    print()

    # Highlight identities needing more data
    thin = [r["identity"] for r in rows
            if r["auc_ci_hi"] - r["auc_ci_lo"] > 0.30]
    if thin:
        print("Wide CI (>0.30) — collect more query frames for:")
        for name in thin:
            r = next(x for x in rows if x["identity"] == name)
            print(f"  {name}  (n_genuine={r['n_genuine']})")
        print()

    # -----------------------------------------------------------------------
    # Save CSV
    # -----------------------------------------------------------------------
    all_rows = rows + [global_row]
    if args.out_csv:
        csv_path = Path(args.out_csv)
    else:
        ckpt_stem = (Path(args.checkpoint).parent.name
                     if args.checkpoint else "zero_shot")
        degrade_tag = f"_degrade{int(args.degrade_p * 100)}"
        csv_path = (ROOT / "csvs" /
                    f"{ckpt_stem}_k{args.k_shot}{degrade_tag}_verification_auc.csv")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Saved CSV: {csv_path}")

    # -----------------------------------------------------------------------
    # Companion meta JSON — records run provenance for traceability
    # -----------------------------------------------------------------------
    meta = {
        "checkpoint":    args.checkpoint or "zero_shot",
        "backbone":      backbone,
        "data_root":     str(Path(args.data_root).resolve()),
        "split":         args.split,
        "gallery_split": gallery_split,
        "k_shot":        args.k_shot,
        "degrade_p":     args.degrade_p,
        "degrade_px":    [args.degrade_min_px, args.degrade_max_px],
        "agg":           args.agg,
        "n_boot":        args.n_boot,
        "seed":          args.seed,
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
    print(f"Saved meta: {meta_path}")


if __name__ == "__main__":
    main()
