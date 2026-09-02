$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'

& (Join-Path $PSScriptRoot 'bootstrap.ps1')

$backend = Start-Process -FilePath $pythonPath -ArgumentList @(
    '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8765', '--reload'
) -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru
$frontend = Start-Process -FilePath 'pnpm.cmd' -ArgumentList @('dev') `
    -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru

Start-Sleep -Seconds 2
Start-Process 'http://127.0.0.1:5173'
Write-Host "Development services started. Backend PID=$($backend.Id), frontend PID=$($frontend.Id)" -ForegroundColor Green
Write-Host 'Stop services with: Stop-Process -Id <PID>'
