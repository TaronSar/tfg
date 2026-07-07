#!/usr/bin/env bash
# =============================================================================
# Create the project's NAS persistence directories and configure the shared
# DVC remote + cache. Run once per machine (Vision server / NAS server).
# Mirrors the sw_ai_detection setup so all Vision projects share conventions.
# =============================================================================
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$PROJECT_ROOT/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

NAS_PATH=${LOCAL_NAS_PATH:-/mnt/Pool_IA/IA_Dataset}
PROJECT_NAS="$NAS_PATH/datasets/uav-few-shot-identification"
DVC_REMOTE_DIR="$NAS_PATH/dvc-storage"
DVC_CACHE_DIR="$NAS_PATH/dvc-cache"

echo "Initializing uv project..."
cd "$PROJECT_ROOT"
uv sync

if [[ ! -d .dvc ]]; then
  echo "Initializing DVC..."
  uv run dvc init --subdir
fi

STORAGE_DIRS=(
  "$DVC_REMOTE_DIR"
  "$DVC_CACHE_DIR"
  "$PROJECT_NAS"
  "$PROJECT_NAS/uav_models"
  "$PROJECT_NAS/backgrounds"
  "$NAS_PATH/mlflow"
  "$NAS_PATH/fiftyone"
  "$NAS_PATH/mongodb"
  "$NAS_PATH/lancedb"
)

MISSING_DIRS=()
for dir in "${STORAGE_DIRS[@]}"; do
  if [[ ! -d "$dir" ]]; then
    MISSING_DIRS+=("$dir")
  fi
done

if [[ ${#MISSING_DIRS[@]} -gt 0 ]]; then
  echo "Creating missing storage directories..."
  sudo mkdir -p "${MISSING_DIRS[@]}"
  sudo chmod -R 777 "${MISSING_DIRS[@]}"
else
  echo "All storage directories already exist - skipping creation."
fi

echo "Configuring DVC..."
# Project level (committed to git) - shared across all devs.
uv run dvc remote add -d -f nas "$DVC_REMOTE_DIR"
uv run dvc config cache.dir "$DVC_CACHE_DIR"
uv run dvc config cache.type "symlink,hardlink"
uv run dvc config cache.shared group
uv run dvc config cache.protected true
uv run dvc config core.autostage false
uv run dvc config core.analytics false

echo "DVC setup complete."
