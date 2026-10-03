# Diagnostics: logs, probes, crash dumps

## Where to look (read these yourself; never ask the tester to paste them)
| What | Path |
|---|---|
| Game log (mounts, asserts, crash summary) | `%LOCALAPPDATA%\Stalker2\Saved\Logs\Stalker2.log` (+ `Stalker2_2.log`, `Stalker2-backup-*.log`) |
| Game crash reports | `%LOCALAPPDATA%\Stalker2\Saved\Crashes\` |
| Player rebinds / settings | `%LOCALAPPDATA%\Stalker2\Saved\CustomizeControls.cfg`, `...\Config\` |
| UE4SS log / crash dumps (only if UE4SS is installed) | `<game>\Stalker2\Binaries\Win64\ue4ss\UE4SS.log`, `ue4ss\crash_*.dmp` |
| UE4SS mod list | `ue4ss\Mods\mods.txt` |
| Installed mods | `<game>\Stalker2\Content\Paks\~mods\` |
| Cook log | `%TEMP%\<Mod>_cook.log` |

## Without UE4SS
- `Print String` is stripped in Shipping. Use visible side effects, counters on the mod actor read back by a probe,
  or a canary key.
- Check the cooked result instead of guessing: extract the staged container (`UnrealPak <x>.utoc -Extract <dir>`)
  and read names / imports with `tools/pak/zen_names.py` (`--imports` shows which assets a Blueprint really
  references; a nulled mod-only reference simply is not there).
- A byte scan (`dump_names.py`) cannot tell a hard import from a soft path; parse the import map (`zen_names.py
  --imports` on cooked files).

## UE4SS probes (modder's PC only, never shipped)
- Read-only C++ probe (`harness/probe/`), SEH-guarded (`__try/__except` around raw memory reads, no objects with
  destructors inside the guarded function), reading only while the relevant state is active.
- **List the probe before `UObjectCacheMod` in `mods.txt`**, or `FindFirstOf` returns stale objects.
- **Write `mods.txt` as ASCII, no BOM**: PowerShell 5.1 `Set-Content -Encoding utf8` writes a BOM and UE4SS then
  silently skips the first line.
- Heavy work (`ForEachUObject`, `FindAllOf`) only on state edges, never per tick; per-tick work runs on the game
  thread and stalls rendering and input.
- Build: RE-UE4SS clone (clone it anywhere and set `ue4ss_source` in the machine settings). Needs VS 2022 Desktop C++, CMake 3.22+, Rust (patternsleuth), the GitHub
  account linked to Epic Games (private `UEPseudo` submodule) and
  `git config --global url."https://github.com/".insteadOf "git@github.com:"`. Only `Game__Shipping__Win64` matches
  the game's CRT (plain Release/Debug don't exist: MSB8013). Output `main.dll` → `ue4ss\Mods\<Probe>\dlls\main.dll`
  + a `mods.txt` line.
- Never introduce a UE4SS type/function the probe hasn't exercised in a single-purpose build first:
  `FWeakObjectPtr` crashes this game (RE-UE4SS allocates serial numbers through a Kismet call).
- UE4SS Lua limits: struct field values of game structs are opaque (`TrivialObject`, no accessor); `LoopAsync` work
  must go through `ExecuteInGameThread`; `RegisterKeyBind` twice in one process crashes (guard reloads with a global
  flag); calling anim functions from Lua crashes. Lua is fine for enumerating objects, names and zero-arg calls.
- UE4SS Debug GUI (`UE4SS-settings.ini` `[Debug]` `GuiConsoleEnabled = 1`, `RenderMode = GameViewportClientTick`)
  gives Live View of all objects; Ctrl+R reloads Lua mods.
- If UE4SS.log shows repeated `AOB scan` failures then `Fatal Error`, nothing of ours loaded: a game update needs new
  UE4SS signatures, or AV interference, or a corrupt install. Not a mod bug.

## Property-diff probe (what changed between two moments)
Snapshot every reflected property (`ForEachPropertyInChain`, bools as 0/1, object refs by name, arrays by count, the
rest as raw bytes) of the pawn, its controller, their subobject components, plus any manager or world actor you
suspect (`FindFirstOf` / `FindAllOf` by class name), at a "good" moment and again after the event; log only the
differences, with noisy names (Location, Rotation, Velocity, Time, Tick, Bounds...) filtered. Gameplay flags often lag
the animation: take the baseline from a ring of snapshots 6-8 s before the state edge, not the last one. Source:
Campfires `zonekit/tools/probe/ImmCampProbeCpp` (`TakeSnap`, `LogDiff`, `BagDiff`). Limits, both seen: state kept in
non-reflected C++ members never shows (the save lock after a sit), and a diff can surface an incidental change that is
not the cause (a detector reference in `ItemAppearanceComponent.SecondaryItemInHands` after a backpack consumable).

## Symptom metrics
Measure the symptom itself, per second, before theorising. Mouse look: `PlayerController.GetInputMouseDelta` against
the change of `ControlRotation` (count samples with a small non-zero delta and no rotation); that found an
`InputTriggerDown` actuation threshold of 0.5 on a mouse-look row (`input.md`). Look stalls: `bHadCameraInputLastTick`
/ `LastCameraInput` vs ControlRotation; hitches: `GameplayStatics.GetWorldDeltaSeconds`.

## Reading a crash without symbols
The AV address and the log's stack often suffice to name the native function: take the exe base (from UE4SS's
`ProcessLocalScriptFunction` address and its signature file), function starts from the exe's `.pdata`, and the exec
thunks from the `FNameNativePtrPair` tables in `.rdata`; a frame inside an exec thunk names the UFunction the script
VM was calling (that is how `PC.IsVaulting` / `PC.HasNightVisionAnimation` were identified). Minidumps: the exception
stream + MemoryListStream + a link map work without a debugger.

## Control tests
When a symptom might not be ours, park our dev pak (outside `Content\Paks\`) and have the tester repeat the exact
steps. Known not-ours: the sleep black-screen soft hang (vanilla with all paks off sleeps fine; with the tester's mod
set it hangs; bisect order if the tester wants it: UltraPlusExtensions → UObjectCacheMod → other time/weather mods).
