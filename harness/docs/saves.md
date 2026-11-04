# Save files (.sav)

What a save holds, how to open and repack one, and the quest-node name-table limit that makes saves unloadable when
mods add too many quest nodes. Tool: `harness/tools/saves/s2sav.py` (stdlib Python, Oodle through ctypes).

## Where they are
| What | Path |
|---|---|
| Saves | `%LOCALAPPDATA%\Stalker2\Saved\STEAM\SaveGames\Data\*.sav` (one file per save, hex-GUID names) |
| Save index | `%LOCALAPPDATA%\Stalker2\Saved\STEAM\SaveGames\CampaignsSave.sav` (same compression, no name table) |
| Temporary campaigns | `...\SaveGames\TempCampaigns\` |
| Automatic backups | `%LOCALAPPDATA%\Stalker2\Saved\Backups\<SteamID>\<timestamp>\` (copies of all saves) |

- Do not write into the live save folder unless the tester asks; unpack into a scratch folder (`-o`).
- Saves are compressed: grepping a `.sav` for SIDs finds nothing. Unpack first.
- The game log (`Stalker2.log`) carries nothing about gameplay, quest nodes or mods (`console-commands.md`), so a
  save is one of the few places where quest progress is visible outside the game.

## Format (checked 2026-10-31 on game patch 2.0.x saves)
- `.sav` = little-endian `uint32` uncompressed size + one **Oodle Kraken** stream.
- Oodle ships with the kit: `<kit>\Engine\Binaries\DotNET\AutomationTool\oo2core_9_win64.dll`
  (`OodleLZ_Decompress`, `OodleLZ_Compress`, `OodleLZ_GetCompressedBufferSizeNeeded`; also in
  `...\DotNET\UnrealBuildTool\`). A 5 MB save unpacks to ~23 MB.
- The decompressed save is binary Unreal data without field names. It opens with the list of installed paks (UTF-16,
  e.g. `<ModName>Stalker2-Windows.pak`) and ends with the **quest-node name table**:
  `uint16 count`, then `count` x (`uint16 length` + chars, no NUL) up to EOF.
- In the saves checked the table follows the bytes `GlassToy_14_Christmas\0\0`. The tool reads it from there and
  falls back to scanning the last 8 MB for a run of entries that ends at EOF and is preceded by its own count.
- The save body refers to quest nodes by `uint16` index into that table.
- Most strings in the body are a `uint16` length + chars with no NUL, so a printable length byte sticks to the text
  in a plain strings dump (`&CantBeKnockedDown...` = length 0x26 + text).
- Values (quest states, global variables, inventory) are not decoded by any known tool. What you can read: the name
  table (every quest node the save refers to), all readable text in file order (quest, prototype, global-variable
  IDs, paks), and text that appears/disappears between two saves.

## s2sav.py
```
python harness\tools\saves\s2sav.py list [dir]                  # newest first: time, size, name count, file
python harness\tools\saves\s2sav.py unpack <sav>... -o <dir>    # <file>.sav.raw
python harness\tools\saves\s2sav.py names <sav|raw> [--dump]    # count; --dump = "index<TAB>name"
python harness\tools\saves\s2sav.py strings <sav|raw> [--grep RE] [--offsets] [-n 6]
python harness\tools\saves\s2sav.py diff <a> <b> [--grep RE]    # "- " only in a, "+ " only in b
python harness\tools\saves\s2sav.py pack <raw> -o <sav>         # compress a .raw back
```
- Every command takes a `.sav` (decompressed in memory) or a `.raw`. Oodle: `--oodle <dll>`, env `OODLE_LIB`, or the
  kit path from the harness settings. Runs on the kit's embedded Python.
- `strings --grep <ModPrefix>` finds one mod's traces (its quest nodes, global variables, pak);
  `diff` before/after a quest step shows what the step wrote.
- **Repacking**: `pack` round-trips byte for byte through `unpack` (re-checked 2026-11-01), but the game has not been
  tested with a repacked or edited save. Keep the original; verify in game before relying on it.

## The 65,535 quest-node name limit (found 2026-10-31)
**Symptom.** Crash on load, or at boot before the main menu (the boot preload reads the newest save), inside
`FCrc::MemCrc32`. Every save written after some point in a playthrough crashes; older saves still load. It looks like
save corruption or a render/Lumen crash and is neither (an earlier reading as a Lumen issue was wrong).

**Mechanism.** The table count and the body's indices are 16-bit. With more than 65,535 distinct names the count wraps
(66,400 is written as 864) and only `count mod 65,536` entries are written. On load an index past the end of the
short table returns a junk FString and hashing it crashes.
- Call chain, retail exe as installed 2026-10-29 (RVAs; they move on every patch): `FCrc::MemCrc32` crash at
  `0x2357b73` (null string) / `0x2357c61` (garbage string) ← name reader `0x22cce46` ← `0xab7d9b` (reads the u16
  count, then the names) ← `0xab78dc` ← quest manager `0xab3e90` (in game) or boot preload `0x1fbbaf6` (main menu).
- The table grows as quests run, so a playthrough crosses the limit later than install time: a mod set that is fine
  on a new game can kill a save 30 minutes later.

**Numbers (one playthrough, 2026-10-31).**
| Save | Names | |
|---|---|---|
| long vanilla playthroughs | 46,000-50,000 | healthy |
| same playthrough with large quest-node mods | 53,917 | loads; one debug mod alone contributed 20,558 |
| 26 min later | 504-864 | overflowed, crash on load |
| 10 backups in between | 601-1,909 | overflowed |
| 42 older backups | 34,844-53,550 | load |

The mods involved had ~32,800 and ~16,800 quest nodes; 12,275 of the latter came from one per-location x per-tier
(N x M) node fan-out.

**Reading a count.** A healthy late-game save shows tens of thousands. A count in the hundreds or low thousands in a
mid-game save means it overflowed. A brand-new game also has a small count, so compare with older saves of the same
playthrough.

**Rules for mods.**
- Budget roughly **15k quest-node names for all installed mods together** on top of a late vanilla playthrough.
- No N x M quest-node fan-out (per location x per tier, per NPC x per state). Drive repeated work through a few nodes
  plus global variables, console-command nodes, or data in prototypes (per-rank blocks) that need no nodes at all.
- Keep debug/test mods with generated node graphs out of `~mods` during real play.
- After a large quest-node change, run `s2sav.py list` on a fresh save from a long playthrough.
- An overflowed save cannot be repaired: the missing names were never written. Remove the mod that pushed it over and
  restore an older save from `Saved\Backups\<SteamID>\<timestamp>\`.

## Related
- `diagnostics.md` § Control tests: the save itself as a suspect, picking a save from before a mod ran.
- `console-commands.md`: `XExportSaves`, `XLoadLastSave`, `XCallQuickSave`, `XTriggerAutoSave`.

## Linux / Proton
- Saves live inside the game's Proton prefix: `<prefix>/drive_c/users/steamuser/AppData/Local/Stalker2/Saved/STEAM/
  SaveGames/Data/`, with `<prefix>` = `<steam>/steamapps/compatdata/1643320/pfx` (1643320 = the game's Steam app id;
  `<steam>` is the library that holds the game, two levels above the game folder `steamapps/common/<game>`).
  `CampaignsSave.sav`, `TempCampaigns/` and `Saved/Backups/<SteamID>/` sit at the same relative places.
- Oodle for a native Linux Python: the kit's `Engine/Binaries/DotNET/AutomationTool/liboo2corelinux64.so.9` (same
  exports). `s2sav.py` picks it automatically off Windows; saves default to the harness setting `game_prefix`, else env
  `S2_PROTON_PREFIX`, else `~/.steam/steam/steamapps/compatdata/1643320/pfx`; or pass the folder to `list`.
