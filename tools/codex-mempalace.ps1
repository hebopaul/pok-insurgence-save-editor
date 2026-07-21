param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CodexArgs
)

$ErrorActionPreference = "Stop"

$UserHome = [Environment]::GetFolderPath("UserProfile")
$CodexHome = Join-Path $UserHome ".codex"
$StatePath = Join-Path $CodexHome "mempalace-folders.json"
$ConfigPath = Join-Path $CodexHome "config.toml"
$MemPalaceVenv = Join-Path $UserHome ".mempalace\codex-venv"
$Python = Join-Path $MemPalaceVenv "Scripts\python.exe"
$MemPalaceMcp = Join-Path $MemPalaceVenv "Scripts\mempalace-mcp.exe"
$RealCodex = Join-Path $UserHome "AppData\Local\Volta\bin\codex.cmd"

function Invoke-RealCodex {
    if (-not (Test-Path -LiteralPath $RealCodex)) {
        throw "Could not find the real Codex launcher at $RealCodex"
    }

    & $RealCodex @CodexArgs
    exit $LASTEXITCODE
}

function Get-NormalizedPath([string] $Path) {
    return ([System.IO.Path]::GetFullPath($Path)).TrimEnd("\").ToLowerInvariant()
}

function Read-State {
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return [ordered]@{ folders = [ordered]@{} }
    }

    $raw = Get-Content -LiteralPath $StatePath -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return [ordered]@{ folders = [ordered]@{} }
    }

    return $raw | ConvertFrom-Json -AsHashtable
}

function Write-State($State) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $StatePath) | Out-Null
    $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Remove-MemPalaceBlock([string[]] $Lines) {
    $result = New-Object System.Collections.Generic.List[string]
    $skip = $false

    foreach ($line in $Lines) {
        if ($line -eq "[mcp_servers.mempalace]") {
            $skip = $true
            continue
        }

        if ($skip -and $line.StartsWith("[") -and $line.EndsWith("]")) {
            $skip = $false
        }

        if (-not $skip) {
            $result.Add($line)
        }
    }

    while ($result.Count -gt 0 -and [string]::IsNullOrWhiteSpace($result[$result.Count - 1])) {
        $result.RemoveAt($result.Count - 1)
    }

    return $result.ToArray()
}

function Quote-TomlString([string] $Value) {
    return "'" + ($Value -replace "'", "''") + "'"
}

function Set-MemPalaceMcp([string] $Mode, [string] $PalacePath) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ConfigPath) | Out-Null

    $lines = @()
    if (Test-Path -LiteralPath $ConfigPath) {
        $lines = @(Get-Content -LiteralPath $ConfigPath)
    }

    $lines = @(Remove-MemPalaceBlock $lines)

    if ($Mode -eq "off") {
        $lines | Set-Content -LiteralPath $ConfigPath -Encoding UTF8
        return
    }

    if ($lines.Count -gt 0) {
        $lines += ""
    }

    $lines += "[mcp_servers.mempalace]"
    $lines += "command = $(Quote-TomlString $MemPalaceMcp)"

    if ($Mode -eq "local") {
        $lines += "args = [$(Quote-TomlString "--palace"), $(Quote-TomlString $PalacePath)]"
    }

    $lines | Set-Content -LiteralPath $ConfigPath -Encoding UTF8
}

function Test-CodexTrusted([string] $ProjectPath) {
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        return $false
    }

    $projectKey = "[projects.'$ProjectPath']"
    $inProject = $false

    foreach ($line in Get-Content -LiteralPath $ConfigPath) {
        if ($line -eq $projectKey) {
            $inProject = $true
            continue
        }

        if ($inProject -and $line.StartsWith("[") -and $line.EndsWith("]")) {
            return $false
        }

        if ($inProject -and $line -match '^\s*trust_level\s*=\s*"trusted"\s*$') {
            return $true
        }
    }

    return $false
}

function Initialize-MemPalace([string] $Mode, [string] $ProjectPath, [string] $PalacePath) {
    $env:PYTHONIOENCODING = "utf-8"

    if (-not (Test-Path -LiteralPath $Python)) {
        throw "MemPalace venv Python not found at $Python"
    }

    if ($Mode -eq "local") {
        & $Python -m mempalace --palace $PalacePath init $ProjectPath --yes --no-llm --auto-mine
    } else {
        & $Python -m mempalace init $ProjectPath --yes --no-llm --auto-mine
    }

    if ($LASTEXITCODE -ne 0) {
        throw "MemPalace init failed with exit code $LASTEXITCODE"
    }
}

function Should-SkipPrompt {
    if ($env:CODEX_MEMPALACE_NO_PROMPT -eq "1") {
        return $true
    }

    if ($CodexArgs.Count -gt 0) {
        $first = $CodexArgs[0]
        if ($first -in @("mcp", "login", "logout", "completion", "help", "--help", "-h", "--version", "-V")) {
            return $true
        }
    }

    if (-not [Environment]::UserInteractive) {
        return $true
    }

    return $false
}

if (Should-SkipPrompt) {
    Invoke-RealCodex
}

$projectPath = Get-NormalizedPath (Get-Location).Path

if (-not (Test-CodexTrusted $projectPath)) {
    Set-MemPalaceMcp "off" $null
    Invoke-RealCodex
}

$state = Read-State
if (-not $state.Contains("folders")) {
    $state["folders"] = [ordered]@{}
}

$choice = $state["folders"][$projectPath]
$localPalace = Join-Path (Get-Location).Path ".mempalace"
$selectedNow = $false

if ([string]::IsNullOrWhiteSpace($choice)) {
    Write-Host ""
    Write-Host "Do you want to use MemPalace for this folder?"
    Write-Host "  1. Yes, enable MemPalace locally for this folder."
    Write-Host "  2. Yes, but use global MemPalace."
    Write-Host "  3. No, but ask me next time."
    Write-Host "  4. No, and don't ask again."
    Write-Host ""
    $answer = Read-Host "Choose 1-4"

    switch ($answer) {
        "1" { $choice = "local"; $selectedNow = $true }
        "2" { $choice = "global"; $selectedNow = $true }
        "4" { $choice = "disabled"; $state["folders"][$projectPath] = $choice; Write-State $state }
        default { $choice = "ask" }
    }
}

switch ($choice) {
    "local" {
        if ($selectedNow) {
            Initialize-MemPalace "local" (Get-Location).Path $localPalace
            $state["folders"][$projectPath] = $choice
            Write-State $state
        }
        Set-MemPalaceMcp "local" $localPalace
    }
    "global" {
        if ($selectedNow) {
            Initialize-MemPalace "global" (Get-Location).Path $null
            $state["folders"][$projectPath] = $choice
            Write-State $state
        }
        Set-MemPalaceMcp "global" $null
    }
    default {
        Set-MemPalaceMcp "off" $null
    }
}

Invoke-RealCodex
