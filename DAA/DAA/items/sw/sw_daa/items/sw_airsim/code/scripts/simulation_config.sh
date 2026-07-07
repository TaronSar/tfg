#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY_SCRIPT="$SCRIPT_DIR/apply_simulation_config.py"
SAVE_SCRIPT="$SCRIPT_DIR/save_simulation_config.py"

usage() {
    cat <<'EOF'
Usage:
  ./simulation_config.sh apply <simulation_name>
  ./simulation_config.sh save  <simulation_name>

Examples:
  ./simulation_config.sh apply simulation1
  ./simulation_config.sh save  simulation1
EOF
}

if [[ $# -ne 2 ]]; then
    usage
    exit 1
fi

ACTION="$1"
SIMULATION_NAME="$2"

if [[ "$ACTION" != "apply" && "$ACTION" != "save" ]]; then
    echo "Error: invalid action '$ACTION'. Use 'apply' or 'save'." >&2
    usage
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found in PATH." >&2
    exit 1
fi

case "$ACTION" in
    apply)
        if [[ ! -f "$APPLY_SCRIPT" ]]; then
            echo "Error: missing script: $APPLY_SCRIPT" >&2
            exit 1
        fi
        exec python3 "$APPLY_SCRIPT" "$SIMULATION_NAME"
        ;;
    save)
        if [[ ! -f "$SAVE_SCRIPT" ]]; then
            echo "Error: missing script: $SAVE_SCRIPT" >&2
            exit 1
        fi
        exec python3 "$SAVE_SCRIPT" "$SIMULATION_NAME"
        ;;
esac
