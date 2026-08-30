# Autopoiesis Engine Automated Installer for Windows PowerShell
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "   Autopoiesis Engine Automated Windows Installer (PS)    " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

# 1. Check Execution Policy
$currentPolicy = Get-ExecutionPolicy -Scope Process
if ($currentPolicy -eq "Restricted" -or $currentPolicy -eq "Undefined") {
    Write-Host "Setting Process Execution Policy to RemoteSigned..." -ForegroundColor Yellow
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
}

# 2. Check Python installation
$pythonExecutable = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonExecutable) {
    Write-Host "[ERROR] Python is not installed or not added to system PATH." -ForegroundColor Red
    Write-Host "Please install Python >= 3.11 from https://www.python.org/ and check 'Add Python to PATH'." -ForegroundColor Yellow
    exit 1
}

$pyVersion = python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
Write-Host "[INFO] Detected Python version: $pyVersion" -ForegroundColor Cyan

# 3. Create Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "[INFO] Creating virtual environment in '.venv'..." -ForegroundColor Yellow
    python -m venv .venv
}

# 4. Locate and Activate Virtual Environment
$activatePs1 = ".\.venv\Scripts\Activate.ps1"
$venvPython = ".\.venv\Scripts\python.exe"

if (Test-Path $activatePs1) {
    Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Yellow
    & $activatePs1
} else {
    Write-Host "[WARNING] Activate.ps1 not found, using direct virtualenv python..." -ForegroundColor Yellow
}

# 5. Upgrade pip and install package locally
Write-Host "[INFO] Upgrading pip and installing autopoiesis-engine in editable mode..." -ForegroundColor Yellow
if (Test-Path $venvPython) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e ".[dev]"
} else {
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
}

# 6. Initialize Workspace and MCP Server Configs
Write-Host "[INFO] Initializing Autopoiesis workspace and IDE MCP configurations..." -ForegroundColor Yellow
$autopoiesisExe = ".\.venv\Scripts\autopoiesis.exe"
if (Test-Path $autopoiesisExe) {
    & $autopoiesisExe init
} else {
    autopoiesis init
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "          Installation & Setup Completed Successfully!    " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "To activate the virtual environment in PowerShell:" -ForegroundColor White
Write-Host "  .\.venv\Scripts\Activate.ps1`n" -ForegroundColor Cyan
Write-Host "To start the MCP Server Daemon in stdio mode (for Claude Desktop / Cursor / VS Code / Kilocode):" -ForegroundColor White
Write-Host "  autopoiesis serve --mode stdio`n" -ForegroundColor Cyan
Write-Host "To start the MCP Server Daemon in HTTP mode:" -ForegroundColor White
Write-Host "  autopoiesis serve --mode http --host 127.0.0.1 --port 8000`n" -ForegroundColor Cyan
