# Docker Hub login for publish scripts.
# Credentials: scripts/docker-hub.env (gitignored) or DOCKERHUB_USER / DOCKERHUB_TOKEN env.
param(
  [string]$EnvFile = (Join-Path $PSScriptRoot "docker-hub.env")
)

$ErrorActionPreference = "Stop"

$user = $env:DOCKERHUB_USER
$token = $env:DOCKERHUB_TOKEN

if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $parts = $line.Split("=", 2)
    if ($parts.Count -ne 2) { return }
    $key = $parts[0].Trim()
    $val = $parts[1].Trim().Trim('"').Trim("'")
    if ($key -eq "DOCKERHUB_USER") { $user = $val }
    if ($key -eq "DOCKERHUB_TOKEN") { $token = $val }
  }
}

if (-not $user -or -not $token) {
  throw "Missing Docker Hub credentials. Set DOCKERHUB_USER/DOCKERHUB_TOKEN or create scripts/docker-hub.env (see docker-hub.env.example)."
}

$token | docker login -u $user --password-stdin
if ($LASTEXITCODE -ne 0) {
  throw "docker login failed"
}
Write-Host "Docker Hub login ok as $user"
