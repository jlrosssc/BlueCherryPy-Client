@echo off
setlocal enabledelayedexpansion
title BluecherryPy Client — Windows Installer

echo === BluecherryPy Client - Windows installer ===
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Download and install Python 3.11 or later from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

:: Check Python version is 3.11+
python -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.11 or later is required.
    python --version
    pause
    exit /b 1
)

:: Clone if not already in the repo directory
if not exist "main.py" (
    git --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Git not found. Install from https://git-scm.com/download/win
        pause
        exit /b 1
    )
    git clone https://github.com/jlrosssc/BlueCherryPy-Client.git
    cd BlueCherryPy-Client
)

:: Create virtual environment
echo Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

:: Activate and install
echo Installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. See output above.
    pause
    exit /b 1
)

:: Create a launch shortcut batch file
echo @echo off > BluecherryPy.bat
echo cd /d "%%~dp0" >> BluecherryPy.bat
echo .venv\Scripts\python.exe main.py >> BluecherryPy.bat

echo.
echo === Install complete ===
echo To run: double-click BluecherryPy.bat
echo Or from this terminal: .venv\Scripts\python.exe main.py
echo.

set /p LAUNCH="Launch now? [Y/n] "
if /i not "%LAUNCH%"=="n" (
    python main.py
)
