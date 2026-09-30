# Shared setup for the harness PowerShell tools. Dot-source it:  . "$PSScriptRoot\common.ps1"
# Gives: $Repo (repo root), $Cfg (harness/config.json < machine settings < harness/local.json), $Kit, $Game, $Mods (~mods),
#        $ModCfg (mod.json or $null), and Get-ModName [-Mod X] (explicit -Mod, else mod.json "name").
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path "$PSScriptRoot\..\..").Path

function Read-Json($path) { if (Test-Path $path) { Get-Content $path -Raw | ConvertFrom-Json } else { $null } }

$Cfg = Read-Json "$Repo\harness\config.json"
# Machine settings (written by setup.ps1) apply to every repo on this PC; harness\local.json overrides per repo.
$MachineSettings = "$env:LOCALAPPDATA\stalker2-modding-harness\settings.json"
foreach ($local in @((Read-Json $MachineSettings), (Read-Json "$Repo\harness\local.json"))) {
    if ($local) { foreach ($p in $local.PSObject.Properties) { $Cfg | Add-Member -Force -NotePropertyName $p.Name -NotePropertyValue $p.Value } }
}
$Kit  = $Cfg.kit  -replace '/', '\'
$Game = ($Cfg.game -replace '/', '\') + "\Stalker2"
$Mods = "$Game\Content\Paks\~mods"
$ModCfg = Read-Json "$Repo\mod.json"
$GameExe = "Stalker2-Win64-Shipping"
$EditorCmd = "$Kit\Stalker2\Binaries\Win64\Stalker2ModEditor-Win64-Shipping-Cmd.exe"
$Uproject = "$Kit\Stalker2\Stalker2.uproject"

function Get-ModName([string]$Mod) {
    if ($Mod) { return $Mod }
    if ($ModCfg -and $ModCfg.name) { return $ModCfg.name }
    throw "No -Mod given and no mod.json in $Repo"
}

function Test-GameRunning { [bool](Get-Process -Name $GameExe -ErrorAction SilentlyContinue) }

function Wait-GameClosed {
    while (Test-GameRunning) { Write-Host "Game is running - close it to continue..."; Start-Sleep -Seconds 10 }
}

# Mount order: priority = 3 + 100 * (N + 1) for a `_N_P` suffix. Kit-named paks mount at 3.
function Get-Priority([string]$key, [int]$default) {
    if ($ModCfg -and $ModCfg.PSObject.Properties[$key]) { return [int]$ModCfg.$key }
    return $default
}

# UAT (RunUAT / AutomationTool) runs one instance per machine: a second cook or CreatePlainMod fails at once with
# "A conflicting instance of AutomationTool is already running". Another session may be cooking; wait for it.
function Wait-UatFree {
    while (Get-CimInstance Win32_Process -Filter "Name='dotnet.exe'" | Where-Object { $_.CommandLine -match 'AutomationTool' }) {
        Write-Host "Another AutomationTool (cook) is running - waiting..."; Start-Sleep -Seconds 15
    }
}
