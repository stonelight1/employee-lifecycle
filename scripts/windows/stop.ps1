param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [int]$BackendPort = 8013,
    [int]$FrontendPort = 5178
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$RunDir = Join-Path $RootDir ".run"
$BackendPidFile = Join-Path $RunDir "backend.pid"
$FrontendPidFile = Join-Path $RunDir "frontend.pid"

if ($BackendOnly -and $FrontendOnly) {
    throw "Use only one of -BackendOnly or -FrontendOnly."
}

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host $Message
}

function Stop-ProcessTree {
    param(
        [int]$RootProcessId,
        [string]$Name
    )

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $RootProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -RootProcessId $child.ProcessId -Name $Name
    }

    $process = Get-Process -Id $RootProcessId -ErrorAction SilentlyContinue
    if ($null -ne $process) {
        Stop-Process -Id $RootProcessId -Force -ErrorAction Stop
    }
}

function Stop-ProcessFromPidFile {
    param(
        [string]$PidFile,
        [string]$Name,
        [int]$Port
    )

    if (-not (Test-Path -LiteralPath $PidFile)) {
        Write-Host "  $Name pid file not found."
        Stop-ProcessByPort -Port $Port -Name $Name
        return
    }

    $rawPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    $processId = 0
    if (-not [int]::TryParse($rawPid, [ref]$processId)) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "  $Name pid file is invalid and has been removed."
        return
    }

    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "  $Name process $processId is already stopped."
        return
    }

    Write-Host "  Stopping $Name process $processId..."
    try {
        Stop-ProcessTree -RootProcessId $processId -Name $Name
    } catch {
        Write-Host "  Failed to stop $Name process ${processId}: $($_.Exception.Message)"
        return
    }

    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Stop-ProcessByPort -Port $Port -Name $Name
}

function Stop-ProcessByPort {
    param(
        [int]$Port,
        [string]$Name
    )

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        return
    }

    $ownerPids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($ownerPid in $ownerPids) {
        if ($ownerPid -le 0) {
            continue
        }

        $process = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
        $processName = if ($process) { $process.ProcessName } else { "unknown" }
        Write-Host "  Stopping residual $Name listener on port $Port (PID $ownerPid, $processName)..."
        try {
            Stop-ProcessTree -RootProcessId $ownerPid -Name $Name
        } catch {
            Write-Host "  Failed to stop residual $Name listener ${ownerPid}: $($_.Exception.Message)"
        }
    }
}

if (-not (Test-Path -LiteralPath $RunDir)) {
    Write-Host "Run directory not found: $RunDir"
    exit 0
}

Write-Step "Stopping Employee Lifecycle System"
if (-not $BackendOnly) {
    Stop-ProcessFromPidFile -PidFile $FrontendPidFile -Name "Frontend" -Port $FrontendPort
}
if (-not $FrontendOnly) {
    Stop-ProcessFromPidFile -PidFile $BackendPidFile -Name "Backend" -Port $BackendPort
}

Write-Host ""
Write-Host "Done."
