param([switch]$NoOpen)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $projectRoot 'backend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
$frontendIndex = Join-Path $projectRoot 'frontend\dist\index.html'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1')
}
if (-not (Test-Path -LiteralPath $frontendIndex)) {
    & (Join-Path $PSScriptRoot 'build.ps1')
}

New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot 'data') | Out-Null
Push-Location $backendRoot
try {
    & $pythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database upgrade failed' }
    & $pythonPath -m app.db.seed_demo
    if ($LASTEXITCODE -ne 0) { throw 'Offline demo seed failed' }

    if (-not $NoOpen) {
        Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
            "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765'"
        ) -WindowStyle Hidden
    }
    & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8765
}
finally {
    Pop-Location
}
