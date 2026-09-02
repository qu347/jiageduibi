$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $projectRoot 'backend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'

& (Join-Path $PSScriptRoot 'build.ps1')

Push-Location $backendRoot
try {
    & $pythonPath -m pytest -v
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed' }
}
finally {
    Pop-Location
}

pnpm --dir (Join-Path $projectRoot 'frontend') test
if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed' }
pnpm --dir (Join-Path $projectRoot 'extension') test
if ($LASTEXITCODE -ne 0) { throw 'Extension tests failed' }
pnpm --dir (Join-Path $projectRoot 'e2e') test
if ($LASTEXITCODE -ne 0) { throw 'Offline end-to-end tests failed' }

Write-Host 'All tests passed.' -ForegroundColor Green
