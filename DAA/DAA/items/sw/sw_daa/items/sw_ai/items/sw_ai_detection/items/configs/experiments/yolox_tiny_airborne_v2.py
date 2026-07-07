# edgeai-mmdetection YOLOX-tiny – airborne detection v2 (FP32 STAGE).
#
# Improvements over V1 baseline:
#
#   1. TWO-STAGE TRAINING — this config is the FP32 pre-training stage.
#      Train to full convergence WITHOUT QAT (quantization=1 is passed
#      separately via CLI for the second stage, NOT DONE YET).
#      Rationale: V2 trained with QAT from epoch 0 and peaked at epoch 20
#      then degraded to 0.156 by epoch 28 — classic observer instability.
#
#   2. CLASS CLEANUP — reduced from 7 → 4 effective classes.
#      Removed airborne/drone/flock/ufo (zero samples in dataset).
#      Empty classes waste head capacity and inject gradient noise.
#
#   3. AUGMENTATION TUNING — added MixUp, narrowed RandomAffine scaling.
#      Aggressive downscaling (0.8x) made tiny objects sub-pixel.
#      MixUp improves regularisation and small-object robustness.
#
#   4. LOSS & ASSIGNMENT — higher bbox loss weight (6.0 vs 5.0),
#      wider SimOTA center_radius (3.5 vs 2.5) for more positive
#      anchors on small objects.
#
#   5. SCHEDULE — 30 epochs FP32, val every 2 epochs.
#      Shorter warmup (3 epochs), cosine to 1e-4, 5 constant tail.
#      Optimised for fast data-refinement iterations.
#
# ⚠  NO Python import statements – MMEngine would classify the file as
#    "lazy_import" mode and refuse to mix it with the non-lazy base chain.
#
# Paths are container-side absolute paths:
#   - workspace is mounted at /workspace/sw_ai_detection
#   - NAS is mounted read-only at the same host path
#
# ------------------------------------------------------------------
# Base – inherits architecture, pipelines, optimizer, LR scheduler.
# Chain: yolox_tiny_lite → yolox_s
# ------------------------------------------------------------------
_base_ = (
    "/workspace/edgeai-tensorlab/edgeai-mmdetection/configs_edgeailite/yolox/yolox_tiny_lite.py"
)

_PROJECT_MOUNT = "/workspace/sw_ai_detection"
_NAS_MOUNT = "/mnt/Pool_IA/IA_Dataset/datasets"

custom_imports = dict(
    imports=["patch_mmcv_nms", "patch_simota", "mlflow_hook", "airborne_coco_metric"],
    allow_failed_imports=False,
)


EXPERIMENT_NAME = "daa_detector"

BATCH_SIZE = 48
MAX_EPOCHS = 30
NUM_LAST_EPOCHS = 5
VAL_INTERVAL = 2

# ------------------------------------------------------------------
# Paths (container-side)
# ------------------------------------------------------------------
_TRAIN_ANN = f"{_PROJECT_MOUNT}/data/09_changed_class_based_on_area/train.json"
_VAL_ANN = f"{_PROJECT_MOUNT}/data/09_changed_class_based_on_area/eval.json"
_TEST_ANN = f"{_PROJECT_MOUNT}/data/09_changed_class_based_on_area/test.json"
_IMG_ROOT = f"{_NAS_MOUNT}/airborne-obj-detection-dataset/airborne_cropped_images/"

_CLASSES = ("airplane", "helicopter", "bird", "undetermined")
NUM_CLASSES = len(_CLASSES)
_METAINFO = dict(classes=_CLASSES)

_IMG_SCALE = (960, 960)  # (height, width)

# ------------------------------------------------------------------
# Lite model + NO Quantization-Aware Training (QAT)
# model_surgery=1: replaces SiLU→ReLU, Focus→FocusLite, etc. (from base).
# ------------------------------------------------------------------
convert_to_lite_model = dict(model_surgery=1)

