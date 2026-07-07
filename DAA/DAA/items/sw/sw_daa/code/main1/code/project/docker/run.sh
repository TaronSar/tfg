#!/bin/bash
# Wrapper: delegates to the shared run-x86.sh in _sw_perception
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

exec "$REPO_ROOT/items/_sw_perception/code/project/docker/run-x86.sh"
