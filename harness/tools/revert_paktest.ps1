# Remove a mod's dev test pak folder(s) so only the Vortex-installed release copy is left (game must be closed).
# Usage:  powershell -File harness\tools\revert_paktest.ps1 [-Mod X] [-Park]
#   -Park moves the folder to <game>\Stalker2\_parked_mods\ instead of deleting it. Never park anything under
#   Content\Paks\: the game scans that tree recursively and would still mount it.
param([string]$Mod, [switch]$Park)
. "$PSScriptRoot\common.ps1"
Assert-Setup game
$Mod = Get-ModName $Mod
if (Test-GameRunning) { throw "game is running" }
$dirs = Get-ChildItem $Mods -Directory -Filter "zzz_${Mod}*_PakTest" -ErrorAction SilentlyContinue
if (-not $dirs) { Write-Host "No dev test pak for $Mod in $Mods"; exit 0 }
foreach ($d in $dirs) {
    if ($Park) {
        $to = "$Game\_parked_mods\$(Get-Date -Format yyyy-MM-dd_HHmm)"
        New-Item -ItemType Directory -Force $to | Out-Null
        Move-Item $d.FullName $to; Write-Host "Parked $($d.Name) -> $to"
    } else { Remove-Item $d.FullName -Recurse -Force; Write-Host "Removed $($d.Name)" }
}
