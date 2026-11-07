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
- **Saving stays locked after a contextual action the game did not finish itself.** Ending the campfire sit by
  `ResetInteractionTarget` (and even calling `RestoreStatesAfterInteraction` / `EnableInputAfterInteraction` after)
  left "can't save now" until a reload; the lock is not in any reflected property of the pawn or controller. Let the
  sit's own exit run: `SetInteractionTarget(<seat component>)` resumes it, `InjectInputForAction(IA_PlayerCAExit)`
  at idle exits it (Campfires v1.0.1).
- The vanilla sit's `SaveStatesBeforeInteraction` is only undone by its own exit (weapon half-state otherwise).
  Calling `SaveStatesBeforeInteraction` / `RestoreStatesAfterInteraction` from a mod stores the weapon (hand type 0)
  but pinned the view pitch at its minimum and left WASD dead after standing: don't.
- Binding `IA_PlayerCAExit` (Started) in a mod actor is fine (Campfires since build 20). The crashes once blamed on it
  were post-process ABP swaps (`animation.md`). While `IMC_PlayerCA` is applied, W/A/S/D/Space/F/Esc all arrive as
  `IA_PlayerCAExit`, not as movement; if it stays applied after a sit (e.g. after re-entering the vanilla sit from a
  mod), the player can look but not walk: remove it via the local player subsystem's `RemoveMappingContext`.
- The sit montage `MG_fp_ca_gd_bonfire`: In 0-4 s, Idle 4-10 (loops), Out 10-14. The vanilla sit waits for the
  `InteractAction` notify at 3.9996 s: `Montage_JumpToSection("Idle")` skips it and leaves the sit state unset (stuck);
  `Montage_SetPosition(3.93)` skips the sit-down and still fires it.
