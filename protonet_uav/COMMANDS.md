# Important Commands

This file collects the main commands used during the YOLOX cropping, enrollment, and ProtoNet identification workflow.

Run all commands from the repository root:

```powershell
cd C:\Users\tsa3\Desktop\TFG\protonet_uav
```

## Activate The Virtual Environment

Activates the local Python environment so commands use the project dependencies.

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation in the current terminal session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## Check ONNX Runtime And CUDA

Shows the installed ONNX Runtime version and which execution providers are available.

```powershell
.\.venv\Scripts\python.exe -c "import onnxruntime as ort; print('onnxruntime', ort.__version__); print('providers available:', ort.get_available_providers())"
```

Checks whether PyTorch can see the GPU and which CUDA version it was installed with.

```powershell
.\.venv\Scripts\python.exe -c "import torch; print('torch cuda:', torch.version.cuda); print('torch gpu:', torch.cuda.is_available())"
```

Checks the NVIDIA driver and GPU visibility from Windows.

```powershell
nvidia-smi
```

Expected working setup after fixing ONNX Runtime GPU compatibility:

```text
torch cuda: 12.1
torch gpu: True
ort: 1.20.1
['CUDAExecutionProvider', 'CPUExecutionProvider']
```

## Install Compatible ONNX Runtime GPU

Use this if ONNX Runtime was installed with a CUDA version that does not match the environment.

```powershell
.\.venv\Scripts\python.exe -m pip uninstall -y onnxruntime-gpu
.\.venv\Scripts\python.exe -m pip install onnxruntime-gpu==1.20.1
```

Why: this matches the existing PyTorch `2.5.1+cu121` CUDA 12.1 setup better than newer ONNX Runtime GPU builds that expect CUDA 13.

## YOLOX Model Path

The QAT YOLOX ONNX file is inside a directory whose name also ends in `.onnx`:

```text
C:\Users\tsa3\Downloads\yolox_tiny_airborne_v2_qat\yolox_tiny_airborne_v2_qat.onnx\model\yolox_tiny_airborne_v2_qat.onnx
```

Use this full path as the `--model` value.

## Crop Query Frames With YOLOX

Crops all raw query frames from:

```text
data\demo\video_fragmentation_preview
```

and writes YOLOX crops to:

```text
data\demo\train\video_fragmentation_preview
```

```powershell
.\.venv\Scripts\python.exe .\scripts\crop_from_yolox.py --model "C:\Users\tsa3\Downloads\yolox_tiny_airborne_v2_qat\yolox_tiny_airborne_v2_qat.onnx\model\yolox_tiny_airborne_v2_qat.onnx" --flat data\demo\video_fragmentation_preview --identity video_fragmentation_preview --split train --out_root data\demo
```

Notes:

- `--input_size` is no longer needed; the script infers it from the ONNX model.
- `--max_crops` is no longer needed; omitting it processes all input images.
- Default `--min_px` is now `15`, so tiny far-away UAV detections are kept.
- Add `--preview` if you want to inspect each crop interactively.

Preview one or more crops manually:

```powershell
.\.venv\Scripts\python.exe .\scripts\crop_from_yolox.py --model "C:\Users\tsa3\Downloads\yolox_tiny_airborne_v2_qat\yolox_tiny_airborne_v2_qat.onnx\model\yolox_tiny_airborne_v2_qat.onnx" --flat data\demo\video_fragmentation_preview --identity video_fragmentation_preview --split train --out_root data\demo --preview
```

## Re-Render Operational Frames Closer

Use this when the operational UAVs are too small. The current renderer default uses a closer operational camera than the old preset: `--operational_distance_mult 32` with `--operational_distance_jitter 1.10 1.35`, aiming for rendered UAVs around `60-120px`. Enrollment remains a separate large-image domain.

Use an absolute output path with Blender on Windows:

