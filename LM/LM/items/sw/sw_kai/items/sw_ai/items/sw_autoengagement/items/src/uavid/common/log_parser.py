"""Parse the ProtoNet training logs into structured run records.

The historical training runs (the ``checkpoints_*`` directories) were produced
before MLflow was wired in. Their stdout was captured to ``logs/*.log`` /
``*.txt``. This module turns those logs back into structured metrics so they
can be re-played into MLflow for full experiment traceability.

Log header (example, mixed-domain run)::

    Device: cuda
    Train: 36 identities | images per identity: min=96 max=96 total=3456
    Val:   11 identities | images per identity: min=96 max=96 total=1056
    Support (enrollment): 31 identities | ...
    Mixed-domain train identities: 20 shared train/support
    Mixed-domain val identities:   11 shared val/support
    Metric: euclidean | L2-normalize: True | train-way: 15 -> test-way: 5
    Shot-robust training: K sampled per-episode from [1, 3, 5, 10, 15]

Per-epoch line::

    epoch 001 | loss 2.5365 | train acc 0.156 | val acc 0.386 | 193.6s | backbone frozen
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_EPOCH_RE = re.compile(
    r"epoch\s+(\d+)\s*\|\s*loss\s+([\d.]+)\s*\|\s*train acc\s+([\d.]+)\s*"
    r"\|\s*val acc\s+([\d.]+)\s*\|\s*([\d.]+)s(.*)$"
)
_METRIC_RE = re.compile(
    r"Metric:\s*(\w+)\s*\|\s*L2-normalize:\s*(\w+)\s*\|\s*"
    r"train-way:\s*(\d+)\s*->\s*test-way:\s*(\d+)"
)
_SHOT_RE = re.compile(r"Shot-robust training:.*from\s*\[([\d,\s]+)\]")
_COUNT_RE = re.compile(r"^(Train|Val):\s*(\d+)\s+identities")
_SUPPORT_RE = re.compile(r"^Support \(([^)]+)\):\s*(\d+)\s+identities")
_SHARED_RE = re.compile(r"Mixed-domain (train|val) identities:\s*(\d+)")


@dataclass
class EpochRecord:
    epoch: int
    loss: float
    train_acc: float
    val_acc: float
    time_s: float
    backbone_frozen: bool


@dataclass
class TrainingLog:
    path: Path
    params: dict = field(default_factory=dict)
    epochs: list[EpochRecord] = field(default_factory=list)

    @property
    def best_val_acc(self) -> float:
        return max((e.val_acc for e in self.epochs), default=0.0)

    @property
    def best_epoch(self) -> int:
        if not self.epochs:
            return 0
        return max(self.epochs, key=lambda e: e.val_acc).epoch

    @property
    def final_epoch(self) -> int:
        return self.epochs[-1].epoch if self.epochs else 0


def _read_text(path: Path) -> str:
    """Read a log file, transparently handling UTF-8 / UTF-16 (BOM-detected).

    Args:
        path: Path to the log file.

    Returns:
        Decoded text content of the file.
    """
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def parse_training_log(path: str | Path) -> TrainingLog:
    """Parse a single training log into a :class:`TrainingLog`.

    Args:
        path: Path to the ``.log`` or ``.txt`` training output file.

    Returns:
        :class:`TrainingLog` with ``params`` dict and list of
        :class:`EpochRecord` entries.
    """
    path = Path(path)
    text = _read_text(path)
    log = TrainingLog(path=path)

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        m = _EPOCH_RE.search(line)
        if m:
            log.epochs.append(
                EpochRecord(
                    epoch=int(m.group(1)),
                    loss=float(m.group(2)),
                    train_acc=float(m.group(3)),
                    val_acc=float(m.group(4)),
                    time_s=float(m.group(5)),
                    backbone_frozen="frozen" in m.group(6).lower(),
                )
            )
            continue

        m = _METRIC_RE.search(line)
        if m:
            log.params["metric"] = m.group(1)
            log.params["l2_normalize"] = m.group(2) == "True"
            log.params["train_way"] = int(m.group(3))
            log.params["test_way"] = int(m.group(4))
            continue

        m = _SHOT_RE.search(line)
        if m:
            log.params["k_shot_range"] = [int(x) for x in m.group(1).split(",")]
            continue

        m = _COUNT_RE.search(line)
        if m:
            key = "n_train_identities" if m.group(1) == "Train" else "n_val_identities"
            log.params[key] = int(m.group(2))
            continue

        m = _SUPPORT_RE.search(line)
        if m:
            log.params["support_split"] = m.group(1)
            log.params["n_support_identities"] = int(m.group(2))
            continue

        m = _SHARED_RE.search(line)
        if m:
            key = f"n_shared_{m.group(1)}_support"
            log.params[key] = int(m.group(2))
            continue

        if line.startswith("Device:"):
            log.params["device"] = line.split(":", 1)[1].strip()

    return log
