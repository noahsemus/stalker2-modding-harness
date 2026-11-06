# Reverse engineering the shipped exe

How to recover native game logic (AI, spawning, combat resolution, looting) from
`<game>\Stalker2\Binaries\Win64\Stalker2-Win64-Shipping.exe` when the kit's cfgs and dumps (`zonekit.md`,
`config-files.md`) do not answer the question. Results so far: `combat.md`, `saves.md` § name limit. Reading a crash
address without symbols: `diagnostics.md` § Reading a crash without symbols (not repeated here).

**The deliverable is a mechanism**: pseudocode and plain English, with assembly only as evidence for a surprising
claim. Every address is build-specific: write it down with the exe's size and date, and expect it to move on the next
patch. Names and mechanisms survive patches.

Tools: `harness/tools/re/pe.py` (PE64 helper, stdlib only), `harness/tools/re/pdbq.py` (stale-PDB queries, needs
`llvm-pdbutil`). Disassembly: `objdump -d -M intel` (GNU binutils) or `llvm-objdump`. Strings: GNU `strings`, or
`pe.py`'s `finda` / `findw`.

## Work in the retail exe
The Zone Kit's editor binary looks richer and is a trap (measured 2026-10, kit vs retail):

| | Kit / mod editor | Retail |
|---|---|---|
| Type-descriptor names (`.?AV...@@`) | 3832 | 1138 |
| ... naming gameplay classes | 383 | 212 |
| gameplay classes with a usable RTTI complete object locator | 0 | 0 |
| ASCII / UTF-16 strings | 1.15 M / 189 K | 604 K / 99 K |
| Size | 356 MB | 194 MB |

- Neither build has gameplay RTTI: all COLs belong to statically linked third-party/`std` code. There is no
  vtable → class-name path; use UHT registration data (below).
- The kit is an **older code revision**, strictly behind retail: 110 vs 132 `ai.*` cvars, 42 vs 43 `EGoalType`
  values, 7 gameplay classes and a whole subsystem (crossfire) only in retail. Tuning values read there may not ship,
  and absence there is not absence.
- Its one use: ~180 extra gameplay class names, mostly the `*Prototype` family (`FAbilityPrototype`,
  `FALifeDirectorScenarioPrototype`, ...). Grep its type-descriptor list for a name, carry the name to retail.
- Same for cfg values: the kit's `GameData` cfgs may differ from what retail ships; for a number that matters, read the
  retail pak's cfg.
- **Where retail keeps them** (game 2.1, 2026-11-06): `<game>\Stalker2\Content\Paks\pakchunk0-Windows.pak` (182 MB,
  legacy pak) holds `Stalker2/Content/GameLite/GameData/...`, partly as plain `.cfg`, but the big trees are merged
  binaries: `QuestNodePrototypes.cfg.bin` (44 MB unpacked), `SpawnActorPrototypes.cfg.bin`, `<Type>.cfg.bin` per
  folder. Pull one out with the kit's UnrealPak: `UnrealPak <pak> -Extract <dir> -Filter=*GameData/<Name>.cfg.bin`
  (`-Filter` does filter for `-Extract`; it is `-List` that ignores it). Format: a pool of length-prefixed strings,
  then 21-byte nodes (name, name, value, source path, flag, child count; references are 1-based string indices). Every
  record keeps its source path (`GameData/SpawnActorPrototypes/WorldMap_WP/<Level>/<GUID>.cfg`), so patch-folder
  placement still follows the original file. SIDs and field names are plain ASCII: a byte search answers "does
  retail still have node / actor X" in seconds.

## Strings: extract twice (the highest-value rule)
```
strings -n 5     Stalker2-Win64-Shipping.exe > s.txt     # ASCII
strings -el -n 5 Stalker2-Win64-Shipping.exe > sw.txt    # UTF-16LE: do not skip
```
- UE stores `TCHAR` as UTF-16. Reflection/UPROPERTY names and header paths land in ASCII; hand-written
  prototype-parser field names, cvar names, log categories and most format strings land only in the wide dump.
  "X does not exist" from the ASCII dump alone is invalid.
