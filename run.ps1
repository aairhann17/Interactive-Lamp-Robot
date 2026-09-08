param(
    [switch]$StrictStartup,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$simulatorPage = Join-Path $repoRoot 'simulator\index.html'

if (-not (Test-Path $venvPython)) {
    throw "Python virtual environment not found at $venvPython. Create it first, then install dependencies with pip install -r requirements.txt."
}

Write-Host 'Starting Interactive Lamp Robot...' -ForegroundColor Cyan

if (-not $NoBrowser) {
    Start-Process $simulatorPage | Out-Null
}

$args = @('main.py')
if ($StrictStartup) {
    $args += '--strict-startup'
}

Push-Location $repoRoot
try {
    & $venvPython @args
}
finally {
    Pop-Location
}
