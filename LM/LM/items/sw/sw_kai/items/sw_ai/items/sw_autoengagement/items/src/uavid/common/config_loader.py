"""Centralised configuration loader for ``configs/dvc_config.yaml``.

``configs/dvc_config.yaml`` is the single source of truth for pipeline
parameters; ``configs/setup.yaml`` holds machine/environment settings. All
loaders cache the parsed YAML to avoid redundant disk I/O within a run.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_DVC_CONFIG_CACHE: dict | None = None
_SETUP_CONFIG_CACHE: dict | None = None


def _project_root() -> Path:
    """Return the item project root (``items/``) relative to this module."""
    # src/uavid/common/config_loader.py -> items/
    return Path(__file__).resolve().parents[3]


def _load_dvc_config() -> dict:
    """Load and cache ``configs/dvc_config.yaml`` as a dict."""
    global _DVC_CONFIG_CACHE
    if _DVC_CONFIG_CACHE is None:
        path = _project_root() / "configs" / "dvc_config.yaml"
        with open(path, encoding="utf-8") as f:
            _DVC_CONFIG_CACHE = yaml.safe_load(f)
    return _DVC_CONFIG_CACHE


def _load_setup_config() -> dict:
    """Load and cache ``configs/setup.yaml`` as a dict."""
    global _SETUP_CONFIG_CACHE
    if _SETUP_CONFIG_CACHE is None:
        path = _project_root() / "configs" / "setup.yaml"
        with open(path, encoding="utf-8") as f:
            _SETUP_CONFIG_CACHE = yaml.safe_load(f)
    return _SETUP_CONFIG_CACHE


def load_paths_config() -> dict:
    """Return the ``paths`` section (dataset roots, derived-artifact dirs).

    Returns:
        Dict with NAS source paths and in-repo output directory keys.
    """
    return _load_dvc_config()["paths"]


def active_dataset_dir() -> str:
    """Return the absolute NAS path of the active training dataset.

    Composed as ``<datasets_root>/<active_dataset>``. This is the curated source
    dataset consumed by training (referenced as an external DVC dep, not
    ``dvc add``-ed).
    """
    paths = load_paths_config()
    return f"{paths['datasets_root']}/{paths['active_dataset']}"


def load_operational_config() -> dict:
    """Return the ``operational`` section (pixel envelope, model input size).

    Returns:
        Dict with ``min_px``, ``max_px``, and ``model_input_size`` keys.
    """
    return _load_dvc_config()["operational"]


def load_split_config() -> dict:
    """Return the ``split`` section (train/val/test ratios and seed).

    Returns:
        Dict with ``train_ratio``, ``val_ratio``, ``test_ratio``, and
        ``seed`` keys.
    """
    return _load_dvc_config()["split"]


def load_train_config() -> dict:
    """Return the ``train`` section (episodic hyperparameters).

    Returns:
        Dict with ``k_shot_range``, ``support_split``, and ``embed_dim`` keys.
    """
    return _load_dvc_config()["train"]


def load_fiftyone_config() -> dict:
    """Return the ``fiftyone`` section (MongoDB URI, dataset name).

    Returns:
        Dict with ``database_uri`` and ``dataset_name`` keys.
    """
    return _load_dvc_config()["fiftyone"]


def load_encoder_config() -> dict:
    """Return encoder architecture defaults (``embed_dim``, ``image_size``).

    These values are the single source of truth for the encoder architecture.
    ``embed_dim`` lives under ``train`` (it is a training hyperparameter saved
    into every checkpoint); ``image_size`` comes from ``operational.model_input_size``
    (the KAI sensor geometry constrains the input resolution).

    Returns:
        Dict with integer keys ``embed_dim`` and ``image_size``.
    """
    cfg = _load_dvc_config()
    return {
        "embed_dim": cfg["train"]["embed_dim"],
        "image_size": cfg["operational"]["model_input_size"],
    }


def load_mlflow_config() -> dict:
    """Return the ``mlflow`` section from ``configs/setup.yaml``.

    Returns:
        Dict with ``tracking_uri`` and ``experiment_name`` keys.
    """
    return _load_setup_config()["mlflow"]
