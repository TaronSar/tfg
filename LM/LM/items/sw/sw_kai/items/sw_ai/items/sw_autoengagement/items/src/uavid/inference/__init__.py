"""Deployment-side inference: enrollment, identification and the Verifier."""

from src.uavid.inference.enroll import enroll_gallery
from src.uavid.inference.identify import identify_paths
from src.uavid.inference.verifier import Verifier

__all__ = ["Verifier", "enroll_gallery", "identify_paths"]
