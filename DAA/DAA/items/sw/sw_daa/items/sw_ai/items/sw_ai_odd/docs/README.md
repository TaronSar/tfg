# sw_ai_odd — Out-of-Distribution Detection Pipeline

Energy-based OOD detection for the DAA airborne background classification
system.  The pipeline trains a ResNet-18 classifier on AOT background frames,
fine-tunes it with corrupted OOD images using energy regularisation and
evaluates detection performance across multiple corruption types and severity
levels.

## Architecture

The pipeline is orchestrated by [DVC](https://dvc.org) and uses these stages:

```
01_create_dataset ─► 02_audit_dataset ─► 03_cleanlab_to_fiftyone ─►
03b_export_cvat_queue ─► 03c_pull_cvat_annotations ─►
03d_build_curation_snapshot ─► 04_apply_curation ─► 05_create_corrupted_full ─►
06_create_corrupted_crops ─► 07_detection_inference ─► 08_train ─►
09_eval ─► 10_build_fiftyone_full ─► 11_build_fiftyone_crops
```

- **01_create_dataset**. CLIP-classify AOT frames into background categories and split into train / val / test.
- **02_audit_dataset**. Compute DINOv2 embeddings, run Cleanlab Datalab, populate FiftyOne and run `fiftyone.brain`.
- **03_cleanlab_to_fiftyone**. Prepare the audited FiftyOne dataset for manual review; the reviewer decides which samples to tag as `relabel`, `to_*`, or `exclude` (and optionally send `relabel` samples to CVAT).
- **03b_export_cvat_queue**. Export `relabel` queue from FiftyOne to a JSONL artifact and create/push a CVAT task.
- **03c_pull_cvat_annotations**. Pull CVAT annotations and write resolved annotation JSONL.
- **03d_build_curation_snapshot**. Freeze the final DVC-tracked `curation_snapshot.jsonl` from current FiftyOne tag state.
- **04_apply_curation**. Consume the stage 03d snapshot and apply exclusions/relabels to produce the curated dataset.
- **05_create_corrupted_full**. Apply image corruptions to curated full-size frames and persist corrupted full images on NAS, while writing local manifests for train / val / test.
- **06_create_corrupted_crops**. Generate corrupted detection crops from persisted corrupted full images using the curated crop offsets and export per-split corrupted crops COCO JSONs.
- **07_detection_inference**. Run YOLOX inference on clean and corrupted persisted crops, compute degradation metrics/plots and export per-crop GT/prediction samples plus the recommended OOD filter.
- **08_train**. Train a ResNet-18 ID classifier, then energy-regularised fine-tuning with OOD exposure using corrupted full images and export to ONNX.
- **09_eval**. Compute classification accuracy and OOD detection metrics (AUROC, FPR@95) and export per-sample OOD scores for downstream visualisation.
- **10_build_fiftyone_full**. Build the full-image FiftyOne dataset with background labels/tags, corruption metadata and per-image OOD score/label.
- **11_build_fiftyone_crops**. Build the crops FiftyOne dataset with GT/predicted detections, crop metadata and inherited parent-frame background + ID/OOD labels.

Each stage writes its outputs to a directory prefixed with its stage number,
so artifacts are easy to trace back to the stage that produced them.

All metrics and artefacts are logged to **MLflow** (`daa_ood_detector` experiment) and models are registered in the MLflow Model Registry.

## Human-in-the-loop curation (FiftyOne ↔ CVAT)

Stages 03b-03d and 04 bracket an interactive, iterative curation loop as follows:

```
02_audit_dataset (cleanlab + brain scores, populates FiftyOne)
        │
03_cleanlab_to_fiftyone  (manual review checkpoint)
        │
   ┌────▼─────────────────────────────────────────────┐
   │  Human loop (repeat as needed):                  │
   │   • Review in FiftyOne UI                         │
   │   • Tag directly (to_Urban / to_Non-urban /      │
   │     to_Water / exclude / relabel)                │
   └────┬─────────────────────────────────────────────┘
   │
03b_export_cvat_queue   (export queue + push CVAT task)
   │
03c_pull_cvat_annotations  (pull CVAT annotations and write resolved annotation JSONL)
   │
03d_build_curation_snapshot  (freeze curation_snapshot.jsonl)
   │
04_apply_curation  (deterministic apply from snapshot file)
```

After each curation round, re-run downstream stages from 04 onward.

## Quick Start

### Prerequisites

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) package manager
- CUDA GPU (optional but recommended)
- AOT dataset mounted
- MLflow tracking server running at `http://localhost:5000`

### Install

```bash
cd items/
uv sync
```

### Run the full pipeline

```bash
uv run dvc repro
```

### Run with human-in-the-loop curation (recommended)

1. Run until the manual review checkpoint is prepared:

   ```bash
   uv run dvc repro 01_create_dataset 02_audit_dataset 03_cleanlab_to_fiftyone
   ```

2. Review in FiftyOne and curate:

   Tag samples directly in the UI: `relabel`, `exclude`, `to_Urban`, `to_Non-urban`, `to_Water`.

   Use `relabel` as a human-only fallback when the correct class is unclear during visual review.

   Use DVC stages to freeze queue/annotations/snapshot artifacts:

   ```bash
   uv run dvc repro 03b_export_cvat_queue
   # annotate in CVAT, then when task is complete:
   uv run dvc repro 03c_pull_cvat_annotations 03d_build_curation_snapshot 04_apply_curation
   ```

3. Continue downstream stages:

   ```bash
   uv run dvc repro 05_create_corrupted_full 06_create_corrupted_crops 07_detection_inference 08_train 09_eval 10_build_fiftyone_full 11_build_fiftyone_crops
   ```

## Development

### Run tests

```bash
uv run pytest test/ -v
```

### Lint and format

```bash
uv run ruff check .
uv run ruff format .
```

### Type checking

```bash
PYTHONPATH=. uv run mypy src/
```
