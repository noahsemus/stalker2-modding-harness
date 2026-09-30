# Copy the committed mod plugin from the repo into the kit (fresh clone, new machine, or rolling back to a checkpoint).
# Usage:  powershell -File harness\tools\deploy_to_kit.ps1 [-Mod X] [-Force]
# Refuses to overwrite a kit copy that has files newer than the repo's unless -Force (that would destroy unsaved
# editor work). Close the editor first, or at least close every asset of this mod.
param([string]$Mod, [switch]$Force)
. "$PSScriptRoot\common.ps1"
Assert-Setup kit
$Mod = Get-ModName $Mod
$src = "$Repo\zonekit\$Mod"
$dst = "$Kit\Stalker2\Mods\$Mod"
if (-not (Test-Path "$src\$Mod.uplugin")) { throw "no plugin in the repo at $src" }
if ((Test-Path $dst) -and -not $Force) {
    $newer = Get-ChildItem $dst -Recurse -File | Where-Object { $_.FullName -notmatch '\\(Intermediate|Saved)\\' } | ForEach-Object {
        $rel = $_.FullName.Substring($dst.Length)
        $r = Get-Item "$src$rel" -ErrorAction SilentlyContinue
        if (-not $r -or $_.LastWriteTime -gt $r.LastWriteTime.AddSeconds(2)) { $rel }
    }
    if ($newer) { Write-Host "Kit copy has newer or extra files (mirror them first, or pass -Force):"; $newer | ForEach-Object { "  $_" }; exit 1 }
}
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "$src\$Mod.uplugin" $dst -Force
foreach ($d in "Content", "Resources") { if (Test-Path "$src\$d") { robocopy "$src\$d" "$dst\$d" /MIR /NJH /NJS /NP /NDL | Out-Null } }
$cls = "$Repo\zonekit\tools\classifier\$Mod"
if (Test-Path $cls) {
    New-Item -ItemType Directory -Force "$Kit\Stalker2\SavedMods\PackageClassifier\$Mod" | Out-Null
    Copy-Item "$cls\*.txt" "$Kit\Stalker2\SavedMods\PackageClassifier\$Mod" -Force
}
Write-Host "Deployed $Mod to $dst. The editor discovers a new plugin only at startup."
exit 0
