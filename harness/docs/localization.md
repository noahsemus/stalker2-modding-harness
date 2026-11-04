# Localized text: how the game stores it, how a mod adds or changes it

From retail `.locres` files (extracted 2026-09-15), the Zone Kit's text assets and in-game tests (2026-09-15 →
10-08). Voice lines and their keys: `dialog-voiceover.md`.

## Where vanilla text lives
- One `Game.locres` per culture, loose inside the `.pak` (not the `.utoc`) of `<game>\Stalker2\Content\Paks\
  pakchunk0-Windows.pak`, at `Stalker2/Content/Localization/Game/<culture>/Game.locres`. Any pak tool that reads
  plain `.pak` files reaches them (`UnrealPak <pak> -Extract <dir>`, `repak get <pak> <path>`).
- 18 cultures, in `ELocalizationLanguage` order: `en uk de fr es it pl cs tr sr pt-BR es-419 ar zh-Hans zh-Hant ja ko
  ru`. Ukrainian is `uk`. `es` = SpanishEuropean, `es-419` = SpanishLatinoAmerican, `pt-BR` = PortugalBrazilian.
- ~82.9k keys per culture, all in one namespace `ST_S2BaseGameLocalization`. Only ~49.6k have English text; the rest
  ship an empty string (placeholders, cut content). A key missing from a dump of one culture often exists but is
  blank: check another culture before concluding a key does not exist.
- Search dumps case-insensitively: both halves of a name can be present while the exact casing typed is not.
- The kit's `Stalker2/Content/TextToolBackup/TextDatabase.json` was a 0-byte stub on the machine checked; it is not a
  text source. (The `TextDatabase_<part>.json` files in the FullEditor pak hold the TextTool character list,
  `dialog-voiceover.md`.)

### `.locres` format (v3, `Optimized_CityHash64_UTF16`)
16-byte magic (`0e 14 74 75 …`), version byte, `int64` string-table offset. At that offset: `int32` count, then
per string `FString` + `int32` refcount. Back after the header: `int32` entry count, `int32` namespace count, then
per namespace `(uint32 hash, FString)` + `int32` key count + per key `(uint32 hash, FString key, uint32 sourceHash,
int32 stringIndex)`. `FString` = `int32` length; negative = UTF-16LE of `-n` chars, positive = 8-bit; both include the
terminator. Enough for a small stdlib dumper to `{key: text}` JSON per culture; redo the dump after each game
patch (official wording changes).

