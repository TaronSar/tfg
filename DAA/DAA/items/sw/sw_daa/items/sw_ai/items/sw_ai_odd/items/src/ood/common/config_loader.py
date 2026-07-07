"""Centralized configuration loader for DVC config.yaml.

Provides type-safe functions to load configuration values with proper defaults.
All configuration is sourced from configs/dvc_config.yaml which is the single
source of truth for pipeline parameters.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Module-level cache to avoid re-parsing YAML on every function call
_CONFIG_CACHE: dict | None = None


def _get_config_path() -> Path:
    """Return path to dvc_config.yaml relative to project root."""
    # Adjust based on where this module is called from
    current = Path(__file__)
    project_root = current.parent.parent.parent.parent  # src/ood/common/config_loader.py -> items/
    config_file = project_root / "configs" / "dvc_config.yaml"
    return config_file


def _load_config_dict() -> dict:
    """Load and return the complete dvc_config.yaml as a dict (cached).
    
    Parses the YAML file only once per interpreter session; subsequent calls
    return the cached dict. This avoids redundant disk I/O across multiple
    config loader calls within a single script invocation.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        config_path = _get_config_path()
        with open(config_path, encoding="utf-8") as f:
            _CONFIG_CACHE = yaml.safe_load(f)
    return _CONFIG_CACHE


def load_fiftyone_dataset_name() -> str:
    """Load FiftyOne dataset name from config.

    Returns:
        Dataset name (default: "ood_cleanlab_audit").
    """
    cfg = _load_config_dict()
    return cfg["fiftyone"]["dataset_name"]


def load_curation_config() -> dict:
    """Load curation configuration section.

    Returns:
        Dict with the curation file-name constants: cvat_queue_file,
        cvat_task_file, cvat_annotations_file, curation_snapshot_file.
    """
    cfg = _load_config_dict()
    return cfg["curation"]


def load_dataset_config() -> dict:
    """Load dataset taxonomy configuration.

    Returns:
        Dict with keys: classes, mix_category, prompts.
    """
    cfg = _load_config_dict()
    return cfg["dataset"]


def load_paths_config() -> dict:
    """Load all path configuration.

    Returns:
        Dict with all path keys (aot_root, curation_snapshot_dir, models_dir, etc.).
    """
    cfg = _load_config_dict()
    return cfg["paths"]
