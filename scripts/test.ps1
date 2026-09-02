$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $projectRoot 'backend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'

& (Join-Path $PSScriptRoot 'build.ps1')

$pluginTestRoot = Join-Path $projectRoot 'opencli-plugin-price-compare-jd\tests'
$pluginTests = @(Get-ChildItem -LiteralPath $pluginTestRoot -Filter '*.test.mjs' -File | ForEach-Object FullName)
if ($pluginTests.Count -eq 0) { throw 'No OpenCLI plugin tests found' }
node --test $pluginTests
if ($LASTEXITCODE -ne 0) { throw 'OpenCLI plugin tests failed' }

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
