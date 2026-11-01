# Editor paste text: sockets, AnimCollection maps, Details-panel properties

Blueprint graph nodes as T3D paste text: `blueprints.md`. This file covers the other clipboard formats the Mod Editor
accepts. Generating text the tester pastes is the fast way to restore or add data on a fresh vanilla checkout
("Checkout selected content to mod plugin folder", `pipeline.md` §2); writing those assets from scripts is not
supported. Both formats below were pasted successfully into the 2.0 Mod Editor (weapon scope work, 2026-10-09).

## Skeleton sockets (`SocketCopyPasteBuffer`)
The tester selects any bone in the Skeleton tree and presses Ctrl+V; each socket lands on its own `BoneName`.
```
SocketCopyPasteBuffer
NumSockets=<n>
IsOnSkeleton=1
Begin Object Class=/Script/Engine.SkeletalMeshSocket Name="SkeletalMeshSocket_0"
   SocketName="X2ScopeSocket"
   BoneName="jnt_ejector"
   RelativeLocation=(X=3.838991,Y=-0.006127,Z=3.153408)
   RelativeRotation=(Pitch=0,Yaw=0,Roll=0)
   RelativeScale=(X=0.8,Y=0.8,Z=0.8)
End Object
IsOnSkeleton=1
Begin Object ...
```
- `NumSockets` must equal the number of blocks.
- Generate it from an asset instead of typing values:
  `python harness/tools/editor/socket_paste.py <SKEL.uasset> [--baseline <vanilla SKEL.uasset>] [--out <file>]`
  (kit Python or any Python 3, stdlib only). With `--baseline` it prints only sockets missing from the baseline, which
  recovers what a mod added once the asset was reset to vanilla. Sources for the old copy: the mod repo's history
  (`git show <rev>:<path> > old.uasset`), a backup, another mod folder.
- Reads uncooked packages in both property-tag formats: legacy (FileVersionUE5 1008, the pre-2.0 kit) and complete
  type names (1012+, the 2.0 kit writes 1013). Output verified byte-identical to the original tool on 8 current and 4
  legacy skeletons (2026-11-01). Rotators are serialised Pitch, Yaw, Roll; Vector/Rotator are 3 doubles.
- Put the text on the clipboard yourself (`Set-Clipboard -Value (Get-Content <file> -Raw)`).

## AnimCollection maps (`PlayerFirearmAnimCollection`)
Weapon attach animations live in `AnimCollection_fp_<gun>` under `_STALKER2/Animations/Weapons/<class>/<gun>/AnimCollections/`.
Third-person collections are not needed for scope attaches. Right-click the **map header** in the Details panel →
Paste. That **replaces the whole map**: have the tester Copy the header first and merge with the existing entries.

`InternalAnimations.AttachingBySID`: `Map<String, AttachDetachAnimations>`, key = attach SID:
```
(("RU_X2Scope_1",(AttachAnimation=(Character="/Script/Engine.AnimMontage'/Game/_STALKER2/Animations/Player/AnimSequences/shg/d12/Attaches/MG_fp_d12_sight_x2_attach.MG_fp_d12_sight_x2_attach'",Weapon=None,PlayRate=1.000000))),("RU_ColimScope_1",(AttachAnimation=(...))))
```
`AttachDetachAnimations` fields: `AttachAnimation`, `DetachAnimation`, `DetachTwinMagazineShifted` (each a
`CharacterWeaponAnimations`), `AttachAnimBlueprint`. Omitted fields keep defaults; vanilla scope entries fill only
`AttachAnimation`. (`Weapon=None` above shows the shape only; see the rules below.)

`InternalAnimations.ShootingWithScope`: `Map<Name, CharacterWeaponAnimations>`:
```
(("RU_X2Scope_1",(Character="/Script/Engine.AnimMontage'/Game/.../MG_fp_d12_shoot_aim_scope_x2.MG_fp_d12_shoot_aim_scope_x2'",Weapon=None,PlayRate=1.000000)),(...))
```
`CharacterWeaponAnimations` fields: `Character` (player-hands montage), `CharacterLeftHand`, `Weapon` (weapon montage),
`PlayRate`. A single struct value pastes onto one field the same way: `(Character="...",Weapon=None,PlayRate=1.000000)`.

### Borrowing animations from another gun (verified 2026-10-10/11)
- `Character` montages (player skeleton) can be borrowed only between guns held the same way. Rifle attach montages on
  a double-barrel shotgun moved the scope through the gun body and posed the fingers for an AK grip: the hands carry
  the scope to where *that* gun's receiver is.
- **Never leave an attach entry's `Weapon=None`.** Every working vanilla entry has a weapon montage; with none, the
  attach state never ends and the gun stays uninteractable until re-equipped. The weapon montage must be on the gun's
  own skeleton; a gun with no attach animation can use its vanilla equip montage (`MG_<gun>_fp_equip`).
- The scope is shown and mounted by `AnimNotify_AttachItem` markers on the **hands** montage (`AttachAction =
  JoinAttachToHand`, then `RemoveAttachFromHandAndAttachToWeapon`), followed by `AnimNotify_WeaponAction`
  `UnlockLeftHandIdle`. Without them the scope pops on when the montage ends. Clean attach for a gun with none: a new
  montage on `SK_stalker_Skeleton`, its own `AS_fp_<gun>_equip` sequence, slot `MainActionSlot`, those three markers
  copied (Ctrl+C / Ctrl+V on the Notifies track) from a vanilla attach montage, both AttachItem markers in the first
  ~0.1 s while the gun is lowered. Markers on a gun-skeleton montage do nothing.
- The montage editor previews only `DefaultSlot`; on `MainActionSlot` it shows a T-pose. Place markers with the slot set
  to `DefaultSlot`, switch back before saving.
- Borrowed `ShootingWithScope` entries pose the hands for the other gun while aiming; with no match, use the gun's own
  `MG_fp_<gun>_shoot_aim` / `MG_<gun>_fp_shoot_aim`.
- Find candidates in the asset registry or the FullEditor pak index (`zonekit.md`): montages are `MG_*`, the sequences
  behind them `AS_*`. Paths are case-insensitive in the editor.

## Any other property
Ask the tester to right-click the property (or one existing element) → **Copy** and paste the text back to you, or
read it from the clipboard yourself (`Get-Clipboard -Raw`); match that shape exactly. General rules seen so far: UE
struct text `(Field=Value,...)`, maps as `((Key,Value),(Key,Value))`, object references as
`"/Script/<Module>.<Class>'<package path>.<object>'"`, `None` for null, floats with six decimals.
For values not exposed to the clipboard, editor Python (`blueprints.md` § Editor Python) or an export
(`export_t3d.py`) reads them.

## Linux / Proton
- `socket_paste.py` runs with the host's Python 3 directly on the kit's `.uasset` files; no Wine needed.
