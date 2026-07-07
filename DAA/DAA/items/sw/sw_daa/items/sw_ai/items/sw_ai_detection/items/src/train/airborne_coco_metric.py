from unittest.mock import patch

import mmdet.evaluation.metrics.coco_metric as _coco_mod  # type: ignore[reportMissingImports]
from mmdet.evaluation.metrics import CocoMetric  # type: ignore[reportMissingImports]
from mmdet.registry import METRICS  # type: ignore[reportMissingImports]


@METRICS.register_module()
class AirborneCocoMetric(CocoMetric):
    """CocoMetric subclass with custom area-range thresholds.

    The base ``CocoMetric.compute_metrics`` creates ``COCOeval`` objects
    with pycocotools default area ranges (small <32², medium <96²).
    There is no parameter to override them.

    This subclass monkey-patches the ``COCOeval`` / ``COCOevalMP``
    constructors used by the base class so that custom area ranges are
    injected **before** ``evaluate()`` runs.  All other base-class logic
    (classwise table, ``metric_items`` validation, per-class AP, etc.)
    is preserved unchanged.

    Output keys are sanitised (``@`` → ``_``) so they are valid MLflow
    metric names.
    """

    def __init__(self, area_ranges=None, **kwargs):
        """Initialise with optional custom area ranges.

        Args:
            area_ranges: List of ``[min, max]`` area ranges for
                ``[small, medium, large]``. Uses COCO defaults when *None*.
            **kwargs: Forwarded to ``CocoMetric.__init__``.
        """
        super().__init__(**kwargs)
        # area_ranges: [[small_min, small_max], [med_min, med_max], [large_min, large_max]]
        # Default COCO: [[0, 1024], [1024, 9216], [9216, 1e10]]
        self.custom_area_ranges = area_ranges

    def compute_metrics(self, results):
        """Run base evaluation with custom area ranges, sanitise keys for MLflow."""
        if self.custom_area_ranges is not None:
            all_range = [0, 1e5**2]
            custom_ranges = [
                all_range,
                self.custom_area_ranges[0],
                self.custom_area_ranges[1],
                self.custom_area_ranges[2],
            ]
            custom_labels = ["all", "small", "medium", "large"]

            _OrigEval = _coco_mod.COCOeval
            _OrigEvalMP = _coco_mod.COCOevalMP

            class _PatchedEval(_OrigEval):
                def __init__(self, *a, **kw):
                    super().__init__(*a, **kw)
                    self.params.areaRng = custom_ranges
                    self.params.areaRngLbl = custom_labels

            class _PatchedEvalMP(_OrigEvalMP):
                def __init__(self, *a, **kw):
                    super().__init__(*a, **kw)
                    self.params.areaRng = custom_ranges
                    self.params.areaRngLbl = custom_labels

            with (
                patch.object(_coco_mod, "COCOeval", _PatchedEval),
                patch.object(_coco_mod, "COCOevalMP", _PatchedEvalMP),
            ):
                metrics = super().compute_metrics(results)
        else:
            metrics = super().compute_metrics(results)

        sanitized = {k.replace("@", "_"): v for k, v in metrics.items()}
        _DEFAULTS = (
            "bbox_mAP",
            "bbox_mAP_50",
            "bbox_mAP_75",
            "bbox_mAP_s",
            "bbox_mAP_m",
            "bbox_mAP_l",
            "bbox_AR_100",
            "bbox_AR_300",
            "bbox_AR_1000",
            "bbox_AR_s_1000",
            "bbox_AR_m_1000",
            "bbox_AR_l_1000",
        )
        for key in _DEFAULTS:
            sanitized.setdefault(key, 0.0)

        # Compute F1 from mAP and AR so it is available to all consumers
        # (log files, CheckpointHook save_best, MLflow, …).
        mAP = sanitized.get("bbox_mAP")
        ar = sanitized.get("bbox_AR_100")
        if mAP is not None and ar is not None and mAP + ar > 0:
            sanitized["bbox_F1"] = 2.0 * mAP * ar / (mAP + ar)
        else:
            sanitized["bbox_F1"] = 0.0

        return sanitized
