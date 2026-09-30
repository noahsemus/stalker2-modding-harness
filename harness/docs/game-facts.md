# Verified game behaviour

Facts established in game (probe or tester) or from the kit, with the mod that found them. Add to this whenever a
mod learns something about the game itself. Line numbers refer to `<kit>\bp_api_dump2.txt` unless noted.

## Player (`PC`, `/Script/Stalker2.PC`; runtime class `BP_Stalker2Character_C`)
- Class members from line ~5141. Useful BP surface: `can_use_inventory`, `contextual_action` / `bInContextualAction`
  (BP-writable, but writing it changes nothing by itself), `is_interaction_in_progress`, `is_using_pda`,
  `is_inspecting_artifact`, `start_use_pda(initial_page_type)`, `start_use_backpack()`, `consume_planned_item`,
  `SetMoveVector` / `MovementInputVector` (the game's own move feed), `IsInStaticDialog`, `IsInCinematic` (on `Obj`),
  `ResetInteractionTarget` / `GetInteractionTarget` / `SetInteractionTarget`, `EnableInputAfterInteraction`,
  `DisableInteractions` / `EnableInteractions`, `ToggleFOVAndForegroundRender`, `ChangeMainHandWeapon`,
  `EquipLastHeldItem`, `HasItemInMainHand`, `IsLeftHandBusy`, `IsUsingBackpack`.
- The native move handler drops `IA_LocomotionForward` while `IsInStaticDialog()`, but not look (Dialogue).
- `IsInStaticDialog()` is also true in story cutscenes that run through the dialogue system; guard with
  `NOT (IsInCinematic OR controller.IsLookInputIgnored)` (Dialogue 2.0.3).
- `IsInStaticDialog` reads a non-reflected pointer at `[PC+0x650]` that is null during the sleep transition (a native
  hook calling it then crashes; Blueprint callers are fine).
- The dialogue ends by distance (`DialogDistance = 5.0` in CoreVariables) possibly while a key is held, so an input
  action's `Completed` can be lost; zero anything the mod fed after a short stale window (Dialogue 2.1.1).
- `CoreVariables.cfg` `MaxInteractionDistance = 200` applies to every interaction; NPC dialogue distance is
  `MinDialogInteractDistance` / `MaxDialogInteractDistance` on the object prototypes (base `[0]`: 75 / 130; ~75 named
  NPCs override it).

## Interactions and contextual actions (Campfires)
- A campfire sit is a `PlayerContextualAction` actor (`BP_PlayerContextualAction*` next to `BP_Stalker2Bonfire*`):
  sets the contextual-action flag, clamps camera yaw/pitch to the actor's limits, pushes `IMC_PlayerCA` at priority
  Exclusive (`InputMappingContextPrototypes.cfg:294-298`).
- The game treats the sit as an **interaction in progress** for its whole length; native PDA / backpack open paths
  refuse while it is (keys and even direct `StartUsePDA` / `StartUseBackpack` calls do nothing). Clearing the
  interaction target ends the sit itself. Hence "own seated mode": take over after the vanilla sit-in, then
  `ResetInteractionTarget`, clear the flag, `EnableInputAfterInteraction`, `ToggleFOVAndForegroundRender(true)`,
  `DisableInteractions` (hides the seat prompt), and play the pose ourselves.
- The vanilla sit's `SaveStatesBeforeInteraction` is only undone by its own exit (weapon half-state otherwise).
- Binding `IA_PlayerCAExit` in a mod actor crashed (the game's delayable handler treats the bound object as the PC;
  AV in the `PC.IsVaulting` thunk).
- `CppMediator.lerp_player_to_location_and_rotation`, `CppMediator.start_quest_node(sid)` exist (seat placement,
  time-skip leads).

## Input
- Gamepad via GameInput.dll, not XInput. DualSense without Steam Input is not an XInput device.
- Quick slots have no BP-callable entry on `PC` (only `consume_planned_item`, which needs a natively planned item).

## Camera
- `CameraModifier_LookAt` centres the camera on the NPC in dialogue; `FindCameraModifierByClass` →
  `DisableModifier(true)` → `RemoveCameraModifier` per tick removes it.
- Actor yaw drags `ControlRotation`; `bOrientRotationToMovement` rotates the actor on strafe in dialogue. Camera
  decouple = camera `Set Absolute` (rotation) + `Set World Rotation(Get Control Rotation)`, restoring the saved relative
  rotation after.
- Camera-manager view pitch/yaw limits can be set per tick for a seated look clamp.

## Player actions, sprint, reload (Reloading research, 2026-09-30)
- The player's action system is native: `ActionType` (read with `unreal.ActionType` in editor Python; includes
  `RELOAD_WEAPON`, `UNLOAD_WEAPON`, `UNJAM_WEAPON`, `SPRINT`, `RUN`, `JOGGING`, `USE_CONSUMABLE_ITEM`, `USE_PDA`,
  `USE_BACKPACK`, ...), `PlayerTriggerState` (`RELOAD_TRIGGER`, `SPRINT_TRIGGER`, `SPRINT_STARTED_TRIGGER`, ...),
  driven by montage notifies `AnimNotify_PlayerAction` (END / INTERRUPT) and `AnimNotify_PlayerActionTrigger`.
  `PC.is_action_active(ActionType)` tests whether an action runs. `MagazineReloadState`: DEFAULT, EJECTED, INSERTED,
  NONE (`Obj.get_current_reload_state`).
