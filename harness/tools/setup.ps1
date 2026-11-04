# Do the automatable part of setting up a PC for the harness (the agent runs this; see docs/setup.md).
# Usage:  powershell -ExecutionPolicy Bypass -File harness\tools\setup.ps1 [-Install] [-Fork] [-EnableRemotePython]
#         Linux (Proton): pwsh -File harness/tools/setup.ps1 [-Fork] [-EnableRemotePython]   (docs/linux-proton.md)
#   (no switches)        find the Zone Kit and the game, read the GitHub login, save them in the machine settings, report
#   -Install             also install missing Git / GitHub CLI with winget (ask the user first; Windows only)
#   -Fork                also fork the harness to the logged-in GitHub account and point this clone's origin at it
#   -EnableRemotePython  also turn on the editor's Python remote execution (Zone Kit editor must be closed)
# Everything per-user goes to the machine settings (%LOCALAPPDATA%\stalker2-modding-harness\settings.json; on Linux
# ~/.config/stalker2-modding-harness/settings.json), never into the repo. Idempotent: safe to run again. Ends with
# check_setup.ps1. On Linux it also records the Proton `wine`, the kit's Wine prefix (both from Heroic, which installs
# the Zone Kit there) and the game's Proton prefix (Steam compatdata).
param([switch]$Install, [switch]$Fork, [switch]$EnableRemotePython)
. "$PSScriptRoot\common.ps1"
$ErrorActionPreference = "Continue"
$settings = [ordered]@{}
$old = Read-Json $MachineSettings
if ($old) { foreach ($p in $old.PSObject.Properties) { $settings[$p.Name] = $p.Value } }
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") }

