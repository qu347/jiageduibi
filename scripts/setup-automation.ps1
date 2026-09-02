$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pluginRoot = (Resolve-Path (Join-Path $projectRoot 'opencli-plugin-price-compare-jd')).Path
$extensionUrl = 'https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk'

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}

if (-not (Get-Command agent-reach -ErrorAction SilentlyContinue)) {
    Write-Host 'Agent-Reach is not installed.' -ForegroundColor Yellow
    Write-Host 'Install it, then rerun this script:'
    Write-Host '  pipx install https://github.com/Panniantong/agent-reach/archive/main.zip'
    exit 1
}

agent-reach install --env=auto --system --channels=opencli
Assert-NativeSuccess 'Install or diagnose OpenCLI through Agent-Reach'

if (-not (Get-Command opencli -ErrorAction SilentlyContinue)) {
    throw 'OpenCLI is still unavailable after Agent-Reach setup.'
}

$pluginUri = ([System.Uri]$pluginRoot).AbsoluteUri
opencli plugin install $pluginUri
Assert-NativeSuccess 'Install the local JD price comparison plugin'

opencli doctor
if ($LASTEXITCODE -ne 0) {
    Write-Host 'The OpenCLI browser bridge is not connected.' -ForegroundColor Yellow
    Write-Host "Install the official extension, keep Chrome running, and rerun this script: $extensionUrl"
    exit 1
}

$registeredCommands = opencli list -f json
Assert-NativeSuccess 'List OpenCLI commands'
if ($registeredCommands -notmatch 'price-compare-jd') {
    throw 'The local JD price comparison plugin was not registered.'
}

Write-Host 'Automatic JD collection environment is ready.' -ForegroundColor Green
