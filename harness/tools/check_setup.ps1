# Check that this machine is ready to make mods with the harness. Safe: it only reads and reports.
# Usage:  powershell -ExecutionPolicy Bypass -File harness\tools\check_setup.ps1
. "$PSScriptRoot\common.ps1"
$ErrorActionPreference = "Continue"
$fails = 0
function Check($ok, $what, $fix) {
    if ($ok) { Write-Host "  OK    $what" -ForegroundColor Green }
    else { Write-Host "  FIX   $what" -ForegroundColor Yellow; Write-Host "        -> $fix"; $script:fails++ }
}
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Write-Host "`nPaths (harness\config.json, overridden by $MachineSettings and harness\local.json):"
Check (Test-Path "$Kit\CreatePlainMod.bat") "Zone Kit at $Kit" `
    "Install the S.T.A.L.K.E.R. 2 Zone Kit from the Epic Games Store, then run harness\tools\setup.ps1 (finds it)."
Check (Test-Path "$Kit\Engine\Binaries\ThirdParty\Python3\Win64\python.exe") "Zone Kit's Python" "Reinstall / verify the Zone Kit in the Epic Games launcher."
Check (Test-Path "$Kit\Stalker2\Binaries\Win64\Stalker2ModEditor-Win64-Shipping-Cmd.exe") "Zone Kit editor (command-line build)" "Reinstall / verify the Zone Kit."
Check (Test-Path "$Game\Content\Paks") "Game at $($Cfg.game)" `
    "Run harness\tools\setup.ps1 (searches Steam libraries); else put the folder containing 'Stalker2' in  as `"game`"."

Write-Host "`nPrograms:"
Check (Has git) "Git" "winget install --id Git.Git -e   (then open a new terminal)"
if (Has git) {
    Check ([bool](git config --global user.name)) "Git user name set" 'git config --global user.name "Your Name"'
    Check ([bool](git config --global user.email)) "Git email set" 'git config --global user.email "you@example.com"'
}
Check (Has gh) "GitHub CLI (gh)" "winget install --id GitHub.cli -e   (then open a new terminal)"
if (Has gh) { gh auth status *> $null; Check ($LASTEXITCODE -eq 0) "Logged in to GitHub" "gh auth login   (choose GitHub.com, HTTPS, log in with a web browser)" }
$agents = @("claude", "codex", "gemini", "cursor-agent", "copilot") | Where-Object { Has $_ }
Write-Host ("  INFO  AI agent command(s) on PATH: " + $(if ($agents) { $agents -join ", " } else { "none found (fine if you use an editor-based agent such as VS Code Copilot or Cursor)" }))

Write-Host "`nHarness settings:"
Check ($Cfg.github_owner) "github_owner = $($Cfg.github_owner)" "Run harness\tools\setup.ps1 (it writes your GitHub user name to the machine settings)."
if (Has gh) {
    $me = (gh api user --jq .login 2>$null)
    if ($me) { Check ($me -eq $Cfg.github_owner) "github_owner matches the GitHub account you are logged in as ($me)" `
        "Run harness\tools\setup.ps1 -Fork (writes github_owner / harness_remote_url to the machine settings and forks the harness)." }
}

Write-Host "`nEditor (only checked if the Zone Kit editor is open):"
if (Get-Process Stalker2ModEditor* -ErrorAction SilentlyContinue) {
    $py = "$Kit\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
    $out = & $py "$PSScriptRoot\ue_exec.py" "print('harness-ok')" --no-prelude 2>&1
    Check ($out -match "harness-ok") "Python remote execution in the editor" `
        "Close the editor, run harness\tools\setup.ps1 -EnableRemotePython, reopen it (or: Edit > Project Settings > Plugins > Python > Enable Remote Execution)."
} else { Write-Host "  SKIP  editor not running (open it and run this again to check remote Python)" }

Write-Host ""
if ($fails) { Write-Host "$fails thing(s) to fix. Fix them and run this again." -ForegroundColor Yellow; exit 1 }
Write-Host "All set." -ForegroundColor Green
