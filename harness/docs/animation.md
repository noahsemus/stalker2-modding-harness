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

- **One montage per slot group, whatever `bStopAllMontages` says** (ImmersiveLooting 2026-10-18): a montage ASSET in
  `FullBody` started with `Montage_Play(bStopAllMontages = false)` right after a paused dynamic FullBody pose table
  stopped the table (probe: the table inactive through every test). Two offset tables cannot stack in one group;
  live per-bone offsets need a post-process layer (`Transform (Modify) Bone` nodes bound to variables).
- Slot groups of the player skeleton (from every player montage, `get_group_name` + `get_montage_slot_names`):
  DefaultGroup = DefaultSlot, LeftHand, RightHand, CameraSlot, WeaponSlot, DeathSlot; ActionGroup = MainActionSlot,
  SecondaryActionSlot, GadgetActionSlot / GadgetActionAimSlot; UpperGroup = UpperBody; FullBodyGroup = FullBody;
  PreActionGroup = PreActionFullbodySlot; CutsceneGroup = CutsceneSlot.

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
- **`LinkAnimClassLayers` of a game posture outside its native flow**: linking `AnimBP_Player_TwoHandedItem` (the
  backpack / two-handed-item posture, parent `AnimInstancePlayer`) into the WeaponLayer from a mod showed no right arm
  and crashed (AV in game code) ~0.5 s after the loot window closed, before any re-link (ImmersiveLooting 2026-10-13).
  The game links it itself inside `PC.StartUseBackpack`, which always ends in Skif's own inventory.

## The game's inventory (backpack) animation (ImmersiveLooting 2026-10-12/13)
- All native: `PC.StartUseBackpack` puts the weapon / hands away (an "unequip" montage, ~0.45 s), makes the backpack a
  hand item (`HandItem` BACKPACK; `AnimCollection_fp_Backpack`: `PlayerAnimBlueprint` = `AnimBP_Player_TwoHandedItem`,
  `PlayerAnimCollection` = `AnimCollection_fp_ar`), gives the hand-item mesh `SK_bpa_pla_01` + `AnimBP_Backpack` (a
  DefaultSlot over the bag idle), plays `MG_fp_backpack_inventory` (MainActionSlot; In 1.5 / Idle 5 / Out 0.667 /
  OutFast 0.333 s, blend 0) and `MG_backpack_fp_inventory` on the bag; `AnimNotify_UseHandItem` (0.567 s) opens the
  inventory (it is on screen ~0.45 s after the key, before most of the In); the close plays Out and an equip.
  `PC.OpenLootMenu` alone (no interaction in progress) does not turn that into a loot window.
- The bag sequences lock their root (`bForceRootLock`, reference rotation -90 deg about X); their keyed root equals the
  player's `jnt_l_weapon` (= `jnt_second_weapon`) every frame: the bag is held in the left hand. The bag's material is
  first-person (`_fov`). A runtime `SkeletalMeshActor` refreshes bones only when drawn (`AlwaysTickPose`): set
  `AlwaysTickPoseAndRefreshBones` or it stays in its reference pose behind the camera.
- What the backpack posture adds over the montage (`AnimBP_Player_TwoHandedItem`): `jnt_camera` and `jnt_weapon`
  copied from their virtual bones (the montage never moves the camera), `jnt_spine_03` taken from another pose in
  component space (the upper body follows the look), a smooth copy of `jnt_r_fore_arm`. Played over another posture in
  MainActionSlot the montage's camera key won (bare hands: view pitch -51 -> -75).
