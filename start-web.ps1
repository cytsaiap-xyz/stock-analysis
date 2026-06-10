# Start the Agentic Investment Committee web app (Django + Channels).
#   .\start-web.ps1
#   $env:PORT="9000"; .\start-web.ps1
#
# .env is loaded automatically; set LLM_PROVIDER + the matching API key first.
$ErrorActionPreference = "Stop"

# Run from the project root (this script's folder), wherever it is invoked from.
Set-Location -Path $PSScriptRoot

# NOTE: do not use $host -- it is a PowerShell automatic variable.
$bindHost = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$port     = if ($env:PORT) { $env:PORT } else { "8000" }

# Prefer a project venv if present, else fall back to system python.
if (Test-Path "venv\Scripts\python.exe") { $py = ".\venv\Scripts\python.exe" }
elseif (Test-Path "venv\bin\python")     { $py = ".\venv\bin\python" }
elseif (Get-Command python  -ErrorAction SilentlyContinue) { $py = "python" }
else { $py = "python3" }

if (-not (Test-Path ".env")) {
  Write-Warning "no .env found - set LLM_PROVIDER + the matching API key first (see CLAUDE.md)."
}

Write-Host ">> Agentic Investment Committee Web -> http://${bindHost}:${port}  (Ctrl+C to stop)"
& $py manage.py runserver "$($bindHost):$($port)"
