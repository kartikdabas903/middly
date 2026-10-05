# Installs everything needed for Middly development on Windows (PowerShell):
#   .env, backend venv + dev deps, frontend deps, Playwright browser, Docker images.
#   Usage:  powershell -ExecutionPolicy Bypass -File scripts\install-dev.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd is required ($hint)" }
}
Need docker "Docker Desktop"
Need node "Node.js 20.9+"
Need npm "comes with Node.js"
Need python "Python 3.11+"

Write-Host "1/5 Environment file"
if (Test-Path .env) {
  Write-Host "  .env exists - kept"
} else {
  Copy-Item .env.example .env
  $vars = "POSTGRES_PASSWORD","REDIS_PASSWORD","RABBITMQ_PASSWORD","KEYCLOAK_ADMIN_PASSWORD","OIDC_CLIENT_SECRET",
          "IDENTITY_CLIENT_SECRET","EDUCATION_API_KEY","EMPLOYMENT_BASIC_PASSWORD","SKILL_API_KEY",
          "GRIEVANCE_CLIENT_SECRET","MOCK_ADMIN_KEY","GRAFANA_ADMIN_PASSWORD","SESSION_SECRET"
  $content = Get-Content .env
  foreach ($v in $vars) {
    $len = if ($v -eq "SESSION_SECRET") { 32 } else { 18 }
    $bytes = New-Object byte[] $len
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $hex = -join ($bytes | ForEach-Object { $_.ToString("x2") })
    $content = $content -replace "^$v=.*", "$v=$hex"
  }
  $content | Set-Content -Encoding ascii .env
  Write-Host "  .env created with random secrets"
}

Write-Host "2/5 Backend virtualenv (backend\.venv) + dev dependencies"
python -m venv backend\.venv
& backend\.venv\Scripts\python.exe -m pip install -q --upgrade pip
& backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "3/5 Frontend dependencies"
Push-Location frontend
npm install --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw "npm install failed" }

Write-Host "4/5 Playwright browser (Chromium)"
npx playwright install chromium
Pop-Location

Write-Host "5/5 Docker images"
docker compose build
if ($LASTEXITCODE -ne 0) { throw "docker compose build failed" }

Write-Host ""
Write-Host "Development environment ready."
Write-Host "  Start the stack:      docker compose up -d   (or scripts/start.sh in Git Bash)"
Write-Host "  Unit tests (local):   cd backend; .venv\Scripts\python -m pytest -m 'not integration'"
Write-Host "  All tests:            scripts/test.sh (Git Bash)"
