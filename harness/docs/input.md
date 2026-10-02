# Input: mapping contexts, rebinds, key sync

## How the game does input
- Enhanced Input. Contexts are `IMC_*` assets; `InputMappingContextPrototypes.cfg` names each context and its
  priority (e.g. `IMC_Exploration` priority Lowest; `IMC_PlayerCA` (campfire/contextual-action sit) **Exclusive**,
  which suppresses every lower context). Priorities and which context is active decide which keys exist at all.
- Native input handlers (`*IPU` classes such as `PDAOpenIPU`, `InventoryIPU`, `QuickSlot*IPU`) consume the actions
  and apply the game's own gates; they have no Blueprint surface and no cfg. A key reaching the action does not mean
  the action runs (`game-facts.md`). Use a **canary** row to tell "override not loaded" from "vetoed natively".
- Some IA assets carry action-level triggers (Tap / Hold / Down); `InputTriggerActionBlocker` would be an asset-side
  veto; check with `tools/editor/dump_imc.py` (prints `action_triggers`).
- The gamepad is read through **GameInput.dll** (Windows GDK), not XInput (XInput is called 4× at startup only).
  Relevant only to native hooks, which we do not ship.

## Player rebinds (Options > Controls)
- Stored by GSC, not Unreal's user settings: `%LOCALAPPDATA%\Stalker2\Saved\CustomizeControls.cfg`, one `struct`
  section per context (`Exploration`, `Aiming`, `Dialogue`, `PlayerContextualAction`, ...), rows with
  `PlayerMappableOption` (the row's mappable name, e.g. `MoveForward`), `InputActionSID`, `Key`, `OldKey`,
  `Triggers`.
- A rebind only reaches rows that carry the mappable name: `SettingBehavior = OverrideSettings` + a
  `PlayerMappableKeySettings` with the game's name. Rows built without it stay on their literal keys (AZERTY players
  then can't use them). Always check with `dump_imc.py` (`mappable` = `OverrideSettings/<Name>`).
- The game only writes a context's section when the player applies bindings with that context known, and it
  applies binds to the **game-path** object only. Don't rely on players re-applying bindings: sync keys at runtime.
- Layouts: Unreal names keys by what they type (the W position reports `Z` on AZERTY); the game does not translate
  layouts.

## Techniques
- **IMC override by moved objects** (headless): duplicate the vanilla context into the mod, duplicate the source
  context (e.g. `IMC_Exploration`) to a temp asset, and **move** its rows' modifier / trigger / mappable-settings
  objects (`rename(outer=override)`) into the override. Keeps dead zones, response curves and the game's custom
  `ApplySensitivity` modifier intact. Never save or `delete_asset` the temp (delete crashes the commandlet).
  Reference: ImmersiveDialogue `zonekit/tools/make_imc_override.py`; in place in the open editor:
  `add_mappable_to_imc.py` (same repo).
- **Load the game-path context by string** at runtime (`Make Soft Object Path`
  ("/Game/_Stalker_2/data/input/InputMappingContexts/IMC_X.IMC_X") → `To Soft Object Reference` →
  `Load Asset Blocking` → `Cast To InputMappingContext`), because the editor redirects `/Game` picks to the mod copy
  and only the game-path object carries the player's binds.
- **Runtime key sync** (ImmersiveCampfires build 18-19, works): load the game-path `IMC_Exploration` and the target
  context, `UnmapAllKeysFromAction` for the actions you carry, `MapKey` each exploration row's key for those actions,
  then `EnhancedInputLibrary.RequestRebuildControlMappingsUsingContext(target, true)`. The player's own keys work
  without any Options visit.
- **Own context instead of overriding**: add `IMC_<Short>` above the game's context on entry and remove it on exit;
  a higher-priority context shadows the same keys in lower ones without editing them. Remember what *you* added
  and remove only that (ImmersiveDialogue 2.0.1: re-adding `IMC_Dialog` after the UI removed it leaked the dialogue
  keys (Q/E/L, pad X/Y/D-pad) into free play until a reload).
- Two rows with the same key in one context fire both actions.
- **Check trigger thresholds when copying or overriding a context.** The vanilla `IMC_PlayerCA` mouse-look row
  (`IA_LookUp` / `Mouse2D`, `InputTriggerDown`) has actuation threshold 0.5, `IMC_Exploration`'s has 0.0: while that
  context handled the mouse, small slow movements were silently dropped ("laggy camera"). Measure with
  `PlayerController.GetInputMouseDelta` vs the change of `ControlRotation`, not by feel (Campfires v1.0.2).
- Input from a mod actor: `EnableInput` + EnhancedInputAction events; the events arrive through the game's own
  `PlayerEnhancedInputComponent`. Binding an action the game's delayable handlers also bind can crash
  (`game-facts.md`, `IA_PlayerCAExit`).
- Hints/prompts (the on-screen key legend) do not list rows a mod adds.
