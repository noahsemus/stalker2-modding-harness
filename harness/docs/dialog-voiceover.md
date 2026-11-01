# Voiced mod dialogs: voice lines, lip-sync, dialog animation

Traced on vanilla data (GameLite cfgs, the kit's `*-WindowsModEditor.pak` files), the retail exe (build of
2026-09-29, game 2.0.x) and in-game tests of a voiced mod quest (2026-10-18 → 10-20), unless marked
*inferred*. Dialog text keys (`sid_phrase_` etc.) are in `localization.md`; player animation in `animation.md`.

## What a voiced phrase is made of
Everything hangs off the phrase's cfg `TextToolPhraseSID`. No cfg field points at audio.

| Piece | What | Where (vanilla) |
|---|---|---|
| Phrase cfg | `DialogPrototypes/<Chain>.cfg`: `SID`, `TextToolPhraseSID`, `DialogMemberIndex`, `HasVOInSequence` | GameLite cfgs |
| Chain cfg | `DialogChainPrototypes/<Chain>.cfg`: `StartingDialogPrototypeSID`, `DialogMembers[*]` (`DialogMemberName`, `IsPCDialogMember`) | GameLite cfgs |
| Wwise | one Sound Voice + one Event `VO_<speaker>_<PhraseSID>` (EN + UA sources) | kit Wwise project |
| `AkAudioEvent` | ~2 KB `.uasset`, `EventInfo { WwiseGuid, WwiseShortId, WwiseName }`, no audio | `/Game/_STALKER2/Audio/WwiseAudio/Events/Voiceover/<Type>/VO_<Quest>/<speaker>/VO_<speaker>_<PhraseSID>` |
| Voice runtime data | `DialogRuntimeData` `<ChainSID>_Voiceover` | `/Game/_Stalker_2/maps/_Stalker2_WorldMap/QuestObjects/Dialogs/<...>/` or `.../QuestObjects/DefaultRuntimeData/` |
| Face runtime data (optional) | `DialogRuntimeData` `<ChainSID>_FaceAnimation` | same folder |
| Face anim (optional) | `AnimSequence` `AS_FAC_<EN\|UA>_<speaker>_<PhraseSID>` on `SKEL_fac` | `/Game/_STALKER2/Animations/CharacterHead/<Type>/<Quest>/<speaker>/<EN\|UA>/` |

- Who speaks which chain: `NPCPrototypes.cfg` (`HelloDialogChain`, `VoiceUA`, `VoiceEN`) or a quest node
  `EQuestNodeType::SetDialog` with `DialogChainPrototypeSID`. Some hello chains (`..._CallPlayer`) have no chain or
  phrase cfg at all: the NPC prototype names the chain and the voice comes from runtime data alone.
- `<Type>` is a quest-type folder: ANC, Bossfights, Encounters, General, Hubs, MainQuests, RepeatableSideQuests,
  SideQuests.
- **Dead route**: the legacy phrase fields `AKEventName` / `AKEventSubPath` (relative to `.../Events/Voiceover/`),
  `AssetsSubPath`, `FaceAnimationAssetName`, `FaceAnimationSubPath` are still set on ~600 vanilla phrases, but
  pointing a mod phrase at an existing vanilla event this way plays nothing (tested 2026-10-18).
- Wwise picks the language: one event per phrase, one auto-defined bank per event per language
  (`GeneratedSoundBanks/Windows/Event/<Language>/<Event>.{bnk,json,xml,txt}`, media `Media/<Language>/<id>.wem`,
  loose, not streamed). Voice media also pulls shared SFX media of the voice-modulator effects (`VM_*` ShareSets,
  `RTPC_VM_Preset`). The cook bundles an event's banks + media into a `.ubulk` next to the event asset.

