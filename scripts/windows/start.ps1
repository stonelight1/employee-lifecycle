param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$NoInstall,
    [switch]$NoMigrate,
    [switch]$NoSeed,
    [string]$HostAddress = "0.0.0.0",
    [int]$BackendPort = 8013,
    [int]$FrontendPort = 5178
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$RunDir = Join-Path $RootDir ".run"
$BackendPidFile = Join-Path $RunDir "backend.pid"
$FrontendPidFile = Join-Path $RunDir "frontend.pid"
$BackendLog = Join-Path $RunDir "backend.log"
$BackendErrLog = Join-Path $RunDir "backend.err.log"
$FrontendLog = Join-Path $RunDir "frontend.log"
$FrontendErrLog = Join-Path $RunDir "frontend.err.log"

if ($BackendOnly -and $FrontendOnly) {
    throw "Use only one of -BackendOnly or -FrontendOnly."
}

if (-not (Test-Path -LiteralPath $RunDir)) {
    New-Item -ItemType Directory -Path $RunDir | Out-Null
}

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host $Message
}

function Require-Command {
    param(
        [string]$Name,
        [string]$InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Command '$Name' was not found. $InstallHint"
    }
}

function Test-ProcessAlive {
    param([string]$PidFile)

    if (-not (Test-Path -LiteralPath $PidFile)) {
        return $false
    }

    $rawPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    $processId = 0
    if (-not [int]::TryParse($rawPid, [ref]$processId)) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        return $false
    }

    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        return $false
    }

    return $true
}

function Assert-PortFree {
    param(
        [int]$Port,
        [string]$ServiceName
    )

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        return
    }

    $ownerPid = ($connections | Select-Object -First 1).OwningProcess
    $owner = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
    $ownerName = if ($owner) { $owner.ProcessName } else { "unknown" }
    throw "$ServiceName port $Port is already in use by PID $ownerPid ($ownerName). Stop that process or choose another port."
}

function Wait-Port {
    param(
        [string]$Name,
        [string]$ConnectHost,
        [int]$Port,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $client = [System.Net.Sockets.TcpClient]::new()
            $task = $client.ConnectAsync($ConnectHost, $Port)
            if ($task.Wait(1000) -and $client.Connected) {
                $client.Dispose()
                Write-Host "  $Name is listening on http://localhost:$Port"
                return
            }
            $client.Dispose()
        } catch {
            Start-Sleep -Milliseconds 500
        }

        Start-Sleep -Milliseconds 500
    }

    throw "$Name did not start within $TimeoutSeconds seconds. Check logs in $RunDir."
}

function Get-BackendPython {
    $pythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $pythonExe) {
        return $pythonExe
    }

    Require-Command -Name "python" -InstallHint "Install Python 3.12+ first."
    Push-Location $BackendDir
    try {
        & python -m venv .venv
    } finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw "Backend virtual environment was not created at $pythonExe."
    }

    return $pythonExe
}

