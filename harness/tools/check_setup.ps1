# Check that this PC is ready to make mods with the harness. Safe: it only reads and reports.
# Usage:  powershell -ExecutionPolicy Bypass -File harness\tools\check_setup.ps1
. "$PSScriptRoot\common.ps1"
$ErrorActionPreference = "Continue"
$fails = 0
$setup = "run harness\tools\setup.ps1"
function Check($ok, $what, $fix) {
    if ($ok) { Write-Host "  OK    $what" -ForegroundColor Green }
    else { Write-Host "  FIX   $what" -ForegroundColor Yellow; Write-Host "        -> $fix"; $script:fails++ }
}
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Write-Host "`nPaths (machine settings: $MachineSettings):"
Check ($Cfg.kit -and (Test-Path "$Kit\CreatePlainMod.bat")) "Zone Kit: $(if ($Cfg.kit) { $Kit } else { 'not set' })" `
    "Install the S.T.A.L.K.E.R. 2 Zone Kit from the Epic Games Store, then $setup (finds it)."
if ($Cfg.kit) {
    Check (Test-Path "$Kit\Engine\Binaries\ThirdParty\Python3\Win64\python.exe") "Zone Kit's Python" "Verify the Zone Kit in the Epic Games launcher."
    Check (Test-Path $EditorCmd) "Zone Kit editor (command-line build)" "Verify the Zone Kit in the Epic Games launcher."
}
Check ($Cfg.game -and (Test-Path "$Game\Content\Paks")) "Game: $(if ($Cfg.game) { $Cfg.game } else { 'not set' })" `
    "$setup (searches Steam libraries); otherwise add the folder that contains 'Stalker2' to the machine settings as `"game`"."

Write-Host "`nPrograms:"
Check (Has git) "Git" "$setup -Install   (or: winget install --id Git.Git -e; then open a new terminal)"
if (Has git) {
    Check ([bool](git config --global user.name)) "Git user name set" 'git config --global user.name "Your Name"'
    Check ([bool](git config --global user.email)) "Git email set" 'git config --global user.email "you@example.com"'
}
Check (Has gh) "GitHub CLI (gh)" "$setup -Install   (or: winget install --id GitHub.cli -e; then open a new terminal)"
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
if ($Cfg.kit -and (Get-Process Stalker2ModEditor* -ErrorAction SilentlyContinue)) {
    $py = "$Kit\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
    $out = & $py "$PSScriptRoot\ue_exec.py" "print('harness-ok')" --no-prelude 2>&1
    Check ($out -match "harness-ok") "Python remote execution in the editor" `
        "Close the editor, $setup -EnableRemotePython, reopen it (or: Edit > Project Settings > Plugins > Python > Enable Remote Execution)."
} else { Write-Host "  SKIP  editor not running (open it and run this again to check remote Python)" }

Write-Host ""
if ($fails) { Write-Host "$fails thing(s) to fix. Fix them and run this again." -ForegroundColor Yellow; exit 1 }
Write-Host "All set." -ForegroundColor Green
