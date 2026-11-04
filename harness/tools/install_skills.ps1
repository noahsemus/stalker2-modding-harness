# Install the harness's agent skills (harness\skills\<name>\) into this repo's .claude\skills\<name>\ so Claude Code
# offers them as /<name>. Every harness skill is copied over (harness\skills is the source; never edit the copies);
# a copied skill gets a .from-harness marker, and marked skills no longer in the harness are removed. Skills the mod
# made itself (no marker) are left alone. Run by sync_harness.ps1 and new_mod.ps1; safe to run any time.
# Usage:  powershell -File harness\tools\install_skills.ps1
. "$PSScriptRoot\common.ps1"
$src = Join-Path $Repo (Join-Path "harness" "skills")
$dst = Join-Path $Repo (Join-Path ".claude" "skills")
$names = @()
if (Test-Path $src) { $names = @(Get-ChildItem -Directory $src | ForEach-Object { $_.Name }) }
if ($names.Count -gt 0) { New-Item -ItemType Directory -Force $dst | Out-Null }
foreach ($n in $names) {
    $to = Join-Path $dst $n
    if (Test-Path $to) { Remove-Item -Recurse -Force $to }
    Copy-Item -Recurse (Join-Path $src $n) $to
    [IO.File]::WriteAllText((Join-Path $to ".from-harness"), "installed from harness/skills/$n by install_skills.ps1; edit the harness copy`n", (New-Object Text.UTF8Encoding $false))
}
if (Test-Path $dst) {
    foreach ($d in Get-ChildItem -Directory $dst) {
        if ((Test-Path (Join-Path $d.FullName ".from-harness")) -and ($names -notcontains $d.Name)) { Remove-Item -Recurse -Force $d.FullName }
    }
}
Write-Host "Skills installed: $(if ($names.Count) { $names -join ', ' } else { 'none' })"
