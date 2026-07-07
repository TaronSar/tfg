"""CLI: pairwise verification AUC for specific hard identity pairs.

For each pair (A, B) taken from a confusability CSV (or specified explicitly):

- **Positives**: cosine score of A's query images against A's prototype
                 + B's query images against B's prototype
- **Negatives**: cross-impostor scores: A's queries vs B's prototype
                 + B's queries vs A's prototype
- AUC = how well the model separates *this specific pair* — no easy contrasts.

One AUC number per pair. Logged to MLflow as metrics + CSV artifact.

Usage::

    PYTHONPATH=. uv run python scripts/hardpair_auc.py \\
        --data_root Z:/Pool_IA/.../uav_dataset_yolox_crops \\
        --checkpoint models/00_train/best.pth \\
        --confusability_csv data/eval/confusability_val.csv \\
        --top_k 6 \\
        --split val
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import fire
import torch
import torch.nn.functional as F
from loguru import logger

from src.uavid.common.transforms import build_transform
from src.uavid.dataset import IdentityIndex, load_image
from src.uavid.eval.openset import roc_auc
from src.uavid.model import ProtoNetEncoder

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _embed(model, paths, tfm, device, batch_size=32):
    out = []
    with torch.no_grad():
        for i in range(0, len(paths), batch_size):
            chunk = paths[i:i + batch_size]
            batch = torch.stack([load_image(p, tfm) for p in chunk]).to(device)
            out.append(model(batch))
    return torch.cat(out, dim=0)


def _proto(embeddings):
    return F.normalize(embeddings.mean(dim=0), p=2, dim=0)


def _cosine_scores(query_embs, proto):
    """Cosine similarity of each query embedding against a prototype."""
    q = F.normalize(query_embs, p=2, dim=-1)
    return (q @ proto).cpu().numpy()


def main(
    data_root: str,
    checkpoint: str,
    confusability_csv: str,
    split: str = "val",
    top_k: int = 6,
    max_queries: int = 50,
    report_dir: str = "data/eval",
    exclude_json: str | None = None,
    mlflow_tracking: bool = True,
) -> None:
    """Compute pairwise verification AUC for the top-K hardest identity pairs.

    Args:
        data_root: Dataset root containing the split subdirectory.
        checkpoint: Path to ``best.pth``.
        confusability_csv: Output of ``scripts/confusability.py`` — pairs sorted
            hardest-first.
        split: Which split to use for queries and gallery.
        top_k: How many hard pairs to evaluate.
        max_queries: Max query images per identity per pair.
        report_dir: Where to write the output CSV and JSON.
        exclude_json: Optional small-crop exclusion list.
        mlflow_tracking: Log the run to MLflow.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Device: {device}")

    # Load model
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
    embed_dim = ckpt.get("embed_dim", 128)
    image_size = ckpt.get("image_size", 224)
    model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=False, l2_normalize=True)
    model.load_state_dict(ckpt["model"])
    model.eval().to(device)

    # Index identities
    excluded: set[str] = set()
    if exclude_json:
        from src.uavid.preprocessing.filter_crops import load_excluded
        excluded = load_excluded(exclude_json)
    index = IdentityIndex(Path(data_root) / split, exclude=excluded,
                          exclude_root=Path(data_root))
    tfm = build_transform(image_size, train=False)

    # Load top-K hard pairs from confusability CSV
    with open(confusability_csv, encoding="utf-8") as f:
        all_pairs = list(csv.DictReader(f))
    # CSV is already sorted hardest-first
    hard_pairs = [
        (r["identity_a"], r["identity_b"], float(r["cosine_similarity"]))
        for r in all_pairs[:top_k]
        if r["identity_a"] in index.identities and r["identity_b"] in index.identities
    ]
    logger.info(f"Evaluating {len(hard_pairs)} hard pairs from {confusability_csv}")

    # Embed all query images once
    logger.info("Embedding all query images...")
    embeddings: dict[str, torch.Tensor] = {}
    for name, paths in index.identities.items():
        paths = paths[:max_queries]
        embeddings[name] = _embed(model, paths, tfm, device)

    # Per-pair AUC
    results = []
    for name_a, name_b, proto_sim in hard_pairs:
        emb_a = embeddings[name_a]
        emb_b = embeddings[name_b]
        proto_a = _proto(emb_a)
        proto_b = _proto(emb_b)

        # Positives: A vs A + B vs B
        pos = torch.cat([
            torch.tensor(_cosine_scores(emb_a, proto_a)),
            torch.tensor(_cosine_scores(emb_b, proto_b)),
        ]).numpy()
        # Negatives: A vs B + B vs A (the specific cross-impostor)
        neg = torch.cat([
            torch.tensor(_cosine_scores(emb_a, proto_b)),
            torch.tensor(_cosine_scores(emb_b, proto_a)),
        ]).numpy()

        auc = roc_auc(pos, neg)
        results.append({
            "identity_a": name_a,
            "identity_b": name_b,
            "proto_cosine_sim": proto_sim,
            "auc": auc,
            "genuine_mean": float(pos.mean()),
            "impostor_mean": float(neg.mean()),
            "genuine_n": len(pos),
            "impostor_n": len(neg),
        })
        logger.info(f"  {name_a:40s} vs {name_b:40s}  "
                    f"proto_sim={proto_sim:.4f}  AUC={auc:.4f}  "
                    f"genuine={pos.mean():.3f}  impostor={neg.mean():.3f}")

    results.sort(key=lambda r: r["auc"])

    # Write outputs
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    out_csv = report_dir / f"hardpair_auc_{split}.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    summary = {
        "split": split,
        "top_k": top_k,
        "n_pairs_evaluated": len(results),
        "mean_hardpair_auc": float(sum(r["auc"] for r in results) / len(results)),
        "min_hardpair_auc": results[0]["auc"],
        "hardest_pair": f"{results[0]['identity_a']} vs {results[0]['identity_b']}",
        "pairs": results,
    }
    out_json = report_dir / f"hardpair_auc_{split}_summary.json"
    out_json.write_text(json.dumps(summary, indent=2))
    logger.info(f"Wrote {out_csv} and {out_json}")
    logger.info(f"Mean hard-pair AUC: {summary['mean_hardpair_auc']:.4f}  "
                f"Min: {summary['min_hardpair_auc']:.4f}  "
                f"(hardest: {summary['hardest_pair']})")

    if mlflow_tracking:
        try:
            import mlflow
            import yaml
            cfg_path = Path(__file__).parent.parent / "configs" / "setup.yaml"
            cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
            uri = cfg.get("mlflow", {}).get("tracking_uri", "http://192.168.2.1:5000")
            exp = cfg.get("mlflow", {}).get("experiment_name", "uav_few_shot_identification")
            mlflow.set_tracking_uri(uri)
            mlflow.set_experiment(exp)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dataset_slug = Path(data_root).name
            with mlflow.start_run(run_name=f"hardpair_auc_{dataset_slug}_{split}_{ts}"):
                mlflow.log_params({
                    "dataset": dataset_slug,
                    "split": split,
                    "top_k": top_k,
                    "checkpoint": checkpoint,
                    "confusability_csv": confusability_csv,
                })
                mlflow.log_metrics({
                    "mean_hardpair_auc": summary["mean_hardpair_auc"],
                    "min_hardpair_auc": summary["min_hardpair_auc"],
                })
                for r in results:
                    safe_a = r["identity_a"].replace("-", "_")[:20]
                    safe_b = r["identity_b"].replace("-", "_")[:20]
                    mlflow.log_metrics({f"auc_{safe_a}_vs_{safe_b}": r["auc"]})
                mlflow.log_artifact(str(out_csv), artifact_path="hardpair_auc")
                mlflow.log_artifact(str(out_json), artifact_path="hardpair_auc")
            logger.info(f"MLflow run logged to {uri}")
        except Exception as exc:
            logger.warning(f"MLflow logging skipped: {exc}")


if __name__ == "__main__":
    fire.Fire(main)