## DialogRuntimeData layout
`UDialogRuntimeData` has two properties: `AssetType` (FName: `Voiceover`, `FaceAnimation`, `VoiceGen`) and an
instanced `AssetContainer`.
- `_Voiceover`: `NameToAsset_AssetContainer`, `Assets: TMap<FName, FSoftObjectPath>`: phrase SID (no `sid_phrase_`
  prefix) → `<event path>.<event name>`.
- `_FaceAnimation`: `NameAndLocalizationToAsset_AssetContainer`: phrase SID → `None` → `{ELocalizationLanguage →
  SoftObjectPath}` to the `AS_FAC_*` anim. A line voiced in one language may point both languages at one anim.
- Nothing in the cfgs or the (editor-only, `PKG_EditorOnly`) Dialog Blueprint references these assets; the runtime
  data's name and folder do not matter at runtime either (next section).

## How the game finds a phrase's voice (retail exe, 2026-10-20)
1. **Discovery, once at boot.** Step 23 of `AInitLevelGameMode`'s init table: `UDialogAssetReferenceSubsystem`
   (instance `/QuestTool/BP_DialogAssetReferenceSubsystem_C`) calls `AssetRegistry->GetAssetsByClass(/Script/
   Stalker2.DialogRuntimeData)` and async-loads every hit (log text "Registering DialogRuntimeData: %s"). No label,
   path, DLC or GameFeatureData scan rule is involved: `UDialogAssetReferenceSettings.bUseSingeAssetLabel` /
   `QuestAssetLabelClass` (config `Quest`) have no reader in retail code, and overriding `QuestAssetLabel` /
   `PAK_Quest_BaseGame` does nothing.
2. **Merge.** Assets are grouped by `AssetType` into one global container each; every asset's entries are appended.
   Mod and vanilla entries share one map (25 384 vanilla `Voiceover` entries in the live game).
3. **Play.** Key = the phrase's `TextToolPhraseSID`, exactly. Lookup `Voiceover`, then `VoiceGen`; `FaceAnimation`
   uses the same key plus the language. A phrase with `ShowNextDialogOptionsAsAnswers = true` (an answer menu, always
   the player in vanilla) plays no voice.
