# Windows Installation & Uninstallation Guide

This guide provides the streamlined, single-source-of-truth installation instructions for Windows environments.

---

## Prerequisites

- **OS:** Windows 10 / 11
- **Python:** `>= 3.11` (Check 'Add Python to PATH' during installation)
- **PowerShell:** Default Windows PowerShell (`powershell.exe`) or PowerShell Core (`pwsh`)

---

## ⚡ 1-Click Automated Installation (Recommended)

Open PowerShell in your project folder and run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\install.ps1
```

---

## ⚡ Direct Installation via Git Repository

To install the package directly from GitHub into an existing Python environment:

```powershell
pip install git+https://github.com/autopoiesis/autopoiesis-engine.git
autopoiesis init
```

---

## 🔄 Reinstalling & Workspace Reset

If you modified directory structures or want to wipe local databases and re-install cleanly:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\reinstall.ps1
```

---

## 🗑️ Uninstallation

To remove the package and clean local workspace database files:

```powershell
.\uninstall.ps1
```

Or to purge workspace database state via CLI without removing the Python package:

```powershell
autopoiesis clean
```
