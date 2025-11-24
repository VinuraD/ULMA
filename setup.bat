@echo off

set ENV_NAME=ulma

rem --- Check if the conda environment already exists ---
conda env list | findstr /C:"%ENV_NAME%" >nul
if %errorlevel%==0 (
    echo Conda environment "%ENV_NAME%" already exists.
) else (
    echo Creating environment "%ENV_NAME%"...
    conda create -y -n %ENV_NAME% python=3.10
)

rem --- Activate the environment ---
call conda activate %ENV_NAME%

rem --- Install requirements ---
pip install -r requirements.txt

echo Environment "%ENV_NAME%" is ready!