4. Mod plugins are registered at init step 11 ("Registered mod plugin" / "Failed to load asset registry for mod
   plugin"): the plugin's `AssetRegistry.bin` (inside the NewContent `.pak`) is appended to the global registry.
   Exe RVAs of that build, for re-finding after a patch: init table `0x148eaa4e8` (16-byte entries), step 23 code
   `0x1410a8e4c`, load callback `0x140a97290`, mod registration `0x146c749aa`, play `0x140e00dc8`.

## What silently breaks it (all show subtitles, no voice)
- **Install folder.** Only mods under `<game>\Stalker2\Content\Paks\~mods\` (or Steam Workshop) take the step-11
  path. In any other folder under `Paks\`, cfgs, overrides and by-path loads work but class queries never see the
  mod's assets, so its runtime data is never loaded (2026-10-20: a mod in `Paks\notmods\` was silent; moved to
  `~mods` it played).
- **Unknown speaker.** Loading a `_Voiceover` / `_FaceAnimation` asset in the Zone Kit (editor and cook alike) drops
  every entry whose phrase's TextTool `Character` is `None` or not in the editor's character list. Verified by
  elimination: 19 entries in the file, 13 in the editor and in the cooked package; all `None` and custom-NPC entries
  gone. The player must be `PC` (`sid_character_PC`); NPCs need a vanilla character SID. The list is the
  `characters` array (`{ id, sid, name_sid }`) of the `TextDatabase_<part>.json` files in the kit's FullEditor pak
  (`Stalker2/Content/TextToolBackup/`). A mod cannot add a file there, so a brand-new NPC character stays silent
  (speak through a vanilla character SID). The code that drops them was not located.
- **A generator that writes only lines with a take** silences any line whose take was removed since the last run.
- Overriding `AKEventName` (above) does nothing.

## Making a voiced line
1. **Takes**: one WAV per line and language. Pad each with ~0.1 s of trailing silence before import: tightly trimmed
   takes make speaker changes sound rushed, dialog cfgs have no per-phrase delay (`PreblendTime` /
   `BlendExpForEaseInOut` are sequence camera blends), and a Wwise initial delay would put lip-sync out of step.
2. **Wwise**: one Sound Voice (EN + UA sources) + one Event `VO_<speaker>_<PhraseSID>` per phrase, banks for just
   those events, then **event assets** (`AkAudioEvent`, Wwise Browser → Reconcile, or a headless checkout). Full
   recipe, shared-`GeneratedSoundBanks` and licence traps: `audio-wwise.md` § Dialog voiceover.
3. Keep a copy of your events' `Event\...` / `Media\...` bank output in the mod repo: every mod's bank generation
   writes the same shared folder, and the cook bundles whatever is there.
4. **Face anims** (NPC lines only; the player has none): "Lip-sync" below.
5. **Runtime data**: `<ChainSID>_Voiceover` (+ `_FaceAnimation`). Editor route: the
   `EUW_GenerateDialogruntimeAssets` widget (`audio-wwise.md` step 6), which assumes an editor-authored Dialog
   Blueprint. Cfg-authored dialogs need the assets written another way (e.g. a vanilla `_Voiceover` package used as a
   binary template with its map rewritten; such a writer round-trips a vanilla template byte-identically). Entries are
   soft object paths `<package>.<asset>`.
6. Cook, install into `~mods`, check with "Debugging".
Adding lines to a mod that already has voice: run every step for the new lines only.

## Lip-sync (`tools/voice/`)
Vanilla face anims: `AnimSequence` on `SKEL_fac`, float curves + bone tracks, 60 fps (EN) or 30 fps (UA), no head or
body motion. The tools learn audio → face channels from one vanilla speaker's own lines and bake new anims from copies
of that speaker's anims. One fitted speaker's model can serve every NPC speaker in a mod.
1. **Pick a speaker**: a folder of their `AS_FAC_*` anims under `/Game/_STALKER2/Animations/CharacterHead/...` (e.g.
   `Hubs/<Hub>/<speaker>`) whose voice WAVs exist as `<kit>\O\Voices\<English(US)|Ukrainian(UA)>\S2_Live\
   VO_<speaker>_<key>.wav` under the same keys. More lines fit better.
2. **Dump** (editor, read-only): `dump_face_anim.py` (`VANILLA`, `OUT`).
3. **Fit** (shell): `<kit python> fit_lipsync.py <dump> <kit>\O\Voices <new_lines> <pred.json>`, where `<new_lines>`
   holds the padded takes as `en\VO_<speaker>_<PhraseSID>.wav` / `uk\...`. Ridge regression from 40-band log-mel frames
   (±6 frames context) to each face channel; channels with held-out correlation > 0.35 are driven by audio (printed),
   the rest come from a base anim (the shortest vanilla line at least as long). It overwrites `<pred.json>`; to extend
   a set, fit the new lines into a scratch file and merge its `anims`. Needs only numpy, which the kit's embedded
   Python ships (numpy 2.0.2 seen). The original was torch/torchaudio-based; this port computes the same features in
   numpy (smoke-tested on synthetic data, not yet re-verified in game).
4. **Bake** (editor, saves): `create_face_anims.py` (`PRED`, `VANILLA`, `DEST`) pasted in the Output Log; 10 anims per
   run (one run over everything stalled after ~20), paste again until `done; 0 left`. Copies are forced to 30 fps
   before resizing, or an EN (60 fps) base plays the line at double speed. The speaker name in `AS_FAC_<L>_<speaker>_
   <SID>` must have no `_` (the tools split on it).
5. Wire into `<ChainSID>_FaceAnimation`. Check in the anim viewer on the speaker's head, then in game.

## Animation during dialog
- **Face**: the `FaceAnimation` entry plays from the phrase start; carries no head/body motion.
- **Body gestures** come from `HumanDefaultAnimCollection`: a phrase's `DialogMembersAnimations[*].DialogAnimations`
  (explicit `EDialogAnimationType`), else a weighted random talking / listening pool. Both are keyed by the NPC's pose
  state, and only contextual-action states have entries (`RelaxStand` maps to `CAStand`, sitting states to their
  own). Armed and combat stances have none: an NPC whose `SetAIBehavior` uses `WeaponState Combat` (or `Relax` with a
  rifle) moves only its head. Give speaking NPCs `EWeaponState::NoWeapon`, as most vanilla Stay goals do. About a
  quarter of the `CAStand` talking pool is low-motion clips, so some lines look stiff regardless.
- **Interrupts**: the face anim is stopped only on the interrupt path of chains with `ContinueAfterInterrupt = true`.
  With `false` the voice stops and the mouth keeps moving to the anim's end (vanilla hub topics too, *inferred*).

## Debugging: subtitles but no voice
Walk the stages in order; the first one missing the key is the culprit.
1. **Source asset**: the runtime data's map holds as many entries as lines expected.
2. **Editor**: `probe_voiceover_keys.py PKG=/<Mod>/.../<ChainSID>_Voiceover`. Fewer keys than the file = the editor
   dropped them (unknown speaker). `RELOAD=1` tells a stale editor copy apart.
3. **Cooked**: extract the staged NewContent container (`UnrealPak <x>.utoc -Extract <dir>`) and count the
   `VO_<speaker>_` names in the runtime-data package (`tools/pak/zen_names.py`). The cook keeps only what the editor
   kept. Audio present at all: the event packages need their `.ubulk`.
4. **Mod registry**: the NewContent `.pak` holds `AssetRegistry.bin` + `.uplugin`; grep it for `DialogRuntimeData`
   and your asset names.
5. **Install folder**: `~mods` (above).
6. **Live game**: `python -I tools/voice/dialog_runtime_probe.py [key ...]` lists the merged maps with entry counts
   per package root and looks up keys, read-only. Addresses are for the 2026-09-29 exe; re-find them after a patch.
   In the registry but missing here: install folder.

## Tools (`harness/tools/voice/`)
| Tool | Runs | Does |
|---|---|---|
| `probe_voiceover_keys.py` | editor (`ue_exec.py` or paste) | keys the editor sees in one runtime-data asset; `RELOAD=1` reloads from disk |
| `dump_face_anim.py` | editor, read-only | a vanilla speaker's face anims → JSON |
| `fit_lipsync.py` | kit Python (numpy) | fit audio → face channels, predict tracks for new lines |
| `create_face_anims.py` | editor (paste), saves | bake + save the predicted `AS_FAC_*` anims |
| `dialog_runtime_probe.py` | any Python 3, game running | merged voice / face maps of the live game (read-only, build-specific) |

## Linux / Proton
- Install folder is the same inside the game folder: `<steam>/steamapps/common/<game folder>/Stalker2/Content/Paks/
  ~mods/`; the `~mods` rule applies unchanged.
- `dialog_runtime_probe.py` runs with the host's Python 3 against the Proton game process: it finds the process by
  the exe mapped in `/proc/<pid>/maps` (several Wine processes can match the name; only one maps the exe) and reads
  `/proc/<pid>/mem`, which needs `kernel.yama.ptrace_scope = 0` or root.
- `fit_lipsync.py` runs on any Linux Python 3 with numpy (the kit's Windows Python is not needed). The editor
  scripts were run under Proton by pasting the header line into the Output Log (Python mode), without remote
  execution; every path in that line is as the editor sees it (a Wine drive-letter path).
- Wwise under Proton (sandbox-visible paths, WwiseConsole output, WAAPI from the host): `audio-wwise.md` § Linux / Proton.
