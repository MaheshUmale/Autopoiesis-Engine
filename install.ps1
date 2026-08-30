# Autopoiesis Engine Automated Installer (Windows PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "=== Autopoiesis Engine Automated Installer (Windows) ===" -ForegroundColor Green

# Check Python installation
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python was not found in PATH. Please install Python >= 3.11."
    exit 1
}

$pyVersion = python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
Write-Host "Detected Python version: $pyVersion" -ForegroundColor Cyan

# Create Virtual Environment if not existing
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment in .venv..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
$ActivateScript = ".\.venv\Scripts\Activate.ps1"

if (Test-Path $ActivateScript) {
    & $ActivateScript
} else {
    Write-Error "Could not find virtual environment activation script at $ActivateScript"
    exit 1
}

Write-Host "Upgrading pip and installing autopoiesis-engine locally..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -e ".[dev]"

Write-Host "Initializing Autopoiesis workspace & MCP config..." -ForegroundColor Yellow
autopoiesis init

Write-Host "`n=== Installation & Setup Complete! ===" -ForegroundColor Green
Write-Host "To activate your virtual environment in future PowerShell sessions, run:"
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the MCP server daemon in stdio mode for IDEs (Claude / Cursor / VS Code):"
Write-Host "  autopoiesis serve --mode stdio" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the MCP daemon in HTTP server mode:"
Write-Host "  autopoiesis serve --mode http --host 127.0.0.1 --port 8000" -ForegroundColor Cyan
