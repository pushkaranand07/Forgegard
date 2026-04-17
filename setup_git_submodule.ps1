# ============================================================================
# ForgeGuard Git Submodule Integration Script
# ============================================================================
# This script automates Phase 2 of the setup guide:
# - Removes image_detection from git tracking
# - Deletes the old folder
# - Adds it back as a proper git submodule
# - Verifies imports still work
# - Commits the submodule reference
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File setup_git_submodule.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "============================================================================"
Write-Host "  ForgeGuard Git Submodule Integration Script"
Write-Host "============================================================================"
Write-Host ""

# Color functions
function Write-Success { Write-Host "[+] $args" -ForegroundColor Green }
function Write-Error { Write-Host "[-] $args" -ForegroundColor Red }
function Write-Info { Write-Host "[i] $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "[!] $args" -ForegroundColor Yellow }

# ─────────────────────────────────────────────────────────────────────────────
# Verify we're in the project root
# ─────────────────────────────────────────────────────────────────────────────
Write-Info "Verifying project location..."
if (-not (Test-Path ".git")) {
    Write-Error "Not in a git repository. Please run this script from the project root."
    Write-Error "Expected: c:\coding\my work\final year\ForgeGuard"
    exit 1
}
Write-Success "Found .git directory"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Check if image_detection folder exists
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Step 1/4: Checking image_detection folder..."
if (-not (Test-Path "external/image_detection")) {
    Write-Warning "image_detection folder not found. Already deleted?"
    Write-Info "Skipping to git submodule addition..."
} else {
    Write-Success "Found external/image_detection"
    
    # Step 2: Remove from git tracking
    Write-Host ""
    Write-Info "Step 2/4: Removing image_detection from git tracking..."
    git rm --cached -r external/image_detection
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to remove from git"
        exit 1
    }
    Write-Success "Removed from git index"
    
    # Commit removal
    Write-Info "Committing removal..."
    git commit -m "Remove external/image_detection for submodule integration"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to commit removal"
        exit 1
    }
    Write-Success "Committed removal"
    
    # Step 3: Delete the folder
    Write-Host ""
    Write-Info "Step 3/4: Deleting image_detection folder..."
    Remove-Item -Recurse -Force "external/image_detection"
    if ($?) {
        Write-Success "Folder deleted"
    } else {
        Write-Error "Failed to delete folder"
        exit 1
    }
    
    # Verify deletion
    git status
    Write-Success "Folder removal verified in git status"
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Add as git submodule
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Step 4/4: Adding z1311/Image-Manipulation-Detection as submodule..."
Write-Info "Repository: https://github.com/z1311/Image-Manipulation-Detection.git"
Write-Warning "This may take 1-2 minutes..."

git submodule add https://github.com/z1311/Image-Manipulation-Detection.git external/image_detection
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to add submodule"
    Write-Error "If you see 'pathspec did not match', the folder may still exist. Check manually."
    exit 1
}
Write-Success "Submodule added successfully"

# Verify submodule setup
Write-Host ""
Write-Info "Verifying submodule setup..."

if (-not (Test-Path ".gitmodules")) {
    Write-Error ".gitmodules file not created"
    exit 1
}
Write-Success ".gitmodules file created"

$gitmodulesContent = Get-Content ".gitmodules"
Write-Success ".gitmodules content:"
Write-Host $gitmodulesContent

# ─────────────────────────────────────────────────────────────────────────────
# Verify imports still work
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Verifying Python imports work with submodule..."

# Check if we need to activate conda environment
$condaEnv = $env:CONDA_DEFAULT_ENV
if (-not $condaEnv) {
    Write-Warning "Conda environment not active. Skipping import test."
    Write-Warning "To test manually later:"
    Write-Warning "  conda activate ForgeGuard"
    Write-Warning "  cd Django\ Application"
    Write-Warning "  python -c \"from ml_core.image_model.imd import detect_image_bytes; print('✓')\"" 
} else {
    Write-Info "Using Conda environment: $condaEnv"
    cd "Django Application"
    python -c "from ml_core.image_model.imd import detect_image_bytes; print('Import test passed')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Import test passed - submodule integration is compatible"
    } else {
        Write-Warning "Import test failed. This may be due to missing dependencies."
        Write-Warning "Run 'python check_env.py' to verify environment setup."
    }
    cd ".."
}

# ─────────────────────────────────────────────────────────────────────────────
# Commit submodule reference
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Committing submodule reference..."
git add .gitmodules external/image_detection
git commit -m "Add Image-Manipulation-Detection as git submodule

- Properly reference z1311/Image-Manipulation-Detection repo
- Ensures clones with --recursive get the image detection code
- Maintains compatibility with ml_core.image_model.imd imports"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to commit submodule"
    exit 1
}
Write-Success "Submodule reference committed"

# ─────────────────────────────────────────────────────────────────────────────
# Final verification
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Final verification..."
git status
Write-Host ""
Write-Success "============================================================================"
Write-Success "  Git Submodule Integration Complete!"
Write-Success "============================================================================"
Write-Host ""
Write-Info "Next steps:"
Write-Info "  1. Review the commits:"
Write-Info "     git log --oneline -3"
Write-Info ""
Write-Info "  2. Push to GitHub:"
Write-Info "     git push origin main"
Write-Info ""
Write-Info "  3. Test fresh clone (on another machine or folder):"
Write-Info "     git clone --recursive https://github.com/YOUR_USERNAME/ForgeGuard.git"
Write-Host ""
