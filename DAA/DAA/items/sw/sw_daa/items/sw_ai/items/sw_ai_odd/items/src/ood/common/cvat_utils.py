"""Shared CVAT configuration and credential handling."""
from __future__ import annotations

import os

from loguru import logger


def load_cvat_credentials(
    cvat_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> tuple[str, str, str]:
    """Load and validate CVAT credentials from parameters or environment variables.

    Args:
        cvat_url: CVAT server URL. Falls back to ``CVAT_URL`` env var.
        username: CVAT username. Falls back to ``FIFTYONE_CVAT_USERNAME`` env var.
        password: CVAT password. Falls back to ``FIFTYONE_CVAT_PASSWORD`` env var.

    Returns:
        A tuple of (cvat_url, username, password).

    Raises:
        ValueError: If any credential is missing.
    """
    cvat_url = cvat_url or os.environ.get("CVAT_URL")
    username = username or os.environ.get("FIFTYONE_CVAT_USERNAME")
    password = password or os.environ.get("FIFTYONE_CVAT_PASSWORD")

    if not all([cvat_url, username, password]):
        msg = "CVAT_URL, FIFTYONE_CVAT_USERNAME, FIFTYONE_CVAT_PASSWORD must be set."
        logger.error(msg)
        raise ValueError(msg)

    return cvat_url, username, password
