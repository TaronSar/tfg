r"""CLI: pairwise identity confusability analysis.

For every pair of identities in a dataset split, computes the cosine similarity
between their mean prototypes. Outputs:

- A CSV with all N*(N-1)/2 pairs sorted by similarity (hard → easy)
- The top-K hardest pairs (most confusable) and bottom-K easiest
- MLflow run with the full matrix logged as an artifact and key stats as metrics

Usage::

    PYTHONPATH=. uv run python scripts/confusability.py \\
        --data_root Z:/Pool_IA/IA_Dataset/datasets/ \\
            uav-few-shot-identification/uav_dataset_yolox_crops \\
        --split train \\
        --checkpoint models/00_train/best.pth \\
        --top_k 10
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
from src.uavid.model import BACKBONE_NORM, build_encoder

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _build_prototypes(
    index: IdentityIndex, model: torch.nn.Module, tfm, device: str, batch_size: int = 32
) -> dict[str, torch.Tensor]:
    """Return L2-normalised mean prototype per identity."""
    model.eval()
    protos = {}
    with torch.no_grad():
        for name, paths in index.identities.items():
            embeddings = []
            for start in range(0, len(paths), batch_size):
                chunk = paths[start : start + batch_size]
                batch = torch.stack([load_image(p, tfm) for p in chunk]).to(device)
                embeddings.append(model(batch))
            emb = torch.cat(embeddings, dim=0)
            proto = F.normalize(emb.mean(dim=0), p=2, dim=0)
            protos[name] = proto
    return protos


def main(
    data_root: str,
    checkpoint: str,
    split: str = "train",
    top_k: int = 10,
    report_dir: str = "data/eval",
    exclude_json: str | None = None,
    mlflow_tracking: bool = True,
) -> None:
    """Compute pairwise identity confusability for all identities in ``split``.

    Args:
        data_root: Dataset root containing the split subdirectory.
        checkpoint: Path to ``best.pth``.
        split: Which split to analyse (default ``train``).
        top_k: Number of hardest / easiest pairs to report.
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
    backbone = ckpt.get("backbone", "mobilenetv3")
    model = build_encoder(backbone, embed_dim=embed_dim, pretrained=False, l2_normalize=True)
    model.load_state_dict(ckpt["model"])
    model.to(device)

    # Index identities
    excluded: set[str] = set()
    if exclude_json:
        from src.uavid.preprocessing.filter_crops import load_excluded

        excluded = load_excluded(exclude_json)
    index = IdentityIndex(Path(data_root) / split, exclude=excluded, exclude_root=Path(data_root))
    norm_mean, norm_std = BACKBONE_NORM[backbone]
    tfm = build_transform(image_size, train=False, mean=norm_mean, std=norm_std)
    logger.info(f"Indexing {len(index.identities)} identities in {split}/")

    # Build prototypes
    protos = _build_prototypes(index, model, tfm, device)
    names = sorted(protos.keys())
    n = len(names)
    logger.info(f"Built {n} prototypes")

    # Pairwise cosine similarity
    proto_matrix = torch.stack([protos[name] for name in names])  # (N, D)
    sim_matrix = (proto_matrix @ proto_matrix.T).cpu()  # (N, N)

    # Collect all unique pairs
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append(
                {
                    "identity_a": names[i],
                    "identity_b": names[j],
                    "cosine_similarity": float(sim_matrix[i, j]),
                }
            )

    pairs.sort(key=lambda x: x["cosine_similarity"], reverse=True)

    # Write full pairs CSV
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    pairs_csv = report_dir / f"confusability_{split}.csv"
    with pairs_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["identity_a", "identity_b", "cosine_similarity"])
        writer.writeheader()
        writer.writerows(pairs)

    hard_pairs = pairs[:top_k]
    easy_pairs = pairs[-top_k:]

    summary = {
        "split": split,
        "n_identities": n,
        "n_pairs": len(pairs),
        "mean_similarity": float(sim_matrix.triu(diagonal=1).sum() / (n * (n - 1) / 2)),
        "hard_pairs": hard_pairs,
        "easy_pairs": easy_pairs,
    }
    summary_json = report_dir / f"confusability_{split}_summary.json"
    summary_json.write_text(json.dumps(summary, indent=2))

    logger.info(f"Wrote {pairs_csv}")
    logger.info(f"Wrote {summary_json}")
    logger.info(f"\nTop-{top_k} HARDEST pairs (most confusable):")
    for p in hard_pairs:
        logger.info(
            f"  {p['identity_a']:40s} vs {p['identity_b']:40s}  sim={p['cosine_similarity']:.4f}"
        )
    logger.info(f"\nTop-{top_k} EASIEST pairs (least confusable):")
    for p in easy_pairs:
        logger.info(
            f"  {p['identity_a']:40s} vs {p['identity_b']:40s}  sim={p['cosine_similarity']:.4f}"
        )

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
            with mlflow.start_run(run_name=f"confusability_{dataset_slug}_{split}_{ts}"):
                mlflow.log_params(
                    {
                        "dataset": dataset_slug,
                        "split": split,
                        "n_identities": n,
                        "checkpoint": checkpoint,
                        "top_k": top_k,
                    }
                )
                mlflow.log_metrics(
                    {
                        "mean_pairwise_similarity": summary["mean_similarity"],
                        "hardest_pair_sim": hard_pairs[0]["cosine_similarity"],
                        "easiest_pair_sim": easy_pairs[0]["cosine_similarity"],
                    }
                )
                for i, p in enumerate(hard_pairs, 1):
                    mlflow.set_tag(
                        f"hard_pair_{i:02d}",
                        f"{p['identity_a']} vs {p['identity_b']} ({p['cosine_similarity']:.4f})",
                    )
                mlflow.log_artifact(str(pairs_csv), artifact_path="confusability")
                mlflow.log_artifact(str(summary_json), artifact_path="confusability")
            logger.info(f"MLflow run logged to {uri}")
        except Exception as exc:
            logger.warning(f"MLflow logging skipped: {exc}")


if __name__ == "__main__":
    fire.Fire(main)
