# Coordination board for several agents (any tool) working on this PC at once: one Zone Kit, one game, one tester.
# The board lives next to the machine settings, so every repo / session sees the same one:
#   %LOCALAPPDATA%\stalker2-modding-harness\coord\claims.json   who holds which shared resource
#   %LOCALAPPDATA%\stalker2-modding-harness\coord\board.log     append-only messages between agents
# Usage:
#   coord.ps1 -Status                          claims (stale after 2 h) + the last 15 messages
#   coord.ps1 -Claim editor -Note "pasting BP" take a resource (exit 2 if another agent holds it; -Force to take over)
#   coord.ps1 -Release editor                  give it back
#   coord.ps1 -Post "cook done, editor free"   leave a message for the other agents
#   coord.ps1 -Read 40                         the last 40 messages
# Resources (docs/coordination.md): editor, cook, game, postprocess-layer, tester. -Agent defaults to the mod name.
param([string]$Claim, [string]$Release, [switch]$Status, [string]$Post, [int]$Read = 0, [string]$Note = "",
      [string]$Agent, [switch]$Force, [string]$Mod)
. "$PSScriptRoot\common.ps1"
$Dir = "$env:LOCALAPPDATA\stalker2-modding-harness\coord"
New-Item -ItemType Directory -Force $Dir | Out-Null
$ClaimsFile = "$Dir\claims.json"
$LogFile = "$Dir\board.log"
if (-not $Agent) {
    try { $Agent = Get-ModName $Mod } catch { $Agent = Split-Path $Repo -Leaf }
}
$StaleHours = 2

function Get-Claims {
    $h = @{}
    $j = Read-Json $ClaimsFile
    if ($j) { foreach ($p in $j.PSObject.Properties) { $h[$p.Name] = $p.Value } }
    return $h
}
function Save-Claims($h) { ($h | ConvertTo-Json -Depth 4) | Set-Content -Encoding utf8 $ClaimsFile }
function Write-Board([string]$msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  [$Agent]  $msg"
    Add-Content -Encoding utf8 $LogFile $line
}
function Test-Stale($c) { ((Get-Date) - [datetime]$c.since).TotalHours -gt $StaleHours }

if ($Claim) {
    $h = Get-Claims
    $c = $h[$Claim]
    if ($c -and $c.agent -ne $Agent -and -not (Test-Stale $c) -and -not $Force) {
        Write-Host "BUSY: '$Claim' is held by $($c.agent) since $($c.since) ($($c.note)). Ask them (board / message) or wait."
        exit 2
    }
    $h[$Claim] = [pscustomobject]@{ agent = $Agent; since = (Get-Date -Format s); note = $Note }
    Save-Claims $h
    Write-Board "claims '$Claim'$(if ($Note) { ": $Note" })"
    Write-Host "Claimed '$Claim' for $Agent."
}
if ($Release) {
    $h = Get-Claims
    if ($h.ContainsKey($Release)) {
        if ($h[$Release].agent -ne $Agent -and -not $Force) { Write-Host "'$Release' is held by $($h[$Release].agent), not $Agent (use -Force)."; exit 2 }
        $h.Remove($Release)
        Save-Claims $h
        Write-Board "released '$Release'"
    }
    Write-Host "Released '$Release'."
}
if ($Post) { Write-Board $Post; Write-Host "Posted." }
if ($Status -or (-not $Claim -and -not $Release -and -not $Post -and -not $Read)) {
    $h = Get-Claims
    Write-Host "Claims:"
    if (-not $h.Count) { Write-Host "  (none)" }
    foreach ($k in $h.Keys) { $c = $h[$k]; Write-Host ("  {0,-18} {1,-22} since {2}{3}  {4}" -f $k, $c.agent, $c.since, $(if (Test-Stale $c) { " (STALE)" } else { "" }), $c.note) }
    $Read = [Math]::Max($Read, 15)
}
if ($Read -and (Test-Path $LogFile)) {
    Write-Host "Board (last $Read):"
    Get-Content $LogFile -Tail $Read | ForEach-Object { Write-Host "  $_" }
}
