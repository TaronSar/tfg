#!/bin/bash
ORIGINAL_DIR="$PWD"

# Create vpgen user settings if not present
VPGEN_SETTINGS="$HOME/.vpgen/settings.json"
if [ ! -f "$VPGEN_SETTINGS" ]; then
    mkdir -p "$HOME/.vpgen"
    echo '{"ticcs_path": ""}' > "$VPGEN_SETTINGS"
fi

cd /home/vscode/Vlibs/vpgen2
python3 vpgen.py --p /workspaces/daa/sw/sw_daa_SIL/code/vpgen/projects.json --g cmake
cd "$ORIGINAL_DIR"