```powershell
.\.venv\Scripts\python.exe .\scripts\batch_render.py --models_dir uav_models --output_dir "C:\Users\tsa3\Desktop\TFG\protonet_uav\data\uav_dataset_rendered_60_120" --blender "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --train_ratio 0.75 --samples 8 --width 640 --height 640 --azimuths 8 --elevations -65 -45 -25 -10 --realistic --variants 1 --sky_count 3 --colorize operational --operational_distance_mult 32 --operational_distance_jitter 1.10 1.35
```

Smoke-test one frame first:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background --python-exit-code 1 --python .\scripts\render_uav.py -- --model "C:\Users\tsa3\Desktop\TFG\protonet_uav\uav_models\baykar_bayraktar_tb2\baykar_bayraktar_tb2.glb" --name closer_smoke --output "C:\Users\tsa3\Desktop\TFG\protonet_uav\data\render_smoke_60_120" --samples 1 --width 640 --height 640 --azimuths 1 --elevations -25 --sky_count 1 --skip_enrollment
```

The smoke-test render measured about `70px` foreground object long-side with the audit estimator.

After rendering, build the ProtoNet-ready YOLOX crop dataset from the new raw renders:

```powershell
.\.venv\Scripts\python.exe .\scripts\crop_from_yolox.py --model "C:\Users\tsa3\Downloads\yolox_tiny_airborne_v2_qat\yolox_tiny_airborne_v2_qat.onnx\model\yolox_tiny_airborne_v2_qat.onnx" --raw_root "C:\Users\tsa3\Desktop\TFG\protonet_uav\data\uav_dataset_rendered_60_120" --out_root "C:\Users\tsa3\Desktop\TFG\protonet_uav\data\uav_dataset_yolox_crops_60_120"

Copy-Item "C:\Users\tsa3\Desktop\TFG\protonet_uav\data\uav_dataset_rendered_60_120\enrollment" "C:\Users\tsa3\Desktop\TFG\protonet_uav\data\uav_dataset_yolox_crops_60_120\enrollment" -Recurse

.\.venv\Scripts\python.exe .\scripts\filter_small_crops.py --data_root "C:\Users\tsa3\Desktop\TFG\protonet_uav\data\uav_dataset_yolox_crops_60_120" --min_px 30

.\.venv\Scripts\python.exe .\scripts\audit_dataset.py --data_root "C:\Users\tsa3\Desktop\TFG\protonet_uav\data\uav_dataset_yolox_crops_60_120" --show_sizes
```

## Clean And Audit YOLOX Crop Dataset

For the training/evaluation YOLOX crop dataset, keep train/val crops at least 30px on the shorter side. The script quarantines small crops into a sibling folder and does not touch `enrollment/`, because enrollment is intentionally a large-image support domain.

Dry-run first:

```powershell
.\.venv\Scripts\python.exe .\scripts\filter_small_crops.py --data_root data\uav_dataset_yolox_crops --min_px 30 --dry_run
```

Apply cleanup:

```powershell
.\.venv\Scripts\python.exe .\scripts\filter_small_crops.py --data_root data\uav_dataset_yolox_crops --min_px 30
```

Audit after cleanup:

```powershell
.\.venv\Scripts\python.exe .\scripts\audit_dataset.py --data_root data\uav_dataset_yolox_crops --show_sizes
```

## Enroll Support Images

Creates an embedding gallery from the support/reference UAV images.

Support images:

```text
data\demo\video_demo\without_bg
```

Output gallery:

```text
data\demo\client_uav\gallery.npy
```

```powershell
.\.venv\Scripts\python.exe -m src.enroll --checkpoint checkpoints_mixed_domain_real_data\best.pth --images data\demo\video_demo\without_bg --out data\demo\client_uav\gallery.npy
```

What it does: embeds each support image with the trained ProtoNet encoder and saves the resulting vectors into `gallery.npy`.

## Identify YOLOX-Cropped Query Images

Compares the enrolled gallery against the YOLOX-cropped query frames.

```powershell
.\.venv\Scripts\python.exe -m src.identify --checkpoint checkpoints_mixed_domain_real_data\best.pth --gallery data\demo\client_uav\gallery.npy --images data\demo\train\video_fragmentation_preview --agg mean --threshold 0.6
```

What it does: scores every query crop against the enrolled support gallery. Higher score means more similar. Images with score greater than or equal to `--threshold` are marked `MATCH`.

---

## Phase 0 — Lock The Measurement Baseline

Run **once** on the best existing checkpoint before any model changes.
This scoreboard is the reference every future phase is judged against.

### 1. Install open-clip-torch (needed for Phase 1 CLIP backbone — skip if you only need Phase 0)

```powershell
.\.venv\Scripts\python.exe -m pip install open-clip-torch>=2.24
```

### 2. Per-identity verification AUC + bootstrap CIs + EER (degraded queries)

Queries use clean images (`--degrade_p 0.0`).
Gallery/enrollment images stay clean.  The scoreboard reveals which identities
have unreliable estimates (wide CI) and need more query frames.

```powershell
.\.venv\Scripts\python.exe .\scripts\eval_verification_auc.py `
    --checkpoint checkpoints_yolox_crops_mixed_domain_real\best.pth `
    --data_root  data\uav_dataset_yolox_crops `
    --k_shot 5 --degrade_p 0.0 `
    --out_csv csvs\phase0_baseline_k5_degrade100_verification_auc.csv
