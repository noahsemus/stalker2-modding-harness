# Cook a Zone Kit mod and install it into the game as the dev test pak.
# Usage:  powershell -File harness\tools\cook_and_install.ps1 [-Mod X] [-Suffix 30] [-NoInstall]
# Save assets in the editor first and wait ~10 s (the cook reads the files on disk). Takes 5-6 minutes.
# The editor may stay open. Install waits for the game to close.
param([string]$Mod, [int]$Suffix = 0, [switch]$NoInstall)
. "$PSScriptRoot\common.ps1"
Assert-Setup kit, game
$Mod = Get-ModName $Mod

# Classifier lists: the kit copy is what the cook reads (and what Package Mod edits). Seed it from the repo if
# missing; afterwards mirror it back so the repo always has what was cooked.
$kitCls  = "$Kit\Stalker2\SavedMods\PackageClassifier\$Mod"
$repoCls = "$Repo\zonekit\tools\classifier\$Mod"
if (-not (Test-Path "$kitCls\OverridePackages.txt") -and (Test-Path $repoCls)) {
    New-Item -ItemType Directory -Force $kitCls | Out-Null
    Copy-Item "$repoCls\*.txt" $kitCls -Force
    Write-Host "Seeded kit classifier lists from the repo."
}
$ovrList = @(Get-Content "$kitCls\OverridePackages.txt" -ErrorAction SilentlyContinue)
$newList = @(Get-Content "$kitCls\NewPackages.txt" -ErrorAction SilentlyContinue)
$both = $ovrList | Where-Object { $_ -and ($newList -contains $_) }
if ($both) { Write-Host "WARNING: listed in BOTH classifier lists (cooked into neither): $($both -join ', ')" }

$log = "$env:TEMP\${Mod}_cook.log"
Wait-UatFree
Write-Host "Cooking $Mod (log: $log) ..."
& "$Kit\Engine\Build\BatchFiles\RunUAT.bat" GSCCookMod "-Project=$Uproject" "-PluginPath=$Kit\Stalker2\Mods\$Mod\$Mod.uplugin" "-PackageClassifierOutputDir=$kitCls" "-UnrealExe=$EditorCmd" -TargetPlatform=Win64 -nocompile -nocompileuat *> $log
if ($LASTEXITCODE -ne 0) { Write-Host "COOK FAILED (exit $LASTEXITCODE). See $log"; exit 1 }
Write-Host "Cook OK."

if (Test-Path $kitCls) { New-Item -ItemType Directory -Force $repoCls | Out-Null; Copy-Item "$kitCls\*.txt" $repoCls -Force }
if ($NoInstall) { exit 0 }
Wait-GameClosed
& "$PSScriptRoot\install_paktest.ps1" -Mod $Mod -Suffix $Suffix