function Start-Backend {
    if (Test-ProcessAlive $BackendPidFile) {
        $existingPid = Get-Content -LiteralPath $BackendPidFile | Select-Object -First 1
        Write-Host "Backend already appears to be running (PID $existingPid)."
        return
    }

    Assert-PortFree -Port $BackendPort -ServiceName "Backend"

    Write-Step "[1/3] Preparing backend virtual environment"
    $pythonExe = Get-BackendPython

    if (-not $NoInstall) {
        Write-Step "[2/3] Installing backend dependencies"
        $uvExe = Join-Path $BackendDir ".venv\Scripts\uv.exe"
        if (Test-Path -LiteralPath $uvExe) {
            Push-Location $BackendDir
            try {
                & $uvExe sync
            } finally {
                Pop-Location
            }
        } else {
            # Fallback: check if uv is globally available, otherwise use pip
            if (Get-Command "uv" -ErrorAction SilentlyContinue) {
                Push-Location $BackendDir
                try {
                    & uv sync
                } finally {
                    Pop-Location
                }
            } else {
                Push-Location $BackendDir
                try {
                    & $pythonExe -m pip install -e .
                } finally {
                    Pop-Location
                }
            }
        }
    } else {
        Write-Step "[2/3] Skipping backend dependency install (-NoInstall)"
    }

    if (-not $NoMigrate) {
        Write-Step "[3/5] Running database migrations"
        Push-Location $BackendDir
        try {
            & $pythonExe -m alembic upgrade head
        } finally {
            Pop-Location
        }
    } else {
        Write-Step "[3/5] Skipping database migrations (-NoMigrate)"
    }

    if (-not $NoSeed) {
        Write-Step "[4/5] Running seed data"
        Push-Location $BackendDir
        try {
            & $pythonExe -m app.seed
        } finally {
            Pop-Location
        }
    } else {
        Write-Step "[4/5] Skipping seed data (-NoSeed)"
    }

    Write-Step "[5/5] Starting backend on port $BackendPort"
    $backendArgs = @(
        "-m", "uvicorn",
        "app.main:app",
        "--reload",
        "--host", $HostAddress,
        "--port", "$BackendPort"
    )
    $process = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList $backendArgs `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $BackendLog `
        -RedirectStandardError $BackendErrLog `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $BackendPidFile -Value $process.Id
    $connectHost = if ($HostAddress -eq "0.0.0.0") { "127.0.0.1" } else { $HostAddress }
    Wait-Port -Name "Backend" -ConnectHost $connectHost -Port $BackendPort
}

function Start-Frontend {
    if (Test-ProcessAlive $FrontendPidFile) {
        $existingPid = Get-Content -LiteralPath $FrontendPidFile | Select-Object -First 1
        Write-Host "Frontend already appears to be running (PID $existingPid)."
        return
    }

    Assert-PortFree -Port $FrontendPort -ServiceName "Frontend"
    Require-Command -Name "npm" -InstallHint "Install Node.js/npm first."

    Write-Step "[4/4] Preparing frontend"
    $nodeModulesPath = Join-Path $FrontendDir "node_modules"
    if ((-not $NoInstall) -and (-not (Test-Path -LiteralPath $nodeModulesPath))) {
        Push-Location $FrontendDir
        try {
            if (Test-Path -LiteralPath (Join-Path $FrontendDir "package-lock.json")) {
                & npm ci
            } else {
                & npm install
            }
        } finally {
            Pop-Location
        }
    } elseif ($NoInstall) {
        Write-Host "  Skipping frontend dependency install (-NoInstall)"
    } else {
        Write-Host "  node_modules already exists"
    }

    Write-Host "  Starting frontend on port $FrontendPort"
    $frontendArgs = @("run", "dev", "--", "--host", $HostAddress, "--port", "$FrontendPort")
    $process = Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList $frontendArgs `
        -WorkingDirectory $FrontendDir `
        -RedirectStandardOutput $FrontendLog `
        -RedirectStandardError $FrontendErrLog `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $FrontendPidFile -Value $process.Id
    $connectHost = if ($HostAddress -eq "0.0.0.0") { "127.0.0.1" } else { $HostAddress }
    Wait-Port -Name "Frontend" -ConnectHost $connectHost -Port $FrontendPort
}

Write-Host "================================================"
Write-Host " Starting Employee Lifecycle System"
Write-Host "================================================"

if (-not $FrontendOnly) {
    Start-Backend
}

if (-not $BackendOnly) {
    Start-Frontend
}

Write-Host ""
Write-Host "================================================"
if (-not $FrontendOnly) {
    Write-Host " Backend:  http://localhost:$BackendPort"
    Write-Host " API Docs: http://localhost:$BackendPort/docs"
}
if (-not $BackendOnly) {
    Write-Host " Frontend: http://localhost:$FrontendPort"
}
Write-Host " Logs:     $RunDir"
Write-Host "================================================"