```

### 3. Same scoreboard on clean queries (upper-bound reference)

```powershell
.\.venv\Scripts\python.exe .\scripts\eval_verification_auc.py `
    --checkpoint checkpoints_yolox_crops_mixed_domain_real\best.pth `
    --data_root  data\uav_dataset_yolox_crops `
    --k_shot 5 --degrade_p 0.0 `
    --out_csv csvs\phase0_baseline_k5_degrade0_verification_auc.csv
```

### Identities that need more query frames (val split)

The following val identities have very few images; their per-identity CIs will
be too wide to be meaningful.  Collect more YOLOX crops from real footage
before trusting their individual AUC numbers:

| Identity           | val images | status                              |
|--------------------|-----------|-------------------------------------|
| real2              | 1         | skipped (< k_shot+1)                |
| Ukraine_PD-2_UAV   | 3         | skipped at k_shot=5 (same-split)    |
| rq-11_raven_uav    | 5         | skipped at k_shot=5 (same-split)    |
| uav                | 5         | skipped at k_shot=5 (same-split)    |

Use a separate enrollment split or gather more real/synthetic frames for these
identities to tighten the CIs.

---

## Phase 1 — DINOv2 / CLIP Backbone (No Hardware Constraints)

Backbone weights are downloaded automatically on first run.
DINOv2 ViT-S/14 ≈ 330 MB;  CLIP ViT-B/32 ≈ 350 MB.  Requires internet.

### Train with DINOv2 ViT-S/14

```powershell
.\.venv\Scripts\python.exe -m src.train `
    --backbone dinov2_vits14 `
    --data_root data\uav_dataset_yolox_crops `
    --out checkpoints_dinov2_vits14 `
    --epochs 30 --n_way 15 --test_n_way 5 `
    --k_shot_range 1 3 5 10 15 --q_query 5 `
    --degrade_p 0.5 --freeze_backbone_epochs 5 --embed_dim 128
```

Freeze backbone longer (`--freeze_backbone_epochs 10`) if the head loss diverges
in early epochs — DINOv2 weights are fragile to high LR.

### Train with DINOv2 ViT-B/14 (heavier, usually better)

```powershell
.\.venv\Scripts\python.exe -m src.train `
    --backbone dinov2_vitb14 `
    --data_root data\uav_dataset_yolox_crops `
    --out checkpoints_dinov2_vitb14 `
    --epochs 30 --n_way 15 --test_n_way 5 `
    --k_shot_range 1 3 5 10 15 --q_query 5 `
    --degrade_p 0.5 --freeze_backbone_epochs 5 --embed_dim 256
```

### Train with CLIP ViT-B/32

```powershell
.\.venv\Scripts\python.exe -m src.train `
    --backbone clip_vit_b32 `
    --data_root data\uav_dataset_yolox_crops `
    --out checkpoints_clip_vit_b32 `
    --epochs 30 --n_way 15 --test_n_way 5 `
    --k_shot_range 1 3 5 10 15 --q_query 5 `
    --degrade_p 0.5 --freeze_backbone_epochs 5 --embed_dim 128
