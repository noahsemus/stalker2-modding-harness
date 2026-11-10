# cfg DSL and quest-graph reference

Loader semantics, inheritance and quest-node behaviour that `config-files.md` does not cover. Read that first (patch
syntax, placement, per-field last-wins). Vanilla data: `<kit>\Stalker2\Content\GameLite\GameData\`.
Before any binary digging on "the game ignores my cfg", diff the mod's cfg against vanilla cfgs of the same kind
(which fields vanilla always sets, which values vanilla never uses). Most such bugs show up there in one step
(e.g. dialog lines with empty `AKEventName` / `AKEventSubPath`, which no vanilla phrase has, played no voice).

## How the loader applies patches (retail exe static RE, 2026-10-21; log strings sit below default verbosity)
- On loading `X.cfg` the game strips the extension, appends `/` and applies **every `.cfg` in folder `X/`** as a
  patch to `X.cfg`. The `_patch_` part of the name is a convention; any file name works. Vanilla relies on this:
  every file in `ObjPrototypes/` (`QuestObjPrototypes.cfg`, `GeneralNPCObjPrototypes.cfg`, the mutant files) is a
  patch merged into `ObjPrototypes.cfg`. A third-party `ObjPrototypes/zz<Name>.cfg` patches the same tree.
- **Merge is per top-level key**, the name before `: struct.begin` (not the `SID` field):

| Patch node | Key absent in target | Key present |
|---|---|---|
| `Key : struct.begin` (plain) | added | **whole node replaced**: every field not restated is gone |
| `Key : struct.begin {bpatch}` | added | recursive field-by-field merge |
| `Key : removenode` | nothing | node deleted |

- Keys can differ from SIDs (vanilla `CorpusMedlak` has `SID = CorpMedlak`). Match the key.
- A plain (non-bpatch) replacement must re-inherit what it drops, e.g.
  `CorpusMedlak : struct.begin {refurl=@BaseGame/ObjPrototypes/QuestObjPrototypes.cfg;refkey=CorpusMedlak}` plus the
  changed fields. Whether a self-`refkey` resolves against the pre-replacement node is not verified.
- The same rule holds below the top level: a **plain struct inside a bpatch replaces that sub-struct whole**. Use
  it on purpose to swap a list (e.g. a lair rank block's `SpawnSettingsPerArchetypes`), and avoid it by accident.
- Order of several patch files in one folder: not verified (a sort follows the scan; third-party `zz` prefixes
  assume alphabetical).

## Inheritance (`refkey` / `refurl`)
- `refkey=<Key>` inherits from a struct in the **same file**. A new struct added by a patch counts as being in the
  patched file, so it can `refkey` any vanilla struct of that file without `refurl`.
- `refurl` only for another file. A **relative `refurl` in a patch resolves against the patched file**, not the
  patch file's own folder: from `ItemPrototypes/DetectorPrototypes/DetectorPrototypes_patch_<Mod>.cfg`,
  `{refurl=../ItemPrototypes.cfg}` reaches `GameData/ItemPrototypes.cfg` (copy vanilla's value verbatim; no extra
  `../`) (verified in game 2026-10).
- **Cross-mount `refurl` needs `@Mount/`.** Config trees are mounted by name: `BaseGame` (`GameLite/GameData`),
  `GameSettings`, and one per mod named after the `ConfigPathName` in its GameFeatureData (the mod's name). A relative
  `refurl` resolves only inside its own mount, so from `GameLite/ModGameData/<Mod>/EffectPrototypes/X.cfg`,
  `{refurl=../EffectPrototypes.cfg}` reaches nothing. No warning; the cook then fails with
  `FParserNode.EnsureNoEntryChildNotExist ... has missing child for Key '<name>'` per unfilled key. Use
  `{refurl=@BaseGame/ItemPrototypes/ConsumablePrototypes.cfg;refkey=TemplateConsumable}`; `@<ModName>/...` addresses
  a mod's ModGameData tree. Patches under `GameLite/GameData/` are already in `BaseGame`, so relative paths work
  there. (Observed in the cook 2026-10; this narrows the `refurl=../EffectPrototypes.cfg` example in
  `config-files.md` to files inside the same mount.)
- **Nested structs inherit too**, from a root struct or a sub-struct by dotted path:
  `Bandits : struct.begin {refkey=Bandits_X.Preset.PossibleInhabitantFactions.Bandits}`, then restate only what
  differs. Vanilla: `BoneDamageMap : struct.begin {refurl=../ref/refs.cfg; refkey=FleshBoneDamageMap}`
  (`ObjPrototypes/BoggyFlesh.cfg`). Keep path segments to named keys (no `[0]`). Whether a nested `refkey` inside a
  bpatch struct resolves (and to the patched or the vanilla donor) is not verified.
- Nested structs merge through `refkey`: a child restating only `VitalParams.MaxHP` keeps the parent's other
  vital params (vanilla zombies do this).
- `bpatch` only touches existing data, so a `refurl` on a bpatch struct does nothing.
- Prefer inheritance over copies: a new struct `refkey`s the closest vanilla one and restates only changed fields
  (an ability variant restates only the changed `TriggeredCooldowns[n]`, not the list). Full copies are needed
  only when the new struct must drop inherited list entries. Copies bloat cfgs fast (one mod's lair file went
  92 MB → 4.7 MB by switching copies to bpatch + refkey, 2026-11-01).
- `{bskipref}` appears to mark a struct or value that skips the inherited content (meaning inferred; vanilla
  `PreinstalledUpgrades { [0] = empty {bskipref} }` in `WeaponPrototypes.cfg`; 42 vanilla files use it). Keep it
  when re-emitting such a list.

## Arrays
- `[*]` entries are numbered `[0]`, `[1]`, `[2]`... in file order and can be addressed by those indices.
- Add to a vanilla `[*]` list: bpatch the list with the **next free index**. A `[*]` inside a bpatch appends
  again on every apply.
- Change one entry of an inherited list: restate only that index.
- **`PreinstalledAttachmentsItemPrototypeSIDs`: never bpatch a single entry.** A partial bpatch replaced the whole
  list in game and stripped weapons' hidden built-in magazines and silencers (verified in game 2026-10-22).
  Re-emit the full list without bpatch, keeping vanilla's `bskipref` entry.
- Some lists are parallel arrays indexed together (consumable `EffectPrototypeSIDs` / `EffectsDisplayTypes` /
  `ShouldShowEffects`): keep their indices aligned.

## DLC data
- DLC cfgs (`DLC1`, `Deluxe`, `Ultimate`, `PreOrder`) are not in the kit's GameLite tree; extract them from the
  game paks (`Stalker2/Content/GameLite/DLCGameData/<DLC>/`).
- DLC trees are flat: one `ItemPrototypes.cfg` per DLC holds every item type. DLC items point back at the vanilla
  file through `refurl` (or inherit it by `refkey` from a DLC-local template), which is how to tell a DLC weapon
  from a DLC armor. A change to a whole prototype family (weapons, armors, attachments, consumables) needs the
  matching DLC patch too, or DLC variants behave differently.
- Retail DLC paks (game 2.1, plain unencrypted `.pak`, `UnrealPak <pak> -List` / `-Extract <dir>` work; entries are
  `.cfg.bin`, read with any strings dump): `pakchunk101` PreOrder, `pakchunk102` Deluxe, `pakchunk104` Ultimate.
- The pre-order backpack (`PreOrder/BackpackPrototypes.cfg`, `Backpack_PreOrder`) is the default backpack's mesh
  `SK_bpa_pla_01` with `MaterialPath = MI_bpa_sta_09_a_02_fov` (default: the mesh's own `MI_bpa_sta_09_a_01_fov`;
  both are base-game assets). A mod reproducing the player's backpack must copy the materials, not only the mesh.
  To test without owning the DLC, a dev pak can bpatch `Backpack_Default` / `Default` with that `MaterialPath`.

## SIDs and keys
- Two mods defining the same root SID: the result depends on load order. Only the owner defines a prototype;
  others bpatch it.
- A condition or node naming a SID that does not exist (an item from an absent mod) **nulls the whole node**,
  taking every other condition in it along. Isolate optional-SID checks in their own node.
- A quest node started by SID from the console (`XStartQuestNodeBySID <SID>`) can sit in any quest and needs no
  quest prefix in its SID.

## Spawn actors on existing saves (`SpawnActorPrototypes/`)
- Spawned actors are not rewritten from a patched prototype on their own. Add a bpatch child
  `NodePrototypeAppliedMods { <ModName> { NodePrototypeModVersion = N } }` to the patched `SpawnActorPrototype`; on
  load the game then deletes the spawned actor and respawns it from the patched data. Bump `N` whenever the patch
  changes. Details in `gameplay-data.md` § Placed actors.
- Never reuse a spawn actor GUID that already spawned something: a named NPC kept returning as the old generic
  actor from a reused GUID (verified in game 2026-10-25).

## Effects and their display
- Consumable buff HUD (number vs bar) is set **on the consumable item**, in `ItemPrototypes/ConsumablePrototypes.cfg`
  (and `QuestItemPrototypes.cfg` for quest consumables): `EffectsDisplayTypes`, parallel to `EffectPrototypeSIDs`.
  `EEffectDisplayType::EffectLevel` = Weak/Strong/Max bar; `EEffectDisplayType::ValueAndTime` = value + duration.
  `ShouldShowEffects` (bool per entry) hides an effect. `ShowUpgradeEffect` / `ShowUpgradeEffectValue` in
  `EffectPrototypes.cfg` only drive the upgrade screen.
- A permanent flag: `Type = EEffectType::FlagEffect`, `bIsPermanent = true`. Base `[0]` has
  `DuplicationType = KeepAll`, which stacks a copy per apply; set `EDuplicateResolveType::KeepOld` for anything
  applied repeatedly.
- Quests can test whether an effect is present (`EQuestConditionType::Effect`), never its magnitude.
- Console: `XApplyEffectOnPlayer <EffectPrototypeSID>`.

## Quest graphs: nodes and launchers
- `Launchers` is a list of groups; each `[n]` is one way to start the node (any one group is enough). A group's
  `Connections` list `{SID, Name}` pairs; `Name` names the source's output when it has several (a `SetDialog`
  ending = its last phrase SID) and is empty for plain sources. A walk-in gate is one group holding
  `[event, condition-pin]` (vanilla SQ18 pins).
- A launcher group with `Excluding = true` undoes the node; vanilla E02_SQ01 removes a `SetQuestGiver` marker this
  way.
- **Disable a node**: empty its `Launchers`. Switching `NodeType` to `Technical` does not: a Technical node still
  executes and downstream nodes still react. Reroute anything launched from it to its upstream trigger.
- **Never `LaunchOnQuestStart = true` on an `If` node**: no vanilla If does it, and it crashed the game on load.
  Start guards from a real start node.
- A `LaunchOnQuestStart` node added to a quest that already started never launches on that save (all vanilla
  `BridgeEvent` nodes are LaunchOnQuestStart).
- `Repeatable` nodes fire again on every quest update (~200 ms) while their launcher counts as done, even after the
  quest's End. Vanilla has no Repeatable `ConsoleCommand` outside launcher-less debug nodes. Put repeating work in a
  quest that ends with a vanilla `End` node and is reset each time it should run.
- `End` with `ExcludeAllNodesInContainer = true` excludes every node of the quest, and an excluded `Spawn` node
  despawns what it spawned (every `SpawnNodeExcludeType`). A quest that spawns a reward (stash, body) must not End
  afterwards; vanilla stash quests (EQ155_P) have none.
- Never chain off a `Spawn` node's output: a node launched by `SpawnHook` did not run on a save that did spawn the
  NPC. Launch follow-ups from the spawn's own launchers plus a `StartDelay`, gated on `IsCreated`.
- `OnTickEvent` runs every frame; use `Technical` nodes with `StartDelay` for polling.
- `SaveGame` node with only launchers = checkpoint save (vanilla `EQ50_SaveGame_StartEQ`).
- Ending quests: `XEndQuestBySID` from a `ConsoleCommand` inside the quest did not end it; vanilla `End` does.
  `XResetQuestBySID` alone restarts a quest (adding `XStartQuestBySID` started it twice).
- `ItemRemove` on an item the player lacks does not fail the chain.
- Rank: `SetCharacterParam` with `Params [0] { ModifiedCharacterParam = EModifiedCharacterParam::Rank,
  ChangeValueMode = EChangeValueMode::Set, Rank = ERank::Experienced }` (vanilla `E05_MQ02`).
- Relationships: `ChangeRelationships` with `UsePreset = true`, `RelationshipValue` 0 = enemies, 2 = neutral,
  3 = friends, player in `FirstTargetSID` (verified in game 2026-10). `EDialogAction::Attack` on a dialog line does
  not make a neutral NPC hostile; add `ChangeRelationships` (value 0) and `ResetAI`.

## Conditions
- `Conditions` holds groups `[0]`, `[1]`... joined by `ConditionCheckType = EConditionCheckType::And`. Put **one
  condition per group**: two conditions in one group behaved as "either" (vanilla
  `SQ18_SetDialog_SQ18_Comment_Gnutyj_Sum_Coming_Pin_2` shows the layout; verified in game 2026-10).
- An `If` on a **global variable that does not exist** fires True whatever it compares.
- `IsCreated` (`ConditionComparance = Equal`, `TargetPlaceholder = <GUID>`) tells whether an NPC exists. Bridge
  conditions on vanilla hub nodes (`OnNPCCreateEvent`, `Phase2`, `Technical_*`) read False on a save long past them;
  vanilla never reads those nodes' state. Bridges on your own quest's nodes work.
- `DistanceToPoint` (`TargetPoint` X/Y/Z, `NumericValue` in cm) is vanilla's usual distance check and does not
  depend on the NPC being loaded.
- `IsLairOwnedByFaction` (`TargetLairPlaceholder = <lair spawn-actor GUID>`, `Faction`) works outside the DLC1 war.
- Player GUID in `TargetCharacter` / `TargetQuestGuid`: `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`.

## Mod quests on existing saves (verified in game 2026-10-25)
- A rootgraph `XStartQuestBySID` launcher did not start a mod quest on a save from before install. On every world
  load, check `If` + Bridge on `<Quest>_Start` and on False run `ConsoleCommand XStartQuestBySID <Quest>`. Progress
  made while the quest was not running is never recorded.
- World load is too early: a chain started at load did nothing, the same chain a minute later worked. Use
  `Technical` `StartDelay = 5`, retry every 5 s while `IsCreated` is False, once more at 30 s.
- Start a node of another quest at the right moment with `ConsoleCommand XStartQuestNodeBySID <SID>`; a parallel
  `SetTimer` of the same length raced the original.
- Debug a broken chain: start each node in turn with `XStartQuestNodeBySID` and ask one yes/no question per step.
  `ShowFadeScreen` message streams go by too fast to read.

## Dialogs
- Adding a topic to a hub NPC: use `OverrideDialogTopic = EOverrideDialogTopic::None` (`Info` is the NPC's single
  info slot; the hub refills it). Put the `SetDialog` nodes into the **hub quest** itself (`QuestSID = <Hub>`, e.g.
  `RookieVillage_Hub`), launched by the nodes that attach the NPC's vanilla topics: a hub re-attaches its NPCs'
  topics per story phase. Hear the result back with `OnInfotopicFinishEvent` (`EventType = OnDialogFinished`,
  `InfotopicLastPhrases` = last phrase SID; vanilla E16_MQ02). (Verified in game 2026-10-08.)
- Quest-giver marker: `EQuestNodeType::SetQuestGiver` (`TargetQuestGuid` = NPC, `MainQuest = false`).
- Launch from a `SetDialog` ending by `Name = <last phrase SID>` plus `Interrupt`. `OutputPinNames` (`End`,
  `End_1`...) are labels only; launchers on them never fire.
- `NextDialogOptions [0] { NextDialogSID = , Terminate = true }` on the last line closes the dialog; with
  `Terminate = false` it stays open until Esc. A line has no on-screen time of its own (split long lines).
- Forced dialog (`StartForcedDialog = true`, `OverrideDialogTopic = Forced`) starts at once at any distance.
- Comment (spoken, no window): chain `DialogOnTheGo = true`, `IsPCDialogMember = false`; phrases
  `Unskippable = true`, `MainReply = false`; `SetDialog` `IsComment = true` (vanilla
  `SQ18_Comment_Gnutyj_Sum_Coming`; not verified for a mod-added chain).
- Branch on a global variable with a dialog `If` (`DialogMemberIndex = -1`, `NextDialogOptions { True {...}
  False {...} }`, vanilla `RSQ05_Dialog_Sich_C11_Finish_If_1`). GlobalVariable conditions on reply options showed
  every variant.
- `EDialogAction::GetItem` (`DialogActionParam` item SID, `ItemsCount`) gives the player an item.
- Named NPC: an `NPCPrototypes.cfg` entry (refkey a generic one) with `NameTextKey`, an ObjPrototype with
  `NPCPrototypeSID = <X>`, and `<X>` as dialog member. `SetAIBehavior` stay with `GoalPriority = HigherThanCombat`
  keeps an NPC from fighting back; `HigherThanALife` holds it in place but combat wins.

## Performance and save limits (verified in game / profiled 2026-10-24 to 10-31)
- A running quest costs game-thread time per node: one always-on quest of ~14,000 nodes, and a 4,100-node quest
  left running, each dropped the game to a few fps. Bulk work belongs in on-demand quests that End.
- Each `XResetQuestBySID` costs ~10 ms of game thread (it walks the UObject array under a lock); never per item or
  in a loop. Ending quests from the console while their `ConsoleCommand` nodes were mid-flight crashed the game.
- **Saves store quest-node names in a table with 16-bit count and indices.** Past 65,535 names the save is written
  truncated and crashes on load (or at boot). A late vanilla playthrough already holds 46-50k, leaving all mods
  together roughly 15k. No N × M node fan-out.

## Linux / Proton
- A Zone Kit installed on Linux (run through Proton) keeps the same layout: the vanilla cfgs are plain text under
  `<kit>/Stalker2/Content/GameLite/GameData/`, so grep / diff them natively with no Wine step (observed on a Proton
  dev box, 2026-10). DLC cfgs are not in the kit; they sit in the game paks under
  `Stalker2/Content/GameLite/DLCGameData/<DLC>/` on either OS.