- Playing the bag sequences as an arms-only layer (montage asset with LeftHand + RightHand slot tracks, `Montage_Play`
  with `bStopAllMontages` false) works over Skif's own posture. Its blend-out must start only once the bag is below
  the view (the game's Out has it there from frame 16-18 of 20; its last frame snaps behind the back).

## Arms, hands and weapon (verified 2026-10-13, ImmersiveLooting)
- Look-vertical additives: `fp_ar_stand_lookvertical` and `AS_fp_bh_lowcrouch_lookvertical` turn spine, arms, hands
  and camera together; the standing bare-hands one (`fp_bh_stand_lookvertical_idle`) turns the camera but leaves the
  hands where they are, so an arm animation laid over bare hands standing drifts up out of view as you look down.
- `VB jnt_camera` and `VB jnt_weapon` are virtual bones under `jnt_spine_03`. The weapon follows `jnt_weapon`, which
  arm-masked slots never move.
- The weapon layer's hand IK (`TwoBoneIK_GSC`) pins each hand to the weapon mesh's own `jnt_l_hand` / `jnt_r_hand`
  socket, alpha `HandsIKData.LeftHand` / `.RightHand`, switched by `AnimNotify_HandIK` (`HandToApply` LEFT_HAND /
  RIGHT_HAND / BOTH_HAND). A weapon hidden with `SetHiddenInGame` stays in the hands, keeps the weapon posture, and
  its IK keeps the hand on the invisible grip until switched off.
- Weapon equip montages `MG_fp_<weapon>_equip` (MainActionSlot; notifies HandIK both on, `WeaponAction`
  UNLOCK_LEFT_HAND_IDLE, `PlayerAction` END EQUIP_MAIN_ITEM) can be replayed with `Montage_Play` on the player with
  the weapon already in hand (no side effects seen). Remember the last one from `OnMontageStarted`.
- Local-space blends take the short way per bone: blending two poses whose bone differs by ~180 deg flips direction
  frame to frame and shows as a near full spin. The vanilla `MG_fp_ak74_weapon_grab` has the left hand 120-180 deg
  from every weapon idle in frames 23-34 (hand at the chest): never blend out there.
- An actor ticking in `TG_PostUpdateWork` runs after this frame's animation update: a montage started there poses the
  mesh from the next frame, so show what it brings in (a weapon, a spawned mesh in its reference pose) 2 ticks later.
- **Left-hand gestures over a held weapon (ImmersiveLooting 2026-10-13, verified in game):** build them per weapon
  family on that family's own idle stance, as the game does (`MG_fp_ar_flashlight`, `MG_fp_pt_flashlight`, NVG per
  family). Long-gun idles' left hands (rifle / SMG / sniper / shotgun) lie within ~0-64 deg (local) of
  `fp_ar_idle_stand`, pistols within 24 deg of `AS_fp_pm_idle`; the vanilla AK grab's grip is 88 deg from a pistol's.
  A gesture keyed on another family's grip flips in the LeftHand slot's blend-in, and the weapon layer's hand IK
  (`AnimNotify_HandIK`) flips whenever it blends between two hand rotations ~180 deg apart: release it over ~0.06 s
  before the wrist turns, re-engage it only once the hand is back near the grip. Turn the wrist only after the slot's
  blend-in, one way round (no per-frame shortest path), half the turn into `jnt_l_fore_arm_roll`. The family stance's
  grip is a few cm off each weapon's own grip: end the keyed path left of / below it so the IK's last stretch comes in
  from the side away from the weapon (a straight return clipped through the barrel and wobbled).
- A left-arm local-space additive in FullBody over another weapon's grip pose (to make one gesture fit all weapons)
  looked "like jelly / alien": dead end.
- ZST's watch check: LeftHand-slot montages with `AnimNotify_HandIKState`, its smooth hand-back comes from its own
  `AnimBP_Player` override (`BPI_WatchPose.SetWatchPose(Alpha, PreserveGrip)`), not reusable without that override.

- **Turning a hand a set way round (Looting 2026-11-05):** a target orientation rolled by ~180 deg lets the slerp pick
  the way round (the tester asked for clockwise and got counter-clockwise). Interpolate the unrolled orientation and
  apply the roll on top, `roll(axis, angle x weight)`, so its sign decides. UE axes are left-handed (X forward, Y right,
  Z up): a NEGATIVE angle about the forward reach turns clockwise as the player sees it. Check with the thumb bone's
  screen angle frame by frame (atan2(dy, dz) relative to the hand).
