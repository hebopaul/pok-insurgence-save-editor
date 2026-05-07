$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

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
