"""Training loops for the OOD pipeline (pure logic, no MLflow)."""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from loguru import logger
from pytorch_ood.loss import EnergyRegularizedLoss
from torch.utils.data import DataLoader


def _train_epoch(
    model: nn.Module,
    loader: DataLoader,
    crit: nn.CrossEntropyLoss,
    opt: torch.optim.Optimizer,
    scaler: torch.amp.GradScaler,
    *,
    device: str,
) -> tuple[float, float]:
    """Run one training epoch; return ``(train_loss, train_acc)``."""
    model.train()
    tr_loss, tr_correct, n = 0.0, 0, 0
    for x, y in loader:
        x = x.to(device, non_blocking=True)
        y = y.to(device, non_blocking=True)
        opt.zero_grad(set_to_none=True)
        with torch.amp.autocast(device_type="cuda", enabled=(device == "cuda")):
            logits = model(x)
            loss = crit(logits, y)
        scaler.scale(loss).backward()
        scaler.step(opt)
        scaler.update()
        tr_loss += loss.item() * x.size(0)
        tr_correct += (logits.argmax(1) == y).sum().item()
        n += x.size(0)
    return tr_loss / max(n, 1), tr_correct / max(n, 1)


def _val_epoch(
    model: nn.Module,
    loader: DataLoader,
    *,
    device: str,
) -> tuple[float, float]:
    """Run one validation epoch; return ``(val_loss, val_acc)``."""
    model.eval()
    v_loss, v_correct, v_n = 0.0, 0, 0
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            y = y.to(device)
            logits = model(x)
            v_loss += F.cross_entropy(logits, y, reduction="sum").item()
            v_correct += (logits.argmax(1) == y).sum().item()
            v_n += y.numel()
    return v_loss / max(v_n, 1), v_correct / max(v_n, 1)


def _energy_stats(
    model: nn.Module,
    id_loader: DataLoader,
    ood_loader: DataLoader,
    *,
    device: str,
) -> tuple[float, float]:
    """Compute mean free energy for ID and OOD validation samples.

    Free energy is defined as ``E(x) = log(sum_c exp(f_c(x)))`` where
    ``f_c`` are the class logits.  Higher energy → more in-distribution.

    Args:
        model: Model in eval mode.
        id_loader: DataLoader yielding in-distribution ``(x, y)`` batches.
        ood_loader: DataLoader yielding OOD ``(x, _)`` batches.
        device: PyTorch device string.

    Returns:
        A 2-tuple ``(id_mean, ood_mean)`` of mean energy scores.
    """
    model.eval()
    id_scores: list[float] = []
    ood_scores: list[float] = []
    with torch.no_grad():
        for x, _ in id_loader:
            logits = model(x.to(device))
            id_scores.extend(torch.logsumexp(logits, dim=1).cpu().tolist())
        for x, _ in ood_loader:
            logits = model(x.to(device))
            ood_scores.extend(torch.logsumexp(logits, dim=1).cpu().tolist())
    return float(np.mean(id_scores)), float(np.mean(ood_scores))


