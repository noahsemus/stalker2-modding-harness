# Create a new mod repo from the harness ("fork"): sibling folder, harness history + remote, templates filled in,
# Zone Kit plugin created, public GitHub repo created and pushed.
# Usage (from the harness repo or any mod repo):
#   powershell -File harness\tools\new_mod.ps1 -Name ImmersiveReloading -Short ImmReload `
#       -RepoName stalker2-immersive-reloading -Description "Sprint while reloading." [-NoKit] [-NoGitHub] [-Private]
# -Name  = Zone Kit plugin name (PascalCase, no spaces; also the /<Name>/ content root and pak base name).
# -Short = prefix for mod-only asset names (BP_<Short>Subsystem, ...), probes and log tags.
param(
    [Parameter(Mandatory)][string]$Name,
    [Parameter(Mandatory)][string]$Short,
    [Parameter(Mandatory)][string]$RepoName,
    [Parameter(Mandatory)][string]$Description,
    [switch]$NoKit, [switch]$NoGitHub, [switch]$Private
)
. "$PSScriptRoot\common.ps1"
Assert-Setup (@("github_owner", "harness_remote_url") + $(if ($NoKit) { @() } else { @("kit") }))
$here = $RepoName   # $Repo (from common.ps1) = this checkout
$dest = Join-Path (Split-Path $Repo -Parent) $here
if (Test-Path $dest) { throw "$dest already exists" }

# 1. Clone the harness (its history comes along, so later syncs are plain fetches)
$harnessSrc = if (Test-Path "$Repo\.harness-sync") { $Cfg.harness_remote_url } else { $Repo }
git clone -q $harnessSrc $dest; if ($LASTEXITCODE) { throw "clone failed" }
Push-Location $dest
$ok = $false
try {
    git remote rename origin harness
    git remote set-url harness $Cfg.harness_remote_url
    $sha = (git rev-parse HEAD).Trim()

    # 2. Replace the harness repo's own root files with the mod templates
    $date = Get-Date -Format yyyy-MM-dd
    $subst = @{ "{{MOD}}" = $Name; "{{SHORT}}" = $Short; "{{REPO}}" = $here; "{{DESCRIPTION}}" = $Description;
                "{{DATE}}" = $date; "{{OWNER}}" = $Cfg.github_owner }
    function Fill($text) { foreach ($k in $subst.Keys) { $text = $text.Replace($k, $subst[$k]) }; $text }
    $utf8 = New-Object Text.UTF8Encoding $false
    $map = @{ "AGENTS.md" = "AGENTS.md"; "CLAUDE.md" = "CLAUDE.md"; "GEMINI.md" = "GEMINI.md"; "PLAN.md" = "PLAN.md"; "BUILD.md" = "BUILD.md"; "README.md" = "README.md";
              "LOG.md" = "zonekit\README.md"; "gitignore" = ".gitignore" }
    New-Item -ItemType Directory -Force "zonekit\$Name", "zonekit\tools\classifier\$Name", "zonekit\builds" | Out-Null
    foreach ($t in $map.Keys) {
        [IO.File]::WriteAllText("$dest\$($map[$t])", (Fill ([IO.File]::ReadAllText("$dest\harness\templates\$t"))), $utf8)
    }
    $mod = [ordered]@{ name = $Name; short = $Short; repo = $here; description = $Description;
                       release_pak_suffix = 20; dev_pak_suffix = 30; nexus_id = $null; optional_plugins = @() }
    [IO.File]::WriteAllText("$dest\mod.json", ($mod | ConvertTo-Json -Depth 4), $utf8)
    foreach ($f in "OverridePackages.txt", "NewPackages.txt") { [IO.File]::WriteAllText("$dest\zonekit\tools\classifier\$Name\$f", "", $utf8) }
    [IO.File]::WriteAllText("$dest\zonekit\builds\.gitkeep", "", $utf8)
    [IO.File]::WriteAllText("$dest\.harness-sync", "$sha`n", $utf8)

    # 3. Zone Kit plugin
    if (-not $NoKit) {
        $plug = "$Kit\Stalker2\Mods\$Name"
        if (-not (Test-Path "$plug\$Name.uplugin")) {
            Wait-UatFree
            Write-Host "Creating the Zone Kit plugin (GSCCreatePlainMod) ..."
            & "$Kit\Engine\Build\BatchFiles\RunUAT.bat" GSCCreatePlainMod "-Project=$Uproject" "-ModName=$Name" *> "$env:TEMP\${Name}_create.log"
            if (-not (Test-Path "$plug\$Name.uplugin")) { throw "plugin not created; see $env:TEMP\${Name}_create.log" }
        }
        $u = Get-Content "$plug\$Name.uplugin" -Raw | ConvertFrom-Json
        $want = [ordered]@{ FriendlyName = $Name; Description = $Description; Category = "Game Features"; CreatedBy = $Cfg.github_owner;
                            EnabledByDefault = $true; CanContainContent = $true; ExplicitlyLoaded = $true;
                            BuiltInInitialFeatureState = "Registered"; Mod = $true }
        foreach ($k in $want.Keys) { $u | Add-Member -Force -NotePropertyName $k -NotePropertyValue $want[$k] }
        [IO.File]::WriteAllText("$plug\$Name.uplugin", ($u | ConvertTo-Json -Depth 8), $utf8)
        & "$dest\harness\tools\mirror_from_kit.ps1" -Mod $Name | Out-Null
    }

    git add -A
    git commit -q -m "Create $Name from stalker2-modding-harness $($sha.Substring(0,7))"
    if (-not $NoGitHub) {
        $vis = if ($Private) { "--private" } else { "--public" }
        gh repo create "$($Cfg.github_owner)/$here" $vis --description $Description --source . --remote origin --push
    }
    $ok = $true
    Write-Host "Created $dest"
    if (-not $NoKit) {
        Write-Host "Tester step: restart the Zone Kit editor, then pick '$Name' in the toolbar mod selector once (creates the GameFeatureData and mounts the plugin). Then run mirror_from_kit.ps1."
    }
} finally {
    Pop-Location
    if (-not $ok -and -not (git -C $dest remote | Select-String -Quiet '^origin$')) { Remove-Item $dest -Recurse -Force; Write-Host "Failed; removed the partial $dest" }
}
