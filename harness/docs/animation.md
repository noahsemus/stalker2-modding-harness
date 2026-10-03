# Player animation: what is known

Mostly from ImmersiveDialogue 2.0-2.1 (walk in dialogue, arms, gestures) and ImmersiveCampfires (own seated mode).

## Structure
- The player mesh's main anim instance is `AnimBP_Player` (parent `AnimInstancePlayer`, native). Its native update
  pushes ~23 BlueprintReadWrite data structs (`StateData`, `LocomotionData`, `CameraData`, ...) into the main
  instance only. The struct members are mostly **not** Blueprint-writable (`Set members in AnimPlayerStateData`
  exposes only `CombatIdleDuration`), so a mod computes its own values and reroutes bindings instead of writing them.
- Weapon / hands poses are composed in **linked anim layers** (e.g. `WeaponLayer` → `AnimBP_player_bh` for bare
  hands; weapon-specific layer BPs for guns). Idle / Moving poses come out of that layer.
- Slots: `FullBody` sits **after everything** in `AnimBP_Player` (`PreFullBodyPose` cache → Slot FullBody →
  LayeredBoneBlend with no layers → out), so any FullBody montage hides the arm-action layers
  (`PreActionFullbodySlot` → `MainActionSlot` / `UpperBody` inside the bh layer). Item use (eat, drink, PDA,
  backpack) plays in MainActionSlot / DefaultSlot / UpperBody.
- Dialogue gestures are montages on the main instance (`IsAnyMontagePlaying` true). Linked layers with
  `bUseMainInstanceMontageEvaluationData` read montage data from the component's main instance.
- The camera hangs off `jnt_camera` (child of `jnt_root`, not the head). With `bUseControllerRotationYaw` off only
  the aim offset turns, not the camera.
- Curves such as `AdditiveMovingUpperBody` read 0 on all instances (not a usable signal).

## Safe ways to change animation without overriding `AnimBP_Player`
- **Post-process anim instance** (ImmersiveDialogue 2.1): a mod ABP (parent `AnimInstancePlayer`, not plain
  `AnimInstance`) attached with `SetOverridePostProcessAnimBP`, switched with `SetDisablePostProcessBlueprint`. A
  disabled post-process instance is neither updated nor evaluated. Copy the main instance's data structs onto it
  every frame, and set its `WeaponLayer` node's Instance Class statically (`LinkAnimClassLayers` at init did not
  take). **Attach exactly once per world, ~1 s after the pawn appears, outside any dialogue / interaction**, via the
  mesh-swap trick: save hidden bones → override None → `Set Skeletal Mesh Asset` (another mesh) → override = ours →
  mesh back → `ToggleFOVAndForegroundRender(true)` → re-hide the saved bones. Armour changes re-create it.
  **Disabling it leaves its last frame's notifies firing** (UE 5.5 source): the mesh still calls
  `DispatchQueuedAnimEvents` on a disabled post-process instance every frame
  (`ConditionallyDispatchQueuedAnimEvents` has no disabled check) and only an update or `InitializeAnimation`
  empties its `NotifyQueue`. Switched off on a frame where its walk played a footstep (`AnimNotify_AnyFootOnGround`
  on the `ar` walk / run sequences), that footstep repeats every frame until it is switched on again
  (ImmersiveDialogue "nonstop footsteps after a conversation"). Re-enabling (the setter, also behind a `SET
  bDisablePostProcessBlueprint` node) runs `InitializeAnimation` → `UninitializeAnimation` → `NotifyQueue.Reset`, so
  one tick after switching it off, switch it on and straight off again. Linked layer instances of it keep being
  updated (`TickAnimInstances` updates every `LinkedInstances` entry), which resets their own queues.
- **Dynamic montages in the mod's own slot group** (ImmersiveCampfires): e.g. a looping additive made from a game
  sequence (`AnimSequence` duplicated, tracks rewritten from Python, additive against a reference frame) played in
  `FullBody` with its own slot group so UpperBody/action montages don't cancel it; heal with
  `IsPlayingSlotAnimation`. Paused dynamic montages with the frame set per tick work as pose tables (sit yaw ×
  pitch).
