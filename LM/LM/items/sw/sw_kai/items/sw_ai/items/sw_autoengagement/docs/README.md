# sw_autoengadgement — Few-Shot UAV Identification

Privacy-preserving few-shot UAV **identification** module for the Embention **KAI**
Autonomous Engagement pipeline. A client enrolls a target UAV from a handful of
reference photographs (processed locally — images never leave the client) and the
device answers, per YOLOX crop, a single yes/no question: *does this match the
enrolled target?*

The model is a Prototypical Network (MobileNetV3-Small → 128-d L2-normalised
embedding) trained episodically with mixed-domain support/query sampling.

> **Note:** All command paths in this document are relative to `items/`.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [MD-IT.668 — UAV Few-Shot Identification](MD-IT.668-uav-few-shot-identification/es/index.md) | Methodology: architecture, dataset, training, evaluation, deployment |
| [IT.980 — AI Training Infrastructure Usage](https://documentation.embention.net/980/en/latest/index.html) | NAS, MLflow, DVC, FiftyOne, CVAT, TIDL deployment |
| [P.073 — Organization Of Design Data](https://documentation.embention.net/) | Repository / item structure standard |

---

## Requirements

- [uv](https://github.com/astral-sh/uv)
- Python 3.13 (managed with uv)
- NVIDIA GPU (training runs on the Vision server, RTX 5090, CUDA 12.8+)
- DVC 3.66+
- Pre-commit (optional, for linting and type-checking)

### Install

```bash
uv sync
pre-commit install   # optional
```

---

## Infrastructure

### Configure `.env`

The `.env` file holds the storage paths and service URIs. Only `LOCAL_NAS_PATH`
changes between the NAS and the Vision server.

| Service  | URL                       | Purpose                          |
|----------|---------------------------|----------------------------------|
| MLflow   | http://192.168.2.1:5000   | Experiment tracking              |
| FiftyOne | http://localhost:5151     | Dataset visualisation & curation |
| CVAT     | http://192.168.2.1:8080   | Manual image/video annotation    |
| MongoDB  | 192.168.2.1:27017         | FiftyOne database backend        |

Run `scripts/setup_data_persistance.sh` once per machine to create the NAS
directories and configure the shared DVC cache + remote.

---

## Configuration

| File | Purpose | Machine-specific? |
|------|---------|:-----------------:|
| `.env` | Service URIs, NAS paths, credentials | No (except `LOCAL_NAS_PATH`) |
| `configs/dvc_config.yaml` | Pipeline params: dataset paths, split/train settings | **Yes** (paths) |
| `configs/setup.yaml` | MLflow tracking URI and experiment name | **Yes** |

### Where the data lives

Following the department convention (`sw_ai_odd`):

| What | Where | DVC |
|------|-------|-----|
| **Image datasets** (renders + crops) | NAS: `/mnt/Pool_IA/IA_Dataset/datasets/uav-few-shot-identification/` | external **dep** (hashed at `dvc repro`, **not** `dvc add`-ed) |
| **Stage manifests** (per-split counts) | repo `data/manifests/` | pipeline **outs** |
| **Small-crop exclusion list** | repo `data/annotations/excluded_crops.json` | pipeline **out** |
| **Eval reports** | repo `data/eval/` | pipeline **outs** |
| **Trained weights / ONNX** | repo `models/` | pipeline **outs** |

Each data-generation stage writes its **images to the NAS** as a side effect and
emits a small **JSON manifest** in `data/manifests/` as its tracked `out` -- the
heavy images are never copied into git or `dvc-storage`.

The active training dataset is set by `paths.active_dataset` in
`configs/dvc_config.yaml` (default `uav_dataset_yolox_crops`). It is listed as an
external DVC dep purely for **traceability** -- its hash is recorded in
`dvc.lock` when training runs. All stages are `frozen: true`, so **editing the
dataset does NOT auto-retrain**: you retrain deliberately by running the training
command (or `dvc repro --force 03_train`).

#### Immutable dataset, no silent re-curation

When a crop is too small to be useful (shorter side below `filter.min_px`, default
30 px), it is **not deleted**. Stage `02_filter_crops` records its dataset-relative
path in `data/annotations/excluded_crops.json`; the episodic loader
(`IdentityIndex(..., exclude=...)`) then skips those crops as if they did not
exist. This keeps the on-NAS dataset bit-for-bit stable (its hash never changes
from filtering), so the dataset stops churning between experiments.

---

## Layout

```
items/
├── configs/        dvc_config.yaml (pipeline params) + setup.yaml (machine/env)
├── data/           DERIVED artifacts only: annotations/ + eval/ (images live on NAS)
├── deployment/     docker-compose for the shared MLOps services
├── models/         trained weights, galleries, exported ONNX (DVC / artifacts)
├── notebooks/      analysis notebooks (embedding maps, ablations)
├── scripts/        thin `fire` CLIs (one per pipeline stage) + render/demo tools
├── src/uavid/      the Python package (see below)
└── test/           unit / smoke tests
```

### `src/uavid/` package

| Module                  | Responsibility                                                   |
|-------------------------|------------------------------------------------------------------|
| `uavid.common`          | I/O + hashing (`io`), config loading, constants, transforms      |
| `uavid.model`           | Encoder, prototypes, distance metrics, attention aggregation     |
| `uavid.dataset`         | Episodic dataset + N-way K-shot samplers (mixed-domain support)  |
| `uavid.preprocessing`   | YOLOX crop extraction, small-crop exclusion list, dataset manifests |
| `uavid.train`           | Episodic prototypical training logic (`trainer`, MLflow-free)    |
| `uavid.inference`       | Enrollment (`gallery.npy`), identification, the `Verifier`       |
| `uavid.eval`            | Open-set evaluation (cross/same-domain AUC)                      |
| `uavid.export`          | Split ONNX export (backbone + projection head) and INT8 quantize |

Following the department convention (`sw_ai_odd`): training/eval **logic** lives
in `src/uavid/`, while the CLIs (`fire`) and MLflow orchestration live in
`scripts/`.

---

## DVC pipeline

`dvc.yaml` is the **pipeline recipe** -- one stage per processing step. The image
datasets live on the NAS (external deps, hashed in `dvc.lock` for traceability);
small JSON manifests / reports in `data/` are the tracked `outs`. All stages are
`frozen: true`, so `dvc repro` does **not** auto-rerun them when a dep changes --
each step is run deliberately.

| Stage | Step | Script | Tracked output |
|-------|------|--------|----------------|
| `00_render` | Synthetic rendering (Blender) | `batch_render.py` | `data/manifests/00_render.json` |
| `01_yolox_crops` | YOLOX cropping | `crop_from_yolox.py` | `data/manifests/01_yolox_crops.json` |
| `02_filter_crops` | Small-crop exclusion list | `filter_small_crops.py` | `data/annotations/excluded_crops.json` |
| `03_train` | Episodic ProtoNet training | `train.py` | `models/00_train/{best,last}.pth` |
| `04_eval` | Open-set evaluation (k-shot sweep) | `evaluate.py` | `data/eval/openset_{results.csv,summary.json}` |
| `05_export` | Split ONNX export (TIDL) | `export_onnx.py` | `models/02_export/*.onnx` |

This maps onto the conceptual **8-step workflow** of the module:

1. **Download GLB models** -> `uav_models/` on the NAS *(manual; not a DVC stage)*
2. **Synthetic rendering** -> `00_render`
3. **YOLOX cropping** -> `01_yolox_crops`
4. **Clean & audit** -> `02_filter_crops`
5. **Episodic training** -> `03_train`
6. **Open-set evaluation** -> `04_eval`
7. **Enrollment** *(client-side runtime)*
8. **Threshold calibration + deployment** *(client-side runtime)*

Steps **1-4** are data generation, **5-6** are model building, and **7-8** are the
client-side runtime. Steps 7-8 are **not** DVC `repro` stages -- they need client
images and cannot be reproduced from the repo; run them with `scripts/enroll.py`,
`scripts/calibrate_threshold.py` and `scripts/deploy_verify.py`.

```bash
dvc repro --force 03_train   # run training deliberately (frozen stage)
dvc repro --dry              # preview what (un-frozen) would run
uv run dvc push              # push pipeline outputs to the NAS BEFORE git commit
```

Or just run the script directly (training logs to MLflow either way):

```bash
PYTHONPATH=. uv run python scripts/train.py --data_root <dataset> --exclude_json data/annotations/excluded_crops.json ...
```

---

## Common commands

```bash
# Train (episodic, mixed-domain, MLflow-tracked). MEAN aggregation is the default.
# data_root points at the curated dataset on the NAS.
PYTHONPATH=. uv run python scripts/train.py \
    --data_root /mnt/Pool_IA/IA_Dataset/datasets/uav-few-shot-identification/uav_dataset_yolox_crops \
    --exclude_json data/annotations/excluded_crops.json \
    --support_split enrollment \
    --n_way 15 --test_n_way 5 --k_shot_range "1,3,5,10,15" --degrade_p 0.0

# Build the small-crop exclusion list (no files are deleted; dataset stays immutable)
PYTHONPATH=. uv run python scripts/filter_small_crops.py \
    --data_root /mnt/Pool_IA/IA_Dataset/datasets/uav-few-shot-identification/uav_dataset_yolox_crops \
    --min_px 30 --out data/annotations/excluded_crops.json

# Open-set evaluation (the deployment metric is cross-domain AUC)
PYTHONPATH=. uv run python scripts/evaluate.py \
    --data_root /mnt/Pool_IA/IA_Dataset/datasets/uav-few-shot-identification/uav_dataset_yolox_crops \
    --exclude_json data/annotations/excluded_crops.json \
    --checkpoint models/00_train/best.pth \
    --split val --gallery_split enrollment --agg mean

# Enroll a target locally (only gallery.npy leaves the client)
PYTHONPATH=. uv run python scripts/enroll.py --images refs/ --out gallery.npy

# Identify
PYTHONPATH=. uv run python scripts/identify.py --gallery gallery.npy --images crops/

# Export to ONNX (split backbone + projection head for TIDL)
PYTHONPATH=. uv run python scripts/export_onnx.py --checkpoint models/00_train/best.pth
```

> Aggregation: use `--agg mean` for all deployment scoring. Attention is documented
> and evaluated (Q4) but rejected — it inflates impostor scores at k ≥ 5.

---

## Scripts

The `scripts/` directory holds thin `fire` CLIs (one per pipeline stage:
`batch_render.py`, `crop_from_yolox.py`, `filter_small_crops.py`,
`dataset_manifest.py`, `train.py`, `evaluate.py`, `export_onnx.py`,
`quantize.py`), the client-side runtime tools (`enroll.py`, `identify.py`,
`calibrate_threshold.py`, `deploy_verify.py`), the historical-run MLflow back-fill
(`backfill_mlflow.py`), the NAS setup script (`setup_data_persistance.sh`), and
the dataset render/composite/demo tooling. All accept `--help` for full argument
docs.
