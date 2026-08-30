# Autopoiesis Engine Uninstaller (Windows PowerShell)
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

Write-Host "=== Autopoiesis Engine Uninstaller (Windows) ===" -ForegroundColor Yellow

Write-Host "Stopping any running autopoiesis daemon processes..." -ForegroundColor Yellow
Get-Process -Name "autopoiesis" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Uninstalling autopoiesis-engine package..." -ForegroundColor Yellow
python -m pip uninstall -y autopoiesis-engine
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv tool uninstall autopoiesis-engine
}

Write-Host "Purging runtime state and legacy workspace files (.autopoiesis, registry, mcp.json)..." -ForegroundColor Yellow
if (Test-Path ".autopoiesis") { Remove-Item -Recurse -Force ".autopoiesis" }
if (Test-Path "registry") { Remove-Item -Recurse -Force "registry" }
if (Test-Path "mcp.json") { Remove-Item -Force "mcp.json" }
if (Test-Path ".cursorrules") { Remove-Item -Force ".cursorrules" }

Write-Host "Uninstallation and workspace cleanup complete!" -ForegroundColor Green
