"""Episodic prototypical training loop and the MLflow tracking hook."""

from src.uavid.train.trainer import run_episode, train_protonet, validate

__all__ = ["run_episode", "validate", "train_protonet"]
