# sw_autoengagement — Pipeline Reference

This document explains the complete structure of the few-shot UAV identification
pipeline: what every file does, how data flows through the stages, and how DVC,
the scripts, and the `src/` library relate to each other.

---

## 1. The big picture

The system answers the question:
> "Is this UAV in the camera's field of view the specific airframe the client
> enrolled?"

It does this without ever receiving the client's images on the server. The
client supplies a few reference photos at deployment time ("enrollment"), the
sensor takes live crops at runtime ("query"), and the model computes a distance
in embedding space.

```
           ┌─────────────────────────────────────────────────────┐
           │                    Training time                    │
           │                                                     │
  GLB      │  batch_render.py ──► NAS renders dataset            │
  models ──►     (Blender)                                       │
           │                  │                                  │
           │  crop_from_yolox.py ──► NAS crops dataset           │
           │     (YOLOX ONNX)    │                               │
           │                     ▼                               │
           │  filter_small_crops.py ──► excluded_crops.json      │
           │                                                     │
           │  train.py ──────────────► models/00_train/best.pth  │
           │                                                     │
           │  evaluate.py ───────────► data/eval/results.csv     │
           │                                                     │
           │  export_onnx.py ────────► backbone_fp32.onnx        │
           │                          backbone_tidl.onnx         │
           │                          projection_head.onnx       │
           └─────────────────────────────────────────────────────┘

           ┌─────────────────────────────────────────────────────┐
           │                   Deployment time                   │
           │                     (client-side)                   │
           │                                                     │
  Client ──► enroll.py ──────────► gallery.npy (prototype)       │
  photos                                                         │
           │  live crops                                         │
  Sensor ──► deploy_verify.py ──► match/no-match decision        │
           └─────────────────────────────────────────────────────┘
```

---

## 2. Repository layout

```
sw_autoengagement/items/
│
├── dvc.yaml                  ← Pipeline recipe (THIS is the master document)
├── configs/
│   ├── dvc_config.yaml       ← Iteration-invariant constants (NAS paths, etc.)
│   └── setup.yaml            ← Machine-specific settings (MLflow URI)
│
├── scripts/                  ← CLI entry-points (one per pipeline stage)
│   ├── batch_render.py       ← Stage 00: render GLB models with Blender
│   ├── render_uav.py         ← Called by batch_render inside Blender process
│   ├── crop_from_yolox.py    ← Stage 01: YOLOX crop + enrollment copy
│   ├── filter_small_crops.py ← Stage 02: build exclusion list
│   ├── dataset_manifest.py   ← Utility: count images, write stamp JSON
│   ├── train.py              ← Stage 03: episodic ProtoNet training
│   ├── evaluate.py           ← Stage 04: open-set k-shot evaluation
│   ├── export_onnx.py        ← Stage 05: export ONNX artefacts
│   ├── enroll.py             ← Runtime: build client gallery
│   ├── calibrate_threshold.py← Runtime: find operating threshold
│   └── deploy_verify.py      ← Runtime: live identification
│
├── src/uavid/                ← Library (pure logic, no CLI/MLflow)
│   ├── model/
│   │   ├── encoder.py        ← ProtoNetEncoder (MobileNetV3-Small backbone)
│   │   ├── prototypes.py     ← Prototype construction (mean / attention)
│   │   └── metrics.py        ← Distance metrics (Euclidean, cosine)
│   ├── dataset/
│   │   └── episodic.py       ← IdentityIndex + episodic sampler
│   ├── train/
│   │   └── trainer.py        ← train_protonet() — pure training loop
│   ├── eval/
│   │   └── openset.py        ← evaluate_openset() — ROC-AUC + TPR@FPR
│   ├── export/
│   │   └── onnx.py           ← export_encoder() — split ONNX export
│   ├── preprocessing/
│   │   ├── filter_crops.py   ← build_exclusion() / load_excluded()
│   │   └── manifest.py       ← write_manifest() — dataset stamp JSON
│   └── common/
│       ├── transforms.py     ← build_transform() + DegradeToOperational
│       ├── config_loader.py  ← load_*_config() helpers
│       └── constants.py      ← IMG_EXTS, IMAGENET_MEAN/STD
│
├── data/
│   ├── manifests/            ← DVC-tracked stage stamps (small JSON files)
│   ├── annotations/
│   │   └── excluded_crops.json ← DVC-tracked output of 02_filter_crops
│   └── eval/
│       ├── openset_results.csv ← DVC-tracked output of 04_eval
│       └── openset_summary.json
│
└── models/
    ├── 00_train/
    │   ├── best.pth          ← DVC-tracked output of 03_train
    │   └── last.pth
    └── 02_export/
        ├── backbone_fp32.onnx
        ├── backbone_tidl.onnx
        └── projection_head.onnx
```

