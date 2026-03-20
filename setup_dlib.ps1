# Setup script for installing dlib and completing project setup
# This script will attempt to install Visual Studio Build Tools and dlib

Write-Host "=== Deepfake Detection Project Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if dlib is already installed
Write-Host "Checking if dlib is installed..." -ForegroundColor Yellow
$dlibInstalled = python -c "import dlib; print('installed')" 2>$null

if ($dlibInstalled -eq "installed") {
    Write-Host "dlib is already installed!" -ForegroundColor Green
    exit 0
}

Write-Host "dlib is not installed. Checking for Visual Studio Build Tools..." -ForegroundColor Yellow

# Check if Visual Studio Build Tools are installed
$vsBuildTools = Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" | Where-Object { $_.DisplayName -like "*Visual Studio*Build Tools*" -or $_.DisplayName -like "*Microsoft Visual C++*" }

if (-not $vsBuildTools) {
    Write-Host ""
    Write-Host "Visual Studio Build Tools not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "To install dlib, you need Visual Studio Build Tools." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Option 1: Install via winget (requires admin):" -ForegroundColor Cyan
    Write-Host "  winget install Microsoft.VisualStudio.2022.BuildTools --silent --override `"--wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended`"" -ForegroundColor White
    Write-Host ""
    Write-Host "Option 2: Download and install manually:" -ForegroundColor Cyan
    Write-Host "  1. Visit: https://visualstudio.microsoft.com/downloads/" -ForegroundColor White
    Write-Host "  2. Download 'Build Tools for Visual Studio 2022'" -ForegroundColor White
    Write-Host "  3. Run installer and select 'Desktop development with C++'" -ForegroundColor White
    Write-Host ""
    Write-Host "Option 3: Try installing dlib-binary (may work):" -ForegroundColor Cyan
    Write-Host "  pip install dlib-binary" -ForegroundColor White
    Write-Host ""
    
    $choice = Read-Host "Would you like to try installing via winget now? (Y/N)"
    if ($choice -eq "Y" -or $choice -eq "y") {
        Write-Host "Attempting to install Visual Studio Build Tools..." -ForegroundColor Yellow
        try {
            winget install Microsoft.VisualStudio.2022.BuildTools --silent --override "--wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
            Write-Host "Installation started. Please wait for it to complete, then run this script again." -ForegroundColor Green
        } catch {
            Write-Host "Failed to install via winget. Please install manually using Option 2." -ForegroundColor Red
        }
    }
} else {
    Write-Host "Visual Studio Build Tools found!" -ForegroundColor Green
    Write-Host "Attempting to install dlib..." -ForegroundColor Yellow
    pip install dlib==19.24.2
}

Write-Host ""
Write-Host "Setup script completed!" -ForegroundColor Green
