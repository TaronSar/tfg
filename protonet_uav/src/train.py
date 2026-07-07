"""Episodic prototypical training.

Usage:
    python -m src.train --data_root ./data --epochs 30 \
        --n_way 5 --k_shot 5 --q_query 5 --degrade_p 0.5
    python -m src.train --data_root ./data --support_split enrollment \
        --n_way 15 --test_n_way 5 --k_shot_range 1 3 5 --degrade_p 0.0

Data layout: data_root/train/<identity>/*.jpg and data_root/val/<identity>/*.jpg
Optional mixed-domain layout: data_root/enrollment/<identity>/*.jpg for support images.
Validation identities must be disjoint from training identities.
"""

import argparse
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from src.dataset import IdentityIndex, build_transform, sample_episode
from src.model import (ProtoNetEncoder, build_prototypes, euclidean_logits,
                       cosine_logits, build_encoder, BACKBONE_NORM)


def run_episode(model, index, tfm, n_way, k_shot, q_query, device,
                metric="euclidean", normalize=True, support_index=None,
                support_tfm=None):
    s_x, s_y, q_x, q_y = sample_episode(index, tfm, n_way, k_shot, q_query,
                                        support_index=support_index,
                                        support_tfm=support_tfm)
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
             support_tfm=None):
    model.eval()
    accs = []
    for _ in range(episodes):
        _, acc = run_episode(model, index, tfm, n_way, k_shot, q_query, device,
                     metric, normalize, support_index=support_index,
                     support_tfm=support_tfm)
        accs.append(acc.item())
    model.train()
    return sum(accs) / len(accs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_root", required=True)
    ap.add_argument("--out", default="checkpoints")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--episodes_per_epoch", type=int, default=100)
    ap.add_argument("--val_episodes", type=int, default=100)
    ap.add_argument("--n_way", type=int, default=5,
                    help="Train-time way. Snell et al.: train with higher way than test. "
                         "Set as high as your identity count allows.")
    ap.add_argument("--test_n_way", type=int, default=5,
                    help="Validation/test way (typically <= n_way).")
    ap.add_argument("--k_shot", type=int, default=5)
    ap.add_argument("--k_shot_range", type=int, nargs="+", default=None,
                    help="If set (e.g. 1 3 5 10), sample shot per-episode from this set "
                         "to train a SHOT-ROBUST model for the unknown client N. "
                         "Departs from the paper's fixed-shot recipe by design.")
    ap.add_argument("--q_query", type=int, default=5)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--backbone_lr", type=float, default=1e-4,
                    help="Lower LR for the pretrained backbone")
    ap.add_argument("--image_size", type=int, default=224)
    ap.add_argument("--embed_dim", type=int, default=128)
    ap.add_argument("--backbone",
                    choices=["mobilenetv3", "dinov2_vits14", "dinov2_vitb14",
                             "clip_vit_b32"],
                    default="mobilenetv3",
                    help="Feature backbone. dinov2_*/clip_* download weights on "
                         "first use and require no TIDL/ONNX constraints.")
    ap.add_argument("--metric", choices=["euclidean", "cosine"], default="euclidean",
                    help="euclidean = Bregman-justified ProtoNet (Snell et al.).")
    ap.add_argument("--no_l2norm", action="store_true",
                    help="Disable final L2-normalization (paper-faithful unnormalized "
                         "Euclidean ablation). Default keeps normalization for deployment.")
    ap.add_argument("--paper_schedule", action="store_true",
                    help="Reproduce Snell et al.: Adam lr 1e-3, halved every 2000 episodes, "
                         "no weight decay, single LR for whole net.")
    ap.add_argument("--degrade_p", type=float, default=0.5,
                    help="Prob. of degrading a training image to the 46-143px envelope. 0 disables.")
    ap.add_argument("--support_split", default=None,
                    help="Optional split for episode support images, e.g. enrollment. "
                         "Queries still come from train/val.")
    ap.add_argument("--freeze_backbone_epochs", type=int, default=2,
                    help="Train only the projection head for the first E epochs")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    normalize = not args.no_l2norm

    train_index = IdentityIndex(Path(args.data_root) / "train")
    val_index = IdentityIndex(Path(args.data_root) / "val")
    support_index = IdentityIndex(Path(args.data_root) / args.support_split) if args.support_split else None
    overlap = set(train_index.names) & set(val_index.names)
    if overlap:
        print(f"WARNING: {len(overlap)} identities appear in BOTH splits -> data leakage: {sorted(overlap)[:5]}")
    print(f"Train: {train_index.stats()}")
    print(f"Val:   {val_index.stats()}")
    if support_index:
        train_common = set(train_index.names) & set(support_index.names)
        val_common = set(val_index.names) & set(support_index.names)
        print(f"Support ({args.support_split}): {support_index.stats()}")
        print(f"Mixed-domain train identities: {len(train_common)} shared train/support")
        print(f"Mixed-domain val identities:   {len(val_common)} shared val/support")
        if not train_common or not val_common:
            raise RuntimeError("support_split must overlap both train and val identities")

    norm_mean, norm_std = BACKBONE_NORM[args.backbone]
    train_tfm   = build_transform(args.image_size, train=True,
                                  degrade_p=args.degrade_p,
                                  mean=norm_mean, std=norm_std)
    val_tfm     = build_transform(args.image_size, train=False,
                                  mean=norm_mean, std=norm_std)
    support_tfm = (build_transform(args.image_size, train=False,
                                   mean=norm_mean, std=norm_std)
                   if support_index else None)

    model = build_encoder(args.backbone, embed_dim=args.embed_dim, pretrained=True,
                          l2_normalize=normalize).to(device)

    if args.paper_schedule:
        # Snell et al.: Adam, lr 1e-3, halve every 2000 episodes, no weight decay
        optim = torch.optim.Adam(model.parameters(), lr=args.lr)
        sched = torch.optim.lr_scheduler.StepLR(optim, step_size=2000, gamma=0.5)
        print("Using paper schedule: Adam lr=1e-3, x0.5 every 2000 episodes, no WD")
    else:
        optim = torch.optim.AdamW([
            {"params": model.features.parameters(), "lr": args.backbone_lr},
            {"params": model.head.parameters(), "lr": args.lr},
        ], weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(
            optim, T_max=args.epochs * args.episodes_per_epoch)

    print(f"Metric: {args.metric} | L2-normalize: {normalize} | "
          f"backbone: {args.backbone} | "
          f"train-way: {args.n_way} -> test-way: {args.test_n_way}")
    if args.k_shot_range:
        print(f"Shot-robust training: K sampled per-episode from {args.k_shot_range}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_acc = 0.0

    for epoch in range(1, args.epochs + 1):
        frozen = epoch <= args.freeze_backbone_epochs
        for p in model.features.parameters():
            p.requires_grad = not frozen

        t0, losses, accs = time.time(), [], []
        for _ in range(args.episodes_per_epoch):
            k = (random.choice(args.k_shot_range) if args.k_shot_range
                 else args.k_shot)
            loss, acc = run_episode(model, train_index, train_tfm,
                                    args.n_way, k, args.q_query, device,
                                    args.metric, normalize,
                                    support_index=support_index,
                                    support_tfm=support_tfm)
            optim.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optim.step()
            sched.step()
            losses.append(loss.item())
            accs.append(acc.item())

        val_acc = validate(model, val_index, val_tfm, args.test_n_way, args.k_shot,
                           args.q_query, args.val_episodes, device,
                           args.metric, normalize,
                           support_index=support_index,
                           support_tfm=support_tfm)
        print(f"epoch {epoch:03d} | loss {sum(losses)/len(losses):.4f} | "
              f"train acc {sum(accs)/len(accs):.3f} | val acc {val_acc:.3f} | "
              f"{time.time()-t0:.1f}s{' | backbone frozen' if frozen else ''}")

        torch.save({"model": model.state_dict(), "embed_dim": args.embed_dim,
                    "image_size": args.image_size, "epoch": epoch,
                    "val_acc": val_acc, "metric": args.metric,
                    "l2_normalize": normalize, "support_split": args.support_split,
                    "backbone": args.backbone}, out_dir / "last.pth")
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save({"model": model.state_dict(), "embed_dim": args.embed_dim,
                        "image_size": args.image_size, "epoch": epoch,
                        "val_acc": val_acc, "metric": args.metric,
                        "l2_normalize": normalize, "support_split": args.support_split,
                        "backbone": args.backbone}, out_dir / "best.pth")
            print(f"  -> new best ({best_acc:.3f}) saved to {out_dir/'best.pth'}")

    print(f"Done. Best val acc: {best_acc:.3f}")


if __name__ == "__main__":
    main()
