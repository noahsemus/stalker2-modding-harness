# Run an editor Python script headlessly (commandlet, ~4.5 min to boot). Needed for anything that must not run in
# the open editor: duplicate_asset from /Game sources, asset moves/renames, class-default edits.
# Usage:  powershell -File harness\tools\run_headless.ps1 -Script <file.py> [-Mod X] [-Arg "SRC=/a","DST=/b"]   (Linux: pwsh -File ...)
# CLOSE the editor first for scripts that move/rename/save assets (a second editor instance makes the commandlet
# exit before the script). The script gets the same prelude as ue_exec.py (MOD, MOD_ROOT, UPLUGIN, SCRATCH, ...).
param([Parameter(Mandatory)][string]$Script, [string]$Mod, [string[]]$Arg = @())
. "$PSScriptRoot\common.ps1"
Assert-Setup kit
$Mod = Get-ModName $Mod
$tmp = Join-Path $Temp "harness_headless_$([IO.Path]::GetFileNameWithoutExtension($Script)).py"
$env:HARNESS_ARGS = ($Arg -join "`n")
$pre = & $Py -c "import os, sys; sys.path.insert(0, r'$PSScriptRoot'); from hconf import prelude; kv = dict(l.split('=', 1) for l in os.environ.get('HARNESS_ARGS', '').splitlines() if '=' in l); print(prelude('$Mod', kv), end='')"
[IO.File]::WriteAllText($tmp, ($pre -join "`n") + "`n" + [IO.File]::ReadAllText((Resolve-Path $Script)), (New-Object Text.UTF8Encoding $false))
$log = Join-Path $Temp "harness_headless.log"
Write-Host "Running $Script headless for $Mod (log: $log) ..."
# The editor writes to stderr (e.g. "ChromaSDKPlugin failed to load!"); under PowerShell 5.1 with "Stop" that aborts
# this script before the summary, although the commandlet keeps running. It also exits 1 on its usual 2 log errors.
$ErrorActionPreference = "Continue"
Invoke-Win $EditorCmd @("$Uproject", "-run=pythonscript", "-script=$tmp", "-unattended", "-nosplash", "-stdout", "-NoShaderCompile") *> $log
$ErrorActionPreference = "Stop"
Write-Host "Exit $LASTEXITCODE. Script lines:"
Select-String -Path $log -Pattern "\[harness\]|Error|EXCEPTION|Traceback" | Select-Object -Last 60 | ForEach-Object { $_.Line }
