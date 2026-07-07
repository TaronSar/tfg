# edgeai-mmdetection YOLOX-tiny – airborne detection (BASE CONFIG).
#
# This file defines shared architecture overrides and
# everything experiment-specific: dataset paths, training
# schedule, optimiser LR, batch size, and MLflow run metadata.
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
MAX_EPOCHS = 40
NUM_LAST_EPOCHS = 5
VAL_INTERVAL = 2

# ------------------------------------------------------------------
# Paths (container-side)
# ------------------------------------------------------------------
_TRAIN_ANN = f"{_PROJECT_MOUNT}/data/06_split/train.json"
_VAL_ANN = f"{_PROJECT_MOUNT}/data/06_split/eval.json"
_TEST_ANN = f"{_PROJECT_MOUNT}/data/06_split/test.json"
_IMG_ROOT = f"{_NAS_MOUNT}/airborne-obj-detection-dataset/airborne_cropped_images/"

_CLASSES = ("airborne", "helicopter", "bird", "drone", "flock", "ufo", "airplane")
NUM_CLASSES = len(_CLASSES)
_METAINFO = dict(classes=_CLASSES)

_IMG_SCALE = (960, 960)  # (height, width)

# ------------------------------------------------------------------
# Lite model + Quantization-Aware Training (QAT)
# model_surgery=1: replaces SiLU→ReLU, Focus→FocusLite, etc. (from base).
# quantization=1 : wraps model in QuantTrainModule — INT8-aware training.
#   BN + observers train for first 50% of epochs, then freeze.
#   Produces TIDL-ready weights with minimal accuracy loss.
# ------------------------------------------------------------------
convert_to_lite_model = dict(model_surgery=1)

LOG_INTERVAL = 200
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
        # Override Mosaic + Resize so they use _IMG_SCALE.
        pipeline=[
            dict(type="Mosaic", img_scale=_IMG_SCALE, pad_val=114.0),
            dict(
                type="RandomAffine",
                scaling_ratio_range=(0.8, 1.5),
                border=(-_IMG_SCALE[0] // 2, -_IMG_SCALE[1] // 2),
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
#   small  <20²  = 400px²   (specks, far aircraft, birds)
#   medium <60²  = 3600px²  (nearby aircraft, drones)
#   large  >60²  = 3600px²+ (close-range, flocks)
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
# FIX: param_scheduler – base schedule targets 300 epochs; with 20 epochs
# the LR never decayed (cosine ran from epoch 5→285).  Now matched to 20.
# ------------------------------------------------------------------
param_scheduler = [
    dict(begin=0, end=3, by_epoch=True, convert_to_iter_based=True, type="mmdet.QuadraticWarmupLR"),
    dict(
        begin=3,
        end=MAX_EPOCHS - NUM_LAST_EPOCHS,
        T_max=MAX_EPOCHS - NUM_LAST_EPOCHS - 3,
        by_epoch=True,
        convert_to_iter_based=True,
        eta_min=0.00001,
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
# Pretrained weights — set to None to train from scratch.
# Use a COCO checkpoint to fine-tune; only matching layers are loaded.
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
    bbox_head=dict(num_classes=NUM_CLASSES),
    test_cfg=dict(
        score_thr=0.01,
        nms=dict(type="nms", iou_threshold=0.65),
        max_per_img=300,
    ),
    # BatchSyncRandomResize disabled — all images are the same size and
    # small objects benefit from training at fixed max resolution (1280).
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
# ------------------------------------------------------------------
custom_hooks = [
    dict(type="YOLOXModeSwitchHook", num_last_epochs=NUM_LAST_EPOCHS, priority=48),
    dict(type="SyncNormHook", priority=48),
    dict(
        type="EMAHook",
        ema_type="ExpMomentumEMA",
        momentum=0.0002,
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