- Guitar: `IA_GuitarContextualAction` is in `/Game/_Stalker_2/data/input/InputActions/Guitar/`; it only works inside
  the vanilla sit (setting `bInContextualAction` and injecting the action from a mod's own seated mode does nothing).
  `AnimInstancePlayer.GuitarData.bPlayingGuitar` tells when the guitar is out.
- `Obj.ChangeMainHandWeapon(None, ...)` did nothing after a takeover; `Obj.RemoveWeaponFromHands` hides the weapon
  (the hand type stays the weapon's, so idle weapon fidgets and re-equips still play).
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
- `PC.GetControlRotation` (pawn) and `Controller.GetControlRotation` are overridden and return the camera's view,
  not `ControlRotation`; the controller actor's rotation never updates. A pose that drives `jnt_camera` from them is a
  feedback loop (shake, no look). The first-person camera is the `jnt_camera` bone (a root child); the game's look
  pitch is `AnimInstancePlayer.CameraData.ClampedControlPitch`, the explicit time of
  `fp_bh_stand_lookvertical_idle` (mesh-space additive, 1 s: 0 = +90 deg, 1 = -90 deg); it equals `ControlRotation`
  pitch exactly. Yaw from `GetControlRotation` is fine (the actor yaw follows it).

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

## PDA (ImmersivePDA research 2026-10-16; kit data + headless reads, not yet probed in game)
- Open: `IA_OpenPDA` (P, pad Special Left; Tap + 1 s Hold triggers) and `IA_WorldMap` / `IA_Journal` / `IA_Note` in
  `IMC_Exploration` -> native `PDAOpenIPU` -> USE_PDA (`ActionType` 24). `PC.StartUsePDA(PDAPageType)` is BP-callable
  (MAP 0, JOURNAL 1, NOTES 2, UPGRADES 3, STATISTIC 4, BESTIARY 5, TUTORIAL 6). `OnPDAUseStarted/EndedBP` exist on
  `PC` but only a pawn override can implement them; mods poll `IsUsingPDA`. Every page pushes its own **Exclusive**
  context (`IMC_PDA_Map` ... `InputMappingContextPrototypes.cfg:59-228`), none with look or walk rows; close =
  `IA_UI_PDA_Close` (Esc / M / P / pad B).
- Animation: `AnimCollection_fp_pda` -> player `MG_fp_pda` (MainActionSlot, 2.3 s: In 0-1.0, Idle loop 1.0-1.133, Out
  -1.967, OutFast -2.3) + device `MG_pda_fp` on `SK_pda` (`AnimBP_PDA`), posture `AnimBP_Player_TwoHandedItem` (as the
  backpack). `AnimNotify_UseHandItem` at 0.833 s opens the UI. No FOV / camera modifier: the device is simply held
  13 cm before the eye (fills the view), `jnt_camera` pitches to -20 deg. The device anims are in character space
  (`jnt_item` stays at the root). Unused-looking `MG_fp_pda_EMP_a` / `MG_pda_fp_EMP_a` (3 s, no UseHandItem) hold it
  ~34 cm ahead with the world around it.
- UI: `W_PDABookView` (native `PDAView`), a fullscreen UMG view with cursor (like `W_Inventory`); the map is
  `BP_WorldMapScene`'s ortho SceneCapture -> `RT_WorldMap` (2048x1024) via `M_WorldMapUIMaterial`. The device's own
  screen material `MI_PDA_Screen` is plain emissive (no texture input).
- Slop yCam suspends itself entirely while `IsUsingPDA` (`compatibility.md`).

## Pickup and looting (Looting research, 2026-10-09; kit only, not yet probed)
- Every loose item in the world is one of two generic actors, `BP_StaticItemContainer_C` /
  `BP_SkeletalItemContainer_C` (`/Game/GameLite/Blueprints/Interactable/ItemContainers/`, `CoreVariables.cfg`
  `StaticItemContainer` / `SkeletalItemContainer`), parent `InteractableItemContainer` (line 3751); visual in its
  `MeshComponent`, interaction in a native `ItemContainerInteractionComponent` plus `ItemContainerHold`. Item cfg
  `MeshPrototypeSID` → `MeshPrototypes.cfg` `MeshPath` is the world mesh; the item's own `MeshPath` is the
  first-person hand mesh.
- Pickup of a loose item is instant (no anim collection on the container BPs). Already animated in vanilla:
  artifacts (`BP_Artifact` → `AnimCollection_PickupArtifact` → `MG_FP_Player_AR/Det_ArtifactPickup_01`,
  MainActionSlot, forces `AnimBP_Player_TwoHandedItem`), mutant parts (`MutantLootAnimCollection(WithoutWidget)`,
  `UseMutantLootWithoutWidget = true` → `MG_fp_bh_creaturestash_looting_common`), body carry
  (`MG_fp_dead_body_pickup`). Corpse search and stashes only open the loot window.
- `IA_Interact` (`InputActions/Delayable/`) is mapped in `IMC_Interactivity` (F / gamepad face-left, priority High,
  `InputMappingContextPrototypes.cfg:229-235`), not `IMC_Exploration`; tap vs hold is native (`HoldTime`,
  `HoldPreventFromDefaultInteractionPercent`).
- `PC.get_interaction_target()` (5193) → `InteractionComponent` under the crosshair; `get_interacted_actor` /
  `get_interacted_component` (5191-5192). `InteractionComponent` (3823) has delegates `on_interacted_event`,
  `on_end_interacted_event`, `on_notify_interact_event`, `on_montage_ended`; `HoldComponent` (3553)
  `on_hold_started/finished/interrupted_event` (BlueprintAssignable or not: unchecked).
- No BP-visible "item added to inventory" event (`ItemManager` has no members; quest `OnPlayerGetItem` needs a fixed
  item SID; the pawn's `on_next_item_to_take_set_bp` needs a pawn override). The pickup sound
  (`PlayerItemsSounds.sfx_pick_up` → `SFX_Item_Pickup`) is posted natively.
- The loot window is the backpack view: corpse search, world stashes, the player's own stash and the I key all open
  `W_Inventory` (parent native `InventoryNew`; `CoreVariables.cfg` `InventoryWidgetClass`) with input context
  `IMC_Inventory` (Exclusive); traders use `W_Trade` / `IMC_Trade`. The widget BP has no logic (open, take, take all,
  drag/drop are native). A mod can see "window open" with `EnhancedInputLocalPlayerSubsystem.HasMappingContext`
  and read the weight texts (`...InventoryWidget / LootGridWidget → WeightBar → CurrentWeightText`, `W_Text_C`,
  `TextWidget.GetText`) by finding them by path name. World stashes (`BP_Stash*`) are subclasses of the item
  container actors; the own stash is a native `PlayerStash` (Looting research 2026-10-09, kit only).
- Which inventory an item used in the loot window came from has no BP-visible signal: the native hook is the pawn
  event `Obj.OnBeforeUseItem_BP(ItemUID)` (D2:4992; a pawn override), `ItemUID` has no BP queries, the right-click menu
  (`RightClickMenuWidget`, enum `ERightClickMenu`: Use, Take, TakeAll, Put, Drop, Equip, ... in the retail exe) is
  native. `IMC_Inventory` maps LMB double-click to both `IA_UI_Inventory_UseItem` and `IA_UI_Inventory_LootTakeItem`
  (native picks by grid); the right-click menu has its own Exclusive context `IMC_RightClickContextualMenu`. Usable
  evidence: the two weight texts (Immersive Looting 2026-11-07, unconfirmed in game).

## Quest doors and signals (ImmersiveBattleFixes 2026-11-06, SIRCAA, in game)
- Quest doors (`BP_DoorView`, double glass doors) are World Partition actors in `WorldMap_WP`, not in the quest logic
  levels. Their receivers (Lock / Unlock / Open / ForceOpen `SignalReceiverComponent`s) are found in the kit's
  `WorldMap-WindowsModEditor.pak` by pairing each GUID with its `BndEvt__BP_DoorView_<Receiver>` delegate; quest
  `SendSignal` node names often lie about the component (`..._ForceCloseReceiver` was a Lock).
- A door signal sent while the player was 40-80 m away did not take effect (E06_MQ02's unlock / open of
  `nii_Door_05` / `_06`; vanilla relies on it); the same signals sent from `Trigger` nodes when the player walks into
  the area next to the door worked. Re-send door signals from a nearby trigger (`TrackBeforeActive = true`) when a
  mod depends on them. (Assumed cause: the door actor is not loaded when the signal arrives.)
- A forced `SetDialog` gated by a `DistanceToPoint` pin (E06_MQ02 Dalin, 4 m) never started for the tester, with or
  without this mod; launching the same SetDialog from an extra launcher group 3 s after the previous dialog ends
  started it (forced dialogs start at any distance).

## Rendering: reflections and ray tracing (research 2026-11-06, game 2.1.0, retail exe + kit exe + UE 5.5 source)
- **No hardware ray tracing is possible from paks, ini or shaders.** Retail and the Zone Kit editor were both built with
  `RHI_RAYTRACING=0` (a UBT compile-time define): the `TEXT()` literals inside `#if RHI_RAYTRACING` in UE 5.5's
  renderer, D3D12 RHI and Lumen HWRT files are absent from both exes (e.g. `FLumenReflectionHardwareRayTracingCS/RGS`,
  any `/Engine/Private/RayTracing/` path, `FTrivialMaterialCHS`), the IID of `ID3D12StateObjectProperties` is absent,
  and the retail global shader map (7,688 shaders) and all 21 material shader archives hold 0 ray tracing shaders.
  Cooked with `r.RayTracing=False` (retail `Stalker2/Config/DefaultEngine.ini:149`; `r.Lumen.HardwareRayTracing=True`
  at :150 is a dead leftover). The `r.Lumen.HardwareRayTracing*` cvars and `BuildRaytracingAccelerationStructure`
  (a D3D12 method-name table) are present but inert. Only native code (injected DLL building its own DXR / inline
  RayQuery pass) could add ray tracing: a months-long project.
- Lumen is software only: screen traces, then mesh SDFs (only up to `r.Lumen.TraceMeshSDFs.TraceDistance` from the
  surface, shared with GI), then the global SDF + surface cache. Vanilla `ReflectionQuality@3` sets
  `r.Lumen.Reflections.TraceMeshSDFs=0`.
- Water is Single Layer Water. Its Lumen reflection pass (UE 5.5 `LumenReflections.cpp`) never traces mesh SDFs (opaque
  pass only), is never temporally denoised and always runs at full resolution: off-screen water reflections come from
  the global SDF (`r.LumenScene.GlobalSDF.Resolution`) + surface cache. `r.Water.SingleLayer.Reflection` 3 forces SSR.
- `r.Nanite.DisableFallbackMeshes` is a GSC cvar ("saves extra VRAM used by nanite fallback"); retail sets it True.
- A user `%LOCALAPPDATA%\Stalker2\Saved\Config\Windows\Engine.ini` is not present by default; graphics mods (Ultra+)
  set cvars at runtime from UE4SS Lua, which outranks ini values for the cvars they touch.
- `r.ReflectionMethod` is overruled by the GSC cvar `r.ReflectionMethod.Override` (scalability sets it to 1 = Lumen
  on every `ReflectionQuality` level): to switch reflection method set the `.Override` cvar (2 = SSR; tester saw the
  change, 2026-11-06). Same pattern exists for `r.DynamicGlobalIlluminationMethod.Override`.
- Planar reflections do not show (tested 2026-11-06): the code and global shaders are in retail
  (`FPlanarReflectionPS`, `TPrefilterPlanarReflectionPS`), `r.AllowGlobalClipPlane=False` (only a warning in UE 5.5),
  and a `/Script/Engine.PlanarReflection` spawned from UE4SS Lua (`World:SpawnActor`, at the player's feet, fade
  400-800 cm, 50/100 %) gets its `PlanarReflectionComponent`, but the tester saw no mirror image with Lumen or SSR
  reflections. Characters occluding the background in reflections (screen traces have no data behind them; the
  fallback is the SDF / surface cache, which has no skinned meshes) therefore has no fix short of ray tracing.
- NPC hair is Groom (HairStrands): each hairstyle = a strands groom `..._STR` plus a cards groom `..._CAR` in
  `AdditionalGrooms` (`GroomGeneratorPrototypes.cfg:95-114`; faces via `AttachMeshPrototypes.cfg` `GroomPrototypeSID`),
  quality copies picked by `mg.HairQuality`. Strands LODs are visible only at close-up screen sizes (head hair STR
  LOD2 invisible below 0.35; CAR LOD0 invisible), so strands appear only in dialogue / cutscene close-ups; stock 5.5
  groom LOD has no hysteresis. Dialogue: FOV 90 -> 70 (`CoreVariables.cfg:332-333`), DOF f/32 (:334-336), GSC cvar
  `ai.AgentLODBiasForCinematicsAndDialogs` (default -1) changes NPC mesh LOD. GSC cvar `r.HairStrands.ForceLOD`
  ("Force the hair LOD to this value", default -1). Research: ImmersiveFixes
  `zonekit/research/2026-11-06-npc-hair-flicker.md`.
