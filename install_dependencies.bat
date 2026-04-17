@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================================================
echo  ForgeGuard - Environment Setup (Direct Batch Method)
echo ============================================================================
echo.

REM Activate the ForgeGuard environment
echo [STEP 1] Activating Conda environment...
call conda activate ForgeGuard
if errorlevel 1 (
    echo ERROR: Failed to activate ForgeGuard environment
    pause
    exit /b 1
)
echo [OK] Environment activated

REM Verify Python 3.10
echo.
echo [STEP 2] Verifying Python 3.10...
python --version
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)
echo [OK] Python verified

REM Install PyTorch with CUDA 12.1
echo.
echo [STEP 3] Installing PyTorch with CUDA 12.1 support...
echo This may take 10-15 minutes...
conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia -y
if errorlevel 1 (
    echo WARNING: CUDA 12.1 installation failed, trying CUDA 11.8...
    conda install pytorch torchvision pytorch-cuda=11.8 -c pytorch -c nvidia -y
    if errorlevel 1 (
        echo WARNING: CUDA 11.8 failed, installing CPU-only version...
        conda install pytorch torchvision cpuonly -c pytorch -y
        if errorlevel 1 (
            echo ERROR: PyTorch installation failed completely
            pause
            exit /b 1
        )
    )
)
echo [OK] PyTorch installed

REM Install dlib
echo.
echo [STEP 4] Installing dlib...
echo This may take 10+ minutes...
conda install -c conda-forge dlib -y
if errorlevel 1 (
    echo ERROR: dlib installation failed
    pause
    exit /b 1
)
echo [OK] dlib installed

REM Install requirements
echo.
echo [STEP 5] Installing remaining dependencies...
cd "Django Application"
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install requirements failed
    cd ..
    pause
    exit /b 1
)
echo [OK] All requirements installed
cd ..

REM Create .env file
echo.
echo [STEP 6] Creating .env file...
if exist ".env" (
    echo WARNING: .env already exists (skipped)
) else (
    copy ".env.example" ".env"
    if errorlevel 1 (
        echo ERROR: Failed to create .env
        pause
        exit /b 1
    )
    echo [OK] .env created from template
)

REM Run health check
echo.
echo [STEP 7] Running environment health check...
python check_env.py
if errorlevel 1 (
    echo WARNING: Health check encountered issues (see above)
) else (
    echo [OK] Health check passed
)

REM Success
echo.
echo ============================================================================
echo  Setup Complete!
echo ============================================================================
echo.
echo Next steps:
echo   1. Keep this environment activated (conda activate ForgeGuard)
echo   2. Run the server:
echo      cd "Django Application"
echo      python manage.py runserver
echo.
echo   3. Open http://127.0.0.1:8000 in your browser
echo.
echo ============================================================================
pause
