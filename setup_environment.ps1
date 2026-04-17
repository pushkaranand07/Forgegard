# ============================================================================
# ForgeGuard Environment Setup Script
# ============================================================================
# This script automates Phase 1 of the setup guide:
# - Creates Conda environment for Python 3.10
# - Installs PyTorch with CUDA support
# - Installs dlib
# - Installs remaining dependencies
# - Creates .env file
# - Runs verification
#
# Usage: 
#   powershell -ExecutionPolicy Bypass -File setup_environment.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "============================================================================"
Write-Host "  ForgeGuard Environment Setup Script"
Write-Host "============================================================================"
Write-Host ""

# Color functions
function Write-Success { Write-Host "[+] $args" -ForegroundColor Green }
function Write-Error { Write-Host "[-] $args" -ForegroundColor Red }
function Write-Info { Write-Host "[i] $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "[!] $args" -ForegroundColor Yellow }

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Check Conda
# ─────────────────────────────────────────────────────────────────────────────
Write-Info "Step 1/5: Checking Conda installation..."
$condaVersion = conda --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Success "Conda found: $condaVersion"
} else {
    Write-Error "Conda not found. Please install Miniconda from:"
    Write-Error "  https://docs.conda.io/projects/miniconda/en/latest/"
    exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Create Conda environment
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Step 2/5: Creating Conda environment 'ForgeGuard' with Python 3.10..."
conda create -n ForgeGuard python=3.10 -y
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create Conda environment"
    exit 1
}
Write-Success "Conda environment created"

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Activate and install PyTorch
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Step 3/5: Activating environment and installing PyTorch..."
Write-Warning "This may take 5-10 minutes..."

# Activate conda environment
$activateScript = & conda shell.powershell hook
Invoke-Expression $activateScript
conda activate ForgeGuard

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to activate environment"
    exit 1
}
Write-Success "Environment activated"

# Install PyTorch with CUDA
Write-Info "Installing PyTorch with CUDA 12.1 support..."
conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia -y

if ($LASTEXITCODE -eq 0) {
    Write-Success "PyTorch installed with CUDA 12.1"
} else {
    Write-Warning "CUDA 12.1 installation failed, trying CUDA 11.8..."
    conda install pytorch torchvision pytorch-cuda=11.8 -c pytorch -c nvidia -y
    if ($LASTEXITCODE -eq 0) {
        Write-Success "PyTorch installed with CUDA 11.8"
    } else {
        Write-Warning "GPU installation failed, trying CPU-only version..."
        conda install pytorch torchvision cpuonly -c pytorch -y
        if ($LASTEXITCODE -ne 0) {
            Write-Error "PyTorch installation failed"
            exit 1
        }
        Write-Success "PyTorch installed (CPU-only mode)"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Install dlib and other dependencies
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Step 4/5: Installing dlib and remaining dependencies..."
Write-Warning "This may take 10+ minutes..."

conda install -c conda-forge dlib -y
if ($LASTEXITCODE -ne 0) {
    Write-Error "dlib installation failed"
    exit 1
}
Write-Success "dlib installed"

Write-Info "Installing requirements from requirements.txt..."
cd "Django Application"
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install requirements failed"
    cd ".."
    exit 1
}
Write-Success "All requirements installed"
cd ".."

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Create .env and verify
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Step 5/5: Creating .env file and verifying setup..."

if (Test-Path ".env") {
    Write-Warning ".env already exists (skipped)"
} else {
    Copy-Item ".env.example" ".env"
    if ($?) {
        Write-Success ".env file created from template"
    } else {
        Write-Error "Failed to create .env file"
        exit 1
    }
}

# Run health check
Write-Host ""
Write-Info "Running environment health check..."
python check_env.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Success "============================================================================"
    Write-Success "  Setup Complete! Environment is ready."
    Write-Success "============================================================================"
    Write-Host ""
    Write-Info "Next steps:"
    Write-Info "  1. Start the Django server:"
    Write-Info "     cd 'Django Application'"
    Write-Info "     python manage.py runserver"
    Write-Info ""
    Write-Info "  2. Open http://127.0.0.1:8000 in your browser"
    Write-Info ""
    Write-Warning "To activate the environment in future sessions:"
    Write-Warning "  conda activate ForgeGuard"
    Write-Host ""
} else {
    Write-Error "Health check failed. Review output above for errors."
    exit 1
}