LOG_INTERVAL = 500
VIS_INTERVAL = 1000
# ------------------------------------------------------------------
# Data loaders
# MMEngine merges nested dicts; only listed keys are overridden.
# ------------------------------------------------------------------
train_dataloader = dict(
    batch_size=BATCH_SIZE,
    num_workers=12,
    dataset=dict(
        dataset=dict(
            data_root="",
            ann_file=_TRAIN_ANN,
            data_prefix=dict(img=_IMG_ROOT),
            metainfo=_METAINFO,
            filter_cfg=dict(filter_empty_gt=True, min_size=0),
        ),
        # Override Mosaic + augmentation pipeline.
        # Changes vs V1:
        #   - RandomAffine scaling narrowed: (0.8,1.5) → (0.9,1.2)
        #     0.8x downscaling made sub-pixel objects; 1.5x upscale OOD.
        #   - MixUp added after RandomAffine for regularisation.
        pipeline=[
            dict(type="Mosaic", img_scale=_IMG_SCALE, pad_val=114.0),
            dict(
                type="RandomAffine",
                scaling_ratio_range=(0.9, 1.2),
                border=(-_IMG_SCALE[0] // 2, -_IMG_SCALE[1] // 2),
            ),
            dict(
                type="MixUp",
                img_scale=_IMG_SCALE,
                ratio_range=(0.8, 1.6),
                pad_val=114.0,
            ),
            dict(type="YOLOXHSVRandomAug"),
            dict(type="RandomFlip", prob=0.5),
            dict(type="Resize", scale=_IMG_SCALE, keep_ratio=True),
            dict(type="Pad", pad_to_square=True, pad_val=dict(img=(114.0, 114.0, 114.0))),
            dict(type="FilterAnnotations", min_gt_bbox_wh=(1, 1), keep_empty=False),
            dict(type="PackDetInputs"),
        ],
    ),
)

test_pipeline = [
    dict(type="LoadImageFromFile", backend_args=None),
    dict(type="Resize", scale=_IMG_SCALE, keep_ratio=True),
    dict(type="Pad", pad_to_square=True, pad_val=dict(img=(114.0, 114.0, 114.0))),
    dict(type="LoadAnnotations", with_bbox=True),
    dict(
        type="PackDetInputs",
        meta_keys=("img_id", "img_path", "ori_shape", "img_shape", "scale_factor"),
    ),
]

val_dataloader = dict(
    batch_size=BATCH_SIZE,
    num_workers=8,
    dataset=dict(
        data_root="",
        ann_file=_VAL_ANN,
        data_prefix=dict(img=_IMG_ROOT),
        metainfo=_METAINFO,
        filter_cfg=dict(filter_empty_gt=True, min_size=0),
        pipeline=test_pipeline,
    ),
)

test_dataloader = dict(
    batch_size=BATCH_SIZE,
    num_workers=8,
    dataset=dict(
        data_root="",
        ann_file=_TEST_ANN,
        data_prefix=dict(img=_IMG_ROOT),
        metainfo=_METAINFO,
        filter_cfg=dict(filter_empty_gt=True, min_size=0),
        pipeline=test_pipeline,
    ),
)

# ------------------------------------------------------------------
# Evaluators – custom area thresholds + recall + per-class AP.
# Default COCO: small <32²=1024, medium <96²=9216px².
# Airborne objects at 1280px are typically 5–80px, so:
#   small  <~14²  =  200px²  (specks, far aircraft, birds)
#   medium <50²   = 2500px²  (nearby aircraft, drones)
#   large  >50²   = 2500px²+ (close-range, flocks)
# ------------------------------------------------------------------
_AREA_RANGES = [[0, 200], [200, 2500], [2500, 1e5**2]]

val_evaluator = dict(
    type="AirborneCocoMetric",
    ann_file=_VAL_ANN,
    area_ranges=_AREA_RANGES,
    metric_items=[
        "mAP",
        "mAP_50",
        "mAP_75",
        "mAP_s",
        "mAP_m",
        "mAP_l",
        "AR@100",
        "AR@300",
        "AR@1000",
        "AR_s@1000",
        "AR_m@1000",
        "AR_l@1000",
    ],
    classwise=True,
)
test_evaluator = dict(
    type="AirborneCocoMetric",
    ann_file=_TEST_ANN,
    area_ranges=_AREA_RANGES,
    metric_items=[
        "mAP",
        "mAP_50",
        "mAP_75",
        "mAP_s",
        "mAP_m",
        "mAP_l",
        "AR@100",
        "AR@300",
        "AR@1000",
        "AR_s@1000",
        "AR_m@1000",
        "AR_l@1000",
    ],
    classwise=True,
)

# ------------------------------------------------------------------
# Training schedule
# ------------------------------------------------------------------
train_cfg = dict(max_epochs=MAX_EPOCHS, val_interval=VAL_INTERVAL)

# ------------------------------------------------------------------
# LR schedule — matched to 30-epoch FP32 training.
#   Warmup:   3 epochs quadratic (0 → 0.012)
#   Cosine:   3 → 25  (T_max=22, decay to 1e-4)
#   Constant: 25 → 30 (last 5 epochs, YOLOX mode-switch)
# Higher eta_min (1e-4 vs 1e-5) prevents LR from vanishing too early.
# ------------------------------------------------------------------
param_scheduler = [
    dict(
        begin=0,
        end=3,
        by_epoch=True,
        convert_to_iter_based=True,
        type="mmdet.QuadraticWarmupLR",
    ),
    dict(
        begin=3,
        end=MAX_EPOCHS - NUM_LAST_EPOCHS,
        T_max=MAX_EPOCHS - NUM_LAST_EPOCHS - 3,
        by_epoch=True,
        convert_to_iter_based=True,
        eta_min=0.0001,
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
# Pretrained weights — COCO-pretrained YOLOX-tiny-lite checkpoint.
# Only matching layers are loaded (num_classes differs).
# ------------------------------------------------------------------
load_from = f"{_PROJECT_MOUNT}/models/yolox_tiny_lite_416x416_20220217_checkpoint.pth"

# ------------------------------------------------------------------
# Optimiser
# ------------------------------------------------------------------
optim_wrapper = dict(optimizer=dict(lr=0.012))

# ------------------------------------------------------------------
# Model – override num_classes and lower val score_thr.
# ------------------------------------------------------------------
model = dict(
    bbox_head=dict(
        num_classes=NUM_CLASSES,
        loss_bbox=dict(loss_weight=6.0),
    ),
    train_cfg=dict(
        assigner=dict(center_radius=3.5),
    ),
    test_cfg=dict(
        score_thr=0.001,
        nms=dict(type="nms", iou_threshold=0.65),
        max_per_img=300,
    ),
    # BatchSyncRandomResize disabled — all images are the same size and
    # small objects benefit from training at fixed resolution (960).
    data_preprocessor=dict(batch_augments=[]),
)

# ------------------------------------------------------------------
# Visualizer – local only.  MLflow is handled entirely by
# MLflowHook (custom_hooks) to avoid duplicate metrics/sessions
# and the MLflowVisBackend add_image extension-less name crash.
# ------------------------------------------------------------------
visualizer = dict(
    type="DetLocalVisualizer",
    vis_backends=[
        dict(type="LocalVisBackend"),
    ],
    name="visualizer",
)

# -------------------------
# Default hooks (KEEP LOGGER)
# -------------------------
default_hooks = dict(
    checkpoint=dict(
        type="CheckpointHook",
        interval=1,
        max_keep_ckpts=3,
        save_best="coco/bbox_mAP",
        rule="greater",
    ),
    logger=dict(type="LoggerHook", interval=LOG_INTERVAL),
    visualization=dict(
        type="DetVisualizationHook",
        draw=True,
        interval=VIS_INTERVAL,
        score_thr=0.3,
    ),
)


# ------------------------------------------------------------------
# Custom hooks – lists fully replace the base list; include all
# YOLOX-required hooks plus the unified MLflow hook.
#
# Changes vs V1:
#   - EMA momentum: 0.0002 → 0.0001 (smoother averaging over
#     training; less noisy weight updates)
# ------------------------------------------------------------------
custom_hooks = [
    dict(type="YOLOXModeSwitchHook", num_last_epochs=NUM_LAST_EPOCHS, priority=48),
    dict(type="SyncNormHook", priority=48),
    dict(
        type="EMAHook",
        ema_type="ExpMomentumEMA",
        momentum=0.0001,
        update_buffers=True,
        priority=49,
    ),
    # Unified MLflow hook: run lifecycle, params, config artifacts,
    # training scalars, organised val/test metrics + F1, system metrics,
    # annotation MD5, and work-dir artifact upload.
    dict(
        type="MLflowHook",
        experiment_name=EXPERIMENT_NAME,
        log_interval=LOG_INTERVAL,
        artifact_suffix=(".json", ".log", ".py", ".yaml", ".pth"),
        train_ann_file=_TRAIN_ANN,
        val_ann_file=_VAL_ANN,
    ),
]
