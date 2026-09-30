# Install the last cooked build of a mod as the dev test pak (game must be closed).
# Usage:  powershell -File harness\tools\install_paktest.ps1 [-Mod X] [-Suffix 30]
#   OverrideContent -> ~mods\zzz_<Mod>_PakTest\zzz_<Mod>_<Suffix>_P.{pak,ucas,utoc}
#   NewContent      -> same folder, kit file name kept (its /<Mod>/ paths exist nowhere else).
# Suffix default = mod.json "dev_pak_suffix" or 30 (order 3103: beats other mods and a Vortex-installed release
# copy at _20_P). Use 40 to beat a mod that itself ships _30_P, 25 to reproduce a user where that mod wins.
param([string]$Mod, [int]$Suffix = 0)
. "$PSScriptRoot\common.ps1"
Assert-Setup kit, game
$Mod = Get-ModName $Mod
if (-not $Suffix) { $Suffix = Get-Priority "dev_pak_suffix" 30 }
if (Test-GameRunning) { throw "game is running" }
$staged = "$Kit\Stalker2\SavedMods\Staged\$Mod\Windows"
$ovr = "$staged\OverrideContent\Windows\Stalker2\Mods\$Mod\Content\Paks\Windows"
$new = "$staged\NewContent\Windows\Stalker2\Mods\$Mod\Content\Paks\Windows"
$dst = "$Mods\zzz_${Mod}_PakTest"
New-Item -ItemType Directory -Force $dst | Out-Null
Remove-Item "$dst\*" -Force -ErrorAction SilentlyContinue
$n = 0
if (Test-Path "$ovr\${Mod}Stalker2-Windows-OverrideContent.utoc") {
    foreach ($ext in "pak", "ucas", "utoc") { Copy-Item "$ovr\${Mod}Stalker2-Windows-OverrideContent.$ext" "$dst\zzz_${Mod}_${Suffix}_P.$ext" -Force }; $n++
}
if (Test-Path "$new\${Mod}Stalker2-Windows-NewContent.utoc") {
    foreach ($ext in "pak", "ucas", "utoc") { Copy-Item "$new\${Mod}Stalker2-Windows-NewContent.$ext" "$dst\${Mod}Stalker2-Windows-NewContent.$ext" -Force }; $n++
}
if (-not $n) { throw "nothing staged under $staged (cook first)" }
Get-ChildItem $dst | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
