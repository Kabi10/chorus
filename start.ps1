# Chorus Launcher
# Usage: Right-click → "Run with PowerShell"  OR  pwsh start.ps1

$ChorusPort = 4747

# ── Open Chorus UI in default browser ────────────────────────────────────────
Start-Sleep -Milliseconds 800
Start-Process "http://localhost:$ChorusPort"

# ── Start Chorus server ──────────────────────────────────────────────────────
Write-Host "[Chorus] Starting server at http://localhost:$ChorusPort ..." -ForegroundColor Cyan
Set-Location $PSScriptRoot
python chorus/main.py