- **The knife and the bolt** (EMainHandEquipmentType 4 / 6) hold the free left hand at (40, -24, -18..-20) cm from the
  eye in view axes at every pitch and stance: their layer = fp_ar_idle_stand + the item's mesh-space idle additive
  (`AS_fp_knife_idle_add` / `AS_fp_bolt_idle_add`) + the rifle look. Left-hand gestures for them are built on that pose
  with no HandIK-on notify (no grip: IK on pulls the free hand to the item's socket = "spinning hands").
- **Door leaves:** a door leaf mesh's pivot is its hinge (`SM_cit_out_door_a_04` 0..104 cm, cupboards -51..0), so the
  free edge = 2 x the leaf component's bounds centre - its location.

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
  `fp_ar_idle_stand`, or the legs swing while an item plays. Root children (`jnt_item`,
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

## First-person arms are drawn squeezed toward the view axis (Looting build 4, kit materials)
The arm / hand materials (`M_MasterHands` → `MF_ForegroundWithShadowSwitch` → `MF_Foreground`) move every vertex in
the vertex shader: `MF_Foreground_FOVCorrection` scales the sideways part (perpendicular to the camera forward) of the
camera-relative position by `s = tan(view hFOV / 2) / MPC_FOV.TanFOV` (`View.ClipToView[0][0]` / the arms' tangent),
then `MF_Foreground_AntiDepthClipping` scales the whole camera-relative position by `MPC_FOV.DepthScale` (0.225;
screen position unchanged). Bones and sockets are NOT moved: a normal world mesh placed at a hand bone shows up further
out than the hand (off screen at the edges). To place a world object where a bone is SEEN:
`C + F*dot(F, P) + (P - F*dot(F, P)) * lerp(1, s, MPC_FOV.IsFOVEnabled)` with `P = bone - C`, `C` / `F` the camera
location / forward (`PlayerCameraManager`), and scale it by the same `s`. `MPC_FOV` =
`/Game/_Stalker_2/Materials/MPC/MPC_FOV` (TanFOV, DepthScale, IsFOVEnabled, CurrentFOV, DisplayFOV).

## Left-hand actions over any weapon (Looting research 2026-10-09, headless read of the layer AnimBPs)
- Every weapon layer has a `LeftHand` slot behind `left_hand_blend_mask` (jnt_l_shoulder to the fingers, local-space
  rotation), after MainActionSlot / UpperBody, chained RightHand → LeftHand → CameraSlot → DefaultSlot:
  `AnimBP_PlayerWeaponLayer` (all firearms, `WeaponSlotsLayer`), `AnimBP_player_bh`, `AnimBP_Player_Knife`,
  `AnimBP_Player_fp_bolt`, `AnimBP_Player_fp_F1`, `AnimBP_Player_TwoHandedItem`, `AnimBP_PlayerDetectorLayer`
  (weighted by `DetectorData.bIsLeftHandSlotEnabled`). In `AnimBP_Player` itself LeftHand appears only in the guitar
  state. Slot group of LeftHand = the default group (with DefaultSlot, WeaponSlot, RightHand, CameraSlot).
- The left hand is held on the foregrip by `TwoBoneIK_GSC` (jnt_l_hand → `jnt_weapon`, alpha
  `HandsIKData.LeftHand.Alpha`, skipped while `StateData.bIsLeftHandBusy`), applied **after** the LeftHand slot. Montages
  switch it with `AnimNotify_HandIK` (HandToApply LeftHand; defaults Start 0 / End 0 / 0.2 s cubic = off; End 1 = on).
  Rifle / pistol LeftHand montages bracket themselves with an off and an on notify; a dynamic montage of a bare
  sequence has no notifies, so the hand stays glued to the grip.
- GSC's per-stance left-hand gestures: `Flashlight/Montages/MG_fp_<stance>_flashlight` and
  `NightVisionGoggles/Montages/MG_FP_Player_*_NVG-SwitchOn/Off_01` (LeftHand + WeaponSlot + CameraSlot), the
  injector `Items/Antirad/MG_fp_antirad_use`, `ar/common/showhide/lefthand/MG_fp_remove_left_hand_from_item` /
  `MG_fp_return_left_hand_on_item` (the latter turns HandIK on at 0.136 s: recovery for a cut left-hand montage).
- Unused vanilla left-hand **grab with a rifle held**: `ar/ak74/MG_fp_ak74_weapon_grab` (= gp37) on
  `ar/common/grabitem/fp_ar_weapon_grab`, 1.667 s, LeftHand, only the left arm moves (camera still). Firearm anim
  collections have a `WeaponAnimations.PickUpItem` field for it, filled only for the grenade-launcher AK / gp37.
- **The arm bones do not follow the view pitch** (Looting b4-b11 probe traces, empty hands): only `jnt_camera` pitches.
  A left-arm pose played in `LeftHand` that is right looking straight ahead ends ~50 cm above the view axis when
  looking 30 deg down. A reach meant to land somewhere on screen needs one pose per view pitch (or per item elevation):
  a table of segments in one sequence, started with `InTimeToStartMontageAt` and stopped with `Montage_Stop`.
- The empty-handed spine differs a lot from the rifle stance: the same left-arm locals put the hand ~40 cm higher.
  Solve left-arm poses on the stance's own spine (`fp_bh_idle_stand` matched the in-game rest hand to 1 cm).
- **With a weapon in hand the whole arm rig follows the view** (the weapon layer pitches `jnt_spine_03` with the
  look-vertical additive): a hand position relative to `jnt_camera` in a sequence is its position in view axes in
  game, whatever the view pitch (ImmersiveLooting 2026-10-10, three traces). Measured hand-bone landing for a planned
  camera-relative point: ahead + 8.4 cm, right x 1.14 + 4.0, up x 1.15 + 2.0 (the sideways scale ~ the arms' FOV
  squeeze). With **empty hands the arms stay in the body frame** (do not follow the pitch): aim per view pitch there.
- **Rifles with an underbarrel idle type pin the left hand**: `AnimBP_PlayerWeaponLayer` → `WeaponUnderbarrelIdleLayer`
  blends the `GripIdle` pose over the left arm with weight `FirearmData.LeftHandCurveValueInverse` = 1 - the montage
  curve `left_hand_curve`. A `LeftHand` montage without that curve plays (slot active, position advancing) but the hand
  never leaves the grip. The game's own left-hand gestures (`MG_fp_ar_flashlight`, NVG) carry `left_hand_curve`
  (0 → 1 in 0.17 s, held, back to 0 ~0.25 s before the end): add it to any mod-made LeftHand sequence
  (`AnimationLibrary.add_curve` + `add_float_curve_keys`).
- A 180 s "pose table" sequence (many segments, `InTimeToStartMontageAt`) works in the bh layer; over a rifle the
  same form never showed (cause not isolated; the curve may have been the whole reason). Many short sequences
  (one per bin) cook to ~15 KB each and are a safe alternative.
- With empty hands the left-hand IK still pulls a `LeftHand` montage's hand toward the grip point (`jnt_weapon`, just
  right of centre): a default `AnimNotify_HandIK` (LeftHand, End 0) at the start keeps it off; a "back on" one (End 1)
  makes the hand jump there.
- Left-hand item point: bone `jnt_l_weapon` (child of `jnt_l_hand`; the game's `AttachItem PickingUpItem` socket).
  `jnt_item` / `jnt_unequipped_item` / `jnt_camera` are root children, not hand bones.
