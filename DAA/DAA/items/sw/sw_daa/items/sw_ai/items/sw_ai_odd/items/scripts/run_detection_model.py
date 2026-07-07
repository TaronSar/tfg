"""Run object-detection inference via Docker.

Currently supports YOLOX (MMEngine-based), but the module is designed to
be extended with additional detectors in the future.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

_DOCKER_IMAGE = os.environ.get("DOCKER_IMAGE", "edgeai-tensorlab-tidl:r11.1")
_EDGEAI_ROOT = os.environ.get("EDGEAI_ROOT", "/workspace/edgeai-tensorlab/edgeai-mmdetection")
_PROJECT_MOUNT = os.environ.get("PROJECT_MOUNT", "/workspace/sw_ai_detection")
_DEGRADATION_MOUNT = os.environ.get("DEGRADATION_MOUNT", "/workspace/degradation_data")


def run_yolox_docker(
    sw_ai_detection_root: Path,
    work_dir: Path,
    config_path: Path,
    checkpoint_path: Path,
    image_prefix: str | None = None,
) -> Path:
    """Run YOLOX inference inside Docker and return the predictions path.

    Args:
        sw_ai_detection_root: Absolute path to ``sw_ai_detection/items/``.
        work_dir: Working directory containing ``combined_coco.json`` and
            (when *image_prefix* is ``None``) an ``images/`` subdirectory.
        config_path: Path to the MMEngine experiment config.
        checkpoint_path: Path to the ``.pth`` checkpoint.
        image_prefix: Override for ``test_dataloader.dataset.data_prefix.img``.
            When ``None`` (default) crops are read from ``images/`` inside the
            mounted work dir.  Pass an empty string ``""`` when the combined
            COCO ``file_name`` fields are absolute NAS paths (the NAS is
            bind-mounted at the same path inside the container), so YOLOX
            reads each crop directly from its absolute path.

    Returns:
        Absolute path to ``predictions.bbox.json``.

    Raises:
        RuntimeError: If ``LOCAL_NAS_PATH`` is not set.
        FileNotFoundError: If the predictions file is not created.
    """
    sw_root = sw_ai_detection_root.resolve()
    work_abs = work_dir.resolve()
    config_abs = config_path.resolve()
    checkpoint_abs = checkpoint_path.resolve()

    nas_path = os.environ.get("LOCAL_NAS_PATH", "")
    if not nas_path:
        env_file = sw_root / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)
            nas_path = os.environ.get("LOCAL_NAS_PATH", "")
    if not nas_path:
        raise RuntimeError(f"LOCAL_NAS_PATH not set.  Export it or add it to {sw_root / '.env'}")

    config_rel = config_abs.relative_to(sw_root)
    checkpoint_rel = checkpoint_abs.relative_to(sw_root)
    outfile_prefix = f"{_DEGRADATION_MOUNT}/predictions"
    img_prefix = f"{_DEGRADATION_MOUNT}/images/" if image_prefix is None else image_prefix

    cmd = [
        "docker",
        "run",
        "--rm",
        "--gpus",
        "all",
        "--network",
        "host",
        "--ipc=host",
        "-v",
        f"{sw_root}:{_PROJECT_MOUNT}",
        "-v",
        f"{nas_path}:{nas_path}:ro",
        "-v",
        f"{work_abs}:{_DEGRADATION_MOUNT}",
        "-e",
        f"PYTHONPATH={_PROJECT_MOUNT}/src/train",
        "-e",
        "MLFLOW_ENABLE_AUTOLOGGING=false",
        "-e",
        "DEBIAN_FRONTEND=noninteractive",
        _DOCKER_IMAGE,
        "python",
        f"{_EDGEAI_ROOT}/tools/test.py",
        f"{_PROJECT_MOUNT}/{config_rel}",
        f"{_PROJECT_MOUNT}/{checkpoint_rel}",
        "--cfg-options",
        f"test_dataloader.dataset.ann_file={_DEGRADATION_MOUNT}/combined_coco.json",
        f"test_dataloader.dataset.data_prefix.img={img_prefix}",
        "test_dataloader.dataset.data_root=",
        f"test_evaluator.outfile_prefix={outfile_prefix}",
        f"test_evaluator.ann_file={_DEGRADATION_MOUNT}/combined_coco.json",
    ]

    logger.info("Running YOLOX inference via Docker …")
    logger.info(f"  Config:     {config_rel}")
    logger.info(f"  Checkpoint: {checkpoint_rel}")
    logger.info(f"  Image root: {img_prefix or '<absolute file_name paths>'}")
    logger.debug("  " + " ".join(cmd))

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Docker exited with code {result.returncode}")

    pred_path = work_abs / "predictions.bbox.json"
    if not pred_path.exists():
        raise FileNotFoundError(f"Expected predictions at {pred_path}")
    logger.info(f"Predictions written to {pred_path}")
    return pred_path
