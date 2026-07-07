"""Identify query images against an enrolled gallery via the ``Verifier``."""
from __future__ import annotations

from pathlib import Path

from src.uavid.common.constants import IMG_EXTS
from src.uavid.inference.verifier import Verifier


def identify_paths(gallery: str | Path, images: str | Path,
                   checkpoint: str | None = None, threshold: float = 0.6,
                   device: str | None = None) -> list[tuple[Path, float, str]]:
    """Score query images against an enrolled gallery and return verdicts.

    Args:
        gallery: Path to the enrolled ``gallery.npy``.
        images: Query image or folder of query images.
        checkpoint: Trained checkpoint (None -> zero-shot features).
        threshold: Score at/above which a query is declared ``MATCH``.
        device: Torch device string (auto-detected if None).

    Returns:
        List of ``(path, score, verdict)`` tuples, ``verdict`` in
        ``{"MATCH", "unknown"}``.

    Raises:
        SystemExit: If no query images are found.
    """
    vf = Verifier(checkpoint, gallery, device=device)
    src = Path(images)
    paths = ([src] if src.is_file()
             else sorted(f for f in src.rglob("*") if f.suffix.lower() in IMG_EXTS))
    if not paths:
        raise SystemExit(f"No images found in {images}")

    scores = vf.score(vf.embed_paths(paths))
    results: list[tuple[Path, float, str]] = []
    for path, s in zip(paths, scores):
        verdict = "MATCH" if s >= threshold else "unknown"
        results.append((path, float(s), verdict))
    return results
