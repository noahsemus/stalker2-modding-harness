# The Zone Kit as a research tool

Default location `G:\Epic Games\STALKER2ZoneKit` (`<kit>`; see `harness/config.json`). The kit is both GSC's UE 5.5
mod editor (`Stalker2ModEditor.exe`, a monolithic Shipping build) and the best available reference for how the game
works. Research order for any new system: **(1) grep the dumps and cfgs, (2) ask the tester to open matching assets
in the editor, (3) only then build something.**

## Files to grep
| Path | What |
|---|---|
| `<kit>\bp_api_dump2.txt` | Python-generated dump of every reachable Blueprint class, UFunction and UProperty (1677 classes). Always grep first for whether a function/property exists and its BP signature and access (e.g. the `PC` player class members start around line 5141). |
| `<kit>\bp_api_dump.txt` | Older dump; the only one with **enums** (e.g. `PlayerTriggerState` at line 5084). |
| `<kit>\Stalker2\Content\GameLite\GameData\**\*.cfg` | All game data in GSC's cfg struct DSL: prototypes (items, weapons, NPCs, effects, abilities), `CoreVariables.cfg`, `InputMappingContextPrototypes.cfg` (IMC names, priorities), dialogue, quests. See `config-files.md`. |
| `<kit>\Stalker2\Config\` | Engine/game ini (e.g. `DefaultInput.ini`, still with legacy axis mappings). |
| `<kit>\Stalker2\S2_WwiseProject\GeneratedSoundBanks\Windows\Event\*.txt` | Every Wwise event with samples, switch groups, states (the `.txt` form is the compact one). |
| `<kit>\Stalker2\Content\Paks\FullEditor-WindowsModEditor.pak` | The uncooked game content (388 GB). `UnrealPak <pak> -List` lists the index (slow; save it once to the scratchpad; `-Filter` does not filter). `tools/pak/extract_from_pak.py` pulls single uncompressed assets out by offset. |
| `%LOCALAPPDATA%\Stalker2\Saved\` | The player's side: `CustomizeControls.cfg` (rebinds), `Config\WindowsEditor\EditorPerProjectUserSettings.ini` (editor), game logs `Logs\Stalker2*.log`. |

Editor Python sees more than the dumps: native **enum values** (`[x for x in dir(unreal.ActionType) if x.isupper()]`),
an asset's triggers/modifiers, class function lists (`dir(unreal.SomeClass)`). Run read-only snippets in the open
editor with `ue_exec.py` before asking the tester to look. Properties that are not BlueprintVisible/EditAnywhere
are invisible to Python; for those, ask him to open the Details panel.

Engine source 5.5 is readable without a clone: `gh api repos/EpicGames/UnrealEngine/contents/<path>?ref=5.5`
(needs the GitHub account linked to Epic Games).

## Asking the tester to look (this beats blind iteration every time)
Grep shows names only. Graph wiring, data-asset values, component defaults, pin bindings and references live in the
editor. Ask targeted questions, e.g.:
- "Content Browser, search `DA_Weapon*`, open the one for the AKM, screenshot the Details panel."
- "Open `BP_X`, Event Graph, Ctrl+F `Reload`, screenshot the wired nodes."
- "Right-click asset W → Reference Viewer, screenshot."
- Better still for graphs: have him select all (Ctrl+A) and copy (Ctrl+C) and read the clipboard, or export the
  graph yourself with `tools/editor/export_t3d.py` through `ue_exec.py` (no tester needed).

Precedent: a full day of blind iteration on a strafe animation ended in 20 minutes once he opened the anim BP and it
showed `MovementPlayRate` was a struct with `RightValue / ForwardValue / PlayRate`, not a float.

## What is worth opening
- Real Blueprints: `BP_*`, `AnimBP_*`, widget BPs `W_*` (event graphs, anim graphs, state machines, bindings).
- Data assets `DA_*` / `DS_*` (the Details panel is meaningful), anim sequences / montages (Notifies and Curves
  tracks), IMC / IA assets.
- **Not** native classes: almost every `/Script/Stalker2` class (`PC`, `CameraModifier_*`, `AnimNotifyState_*`,
  `*IPU` input handlers, the player controller, `PlayerEnhancedInputComponent`) is C++ with no graph ("C++ Class"
  in the Content Browser). Look for the assets that *use* them instead (e.g. anim sequences carrying a notify state,
  data-asset instances of a native class), and use Reference Viewer on assets, not classes.

## Useful asset paths
- Input: `/Game/_Stalker_2/data/input/InputMappingContexts/IMC_*` (`IMC_Exploration`, `IMC_Dialog`,
  `IMC_DialogOnTheGo`, `IMC_PlayerCA`, `IMC_NoInput`, `IMC_Cutscene`, ...), actions under
  `/Game/_Stalker_2/data/input/InputActions/` (subfolders such as `Delayable/`, `Guitar/`).
- Player: `/Game/GameLite/Blueprints/Characters/Player/BP_Stalker2Character` (pawn, parent `/Script/Stalker2.PC`),
  `/Game/_STALKER2/Animations/Player/AnimBP_Player`, `AnimBP_Player_Shadow`, weapon layers such as
  `AnimBP_player_bh` (bare hands), `AnimBP_PlayerWeaponLayer`, `AnimBP_Player_Knife`.
- Player anim sequences: `/Game/_STALKER2/Animations/Player/AnimSequences/` (items, pda, bpa (backpack),
  contextual_action/...). Skeleton `/Game/_STALKER2/SkeletalMeshes/SK_stalker_Skeleton`.
- UI: `/Game/GameLite/FPS_Game/UIRemaster/...` (e.g. `Dialogue/W_DialogueView`, `W_SkipHintView`).
- ModKit classes for mods: `ModWorldSubsystem` (see `runtime-host.md`), GameFeatureData per mod.