- **Diagnostic:** a cfg field name present only in the wide dump is not a UPROPERTY; a hand-written parser reads it
  (no Blueprint/editor exposure, no validation). Run this on retail only: the editor build leaks hand-parsed names
  into ASCII (`AllowedUserRestriction`, `RequireMinRank` are wide-only in retail but ASCII in the kit).

## Naming a class without RTTI (UHT registration)
1. Spelling first: grep the ASCII dump for `\.\?A[VU][^\x00]*@@`.
2. Find the class name as UTF-16 **with** its `U`/`A`/`F` prefix (`findw('UMyClass')`).
   `GetPrivateStaticClassBody` gets the name without the prefix (`name_va + 2`).
3. `ptrsto(name_va)` → a hit in `.data` inside an `FClassRegisterCompiledInInfo` array (stride 40):
   `[-0x10]` OuterRegister → `Z_Construct_UClass_X`, `[-0x08]` InnerRegister → `X::GetPrivateStaticClass`,
   `[0]` name, `[+0x08]` `FClassRegistrationInfo`, `[+0x10]` hash.
4. Disassemble InnerRegister; its `GetPrivateStaticClassBody` call carries the layout:

   | Location | Meaning |
   |---|---|
   | `rcx` / `rdx` | package (`/Script/...`) / class name without prefix |
   | `r8` | `&ReturnClass` (static `UClass*`) |
   | `[rsp+0x20]` / `[rsp+0x28]` | **sizeof** / alignment |
   | `[rsp+0x30]` | EClassFlags (`0x1` = abstract) |
   | `r11-0x50` | ClassConstructor |
   | `r11-0x38` | SuperClassFn: disassemble, read its `lea rdx` name operand → parent |
   | `r11-0x30` | WithinClassFn |
5. ClassConstructor is an `InternalConstructor` thunk (`mov rcx,[rcx]; test; jne <real ctor>`). The real constructor
   stores the **vtable** (`lea rax,[rip+X]; mov [rbx],rax`) and initialises members: offsets and defaults.

## Finding a virtual method: vtable diffing
1. Get vtables of the abstract base and two or more concrete subclasses (`vtable(va)`).
2. Vtables are packed back to back with no terminator. The next vtable's slots 1..5 repeat the base's slots 1..5
   (shared `UObject` virtuals): scan forward for that repeat; match position minus 1 = next vtable start.
3. Diff, ignoring slot 0 (destructor). Class-specific virtuals are a short run near the end.
4. The target is the slot where the base has a tiny stub and every subclass overrides it with hundreds-thousands of
   bytes. Exact bounds from `.pdata` (`fnrange`), never from `int3` padding.

## Reading logic
- **Entry points are log and debug strings.** Find a subsystem's `Log<Name>` category in the wide dump, then nearby
  format strings: one translation unit's strings cluster in `.rdata`, often the full set of outcomes of a function
  (e.g. `"No lair"`, `"No participants"`, `"Success(CanCapture)"` gave a 1.7 KB function's control flow before
  reading it). From a string VA, grep a `.text` disassembly for the address.
- Keep one full `objdump -d -j .text -M intel` dump on disk and grep it repeatedly (a few minutes on ~200 MB; run it
  in the background). Re-disassembling per address is the biggest time sink.
- Cfg fields read by a hand-written parser: find the `lea rdx,[name]` site (a flat `TryGetField(name)` → store-to-global
  chain), follow the store, then xref the global for readers.

### Idioms
- **`SRand` / `FMath::RandHelper`** marks every gameplay random roll (one global seed shared by all systems):
  `imul eax,[GSRandSeed],0xbb38435; add eax,0x3619636b; shr eax,9; or eax,0x3f800000; subss 1.0` (→ [0,1)),
  then `mulss N; cvttss2si` for `RandHelper(N)`.
- **Cvar read** (`TConsoleVariableData<T>::GetValueOnAnyThread`): load the value pointer, two thread-check calls,
  `mov eax,[base+0|4]`.
