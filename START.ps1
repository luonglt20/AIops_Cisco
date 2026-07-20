# MerakiMind AIOps Platform — PowerShell Launcher (Windows)
Set-Location $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  MerakiMind v4.0 / v5.0 — AI Network Intelligence" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "🧹 Cleaning up existing processes on ports 8765 and 5173..." -ForegroundColor Yellow

# Kill process on port 8765
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}

# Kill process on port 5173
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1

Write-Host "🚀 Starting MerakiMind Multi-Agent Backend (Python)..." -ForegroundColor Cyan
$backendProc = Start-Process python -ArgumentList "server.py" -PassThru -NoNewWindow

Write-Host "🚀 Starting React + Vite Frontend Dev Server (Node.js)..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\frontend"
$frontendProc = Start-Process npm -ArgumentList "run dev" -PassThru -NoNewWindow
Set-Location $PSScriptRoot

Start-Sleep -Seconds 3

Write-Host "🌐 Opening Dashboard at http://localhost:5173 ..." -ForegroundColor Green
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "✅ Dashboard launched successfully at http://localhost:5173" -ForegroundColor Green
Write-Host "🛑 Press Ctrl+C to stop both backend and frontend servers" -ForegroundColor Yellow

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`n🛑 Stopping MerakiMind processes..." -ForegroundColor Red
    if ($backendProc -and -not $backendProc.HasExited) { Stop-Process -Id $backendProc.Id -Force }
    if ($frontendProc -and -not $frontendProc.HasExited) { Stop-Process -Id $frontendProc.Id -Force }
}
