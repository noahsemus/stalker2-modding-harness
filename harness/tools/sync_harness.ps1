# Pull the latest harness into this mod repo: harness\ is replaced by the upstream copy (files deleted upstream are
# deleted here), .harness-sync records the upstream commit, and the result is committed. Mod files are never touched.
# Usage:  powershell -File harness\tools\sync_harness.ps1 [-Force] [-NoCommit]
# Refuses while harness\ has local changes that were never promoted (push_harness.ps1 first), unless -Force
# (which discards them).
param([switch]$Force, [switch]$NoCommit)
. "$PSScriptRoot\common.ps1"
Assert-Setup harness_remote_url
Set-Location $Repo
if (-not (Test-Path "$Repo\.harness-sync")) { throw "not a mod repo (no .harness-sync); in the harness repo itself just git pull" }
if (-not (git remote | Select-String -Quiet '^harness$')) { git remote add harness $Cfg.harness_remote_url }
git fetch -q harness main; if ($LASTEXITCODE) { throw "fetch failed" }
$base = (Get-Content "$Repo\.harness-sync" -Raw).Trim()
$new = (git rev-parse harness/main).Trim()

git add -N harness
$local = git diff --name-only $base -- harness
if ($local -and -not $Force) {
    Write-Host "harness\ differs from the last synced upstream ($($base.Substring(0,7))) in:"; $local | ForEach-Object { "  $_" }
    Write-Host "Promote them first (push_harness.ps1 -Message ...) or re-run with -Force to discard them."
    exit 1
}
if ($base -eq $new -and -not $local) { Write-Host "Harness already at $($new.Substring(0,7))."; exit 0 }
git restore --source=harness/main --staged --worktree -- harness
# restore leaves untracked new files alone; remove any that are not upstream (local.json is gitignored and kept)
git clean -q -f -- harness
[IO.File]::WriteAllText("$Repo\.harness-sync", "$new`n", (New-Object Text.UTF8Encoding $false))
git add .harness-sync harness
Write-Host "Harness $($base.Substring(0,7)) -> $($new.Substring(0,7)):"
git log --oneline "$base..$new" -- harness
if (-not $NoCommit) { git commit -q -m "Sync harness to $($new.Substring(0,7))"; Write-Host "Committed." }
