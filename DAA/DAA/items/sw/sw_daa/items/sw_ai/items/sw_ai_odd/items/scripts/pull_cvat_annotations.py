"""Stage 03c: fail-fast pull of CVAT annotations and resolved annotation artifact export."""
from __future__ import annotations

import json
import os
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
from src.ood.common.io import read_jsonl
from src.ood.curation.annotation_stage import (
    assert_annotation_run_complete,
    build_annotations_rows,
    write_annotations_jsonl,
)
from src.ood.curation.cvat_sync import apply_cvat_annotations

load_dotenv()


def main(
    dataset_name: str | None = None,
    anno_key: str = "relabel_round3",
    queue_in: str | None = None,
    task_in: str | None = None,
    annotations_out: str | None = None,
    cvat_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    skip_status_check: bool = False,
) -> None:
    """Pull CVAT annotations and export resolved decisions for queued samples.
    
    Iteration-specific annotation key defaults to the value used by the pipeline;
    the DVC stage passes it explicitly. File paths and dataset name fall back to
    constants in dvc_config.yaml when not provided.
    """
    # Load config defaults
    curation_cfg = load_curation_config()
    paths_cfg = load_paths_config()
    dataset_name = dataset_name or load_fiftyone_dataset_name()
    queue_in = queue_in or str(Path(paths_cfg["cvat_queue_dir"]) / curation_cfg["cvat_queue_file"])
    task_in = task_in or str(Path(paths_cfg["cvat_queue_dir"]) / curation_cfg["cvat_task_file"])
    annotations_out = annotations_out or str(
        Path(paths_cfg["cvat_annotations_dir"]) / curation_cfg["cvat_annotations_file"]
    )
    task_in_p = Path(task_in)
    if task_in_p.exists():
        task = json.loads(task_in_p.read_text(encoding="utf-8"))
        anno_key = task.get("anno_key", anno_key)

    queue_rows = read_jsonl(Path(queue_in))
    if not queue_rows:
        logger.warning(
            f"Queue artifact '{queue_in}' is empty. "
            "Writing empty annotations artifact and skipping CVAT pull."
        )
        write_annotations_jsonl(Path(annotations_out), [])
        return

    dataset = load_fiftyone_dataset(dataset_name)
    assert_annotation_run_complete(dataset, anno_key, skip_check=skip_status_check)

    cvat_url, username, password = load_cvat_credentials(cvat_url, username, password)
    apply_cvat_annotations(dataset, anno_key, cvat_url, username, password)
    rows = build_annotations_rows(dataset, queue_rows, anno_key)
    write_annotations_jsonl(Path(annotations_out), rows)


if __name__ == "__main__":
    fire.Fire(main)
