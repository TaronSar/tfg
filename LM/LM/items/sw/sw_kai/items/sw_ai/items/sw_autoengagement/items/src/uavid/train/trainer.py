"""Episodic prototypical training logic (pure -- no MLflow, no argument parsing).

Following the department convention (see ``sw_ai_odd``), the training *logic*
lives here and the MLflow orchestration + CLI lives in ``scripts/train.py``.
Per-epoch metrics are surfaced through an ``on_epoch`` callback so this module
never imports MLflow.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from loguru import logger

from src.uavid.dataset import IdentityIndex, sample_episode, preload_images
from src.uavid.model import (
    build_encoder,
    BACKBONE_NORM,
    build_prototypes,
    cosine_logits,
    euclidean_logits,
)


def run_episode(model, index, tfm, n_way, k_shot, q_query, device,
                metric="euclidean", normalize=True, support_index=None,
                support_tfm=None, hard_negatives=None,
                hard_negative_p=0.5) -> tuple[torch.Tensor, torch.Tensor]:
    """Run one episode and return ``(loss, accuracy)``."""
    s_x, s_y, q_x, q_y = sample_episode(index, tfm, n_way, k_shot, q_query,
                                        support_index=support_index,
                                        support_tfm=support_tfm,
                                        hard_negatives=hard_negatives,
                                        hard_negative_p=hard_negative_p)
    s_x, s_y = s_x.to(device), s_y.to(device)
    q_x, q_y = q_x.to(device), q_y.to(device)
    actual_n_way = int(s_y.max().item()) + 1

    emb = model(torch.cat([s_x, q_x], dim=0))
    s_emb, q_emb = emb[: len(s_x)], emb[len(s_x):]
    protos = build_prototypes(s_emb, s_y, actual_n_way, normalize=normalize)
    logits = (euclidean_logits(q_emb, protos) if metric == "euclidean"
              else cosine_logits(q_emb, protos))
    loss = F.cross_entropy(logits, q_y)
    acc = (logits.argmax(dim=1) == q_y).float().mean()
    return loss, acc


@torch.no_grad()
def validate(model, index, tfm, n_way, k_shot, q_query, episodes, device,
             metric="euclidean", normalize=True, support_index=None,
             support_tfm=None) -> float:
    """Return the mean episodic accuracy over ``episodes`` validation episodes."""
    model.eval()
    accs = []
    for _ in range(episodes):
        _, acc = run_episode(model, index, tfm, n_way, k_shot, q_query, device,
                             metric, normalize, support_index=support_index,
                             support_tfm=support_tfm)
        accs.append(acc.item())
    model.train()
    return sum(accs) / len(accs)


def train_protonet(
    *,
    train_index: IdentityIndex,
    val_index: IdentityIndex,
    train_tfm,
    val_tfm,
    support_index: IdentityIndex | None = None,
    support_tfm=None,
    out_dir: Path,
    epochs: int = 30,
    episodes_per_epoch: int = 100,
    val_episodes: int = 100,
    n_way: int = 5,
    test_n_way: int = 5,
    k_shot: int = 5,
    k_shot_range: list[int] | None = None,
    q_query: int = 5,
    lr: float = 1e-3,
    backbone_lr: float = 1e-4,
    embed_dim: int = 128,
    image_size: int = 224,
    metric: str = "euclidean",
    normalize: bool = True,
    degrade_p: float = 0.5,
    support_split: str | None = None,
    freeze_backbone_epochs: int = 2,
    backbone: str = "mobilenetv3",
    grad_accum: int = 1,
    preload: bool = True,
    hard_negatives: list[str] | None = None,
    hard_negative_p: float = 0.5,
    resume: str | None = None,
    device: str = "cpu",
    on_epoch: Callable[[int, dict[str, float]], None] | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Train the ProtoNet encoder episodically and save best/last checkpoints.

    Args:
        train_index / val_index: Identity indices for the train / val splits.
        train_tfm / val_tfm: Transforms for train / val images.
        support_index / support_tfm: Optional mixed-domain support split.
        out_dir: Directory where ``best.pth`` / ``last.pth`` are written.
        epochs ... freeze_backbone_epochs: Episodic hyperparameters.
        device: Torch device string.
        on_epoch: Optional callback ``(epoch, metrics)`` invoked each epoch
            (used by the CLI to log to MLflow without coupling this module to it).

    Returns:
        Tuple ``(best_val_acc, history)`` where ``history`` is a list of
        per-epoch metric dicts.
    """
    model = build_encoder(backbone, embed_dim=embed_dim, pretrained=(resume is None),
                          l2_normalize=normalize).to(device)
    if resume:
        import torch as _torch
        ckpt = _torch.load(resume, map_location=device, weights_only=True)
        model.load_state_dict(ckpt["model"])
        logger.info(f"Resumed from {resume} | val_acc={ckpt.get('val_acc', '?'):.4f} epoch={ckpt.get('epoch', '?')}")

    if preload:
        indices = [train_index, val_index]
        if support_index is not None:
            indices.append(support_index)
        preload_images(*indices)
    optim = torch.optim.AdamW([
        {"params": model.features.parameters(), "lr": backbone_lr},
        {"params": model.head.parameters(), "lr": lr},
    ], weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(
        optim, T_max=epochs * episodes_per_epoch)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_acc = 0.0
    history: list[dict[str, Any]] = []

    for epoch in range(1, epochs + 1):
        frozen = epoch <= freeze_backbone_epochs
        for p in model.features.parameters():
            p.requires_grad = not frozen

        t0, losses, accs = time.time(), [], []
        optim.zero_grad()
        for ep_idx in range(episodes_per_epoch):
            k = random.choice(k_shot_range) if k_shot_range else k_shot
            loss, acc = run_episode(model, train_index, train_tfm, n_way, k,
                                    q_query, device, metric, normalize,
                                    support_index=support_index,
                                    support_tfm=support_tfm,
                                    hard_negatives=hard_negatives,
                                    hard_negative_p=hard_negative_p)
            (loss / grad_accum).backward()
            if (ep_idx + 1) % grad_accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optim.step()
                sched.step()
                optim.zero_grad()
            losses.append(loss.item())
            accs.append(acc.item())

        val_acc = validate(model, val_index, val_tfm, test_n_way, k_shot,
                           q_query, val_episodes, device, metric, normalize,
                           support_index=support_index, support_tfm=support_tfm)
        epoch_loss = sum(losses) / len(losses)
        train_acc = sum(accs) / len(accs)
        dt = time.time() - t0
        logger.info(
            f"epoch {epoch:03d} | loss {epoch_loss:.4f} | train acc {train_acc:.3f} "
            f"| val acc {val_acc:.3f} | {dt:.1f}s{' | backbone frozen' if frozen else ''}"
        )

        metrics = {
            "loss": epoch_loss,
            "train_acc": train_acc,
            "val_acc": val_acc,
            "epoch_time_s": dt,
            "lr": optim.param_groups[-1]["lr"],
        }
        history.append({"epoch": epoch, **metrics})

        ckpt = {"model": model.state_dict(), "embed_dim": embed_dim,
                "image_size": image_size, "epoch": epoch, "val_acc": val_acc,
                "metric": metric, "l2_normalize": normalize,
                "support_split": support_split, "backbone": backbone}
        torch.save(ckpt, out_dir / "last.pth")
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(ckpt, out_dir / "best.pth")
            logger.info(f"  -> new best ({best_acc:.3f}) saved to {out_dir / 'best.pth'}")
            metrics["best_val_acc"] = best_acc

        if on_epoch is not None:
            on_epoch(epoch, metrics)

    logger.info(f"Done. Best val acc: {best_acc:.3f}")
    return best_acc, history
