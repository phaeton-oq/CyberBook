#Requires -Version 5.1
param([switch]$Seed)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "gen_secrets..." -ForegroundColor Cyan
python scripts/gen_secrets.py

Write-Host "pip install..." -ForegroundColor Cyan
pip install -r requirements.txt -q

if ($Seed) {
    Write-Host "seed..." -ForegroundColor Cyan
    python seed.py
}

Write-Host "build ok" -ForegroundColor Green
