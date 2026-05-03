param(
    [int]$ApiPort = 8000,
    [int]$TeamsPort = 3978,
    [switch]$InstallDeps,
    [switch]$SkipIndexRebuild,
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{
            FilePath = "python"
            PrefixArgs = @()
        }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{
            FilePath = "py"
            PrefixArgs = @("-3")
        }
    }
    throw "Python executable was not found in PATH."
}

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    foreach ($rawLine in Get-Content -Path $Path -Encoding UTF8) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            continue
        }
        $eqIndex = $line.IndexOf("=")
        if ($eqIndex -le 0) {
            continue
        }
        $key = $line.Substring(0, $eqIndex).Trim()
        $value = $line.Substring($eqIndex + 1).Trim()

        if ($value.Length -ge 2) {
            $startsWithDouble = $value.StartsWith('"')
            $endsWithDouble = $value.EndsWith('"')
            $startsWithSingle = $value.StartsWith("'")
            $endsWithSingle = $value.EndsWith("'")
            if (($startsWithDouble -and $endsWithDouble) -or ($startsWithSingle -and $endsWithSingle)) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        Set-Item -Path "Env:$key" -Value $value
    }
}

function Start-DemoProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$LogDirectory
    )

    $stdoutPath = Join-Path $LogDirectory "$Name.out.log"
    $stderrPath = Join-Path $LogDirectory "$Name.err.log"

    if (Test-Path $stdoutPath) {
        Remove-Item -Path $stdoutPath -Force
    }
    if (Test-Path $stderrPath) {
        Remove-Item -Path $stderrPath -Force
    }

    return Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru
}

function Wait-ApiReady {
    param(
        [string]$ApiBaseUrl,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri "$ApiBaseUrl/health" -Method Get -TimeoutSec 3
            if ($health.status -eq "ok") {
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 1000
            continue
        }
        Start-Sleep -Milliseconds 1000
    }
    return $false
}

function Get-RunningDemoPids {
    param([string]$PidFilePath)

    if (-not (Test-Path $PidFilePath)) {
        return @()
    }

    try {
        $meta = Get-Content -Path $PidFilePath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return @()
    }

    $running = @()
    foreach ($name in @("api_pid", "teams_pid", "teams_chat_pid", "teams_admin_pid")) {
        if (-not ($meta.PSObject.Properties.Name -contains $name)) {
            continue
        }
        $pidValue = [int]$meta.$name
        if ($pidValue -le 0) {
            continue
        }
        $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if ($proc) {
            $running += $pidValue
        }
    }
    return $running
}

$projectRoot = Split-Path -Parent $PSCommandPath
if (-not $projectRoot) {
    $projectRoot = (Get-Location).Path
}
Set-Location $projectRoot

$python = Resolve-Python
$apiBaseUrl = "http://127.0.0.1:$ApiPort"
$teamsBaseUrl = "http://127.0.0.1:$TeamsPort"
$teamsChatUrl = "$teamsBaseUrl/api/messages/chat"
$teamsAdminUrl = "$teamsBaseUrl/api/messages/admin"

$logDirectory = Join-Path $projectRoot ".demo_logs"
$stateDirectory = Join-Path $projectRoot ".demo_state"
$pidFile = Join-Path $stateDirectory "teams_demo_processes.json"
$envFile = Join-Path $projectRoot ".env"

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $stateDirectory | Out-Null

Import-DotEnv -Path $envFile
$env:API_BASE_URL = $apiBaseUrl
$env:TEAMS_PORT = "$TeamsPort"
$env:PYTHONUNBUFFERED = "1"
if (-not $env:WORKFLOW_DB) {
    $env:WORKFLOW_DB = (Join-Path $stateDirectory "workflow.db")
}
if (-not $env:LOG_PATH) {
    $env:LOG_PATH = (Join-Path $stateDirectory "chat_logs.jsonl")
}
if (-not $env:INDEX_PATH) {
    $env:INDEX_PATH = (Join-Path $stateDirectory "index.json")
}
if (-not $env:SYSTEM_PROMPT_PATH) {
    $env:SYSTEM_PROMPT_PATH = (Join-Path $stateDirectory "system_prompt.txt")
}

$runningPids = Get-RunningDemoPids -PidFilePath $pidFile
if ($runningPids.Count -gt 0) {
    if (-not $ForceRestart) {
        throw "Teams demo services are already running (PIDs: $($runningPids -join ', ')). Use -ForceRestart to restart."
    }
    foreach ($runningPid in $runningPids) {
        Stop-Process -Id $runningPid -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 1000
}

if ($InstallDeps) {
    & $python.FilePath @($python.PrefixArgs + @("-m", "pip", "install", "-r", "requirements.txt"))
}

$apiArgs = $python.PrefixArgs + @(
    "-m", "uvicorn", "app:app",
    "--host", "127.0.0.1",
    "--port", "$ApiPort"
)
$teamsArgs = $python.PrefixArgs + @(
    "-m", "uvicorn", "teams_app:app",
    "--host", "127.0.0.1",
    "--port", "$TeamsPort"
)

$apiProc = Start-DemoProcess `
    -Name "teams-api" `
    -FilePath $python.FilePath `
    -ArgumentList $apiArgs `
    -WorkingDirectory $projectRoot `
    -LogDirectory $logDirectory

$teamsProc = Start-DemoProcess `
    -Name "teams" `
    -FilePath $python.FilePath `
    -ArgumentList $teamsArgs `
    -WorkingDirectory $projectRoot `
    -LogDirectory $logDirectory

$apiReady = Wait-ApiReady -ApiBaseUrl $apiBaseUrl -TimeoutSeconds 45
if (-not $apiReady) {
    Write-Warning "API did not become healthy in time. Check .demo_logs\\api.err.log"
}

if (-not $SkipIndexRebuild -and $apiReady) {
    if ($env:ADMIN_TOKEN) {
        try {
            Invoke-RestMethod `
                -Uri "$apiBaseUrl/admin/rebuild-index" `
                -Method Post `
                -Headers @{ "X-Admin-Token" = $env:ADMIN_TOKEN } `
                -TimeoutSec 180 | Out-Null
            Write-Host "RAG index rebuilt successfully."
        } catch {
            Write-Warning "Index rebuild failed: $($_.Exception.Message)"
        }
    } else {
        Write-Warning "ADMIN_TOKEN is empty; skipped automatic index rebuild."
    }
}

$meta = [ordered]@{
    started_at = (Get-Date).ToString("o")
    api_pid = $apiProc.Id
    teams_pid = $teamsProc.Id
    api_url = $apiBaseUrl
    teams_url = $teamsBaseUrl
    teams_chat_url = $teamsChatUrl
    teams_admin_url = $teamsAdminUrl
    logs_dir = $logDirectory
}
$meta | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8

Write-Host ""
Write-Host "Teams demo services started."
Write-Host "API:            $apiBaseUrl"
Write-Host "Teams Gateway:  $teamsBaseUrl"
Write-Host "Teams Chat API: $teamsChatUrl"
Write-Host "Teams Admin API:$teamsAdminUrl"
Write-Host "Logs:           $logDirectory"
Write-Host "PIDs file:      $pidFile"
Write-Host ""
Write-Host "To stop all services run: .\\stop_teams_demo.ps1"
