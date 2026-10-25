# Sikka and Smash Arcade - Complete Dependency & Environment Installer
# Checks for Python, installs Python 3.12 if missing, configures PATH,
# upgrades pip, installs pygame, and verifies all required components.

[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SIKKA AND SMASH ARCADE - ENVIRONMENT & DEPENDENCY SETUP   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

function Find-PythonExecutable {
    # 1. Check if python is already in the current PATH and is a working python (not a dead WindowsStore stub)
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $testVer = & $cmd.Source --version 2>$null
        if ($testVer -and ($cmd.Source -notlike "*WindowsApps*")) {
            return $cmd.Source
        }
    }

    # 2. Check Windows Registry for registered Python installations
    $regPaths = @(
        "HKLM:\SOFTWARE\Python\PythonCore\*\InstallPath",
        "HKCU:\SOFTWARE\Python\PythonCore\*\InstallPath",
        "HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore\*\InstallPath"
    )
    foreach ($reg in $regPaths) {
        $keys = Get-ItemProperty -Path $reg -ErrorAction SilentlyContinue
        foreach ($k in $keys) {
            $p = Join-Path $k.'(default)' "python.exe"
            if (Test-Path $p) {
                return $p
            }
        }
    }

    # 3. Check common installation directories
    $searchDirs = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python310\python.exe",
        "${env:ProgramFiles(x86)}\Python313\python.exe",
        "${env:ProgramFiles(x86)}\Python312\python.exe",
        "${env:ProgramFiles(x86)}\Python311\python.exe",
        "${env:ProgramFiles(x86)}\Python310\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe"
    )
    foreach ($cand in $searchDirs) {
        if (Test-Path $cand) {
            return $cand
        }
    }

    return $null
}

# --- STEP 1: Detect or Install Python ---
Write-Host "[1/4] Checking Python installation..." -ForegroundColor Yellow

$pythonExe = Find-PythonExecutable

if (-not $pythonExe) {
    Write-Host "      Python not found on this system." -ForegroundColor Yellow
    Write-Host "      Downloading official Python 3.12 (64-bit) from python.org..." -ForegroundColor Cyan

    $downloadUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
    $installerPath = Join-Path $env:TEMP "python-3.12.8-installer.exe"

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing
        Write-Host "      Download completed. Running silent installation with Tkinter and PATH..." -ForegroundColor Cyan

        # Run official installer with PrependPath=1, Include_tcltk=1, Include_pip=1
        $proc = Start-Process -FilePath $installerPath -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0", "Include_pip=1", "Include_tcltk=1", "SimpleInstall=1" -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            Write-Host "      Machine-wide install returned code $($proc.ExitCode); retrying per-user install..." -ForegroundColor Gray
            $proc = Start-Process -FilePath $installerPath -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0", "Include_pip=1", "Include_tcltk=1" -Wait -PassThru
        }
    }
    catch {
        Write-Host "      Automatic download/install encountered an error: $_" -ForegroundColor Red
    }
    finally {
        if (Test-Path $installerPath) {
            Remove-Item -Path $installerPath -Force -ErrorAction SilentlyContinue
        }
    }

    # Refresh PATH from registry after installation
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"

    $pythonExe = Find-PythonExecutable
}

if (-not $pythonExe) {
    Write-Host ""
    Write-Host "ERROR: Could not locate or install Python." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ manually from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "Make sure to check 'Add python.exe to PATH' during installation." -ForegroundColor Red
    Exit 1
}

$pyDir = Split-Path -Parent $pythonExe
$pyScriptsDir = Join-Path $pyDir "Scripts"
$pyVer = & $pythonExe --version

Write-Host "      Found: $pyVer" -ForegroundColor Green
Write-Host "      Path : $pythonExe" -ForegroundColor Green

# --- STEP 2: Configure System & User PATH Permanently ---
Write-Host ""
Write-Host "[2/4] Ensuring Python is in permanent Windows PATH..." -ForegroundColor Yellow

$currentUserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$userPathList = ($currentUserPath -split ";") | Where-Object { $_ -and $_.Trim() -ne "" }
$needsUpdate = $false

if ($userPathList -notcontains $pyDir) {
    $currentUserPath = "$pyDir;$currentUserPath"
    $needsUpdate = $true
}
if ($userPathList -notcontains $pyScriptsDir) {
    $currentUserPath = "$pyScriptsDir;$currentUserPath"
    $needsUpdate = $true
}

if ($needsUpdate) {
    try {
        [System.Environment]::SetEnvironmentVariable("Path", $currentUserPath, "User")
        Write-Host "      [+] Added Python and Scripts directory to Windows User PATH." -ForegroundColor Green
    }
    catch {
        Write-Host "      Could not update User PATH in registry: $_" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "      Python and Scripts directories are already configured in Windows PATH." -ForegroundColor Green
}

# Ensure active session PATH includes Python and Scripts
if (($env:Path -split ";") -notcontains $pyDir) {
    $env:Path = "$pyDir;$pyScriptsDir;$env:Path"
}

# --- STEP 3: Install & Upgrade Python Dependencies (Pip & Pygame) ---
Write-Host ""
Write-Host "[3/4] Installing / Upgrading pip and pygame..." -ForegroundColor Yellow

Write-Host "      Upgrading pip to latest version..." -ForegroundColor Gray
& $pythonExe -m pip install --upgrade pip --quiet

Write-Host "      Installing pygame..." -ForegroundColor Gray
& $pythonExe -m pip install pygame

# --- STEP 4: Verify Environment & Core Components ---
Write-Host ""
Write-Host "[4/4] Verifying Arcade Carousel components..." -ForegroundColor Yellow

$verifyScript = @"
import sys
import pygame
pygame.init()
import tkinter
root = tkinter.Tk()
root.withdraw()
root.destroy()
import ctypes
print('OK')
"@

$verifyResult = & $pythonExe -c $verifyScript 2>&1

$pythonwExe = Join-Path $pyDir "pythonw.exe"
$hasPythonw = Test-Path $pythonwExe

if ($verifyResult -contains "OK" -and $hasPythonw) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  SUCCESS! ALL DEPENDENCIES INSTALLED AND VERIFIED          " -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  [OK] Python Runtime : $pyVer" -ForegroundColor Green
    Write-Host "  [OK] PythonW Runner : $pythonwExe" -ForegroundColor Green
    Write-Host "  [OK] Windows PATH   : Fully configured" -ForegroundColor Green
    Write-Host "  [OK] Pygame Module  : Installed & Verified" -ForegroundColor Green
    Write-Host "  [OK] Tkinter Module : Installed & Verified (for overlays)" -ForegroundColor Green
    Write-Host "  [OK] Win32 ctypes   : Verified (for administrator input)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Ready to play! You can now launch:" -ForegroundColor Cyan
    Write-Host "  * run_arcade.bat       -> Starts the full-screen arcade carousel" -ForegroundColor White
    Write-Host "  * run_coin_mapper.bat  -> Map your coin drop button / added time" -ForegroundColor White
    Write-Host "  * install_autostart.bat-> Automatically boot arcade on Windows startup" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "WARNING: Setup completed with potential warnings:" -ForegroundColor DarkYellow
    if (-not $hasPythonw) {
        Write-Host "  - pythonw.exe was not found in $pyDir" -ForegroundColor Red
    }
    Write-Host "  - Test output: $verifyResult" -ForegroundColor DarkYellow
}
