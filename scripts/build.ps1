$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

pnpm --dir (Join-Path $projectRoot 'frontend') build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
pnpm --dir (Join-Path $projectRoot 'extension') build
if ($LASTEXITCODE -ne 0) { throw 'Extension build failed' }

Write-Host 'Build complete: frontend\dist and extension\dist' -ForegroundColor Green