# 1. Zone Kit: already known and valid, else the Epic launcher's install manifests (Heroic's on Linux)
if ($OnLinux) {
    # Heroic (native or Flatpak) keeps Epic installs in legendaryConfig and per-game Wine settings in GamesConfig.
    $heroic = @("$HOME/.config/heroic", "$HOME/.var/app/com.heroicgameslauncher.hgl/config/heroic") | Where-Object { Test-Path $_ }
    $kitApp = $null; $kitHeroic = $null
    foreach ($h in $heroic) {
        $inst = Read-Json "$h/legendaryConfig/legendary/installed.json"
        if (-not $inst) { continue }
        foreach ($p in $inst.PSObject.Properties) {
            if ($p.Value.title -match "Zone Kit" -or ($p.Value.install_path -and (Test-Path "$($p.Value.install_path)/CreatePlainMod.bat"))) {
                $kitApp = $p.Name; $kitHeroic = $h; $kitPath = $p.Value.install_path; break
            }
        }
        if ($kitApp) { break }
    }
    if ($Cfg.kit -and (Test-Path "$Kit/CreatePlainMod.bat")) { $settings.kit = $Cfg.kit; Write-Host "Zone Kit: $Kit" }
    elseif ($kitApp) { $settings.kit = $kitPath; Write-Host "Zone Kit found (Heroic): $kitPath" }
    else { Write-Host "Zone Kit NOT found. Install 'S.T.A.L.K.E.R. 2 Zone Kit' with the Heroic Games Launcher (Epic account), or add `"kit`" to $MachineSettings." }

    # Wine prefix and Proton build the kit runs with (Heroic: game settings > Wine). The tools call <proton>/files/bin/wine.
    $gc = if ($kitApp) { Read-Json "$kitHeroic/GamesConfig/$kitApp.json" } else { $null }
    $g = if ($gc) { $gc.$kitApp } else { $null }
    if ($Cfg.kit_prefix -and (Test-Path "$($Cfg.kit_prefix)/drive_c")) { $settings.kit_prefix = $Cfg.kit_prefix }
    elseif ($g -and $g.winePrefix) { $settings.kit_prefix = $g.winePrefix; Write-Host "Zone Kit Wine prefix: $($g.winePrefix)" }
    else { Write-Host "Zone Kit Wine prefix unknown: set `"kit_prefix`" in $MachineSettings (Heroic: the game's settings > Wine prefix)." }
    if ($Cfg.wine -and (Test-Path $Cfg.wine)) { $settings.wine = $Cfg.wine }
    elseif ($g -and $g.wineVersion -and $g.wineVersion.bin) {
        $bin = $g.wineVersion.bin
        $wine = if ($g.wineVersion.type -eq "proton") {
            @("files/bin/wine", "dist/bin/wine") | ForEach-Object { Join-Path (Split-Path $bin) $_ } | Where-Object { Test-Path $_ } | Select-Object -First 1
        } else { $bin }
        if ($wine) { $settings.wine = $wine; Write-Host "Proton wine: $wine" }
        else { Write-Host "No wine binary next to $bin: set `"wine`" in $MachineSettings to <proton>/files/bin/wine." }
    } else { Write-Host "Proton/Wine build unknown: set `"wine`" in $MachineSettings to <proton>/files/bin/wine (e.g. a GE-Proton in compatibilitytools.d)." }
}
elseif ($Cfg.kit -and (Test-Path "$Kit\CreatePlainMod.bat")) { $settings.kit = $Cfg.kit; Write-Host "Zone Kit: $Kit" }
else {
    $found = Get-ChildItem "$env:ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-Content $_.FullName -Raw | ConvertFrom-Json } |
        Where-Object { $_.DisplayName -match "Zone Kit" -or (Test-Path "$($_.InstallLocation)\CreatePlainMod.bat") } |
        Select-Object -First 1
    if ($found) { $settings.kit = ($found.InstallLocation -replace '\\', '/'); Write-Host "Zone Kit found: $($found.InstallLocation)" }
    else { Write-Host "Zone Kit NOT found. The user must install 'S.T.A.L.K.E.R. 2 Zone Kit' from the Epic Games Store." }
}

# 2. Game: already known and valid, else every Steam library
$gameRel = ConvertTo-NativePath "steamapps\common\S.T.A.L.K.E.R. 2 Heart of Chornobyl"
$libs = @()
$steamRoots = if ($OnLinux) {
    @("$HOME/.local/share/Steam", "$HOME/.steam/steam", "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam") | Where-Object { Test-Path $_ }
} else { @((Get-ItemProperty "HKCU:\Software\Valve\Steam" -ErrorAction SilentlyContinue).SteamPath) | Where-Object { $_ } }
foreach ($steam in $steamRoots) {
    $libs += $steam
    $vdf = Join-Path $steam "steamapps/libraryfolders.vdf"
    if (Test-Path $vdf) { $libs += [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"') | ForEach-Object { ConvertTo-NativePath ($_.Groups[1].Value -replace '\\\\', '\') } }
}
if ($Cfg.game -and (Test-Path "$Game\Content\Paks")) { $settings.game = $Cfg.game; Write-Host "Game: $Game" }
else {
    $hit = $libs | Where-Object { Test-Path (Join-Path $_ "$gameRel\Stalker2\Content\Paks") } | Select-Object -First 1
    if ($hit) { $settings.game = ((Join-Path $hit $gameRel) -replace '\\', '/'); Write-Host "Game found: $(Join-Path $hit $gameRel)" }
    else { Write-Host "Game NOT found in Steam libraries. Ask the user where it is installed (the folder that contains 'Stalker2') and add it to $MachineSettings as `"game`" (forward slashes)." }
}

# Linux: the game's Proton prefix (Steam compatdata of app 1643320) holds what Windows keeps in %LOCALAPPDATA%\Stalker2.
if ($OnLinux) {
    if ($Cfg.game_prefix -and (Test-Path "$($Cfg.game_prefix)/drive_c")) { $settings.game_prefix = $Cfg.game_prefix }
    else {
        $pfx = $libs | ForEach-Object { Join-Path $_ "steamapps/compatdata/1643320/pfx" } | Where-Object { Test-Path "$_/drive_c" } | Select-Object -First 1
        if ($pfx) { $settings.game_prefix = $pfx; Write-Host "Game Proton prefix: $pfx" }
        else { Write-Host "Game Proton prefix not found: start the game once through Steam (Proton), then run this again." }
    }
}

# 3. Git and GitHub CLI
foreach ($t in @(@{ cmd = "git"; id = "Git.Git" }, @{ cmd = "gh"; id = "GitHub.cli" })) {
    if (-not (Has $t.cmd)) {
        if ($OnLinux) { Write-Host "$($t.cmd) missing: install it with the distribution's package manager." }
        elseif ($Install) { winget install --id $t.id -e --accept-source-agreements --accept-package-agreements; Refresh-Path }
        else { Write-Host "$($t.cmd) missing: re-run with -Install (after asking the user) or: winget install --id $($t.id) -e" }
    }
}

# 4. GitHub account -> github_owner (harness_remote_url then defaults to that account's copy of the harness)
$ghOk = $false; if (Has gh) { gh auth status *> $null; $ghOk = ($LASTEXITCODE -eq 0) }
if ($ghOk) {
    $me = (gh api user --jq .login).Trim()
    $settings.github_owner = $me
    Write-Host "GitHub account: $me (new mods are published under it)"
    $upstreamOwner = if ($Cfg.upstream_url -match 'github\.com/([^/]+)/') { $Matches[1] } else { "" }
    if ($me -ne $upstreamOwner) {
        Push-Location $Repo
        $origin = (git remote get-url origin 2>$null)
        if ($origin -match "/$me/") { Write-Host "Harness origin is already $me's fork." }
        elseif ($Fork) {
            gh repo fork --remote --remote-name origin   # the original becomes 'upstream'
            Write-Host "Forked the harness to $me; origin = the fork, upstream = the original."
        } else { Write-Host "The harness is not forked to $me yet: re-run with -Fork." }
        Pop-Location
    }
} elseif (Has gh) {
    Write-Host "Not logged in to GitHub. Run: gh auth login --hostname github.com --git-protocol https --web  (the user completes it in the browser)"
}

# 5. Editor remote Python (Project Settings > Plugins > Python > Enable Remote Execution), written to the kit's ini
if ($settings.kit) {
    $ini = ConvertTo-NativePath "$($settings.kit)/Stalker2/Config/DefaultEngine.ini"
    if (Test-Path $ini) {
        $text = Get-Content $ini -Raw
        if ($text -match '(?m)^bRemoteExecution=True') { Write-Host "Editor remote Python: on" }
        elseif ($EnableRemotePython) {
            if (Test-EditorRunning) { Write-Host "Close the Zone Kit editor first, then re-run with -EnableRemotePython." }
            else {
                Copy-Item $ini "$ini.bak_harness" -Force
                $sec = '[/Script/PythonScriptPlugin.PythonScriptPluginSettings]'
                if ($text.Contains($sec)) { $text = $text.Replace($sec, "$sec`r`nbRemoteExecution=True") -replace '(?m)^bRemoteExecution=False\r?\n', '' }
                else { $text = $text.TrimEnd() + "`r`n`r`n$sec`r`nbRemoteExecution=True`r`n" }
                [IO.File]::WriteAllText($ini, $text, (New-Object Text.UTF8Encoding $false))
                Write-Host "Editor remote Python: turned on (backup $ini.bak_harness)"
            }
        } else { Write-Host "Editor remote Python: off. Re-run with -EnableRemotePython while the editor is closed." }
    }
}

# 6. Save the machine settings
New-Item -ItemType Directory -Force (Split-Path $MachineSettings) | Out-Null
[IO.File]::WriteAllText($MachineSettings, ($settings | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
Write-Host "Saved $MachineSettings"

# the same PowerShell that runs this script (powershell.exe, or pwsh on Linux)
& (Get-Process -Id $PID).Path -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "check_setup.ps1")
