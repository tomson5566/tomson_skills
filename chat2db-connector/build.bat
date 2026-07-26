@echo off
REM ==========================================================
REM   Chat2DB Connector - Build Script
REM
REM   Important: builds inside a local .venv to avoid miniconda
REM   / system Python path issues with cryptography's bundled
REM   OpenSSL. Do NOT run PyInstaller from your global Python.
REM
REM   Usage: double-click this file.
REM ==========================================================

setlocal
cd /d "%~dp0"

set VENV_DIR=%~dp0.venv
set VENV_PY=%VENV_DIR%\Scripts\python.exe

echo [1/6] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo [X] Python not found. Install Python 3.9+ from https://www.python.org/downloads/
    echo     IMPORTANT: check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
python --version

echo [2/6] Preparing build venv at %VENV_DIR%...
if not exist "%VENV_PY%" (
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [X] venv creation failed
        pause
        exit /b 1
    )
)

echo [3/6] Upgrading pip in venv...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [X] pip upgrade failed
    pause
    exit /b 1
)

echo [4/6] Installing dependencies in venv (this may take a few minutes)...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [X] Dependency installation failed
    pause
    exit /b 1
)

echo [5/6] Cleaning old artifacts...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist "Chat2DBConnector.spec" del /q "Chat2DBConnector.spec"

echo [6/6] Building with PyInstaller (from venv)...
"%VENV_PY%" -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "Chat2DBConnector" ^
    --collect-all=paramiko ^
    --collect-all=PySide6 ^
    chat2db-connector.py

if errorlevel 1 (
    echo [X] Build failed
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo   Build complete!
echo   Output: %cd%\dist\Chat2DBConnector.exe
echo   Double-click to run. No Python install needed on target.
echo ==========================================================
echo.
pause
endlocal