---

## 3. DVC: what it is and what it tracks

DVC is a version-control layer for data and models that sits on top of Git.

```
Git tracks:    source code, dvc.yaml, dvc_config.yaml, small JSON outputs
DVC tracks:    binary/large files (best.pth, ONNX files) → stored on NAS
NAS stores:    image datasets (never `dvc add`-ed), model checkpoints, ONNX
```

### The key DVC concepts used here

| Concept | What it means |
|---------|---------------|
| `stage` | One step of the pipeline (cmd + deps + params + outs) |
| `deps`  | Files DVC hashes to detect if the stage needs re-running |
| `params`| Specific YAML keys DVC tracks for change detection |
| `outs`  | Files DVC stores / tracks as the stage's output |
| `frozen: true` | Stage is locked — DVC will NOT auto-rerun it even if a dep changes. You must run it deliberately with `dvc repro --force <stage>` |
| `cache: false` | Output file is tracked (its hash goes into dvc.lock) but NOT pushed to DVC storage — it stays in Git as a regular text file |

### Why all stages are frozen

Each stage represents a deliberate, expensive operation (hours of Blender
rendering, a GPU training run). Freezing prevents DVC from re-executing them
automatically when something unrelated changes (e.g. editing a utility script
after a training run is consolidated). You decide when to re-run.

### DVC stage dependency graph (DAG)

```
00_render
    │  out: data/manifests/00_render.json
    ▼
01_yolox_crops
    │  out: data/manifests/01_yolox_crops.json
    ▼
02_filter_crops
    │  out: data/annotations/excluded_crops.json
    ▼
03_train ──────────────────────────────────────────────────────────┐
    │  out: models/00_train/best.pth                               │
    │       models/00_train/last.pth                               │
    ▼                                                              ▼
04_eval                                                        05_export
    out: data/eval/openset_results.csv                             out: models/02_export/backbone_fp32.onnx
         data/eval/openset_summary.json                                 models/02_export/backbone_tidl.onnx
                                                                        models/02_export/projection_head.onnx
```

The manifest files (`00_render.json`, `01_yolox_crops.json`) serve as **stage
stamps**: they are tiny JSON files (just image counts) that DVC tracks so it
knows a previous stage finished successfully. They form the chain that connects
each stage to the one before it.

---

## 4. Configuration: dvc_config.yaml

Stores only **iteration-invariant constants** — values that do not change from
one training run to the next.

```yaml
paths:          # NAS locations + in-repo output directories
render:         # Blender rendering parameters (per iteration → tracked as params)
filter:         # Small-crop filter threshold (per iteration → tracked as params)
train:          # k_shot_range and support_split (per iteration → tracked as params)
eval:           # k_shots sweep list
operational:    # Sensor pixel envelope (used by transforms + deployment)
split:          # Train/val/test ratio (used by some offline scripts)
fiftyone:       # FiftyOne/MongoDB connection (used by notebook scripts)
```

### Parameter tracking convention

Some values (render, filter, train) are tracked as DVC `params`. This means
DVC records the exact value at the time the stage ran in `dvc.lock`. Changing
the value in `dvc_config.yaml` will make DVC report the stage as "changed" in
`dvc status`.

The other values in each stage `cmd` that are hardcoded (e.g. `--epochs 50`)
are NOT tracked by DVC params — they are only visible in the `cmd` line itself.
This is intentional: those are per-training-run decisions that go into Git
history via the `dvc.yaml` commit, not into DVC's param tracking.

---

## 5. Pipeline stages in detail

### Stage 00 — Synthetic rendering (`00_render`)

```
scripts/batch_render.py  ──► GLB files on NAS
                              │
                              │ Blender subprocess per identity per split
                              │ (train / val / enrollment)
                              ▼
                         NAS: uav_dataset_rendered/
                              ├── train/    <identity>/ *.jpg
                              ├── val/      <identity>/ *.jpg
                              └── enrollment/<identity>/ *.jpg
                              │
                              │ --manifest_out
                              ▼
                         data/manifests/00_render.json   ← DVC out
```

**What it does:**
- Iterates over every `.glb` / `.fbx` model subfolder under `uav_models_root`.
- Splits identities into train / val by `train_ratio` (positives only;
  `neg_*` folders go train-only, no enrollment).
- For each identity, calls `render_uav.py` inside a Blender subprocess.
  `render_uav.py` renders the model from multiple azimuths and elevations,
  applying realistic camera/lighting randomisation (`--realistic`), operational
  distance scaling, and optional colorisation.
