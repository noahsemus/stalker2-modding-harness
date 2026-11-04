# Audio: Wwise projects, WAAPI, SoundBanks, shipping

Proven on a menu-music replacement, a radio-playlist mod and ~140 voiced dialog lines (2026-10).
The kit's Wwise event dumps (`GeneratedSoundBanks\Windows\Event\*.txt`) are in `zonekit.md`.

## Official flow (editor clicks)
GSC's "Zone Kit – Audio modding quick start guide" (Google Doc): Mod Editor toolbar **Audio Modding → Open Wwise
Project**, edit, generate SoundBanks (F7), then in the editor's **Wwise Browser** right-click → **Checkout** existing
AkAudioEvents you changed, or **Reconcile** new ones, then package/cook.
- **Regenerate banks whenever you switch mods**: every mod's project writes into one shared GeneratedSoundBanks folder.
- Open the Wwise Browser only after `Stalker2.log` shows "Successfully connected to Wwise Authoring". It once
  deadlocked the editor, and while open the editor drops to ~8 FPS: close it when done. "Not connected" there can just
  mean the mod and root project paths differ; it still reads the banks from disk.
- Wwise version must match the kit's integration: Wwise **2024.1.10.8979** (2026-10).

## Project layout
| What | Where |
|---|---|
| Per-mod project | `<kit>\Stalker2\Mods\<Mod>\S2_WwiseProject\S2_WwiseProject.wproj` (a full copy of the game's project, ~256 MB; not cooked) |
| Its template | `Stalker2/Plugins/ModKit/Templates/ModWwiseOverlay/S2_WwiseProject` inside `<kit>\Stalker2\Content\Paks\Wwise-WindowsModEditor.pak`. "Open Wwise Project" only copies it out. The same pak holds every vanilla `AkAudioEvent` .uasset and the vanilla GeneratedSoundBanks |
| Originals (source WAVs), shared by all mods | `<kit>\O\SFX\...` (`.wproj` `MiscSettings/Originals` = `..\..\..\..\O`); voice under `<kit>\O\Voices\<Language>\...`; vanilla radio music `O\SFX\S2_Live\` |
| SoundBank output (what the editor and cook read) | `<kit>\Stalker2\S2_WwiseProject\GeneratedSoundBanks\Windows`. Auto-defined bank per event (`Event\<EventName>.{bnk,json,xml,txt}`); streamed media loose as `Media\<id>.wem` (~50k files) |
| Event → UI sound map | `UIRemaster/UISounds/BaseGame_UISounds.uasset` (FullEditor pak) maps `EUISound` → event |

Without the editor: extract the template folder with `repak unpack -o <dir> -i Stalker2/Plugins/ModKit/Templates/ModWwiseOverlay
<pak>` (seconds) and copy it to `<kit>\Stalker2\Mods\<Mod>\S2_WwiseProject`.

## WAAPI (Wwise Authoring API) over HTTP
Wwise Authoring serves WAAPI by default (HTTP **8090**, WAMP/WebSocket 8080). No client library is needed: POST JSON to
`http://127.0.0.1:8090/waapi`. `tools/audio/waapi.py <uri> [args-json|@file] [--return id,name,path]` wraps it.
- Body is always `{"uri": ..., "args": {...}, "options": {...}}`. Errors come back as `{"uri":"ak.wwise.error...",
  "message":...}`; an empty `{}` is success for setters. Smoke test: `ak.wwise.core.getInfo`.
- `options.return` picks fields: `id`, `name`, `type`, `path`, `parent`, `parent.name`, `originalFilePath`, `duration`,
  `@<Property>` (e.g. `@Target` on event actions).
- **Edit through WAAPI, never by writing `.wwu` files while Wwise is open** (reload prompt, lost state). Finish with
  `ak.wwise.core.project.save`.
- **No GUI**: `WwiseConsole.exe waapi-server <wproj> --http-port 8090 --wamp-port 8080` serves the same API; stop it
  after `project.save`. `WwiseConsole.exe generate-soundbank <wproj> --platform Windows` builds banks (~1 min on a
  trimmed project).

### Recipes (args JSON)
| Goal | uri | args |
|---|---|---|
| Find containers by name | `ak.wwise.core.object.get` | `{"from":{"path":["\\Actor-Mixer Hierarchy"]},"transform":[{"select":["descendants"]},{"where":["name:matches","^Radio_"]}]}` |
| Event actions and targets | `ak.wwise.core.object.get` | `{"from":{"ofType":["Event"]},"transform":[{"where":["name:matches","^SFX_RadioTable_X_"]},{"select":["children"]}]}` + return `id,parent.name,@Target` |
| Clone a container (keeps bus, attenuation, loop, children) | `ak.wwise.core.object.copy` | `{"object":"<srcId>","parent":"<parentId>","onNameConflict":"rename"}`, then `ak.wwise.core.object.setName` `{"object":"<newId>","value":"Radio_New"}` |
| Swap a Sound's audio, keep its settings | `ak.wwise.core.object.delete` the old AudioFileSource, then `ak.wwise.core.audio.import` | `{"importOperation":"useExisting","default":{"importLanguage":"SFX"},"imports":[{"audioFile":"<kit>\\O\\SFX\\S2_Live\\Track.wav","objectPath":"\\Actor-Mixer Hierarchy\\...\\Radio_New\\<Sound>Track","originalsSubFolder":"S2_Live"}]}` |
| Retarget an event action | `ak.wwise.core.object.setReference` | `{"object":"<actionId>","reference":"Target","value":"<containerId>"}` |
| Save | `ak.wwise.core.project.save` | `{}` |
| Open another project | `ak.wwise.ui.project.open` | `{"path":"<...>.wproj","bypassSave":true}` |

- After an import check the source's `duration` matches the WAV. Source-level trims and loop points (`TrimBegin`,
  `LoopBegin`) are lost with the deleted source.
