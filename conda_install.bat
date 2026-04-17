@echo off
REM ============================================================
REM  ForgeGuard — CUDA-enabled PyTorch install (Conda)
REM  Run this ONCE after creating the ForgeGuard conda env.
REM
REM  Installs PyTorch with CUDA 12.1 support.
REM  Change pytorch-cuda=12.1 to match your driver:
REM    CUDA 11.8  →  pytorch-cuda=11.8
REM    CUDA 12.1  →  pytorch-cuda=12.1
REM    CUDA 12.4  →  pytorch-cuda=12.4
REM ============================================================

echo [ForgeGuard] Activating conda environment...
call conda activate ForgeGuard

echo.
echo [ForgeGuard] Checking current CUDA availability...
python -c "import torch; print('Current torch:', torch.__version__, '| CUDA:', torch.cuda.is_available())"

echo.
echo [ForgeGuard] Installing CUDA-enabled PyTorch (CUDA 12.1)...
echo    This may take several minutes on first run.
echo.

conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia -y

echo.
echo [ForgeGuard] Verifying installation...
python -c "import torch; import torchvision; print('torch:', torch.__version__); print('torchvision:', torchvision.__version__); print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"

echo.
echo [ForgeGuard] Installing additional ML packages...
pip install huggingface_hub datasets tqdm pyarrow --quiet

echo.
echo [ForgeGuard] Done. Run check_env.py to verify everything.
pause