- After rendering, moves images out of the intermediate `operational/` subfolder
  into the flat ProtoNet-expected layout (`train/<identity>/*.jpg`).
- Writes `--manifest_out` (image counts per split) as the DVC tracked output.

**Key parameters tracked by DVC (`params: render`):**
`blender`, `train_ratio`, `samples`, `width`, `height`, `azimuths`,
`elevations`, `colorize`, `operational_distance_mult`,
`operational_distance_jitter`

---

### Stage 01 — YOLOX cropping (`01_yolox_crops`)

```
NAS: uav_dataset_rendered/         NAS: yolox_tiny_airborne_v2_qat.onnx
  train/<identity>/*.jpg   ──────────────────────────────┐
  val/<identity>/*.jpg                                    │
                                                          ▼
                              scripts/crop_from_yolox.py
                                   │ runs YOLOX on each frame
                                   │ saves tight crops (+ padding)
                                   │ skips crops below --min_px
                                   ▼
                         NAS: uav_dataset_yolox_crops/
                              ├── train/    <identity>/ *.jpg  (YOLOX crops)
                              ├── val/      <identity>/ *.jpg  (YOLOX crops)
                              └── enrollment/<identity>/ *.jpg (copied uncropped)
                                   │
                                   │ --manifest_out
                                   ▼
                         data/manifests/01_yolox_crops.json   ← DVC out
```

**What it does:**
- Runs the YOLOX-tiny airborne detector ONNX model on every image in the
  rendered train/val splits to produce tight bounding-box crops around each UAV.
- Crops are padded by `--pad` (default 15%) and discarded if either side is
  below `--min_px`.
- The enrollment split is **not** run through YOLOX — enrollment images are
  large close-up renders; they are copied uncropped via `--copy_enrollment`
  (uses `shutil.copytree`, cross-platform).
- Writes the manifest as DVC tracked output.

**Why YOLOX crops?**
At runtime the sensor feeds YOLOX crops to the identification model, not full
frames. Training on YOLOX crops ensures the model sees the same input
distribution it will face in production (domain alignment).

**Why enrollment stays uncropped?**
Enrollment images are high-quality close-up reference photos. The cross-domain
gap (large enrollment photo vs tiny distant crop) is a deliberate part of the
problem. The encoder must bridge it.

---

### Stage 02 — Small-crop filter (`02_filter_crops`)

```
NAS: uav_dataset_yolox_crops/ (train + val)
         │
         ▼
scripts/filter_small_crops.py
         │ scans every crop
         │ records those below --min_px (shorter side)
         ▼
data/annotations/excluded_crops.json   ← DVC out
```

**What it does:**
- Walks the train/val splits of the YOLOX-cropped dataset.
- Records (but does NOT delete) any crop whose shorter side is below `min_px`
  pixels.
- The `IdentityIndex` dataset loader in `src/uavid/dataset/episodic.py` reads
  this JSON at training/evaluation time and skips the listed files.

**Why not just delete small crops?**
Keeping files intact means the dataset on the NAS never changes. Its directory
hash stays stable, so DVC's external-dep tracking stays consistent. The
exclusion list is the only mutable artefact.

**Tracked by DVC params:** `filter.min_px`, `filter.splits`

---

### Stage 03 — Episodic ProtoNet training (`03_train`)

```
NAS: uav_dataset_yolox_crops/    data/annotations/excluded_crops.json
              │                                │
              └──────────────┬────────────────┘
                             ▼
                    scripts/train.py
                         │
                         │  IdentityIndex (train, val, enrollment)
                         │  episodic sampling → episodes
                         │  ProtoNetEncoder (MobileNetV3-Small)
                         │  euclidean prototypical loss
                         │  Adam optimizer (backbone_lr + head lr)
                         │
                         ├── best.pth   ← DVC out (best val accuracy)
                         └── last.pth   ← DVC out (final epoch)
                         │
                         └── MLflow run (params + metrics + artefacts)
```

**What it does:**
- Loads the dataset through `IdentityIndex` which respects the exclusion list.
- Runs `N` epochs, each with `episodes_per_epoch` episodes.
- **Episode**: sample `n_way` identities, take `k_shot` support images from
  enrollment (or train if no enrollment split), take `q_query` query images from
  train. Compute prototypes → Euclidean distance → cross-entropy loss.
- Validates on val split every epoch (`test_n_way` identities, fixed shots).
- Saves `best.pth` (best val accuracy) and `last.pth` (last epoch).
- Logs everything to MLflow (params, per-epoch accuracy/loss, final checkpoints).

