@echo off
cd /d "%~dp0"

echo Starting PDF Compressor...

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo Creating Python virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Error: Failed to create virtual environment. Ensure Python is installed and in your PATH.
        pause
        exit /b 1
    )
)

REM Activate venv
call "venv\Scripts\activate.bat"

REM Install requirements if needed
echo Checking dependencies...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies.
    pause
    exit /b 1
)

REM Run the app
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)
