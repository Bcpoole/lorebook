# dev.ps1 — launch FastAPI and Vite dev server concurrently
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$ui = Join-Path $root 'ui'

Write-Host "Starting FastAPI on http://localhost:8000 ..."
$api = Start-Process -NoNewWindow -PassThru -FilePath $python `
  -ArgumentList "-m", "uvicorn", "lorebook.api.app:app", "--reload", "--port", "8000", "--log-config", "scripts/uvicorn-log-config.json" `
  -WorkingDirectory $root

Write-Host "Starting Vite on http://localhost:5173 ..."
$vite = Start-Process -NoNewWindow -PassThru -FilePath "npm" `
  -ArgumentList "run", "dev" `
  -WorkingDirectory $ui

Write-Host "Both servers running. Press Ctrl+C to stop."
try {
  Wait-Process -Id $api.Id, $vite.Id
}
finally {
  Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
  Stop-Process -Id $vite.Id -ErrorAction SilentlyContinue
}