**Hardcoded in dvc.yaml (per-run decisions):**
`n_way=15`, `test_n_way=5`, `q_query=5`, `epochs=50`,
`episodes_per_epoch=200`, `lr=0.001`, `backbone_lr=0.0001`,
`metric=euclidean`, `degrade_p=0.0`

**Tracked by DVC params (global constants in config):**
`train.support_split` (which split is the enrollment gallery),
`train.k_shot_range` (set of k values for shot-robust sampling during training)

---

### Stage 04 — Open-set evaluation (`04_eval`)

```
NAS: uav_dataset_yolox_crops/    excluded_crops.json    models/00_train/best.pth
           │                            │                         │
           └────────────────────────────┴─────────────────────────┘
                                        ▼
                             scripts/evaluate.py
                                        │
                    for each k in eval.k_shots:
                    ┌───────────────────────────────────────┐
                    │  gallery: embed enrollment images     │
                    │  queries: embed val images            │
                    │  for each query identity:             │
                    │    build prototype (mean of k shots)  │
                    │    score all queries                  │
                    │    separate genuine vs impostor       │
                    │    compute ROC-AUC + TPR@FPR          │
                    └───────────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
         data/eval/openset_results.csv         data/eval/openset_summary.json
              (DVC out, cache:true)                (DVC metric, cache:true)
                                        │
                                        └── MLflow run (metrics + artefacts)
```

**What it does (open-set evaluation):**
- For each k in `eval.k_shots` (default: 1, 3, 5, 10, 15):
  - Builds a **gallery prototype** per identity by averaging `k` randomly
    sampled enrollment embeddings (mean aggregation, `--agg mean`).
  - Scores all val (query) images against every prototype.
  - Splits scores into **genuine** (query identity matches gallery) and
    **impostor** (query identity does not match gallery).
  - Computes ROC-AUC and TPR at 1%, 5%, 10% FPR.
- Writes one row per k into `openset_results.csv`.
- The best-k summary goes into `openset_summary.json` (also a DVC metric so
  `dvc metrics show` can display it).

**Why "open-set"?**
The model never sees the val identities during training. At evaluation time it
must score each query as genuine or impostor with no re-training — exactly what
deployment looks like when a client enrolls a new, previously-unseen airframe.

---

### Stage 05 — ONNX export (`05_export`)

```
models/00_train/best.pth
         │
         ▼
scripts/export_onnx.py
         │
         ├── backbone_fp32.onnx      (image → 128-d embedding, full precision)
         ├── backbone_tidl.onnx      (image → 576-d features, TIDL-accelerated)
         └── projection_head.onnx   (576-d → 128-d + LayerNorm + L2, ARM/CPU)
```

**What it does:**
- Loads `best.pth` and creates two split sub-modules:
  - `BackboneTIDL`: `features + avgpool + flatten → (B, 576)` — the part
    TI's TIDL accelerator can run on the C7x/MMA DSP.
  - `ProjectionHead`: `Linear(576→128) + LayerNorm + L2 → (B, 128)` — runs on
    ARM cores via ONNX Runtime because TIDL does not support `LayerNorm`.
- Also exports `backbone_fp32.onnx` (the full pipeline fused) for the client
  enrollment app running on a regular PC.

---

## 6. The model in detail

```
Input image (224×224 RGB)
        │
        ▼
  MobileNetV3-Small
  ┌─────────────────────────────────────────────────────┐
  │  features (16 inverted residual blocks)             │  → (B, 576, 7, 7)
  │  avgpool                                            │  → (B, 576, 1, 1)
  └───────────────────────── backbone_tidl.onnx ────────┘
        │
        ▼  flatten → (B, 576)
  ┌─────────────────────────────────────────────────────┐
  │  Linear(576 → 128)                                  │
  │  LayerNorm(128)                                     │
  │  L2 normalise                                       │
  └───────────────────────── projection_head.onnx ──────┘
        │
        ▼
  128-d unit-sphere embedding
```

Everything lives on the unit sphere (L2-normalised). Euclidean distance on the
unit sphere is equivalent in ranking to cosine distance, but the Euclidean form
is used to stay faithful to Snell et al. 2017.

---

## 7. Episodic training explained

```
Episode (one forward pass):

  Support set (from enrollment split):         Query set (from train split):
  ┌─────────────────────────────┐              ┌────────────────────────────┐
  │ identity A: k images        │              │ identity A: q images       │
  │ identity B: k images        │              │ identity B: q images       │
  │ ...         (n_way × k)     │              │ ...        (n_way × q)     │
  └─────────────────────────────┘              └────────────────────────────┘
              │                                             │
              ▼  embed all via encoder                      │
  ┌─────────────────────────────┐                          │
  │ prototype_A = mean(embeds_A)│                          │
  │ prototype_B = mean(embeds_B)│                          │
  │ ...                         │                          │
  └─────────────────────────────┘                          │
              │                                            │
              └──────────── distance matrix ───────────────┘
                         (n_way × q queries)
                                │
                                ▼
                      cross-entropy loss
                      (query → nearest prototype)
```

