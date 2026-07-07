"""JSONL I/O, file hashing, and shared pipeline utilities."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file and return a list of dicts.

    Args:
        path: Path to the ``.jsonl`` file.

    Returns:
        List of parsed JSON objects, one per non-empty line.
    """
    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write a list of dicts as a JSONL file (one JSON object per line).

    Args:
        path: Destination file path.  Parent directories are created
            automatically.
        records: List of JSON-serialisable dicts to write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def md5_file(path: Path) -> str:
    """Compute MD5 hex digest of a file (DVC-compatible, 1 MiB chunks).

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
    """Build a unique MLflow run name from *prefix*, a timestamp, and git SHA.

    Args:
        prefix: Human-readable label prepended to the generated name.

    Returns:
        String in the form ``"<prefix>_YYYYMMDD_HHMMSS_<short-sha>"``.
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True,
        ).strip()
    except Exception:
        sha = "unknown"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}_{sha}"


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def parse_ood_filter(raw: str) -> dict[str, int]:
    """Parse an OOD filter string into a ``{corruption_type: min_severity}`` dict.

    The format is ``"type:min_sev,type:min_sev,..."``.
    The special token ``"all:N"`` expands to every corruption type in
    :data:`~src.ood.common.transforms.CORRUPTIONS` with minimum severity *N*.

    Args:
        raw: Comma-separated filter string, e.g. ``"fog:3,darken:2"``
            or ``"all:1"`` (default = no filtering).

    Returns:
        Dict mapping each corruption name to its minimum severity.

    Raises:
        ValueError: If a token cannot be parsed as ``"name:int"``.
    """
    from src.ood.common.transforms import CORRUPTIONS

    filt: dict[str, int] = {}
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        parts = token.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid ood_filter token: {token!r} (expected 'name:min_sev')")
        name, sev_str = parts
        sev = int(sev_str)
        if name == "all":
            return {c: sev for c in CORRUPTIONS}
        filt[name] = sev
    return filt


def filter_ood_records(
    records: list[dict],
    ood_filter: dict[str, int],
) -> list[dict]:
    """Keep only records whose type and severity satisfy *ood_filter*.

    A record is retained when its ``"type"`` appears in *ood_filter* **and**
    its ``"severity"`` is ≥ the corresponding minimum.

    Args:
        records: List of JSONL dicts with ``"type"`` and ``"severity"`` keys.
        ood_filter: Mapping from corruption name to minimum severity, as
            returned by :func:`parse_ood_filter`.

    Returns:
        Filtered list of records (order preserved).
    """
    return [
        r for r in records
        if r["type"] in ood_filter and int(r["severity"]) >= ood_filter[r["type"]]
    ]