def train_classifier(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    *,
    epochs: int = 12,
    lr: float = 3e-4,
    weight_decay: float = 1e-4,
    class_weights: list[float] | None = None,
    label: str = "model",
    device: str = "cpu",
    checkpoint_path: Path | str | None = None,
    early_stopping_patience: int = 0,
) -> tuple[nn.Module, float, dict]:
    """Fine-tune with AdamW + cosine LR; return the best-accuracy checkpoint.

    Checkpoint selection and early stopping intentionally use different
    validation metrics:
    - Best checkpoint/model state is selected by highest ``val_acc``.
    - Early stopping is triggered by lack of ``val_loss`` improvement.
    Therefore, the returned/saved model may come from an earlier epoch than
    the epoch where training stopped.

    Args:
        model: The ``nn.Module`` to train (only requires_grad params are updated).
        train_loader: DataLoader yielding ``(x, y)`` batches for training.
        val_loader: DataLoader yielding ``(x, y)`` batches for validation.
        epochs: Number of training epochs.
        lr: Initial AdamW learning rate.
        weight_decay: AdamW weight decay.
        class_weights: Optional per-class loss weights for ``CrossEntropyLoss``.
        label: Human-readable label used in progress output.
        device: PyTorch device string (e.g. ``"cpu"`` or ``"cuda"``).
        checkpoint_path: If given, the best-accuracy state dict is written
            here after every ``val_acc`` improvement so training can be
            resumed if interrupted.
        early_stopping_patience: Stop training when val_loss has not improved
            for this many consecutive epochs.  ``0`` (default) disables early
            stopping.

    Returns:
        A 3-tuple ``(best_model, best_val_acc, history)`` where *history* is a
        dict of lists keyed by ``"train_loss"``, ``"val_loss"``,
        ``"train_acc"``, and ``"val_acc"``.  ``best_model`` corresponds to
        the best observed ``val_acc`` (not necessarily the final epoch before
        early stopping).
    """
    model = model.to(device)
    opt = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr,
        weight_decay=weight_decay,
    )
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    scaler = torch.amp.GradScaler(enabled=(device == "cuda"))

    w = None
    if class_weights is not None:
        w = torch.tensor(class_weights, dtype=torch.float32, device=device)
    crit = nn.CrossEntropyLoss(weight=w)

    history: dict[str, list[float]] = {
        "train_loss": [],
        "val_loss": [],
        "train_acc": [],
        "val_acc": [],
    }
    best_val_acc, best_val_loss, best_state = -1.0, float("inf"), None
    epochs_without_improvement = 0

    for epoch in range(1, epochs + 1):
        train_loss, train_acc = _train_epoch(
            model, train_loader, crit, opt, scaler, device=device,
        )
        sched.step()
        val_loss, val_acc = _val_epoch(model, val_loader, device=device)

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["train_acc"].append(train_acc)
        history["val_acc"].append(val_acc)
        is_best_acc = val_acc > best_val_acc
        val_loss_improved = val_loss < best_val_loss
        logger.info(
            "[{}] epoch {:02d}  train_loss={:.4f}  val_loss={:.4f}  "
            "train_acc={:.4f}  val_acc={:.4f}{}",
            label, epoch, train_loss, val_loss, train_acc, val_acc,
            "  ✓ saved" if is_best_acc else "",
        )
        if is_best_acc:
            best_val_acc = val_acc
            best_state = {
                k: v.detach().cpu().clone() for k, v in model.state_dict().items()
            }
            if checkpoint_path is not None:
                torch.save(best_state, checkpoint_path)
                logger.debug("[{}] checkpoint saved → {}", label, checkpoint_path)

        if val_loss_improved:
            best_val_loss = val_loss
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if early_stopping_patience > 0 and epochs_without_improvement >= early_stopping_patience:
                logger.info(
                    "[{}] early stopping triggered after {} epochs without val_loss improvement.",
                    label, epochs_without_improvement,
                )
                break

    model.load_state_dict(best_state)
    logger.info("[{}] best val loss = {:.4f}  (val_acc = {:.4f})", label, best_val_loss, best_val_acc)
    return model, best_val_acc, history


