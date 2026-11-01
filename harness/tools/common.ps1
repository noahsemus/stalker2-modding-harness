# Shared setup for the harness PowerShell tools. Dot-source it:  . "$PSScriptRoot\common.ps1"
# Gives: $Repo (repo root), $Cfg (harness/config.json < machine settings < harness/local.json), $Kit, $Game, $Mods (~mods),
#        $ModCfg (mod.json or $null), and Get-ModName [-Mod X] (explicit -Mod, else mod.json "name").
# Windows (PowerShell 5.1 or 7) and Linux (PowerShell 7 + Proton/Wine, docs/linux-proton.md) share these tools. On
# Linux every Windows program (RunUAT, the editor, UnrealPak) goes through Invoke-Win, which runs it with the Proton
# `wine` in the kit's prefix and turns Linux path arguments into Wine drive paths.
$ErrorActionPreference = "Stop"
$OnLinux = [bool]$IsLinux   # automatic variable in PowerShell 7; $null (false) in Windows PowerShell 5.1
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path

function Read-Json($path) { if (Test-Path $path) { Get-Content $path -Raw | ConvertFrom-Json } else { $null } }

# Machine settings (written by setup.ps1) apply to every repo on this PC; harness\local.json overrides per repo.
$HarnessHome = if ($OnLinux) {
    Join-Path $(if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $HOME ".config" }) "stalker2-modding-harness"
} else { "$env:LOCALAPPDATA\stalker2-modding-harness" }
$MachineSettings = Join-Path $HarnessHome "settings.json"
$Temp = [IO.Path]::GetTempPath().TrimEnd('\', '/')

$Cfg = Read-Json (Join-Path $Repo "harness/config.json")
foreach ($local in @((Read-Json $MachineSettings), (Read-Json (Join-Path $Repo "harness/local.json")))) {
    if ($local) { foreach ($p in $local.PSObject.Properties) { $Cfg | Add-Member -Force -NotePropertyName $p.Name -NotePropertyValue $p.Value } }
}
if (-not $Cfg.harness_remote_url -and $Cfg.github_owner) {
    $Cfg | Add-Member -Force -NotePropertyName harness_remote_url -NotePropertyValue "https://github.com/$($Cfg.github_owner)/stalker2-modding-harness.git"
}

# Tools call this for the settings they need; config.json ships empty values, setup.ps1 fills them per machine.
function Assert-Setup([string[]]$Keys = @("kit", "game")) {
    if ($OnLinux -and ($Keys -contains "kit")) { $Keys += @("wine", "kit_prefix") }
    $missing = $Keys | Where-Object { -not $Cfg.$_ }
    if ($missing) { throw "Not set up on this PC yet ($($missing -join ', ') missing). Run: $(Get-ToolCommand setup.ps1)" }
}

# A path in this OS's own form (settings store forward slashes).
function ConvertTo-NativePath([string]$p) { if ($OnLinux) { $p -replace '\\', '/' } else { $p -replace '/', '\' } }

$Kit  = ConvertTo-NativePath $Cfg.kit
$Game = (ConvertTo-NativePath $Cfg.game) + $(if ($OnLinux) { "/Stalker2" } else { "\Stalker2" })
$Mods = ConvertTo-NativePath "$Game/Content/Paks/~mods"
$ModCfg = Read-Json (Join-Path $Repo "mod.json")
$GameExe = "Stalker2-Win64-Shipping"
$EditorCmd = ConvertTo-NativePath "$Kit/Stalker2/Binaries/Win64/Stalker2ModEditor-Win64-Shipping-Cmd.exe"
$Uproject = ConvertTo-NativePath "$Kit/Stalker2/Stalker2.uproject"
# The game's %LOCALAPPDATA%\Stalker2 (logs, crashes, saves, rebinds). On Linux it is inside the game's Proton prefix.
$GameUserDir = if ($OnLinux) { "$($Cfg.game_prefix)/drive_c/users/steamuser/AppData/Local/Stalker2" } else { "$env:LOCALAPPDATA\Stalker2" }
# Python for tools that run outside the editor: the kit's embedded 3.11 on Windows, the system python3 on Linux.
$Py = if ($OnLinux) { "python3" } else { "$Kit\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" }

# How to tell the user / agent to run another tool on this OS.
function Get-ToolCommand([string]$Tool) {
    if ($OnLinux) { "pwsh -File harness/tools/$Tool" } else { "powershell -ExecutionPolicy Bypass -File harness\tools\$Tool" }
}

# --- Wine / Proton (Linux only) -------------------------------------------------------------------------------------
# Drive letters of the kit's prefix (dosdevices\x: -> /some/dir), longest target first, so a path maps to the most
# specific drive the way `winepath -w` does. Every prefix has z: -> / ; extra drives (e.g. u: -> /media) are honoured.
$WineDrives = @()
if ($OnLinux -and $Cfg.kit_prefix -and (Test-Path (Join-Path $Cfg.kit_prefix "dosdevices"))) {
    $WineDrives = @(Get-ChildItem (Join-Path $Cfg.kit_prefix "dosdevices") | Where-Object { $_.Name -match '^[a-z]:$' -and $_.LinkTarget } |
        ForEach-Object {
            $t = $_.LinkTarget
            if (-not $t.StartsWith('/')) { $t = [IO.Path]::GetFullPath((Join-Path (Join-Path $Cfg.kit_prefix "dosdevices") $t)) }
            [pscustomobject]@{ Letter = $_.Name.ToUpper(); Target = $t.TrimEnd('/') }
        } | Sort-Object { $_.Target.Length } -Descending)
}

# Linux path -> Wine path (Z:\media\x or the drive the prefix maps it to). Anything else is returned unchanged.
function ConvertTo-WinPath([string]$p) {
    if (-not $OnLinux) { return $p }
    $u = $p -replace '\\', '/'
    if (-not $u.StartsWith('/')) { return $p }
    foreach ($d in $WineDrives) {
        if ($d.Target -eq '' -or $u -eq $d.Target -or $u.StartsWith($d.Target + '/')) {
            return $d.Letter + ($u.Substring($d.Target.Length) -replace '/', '\')
        }
    }
    return 'Z:' + ($u -replace '/', '\')
}

# One command-line argument: a bare Linux path, or "-Key=<Linux path>", becomes its Wine path.
function ConvertTo-WinArg([string]$a) {
    if (-not $OnLinux) { return $a }
    if ($a -match '^(-[^=]+=)(.*)$' -and ($Matches[2] -replace '\\', '/').StartsWith('/')) { return $Matches[1] + (ConvertTo-WinPath $Matches[2]) }
    return ConvertTo-WinPath $a
}

# Run a Windows program (exe or .bat): directly on Windows, through Proton's wine in the kit's prefix on Linux.
# Output and $LASTEXITCODE behave like calling the program with &, so `Invoke-Win ... *> $log` works on both.
function Invoke-Win([string]$Exe, [string[]]$ArgList = @()) {
    if (-not $OnLinux) { & $Exe @ArgList; return }
    $env:WINEPREFIX = $Cfg.kit_prefix
    if (-not $env:WINEDEBUG) { $env:WINEDEBUG = "-all" }
    & $Cfg.wine (ConvertTo-WinPath $Exe) @($ArgList | ForEach-Object { ConvertTo-WinArg $_ })
}

# --- Processes ------------------------------------------------------------------------------------------------------
# Command lines of running processes matching a regex. On Linux Wine processes keep the .exe path in their arguments.
function Find-ProcessLine([string]$Pattern) {
    if ($OnLinux) { @(& ps -eo args 2>$null) -match $Pattern }
    else { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match $Pattern } | ForEach-Object { $_.CommandLine }) }
}

function Test-GameRunning {
    if ($OnLinux) { [bool](Find-ProcessLine "$GameExe\.exe") }
    else { [bool](Get-Process -Name $GameExe -ErrorAction SilentlyContinue) }
}

# The interactive Zone Kit editor (the -Cmd build used by cooks and headless runs does not count on Linux).
function Test-EditorRunning {
    if ($OnLinux) { [bool](Find-ProcessLine 'Stalker2ModEditor-Win64-Shipping\.exe') }
    else { [bool](Get-Process Stalker2ModEditor* -ErrorAction SilentlyContinue) }
}

function Wait-GameClosed {
    while (Test-GameRunning) { Write-Host "Game is running - close it to continue..."; Start-Sleep -Seconds 10 }
}

function Get-ModName([string]$Mod) {
    if ($Mod) { return $Mod }
    if ($ModCfg -and $ModCfg.name) { return $ModCfg.name }
    throw "No -Mod given and no mod.json in $Repo"
}

# Mount order: priority = 3 + 100 * (N + 1) for a `_N_P` suffix. Kit-named paks mount at 3.
function Get-Priority([string]$key, [int]$default) {
    if ($ModCfg -and $ModCfg.PSObject.Properties[$key]) { return [int]$ModCfg.$key }
    return $default
}

# UAT (RunUAT / AutomationTool) runs one instance per machine: a second cook or CreatePlainMod fails at once with
# "A conflicting instance of AutomationTool is already running". Another session may be cooking; wait for it.
function Wait-UatFree {
    while ($(if ($OnLinux) { Find-ProcessLine 'AutomationTool' }
             else { Get-CimInstance Win32_Process -Filter "Name='dotnet.exe'" | Where-Object { $_.CommandLine -match 'AutomationTool' } })) {
        Write-Host "Another AutomationTool (cook) is running - waiting..."; Start-Sleep -Seconds 15
    }
}

# Mirror a folder (robocopy /MIR on Windows, rsync --delete on Linux): files missing in $Src are deleted in $Dst.
function Sync-Dir([string]$Src, [string]$Dst, [switch]$WhatIf, [switch]$Quiet) {
    New-Item -ItemType Directory -Force $Dst | Out-Null
    if ($OnLinux) {
        $flags = @("-a", "--delete") + $(if ($WhatIf) { @("-n", "-v") } elseif (-not $Quiet) { @("-v") } else { @() })
        $out = & rsync @flags "$((ConvertTo-NativePath $Src).TrimEnd('/'))/" "$((ConvertTo-NativePath $Dst).TrimEnd('/'))/"
    } else {
        $flags = @("/MIR", "/NJH", "/NJS", "/NP", "/NDL") + $(if ($WhatIf) { @("/L") } else { @() })
        $out = robocopy $Src $Dst @flags
    }
    if (-not $Quiet) { $out | Where-Object { "$_".Trim() } }
}
