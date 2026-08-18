$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# PowerShell parameter binding is case-insensitive, but the release workflow
# intentionally distinguishes -v from -V. Parse the untouched arguments with
# case-sensitive comparisons instead of declaring a param() block.
if ($args.Count -gt 1) {
    throw 'Usage: .\build.ps1 [-v|-V]'
}

$versionBump = 'none'
if ($args.Count -eq 1) {
    if ($args[0] -ceq '-v') {
        $versionBump = 'small'
    }
    elseif ($args[0] -ceq '-V') {
        $versionBump = 'major'
    }
    else {
        throw "Unknown option '$($args[0])'. Usage: .\build.ps1 [-v|-V]"
    }
}

$versionLogPath = Join-Path $scriptDir 'version_history.txt'
$targetVersion = $null
if ($versionBump -ne 'none') {
    if (-not (Test-Path -LiteralPath $versionLogPath -PathType Leaf)) {
        throw "Version log not found: $versionLogPath"
    }

    $versionEntries = @(
        Get-Content -LiteralPath $versionLogPath |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and -not $_.StartsWith('#') }
    )
    if ($versionEntries.Count -eq 0) {
        throw 'The version log does not contain a version.'
    }

    $currentVersionText = $versionEntries[-1]
    if ($currentVersionText -notmatch '^\d+\.\d+\.\d+$') {
        throw "Invalid current version '$currentVersionText' in version_history.txt. Expected MAJOR.MINOR.PATCH."
    }
    $currentVersion = [Version]$currentVersionText

    switch ($versionBump) {
        'small' {
            $targetVersion = '{0}.{1}.{2}' -f $currentVersion.Major, $currentVersion.Minor, ($currentVersion.Build + 1)
        }
        'major' {
            $targetVersion = '{0}.{1}.0' -f $currentVersion.Major, ($currentVersion.Minor + 1)
        }
    }
}

$env:PYGAME_HIDE_SUPPORT_PROMPT = '1'
$env:PYTHONWARNINGS = 'ignore:pkg_resources is deprecated as an API:UserWarning'

$pythonPrefix = (& python -c "import sys; print(sys.base_prefix)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $pythonPrefix) {
    throw 'Python is required to build this project.'
}

$tclCandidates = @(
    'C:\Program Files\Git\mingw64\lib\tcl8.6',
    (Join-Path $pythonPrefix 'tcl\tcl8.6')
)
$tkCandidates = @(
    'C:\Program Files\Git\mingw64\lib\tk8.6',
    (Join-Path $pythonPrefix 'tcl\tk8.6')
)

$env:TCL_LIBRARY = $tclCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$env:TK_LIBRARY = $tkCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $env:TCL_LIBRARY) {
    throw 'Could not find Tcl 8.6. Install Python with Tcl/Tk support or Git for Windows.'
}
if (-not $env:TK_LIBRARY) {
    throw 'Could not find Tk 8.6. Install Python with Tcl/Tk support or Git for Windows.'
}

$pyinstaller = Get-Command pyinstaller -ErrorAction Stop
& $pyinstaller.Source 'Pokemon Insurgence Save Editor.spec' --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$exePath = Join-Path $scriptDir 'dist\Pokemon Insurgence Save Editor.exe'
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Build completed without producing the expected executable: $exePath"
}

if ($versionBump -ne 'none') {
    $archiveName = "Pokemon.Insurgence.Save.Editor.v$targetVersion.zip"
    $archivePath = Join-Path $scriptDir "dist\$archiveName"
    Compress-Archive -LiteralPath $exePath -DestinationPath $archivePath -CompressionLevel Optimal -Force
    Add-Content -LiteralPath $versionLogPath -Value $targetVersion
    Write-Host "Created dist\$archiveName"
}
else {
    Write-Host 'Created dist\Pokemon Insurgence Save Editor.exe (no version bump or ZIP)'
}