```

### Evaluate Phase 1 checkpoint on the Phase 0 scoreboard

Replace `checkpoints_dinov2_vits14` with whichever checkpoint you want to compare:

```powershell
.\.venv\Scripts\python.exe .\scripts\eval_verification_auc.py `
    --checkpoint checkpoints_dinov2_vits14\best.pth `
    --data_root  data\uav_dataset_yolox_crops `
    --k_shot 5 --degrade_p 0.0 `
    --out_csv csvs\phase1_dinov2_vits14_k5_degrade100_verification_auc.csv
```

K-shot sweep for a full open-set comparison:

```powershell
.\.venv\Scripts\python.exe .\scripts\eval_kshot_sweep.py `
    --checkpoint checkpoints_dinov2_vits14\best.pth `
    --data_root  data\uav_dataset_yolox_crops `
    --split val --agg mean --k_shots 1 3 5 10 15
```

## Video-Style Scoring Against Support Images

Scores query frames/crops as a video-like set and writes CSV summaries.

Using YOLOX-cropped query frames:

```powershell
.\.venv\Scripts\python.exe .\scripts\demo_video_identity_scores.py --checkpoint checkpoints_mixed_domain_real_data\best.pth --support data\demo\video_demo\without_bg --query_frames data\demo\train\video_fragmentation_preview --max_frames 0 --top_k_frames 5 --no_dataset_identities --out_csv csvs\demo_video_without_bg_support_scores.csv --out_frame_csv csvs\demo_video_without_bg_support_frame_scores.csv
```

What it does:

- Uses `data\demo\video_demo\without_bg` as support/reference images.
- Uses `data\demo\train\video_fragmentation_preview` as YOLOX-cropped query frames.
- Scores all frames and reports mean, max, and top-k frame similarity.
- Saves summary scores to `csvs\demo_video_without_bg_support_scores.csv`.
- Saves per-frame scores to `csvs\demo_video_without_bg_support_frame_scores.csv`.

If you want to score the raw, uncropped query frames instead, use:

```powershell
.\.venv\Scripts\python.exe .\scripts\demo_video_identity_scores.py --checkpoint checkpoints_mixed_domain_real_data\best.pth --support data\demo\video_demo\without_bg --query_frames data\demo\video_fragmentation_preview --max_frames 0 --top_k_frames 5 --no_dataset_identities --out_csv csvs\demo_video_without_bg_support_raw_scores.csv --out_frame_csv csvs\demo_video_without_bg_support_raw_frame_scores.csv
```

## Previous Evaluation Commands

K-shot sweep on the enrollment gallery split:

```powershell
.\.venv\Scripts\python.exe .\scripts\eval_kshot_sweep.py --checkpoint checkpoints_mixed_domain_enrollment_support_15way\best.pth --data_root data\uav_dataset_color_mild_clean --gallery_split enrollment --split val --agg mean --k_shots 11 12 13 14 15 16
```

Open-set evaluation for selected k-shot values:

```powershell
foreach ($k in 5,10) {.\.venv\Scripts\python.exe -m src.eval_openset --checkpoint checkpoints_mixed_domain_extended\best.pth --data_root data\uav_dataset_color_mild_clean --k_shot $k --agg mean --gallery_split enrollment --split val}
```

## Typical End-To-End Flow

1. Crop the raw query frames with YOLOX.
2. Enroll the support images into `gallery.npy`.
3. Identify the cropped query frames against the gallery.
4. Optionally run the video-style scoring script for CSV summaries.

Commands:

