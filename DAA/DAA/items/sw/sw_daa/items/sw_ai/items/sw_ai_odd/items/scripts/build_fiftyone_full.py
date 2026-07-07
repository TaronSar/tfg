"""Build the full-image FiftyOne dataset for ID/OOD visualisation.

Stage 10 of the OOD pipeline.  Materialises a persistent FiftyOne dataset of
*full-size* frames — clean (in-distribution) frames from the curated
background-classification and corrupted (out-of-distribution) frames
of stage 05.  Each sample carries:

* the background-classification label,
* the corruption type / severity (``None`` / ``0`` for clean frames),
* the per-image energy OOD score and ID-vs-OOD verdict from stage 09, and
* a ``group_id`` equal to the source frame so the App can group each clean
  frame with all its corrupted variants.

No detection boxes are attached here — those live on the crops dataset.

A DVC-tracked JSONL snapshot and a stamp file are written to *output_dir*.
"""
from __future__ import annotations

from pathlib import Path

import fire
from loguru import logger
import fiftyone as fo

from src.ood.common.fiftyone_utils import build_ood_fiftyone_dataset, resolve_image_path
from src.ood.common.io import read_jsonl
from src.ood.preprocessing.corruptions import corrupted_full_path


def _load_full_rows(
    aot_root: Path,
    curated_dir: Path,
    corrupted_full_dir: Path,
    full_dir: Path,
    splits: tuple[str, ...],
) -> list[dict]:
    """Collect clean + corrupted full-frame sample rows.

    Args:
        aot_root: Root path of the AOT dataset (clean full frames).
        curated_dir: Directory of curated background JSONLs (``<split>.jsonl``).
        corrupted_full_dir: Local dir of corrupted-full manifests
            (``<split>/dataset.jsonl``).
        full_dir: Root of the corrupted full-image tree.
        splits: Splits to include.

    Returns:
        List of flat sample dicts (one per full frame variant).
    """
    rows: list[dict] = []
    for split in splits:
        clean_path = curated_dir / f"{split}.jsonl"
        if clean_path.exists():
            for rec in read_jsonl(clean_path):
                rows.append(
                    {
                        "split": split,
                        "source_variant": "clean",
                        "img_name": rec.get("img_name"),
                        "filepath": str((aot_root / rec["path"]).absolute()),
                        "source_frame": rec["path"],
                        "flight_id": rec.get("flight_id"),
                        "time": rec.get("time"),
                        "background_label_gt": rec["label"],
                        "corruption_type": None,
                        "corruption_severity": 0,
                    }
                )
        else:
            logger.warning(f"Curated JSONL not found: {clean_path}")

        corr_path = corrupted_full_dir / split / "dataset.jsonl"
        if corr_path.exists():
            for rec in read_jsonl(corr_path):
                full_path = corrupted_full_path(
                    rec["path"], rec["type"], int(rec["severity"]), full_dir
                )
                rows.append(
                    {
                        "split": split,
                        "source_variant": f"{rec['type']}_{int(rec['severity'])}",
                        "img_name": rec.get("img_name"),
                        "filepath": str(full_path.absolute()),
                        "source_frame": rec["path"],
                        "flight_id": rec.get("flight_id"),
                        "time": rec.get("time"),
                        "background_label_gt": rec["label"],
                        "corruption_type": rec["type"],
                        "corruption_severity": int(rec["severity"]),
                    }
                )
        else:
            logger.warning(f"Corrupted-full manifest not found: {corr_path}")
    return rows


def build_fiftyone_full(
    aot_root: str,
    curated_dir: str,
    corrupted_full_dir: str,
    full_dir: str,
    ood_samples_jsonl: str,
    output_dir: str,
    dataset_name: str,
    splits: str = "train,val,test",
) -> None:
    """Build the full-image FiftyOne dataset plus DVC snapshot.

    Args:
        aot_root: Root path of the AOT dataset.
        curated_dir: Directory of curated background JSONLs (stage 04).
        corrupted_full_dir: Local dir of corrupted-full manifests (stage 05).
        full_dir: Root of the corrupted full-image tree.
        ood_samples_jsonl: Per-sample OOD export from stage 09
            (``ood_per_sample.jsonl``).
        output_dir: Directory for snapshot/stamp artifacts.
        dataset_name: FiftyOne persistent dataset name to (re)create.
        splits: Comma-separated splits to include.
    """
    aot_root_p = Path(aot_root)
    curated_dir_p = Path(curated_dir)
    corrupted_full_dir_p = Path(corrupted_full_dir)
    full_dir_p = Path(full_dir)
    ood_path = Path(ood_samples_jsonl)
    output_dir_p = Path(output_dir)
    output_dir_p.mkdir(parents=True, exist_ok=True)
    if isinstance(splits, str):
        split_tuple = tuple(s.strip() for s in splits.split(",") if s.strip())
    else:
        split_tuple = tuple(splits)

    rows = _load_full_rows(
        aot_root_p, curated_dir_p, corrupted_full_dir_p, full_dir_p, split_tuple
    )

    ood_rows = read_jsonl(ood_path) if ood_path.exists() else []
    ood_by_filepath: dict[str, dict] = {}
    for r in ood_rows:
        fp = resolve_image_path(r.get("filepath"))
        if fp is not None:
            ood_by_filepath[fp] = r
    logger.info(f"Loaded {len(ood_by_filepath):,} OOD-scored full frames from {ood_path}")

    def _get_ood(_row: dict, fp: str) -> dict | None:
        return ood_by_filepath.get(fp)

    def _enrich(sample: fo.Sample, row: dict) -> None:
        sample["source_split"] = row["split"]
        sample["flight_id"] = row.get("flight_id")

    def _extra_snapshot(row: dict) -> dict:
        return {"source_split": row["split"]}

    def _extra_stats(snapshot_rows: list[dict]) -> dict:
        return {"num_ood_scored": sum(1 for r in snapshot_rows if r["ood_score_energy"] is not None)}

    build_ood_fiftyone_dataset(
        rows=rows,
        get_ood=_get_ood,
        enrich_sample=_enrich,
        extra_snapshot_fields=_extra_snapshot,
        extra_stats=_extra_stats,
        index_fields=(
            "source_split",
            "source_variant",
            "group_id",
            "background_label_gt",
            "background_label_pred",
            "corruption_type",
            "corruption_severity",
            "ood_score_energy",
            "ood_label",
        ),
        dataset_name=dataset_name,
        dataset_description="OOD full-image visual dataset",
        output_dir=output_dir_p,
        stamp_name="10_build_fiftyone_full.stamp",
        snapshot_filename="fiftyone_full_snapshot.jsonl",
        stats_filename="fiftyone_full_stats.jsonl",
    )


if __name__ == "__main__":
    fire.Fire(build_fiftyone_full)
