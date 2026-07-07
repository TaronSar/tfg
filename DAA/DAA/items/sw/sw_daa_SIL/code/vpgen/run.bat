@echo off
set "ORIGINAL_DIR=%CD%"
cd ../../../sw_daa/items/_sw_perception/items/Vlibs/vpgen2
python vpgen.py --p ../../../../../../sw_daa_SIL/code/vpgen/projects.json --g cmake
cd /d "%ORIGINAL_DIR%"