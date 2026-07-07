import hashlib
import math
import os

import mlflow
from mmengine.hooks import Hook  # type: ignore[reportMissingImports]
from mmengine.registry import HOOKS  # type: ignore[reportMissingImports]

KEYS_TO_SKIP = {"data_time", "iter", "epoch", "time", "base_lr"}


@HOOKS.register_module()
class MLflowHook(Hook):
    """Unified MLflow hook for experiment tracking.

    Manages the complete MLflow integration in a single hook, replacing
    the combination of ``MLflowVisBackend`` + separate logging hooks
    that caused duplicate metrics and sessions.

    Features:
        - MLflow run lifecycle (start / end)
        - System metrics (CPU, GPU, memory)
        - Flattened config as MLflow params
        - Source and merged config as artifacts
        - Annotation-file MD5 hashes (DVC-compatible) as params
        - Training scalars (loss, lr, …) at configurable interval
        - Organised val/test metrics with computed F1
        - Work-dir artifact upload on completion (configs, logs,
          checkpoints matching ``artifact_suffix``)

    Args:
        tracking_uri: MLflow tracking server URI.  Overridden by
            ``MLFLOW_TRACKING_URI`` env var.
        experiment_name: MLflow experiment name.  Overridden by
            ``MLFLOW_EXPERIMENT_NAME`` env var.
        run_name: MLflow run name.  Defaults to the ``work_dir``
            basename.  Overridden by ``MLFLOW_RUN_NAME`` env var.
        log_interval: Log training scalars every *n* iterations.
        artifact_suffix: File extensions uploaded from ``work_dir``
            when the run finishes.
        train_ann_file: Training annotation JSON path (MD5 logged).
        val_ann_file: Validation annotation JSON path (MD5 logged).
    """

    def __init__(
        self,
        tracking_uri: str = "http://localhost:5000",
        experiment_name: str = "mmdet_training",
        run_name: str | None = None,
        log_interval: int = 50,
        artifact_suffix: tuple[str, ...] = (".json", ".log", ".py", ".yaml", ".pth"),
        train_ann_file: str | None = None,
        val_ann_file: str | None = None,
    ) -> None:
        self.tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", tracking_uri)
        self.experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", experiment_name)
        self.run_name = os.environ.get("MLFLOW_RUN_NAME", run_name)
        self.log_interval = log_interval
        self.artifact_suffix = artifact_suffix
        self.train_ann_file = train_ann_file
        self.val_ann_file = val_ann_file

        self._is_master = True
        self._active = False

    def _is_main_process(self, runner):
        """Return True if running on rank 0."""
        return runner.rank == 0

    @staticmethod
    def _dvc_md5(path: str) -> str:
        """Compute MD5 hex digest of *path* (DVC-compatible, 1 MiB chunks)."""
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(2**20), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _flatten_dict(d, parent_key="", sep="."):
        """Recursively flatten a nested dict using dot-separated keys."""
        items = []
        for k, v in d.items():
            key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(MLflowHook._flatten_dict(v, key, sep).items())
            else:
                items.append((key, v))
        return dict(items)

    def _safe_log_artifact(self, path, artifact_path, runner):
        """Log an artifact to MLflow, warning on failure instead of raising."""
        try:
            mlflow.log_artifact(path, artifact_path=artifact_path)
        except Exception as e:
            runner.logger.warning(f"MLflow artifact upload failed ({path}): {e}")

    @staticmethod
    def _sanitize(val):
        """Convert a value to float, replacing NaN/Inf with 0.0."""
        v = float(val)
        return 0.0 if (math.isnan(v) or math.isinf(v)) else v

    def before_run(self, runner):
        """Set up MLflow tracking URI and experiment on rank 0."""
        self._is_master = self._is_main_process(runner)
        if not self._is_master:
            return

        mlflow.autolog(disable=True)

        if self.tracking_uri:
            mlflow.set_tracking_uri(self.tracking_uri)
        if self.experiment_name:
            mlflow.set_experiment(self.experiment_name)

    def after_run(self, runner):
        """Safety net: end any run left open by a crash during training."""
        if not self._is_master:
            return
        if self._active:
            mlflow.end_run()
            self._active = False

    def before_train(self, runner):
        """Start an MLflow run and log config, params, and annotation hashes."""
        if not self._is_master:
            return
        if mlflow.active_run() is not None:
            mlflow.end_run()

        run_name = self.run_name or os.path.basename(runner.work_dir)
        mlflow.start_run(run_name=run_name)
        self._active = True

        # Source config artifact
        cfg_file = getattr(runner.cfg, "filename", None)
        if cfg_file and os.path.isfile(cfg_file):
            self._safe_log_artifact(cfg_file, "config", runner)

        # Merged config artifact
        try:
            merged = os.path.join(runner.work_dir, "full_config.py")
            runner.cfg.dump(merged)
            self._safe_log_artifact(merged, "config", runner)
        except Exception as e:
            runner.logger.warning(f"MLflow config dump failed: {e}")

        # Flattened hyperparams
        try:
            flat = self._flatten_dict(runner.cfg.to_dict())
            clean = {k: str(v) for k, v in flat.items() if isinstance(v, (int, float, str, bool))}
            mlflow.log_params(clean)
        except Exception as e:
            runner.logger.warning(f"MLflow param logging failed: {e}")

        # Annotation MD5 hashes
        md5 = {}
        if self.train_ann_file and os.path.isfile(self.train_ann_file):
            md5["train_ann_md5"] = self._dvc_md5(self.train_ann_file)
        if self.val_ann_file and os.path.isfile(self.val_ann_file):
            md5["val_ann_md5"] = self._dvc_md5(self.val_ann_file)
        if md5:
            try:
                mlflow.log_params(md5)
            except Exception as e:
                runner.logger.warning(f"MLflow MD5 logging failed: {e}")

    def after_train_iter(self, runner, batch_idx, data_batch=None, outputs=None):
        """Log training scalars to MLflow at the configured interval."""
        if not self._is_master or not self._active:
            return
        if not self.every_n_train_iters(runner, self.log_interval):
            return

        result = runner.log_processor.get_log_after_iter(runner, batch_idx, mode="train")
        if not result:
            return

        log_dict, _ = result
        try:
            mlflow.log_metrics(
                {
                    k: float(v)
                    for k, v in log_dict.items()
                    if isinstance(v, (int, float)) and k not in KEYS_TO_SKIP
                },
                step=runner.iter,
            )
        except Exception as e:
            runner.logger.warning(f"MLflow train metric logging failed: {e}")

    def after_train(self, runner):
        """Upload work-dir artifacts and close the MLflow run."""
        if not self._is_master or not self._active:
            return

        work_dir = runner.work_dir
        if os.path.isdir(work_dir):
            for fname in sorted(os.listdir(work_dir)):
                if fname.endswith(tuple(self.artifact_suffix)):
                    self._safe_log_artifact(os.path.join(work_dir, fname), "", runner)

        mlflow.end_run()
        self._active = False

    def _organize_metrics(self, metrics, prefix="val"):
        organized = {}
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                val = self._sanitize(v)
            elif isinstance(v, str) and v.lower() == "nan":
                val = 0.0
            else:
                continue
            clean = k.replace("coco/", "").replace("@", "_").replace("bbox_", "")
            if clean.startswith(("mAP", "AR", "F1")):
                organized[f"{prefix}/{clean}"] = val
            else:
                organized[f"{prefix}/per_class/{clean}"] = val
        return organized

    def _log_metrics(self, runner, metrics, prefix="val"):
        organized = self._organize_metrics(metrics, prefix=prefix)
        try:
            mlflow.log_metrics(organized, step=runner.epoch)
        except Exception as e:
            runner.logger.warning(f"MLflow {prefix} logging failed: {e}")

    def after_val_epoch(self, runner, metrics=None):
        """Log validation metrics to MLflow."""
        if not self._is_master or not self._active or not metrics:
            return
        self._log_metrics(runner, metrics, prefix="val")

    def after_test_epoch(self, runner, metrics=None):
        """Log test metrics to MLflow."""
        if not self._is_master or not self._active or not metrics:
            return
        self._log_metrics(runner, metrics, prefix="test")
