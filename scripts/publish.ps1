# Build and push Home Box images to Docker Hub (avniademi/*).
param(
  [string]$RegistryUser = "avniademi",
  [string]$Tag = "0.1.0",
  [switch]$Latest = $true
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Push-Tagged([string]$Name) {
  $full = "${RegistryUser}/${Name}:${Tag}"
  docker push $full
  if ($Latest) {
    docker tag $full "${RegistryUser}/${Name}:latest"
    docker push "${RegistryUser}/${Name}:latest"
  }
}

Write-Host "Building images as ${RegistryUser}/*:${Tag}"

docker build -t "${RegistryUser}/home-box:${Tag}" ./image
docker build -t "${RegistryUser}/home-box-enroll:${Tag}" -f ./platform/Dockerfile.enroll ./platform
docker build -t "${RegistryUser}/home-box-tuya-import:${Tag}" -f ./platform/Dockerfile.tuya-import ./platform
docker build -t "${RegistryUser}/home-box-mcp:${Tag}" -f ./platform/Dockerfile.mcp ./platform
docker build -t "${RegistryUser}/home-box-lan-router:${Tag}" -f ./platform/Dockerfile.lan-router .
docker build -t "${RegistryUser}/home-box-gateway:${Tag}" -f ./nginx/Dockerfile ./nginx

# Keep local lab tags working
docker tag "${RegistryUser}/home-box:${Tag}" home-box:local
docker tag "${RegistryUser}/home-box-enroll:${Tag}" home-box-enroll:local
docker tag "${RegistryUser}/home-box-tuya-import:${Tag}" home-box-tuya-import:local
docker tag "${RegistryUser}/home-box-mcp:${Tag}" home-box-mcp:local

Push-Tagged "home-box"
Push-Tagged "home-box-enroll"
Push-Tagged "home-box-tuya-import"
Push-Tagged "home-box-mcp"
Push-Tagged "home-box-lan-router"
Push-Tagged "home-box-gateway"

Write-Host "Done. Deploy from .\deploy with Tag=$Tag (or latest)."
