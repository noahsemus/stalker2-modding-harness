# Promote edits made under harness\ in this mod repo to the central harness, then sync back.
# Usage:  powershell -File harness\tools\push_harness.ps1 -Message "docs: <what was learned>" [-NoPush]
# How: diff harness\ against the upstream commit in .harness-sync, apply that patch (3-way) in the local harness
# clone (config "harness_clone", cloned if missing), commit + push there, then sync_harness.ps1 here.
# Other mods pick the change up with their own sync_harness.ps1.
param([Parameter(Mandatory)][string]$Message, [switch]$NoPush)
. "$PSScriptRoot\common.ps1"
Assert-Setup harness_remote_url
Set-Location $Repo
if (-not (Test-Path "$Repo\.harness-sync")) { throw "run this from a mod repo; in the harness repo just commit and push" }
$base = (Get-Content "$Repo\.harness-sync" -Raw).Trim()
if (-not (git remote | Select-String -Quiet '^harness$')) { git remote add harness $Cfg.harness_remote_url }
git fetch -q harness main   # makes sure the base commit is present locally
git add -A harness
$patch = "$env:TEMP\harness_promote.patch"
git diff --cached --binary "--output=$patch" $base -- harness
if ((Get-Item $patch).Length -eq 0) { Write-Host "No harness changes to promote."; exit 0 }
git diff --cached --stat $base -- harness

$clone = [IO.Path]::GetFullPath((Join-Path $Repo $Cfg.harness_clone))
if (-not (Test-Path "$clone\.git")) { git clone -q $Cfg.harness_remote_url $clone }
Push-Location $clone
try {
    if (git status --porcelain) { throw "harness clone $clone has uncommitted changes; resolve them first" }
    git checkout -q main; git pull -q --ff-only
    git apply --3way --index $patch
    if ($LASTEXITCODE) { throw "patch did not apply cleanly in $clone; resolve there (git status), commit, then sync_harness.ps1 here" }
    git commit -q -m $Message
    if (-not $NoPush) { git push -q origin main; if ($LASTEXITCODE) { throw "push failed" } }
    Write-Host "Promoted to harness: $((git rev-parse --short HEAD).Trim()) $Message"
} finally { Pop-Location }

if ($NoPush) { Write-Host "Not pushed; sync_harness.ps1 will pick it up after you push $clone."; exit 0 }
git reset -q -- harness   # unstage; sync replaces harness\ with the promoted upstream copy
& "$PSScriptRoot\sync_harness.ps1" -Force
