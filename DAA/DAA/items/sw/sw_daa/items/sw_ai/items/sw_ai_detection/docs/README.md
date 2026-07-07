# AI Environment

MLOps pipeline for airborne object detection: data ingestion, curation, annotation, and YOLOX training.

> **Note:** All command paths in this document are relative to `items/`.

---

## Requirements

- [uv](https://github.com/astral-sh/uv)
- Python 3.13 (managed with [uv](https://github.com/astral-sh/uv))
- Docker with NVIDIA GPU support (`--gpus all`)
- DVC 3.66+
- Pre-commit (optional, for linting and type-checking)

### Install

```bash
uv sync
pre-commit install   # optional
```

---

## Infrastructure

### Configure .env

The `.env` file contains the paths of the different storage folders. Only `LOCAL_NAS_PATH` should change between NAS or Vision server.

Services are defined in `deployment/docker-compose.yml`.
The `.env` file in the item root must be symlinked into `deployment/` before starting:

```bash
cd deployment && ln -s ../.env .env
```

### Start all services

```bash
cd deployment
docker-compose up -d
```

| Service  | URL                    | Purpose                          |
|----------|------------------------|----------------------------------|
| MLflow   | http://localhost:5000  | Experiment tracking              |
| FiftyOne | http://localhost:5151  | Dataset visualisation & curation |
| CVAT     | http://localhost:8080  | Manual image/video annotation    |
| MongoDB  | localhost:27017        | FiftyOne database backend        |

All service state is persisted on the NAS (`LOCAL_NAS_PATH` from `.env`):
MLflow artifacts, FiftyOne DB, MongoDB data, CVAT attachments.
Run `scripts/setup_data_persistance.sh` once per machine to create these
directories and configure the shared DVC cache.

---

## Configuration

| File | Purpose | Machine-specific? |
|------|---------|:-----------------:|
| `.env` | Service URIs, NAS paths, credentials | No (except `LOCAL_NAS_PATH`) |
| `configs/dvc_config.yaml` | Dataset paths, class lists, sampling targets | **Yes** (paths) |
| `configs/setup.yaml` | Docker image and mount points for training | **Yes** |
| `configs/experiments/yolox_tiny_airborne.py` | Base MMEngine model config (architecture + training schedule) | Paths yes |


### `configs/setup.yaml` — Docker training container settings

```yaml
docker_train:
  image:        edgeai-tensorlab-tidl:r11.1
  ia_env_mount: /ia_env          # workspace mount point inside the container
  dvc_cache:    /data/dvc-cache  # host DVC cache mounted read-only
  mlflow_data:  /data/mlflow     # host path for MLflow data
  dataset_root: /data/datasets/airborne-obj-detection-challenge-training/
```

### `configs/dvc_config.yaml` — dataset paths and class definitions

```yaml
paths:
  airborne_dataset_root: /mnt/Pool_IA/IA_Dataset/datasets/airborne-obj-detection-challenge-training/

airborne_classes: airborne helicopter bird drone flock ufo
```

---

## DVC Pipeline

The full planned pipeline (stages marked with ☐ are currently commented out in `dvc.yaml`):

```
00_airborne_to_coco
        ↓
01_merge_coco_annotations
```

Run a specific stage:

```bash
dvc repro STAGE_NAME
```

Dry-run to see what would execute without running it:

```bash
dvc repro --dry
```

---

## Training

Each experiment is a self-contained MMEngine config in `configs/experiments/`
that inherits from the YOLOX-tiny base and overrides dataset paths, training
schedule, LR, batch size, and MLflow run metadata.

### Create a new experiment

```bash
cp configs/experiments/yolox_tiny_airborne.py configs/experiments/my_experiment.py
# edit paths, max_epochs, base_lr, MLflow run_name, etc.
```

### Run training

```bash
python -m src.tools.run_docker train --config configs/experiments/my_experiment.py
```

### Run evaluation

```bash
python -m src.tools.run_docker test \
    --config configs/experiments/yolox_tiny_airborne.py \
    --checkpoint experiments/<run>/best_*.pth
```

The launcher reads Docker settings from `configs/setup.yaml` and the MLflow
URI from `.env`. Checkpoints are saved to `experiments/<config_stem>/`.

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup_data_persistance.sh` | First-time DVC + NAS persistent storage setup |

### Data pipeline scripts (`src/`)

The `src/` package contains modules for each pipeline stage: dataset conversion
(`src.dataset`), preprocessing and splitting (`src.preprocessing`), FiftyOne /
CVAT integration (`src.fiftyone`), and training utilities (`src.train`).
All modules are runnable with `python -m <module>` and accept `--help` for
full argument documentation.

---

## DVC cache management

```bash
dvc gc -w   # remove cache files not used by the current workspace
dvc gc -a   # remove cache files not used by any git commit/branch
```
