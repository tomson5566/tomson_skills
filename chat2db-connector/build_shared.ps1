# ==========================================================
#   Chat2DB Connector - Shared Key Packager
#
#   Bundles dist\Chat2DBConnector.exe + your private key +
#   userreadme_shared.md into a single zip that you can hand
#   to colleagues. They just unzip and double-click.
#
#   !!!!  WARNING !!!!
#   This zip contains your private SSH key. Anyone who gets
#   the zip can log into the server. Only use for trusted,
#   short-term, small-team scenarios.
# ==========================================================

$ErrorActionPreference = "Stop"

$root       = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe        = Join-Path $root "dist\Chat2DBConnector.exe"
$key        = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$doc        = Join-Path $root "userreadme_shared.md"
$stage      = Join-Path $root "build_shared"
$zipName    = "Chat2DB-shared-key.zip"
$zipPath    = Join-Path $root $zipName

# --- preflight ---
if (-not (Test-Path $exe)) {
    Write-Host "[X] Missing: $exe" -ForegroundColor Red
    Write-Host "    Run build.bat first to produce the EXE." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $key)) {
    Write-Host "[X] Missing: $key" -ForegroundColor Red
    Write-Host "    Generate a key first:" -ForegroundColor Yellow
    Write-Host "    ssh-keygen -t ed25519 -f `"$env:USERPROFILE\.ssh\id_ed25519`"" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path $doc)) {
    Write-Host "[X] Missing: $doc" -ForegroundColor Red
    exit 1
}

# --- stage files ---
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
New-Item -ItemType Directory -Path $stage | Out-Null

Copy-Item $exe $stage
Copy-Item $key (Join-Path $stage "id_ed25519")
Copy-Item $doc (Join-Path $stage "使用说明.md")

# --- zip ---
# Use built-in Compress-Archive (Win10+)
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force

# --- summary ---
$size = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Packaged: $zipName ($size MB)" -ForegroundColor Green
Write-Host "  Path:     $zipPath" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Reminder: this zip contains your private SSH key." -ForegroundColor Yellow
Write-Host "  Send it only to people you trust, only via a private channel." -ForegroundColor Yellow
Write-Host ""

# cleanup staging
Remove-Item -Recurse -Force $stage
