$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $projectRoot 'backend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    py -3.12 -m venv (Join-Path $backendRoot '.venv')
    Assert-NativeSuccess 'Create Python virtual environment'
}

& $pythonPath -m pip install -e "${backendRoot}[dev]"
Assert-NativeSuccess 'Install backend dependencies'

pnpm --dir (Join-Path $projectRoot 'frontend') install --frozen-lockfile
Assert-NativeSuccess 'Install frontend dependencies'
pnpm --dir (Join-Path $projectRoot 'extension') install --frozen-lockfile
Assert-NativeSuccess 'Install extension dependencies'
pnpm --dir (Join-Path $projectRoot 'e2e') install --frozen-lockfile
Assert-NativeSuccess 'Install end-to-end dependencies'

$dataRoot = Join-Path $projectRoot 'data'
New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
Push-Location $backendRoot
try {
    & $pythonPath -m alembic upgrade head
    Assert-NativeSuccess 'Upgrade database'
    & $pythonPath -m app.db.seed_catalog
    Assert-NativeSuccess 'Seed catalog'
}
finally {
    Pop-Location
}

Write-Host 'Bootstrap complete.' -ForegroundColor Green
