#!/bin/bash
# Wrapper: delegates to the shared run.sh in _sw_perception, passing the product name, in lowercase.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

PRODUCT="$(basename "$REPO_ROOT" | tr '[:upper:]' '[:lower:]')"

exec "$REPO_ROOT/items/_sw_perception/code/project/docker-cross-jetson-22-04/run.sh" "$PRODUCT"