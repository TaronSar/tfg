@echo off
echo Creating Python virtual environment...
python -m venv .venv

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt
pip install --no-deps sw_trajectory_generator\package\cam_track_gen-0.1.0-py3-none-any.whl

echo Installing project (editable) for the daa_* packages...
pip install -e . --no-deps

echo.
echo Virtual environment ready. Activate it with:
echo   .venv\Scripts\activate.bat
