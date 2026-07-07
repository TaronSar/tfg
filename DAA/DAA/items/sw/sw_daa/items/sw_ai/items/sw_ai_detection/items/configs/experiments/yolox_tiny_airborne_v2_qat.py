# edgeai-mmdetection YOLOX-tiny – airborne detection v2 (QAT STAGE).
#
# SECOND STAGE of the two-stage training workflow.
# Inherits the v2 FP32 config and overrides only QAT-specific settings:
#
#   - Loads the best FP32 checkpoint from stage 1.
#   - Trains for 5 epochs with QAT enabled (--quantization 2 via CLI).
#   - Disables Mosaic/MixUp — uses simple augmentation pipeline.
#     Heavy augmentation is counterproductive for QAT: the model is
#     already converged, and synthetic compositions add noise that
#     makes quantizer range estimation harder.  This also cuts
#     data_time ~5× (1 image/sample vs 5 with Mosaic+MixUp).
#   - 10× lower LR than FP32 to avoid disrupting converged weights.
#
# Launch:
#   python tools/train.py configs/.../yolox_tiny_airborne_v2_qat.py \
#       --work-dir experiments/yolox_tiny_airborne_v2_qat_$(date +%Y%m%d_%H%M%S) \
#       --quantization 2
#
# Expected time: ~8-10 hours (vs ~50h with Mosaic pipeline).
# Expected accuracy: mAP within ~1% of FP32 best.
#
# ⚠  NO Python import statements – MMEngine would classify the file as
#    "lazy_import" mode and refuse to mix it with the non-lazy base chain.
#
# ------------------------------------------------------------------
# Base – inherits everything from v2 FP32 config.
# ------------------------------------------------------------------
_base_ = "./yolox_tiny_airborne_v2.py"

_PROJECT_MOUNT = "/workspace/sw_ai_detection"

# ------------------------------------------------------------------
# QAT schedule overrides
# ------------------------------------------------------------------
EXPERIMENT_NAME = "daa_detector"

MAX_EPOCHS = 5
NUM_LAST_EPOCHS = 2
VAL_INTERVAL = 1

BATCH_SIZE = 48
LOG_INTERVAL = 500

# ------------------------------------------------------------------
# Paths (container-side)
# ------------------------------------------------------------------
_NAS_MOUNT = "/mnt/Pool_IA/IA_Dataset/datasets"
_IMG_ROOT = f"{_NAS_MOUNT}/airborne-obj-detection-dataset/airborne_cropped_images/"
_TRAIN_ANN = f"{_PROJECT_MOUNT}/data/09_changed_class_based_on_area/train.json"
_VAL_ANN = f"{_PROJECT_MOUNT}/data/09_changed_class_based_on_area/eval.json"
_METAINFO = dict(classes=("airplane", "helicopter", "bird", "undetermined"))
_IMG_SCALE = (960, 960)  # (height, width)

# ------------------------------------------------------------------
# Load the best FP32 checkpoint from stage 1.
# ------------------------------------------------------------------
load_from = (
    f"{_PROJECT_MOUNT}/experiments/yolox_tiny_airborne_v2_20260528_122830/"
    "best_coco_bbox_mAP_epoch_26.pth"
)

# ------------------------------------------------------------------
# Training schedule — short QAT fine-tuning.
# ------------------------------------------------------------------
train_cfg = dict(max_epochs=MAX_EPOCHS, val_interval=VAL_INTERVAL)

# ------------------------------------------------------------------
# LR schedule — gentle fine-tuning for 5 epochs.
#   Warmup:   1 epoch quadratic (0 → 1e-3)
#   Cosine:   1 → 3 (T_max=2, decay to 5e-5)
#   Constant: 3 → 5 (last 2 epochs, mode-switch off)
# ------------------------------------------------------------------
param_scheduler = [
    dict(
        begin=0,
        end=1,
        by_epoch=True,
        convert_to_iter_based=True,
        type="mmdet.QuadraticWarmupLR",
    ),
    dict(
        begin=1,
        end=MAX_EPOCHS - NUM_LAST_EPOCHS,
        T_max=MAX_EPOCHS - NUM_LAST_EPOCHS - 1,
        by_epoch=True,
        convert_to_iter_based=True,
        eta_min=0.00005,
        type="CosineAnnealingLR",
    ),
    dict(
        begin=MAX_EPOCHS - NUM_LAST_EPOCHS,
        end=MAX_EPOCHS,
        by_epoch=True,
        factor=1,
        type="ConstantLR",
    ),
]

# ------------------------------------------------------------------
# Optimiser — 10x lower LR than FP32 stage.
# ------------------------------------------------------------------
optim_wrapper = dict(optimizer=dict(lr=0.001))

# ------------------------------------------------------------------
# Dataloader — simple pipeline (no Mosaic/MixUp).
#
# Mosaic loads 4 images + MixUp adds 1 more = 5 NAS reads per sample.
# Simple pipeline: 1 read per sample → data_time drops from ~1.1s to
# ~0.2s per iteration, cutting total training time ~3×.
# QAT only needs to calibrate fake quantizers on real data — heavy
# augmentation adds noise without benefit.
# ------------------------------------------------------------------
train_dataloader = dict(
    batch_size=BATCH_SIZE,
    num_workers=12,
    persistent_workers=True,
    sampler=dict(shuffle=True, type="DefaultSampler"),
    dataset=dict(
        _delete_=True,
        type="CocoDataset",
        ann_file=_TRAIN_ANN,
        data_prefix=dict(img=_IMG_ROOT),
        data_root="",
        filter_cfg=dict(filter_empty_gt=True, min_size=0),
        metainfo=_METAINFO,
        pipeline=[
            dict(backend_args=None, type="LoadImageFromFile"),
            dict(type="LoadAnnotations", with_bbox=True),
            dict(keep_ratio=True, scale=_IMG_SCALE, type="Resize"),
            dict(
                pad_to_square=True,
                pad_val=dict(img=(114.0, 114.0, 114.0)),
                type="Pad",
            ),
            dict(type="YOLOXHSVRandomAug"),
            dict(prob=0.5, type="RandomFlip"),
            dict(
                keep_empty=False,
                min_gt_bbox_wh=(1, 1),
                type="FilterAnnotations",
            ),
            dict(type="PackDetInputs"),
        ],
    ),
)

# ------------------------------------------------------------------
# Custom hooks — no YOLOXModeSwitchHook needed (no Mosaic to switch
# off). EMA removed by train.py when --quantization is passed.
# ------------------------------------------------------------------
custom_hooks = [
    dict(type="SyncNormHook", priority=48),
    dict(
        type="EMAHook",
        ema_type="ExpMomentumEMA",
        momentum=0.0002,
        update_buffers=True,
        priority=49,
    ),
    dict(
        type="MLflowHook",
        experiment_name=EXPERIMENT_NAME,
        log_interval=LOG_INTERVAL,
        artifact_suffix=(".json", ".log", ".py", ".yaml", ".pth"),
        train_ann_file=_TRAIN_ANN,
        val_ann_file=_VAL_ANN,
    ),
]
