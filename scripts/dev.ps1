# dev.ps1 — launch FastAPI and Vite dev server concurrently
$root = Split-Path -Parent $PSScriptRoot
$ui = Join-Path $root 'ui'
$venvPython = Join-Path $root '.venv\Scripts\python.exe'

$pythonFilePath = $null
$pythonArgsPrefix = @()

if (Test-Path $venvPython) {
  $pythonFilePath = $venvPython
} else {
  $pyCmd = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCmd) {
    $pythonFilePath = $pyCmd.Source
    $pythonArgsPrefix = @("-3")
  } else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
      $pythonFilePath = $pythonCmd.Source
    }
  }
}

if (-not $pythonFilePath) {
  Write-Error "Python runtime not found. Create .venv or install Python (py/python on PATH)."
  exit 1
}

$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) {
  Write-Error "npm.cmd was not found on PATH."
  exit 1
}

$api = $null
$vite = $null

Write-Host "Starting FastAPI on http://localhost:8000 ..."
try {
  $apiArgs = @(
    $pythonArgsPrefix
    "-m", "uvicorn", "lorebook.api.app:app", "--app-dir", "src", "--reload", "--port", "8000", "--log-config", "scripts/uvicorn-log-config.json"
  )
  $api = Start-Process -NoNewWindow -PassThru -FilePath $pythonFilePath `
    -ArgumentList $apiArgs `
    -WorkingDirectory $root
} catch {
  Write-Error "Failed to start FastAPI: $($_.Exception.Message)"
}

Write-Host "Starting Vite on http://localhost:5173 ..."
try {
  $vite = Start-Process -NoNewWindow -PassThru -FilePath $npmCmd.Source `
    -ArgumentList "run", "dev" `
    -WorkingDirectory $ui
} catch {
  Write-Error "Failed to start Vite: $($_.Exception.Message)"
}

Write-Host "Both servers running. Press Ctrl+C to stop."
try {
  $apiId = if ($api) { $api.Id } else { 0 }
  $viteId = if ($vite) { $vite.Id } else { 0 }
  if ($apiId -le 0 -or $viteId -le 0) {
    Write-Error "Failed to launch one or both servers. API PID: $apiId, Vite PID: $viteId"
    exit 1
  }
  Wait-Process -Id $apiId, $viteId
}
finally {
  if ($api -and $api.Id -gt 0) {
    Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
  }
  if ($vite -and $vite.Id -gt 0) {
    Stop-Process -Id $vite.Id -ErrorAction SilentlyContinue
  }
}