```powershell
.\.venv\Scripts\python.exe .\scripts\crop_from_yolox.py --model "C:\Users\tsa3\Downloads\yolox_tiny_airborne_v2_qat\yolox_tiny_airborne_v2_qat.onnx\model\yolox_tiny_airborne_v2_qat.onnx" --flat data\demo\video_fragmentation_preview --identity video_fragmentation_preview --split train --out_root data\demo

.\.venv\Scripts\python.exe -m src.enroll --checkpoint checkpoints_mixed_domain_real_data\best.pth --images data\demo\video_demo\without_bg --out data\demo\client_uav\gallery.npy

.\.venv\Scripts\python.exe -m src.identify --checkpoint checkpoints_mixed_domain_real_data\best.pth --gallery data\demo\client_uav\gallery.npy --images data\demo\train\video_fragmentation_preview --agg mean --threshold 0.6

.\.venv\Scripts\python.exe .\scripts\demo_video_identity_scores.py --checkpoint checkpoints_mixed_domain_real_data\best.pth --support data\demo\video_demo\without_bg --query_frames data\demo\train\video_fragmentation_preview --max_frames 0 --top_k_frames 5 --no_dataset_identities --out_csv csvs\demo_video_without_bg_support_scores.csv --out_frame_csv csvs\demo_video_without_bg_support_frame_scores.csv
```

## Deployment Demo — One-Command Binary Verification (Embention)

This is the deployed runtime. It answers one binary question per frame: does the
detected UAV match the **enrolled** target? It does NOT rank against training
identities. Pipeline: `raw frame -> YOLOX detect+crop -> ProtoNet embed -> cosine
vs enrolled gallery -> threshold -> MATCH/UNKNOWN`, then an aggregated verdict.

Active checkpoint: `checkpoints_yolox_crops_mixed_domain\best.pth` (epoch 8,
val_acc 0.851). Always score with the mean prototype.

### 1. Enroll the target (client side, one time)

```powershell
New-Item -ItemType Directory -Force -Path galleries | Out-Null
.\.venv\Scripts\python.exe -m src.enroll --checkpoint checkpoints_yolox_crops_mixed_domain\best.pth --images data\demo\video_demo_enrollment\without_bg --out galleries\demo_target_without_bg.npy
```

Only `galleries\demo_target_without_bg.npy` ever leaves the client.

### 2. Calibrate the MATCH threshold from data

Positives = crops of the enrolled target. Negatives = curated impostor crops.

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_threshold.py --checkpoint checkpoints_yolox_crops_mixed_domain\best.pth --gallery galleries\demo_target_without_bg.npy --pos data\demo\camera_video_fragmentation_preview --neg data\demo\video_demo_enrollment\impostor --out_csv csvs\threshold_calibration_demo_target.csv
```

Result for the demo target: positives mean 0.28 (max 0.61), impostors mean 0.14
(max 0.17). Recommended threshold **0.18** -> 76% per-frame detection at **0%
false-accept** (balanced accuracy 88%). Use `--target_far 0.05` to pick a
threshold at a target false-accept rate. Note: only the *curated* impostor set is
a true negative; `vector_uav` is visually similar and scores high (hard negative),
so it is not used as a calibration negative.

### 3. Run end-to-end verification (video file OR folder of frames)

```powershell
.\.venv\Scripts\python.exe scripts\deploy_verify.py --model "C:\Users\tsa3\Downloads\yolox_tiny_airborne_v2_qat\yolox_tiny_airborne_v2_qat.onnx\model\yolox_tiny_airborne_v2_qat.onnx" --checkpoint checkpoints_yolox_crops_mixed_domain\best.pth --gallery galleries\demo_target_without_bg.npy --threshold 0.18 --input data\demo\video_fragmentation_preview --out_csv csvs\deploy_demo_target.csv --save_overlay out\overlay_demo_target
```

`--input` accepts a video file (`.mp4/.avi/.mov/...`) or a folder of frames.
Useful flags: `--frame_stride N`, `--max_frames N`, `--conf` (YOLOX), `--save_overlay`
(annotated frames with boxes + verdict), and the verdict rule `--min_votes` /
`--min_match_frac`.

Genuine target result: 51/70 frames MATCH, top-15 score 0.60 -> **TARGET
CONFIRMED**. Running the same command on impostor footage -> **TARGET NOT
CONFIRMED**.
