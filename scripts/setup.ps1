# Sets up PotencyGuard on a Windows laptop: a Python environment in .venv (inside this folder),
# the Python packages, and the dashboard's npm packages. Safe to run twice. Touches nothing
# outside the repo folder (apart from npm's normal download cache).
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#
# Needs: Python 3.11 or newer, and Node.js 22.12 or newer (the version that comes with npm).

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

# ---------------------------------------------------------------- Python 3.11+
Step "Looking for Python 3.11 or newer"
$candidates = @(
    @("py", "-3.13"), @("py", "-3.12"), @("py", "-3.11"), @("py", "-3"), @("python"), @("python3")
)
$python = $null
foreach ($c in $candidates) {
    try {
        $exe = $c[0]
        $rest = @()
        if ($c.Length -gt 1) { $rest = $c[1..($c.Length - 1)] }
        $out = & $exe @rest -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $parts = ($out | Select-Object -First 1).Trim().Split(".")
            if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 11) {
                $python = @($exe) + $rest
                Write-Host "Found Python $out ($($c -join ' '))"
                break
            }
        }
    } catch { }
}
if (-not $python) {
    Fail ("Python 3.11 or newer was not found.`n" +
          "Install it from https://www.python.org/downloads/windows/ and tick 'Add python.exe to PATH' in the installer, then open a NEW PowerShell window and run this script again.")
}

# ---------------------------------------------------------------- Node 22.12+
Step "Looking for Node.js 22.12 or newer"
$nodeVersion = $null
try { $nodeVersion = (& node --version 2>$null) } catch { }
if (-not $nodeVersion) {
    Fail ("Node.js was not found.`n" +
          "Install the LTS version from https://nodejs.org/ (it includes npm), then open a NEW PowerShell window and run this script again.")
}
$m = [regex]::Match($nodeVersion, "v(\d+)\.(\d+)")
$nodeMajor = [int]$m.Groups[1].Value
$nodeMinor = [int]$m.Groups[2].Value
$nodeOk = ($nodeMajor -gt 22) -or ($nodeMajor -eq 22 -and $nodeMinor -ge 12)
if (-not $nodeOk) {
    Fail ("Node.js $nodeVersion is too old. The dashboard needs 22.12 or newer.`n" +
          "Install the current LTS version from https://nodejs.org/, then open a NEW PowerShell window and run this script again.")
}
Write-Host "Found Node.js $nodeVersion"
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Fail "npm was not found, although Node.js is installed. Reinstall Node.js from https://nodejs.org/ and open a NEW PowerShell window."
}

# ---------------------------------------------------------------- Python environment
Step "Creating the Python environment in .venv (inside this folder)"
$venvPython = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $exe = $python[0]
    $rest = @()
    if ($python.Length -gt 1) { $rest = $python[1..($python.Length - 1)] }
    & $exe @rest -m venv (Join-Path $Repo ".venv")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) { Fail "Could not create the .venv folder." }
    Write-Host "Created .venv"
} else {
    Write-Host ".venv already exists, reusing it"
}

Step "Installing the Python packages (requirements-dev.txt)"
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $Repo "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) { Fail "Installing the Python packages failed. Check your internet connection and run this script again." }

# ---------------------------------------------------------------- Dashboard packages
Step "Installing the dashboard packages (npm ci)"
$dash = Join-Path $Repo "dashboard"
$nm = Join-Path $dash "node_modules"
$isLink = $false
if (Test-Path $nm) {
    $isLink = [bool]((Get-Item $nm -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)
}
if ($isLink) {
    Write-Host "dashboard\node_modules is a link to another folder; leaving it alone (npm ci would replace it)."
} else {
    Push-Location $dash
    try {
        & npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { Fail "npm ci failed. Check your internet connection, then run this script again." }
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next:"
Write-Host "  scripts\run-demo.ps1        start the demo, then open http://127.0.0.1:4173"
Write-Host "  scripts\check.ps1           run all the checks"
Write-Host ""
Write-Host "If PowerShell says scripts are disabled, run this once in the same window, then try again:"
Write-Host "  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass"
