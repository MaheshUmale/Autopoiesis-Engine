# Autopoiesis Engine Automated Reinstaller (Windows PowerShell)
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "=== Autopoiesis Engine Reinstaller (Windows) ===" -ForegroundColor Green

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force

if (Test-Path ".\uninstall.ps1") {
    & ".\uninstall.ps1"
}

if (Test-Path ".\install.ps1") {
    & ".\install.ps1"
}

Write-Host "`n=== Reinstallation Completed Successfully! ===" -ForegroundColor Green