- **Cvar registration** through the `IConsoleManager` vtable gives defaults: slot `+0x18`
  `RegisterConsoleVariable(name, int default, help, flags)` (default = `r8d`); slot `+0x30`
  `RegisterConsoleVariableRef(name, T& var, ...)` (`r8` → storage holding the default). The help string sits next to
  the name and often states units.
- **TMap lookup**: hash call, `and` with `[map+0xE8]-1`, index `[map+0xD8]`, elements at `[map+0xA0]`, `-1` empty,
  `+0x68` next-in-chain.
- **Chunked pools**: `if (i < 0x400) inline array of stride S else heap chunk` gives entry size and chunk size.
- **Budgeted round-robin**: `budget = min(cvar, total); scaledDelta = total * dt / budget; cursor = (cursor+1) % total`.
  Nothing is culled; only temporal resolution drops as the population grows. Answer "how much is simulated" with the
  update interval and per-update jump.

## Constant provenance: check before saying "hardcoded"
| Where the float lives | Meaning |
|---|---|
| `.rdata` | compile-time constant |
| `.data` within the section's raw size | initialised at build; look for writers |
| `.data` beyond raw size (`va2off()` returns `None`) | zero at load, written at runtime: a cfg/prototype value whose number is not in the exe |

- Classify every `.text` reference to the address: `movss xmm,[rip+..]` = read, `movss [rip+..],xmm` = write.
  "Hardcoded" only with zero writes; neighbouring slots with writers are a control that the scan works.
- A cfg parser may write a whole struct through a base pointer and never name the field's address, so no direct store
  is not proof. MSVC pools identical float literals: one address can serve unrelated call sites.
- `.data` defaults compiled in for CoreVariables are overwritten from `CoreVariables.cfg` at load (`combat.md`).

## World units
Never assume centimetres; confirm twice: an in-data comment (`FarLairDistance = 100000.f // 1000m`) and a spatial
grid's extent (cell size from the reciprocal the code multiplies by x axis count from the clamp bound, e.g.
`mov r9d,0x4f` → 80 cells) against the known map size.

## Optional decompiler: Ghidra via REA (not yet run on this exe)
[REA](https://github.com/morluto/rea) (`rea-agents` on npm, 6.5.0 as of 2026-10-17) is an MCP server/CLI driving
Ghidra headless (pseudocode, typed READ/WRITE xrefs, call targets). It speeds up reading a function once found; UHT
registration, vtable diffing and string clusters still find it. Costs below are from REA's docs only.
- Needs Ghidra 12.1.x and a 64-bit JDK 21+. Register REA's MCP server with your agent client (its `setup` command
  has a `--dry-run`); set `GHIDRA_HEADLESS_MAXMEM` (2G default is far too small for a ~200 MB PE; start at 24G),
  `REA_GHIDRA_STARTUP_TIMEOUT_MS` (default 330 s covers import + analysis of small binaries only; use hours) and, if one
  analyzer stalls, `REA_GHIDRA_DISABLED_ANALYZERS`. These are read at server start.
- Projects are ephemeral: every new session re-imports and re-analyses. Use the MCP server (the CLI re-analyses per
  call), open the exe once, keep the session open, snapshot before closing (snapshots replay identical queries only).
- `REA_GHIDRA_SEED_FILE` (TSV `address<TAB>function|code|label[<TAB>name]`) seeds names found with `pe.py` before
  analysis; changing it re-analyses, so collect first and seed once.
- Ghidra uses the image's VAs (`0x14...`), matching objdump and `pe.py`. Pseudocode often mistypes floats and folds
  constants: check any reported number against the instruction and its section. Unresolved indirect calls (vtable
  dispatch) stay unknown.