- Rebinding pins inside an override (`Select Float` on our flag, rules OR'd with our flag) works but makes the
  asset a conflict magnet; frozen-interface lesson in `compatibility.md`.

## Crash families (do not retry)
- `SetAnimInstanceClass` on the player mesh: `EXCEPTION_ACCESS_VIOLATION reading 0xa00` at once (native code keeps
  the instance it created at spawn).
- `SetOverridePostProcessAnimBP(..., Reinit=true)`: AV reading `0xac0` (reinit without waiting for the parallel anim
  task).
- **Any post-process swap during play that overlaps a native interaction** (contextual-action sit): AV in exec
  thunks of `PC.IsVaulting` / `PC.HasNightVisionAnimation` (native code treats the post-process instance as the
  player's `AnimInstancePlayer` while the interaction runs). Even swapping ImmersiveDialogue's own class back after a
  sit crashed. Only the single swap at load is known safe.
- Calling `GetCurrentStateName` / state-machine queries from outside the anim update (probe) faults.

## Dead ends
- Montage blend profiles as masks (UE 5.5 clears `ActiveBlendProfile` once the blend-in ends; BlendMask mode is not
  handled for montages).
- `DetectorLayer` (no input pose), a Linked Anim Graph pass-through (never offers an `In Pose` pin).
- Recooking `AnimBP_player_bh` as an override breaks the unarmed sprint left-hand animation from a fresh load, even
  with no edits. Duplicate it to a mod-only path instead.
- `BS_fp_bh_walk` is the bare-hands arm additive, not locomotion.

## Pose tables (Campfires, working)
- A seated pose that follows the view without an AnimBP: bake a sequence whose keys are the pose per view angle
  (yaw rows x pitch keys, 30 fps), play it with `PlaySlotAnimationAsDynamicMontage` in `FullBody` and set its position
  every tick from the view (actor ticks before the mesh: `AddTickPrerequisiteActor`). The montage does not stay
  paused (`Montage_SetPlayRate(0)` did not hold): set position = target - DeltaSeconds * rate so the anim update lands
  on the target. A plain pose also overrides `jnt_camera`, so bake the look pitch into it (see `game-facts.md`
  § Camera for the pitch source); an additive pose passes the game's look through.
- Item / PDA / backpack montages (`MainActionSlot`; mods may use `DefaultSlot` / `UpperBody`) key the hips 7.4 cm /
  19 deg away from `fp_bh_idle_stand`, the same as `fp_ar_idle_stand`: build an additive meant to run under items on
  `fp_ar_idle_stand`, or the legs swing while an item plays. Root children (`jnt_item` carries the PDA,
  `jnt_camera`, IK roots) must move with a lowered pelvis.
- Look up with `IsSlotActive(<slot>)` which kind of montage runs; `GetCurrentActiveMontage` returns the most recent
  one only, and from an actor's tick it is not reliable for "which item is playing" (Campfires: an item used from
  the backpack was never returned; a pose montage of ours was). Bind `AnimInstance.OnMontageStarted` instead
  (`K2Node_AddDelegate` + custom event, once per anim instance) and keep the last montage it reports. Dynamic
  montages from `PlaySlotAnimationAsDynamicMontage` with a big LoopCount have a huge `GetPlayLength`: filter them out
  by length. `Montage_SetPlayRate` / `Montage_IsActive` / `Montage_IsPlaying` with a None montage act on ANY montage.

## Vanilla behaviour worth knowing
- In static dialogue the native update keeps running but leaves `StateData.bMoving`, `bWalking`,
  `LocomotionData.MovementPlayRate.{Right,Forward}` at 0 and sets `bWalkingOverride = 1`;
  `StateData.bForceBindedHandsLookVertical` = 1 raises idle arms out of view (the vanilla "no arms in dialogue").
- The campfire sit (`MG_fp_ca_gd_bonfire`, slot FullBody, sections In → Idle (loops) → Out) comes with
  `AnimCollection_pca_bonfire` settings `bShouldLerpToInteractable`, `bShouldToggleFOV`: the sit turns the
  first-person FOV / foreground render off and only its own exit turns it back on
  (`ToggleFOVAndForegroundRender(true)` to restore; otherwise FP items render off-centre and the weapon vanishes).
- **`Obj.RemoveWeaponFromHands` swaps the stance/arm layer in one frame** (item stance -> empty hands: hips 7.4 cm /
  19 deg apart). Calling it while a pose of yours is blending in shows as the hips and both hands jumping (probe:
  hips 8 cm, hands ~30 cm in one frame). Call it only when your full-body pose is fully in.
- **Every vanilla consumable animation ends by reaching both hands to the weapon-ready pose** (the last 0.1-1.1 s;
  measured per item from the `AS_fp_*_use` sequences). If the weapon is hidden, that reach looks like grabbing
  nothing: leave the item (or hold it, `Montage_SetPlayRate` ~0) before its reach.
- Item animations do not all use `MainActionSlot`: the antirad injector plays in the bh layer's `LeftHand` slot
  (after MainActionSlot, `left_hand_blend_mask`). Slots in `AnimBP_player_bh` WeaponLayer, in order: MainActionSlot,
  RightHand / LeftHand (hand masks), CameraSlot, DefaultSlot, then the "Additional" input on the left hand; only
  `FullBody` in `AnimBP_Player` comes after all of them. Slot groups: MainActionSlot = ActionGroup, LeftHand =
  DefaultGroup, FullBody = FullBodyGroup (a montage in one group does not stop the others).
- A dynamic pose-table montage starts at frame 0 unless `InTimeToStartMontageAt` is set: blend it in from the right
  frame or the first frames blend a wrong pose.
