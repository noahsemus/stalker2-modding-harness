# Linux with Proton

The harness runs on Linux: the Zone Kit and the game run under Proton (Wine), the harness tools under PowerShell 7
(`pwsh`) and the system `python3`. Proven setup: Zone Kit installed with the Heroic Games Launcher (Epic account) into
its own Wine prefix, driven by a GE-Proton build; the game from Steam with Proton; mods cooked, installed and released
from Linux (2026-08 → 2026-11). The harness's Linux branch itself (the `.ps1` changes) is new: report what breaks.

## What runs where
| Piece | On Linux |
|---|---|
| Zone Kit editor (`Stalker2ModEditor-Win64-Shipping.exe`) | Heroic (Epic) → its Wine prefix (`kit_prefix`), started from Heroic |
| Cook, `CreatePlainMod`, headless editor Python, UnrealPak | the harness calls `RunUAT.bat` / the `-Cmd` editor / `UnrealPak.exe` through `<proton>/files/bin/wine` with `WINEPREFIX=<kit_prefix>` (`Invoke-Win` in `tools/common.ps1`) |
| Game | Steam + Proton, prefix `steamapps/compatdata/1643320/pfx` (`game_prefix`) |
| Harness `.ps1` tools | `pwsh -File harness/tools/<tool>.ps1` (PowerShell 7 for Linux) |
| Harness `.py` tools outside the editor | system `python3` (3.10+; same scripts as the kit's embedded 3.11 on Windows) |
| Scripts inside the editor (`ue_exec.py`, `run_headless.ps1`) | the editor's own Python under Wine; the prelude hands them Wine paths |
| `.pak` listing / unpacking | `repak` (native, `cargo install repak`) for plain `.pak` files, or `UnrealPak.exe` through Wine for IoStore `.utoc` |

## Setup (agent runbook; replaces `setup.md` steps 0-2 on Linux)
1. **The user installs**: Steam + the game, started once with Proton (creates the game's prefix); the
   [Heroic Games Launcher](https://heroicgameslauncher.com/) logged in to Epic, then *S.T.A.L.K.E.R. 2 Zone Kit* from
   it (~600 GB), started once until the editor window is fully open. In Heroic's game settings for the kit pick a
   Proton build (GE-Proton worked; Wine-GE / plain Wine untested) and note the prefix it shows.
2. **Programs** (distribution packages, the agent installs after asking): `git`, `gh`, `python3`, `rsync`, PowerShell 7
   (`pwsh`: Microsoft's packages for Debian/Ubuntu/Fedora, `powershell-bin` on Arch, or the `.tar.gz` from the
   PowerShell GitHub releases unpacked anywhere on PATH). Optional: `repak`.
3. `pwsh -File harness/tools/setup.ps1`. On Linux it reads Heroic's config (`~/.config/heroic` or the Flatpak's
   `~/.var/app/com.heroicgameslauncher.hgl/config/heroic`): `legendaryConfig/legendary/installed.json` → `kit`,
   `GamesConfig/<app>.json` → `kit_prefix` (`winePrefix`) and `wine` (`wineVersion.bin`'s folder + `files/bin/wine`);
   Steam's `libraryfolders.vdf` (native, `~/.steam/steam` or Flatpak) → `game` and `game_prefix`. Anything it can't
   find it names; write it into the settings by hand.
4. Then `setup.md` steps 3-6 as on Windows (`-Fork`, `-EnableRemotePython` with the editor closed in Heroic).

## Machine settings (`~/.config/stalker2-modding-harness/settings.json`, or under `$XDG_CONFIG_HOME`)
Same keys as on Windows, Linux paths with forward slashes, plus:
| Key | Example | Used for |
|---|---|---|
| `wine` | `~/.local/share/Steam/compatibilitytools.d/GE-Proton10-34/files/bin/wine` (absolute) | every Windows program the tools start |
| `kit_prefix` | `<Heroic prefixes>/S.T.A.L.K.E.R. 2 Zone Kit` | `WINEPREFIX` for those programs; its `dosdevices` drive letters decide the Wine paths |
| `game_prefix` | `<steam library>/steamapps/compatdata/1643320/pfx` | logs, crashes, saves, rebinds |
The coordination board (`coord.ps1`) lives next to it in `coord/`.

Call the prefix's `files/bin/wine` directly with `WINEPREFIX` set. The `proton` script itself (`proton run ...`)
returns at once while the program keeps running, wraps it in the Steam Runtime sandbox (paths outside it are invisible),
and swallows stdout; the tools need the exit code and the log.

## Paths
- Windows programs get Wine paths. The tools convert every Linux-path argument (`-Project=/media/...`,
  `-script=/tmp/...`) with the prefix's `dosdevices`: the longest matching drive wins (`u: -> /media` turns
  `/media/games/Kit` into `U:\games\Kit`), `z: -> /` is the fallback every prefix has. Inside response files and editor
  scripts write the same form yourself (`hconf.win_path()` in Python, `ConvertTo-WinPath` in PowerShell).
- The game's `%LOCALAPPDATA%\Stalker2` is `<game_prefix>/drive_c/users/steamuser/AppData/Local/Stalker2`
  (`$GameUserDir` / `hconf.GAME_USER_DIR`): `Saved/Logs/Stalker2.log`, `Saved/Crashes/`, `Saved/STEAM/SaveGames/`,
  `Saved/CustomizeControls.cfg`. Every `%LOCALAPPDATA%\Stalker2\...` path in these docs maps there.
- The kit's own `%LOCALAPPDATA%` / `%APPDATA%` (editor settings, UAT logs) are under
  `<kit_prefix>/drive_c/users/<user>/AppData/` (`steamuser` with Proton). UAT logs:
  `.../AppData/Roaming/Unreal Engine/AutomationTool/Logs/<kit path>/`.

## Cook under Proton
- It works with the same `GSCCookMod` command and flags (`pipeline.md` § 4-5), only slower: in 2026-08 each pass spent
  ~21 min starting up (Wine file access over the kit's mounted paks), 40-45 min per full cook; on the 2.0 kit one
  measured cook took 6 min 27 s (2026-10-07). See `cook-performance.md` § Linux / Proton and its two real savings
  (override-only cook, repack without the editor).
- The editor may stay open in Heroic during a cook (same prefix, one wineserver).
- **Stopping a cook**: killing `pwsh` does not stop it. `dotnet ... AutomationTool.dll GSCCookMod ...` and
  `Stalker2ModEditor-Win64-Shipping-Cmd.exe -run=Cook ...` keep running and keep writing to `SavedMods/`. Kill those by
  pid, matching the mod name and `AutomationTool` / `-Cmd`; never a bare `Stalker2ModEditor-Win64-Shipping.exe`
  (without `-Cmd`): that is the tester's open editor. A cook killed between its passes leaves a half-staged tree
  (OverrideContent only); re-cook before installing.
- Finding processes: `pgrep -f Stalker2-Win64-Shipping` matches the shell running pgrep itself. Read `ps -eo pid,args`
  and match `Stalker2-Win64-Shipping\.exe` (the tools do this in `Find-ProcessLine`).

## Game and testing
- Install works with the game closed exactly as on Windows (`install_paktest.ps1`); there is no Vortex on Linux, so the
  "release copy shadows the test build" check concerns hand-installed or Steam Workshop copies: a Workshop
  subscription and a `~mods` copy of the same mod both mount.
- Launch from Steam (`steam steam://run/1643320`) only when the tester asks.
- UE4SS probes under Proton: not covered by the harness tools yet; building them needs Windows / Visual Studio
  (`diagnostics.md`).

## Editor remote Python (`ue_exec.py`)
The editor under Wine uses the host network, so UE remote execution (UDP multicast 239.0.0.1:6766, then a TCP command
connection) should reach it from the host `python3`; `ue_exec.py` imports `remote_execution.py` from the kit folder.
Not yet confirmed on Linux: run `check_setup.ps1` with the editor open, and fall back to `run_headless.ps1` (works,
same prelude) or pasting into the editor's Output Log if it reports no editor node.

## Other Windows programs
- Wwise Authoring / WwiseConsole run in the kit's prefix: `audio-wwise.md` § Linux / Proton (one wineserver per
  prefix, sandbox-visible paths, capturing WwiseConsole output). Audiokinetic's launcher and licence site refuse
  Linux: use a Windows VM for those few steps.
- Saves: `tools/saves/s2sav.py` loads Oodle from the kit's `liboo2corelinux64.so.9` (`saves.md`).
