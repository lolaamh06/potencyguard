# Serves the PotencyGuard dashboard on this computer only (127.0.0.1).
#
#   scripts\run-demo.ps1             builds the dashboard if needed and serves the production build (port 4173)
#   scripts\run-demo.ps1 -Dev        runs the development server instead (port 5173)
#   scripts\run-demo.ps1 -Backend    also starts the backend API on 127.0.0.1:8765 (used by ?mode=live)
#   scripts\run-demo.ps1 -Rebuild    forces a fresh build
#
# Press Ctrl+C to stop. Needs scripts\setup.ps1 to have been run once.

param(
    [switch]$Dev,
    [switch]$Backend,
    [switch]$Rebuild,
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Dash = Join-Path $Repo "dashboard"
$VenvPython = Join-Path $Repo ".venv\Scripts\python.exe"

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function PortInUse([int]$P) {
    try {
        $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), $P)
        $l.Start()
        $l.Stop()
        return $false
    } catch {
        return $true
    }
}

if (-not (Test-Path (Join-Path $Dash "node_modules"))) { Fail "The dashboard packages are not installed. Run scripts\setup.ps1 first." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail "npm was not found. Install Node.js 22.12 or newer from https://nodejs.org/ and open a NEW PowerShell window." }

if ($Port -eq 0) { if ($Dev) { $Port = 5173 } else { $Port = 4173 } }
if (PortInUse $Port) { Fail "Port $Port is already in use. Close the other program (or an earlier run of this script), or pick another port with -Port 4200." }

$backendProcess = $null
try {
    if ($Backend) {
        if (-not (Test-Path $VenvPython)) { Fail "The Python environment is missing. Run scripts\setup.ps1 first." }
        if (PortInUse 8765) { Fail "Port 8765 (the backend) is already in use. Close the other program and try again." }
        Write-Host "Starting the backend on http://127.0.0.1:8765 (no authentication; sample data only)"
        $backendProcess = Start-Process -FilePath $VenvPython -ArgumentList @("-m", "backend", "serve") -WorkingDirectory $Repo -PassThru -WindowStyle Hidden
    }

    Set-Location $Dash
    if ($Dev) {
        Write-Host ""
        Write-Host "Open  http://127.0.0.1:$Port  (development server; Ctrl+C stops it)" -ForegroundColor Green
        & npx vite --host 127.0.0.1 --port $Port --strictPort
    } else {
        $dist = Join-Path $Dash "dist\index.html"
        $needBuild = $Rebuild -or -not (Test-Path $dist)
        if (-not $needBuild) {
            $built = (Get-Item $dist).LastWriteTimeUtc
            $newest = Get-ChildItem (Join-Path $Dash "src"), (Join-Path $Dash "public") -Recurse -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
            if ($newest -and $newest.LastWriteTimeUtc -gt $built) { $needBuild = $true }
        }
        if ($needBuild) {
            Write-Host "Building the dashboard (about a minute the first time)..."
            & npm run build
            if ($LASTEXITCODE -ne 0) { Fail "The build failed. Run scripts\check.ps1 to see which check fails." }
        }
        Write-Host ""
        Write-Host "Open  http://127.0.0.1:$Port  (Ctrl+C stops it)" -ForegroundColor Green
        & npx vite preview --host 127.0.0.1 --port $Port --strictPort
    }
} finally {
    Set-Location $Repo
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Backend stopped."
    }
}