def energy_finetune(
    base_clf: nn.Module,
    train_loader: DataLoader,
    ood_loader: DataLoader,
    val_loader: DataLoader,
    ood_val_loader: DataLoader,
    *,
    n_epochs: int = 6,
    lr: float = 1e-4,
    weight_decay: float = 1e-4,
    energy_alpha: float = 0.1,
    energy_margin_in: float = -25.0,
    energy_margin_out: float = -7.0,
    min_val_acc: float = 0.97,
    label: str = "resnet18",
    device: str = "cpu",
    checkpoint_path: Path | str | None = None,
) -> tuple[nn.Module, dict]:
    """Energy fine-tuning with outlier exposure.

    Warm-starts from *base_clf*; each step mixes one ID batch with one OOD
    batch (label = -1 by ``pytorch_ood`` convention).  A cosine LR schedule
    decays the learning rate over the fine-tuning epochs.  The saved checkpoint
    is the one with the largest ID/OOD energy gap among epochs where
    ``val_acc >= min_val_acc``, preventing catastrophic forgetting.

    Args:
        base_clf: Pre-trained classifier to warm-start from (deep-copied).
        train_loader: ID DataLoader yielding ``(x, y)`` batches.
        ood_loader: OOD train DataLoader yielding ``(x, _)`` batches.
        val_loader: ID validation DataLoader yielding ``(x, y)`` batches.
        ood_val_loader: OOD validation DataLoader yielding ``(x, _)`` batches,
            used to track the ID/OOD energy score gap during fine-tuning.
        n_epochs: Number of energy fine-tuning epochs.
        lr: Initial AdamW learning rate (decayed via cosine schedule).
        weight_decay: AdamW weight decay.
        energy_alpha: Weight of the energy regularisation term.
        energy_margin_in: Energy margin target for in-distribution samples.
        energy_margin_out: Energy margin target for OOD samples.
        min_val_acc: Minimum ID validation accuracy required for a checkpoint
            to be considered.  Guards against catastrophic forgetting.
        label: Human-readable label used in progress output.
        device: PyTorch device string.
        checkpoint_path: If given, the best state dict is written here after
            every improvement so training can be resumed if interrupted.

    Returns:
        A 2-tuple ``(finetuned_model, history)`` where *history* has
        ``"energy_loss"``, ``"val_acc"``, ``"energy_id_mean"``, and
        ``"energy_ood_mean"`` lists with one value per epoch.
    """
    clf_e = copy.deepcopy(base_clf).to(device)
    opt = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, clf_e.parameters()),
        lr=lr,
        weight_decay=weight_decay,
    )
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=n_epochs)
    scaler = torch.amp.GradScaler(enabled=(device == "cuda"))
    e_loss_fn = EnergyRegularizedLoss(
        alpha=energy_alpha,
        margin_in=energy_margin_in,
        margin_out=energy_margin_out,
    )

    history: dict[str, list[float]] = {
        "energy_loss": [], "val_acc": [], "energy_id_mean": [], "energy_ood_mean": [],
    }
    best_gap, best_state = float("-inf"), None  # gap = id - ood; larger = better separation

    for ep in range(1, n_epochs + 1):
        clf_e.train()
        losses: list[float] = []
        for (x_id, y_id), (x_oo, _) in zip(train_loader, ood_loader, strict=False):
            x = torch.cat([x_id, x_oo]).to(device, non_blocking=True)
            y = torch.cat([
                y_id, -torch.ones(x_oo.size(0), dtype=torch.long)
            ]).to(device)
            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type="cuda", enabled=(device == "cuda")):
                logits = clf_e(x)
                loss = e_loss_fn(logits, y)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            losses.append(loss.item())
        sched.step()
        epoch_loss = float(np.mean(losses))
        _, val_acc = _val_epoch(clf_e, val_loader, device=device)
        energy_id_mean, energy_ood_mean = _energy_stats(
            clf_e, val_loader, ood_val_loader, device=device,
        )

        history["energy_loss"].append(epoch_loss)
        history["val_acc"].append(val_acc)
        history["energy_id_mean"].append(energy_id_mean)
        history["energy_ood_mean"].append(energy_ood_mean)
        gap = energy_id_mean - energy_ood_mean
        is_best = val_acc >= min_val_acc and gap > best_gap
        logger.info(
            "[{}] energy-FT epoch {}/{}  energy_loss={:.3f}  val_acc={:.4f}"
            "  energy_id={:.3f}  energy_ood={:.3f}  gap={:.3f}{}",
            label, ep, n_epochs, epoch_loss, val_acc,
            energy_id_mean, energy_ood_mean, gap,
            "  ✓ saved" if is_best else "",
        )
        if is_best:
            best_gap = gap
            best_state = {
                k: v.detach().cpu().clone() for k, v in clf_e.state_dict().items()
            }
            if checkpoint_path is not None:
                torch.save(best_state, checkpoint_path)
                logger.debug("[{}] energy checkpoint saved → {}", label, checkpoint_path)

    if best_state is None:
        logger.warning(
            "[{}] no epoch met min_val_acc={:.2f} — returning last epoch weights.",
            label, min_val_acc,
        )
        best_state = {k: v.detach().cpu().clone() for k, v in clf_e.state_dict().items()}
    clf_e.load_state_dict(best_state)
    logger.info("[{}] best energy gap = {:.3f}", label, best_gap)
    return clf_e, history
