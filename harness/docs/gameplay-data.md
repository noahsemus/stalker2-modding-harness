# Vanilla gameplay data systems

How the main data-driven systems fit together, by cfg. Paths are relative to
`<kit>\Stalker2\Content\GameLite\GameData\`. DSL and quest-node rules: `cfg-reference.md`; patching: `config-files.md`.
Unless marked otherwise, facts come from reading vanilla cfgs (kit data, 2026-10).

## Armor and helmets
`ItemPrototypes/ArmorPrototypes.cfg` (body armor and helmets in one file).
- Templates: `TemplateArmor` (body: `ItemSlotType = EInventoryEquipmentSlot::Body`, grid 2x3, `ArtifactSlots = 2`)
  and `TemplateHelmet` (refkey of TemplateArmor: `Head`, grid 2x2, `ArtifactSlots = 0`,
  `PhysicsInteractionPrototypeSID = Helmet`). New armor: refkey the template or a similar armor, restate only changes.
- `Protection` (player) and `ProtectionNPC` (NPC wearers, usually higher) per damage type: `Strike`, `Radiation`,
  `Burn`, `Shock`, `ChemicalBurn`, `PSY`, `Fall`.
- `bBlockHead`: armor occupies the head slot (heavy, scientific, exoskeleton and many NPC suits).
  `bPreventFromLimping = true` only on the exoskeleton family, which also carries `EffectPrototypeSIDs` (e.g.
  sprint block, see `game-facts.md`). `IncreaseSpeedCoef` / `NoiseCoef` are set only in the template.
- `VoiceModulatorSID = Gasmask` muffles the wearer's voice (e.g. `Heavy2_Military_Armor`, `Heavy_Varta_Helmet`).
- `Invisible = true` hides NPC-only suits (most `NPC_*` armors) from player-facing UI.
- `MeshPrototypeSID` → `MeshPrototypes.cfg` is the dropped / inventory static mesh only. What an NPC wears visually
  comes from `NpcMeshGenerator` and the body-mesh system (next section).
- Upgrades: `UpgradePrototypeSIDs` plus `SectionSettings`, 5 entries keyed by `EUpgradeTargetPartType`
  (`Barrel`, `Handguard`, `Body`, `PistolGrip`, `Stock`), each with `SectionIsEnabled` and UI layout. An upgrade on
  a section that is not enabled cannot be reached in game. `PreinstalledUpgrades` is used once in vanilla
  (`Anomaly_Scientific_Armor_PSY_preinstalled`).
- `ArmorSoundType` appears both as `AkSwitchValue'...'` and `/Script/AkAudio.AkSwitchValue'...'`; same value.

## NPC appearance (worn armor and helmet meshes)
Data-only, no equip callback. Chain:

| cfg | Role |
|---|---|
| `ObjPrototypes/GeneralNPCObjPrototypes.cfg` (+ faction files) | `MeshGeneratorPrototypeSID` per NPC template |
| `MeshGeneratorPrototypes.cfg` | `*_MeshGenerator`: named slots (`BodyArmor`, `Face`, `Head`, `Mas`, `Bpa`, `Hea`...) with weighted `BodyMeshSID` lists |
| `BodyMeshPrototypes/AttachMeshPrototypes.cfg` | each `BodyMeshSID`: `MeshPath`, `BodyMeshType`, `AdditionalMesh`, material variations, optional `ItemPrototypeSID` |
| `ItemPrototypes/ArmorPrototypes.cfg` | item → `MeshPrototypeSID` |
| `MeshPrototypes.cfg` | dropped / inventory static mesh |

- The generator rolls one compatible combination across slots. `BlockingSlots` and `BlockingBodyMeshes` on a
  candidate rule out other slots / meshes once it wins (a mask face blocks `Head`, `Hea`, `Bpa`, `Fbe`; plain
  faces list the mask variants they exclude).
- **`ItemPrototypeSID` on an attach mesh gates it**: the entry is eligible only while the NPC has that item
  equipped (e.g. several `Fac_*_mas_*` faces with `ItemPrototypeSID = Light_Duty_Helmet`, one per body / backpack
  combination). It applies to loadout and picked-up items alike.
- A new helmet that should show on NPCs needs: the armor item, a `MeshPrototypes` entry, one or more attach meshes
  with `ItemPrototypeSID = <item>` and `BodyMeshType = EBodyMeshType::Head`, and those meshes added to the relevant
  generators' slots with blocking rules. Without an attach mesh it equips fine and shows nothing.

## Item generators (loot, loadouts, traders)
`ItemGeneratorPrototypes/DynamicItemGenerator.cfg` (general), `QuestItemGeneratorPrototypes.cfg` (quest / NPC),
`ItemGeneratorPrototypes.cfg` (base, `EmptyQuest`), `QuestStashBodyItemGeneratorPrototypes/`,
`QuestNPCGeneratorPrototypes/`.
- A generator: `SID`, `ItemGenerator` (list of category entries; indexed, `[*]` or named), optional
  `MoneyGenerator`, `RefreshTime`, `SpecificRewardSound`.
- Entry: `Category = EItemGenerationCategory::*` (`WeaponPrimary`, `WeaponPistol`, `WeaponSecondary`, `BodyArmor`,
  `Head`, `Consumable`, `Ammo`, `Attach`, `Artifact`, `Detector`, `NightVision`, `Junk`, `SubItemGenerator`,
  `None`), `PlayerRank` and `Diff` gates (one value or comma list; absent = all), trader-only
  `ReputationThreshold`, `RefreshTime` (e.g. `1h`), `bAllowSameCategoryGeneration`, and `PossibleItems`.
- `PossibleItems` entry: `ItemPrototypeSID` (or `ItemGeneratorPrototypeSID` under `SubItemGenerator`, composing
  generators), `Weight` (relative priority among entries, loadouts), `Chance` (independent roll, `1` = always,
  consumables), `MinCount`/`MaxCount`, `MinDurability`/`MaxDurability`, `AmmoMinCount`/`AmmoMaxCount` (vanilla also
  has 3 typos `AmmoMaxcount`), `bRequireAmmo`, `bRequireWeapon`, `bUnloadedWeapon`, `Attaches`, `Upgrades`.
- **`PlayerRank` is the player's rank**, not the wearer's: an NPC generator hands out gear by the player's
  progress.
- Name families: `GeneralNPC_*`, `GuardNPC_*`, `GeneralZombie_*` (NPC loadouts), `Trader_*`, `Bartender_*`,
  `Medic_*`, `Technician_*` and per-location vendors. Medic stocks are `Medic_<Location>_Consumables_ItemGenerator`.
- Quest generators usually `refurl` / `refkey` a dynamic one and override categories; resolve the base first.
  Quest nodes reference them through `QuestItemGeneratorSID`.
- Add an item to a trader: bpatch the generator → `ItemGenerator` → the right `[n]` → `PossibleItems`, adding a
  named entry (`ItemPrototypeSID`, `Chance`, `MinCount`, `MaxCount`).

## Ranks
Values `ERank::Newbie`, `Experienced`, `Veteran`, `Master` (`ERank::GetCount` as sentinel in scenarios).
- Set by quest nodes `EQuestNodeType::SetCharacterParam` with `EModifiedCharacterParam::Rank` across the main
  quests (E03_MQ01, E05_MQ02, E07_MQ05, E12_MQ01, E16_MQ01, ...), and by the console `XSwitchPlayerRank Veteran`
  (debug OnGameLaunch scripts, a few boss-fight `ConsoleCommand` nodes).
- Gated by the player's rank:
  - A-Life: region rank bounds (`AIGlobals.cfg`), scenario limits and minimum rank
    (`ALifePrototypes/ALifeDirectorScenarioPrototypes.cfg`), `MutantCorpseProcessFactionPerRank`.
  - Lairs: `SpawnSettingsPerPlayerRanks` in `LairPrototypes.cfg` / `LairPrototypes/GenericLairPrototypes.cfg`;
    spawn actors' `MinSpawnRank` / `MaxSpawnRank`.
  - Loot: generator `PlayerRank`, `Gamepass_ItemGenerators.cfg`, `PackOfItemsGroupPrototypes.cfg`,
    `StashPrototypes.cfg` (`SmartLootParams`), `CorpseClueStashPrototypes.cfg`.
  - Artifacts: per-rank attempts and rarity luck in `CoreVariables.cfg`.
  - Trade: per-rank buy/sell modifiers in `TradePrototypes.cfg` through `EBoolProviderType::PlayerRank` providers
    (`BoolProviderPrototypes/`).
  - Dialogs: `EQuestConditionType::Rank`; contextual actions: minimum rank on `ContextualActionNodePrototypes/`.
  - Zombie allowed weapons (`ObjPrototypes.cfg`).
- A rank change regenerates items near the player (`CoreVariables.cfg` `RegenerateItemsOnRankUpdateRadius = 40000`,
  `RegenerateItemsOnRankUpdateTimer = 10`).
- NPC rank: `Rank` on quest NPC prototypes (`ObjPrototypes/QuestObjPrototypes.cfg`) or per spawn actor.

## Faction relations
`RelationPrototypes.cfg`: relation bands, minimum relation to trade, rollback / cooldowns, deltas per event
(damage, kill, heal, wounded) for characters and factions, faction hierarchy (e.g. `Duty` under `Army`, `Freedom`
under `FreeStalkers`), special factions (`ArenaEnemy`, `ArenaFriend`, bosses), and initial relations.
- Player baselines: `Mutant`, `Bandits`, `Monolith`, `Militaries`, `Mercenaries` -800; `Duty`, `Freedom`, `Varta`,
  `Neutrals`, `Spark`, `Scientists`, `Corpus`, `Noon` 0; `ArenaFriend` 800.
- Quests change relations with `ChangeRelationships` (1830 vanilla nodes; most `UsePreset = true` with small values,
  see `cfg-reference.md` for the verified preset meanings; 115 use direct deltas, many targeting NPC GUIDs).

## Weapon and armor upgrade trees
`UpgradePrototypes.cfg` (cells, prerequisites, blocking, lines), `WeaponData/WeaponGeneralSetupPrototypes.cfg`
(fire modes, per-weapon `UpgradePrototypeSIDs`), `NPCPrototypes.cfg` (technician offers and `Enabled` states),
`QuestNodePrototypes/Kazkovy_Hub.cfg` (toolbox unlocks), `EffectPrototypes.cfg` (fire-mode replacement effects).
- `HorizontalPosition` is zero-based (0/1/2 = tiers 1/2/3); `UpgradeTargetPart` picks the part's tree;
  `VerticalPosition` the top or bottom cell. Check the cell against the weapon's own `UpgradePrototypeSIDs`
  (ignore `IsModification` entries, shown separately).
- `RequiredUpgradePrototypeSIDs` listing both mutually exclusive previous-tier upgrades means "either one".
- Vanilla top cells connect down (`ConnectionLines = [EConnectionLineState::Down]`), bottom cells up (`Top`); the
  template default is `None`.
- An upgrade targeting a part the weapon has no non-modification branch for most likely does not display (seen on
  a `Body` fire-mode upgrade for the SVU; config analysis 2026-10-07, not checked in game).

## Lairs (A-Life spawn points)
`SpawnActorPrototypes/WorldMap_WP/<GUID>.cfg` (one lair per file, `SpawnType = ESpawnType::LairSpawner`),
`LairPrototypes.cfg` + `LairPrototypes/GenericLairPrototypes.cfg`, `ObjPrototypes/*` (archetypes),
`ALifePrototypes/ALifePopulationManagerFactionPrototypes.cfg`, `NPCNeedsPresetPrototypes.cfg`.
- **Spawn actor** (key and `SID` = GUID): position, `LairPrototypeSID`, `LairType` (`ALifeLair`, `RestingLair`...),
  `InitialInhabitantFaction`, `CanBeCaptured` / `CanAttack` / `CanDefend`, `ActiveLair`, `SpawnOnStart`,
  `MinSpawnRank` / `MaxSpawnRank` (player-rank band the lair exists in), volume GUIDs (`LairCoreVolumes`,
  `LairTerritoryVolumes`, `NavModifierVolumes`), `RestrictionRadius`. 381 lairs on the world map; most other
  world-map entries beside them are their trigger volumes. DLC1 has 64 more in `DLCGameData/DLC1/`.
- **Lair prototype**: `Preset.PossibleInhabitantFactions.<Faction>` (`Faction`, `FactionPriority`), each with
  `SpawnSettingsPerPlayerRanks.Newbie..Master` (`MaxSpawnQuantity`, `InitialSpawnQuantityPercent`, respawn
  timers, `WipeRespawnTimeoutSeconds`) and `SpawnSettingsPerArchetypes.<ObjPrototype key>`
  (`MinQuantityPerArchetype`, `SpawnWeight`). No inheritance between vanilla lair prototypes.
- The game picks the block for the **player's** rank. Squads already spawned keep their makeup until they die.
- A placed lair spawns only its `InitialInhabitantFaction`'s list even when the prototype allows several; give a
  single lair a different pool through its own prototype (refkey the vanilla one, restate the faction block).
- `SpawnWeight = 0` archetypes never spawn (e.g. some Heavy variants at every rank).
- Quest control: `ToggleLairActivity` (`Activate`, `ForceDespawn`) is the only lair node vanilla uses
  (484 nodes, 230 lairs); `SpawnLair` appears once. Condition `IsLairOwnedByFaction` exists; no lair events.
- NPC speed: `MovementParams` Walk/Run/Sprint (and `MovementSpeedCoef`) only changed off-screen movement; on-screen
  speed follows the locomotion animation (verified in game 2026-10-23). A `VelocityChange` effect (vanilla
  `ZombificationVelocityChange`) works but takes hold only when movement is recalculated, and cfgs cannot put a
  permanent effect on a spawned NPC.
- Mutant difficulty knobs: `MutantAttackParams.<Attack>.Cooldown` on the ObjPrototype, and per-mutant
  `AbilityPrototypes/<Mutant>Abilities.cfg` abilities (`AbilityType` Attack, Charge, LongJump, PSYStrike, Throw,
  Summon, Shield...) with `TriggeredCooldowns[*].Duration`, `MinCooldown`/`MaxCooldown`, `CooldownMin`/`CooldownMax`.
  An ObjPrototype points at abilities through `Abilities.<key>.SID`.

### Lair ownership and A-Life expansion (retail exe static RE 2026-08/10-29, plus play observation)
- Ownership lives on the lair (faction + index into its prototype's `PossibleInhabitantFactions`). It changes only
  when a squad finishes a capture step: the generic A-Life `AttachToLair` strategy (used by the Expansion need),
  `AttackLairGoal` (A-Life director `CaptureLairs` scenarios), or the faction-war squad capture. Only these fire
  `OnLairOwnershipHasChanged`; preset changes (`FWChangePreset`, `InitialInhabitantFaction`) change the owner
  silently. Nothing captures by presence alone.
- Hard gate: the new owner must be listed in the lair prototype's `PossibleInhabitantFactions` (checked twice).
  Vanilla lists only the lair's own faction in most prototypes. Also required: `CanBeCaptured`, the owner hostile
  to the attacker (most hostile band), no enemies within 50 m. Capture distances are cvars:
  `gsc.fw.Capture_DistSquadLair` 20 m, `gsc.fw.PlayerCapture_DistSquadLair` 25 m and
  `gsc.fw.PlayerCapture_DistPlayerLair` 15 m (player-assisted, allied player), `gsc.fw.NoEnemyToLairToCapture`
  50 m. Despite the `gsc.fw.` prefix they gate generic A-Life. No level, DataLayer or quest check.
- Expansion: a squad sets out when its NPCs' `AI.Need.Expansion` (`NPCNeedsPresetPrototypes.cfg` GoalNeeds) fills,
  resolved by `ExpansionResolverFactory`. Vanilla gives it to the generic human preset (and refkey children),
  zombies and `MutantGenericNeedsPreset`; `MutantGenericNeedsNoExpansionPreset` and `_Guard` presets lack it.
  Cvars `ALife.ExpandToRestingLairs` / `ALife.ReuniteToRestingLairs` default on; the resolver searches lairs within
  a compiled-in 700 m (the cfg `ALifeLairExpansionRadius = 500000` is a different value).
- Faction modes: each faction in `ALifePopulationManagerFactionPrototypes.cfg` `Default.Factions` has
  `Aggressive` / `Normal` / `Defensive` `MinLairs`/`MaxLairs` ranges (Bandits 1-5 / 6-20 / 21-900),
  `ALifeLairExpansionBattleChance`. A lair is an expansion target only while its owner is not `Aggressive`, so a
  faction down to a few lairs has them protected. Factions with no entry there (Scientists, NeutralMSOP,
  IkarVarta, ShevchenkoStalkers...) never expand and never own capturable lairs.
- In play, no capturable hostile lair changed hands in about an hour outside the faction war (2026-10-29): the
  non-war paths are rare.
- Faction war (`ESpawnType::FactionWar` spawn actors): `FactionsPresets.<preset>.FactionsParams` is a generic list
  (any number of factions, names resolve through the normal faction registry; an unknown name is dropped silently;
  the `FW_` prefix has no meaning in code). The war follows only the lairs named by its `Reinforcers`'
  `TargetLair`; it has no radius. Reinforcers (`OwningFaction`, `TargetLair`, `DefendersCount`, squad sizes) and
  UnitSpawners (`OwningFaction`, `Lair`, `SpawnedSquadSize`) are one per (faction, lair). The `FW_*` lair
  prototypes are unused. Not traced: the attack scheduler, and whether ownership persists in saves.

## Placed actors on existing saves (`SpawnActorPrototypes/`)
Source: ZoneKit support guide "How to Mod Placeholders" (Phase 2), summarized.
- Every placed placeholder (item, NPC, lair, trigger, stash...) has a SpawnActorPrototype cfg keyed by GUID.
  `SpawnOnStart = true` spawns it at game start or load (world items, loot, open-world NPCs); `false` waits for a
  quest or event.
- The editor writes these cfgs for you: patched vanilla placeholder → bpatch cfg in
  `<kit>\Stalker2\Mods\<Mod>\Content\GameLite\GameData\SpawnActorPrototypes\<level>\<GUID>.cfg`; deleted → `<GUID> : removenode`
  in the same place; new → a cfg under `.../ModGameData/SpawnActorPrototypes/`. You can also write them by hand.
- Patched cfgs carry `NodePrototypeAppliedMods { <Mod> { NodePrototypeModVersion = N } }`, which is stored in the
  save. On load, an already spawned actor whose prototype changed (mod applied, version different) is deleted and
  then respawned from the new data (`SpawnOnStart`) or spawned when needed. Bump `N` to force a refresh.
- `PackOfItems` placeholders need a new game to change.

## Detecting another installed mod
Pattern: the **provider** puts a flag effect on the player at every world load; the **consumer** checks it with a
quest `If`. (Verified in game 2026-10.)
1. Provider defines a root effect `<Mod>Installed` (patch to `EffectPrototypes.cfg`, `{refkey=[0]}`, modelled on
   vanilla `FaustPsyResist`): `Type = EEffectType::FlagEffect`, `bIsPermanent = true`,
   `DuplicationType = EDuplicateResolveType::KeepOld` (the default `KeepAll` stacks a copy per load),
   `ShowUpgradeEffect = false`.
2. Provider applies it from a `ModWorldSubsystem` Blueprint (`runtime-host.md`): `OnWorldBeginPlay` → skip
   `MainMenuMap` (do not gate on `WorldMap_WP`: saves can load into logic levels) → `Delay 1.0` → loop until
   `GetPlayerCharacter(0)` is valid → `Execute Console Command "XApplyEffectOnPlayer <Mod>Installed"`. The SID can
   be built from the Blueprint's own class path (`Get Class` → soft class reference → `To String` → `Get Path` →
   `Right Chop 1` gives `<Mod>`), so one Blueprint works in any mod. The same Blueprint can run a second console
   command per load (e.g. `XStartQuestNodeBySID <Mod>_OnWorldLoad`).
3. The subsystem only runs when listed in a `*_WorldSubsystemData` asset (the editor's Package Mod writes it).
   `ModAssetSupportSubsystem` finds mod data assets in any folder by file-name suffix: `_LocalizationDatabase`,
   `_ActorReplacementData`, `_ActorDeletionsData`, `_ActorPatchesData`, `_WorldSubsystemData`.
4. Consumer: `If` with `ConditionType = EQuestConditionType::Effect`, `ConditionComparance = Equal`,
   `TargetCharacter = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`, `EffectPrototypeSID = <Mod>Installed`,
   `RequiredSquadMembers = AllMembers` (vanilla `E08_MQ05_C02.cfg` checks `FaustPsyResist` this way). True =
   installed; False = absent (the effect SID then does not exist, which is fine here).
- Rules: one action per branch (swapping an item in a container while the player watched left a ghost item);
  provider-only SIDs only on the True branch, in their own node (a missing SID nulls the whole node); do not
  check right at load (the flag lands ≥ 0.5 s after begin play); only the provider defines the effect; never
  remove it; never use a global variable as the flag (`cfg-reference.md` § Conditions).

## Temporary effect icons via camera shake (community method)
Thanks to rbwadle and Zivaka for finding and explaining this. Working pattern, not fully verified.
- An effect of `Type = EEffectType::CameraShake` (`CameraShakePrototypeSID`, `ValueMin = ValueMax = 1`,
  `CameraShakeEffectSubtype = ECameraShakeEffectSubtype::AddEffect`) points at a `CameraShakePrototypes.cfg`
  entry (`Type = ECameraShakeType::Constant`, `Scale = 0`, its own `GroupSID`, `CameraShakePath` = a Blueprint).
- A quest `SetCharacterEffect` (target = player GUID) applies it; the Blueprint (parent `CS_OnShooting`,
  overriding `ReceivePlayShake`) gets a callback when the effect starts and forwards it to a widget or component
  that draws the icon.
- `Scale > 0` makes the player twitch; a dedicated `GroupSID` avoids clashes with other shakes.
- Open: whether effect removal gives a matching callback (hide the icon by separate logic until known), and the
  exact class chain under `CS_OnShooting`.

## Map markers (verified in game 2026-10-27/29, plus static RE)
- A `MarkerPrototype` (`MarkType = EMarkerType::Guide`, `WorldPosition`,
  `InitDiscoverState = EMarkerState::Explored`) plus an `ESpawnType::Marker` spawn actor shows an icon. Its
  `Title` is not displayed on a Guide marker; `EQuestNodeType::SetLocationName` (`Location`, `NewTitle`) labels it,
  repeatedly if needed.
- **The save keeps a marker once shown.** `ShowMarker` creates a record keyed by the marker SID, copying position,
  type and state once, and can only raise the state. `ShowMarker Discovered = false`, despawning its actor,
  `MarkType = None` or moving it all fail to hide or move it. `Despawn` removes a marker record only through the
  handle stored by its own quest's `Spawn` node. `XDiscoverMarker`, `XListMapMarkers`, `XRevealAllMarkers` are
  empty in shipping. So never `ShowMarker` a marker you may need to remove; spawning and despawning from one quest
  is the only candidate (untested).
