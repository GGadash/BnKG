[CmdletBinding()]
param([switch]$NoLaunch, [switch]$CheckOnly, [string]$PythonExe = '')
$ErrorActionPreference = 'Stop'
# Process-only execution policy from the CMD wrapper; no persistent policy change.
$probe = "import sys,struct; assert (3,12)<=sys.version_info[:2]<(3,15) and struct.calcsize('P')==8; print(sys._base_executable)"
$chosen = $null
function Find-Python([string]$Exe, [string[]]$Prefix) {
    try {
        $result = & $Exe @Prefix -c $probe 2>$null
        if ($LASTEXITCODE -eq 0 -and $result) {
            $candidate = ([string]($result | Select-Object -Last 1)).Trim()
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
        }
    } catch { }
    return $null
}
if ($PythonExe) {
    $chosen = Find-Python $PythonExe @()
} else {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($version in @('-3.12', '-3.13', '-3.14')) {
            $chosen = Find-Python $launcher.Source @($version)
            if ($chosen) { break }
        }
    }
    if (-not $chosen) {
        $projectRoot = Split-Path -Parent $PSScriptRoot
        # Read old environment metadata to find its installed base Python after a move.
        $candidates = Get-ChildItem -LiteralPath $projectRoot -Directory -Force | Where-Object { $_.Name -eq '.venv' -or $_.Name -like '.venv-before-move*' } | Sort-Object LastWriteTime -Descending
        foreach ($candidate in $candidates) {
            $config = Join-Path $candidate.FullName 'pyvenv.cfg'
            if (Test-Path -LiteralPath $config -PathType Leaf) {
                $homeLine = Get-Content -LiteralPath $config | Where-Object { $_ -match '^home\s*=' } | Select-Object -First 1
                if ($homeLine) {
                    $baseDir = ($homeLine -split '=', 2)[1].Trim()
                    $basePython = Join-Path $baseDir 'python.exe'
                    if (Test-Path -LiteralPath $basePython -PathType Leaf) { $chosen = Find-Python $basePython @() }
                    if ($chosen) { break }
                }
            }
        }
    }
    if (-not $chosen) {
        $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($pythonCommand) { $chosen = Find-Python $pythonCommand.Source @() }
    }
}
if (-not $chosen) {
    Write-Host '[FAILED: Find Python] Install 64-bit Python 3.12 (recommended), 3.13 or 3.14 with the Python launcher, then rerun this file.' -ForegroundColor Red
    Write-Host 'You can also run scripts\Setup-BnKG.ps1 -PythonExe "C:\Python312\python.exe". No project files were changed.'
    exit 1
}
Write-Host "[PASS: Find Python] $chosen"
$helper = Join-Path $PSScriptRoot 'setup_after_move.py'
$helperArgs = @($helper)
if ($NoLaunch) { $helperArgs += '--no-launch' }
if ($CheckOnly) { $helperArgs += '--check-only' }
& $chosen @helperArgs
exit $LASTEXITCODE
