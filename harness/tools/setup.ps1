# Do the automatable part of setting up a machine for the harness (the agent runs this; see docs/setup.md).
# Usage:  powershell -ExecutionPolicy Bypass -File harness\tools\setup.ps1 [-Install] [-Fork] [-EnableRemotePython]
#   (no switches)        find the Zone Kit and the game, read the GitHub login, write the machine settings, report
#   -Install             also install missing Git / GitHub CLI with winget (ask the user first)
#   -Fork                also fork the harness to the logged-in GitHub account and point this clone's origin at it
#   -EnableRemotePython  also turn on the editor's Python remote execution (Zone Kit editor must be closed)
# Idempotent: safe to run again. Ends with check_setup.ps1.
param([switch]$Install, [switch]$Fork, [switch]$EnableRemotePython)
. "$PSScriptRoot\common.ps1"
$ErrorActionPreference = "Continue"
$base = Read-Json "$Repo\harness\config.json"
$localPath = $MachineSettings   # %LOCALAPPDATA%\stalker2-modding-harness\settings.json, shared by every repo
$local = @{}
$old = Read-Json $localPath
if ($old) { foreach ($p in $old.PSObject.Properties) { $local[$p.Name] = $p.Value } }
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") }

# 1. Zone Kit: configured path, else the Epic launcher's install manifests
if (-not (Test-Path "$Kit\CreatePlainMod.bat")) {
    $found = Get-ChildItem "$env:ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-Content $_.FullName -Raw | ConvertFrom-Json } |
        Where-Object { $_.DisplayName -match "Zone Kit" -or (Test-Path "$($_.InstallLocation)\CreatePlainMod.bat") } |
        Select-Object -First 1
    if ($found) { $local.kit = ($found.InstallLocation -replace '\\', '/'); Write-Host "Zone Kit found: $($found.InstallLocation)" }
    else { Write-Host "Zone Kit NOT found. The user must install 'S.T.A.L.K.E.R. 2 Zone Kit' from the Epic Games Store." }
} else { Write-Host "Zone Kit: $Kit" }

# 2. Game: configured path, else every Steam library
$gameRel = "steamapps\common\S.T.A.L.K.E.R. 2 Heart of Chornobyl"
if (-not (Test-Path "$Game\Content\Paks")) {
    $libs = @()
    $steam = (Get-ItemProperty "HKCU:\Software\Valve\Steam" -ErrorAction SilentlyContinue).SteamPath
    if ($steam) {
        $libs += $steam
        $vdf = "$steam\steamapps\libraryfolders.vdf"
        if (Test-Path $vdf) { $libs += [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"') | ForEach-Object { $_.Groups[1].Value -replace '\\\\', '\' } }
    }
    $hit = $libs | Where-Object { Test-Path (Join-Path $_ "$gameRel\Stalker2\Content\Paks") } | Select-Object -First 1
    if ($hit) { $local.game = ((Join-Path $hit $gameRel) -replace '\\', '/'); Write-Host "Game found: $(Join-Path $hit $gameRel)" }
    else { Write-Host "Game NOT found in Steam libraries. Ask the user where it is installed (the folder containing 'Stalker2') and put it in  as `"game`" (forward slashes)." }
} else { Write-Host "Game: $Game" }

# 3. Git and GitHub CLI
foreach ($t in @(@{ cmd = "git"; id = "Git.Git" }, @{ cmd = "gh"; id = "GitHub.cli" })) {
    if (-not (Has $t.cmd)) {
        if ($Install) { winget install --id $t.id -e --accept-source-agreements --accept-package-agreements; Refresh-Path }
        else { Write-Host "$($t.cmd) missing: re-run with -Install (after asking the user) or: winget install --id $($t.id) -e" }
    }
}

# 4. GitHub account -> github_owner / harness_remote_url for this machine
$ghOk = $false; if (Has gh) { gh auth status *> $null; $ghOk = ($LASTEXITCODE -eq 0) }
if ($ghOk) {
    $me = (gh api user --jq .login).Trim()
    if ($me -and $me -ne $base.github_owner) {
        $local.github_owner = $me
        $local.harness_remote_url = "https://github.com/$me/stalker2-modding-harness.git"
        Write-Host "GitHub account $($me): mods and the harness fork go under it."
    }
    if ($Fork -and $me -ne $base.github_owner) {
        Push-Location $Repo
        $origin = (git remote get-url origin 2>$null)
        if ($origin -notmatch "/$me/") {
            gh repo fork --remote --remote-name origin   # the original becomes 'upstream'
            Write-Host "Forked the harness to $me; origin now points at the fork, upstream at the original."
        } else { Write-Host "origin already points at $me's fork." }
        Pop-Location
    }
} elseif (Has gh) {
    Write-Host "Not logged in to GitHub. Run: gh auth login --hostname github.com --git-protocol https --web  (the user completes it in the browser)"
}

# 5. Editor remote Python (Project Settings > Plugins > Python > Enable Remote Execution), written to the kit's ini
$kitNow = if ($local.kit) { $local.kit -replace '/', '\' } else { $Kit }
$ini = "$kitNow\Stalker2\Config\DefaultEngine.ini"
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

# 6. Save the machine settings (only when something differs from config.json)
if ($local.Count) { New-Item -ItemType Directory -Force (Split-Path $localPath) | Out-Null; [IO.File]::WriteAllText($localPath, ($local | ConvertTo-Json), (New-Object Text.UTF8Encoding $false)); Write-Host "Wrote $localPath" }

& "$PSScriptRoot\check_setup.ps1"
