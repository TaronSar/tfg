"""Stage 03b: export relabel queue artifact and create/push a CVAT task."""
from __future__ import annotations

import json
from pathlib import Path

import fire
from dotenv import load_dotenv
from loguru import logger

from src.ood.common.config_loader import (
    load_curation_config,
    load_fiftyone_dataset_name,
    load_paths_config,
)
from src.ood.common.cvat_utils import load_cvat_credentials
from src.ood.common.fiftyone_utils import load_fiftyone_dataset
from src.ood.curation.cvat_sync import push_relabel_queue
from src.ood.curation.queue_stage import (
    build_queue_rows,
    validate_queue_nonempty,
    write_queue_jsonl,
)

load_dotenv()


def main(
    dataset_name: str | None = None,
    anno_key: str = "relabel",
    queue_out: str | None = None,
    task_out: str | None = None,
    cvat_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    label_classes: str = "Urban,Non-urban,Water,Exclude",
) -> None:
    """Export relabel queue and push the corresponding samples to CVAT.
    
    Iteration-specific annotation key and label classes default to the values
    used by the pipeline; the DVC stage passes them explicitly. File paths
    and dataset name fall back to constants in dvc_config.yaml when not provided.
    """
    # Load config defaults
    curation_cfg = load_curation_config()
    paths_cfg = load_paths_config()
    dataset_name = dataset_name or load_fiftyone_dataset_name()
    queue_out = queue_out or (Path(paths_cfg["cvat_queue_dir"]) / curation_cfg["cvat_queue_file"])
    task_out = task_out or (Path(paths_cfg["cvat_queue_dir"]) / curation_cfg["cvat_task_file"])
    dataset = load_fiftyone_dataset(dataset_name)

    # Filter once and reuse the view to avoid double-filtering
    view = dataset.match_tags("relabel")
    rows = build_queue_rows(view, anno_key)
    has_queue_rows = validate_queue_nonempty(rows, allow_empty=True)

    classes = [c.strip() for c in label_classes.split(",")]

    if not has_queue_rows:
        task_info = {
            "dataset_name": dataset_name,
            "anno_key": anno_key,
            "queue_rows": 0,
            "skipped": True,
            "reason": "empty_relabel_queue",
            "label_classes": classes,
        }
        task_out_p = Path(task_out)
        task_out_p.parent.mkdir(parents=True, exist_ok=True)
        task_out_p.write_text(json.dumps(task_info, indent=2), encoding="utf-8")
        logger.success(
            "No pending relabel samples. Wrote task info and skipped CVAT push."
        )
        return

    # Write queue artifact only when it has content
    write_queue_jsonl(Path(queue_out), rows)

    cvat_url, username, password = load_cvat_credentials(cvat_url, username, password)
    push_relabel_queue(view, anno_key, cvat_url, username, password, classes, skip_filter=True)

    task_info = {
        "dataset_name": dataset_name,
        "anno_key": anno_key,
        "queue_rows": len(rows),
        "cvat_url": cvat_url,
        "label_classes": classes,
    }
    task_out_p = Path(task_out)
    task_out_p.parent.mkdir(parents=True, exist_ok=True)
    task_out_p.write_text(json.dumps(task_info, indent=2), encoding="utf-8")
    logger.success(f"Wrote CVAT task metadata -> {task_out_p}")


if __name__ == "__main__":
    fire.Fire(main)
