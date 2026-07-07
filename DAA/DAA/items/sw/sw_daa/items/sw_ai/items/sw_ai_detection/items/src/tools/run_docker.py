import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values
from loguru import logger

_EDGEAI_ROOT = "/workspace/edgeai-tensorlab/edgeai-mmdetection"
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
_PROJECT_MOUNT = "/workspace/sw_ai_detection"
_DOCKER_IMAGE = "edgeai-tensorlab-tidl:r11.1"


def _load_dotenv() -> dict[str, str | None]:
    """Load ``.env`` from project root."""
    env_file = _PROJECT_ROOT / ".env"
    return dotenv_values(env_file) if env_file.is_file() else {}


def _nas_path() -> str:
    """Resolve NAS mount path from env or ``.env`` file."""
    dotenv = _load_dotenv()
    path = os.environ.get("LOCAL_NAS_PATH") or dotenv.get("LOCAL_NAS_PATH")
    if not path:
        raise RuntimeError("LOCAL_NAS_PATH not set in environment or .env file")
    return path


def _mlflow_uri() -> str:
    """Resolve the MLflow tracking URI from env or ``.env`` file."""
    dotenv = _load_dotenv()
    return (
        os.environ.get("MLFLOW_TRACKING_URI")
        or dotenv.get("MLFLOW_TRACKING_URI")
        or "http://localhost:5000"
    )


def _base_docker_cmd() -> list[str]:
    """Build the common ``docker run`` prefix (mounts, env, flags)."""
    nas = _nas_path()

    return [
        "docker",
        "run",
        "--rm",
        "--gpus",
        "all",
        "--network",
        "host",
        "--ipc=host",
        "-v",
        f"{_PROJECT_ROOT}:{_PROJECT_MOUNT}",
        "-v",
        f"{nas}:{nas}:ro",
        "-e",
        f"PYTHONPATH={_PROJECT_MOUNT}/src/train",
        "-e",
        f"MLFLOW_TRACKING_URI={_mlflow_uri()}",
        "-e",
        "MLFLOW_ENABLE_AUTOLOGGING=false",
        "-e",
        "DEBIAN_FRONTEND=noninteractive",
    ]


def _run_train(args: argparse.Namespace) -> None:
    """Launch a YOLOX training run inside Docker."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = f"{Path(args.config).stem}_{timestamp}"
    work_dir = f"{_PROJECT_MOUNT}/experiments/{run_dir}"
    (_PROJECT_ROOT / "experiments" / run_dir).mkdir(parents=True, exist_ok=True)

    cmd = [
        *_base_docker_cmd(),
        "-e",
        f"MLFLOW_RUN_NAME={run_dir}",
        "--detach",
        _DOCKER_IMAGE,
        "python",
        f"{_EDGEAI_ROOT}/tools/train.py",
        f"{_PROJECT_MOUNT}/{args.config}",
        "--work-dir",
        work_dir,
        "--quantization",
        str(args.quantization),
    ]

    logger.info(f"Config:   {args.config}")
    logger.info(f"Work dir: experiments/{run_dir}")
    logger.info("  " + " ".join(cmd))

    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)


def _run_test(args: argparse.Namespace) -> None:
    """Run YOLOX inference inside Docker and dump predictions."""
    if args.output_dir:
        out_path = _PROJECT_ROOT / args.output_dir
    else:
        out_path = (_PROJECT_ROOT / args.checkpoint).parent
    out_path.mkdir(parents=True, exist_ok=True)

    prefix = args.output_prefix or "predictions"
    outfile_prefix = f"{_PROJECT_MOUNT}/{out_path.relative_to(_PROJECT_ROOT)}/{prefix}"

    cmd = [
        *_base_docker_cmd(),
        _DOCKER_IMAGE,
        "python",
        f"{_EDGEAI_ROOT}/tools/test.py",
        f"{_PROJECT_MOUNT}/{args.config}",
        f"{_PROJECT_MOUNT}/{args.checkpoint}",
        "--cfg-options",
        f"test_evaluator.outfile_prefix={outfile_prefix}",
        "--cfg-options",
        "default_hooks.visualization.draw=False",
        "--quantization",
        str(args.quantization),
    ]

    if args.ann_file:
        ann_path = f"{_PROJECT_MOUNT}/{args.ann_file}"
        cmd.extend(
            [
                "--cfg-options",
                f"test_dataloader.dataset.ann_file={ann_path}",
                "--cfg-options",
                f"test_evaluator.ann_file={ann_path}",
            ]
        )

    logger.info(f"Config:     {args.config}")
    logger.info(f"Checkpoint: {args.checkpoint}")
    logger.info(f"Output:     {out_path}/{prefix}.bbox.json")
    logger.info("  " + " ".join(cmd))

    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run YOLOX training or testing inside Docker",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    train_p = sub.add_parser("train", help="Launch a training run")
    train_p.add_argument(
        "--config",
        required=True,
        help="MMEngine experiment config (.py), relative to CWD",
    )
    train_p.add_argument(
        "--quantization",
        type=int,
        default=1,
        help="Quantization-Aware Training level (0=off, 1=QAT). Forwarded to edgeai train.py.",
    )

    test_p = sub.add_parser("test", help="Run inference and dump predictions")
    test_p.add_argument(
        "--config",
        required=True,
        help="MMEngine experiment config (.py), relative to CWD",
    )
    test_p.add_argument(
        "--checkpoint",
        required=True,
        help="Path to the .pth checkpoint, relative to CWD",
    )
    test_p.add_argument(
        "--output-dir",
        default=None,
        help="Directory for the output JSON (default: checkpoint's directory)",
    )
    test_p.add_argument(
        "--output-prefix",
        default=None,
        help="Prefix for the output predictions file (default: predictions). "
        "MMDetection appends .bbox.json automatically.",
    )
    test_p.add_argument(
        "--ann-file",
        default=None,
        help="Override the annotation file used by test_dataloader and test_evaluator. "
        "Allows running inference on train or eval splits instead of the default test split.",
    )
    test_p.add_argument(
        "--quantization",
        type=int,
        default=1,
        help="Quantization level for inference (0=FP32, 1=QAT). Should match training setting.",
    )

    args = parser.parse_args()

    if args.command == "train":
        _run_train(args)
    else:
        _run_test(args)


if __name__ == "__main__":
    main()
