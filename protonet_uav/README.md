# ProtoNet UAV — local few-shot identification prototype

Minimal local prototype of the TFG pipeline: MobileNetV3-Small -> 576 -> Linear ->
LayerNorm -> 128-dim L2-normalized embeddings, prototypical episodic training,
enrollment to `gallery.npy`, identification by cosine similarity. No Embention
infrastructure required — runs on a single PC (CUDA or CPU).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # or conda
pip install -r requirements.txt
```

## Data layout

One folder per **physical airframe / distinct model**, split by identity
(an identity must never appear in both splits):

```
uav_dataset/
  train/
    mq1_predator/      operational renders only: small UAV, far away, sky bg
    tb2_bayraktar/
    mq9_reaper/
    neg_bird_eagle/    train-only negative: no val, no enrollment
  val/
    global_hawk/       same operational style, but identities never seen in train
    hermes_450/
  enrollment/
    mq1_predator/      close-up sharp renders for enroll.py only
    tb2_bayraktar/
    mq9_reaper/
    global_hawk/
    hermes_450/
```

Guideline: >=10 train identities and >=5 val identities, >=10 images each, to
see meaningful learning. Crops of the object (detector-style) work best, but
full photos are fine for a first smoke test.

The training code reads only `train/` and `val/`. The `enrollment/` folder may
contain all identities, including train identities, because it simulates client
reference photos and is used by `src.enroll`, not by metric training. Reported
generalization must come from `val/` identities that do not appear in `train/`.

Folders whose names start with `neg_` are hard negatives. They are rendered only
into `train/` as operational images. They are never placed in `val/` and never
rendered into `enrollment/`.

## Test sequence

**0. Zero-shot sanity check (no training).** The ImageNet-pretrained encoder
already produces usable embeddings:

```bash
python -m src.enroll --images data/val/identity_X_subset5 --out gallery.npy
python -m src.identify --gallery gallery.npy --images data/val/identity_X_rest
python -m src.identify --gallery gallery.npy --images data/val/identity_Y   # impostor
```

If genuine scores already sit above impostor scores, the metric-learning
premise holds before you train anything.

**1. Train:**

```bash
python -m src.train --data_root ./data --epochs 30 \
    --n_way 5 --k_shot 5 --q_query 5 --degrade_p 0.5
```

`--degrade_p 0.5` randomly degrades training images to the 46–143 px
operational envelope (downscale + blur + upscale). Set `0` to disable —
comparing both runs is your first Q3 data point.

**2. Open-set evaluation (the number that matters):**

```bash
python -m src.eval_openset --checkpoint checkpoints/best.pth \
    --data_root ./data --k_shot 5 --agg mean
python -m src.eval_openset --checkpoint checkpoints/best.pth \
    --data_root ./data --k_shot 5 --agg attention   # Approach 2
```

Reports ROC-AUC (target vs impostor) and TPR at FPR 1/5/10%. Run with
`--checkpoint` omitted first to get the zero-shot baseline; training should
beat it clearly. Sweep `--k_shot 1 3 5 10` for an early Q1 curve.

**3. Manual enrollment demo (what the client-side app will do):**

```bash
python -m src.enroll --checkpoint checkpoints/best.pth \
    --images photos_of_target/ --out gallery.npy
python -m src.identify --checkpoint checkpoints/best.pth \
    --gallery gallery.npy --images query_crops/ --agg attention --threshold 0.6
```

## Distance metric (Snell et al. 2017)

The default metric is **squared Euclidean** (`--metric euclidean`), not cosine.
Squared Euclidean is a Bregman divergence, which is the property that makes the
class mean the optimal prototype. Cosine is kept as `--metric cosine` for the
ablation.

Subtlety specific to this project: the encoder L2-normalizes embeddings by
default (required by the gallery/threshold/privacy design). On the unit sphere,
squared Euclidean and cosine are monotonically equivalent, so the Bregman
justification is satisfied trivially. To reproduce the paper's *unnormalized*
Euclidean setting, train with `--no_l2norm` and compare — a legitimate ablation.

## Paper-aligned training options

- `--metric euclidean|cosine` — distance metric (default euclidean).
- `--no_l2norm` — disable final L2-normalization (unnormalized-Euclidean ablation).
- `--n_way` / `--test_n_way` — Snell et al. found training with **higher way**
  than test helps; set `--n_way` as high as your identity count allows and
  `--test_n_way` lower (e.g. train 15-way, test 5-way).
- `--k_shot_range 1 3 5 10` — sample shot per-episode to train a **shot-robust**
  model. The paper recommends matching train/test shot, but your test-time shot
  is the client's unknown N, so a single shot-robust model is the deployment-
  correct choice. Documented as a deliberate departure.
- `--paper_schedule` — reproduce their recipe: Adam, lr 1e-3, halved every
  2000 episodes, no weight decay, single LR for the whole network.

Note: the default (AdamW + cosine schedule + lower backbone LR + mild weight
decay) is tuned for fine-tuning a pretrained ImageNet backbone on few
identities — a different regime from the paper's from-scratch tiny conv nets.
Keep some weight decay: "BN is enough regularization" held at Omniglot scale,
not with a 2.5M-param backbone on tens of identities.

## Interpreting results

- **val acc (training log):** episodic 5-way accuracy on unseen identities.
  Chance = 0.20. Zero-shot ImageNet typically lands well above chance;
  training should push it substantially higher.
- **ROC-AUC (eval_openset):** 0.5 = useless, >0.9 = the approach works on
  your data. This is the go/no-go signal for the concept.
- **threshold:** take the threshold printed at your preferred FPR as the
  starting `--threshold` for identify.

## Files

- `src/model.py`     encoder (matches the TIDL split-export architecture) + prototype utils
- `src/dataset.py`   identity index, episodic sampler, operational degradation transform
- `src/train.py`     episodic training with identity-disjoint validation
- `src/enroll.py`    N images -> gallery.npy (Option A client-side artifact)
- `src/identify.py`  queries vs gallery, mean or attention aggregation
- `src/eval_openset.py`  ROC-AUC target-vs-impostor on held-out identities

## Notes

- Checkpoints store `embed_dim`/`image_size`; enroll/identify read them.
- The forward pass equals backbone_tidl.onnx + projection_head.onnx
  concatenated, so a trained `best.pth` exports through the existing split path.
- Training on an RTX 3090: a 30-epoch run at defaults is well under an hour.