- Still `pe.py` for class names/sizes/vtables (Ghidra sees no gameplay RTTI either), still two `strings` dumps, still
  objdump for the full `.text` dump (REA's objdump wrapper caps output at 16 MiB).

## Using a stale PDB for names only
A PDB from an older build of the game is a vocabulary and structure oracle, never a layout oracle. The exe is the
source of truth.
- `llvm-pdbutil dump --summary x.pdb`: want `Has Types: true`, `Is stripped: false`. Compare its GUID with the exe's
  `RSDS` debug record. Match = real symbols, use directly. Mismatch = stale, rules below. The PDB name an exe
  references proves nothing; only the GUID does.
- `pdbq.py` wraps `llvm-pdbutil dump --types` (works without DIA; `pretty` needs DIA):
  `index <pdb>` (one-time cache, ~40 s-4 min for 2 GB), `grep <pdb> <regex>`, `class <pdb> <Name>` (bases, members,
  methods, vtable slots), `enum <pdb> <Name>`, `bases <pdb> <Name>`. Never dump all types to a file (~9 M records,
  several GB of text). Names resolve to forward-ref stubs (`sizeof 0`); the tool follows them.
- In `class` output, virtuals a class introduces carry a vftable offset; overrides report `-1` (they reuse the base
  slot) and are still virtual.

| Fact (2023 PDB vs 2026 retail, 29 classes) | Transfers? |
|---|---|
| class / struct / enum names, inheritance chain, method names, virtual-or-not | yes |
| member names | mostly (11/12 `AAnomaly` members) |
| order of a class's own virtuals | yes (contiguous run, appended to) |
| `sizeof`, member offsets | no (5/29 sizes equal; `AStalker2PlayerController` 2064 → 3264, `AAnomaly` 848 → 944) |
| enum values, absolute vtable slot indices, addresses | no |

- Divergence runs both ways and additions dominate: of 120 sampled retail enums, 66 did not exist in the PDB; of the
  54 shared, 186 enumerators were retail-only and 4 PDB-only. Whole subsystems are missing (`EAIFeature` lacks
  `ALifeDirector`, `ALifePopulationManager`, `SeePlayer`, `ProcessCorpse`; `EAgentType` lacks Boar/Burer/Chimera/
  Poltergeist/Snork). Spellings move (`CannotAddItseflAsAChild` → `CannotAddItselfAsAChild`). **Absence in the PDB
  proves nothing**, and it is weakest on the newest systems, the ones most worth investigating.
- Order: locate the subject in the exe first (strings, registration data), then ask the PDB for names, parents, fields;
  confirm each borrowed name in the exe's string dumps (`AAnomaly::ForceActiveState` is gone from retail); re-derive
  every number from the exe (offsets from the constructor, sizeof from `InSize`, enum values from its reflection data).
  Never let the PDB bound a search for a complete list.
- When asked not to use the PDB, do a blind pass: it avoids anchoring on old structures, stopping at the PDB's member
  count, and writing a remembered name as if confirmed.
- Do not paste symbol dumps or generated headers into public repos or issues; cite the behaviour verified in the exe.

## Reporting
- Label every number's source: binary, cfg (kit or retail pak), or inferred. Never report a constant read from the
  kit build as what ships.
- Separate "the field exists and is read" from "what it controls". Say what you did not trace (callers, frequency).
- Correct earlier claims plainly with the check that overturned them. Distances in raw units and converted.

## Linux / Proton
- The game exe is the same Windows PE under Proton: `<steam>/steamapps/common/<game folder>/Stalker2/Binaries/Win64/
  Stalker2-Win64-Shipping.exe`. All addresses and methods above apply unchanged.
- Linux hosts have GNU `strings` / `objdump` natively; `capstone`, `pefile`, `numpy` and even `pip` are often absent,
  which is why `pe.py` and `pdbq.py` are stdlib only. `pe.py` runs as `python3 -i pe.py <exe>`.
- `llvm-pdbutil pretty` fails off Windows with "LLVM was not compiled with support for DIA ...": nothing is corrupt,
  the subcommand is unavailable; `dump --types` (what `pdbq.py` uses) works. Its cache lives in
  `~/.cache/ue-pdb-index/`.
- REA needs `ps` (procps) on `PATH`. Kuna, REA's other free decompiler, rejects PE files; Ghidra is the free option.