## Key names (SIDs)
| Prefix | Text |
|---|---|
| `sid_character_<NPC prototype id>` | NPC names (`sid_character_micman_0` → "Ensign") |
| `sid_topic_<DialogChainSID>` | topic line in the NPC's dialog menu |
| `sid_label_<label>` | short reply option (the player's choice) |
| `sid_phrase_<TextToolPhraseSID>` | a full spoken line |
| `sid_notes_` | notes / documents |
| `sid_items_<ItemSID>_name` / `_description` / `_short_name` | item text; `_short_name` only weapons/ammo (tight UI slots) |
| `sid_journal_<QuestSID>_Name` | journal quest title |
| `sid_journal_description_<DescriptionSID>` | journal description |
| `sid_journal_stage_<StageSID>` | journal stage (keyed by the stage SID, not its `Description` field) |

- **Items**: name and description are not prototype fields; the game derives `sid_items_<SID>_name` /
  `_description` from the item prototype's `SID`. A new item needs only that pair; without it the UI shows the raw
  SID. The prototype field `LocalizationSID` redirects the lookup to `sid_items_<LocalizationSID>_name` (vanilla
  mutant loot `mutpartspack_*` does this), so variants can share one text.
- **Dialog phrases**: a `DialogPrototype` with no `TextToolPhraseSID` has no text key. Vanilla copies (`..._41275_1`)
  reuse the original's `TextToolPhraseSID`.
- **Labels are derived**: the game drops the last `_<segment>` of a `TextToolPhraseSID` to find the reply label
  (`RSQ01_Dialog_Warlock_RSQ_confirm_26957` → `sid_label_RSQ01_Dialog_Warlock_RSQ_confirm`; that text is the answer
  option in WaitForReply pickers). So name every phrase `<label SID>_<NNN>` (vanilla: `<label>_<5-digit id>`). The
  cut is always at the last `_`: `Foo_Accept_Bar_1` was read in game as `sid_phrase_Foo_Accept_Bar`, and
  `Foo_Accept_Accepted_1`'s label as `sid_label_Foo_Accept` (2026-10-08).

## How a mod ships text
- **Source asset**: the Mod Editor's Text Tool creates a `LocalizationModTextToolAsset` in the mod's `Content`, whose
  single export is `LocalizedTexts: Array<{ SID: FString, LanguagesToLocalizedStrings: Map<ELocalizationLanguage,
  FString> }>`. Language keys are the enum members exactly: `English, Ukrainian, German, French, SpanishEuropean,
  Italian, Polish, Czech, Turkish, Serbian, PortugalBrazilian, SpanishLatinoAmerican, Arabic, ChineseSimplified,
  ChineseTraditional, Japanese, Korean, Russian`. SIDs are free-form strings.
- **Dialog text asset**: `/Script/ModKitEditor.DialogModTextToolAsset`, export `Dialogs`:
  ```
  Dialogs: Array<DialogTopicTextTool_ModEditor>
    TextToolTopicName, SID = <ModName>_<TopicName>       GlobalWFR.SID  = sid_topic_<SID>
    TopicCharacterSIDs: Array<Name>
    Labels: Array<DialogLabelTextTool_ModEditor>
      TextToolLabelName, SID = <topic SID>_<LabelName>   LabelWFR.SID   = sid_label_<SID>
      Phrases: Array<DialogPhraseTextTool_ModEditor>
        SID = <label SID>_000, _001, ...                 PhraseText.SID = sid_phrase_<SID>
        Character: Name (speaker, e.g. a vanilla character id; None when unset)
  ```
  `GlobalWFR` / `LabelWFR` / `PhraseText` are each `{ SID, LanguagesToLocalizedStrings }`. The scheme matches what
  the game expects of `DialogPrototype.TextToolPhraseSID` (label = phrase SID minus `_<NNN>`). A label groups a
  reply option with the lines spoken after it. `Character` must be a known TextTool character for voice to register
  (`dialog-voiceover.md`). Whether the cook-time gather picks up dialog text by itself: not verified.
- **What the game reads**: at cook the editor gathers every text asset into one generated package (log:
  `LogModTextToolManager: Created mod localization database with N localized texts from M ModTextToolAsset assets`,
  `LogModAssetCreator: Saved ModLocalizationDatabaseDataAsset '../../Mods/<Mod>/Content/Autogenerated_<n>_
  LocalizationDatabase.uasset'`). Export `LocalizationDatabase: TMap<FString SID, FModLocalizationLocalizedStrings
  Container>` holding the same language map. `<n>` is the save's Unix timestamp; once cooked, that name is the mod's
  identity. The `.uplugin` lists no assets: anything in `Content` gets cooked.
- **One database per mod.** A second `Autogenerated_<m>_LocalizationDatabase` of the same SIDs left in `Content`
  (e.g. after copying assets between machines) is cooked too, and the classifier can put the two in different
  containers (seen 2026-09-15: one in OverrideContent only, the other in both). Delete the stale one.
- **Package identity**: copying another mod's text asset and renaming the file leaves its package name pointing at
  that mod; create a fresh asset in the Text Tool. The asset's `LocalizationId` namespaces its gathered text: two
  mods must not share one. A text package's name is stored in the summary `PackageName`, twice in the name table and
  again in the asset-registry section, so a rename is not a string replace.

## Overriding vanilla text
- A mod's localization database **overrides** base-game keys (verified in game 2026-09-15: 22 vanilla `sid_label_*`
  dialog options re-worded with no cfg patch). Renaming any shipped string is a text-only mod.
- Supply every language for an overridden key; a language left out falls back to English. Take the official wording of the other cultures from the `.locres` dumps.

## Checks
- UI shows the raw key (`sid_items_<SID>_name`): the key is not in the cooked database. Extract the staged container
  and search for the SID (it is stored as an FString: a plain byte / UTF-16 grep of the `.ucas` finds it) before
  suspecting anything else; then check the database's name (one per mod) and that the key spelling matches the
  derivation rules above.
- New item shows the SID: the `sid_items_<SID>_name` pair is missing or `LocalizationSID` points elsewhere.
- A reply option shows the wrong text or a raw key: the phrase SID's last `_` segment cut it differently than meant.

## Linux / Proton
- The game's paks and the kit read the same from a Linux host: `repak list "<game>/Stalker2/Content/Paks/
  pakchunk0-Windows.pak" | grep locres`, then `repak get <pak> Stalker2/Content/Localization/Game/<culture>/
  Game.locres > <culture>.locres` (no IoStore tooling needed). Under Steam/Proton, `<game>` is
  `<steam>/steamapps/common/<game folder>`.
- Check a staged build with `strings -a <staged>.ucas | grep <SID>` (8-bit text; add `-el` for UTF-16 strings).
- Text assets and the database are plain UE packages; the Mod Editor running under Proton writes the same files as
  on Windows.