- Import from a path inside the Originals folder; a failed import ("File not found") leaves an empty source; placing the
  file at the source's `originalFilePath` afterwards also works.
- `ak.wwise.core.soundbank.generate` with `soundbanks:[{"name":"<Event>"}]` does **not** select an auto-defined event
  bank: it creates an empty 48-byte user-defined bank of that name and regenerates all ~55k auto-defined banks (~30
  min, WAAPI blocked throughout). Use the trimmed copy below. Untested ways to keep it small: `events` inside the
  soundbank entry, or a user-defined bank. `writeToDisk:false` = dry run. Filter its `logs` for errors other than the
  Convolution / Mastering / Motion plug-in licence noise.

## Licence gate
The `.wproj` ships with an empty `LicenseKey`. On the trial, bank generation fails with "Trial license: Maximum number
of media items exceeded (105976 out of the 200 permitted)" after tens of thousands of plug-in licence errors
(Mastering Suite, Convolution Reverb, Motion Source) and writes nothing. Authoring edits (copy, import, references,
save) all work without a key.

**Preferred: stay on the trial with a trimmed copy.** The 200-item limit counts media in the whole project, so generate
from a copy with every object but almost no sources:
1. `tools/audio/wwise_trim.py <mod project dir> <copy dir> --keep {GUID} ... --events '^<YourEvent>$'`. `--keep` takes
   the GUID of every Actor-Mixer / container your events play (keep the **whole Actor-Mixer** an event plays, or its
   other sounds are stripped; a Work Unit's own GUID keeps nothing). `--events` drops all other events, so generation
   takes seconds. GUIDs and ShortIDs are unchanged, so banks match the full project.
2. In the copy's `.wproj`: Originals → the absolute `<kit>\O`; SoundBankPaths `..\..\..\S2_WwiseProject\GeneratedSoundBanks`
   → `GeneratedSoundBanks` (local).
3. Open the copy (`ak.wwise.ui.project.open` or `WwiseConsole generate-soundbank`), generate.
4. Copy only your events' `Event\<Name>.{bnk,json,xml,txt}` and the new `Media\<id>.wem` into the real
   `GeneratedSoundBanks\Windows`; reopen the mod project.
5. Diff the new `Event\<Name>.json` against the vanilla one: only your media should differ.
- Plug-in licence errors are non-fatal on the trial.
- Over ~95 voice events with two languages (2 media each) is over 200 even trimmed: build in batches (one trim per
  batch, `--events` an exact-name alternation) and collect each batch's output (137 lines took three batches).

**Getting a key** (free Non-Commercial), if trimming is not enough: register at
https://www.audiokinetic.com/en/register-project/ (signed in) → "Gaming" → **"I need more than 200 media assets"** →
project details (Windows, UE5, Wwise 2024.1, free fan mod). Also ask for Convolution Reverb, Mastering Suite and Motion:
the game's Init bank uses them. Apply in Wwise: Project → License Manager; check the plug-in errors are gone before
trusting the output. Windows Launcher download: `https://www.audiokinetic.com/en/download-launcher/?platform=1`
(signed in; not needed for licensing).

## What an audio change needs to ship
- A checked-out / reconciled **AkAudioEvent .uasset** (~2 KB, no audio in it) at
  `/<Mod>/_STALKER2/Audio/WwiseAudio/Events/<same path as vanilla>/<Name>` in the mod's `Content`, and in the classifier
  list (`pipeline.md` §3).
- **The cook bundles each event's bank and media from the shared GeneratedSoundBanks into a `.ubulk`** next to the
  event. Any mod's later bank generation can overwrite those files, so keep your own copies of your events'
  `Event\<Name>.*` and `Media\<id>.wem` (and the edited `.wwu` work units) in the mod repo, and copy them back into the
  kit before every cook.
- Check the result: the cook log has `Cooking <mediaId>.wem`; the staged OverrideContent `.utoc` contains
  `<Event>.ubulk` (`UnrealPak <utoc> -List`, or a strings search). An event cooked without its `.ubulk` is silent in
  game (a radio mod's container went 7 MB → 151 KB when a hand-made repack left bulk files out of the IoStore list;
  `cook-performance.md`).
- **Headless checkout** (no Wwise Browser): an event asset is the vanilla event re-saved under the mod path. The pak's
  vanilla event `.uasset`s are UE5 file version 1008 and the editor writes 1013, so the template has to be an
  **editor-saved** event from any mod: rename its package to the new path (`WwiseName` is the same FName as the
  package short name) and replace `EventInfo.WwiseGuid` / `WwiseShortId` with `Events[0].GUID` / `.Id` from the new
  bank's `.json`. No harness tool does this yet (package rename needs a header rewriter); the Checkout click is simpler.
- Pick a replacement target by ear before cooking (play the vanilla candidates from `<kit>\O\SFX\S2_Live`) and let the
  tester confirm. Names mislead: the pause-menu music is `S_UI_IdleScreen_Loop` (event `SFX_UI_IdleScreen`);
  `S_UI_PauseMenu_Loop` is a muffled bed.
- Loudness: measure (`ffmpeg -af ebur128=peak=true`) and match the vanilla source's integrated LUFS before import; the
  Sound's own MakeUpGain / Lowpass still apply on top.

## Example: radio structure
- Events in `Events/S2 Live/Interactive Objects/IO_RadioTable.wwu`: `SFX_RadioTable_<Place>_On/_Off/_FreqSwitch`. On
  plays the `S_IO_RadioTable_On` click plus the music container, then seeks to a random position (ActionType 36,
  SeekPercent 0-100); FreqSwitch stops, replays and seeks; Off stops.
- Music containers: `Actor-Mixer Hierarchy\S2 Live\Interactive Objects\IO_RadioTable\Radio_Music\{Factions,Unique}`.
  Hubs often reuse faction playlists (the 100 Rads bar plays `Radio_Freedom`): to change one radio, clone a container
  and retarget only that radio's events.
- `Radio_Sidorovich` is the single-track template: sequence container, `PlayMechanismLoop` on, one streamed Sound on
  the `IO_Radio_Music` bus with 3D attenuation.

## Dialog voiceover (editor route; community "Volucris" guide, PDF)
How the game finds a phrase's voice and face animation, and what breaks it at cook: `dialog-voiceover.md`.

Wwise (Designer layout, F5):
1. Audio tab: `Actor-Mixer Hierarchy\S2 Live\Voiceover\VO_Voiceover\Voiceover_VM_AM\<type>` (`<type>`: ANC,
   Bossfights, Encounters, General, Hubs, MainQuests, RepeatableSideQuests, SideQuests) → New Child Work Unit
   `VO_<Quest>` → one Actor-Mixer per speaker.
2. One **Sound Voice** per phrase: phrase SID `sid_phrase_<Quest>_<Rest>` → object `VO_<speaker>_<Quest>_<Rest>`. Add
   Source → Import for English(US), again for Ukrainian(UA) (files land in `<kit>\O\Voices\<Language>\...` as
   `EN_VO_...` / `UA_VO_...`; Reference language = English(US)).
3. Events tab: `Events\Voiceover\<type>` → Work Unit `VO_<Quest>` → a Virtual Folder per speaker → one Event per Sound
   Voice, same name, a single Play action targeting it.
4. SoundBank layout (F7), Auto-Defined SoundBanks: uncheck Default Work Unit and `S2 Live`; under `Voiceover` check
   only `<type>` → `VO_<Quest>`. Platform Windows; languages English(US) + Ukrainian(UA). Generate Checked, save. One
   bank per event per language. (The guide assumes a licensed project; on the trial use the trimmed copy.)

Zone Kit:
5. Audio Modding → Wwise Browser → select the new events (status "UAsset Missing") → Reconcile icon → Reconcile Unreal
   Assets. They appear under `/<Mod>/_STALKER2/Audio/WwiseAudio/Events/Voiceover/<type>/VO_<Quest>/<speaker>/`. Many may
   then show as corrupted; restarting the kit fixes it.
6. Editor Preferences → General - Dialog Editor → "Dialog Runtime Data Asset Default Folder" = the mod's dialog folder.
   Run the Editor Utility Widget `/QuestTool/DialogUtilities/EUW_GenerateDialogruntimeAssets`, select the Dialog
   Blueprint, choose `Voiceover`, "Generate for DialogBlueprint". In the generated data asset (`NameToAsset_AssetContainer`
   map) set an AkAudioEvent per phrase key (`<Quest>_<Rest>`, no `sid_phrase_` prefix) and save.
   `RemoveNonExistingPhrases` prunes stale keys.
This route assumes an editor-authored Dialog Blueprint; mapping it onto dialogs generated from cfgs was not tried.

## Linux / Proton
For a kit running under Proton (`<proton>` = the Proton build's `proton` script, `<prefix>` = the kit's Wine prefix).
- Install Wwise once on Windows (or in a Windows VM, below) and copy the install into the prefix at
  `C:\Audiokinetic\Wwise_2024.1.10.8979`; set `WWISEROOT` / `WWISESDK` for that prefix. Prefer opening Wwise from the
  editor (Audio Modding → Open Wwise Project). **Do not start Wwise under a second wineserver while the kit editor is
  up**: it clobbers the prefix registry.
- WAAPI is reachable from Linux directly (Wine shares the host network): `waapi.py` / curl to `127.0.0.1:8090` from the
  host shell.
- Paths given to Wwise must be visible inside the Proton / pressure-vessel sandbox, under a drive letter the prefix
  maps. `/tmp` (and per-tool scratch dirs) are not: imports report "File not found" and leave an empty source. Copy WAVs
  into the Originals folder first, and keep the trimmed project copy outside `/tmp`. A fresh prefix may lack the drive
  letter the per-mod `.wproj` paths use; use one the prefix does map.
- `WwiseConsole.exe` output is swallowed by Proton: run `<proton> run cmd /c "<...>\WwiseConsole.exe <args> > <X:\...>\wwc.log 2>&1"`.
  `proton run` returns at once while WwiseConsole keeps running: wait by polling the process list for
  `WwiseConsole.exe <op>`, and never `pkill -f` a pattern that also appears in your own shell's command line (it kills
  the shell). Stop a `waapi-server` with `kill <pid>` after `project.save`.
- Audiokinetic's site gates on OS: from a Linux browser the project-registration form landed on `/en/access-denied/`
  and the download page hides the Windows Launcher. **Fallback: a Windows VM** (e.g. Windows 11 LTSC evaluation under
  QEMU/KVM, ~10 GB qcow2) for registration, licence requests and the Wwise install; share a host folder over SMB to move
  files and logs both ways.
- Play candidates with `ffplay -nodisp -autoexit <wav>`.
