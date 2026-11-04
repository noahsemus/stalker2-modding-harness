# Cook performance: where `GSCCookMod` time goes, what helps, what does not

Measured on 4 mods (cfg-only to asset mods) in Aug 2026 and once more on the 2.0 kit (2026-10-07), all under Proton.
Native Windows cooks take 5-6 min (`pipeline.md` §5); the structure below holds for both, the absolute numbers are Proton's
(§ Linux / Proton).

## Anatomy of a cook
- `GSCCookMod` (what the editor's Package Mod runs) drives **two child passes**, `GSCCookModOverrideContent` and
  `GSCCookModNewContent`, each a full `Stalker2ModEditor-Win64-Shipping-Cmd.exe` start. Before starting, the parent wipes
  `<kit>\Stalker2\SavedMods\{Cooked,Staged}\<Mod>`; a child run clears only its own variant.
- Per pass: editor start-up (AssetRegistry directory discovery, the `BaseGame` cfg refresh of ~151k loose `.cfg`) →
  the cook commandlet → two `UnrealPak` runs that write the shipped containers.
- **The commandlet itself is short** (42-56 s for small mods; 150 s for a 58-package asset mod with 129 shader jobs),
  and `UnrealPak` takes ~1.1 s. Everything else is start-up and shutdown.
- Read timings from `Log.json`, the only UAT log with timestamps:
  `%APPDATA%\Unreal Engine\AutomationTool\Logs\<kit path, "\" → "+">\` (child logs per pass alongside). Compare
  `Execution of commandlet took: <s>` with `Took <s> to run Stalker2ModEditor-Win64-Shipping-Cmd.exe`. Trust these over
  remembered numbers: a stale "21 min/pass" comment once sent a whole investigation the wrong way.

## Real savings
1. **Skip the NewContent pass when the mod has no new packages** (empty `NewPackages.txt`). Its output is then only
   the `.uplugin` plus a stub `AssetRegistry.bin`, identical for every mod. Run just the override child, as the kit's
   own `PakPlainMod.bat` does:
   `RunUAT GSCCookModOverrideContent -CustomConfig=ModCookOverrideContent "-AssetsToCookWithDLCList=<...>\OverridePackages.txt"
   "-AssetsToNeverCookWithDLCList=<...>\NewPackages.txt" -Project=<uproject> -PluginPath=<uplugin> -TargetPlatform=Win64
   -BasedOnReleaseVersion=Latest -UnrealExe=<...Cmd.exe> -nocompile -nocompileuat` (the parent passes the lists via
   `-PackageClassifierOutputDir`). Halves a cold cook; applied to 71 of 85 mods. The override pass is the one that
   carries the loose `.cfg` patches, so it always runs. Delete a stale `Cooked\<Mod>\Windows\NewContent` and
   `Staged\<Mod>\Windows\NewContent` left by an earlier full cook, or a stale half ships. Check before a release that
   skipping does not drop a NewContent pak users already have.
2. **Repack without the editor when only loose files changed** (cfg edits, re-publish, recompress): replay just the
   packaging tail from the existing `SavedMods\Cooked\<Mod>` tree. Cfg-only change: whole cook → ~9 s. Byte-identical
   `.utoc` / `.ucas` and response files on four mods. The two commands (verbatim from a UAT log):
   - loose pak: `UnrealPak.exe <uproject> -cryptokeys=<Crypto.json> -patchpaddingalign=1048576 -blocksize=1048576
     -compressionformats=Oodle -compresslevel=4 -compressmethod=Kraken -platform=Windows -compressionblocksize=256KB
     -CreateMultiple=<PakCommands.txt>`
   - IoStore container: `UnrealPak.exe <uproject> -CreateDLCContainer=<Mod>.uplugin [-RemapPluginContentToGame]
     -PackageStoreManifest=<packagestore.manifest> -CookedDirectory=<Cooked> -Commands=<IoStoreCommands.txt>
     -ScriptObjects=<scriptobjects.bin> -patchpaddingalign=1048576 -blocksize=1048576 -compressionformats=Oodle
     -compresslevel=4 -compressmethod=Kraken -compressionblocksize=256KB -cryptokeys=<Crypto.json>
     -compressionMinBytesSaved=1024 -compressionMinPercentSaved=5 -WriteBackMetadataToAssetRegistry=Disabled
     -BasedOnReleaseVersionPath=<Releases\Latest\Windows>`
   - `-RemapPluginContentToGame` is the only difference between variants: present for OverrideContent.
   - `PakCommands.txt`: `"<out>\<Container>.pak" -create="<PakList.txt>"`; `IoStoreCommands.txt`:
     `-Output="<out>\<Container>.utoc" -ContainerName=<Container> -ResponseFile="<PakListIoStore.txt>"`. List lines:
     `"<abs src>" "../../../<dest>" -compress`.
   - Entries: every file under the cooked tree **minus** `Metadata\` and minus anything not below `Stalker2/Mods/<Mod>/`
     (drops a cooked `WorldMap_WP.umap` stub UAT also excludes). NewContent adds the `.uplugin`
     (`Stalker2/Mods/<Mod>/<Mod>.uplugin`); OverrideContent does not, and adds the mod's loose cfgs from
     `Mods\<Mod>\Content\GameLite\GameData\**` (only GameData; `DLCGameData` cfgs are not packed by the kit cook).
   - Dest: OverrideContent remaps `Stalker2/Mods/<Mod>/Content/X` → `Stalker2/Content/X`; NewContent keeps the path
     relative to the cooked dir.
   - `.uasset` / `.umap` → `PakListIoStore`, each followed by its **`.ubulk` / `.uptnl`**. `.uexp` is listed nowhere
     (IoStore finds it; listing it corrupts the container). **Bulk files left out are silently dropped**: UnrealPak
     exits 0 and the package has no bulk chunk (Wwise events lost their media, 7 MB → 151 KB). Everything else
     (`.cfg`, `.uplugin`, `AssetRegistry.bin`) → `PakList`.
   - Order: a directory's own files before its subdirectories, alphabetical within a level (not a plain string sort;
     order decides the byte layout).
   - Response files: UTF-8 **with BOM**, **CRLF** including after the last line, absolute paths with backslashes.
   - `packagestore.manifest` is not the authority on what gets packed (it lists the excluded `WorldMap_WP.umap`); use it
     only as a cross-check that every package you emit is in it.
   - The kit names response files in `<kit>\Engine\Programs\AutomationTool\Saved\ResponseFiles` after the container
     only, so the two variants of one mod overwrite each other there: keep your own copies.
   - With an empty cooked tree (nothing new), UnrealPak exits 3: skip that variant.
3. Decide per change by content hash, not mtime: identical inputs → skip; only loose files differ → repack; any
   `.uasset/.uexp/.umap/.ubulk/.uptnl` differs → cook.

## Verifying a repack or a cook against another
- `.pak` bytes never match between runs: the path-hash seed is random per run (not derived from the file name), so
  compare unpacked entries (`repak unpack` / `UnrealPak -Extract`), not bytes. `.utoc` / `.ucas` are reproducible.
- Time-derived bytes to tolerate: `__ModKitWwiseCookAnchor_<unixtime>__` (differs between the two passes of one
  cook), `Autogenerated_<unixtime>_*`, `Manifest_UFSFiles_Win64.txt` (ISO mtime per line), and what contains them
  (`Metadata\`, `ChunkManifest\*.txt`, `.pak/.ucas/.utoc`). A file present on one side only is always a failure.

## Disproved theories (each looked convincing; measured under Proton, 2026-08-27)
| Theory | Result |
|---|---|
| Derived Data Cache latency (132 GB `Compressed.ddp` reported 24.85 ms latency) | `TotalGets = 363`, `Assets Built: 0`: ~9 s total |
| The ~151k `.cfg` GameData load (reportedly what GSC devs blame) | Real but 189 s of 1214 s start-up (~15%) |
| `AssetRegistryDiscoveryCache=AlwaysWrite` in `Stalker2\Config\DefaultEngine.ini` (kit ships `Never` in `Engine\Config\BaseEngine.ini`) | Not honoured on this path: no `AssetDiscovery cache` log line, identical timing |
| Cache warming | The GameData tree (351 MB) stays in the OS page cache; nothing to warm |
| `DirectoriesToNeverCook` | Affects what is cooked, not the start-up scan |
| Hiding GameData cfgs (`SpawnActorPrototypes` = 86% of the cfg files) during the cook | Safe (output identical) and pointless: −3.7% (1322 → 1273 s) |
Untried: `-AssetGatherAll=false` / `EditorGameScansAR=false`, the switch that skips the initial asset scan.

## Linux / Proton
- Under Proton the start-up dominates: Aug 2026 (pre-2.0 kit) each pass took ~21 min, of which AssetRegistry discovery
  was 1214 s and the commandlet 42-56 s; full cook 40-43 min. Cause: Wine's per-file syscall overhead across the four
  mounted content paks (578 GB) and the loose cfg tree: enumerating the cfg tree took 38 s under Wine vs 0.16 s native,
  linear in file count.
- 2.0 kit, 2026-10-07 (one run, cache state not controlled, cause of the speed-up unknown): full two-pass cook of an
  asset mod 6 min 27 s.
  | Pass | Editor process | Commandlet | UAT child |
  |---|---:|---:|---:|
  | OverrideContent | 139.8 s | 56.8 s | 144.4 s |
  | NewContent | 235.1 s | 149.6 s | 239.3 s |
- UAT logs live in the prefix: `<prefix>/drive_c/users/steamuser/AppData/Roaming/Unreal Engine/AutomationTool/Logs/<kit path>/`.
- Run UnrealPak for a repack through Wine with NT paths (`Z:\...` or the prefix's drive letter) inside the response
  files; the editor round-trip it skips is where Proton loses the most.
