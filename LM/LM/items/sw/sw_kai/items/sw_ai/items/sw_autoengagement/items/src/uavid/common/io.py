"""File hashing, run-name generation and shared pipeline utilities."""
from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def md5_file(path: Path | str) -> str:
    """Compute the MD5 hex digest of a file (DVC-compatible, 1 MiB chunks).

    Args:
        path: Path to the file to hash.

    Returns:
        Lowercase hexadecimal MD5 digest string.
    """
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(2**20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_name(prefix: str) -> str:
    """Build a unique MLflow run name from *prefix*, a timestamp and git SHA.

    Args:
        prefix: Human-readable label prepended to the generated name.

    Returns:
        String of the form ``"<prefix>_YYYYMMDD_HHMMSS_<short-sha>"``.
    """
    try:
        # Use __file__ as anchor so git is called from within the repo tree,
        # regardless of the cwd uv/the caller happens to use.
        repo_dir = Path(__file__).resolve().parent
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True, cwd=repo_dir,
        ).strip()
    except Exception:
        sha = "unknown"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}_{sha}"


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()
