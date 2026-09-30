# Compatibility with other mods

## Principle
Per asset (and per whole `.cfg` file), the last-mounted pak wins outright. Nothing merges. Every override is a
conflict with every other mod shipping that asset, and whichever loses loses *all* its edits to it. So:
- Put logic in NewContent (`runtime-host.md`); override only data the mod cannot work without.
- cfg: patch files only (`config-files.md`), never whole files.
- When an override is unavoidable, rename the override pak `zzz_<Mod>_20_P` so it beats the usual `_P` / `_10_P`
  mods, and document the edit so other authors can merge it.
- Never hard-import another mod's assets from the main mod (it then fails to load without that mod). Optional
  integrations go in a separate optional plugin/pak.

## Checking a conflict
- `tools/pak/scan_mods.py <AssetName> ...` lists every installed container that mentions it and its mount order.
- Extract a container (`UnrealPak <x>.utoc -Extract <scratch>`) and read `zen_names.py` (names) / `--imports`.
- Shared assets seen in the wild: `AnimBP_Player` (ZoneWatch/ZST, WRP-type animation mods, S-Watch),
  `BP_Stalker2Character` (Slop yCam, ImmersiveDialogue ≤ 2.1), `IMC_Exploration` (Immersive HUD, ZST),
  `DA_InputElementsModels` (Controls menu entries: IHUD, ZST), `AnimBP_PlayerWeaponLayer` / `AnimBP_Player_Knife` /
  weapon AnimCollections (Slop yCam), `W_GameHUD` (IHUD), `CoreVariables.cfg` (FOV mods like No Dialogue Zoom).

## Known mods
- **ZST / ZoneWatch** (dannicroax, Nexus 2721): `BP_ZoneWatchSubsystem` → `BP_ZoneWatch` polls keys from
  `QueryKeysMappedToAction`; overrides `AnimBP_Player`, `IMC_Exploration`, `DA_InputElementsModels`; ships a combined
  `AnimBP_Player` as `_30_P` and once gated another mod's block on a per-cook anchor asset
  (`/Game/__ModKitWwiseCookAnchor_<Mod>_<timestamp>__`), which only exists in one build. Lesson: offer a
  **permanent marker asset** with an interface revision in its name (`tools/editor/create_marker.py`) and freeze the
  shared block; never tell others to detect cook anchors.
- **Immersive HUD** (Nexus 1895): NewContent under `/ImmersiveModePlus/` (own IAs, `IMC_ImmersiveHUD`, world
  subsystem `BP_ModWorldImp` → `BP_ModActorImp` with `EnableInput` and EnhancedInputAction events); overrides
  `IMC_Exploration`, `DA_InputElementsModels`, `W_GameHUD`, stat panel assets; **hard-imports MCM**.
- **Slop yCam**: override pak replaces `BP_Stalker2Character` and weapon anim assets, plus a UE4SS part polling
  `PC:IsInStaticDialog`. Hard conflict with any pawn override.
- **UltraPlus / UltraPlusExtensions** (UE4SS Lua): hooks sequence players, toggles DLSSG in cutscenes; suspect in
  soft hangs during sequences (sleep).
- **UObjectCacheMod** (UE4SS Lua): caches objects, rebuilds on transitions; probes must load before it.
- **Better Vaulting, grEdit**: examples of cfg `_patch_` style mods.

- **OXA** (Nexus 939): bpatches `WeaponReloadTimePerAttachment` and more for many weapons, adds ~27 weapons with their
  own arrays, `ReloadTime_Minus*` effects on magazines, and **overrides 38 vanilla `AnimCollection_fp_*`** (the
  player's per-weapon animation collections). Never override those; per-weapon cfg presets would fight OXA and miss
  its weapons.
- **grEdit Ballistics**: recoil/dispersion bpatches in the weapon file; **Better Stamina** patches Player
  `StaminaPerAction.Sprint`; **PIR** patches Player vitals and sleep-mechanic effects. All patch-file mods: only the
  same field collides.

## MCM (Mod Configuration Menu 2.0, Nexus 2225, by KynesPeace)
Community settings menu (Zone Kit NewContent under `/ModConfigurationMenu/`, opened in game from its own key).
Read from the installed containers with `zen_names.py` (2026-09-30):
- `BPI_MCM_API`: `AddUniqueModID`, `RegisterModSetting`, `RegisterDefaultModSetting`, `GetModSetting`,
  `SetModSetting`, `TriggerButtonAction` (params ModID, SettingID, Category, Type, AuthorName, SettingHoverText,
  Bool/Float/Int/String/Vector/Rotator/Transform values, Keybind, ComboBoxOptions, ButtonText,
  FloatControllerStepValue, header textures).
- `BPI_MCM_SettingsProvider`: `RegisterMCMSettings`, `RegisterMCMDefaultSettings`, `ApplyMCMSettings`,
  `OnMCMButtonPressed`.
- `Enums/E_MCM_SettingType`: bool, float, int, string, vector, rotator, transform, key, combobox, button.
- Discovery: `BP_MCM_Manager` calls `GetAllActorsWithInterface` and calls the provider interface on each, so **a
  provider is any spawned actor implementing `BPI_MCM_SettingsProvider`**. Values persist in the save game
  (`MWS_MCM` subsystem, `SG_MCM_Settings`).
- Author guide (Notion) and an "MCM Example Mod" are linked from the Nexus / Steam Workshop pages.

Rule: a Blueprint that implements or calls these interfaces hard-imports `/ModConfigurationMenu/...` and fails to
load without MCM (Immersive HUD's actor does this). So the main mod keeps settings as variables with defaults and
imports nothing from MCM; an optional `<Mod>MCM` plugin spawns the provider and writes values into the main mod's
actor. Open: whether a NewContent Blueprint in one plugin can reference another plugin's class and survive the cook
(untested; fallback = ship an MCM variant of the whole mod). Compiling needs MCM's interface assets in the kit (its
source plugin in `<kit>\Stalker2\Mods\`, from the example mod / guide).
