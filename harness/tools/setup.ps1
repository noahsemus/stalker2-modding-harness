# Do the automatable part of setting up a PC for the harness (the agent runs this; see docs/setup.md).
# Usage:  powershell -ExecutionPolicy Bypass -File harness\tools\setup.ps1 [-Install] [-Fork] [-EnableRemotePython]
#   (no switches)        find the Zone Kit and the game, read the GitHub login, save them in the machine settings, report
#   -Install             also install missing Git / GitHub CLI with winget (ask the user first)
#   -Fork                also fork the harness to the logged-in GitHub account and point this clone's origin at it
#   -EnableRemotePython  also turn on the editor's Python remote execution (Zone Kit editor must be closed)
# Everything per-user goes to the machine settings (%LOCALAPPDATA%\stalker2-modding-harness\settings.json), never into
# the repo. Idempotent: safe to run again. Ends with check_setup.ps1.
param([switch]$Install, [switch]$Fork, [switch]$EnableRemotePython)
. "$PSScriptRoot\common.ps1"
$ErrorActionPreference = "Continue"
$settings = [ordered]@{}
$old = Read-Json $MachineSettings
if ($old) { foreach ($p in $old.PSObject.Properties) { $settings[$p.Name] = $p.Value } }
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") }

# 1. Zone Kit: already known and valid, else the Epic launcher's install manifests
if ($Cfg.kit -and (Test-Path "$Kit\CreatePlainMod.bat")) { $settings.kit = $Cfg.kit; Write-Host "Zone Kit: $Kit" }
else {
    $found = Get-ChildItem "$env:ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-Content $_.FullName -Raw | ConvertFrom-Json } |
        Where-Object { $_.DisplayName -match "Zone Kit" -or (Test-Path "$($_.InstallLocation)\CreatePlainMod.bat") } |
        Select-Object -First 1
    if ($found) { $settings.kit = ($found.InstallLocation -replace '\\', '/'); Write-Host "Zone Kit found: $($found.InstallLocation)" }
    else { Write-Host "Zone Kit NOT found. The user must install 'S.T.A.L.K.E.R. 2 Zone Kit' from the Epic Games Store." }
}

# 2. Game: already known and valid, else every Steam library
$gameRel = "steamapps\common\S.T.A.L.K.E.R. 2 Heart of Chornobyl"
if ($Cfg.game -and (Test-Path "$Game\Content\Paks")) { $settings.game = $Cfg.game; Write-Host "Game: $Game" }
else {
    $libs = @()
    $steam = (Get-ItemProperty "HKCU:\Software\Valve\Steam" -ErrorAction SilentlyContinue).SteamPath
    if ($steam) {
        $libs += $steam
        $vdf = "$steam\steamapps\libraryfolders.vdf"
        if (Test-Path $vdf) { $libs += [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"') | ForEach-Object { $_.Groups[1].Value -replace '\\\\', '\' } }
    }
    $hit = $libs | Where-Object { Test-Path (Join-Path $_ "$gameRel\Stalker2\Content\Paks") } | Select-Object -First 1
    if ($hit) { $settings.game = ((Join-Path $hit $gameRel) -replace '\\', '/'); Write-Host "Game found: $(Join-Path $hit $gameRel)" }
    else { Write-Host "Game NOT found in Steam libraries. Ask the user where it is installed (the folder that contains 'Stalker2') and add it to $MachineSettings as `"game`" (forward slashes)." }
}

# 3. Git and GitHub CLI
foreach ($t in @(@{ cmd = "git"; id = "Git.Git" }, @{ cmd = "gh"; id = "GitHub.cli" })) {
    if (-not (Has $t.cmd)) {
        if ($Install) { winget install --id $t.id -e --accept-source-agreements --accept-package-agreements; Refresh-Path }
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
    $ini = ($settings.kit -replace '/', '\') + "\Stalker2\Config\DefaultEngine.ini"
    if (Test-Path $ini) {
        $text = Get-Content $ini -Raw
        if ($text -match '(?m)^bRemoteExecution=True') { Write-Host "Editor remote Python: on" }
        elseif ($EnableRemotePython) {
            if (Get-Process Stalker2ModEditor* -ErrorAction SilentlyContinue) { Write-Host "Close the Zone Kit editor first, then re-run with -EnableRemotePython." }
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

& powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\check_setup.ps1"
