# Check that this PC is ready to make mods with the harness. Safe: it only reads and reports.
# Usage:  powershell -ExecutionPolicy Bypass -File harness\tools\check_setup.ps1     (Linux: pwsh -File harness/tools/check_setup.ps1)
. "$PSScriptRoot\common.ps1"
$ErrorActionPreference = "Continue"
$fails = 0
$setup = "run $(Get-ToolCommand setup.ps1)"
function Check($ok, $what, $fix) {
    if ($ok) { Write-Host "  OK    $what" -ForegroundColor Green }
    else { Write-Host "  FIX   $what" -ForegroundColor Yellow; Write-Host "        -> $fix"; $script:fails++ }
}
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Write-Host "`nPaths (machine settings: $MachineSettings):"
Check ($Cfg.kit -and (Test-Path "$Kit\CreatePlainMod.bat")) "Zone Kit: $(if ($Cfg.kit) { $Kit } else { 'not set' })" `
    "Install the S.T.A.L.K.E.R. 2 Zone Kit from the Epic Games Store, then $setup (finds it)."
if ($Cfg.kit) {
    if (-not $OnLinux) { Check (Test-Path $Py) "Zone Kit's Python" "Verify the Zone Kit in the Epic Games launcher." }
    Check (Test-Path $EditorCmd) "Zone Kit editor (command-line build)" "Verify the Zone Kit in the Epic Games launcher (Heroic on Linux)."
}
if ($OnLinux) {
    Check ($Cfg.wine -and (Test-Path $Cfg.wine)) "Proton wine: $(if ($Cfg.wine) { $Cfg.wine } else { 'not set' })" `
        "$setup (reads Heroic's Proton choice for the Zone Kit); otherwise set `"wine`" to <proton>/files/bin/wine in $MachineSettings."
    Check ($Cfg.kit_prefix -and (Test-Path (Join-Path $Cfg.kit_prefix "drive_c"))) "Zone Kit Wine prefix: $(if ($Cfg.kit_prefix) { $Cfg.kit_prefix } else { 'not set' })" `
        "$setup (reads Heroic's prefix for the Zone Kit); otherwise set `"kit_prefix`" in $MachineSettings."
    Check ($Cfg.game_prefix -and (Test-Path $GameUserDir)) "Game Proton prefix (logs, saves): $(if ($Cfg.game_prefix) { $Cfg.game_prefix } else { 'not set' })" `
        "Start the game once through Steam, then $setup (finds steamapps/compatdata/1643320/pfx)."
}
Check ($Cfg.game -and (Test-Path "$Game\Content\Paks")) "Game: $(if ($Cfg.game) { $Cfg.game } else { 'not set' })" `
    "$setup (searches Steam libraries); otherwise add the folder that contains 'Stalker2' to the machine settings as `"game`"."

Write-Host "`nPrograms:"
if ($OnLinux) {
    Check (Has python3) "python3 (3.10+)" "Install python3 with the distribution's package manager."
    Check (Has rsync) "rsync (mirror_from_kit / deploy_to_kit)" "Install rsync with the distribution's package manager."
}
Check (Has git) "Git" $(if ($OnLinux) { "Install git with the distribution's package manager." } else { "$setup -Install   (or: winget install --id Git.Git -e; then open a new terminal)" })
if (Has git) {
    Check ([bool](git config --global user.name)) "Git user name set" 'git config --global user.name "Your Name"'
    Check ([bool](git config --global user.email)) "Git email set" 'git config --global user.email "you@example.com"'
}
Check (Has gh) "GitHub CLI (gh)" $(if ($OnLinux) { "Install gh: https://github.com/cli/cli/blob/trunk/docs/install_linux.md" } else { "$setup -Install   (or: winget install --id GitHub.cli -e; then open a new terminal)" })
$me = $null
if (Has gh) {
    gh auth status *> $null
    Check ($LASTEXITCODE -eq 0) "Logged in to GitHub" "gh auth login --hostname github.com --git-protocol https --web"
    if ($LASTEXITCODE -eq 0) { $me = (gh api user --jq .login 2>$null) }
}
$agents = @("claude", "codex", "gemini", "cursor-agent", "copilot") | Where-Object { Has $_ }
Write-Host ("  INFO  AI agent command(s) on PATH: " + $(if ($agents) { $agents -join ", " } else { "none found (fine if you use an editor-based agent)" }))

Write-Host "`nAccount:"
Check ($Cfg.github_owner) "GitHub account in the machine settings: $(if ($Cfg.github_owner) { $Cfg.github_owner } else { 'not set' })" "$setup"
if ($me -and $Cfg.github_owner) { Check ($me -eq $Cfg.github_owner) "matches the logged-in GitHub account ($me)" "$setup" }

Write-Host "`nEditor (only checked if the Zone Kit editor is open):"
if ($Cfg.kit -and (Test-EditorRunning)) {
    $out = & $Py (Join-Path $PSScriptRoot "ue_exec.py") "print('harness-ok')" --no-prelude 2>&1
    Check ($out -match "harness-ok") "Python remote execution in the editor" `
        "Close the editor, $setup -EnableRemotePython, reopen it (or: Edit > Project Settings > Plugins > Python > Enable Remote Execution)."
} else { Write-Host "  SKIP  editor not running (open it and run this again to check remote Python)" }

Write-Host ""
if ($fails) { Write-Host "$fails thing(s) to fix. Fix them and run this again." -ForegroundColor Yellow; exit 1 }
Write-Host "All set." -ForegroundColor Green