`k_shot_range = "1,3,5,10,15"` means each episode randomly picks one of those
k values. This makes the model robust to different enrollment sizes at deployment
without needing separate training runs.

---

## 8. Deployment (runtime, not DVC stages)

These scripts are NOT DVC stages — they require client data that is never in the
repo.

```
Client supplies N photos of their UAV
              │
              ▼
        enroll.py
              │  embed each photo with backbone_fp32.onnx (or split ONNX)
              │  average embeddings → one prototype per identity
              ▼
        gallery.npy   (saved locally, never leaves client)

Live sensor crops
              │
              ▼
        deploy_verify.py
              │  embed crop
              │  cosine distance to gallery prototype
              │  apply threshold (from calibrate_threshold.py)
              ▼
        MATCH / NO MATCH decision
```

`calibrate_threshold.py` finds the operating threshold from a held-out set of
positive and negative examples to meet a target FAR (false acceptance rate).

---

## 9. Data locations (NAS paths)

```
NAS root: /mnt/Pool_IA/IA_Dataset/datasets/uav-few-shot-identification/

├── uav_models/                        ← GLB source models (input to 00_render)
├── uav_dataset_rendered/              ← output of 00_render
│   ├── train/<identity>/*.jpg
│   ├── val/<identity>/*.jpg
│   └── enrollment/<identity>/*.jpg
├── uav_dataset_yolox_crops/           ← output of 01_yolox_crops (active dataset)
│   ├── train/<identity>/*.jpg         (YOLOX crops)
│   ├── val/<identity>/*.jpg           (YOLOX crops)
│   └── enrollment/<identity>/*.jpg    (uncropped, copied from renders)
└── backgrounds/                       ← sky/background images (offline scripts)

NAS model: /mnt/Pool_IA/IA_Dataset/models/yolox_tiny_airborne_v2_qat/
└── yolox_tiny_airborne_v2_qat.onnx    ← YOLOX detector used by 01_yolox_crops
```

---

## 10. How to run a stage deliberately

```bash
# On the Vision server (RTX 5090, NAS mounted at /mnt/Pool_IA/...)

# Run a specific frozen stage (ignores frozen flag):
dvc repro --force 03_train

# Run from a specific stage onward (respects DAG):
dvc repro --force 03_train 04_eval 05_export

# Check what DVC considers stale (deps/params changed):
dvc status

# After running: push data artefacts BEFORE git commit:
dvc push
git add dvc.lock
git commit -m "train: iteration 2 — 15-way euclidean, degrade_p=0.3"
```

---

## 11. File tracking summary

| File | Tracked by | Location |
|------|-----------|----------|
| `data/manifests/00_render.json` | DVC out | git (small) |
| `data/manifests/01_yolox_crops.json` | DVC out | git (small) |
| `data/annotations/excluded_crops.json` | DVC out | DVC cache / NAS |
| `models/00_train/best.pth` | DVC out | DVC cache / NAS |
| `models/00_train/last.pth` | DVC out | DVC cache / NAS |
| `data/eval/openset_results.csv` | DVC out (`cache:true`) | DVC cache / NAS |
| `data/eval/openset_summary.json` | DVC metric (`cache:true`) | DVC cache / NAS |
| `models/02_export/*.onnx` | DVC out | DVC cache / NAS |
| `dvc.yaml` | git | repo |
| `dvc.lock` | git | repo |
| `configs/dvc_config.yaml` | git | repo |
| NAS image datasets | NOT tracked (external dep) | NAS only |

---

## 12. src/ vs scripts/ — the separation convention

Following the department convention (same as `sw_ai_detection`, `sw_ai_odd`):

```
scripts/      ← "thin wrappers"
              • Own the CLI (argparse or fire.Fire)
              • Own MLflow orchestration (start_run, log_params, log_metrics)
              • Call exactly one function from src/

src/uavid/    ← "pure logic"
              • No CLI
              • No MLflow imports
              • No argparse
              • Testable in isolation
              • Reusable across scripts
```

This means if you want to change what gets logged to MLflow, you only touch
`scripts/train.py`. If you want to change how episodes are sampled, you only
touch `src/uavid/dataset/episodic.py`. The boundary is clean.
