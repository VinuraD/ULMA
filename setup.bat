@echo off
setlocal

set "ENV_NAME=ulma"
set "SCRIPT_DIR=%~dp0"
set "REQ_FILE=%SCRIPT_DIR%requirements.txt"

rem --- Locate conda ---
if not defined CONDA_EXE (
    for %%I in (conda.exe) do set "CONDA_EXE=%%~$PATH:I"
)
if not defined CONDA_EXE (
    echo [ERROR] conda.exe not found on PATH. Please install Miniconda/Anaconda and reopen your shell.
    exit /b 1
)
for %%I in ("%CONDA_EXE%") do set "CONDA_ROOT=%%~dpI.."

rem --- Initialize conda in this shell ---
call "%CONDA_ROOT%\Scripts\activate.bat" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to initialize conda from "%CONDA_ROOT%".
    exit /b 1
)

rem --- Create env if missing ---
conda env list | findstr /C:" %ENV_NAME% " >nul
if %errorlevel%==0 (
    echo Conda environment "%ENV_NAME%" already exists.
) else (
    echo Creating environment "%ENV_NAME%"...
    call conda create -y -n "%ENV_NAME%" python=3.11 || exit /b 1
)

rem --- Activate and install ---
call conda activate "%ENV_NAME%" || exit /b 1
python -m pip install --upgrade pip || exit /b 1
python -m pip install -r "%REQ_FILE%" || exit /b 1

echo Environment "%ENV_NAME%" is ready!