- `Obj` (player base) BP surface: `can_enter_to_sprint`, `is_sprinting`, `is_should_sprint`, `reload`,
  `reload_weapon`, `interrupt_reload`, `finish_reload`, `is_reload_available`, `set_speed_multiplier` /
  `get_speed_multiplier`, `update_movement_speed`, `force_set_sp` / `get_sp` / `get_max_sp` (stamina);
  `PC.velocity_multimplier` (sic, Read-Write), `PC.on_sprint_released`.
- Vanilla (player reports, to confirm): sprinting cancels a reload (it restarts from the beginning); pressing reload
  while sprinting drops to a run and reloads. No cfg field governs it; `IA_Sprint` and `IA_Reload`
  (`InputActions/Delayable/`) carry **no triggers or modifiers** (checked 2026-09-30), so there is no asset-side
  blocker: the rule is native. There is no `ReloadIPU`; `SprintIPU` is native.
- Blocking an action by data: effect `EEffectType::BlockAnimationActionType` with `BlockAnimationTypes`
  `EActionType::Sprint` (vanilla `BlockSprintEffect`, permanent, used for heavy exoskeletons; `ConcussionBlockSprint`
  is timed, `Duration = 3`). Stamina gates sprint through `StaminaDisableThresholds` (16.1) and overweight state tags.
- Reload speed by data: effect `EEffectType::ReloadingTime`, `ValueMin/Max` in %, **negative = faster**
  (`ReloadingTimeDecBy25` -25%; sleepiness applies +15% / +18.75% to the player; OXA puts them on magazines). Per
  weapon: `WeaponReloadTimePerAttachment` multipliers (lower = faster) in `WeaponGeneralSetupPrototypes.cfg`, likely
  shared with NPC weapons.
- Applying an effect from Blueprint: no direct function. Candidates: `ApplyEffectComponent.apply_effects(target)` /
  `remove_effects` (its effect list is not visible to Python; check the Details panel), or
  `CppMediator.start_quest_node(sid)` on a mod quest node `EQuestNodeType::SetCharacterEffect` (empty target = player,
  as in `QuestNodePrototypes/Benchmark_combat.cfg:273`; no "remove effect" node exists, use timed effects). Neither is
  tested yet.
- ~540 first-person reload montages (`MG_*reload*`) sit behind per-weapon `AnimCollection_fp_*` data assets
  (`PlayerFirearmAnimCollection`) and the layer graph `AnimBP_PlayerWeaponLayer` / `AnimLI_PlayerWeapon*`.

## Items and UI
- Artifact inspection has no input action of its own; it launches from the backpack UI.
- The dialogue skip hint `W_SkipHintView` has native show logic (`SkipHintView` base); the BP is layout + fade only.
- Trading opens inside the dialogue (`IsInStaticDialog` stays true) and takes UI-only input.
- No BP-exposed API opens the PDA / inventory views directly (nothing on UIManagerEx / ViewBase / CppMediator).
