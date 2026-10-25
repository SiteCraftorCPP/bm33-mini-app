$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$web = Join-Path $root "web"

if (-not (Test-Path $python)) {
    python -m venv (Join-Path $root ".venv")
}

& $python -m pip install -q -r (Join-Path $root "backend\requirements.txt")
if (-not (Test-Path (Join-Path $web "node_modules"))) {
    Push-Location $web
    npm install
    Pop-Location
}

$env:PYTHONPATH = Join-Path $root "backend"
$api = Start-Process `
    -FilePath $python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" `
    -WorkingDirectory $root `
    -NoNewWindow `
    -PassThru

try {
    Push-Location $web
    npm run dev
}
finally {
    Pop-Location
    if (-not $api.HasExited) {
        Stop-Process -Id $api.Id
    }
}
