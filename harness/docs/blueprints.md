# Blueprints: paste text, reading graphs back, editor Python, editor traps

## Blueprint nodes as clipboard text (T3D)
Graph nodes copy/paste as plain text: `Begin Object Class=/Script/BlueprintGraph.K2Node_... Name="..."`, one
`CustomProperties Pin (...)` line per pin, links as `LinkedTo=(NodeName PinId,)`, `End Object`. Proven for blocks
of 20-200 nodes (event graphs and anim graphs).

1. Ask the tester to select a few existing nodes of the needed types in the editor and press Ctrl+C. Read them with
   PowerShell `Get-Clipboard -Raw`: that is the exact pin format for this engine build. Or export a whole asset
   yourself: `ue_exec.py tools/editor/export_t3d.py --arg ASSET=/Game/...` (no tester).
2. Generate the block with `tools/t3d/bp_graph.py` (declare nodes and pins, `graph.link(a, b)` writes links on
   **both** ends, `graph.box(...)` comment boxes) on top of `bp_t3d.py` (pin/type strings, fresh 32-hex GUIDs).
   `t3d_lift.py` lifts real nodes out of an exported T3D (e.g. the game's own AnimGraph nodes with their nested
   binding sub-objects), renames them, gives every pin a fresh id and lets you relink them.
3. Put it on the clipboard (`Set-Clipboard -Value (Get-Content <file> -Raw)`), the tester clicks into the graph and
   presses Ctrl+V, then wires only the 1-3 pins that connect to nodes outside the block. **Links to nodes that are
   not in the paste are dropped**, so keep external wiring minimal and name those pins exactly.
   **Asset defaults (`DefaultObject="/Mod/.../AS_X.AS_X"`) resolve only for assets loaded in the editor at paste
   time**; an unloaded one is dropped silently (empty pin, compiles fine). Assets you just built with editor Python
   get garbage-collected once nothing references them (Looting 2026-11-04: 28 new animations came through empty;
   the ones the Blueprint already referenced were fine). Before handing over a paste with new asset references,
   load them and hold them from the editor's Python (`builtins._keep = [unreal.load_asset(p) for p in paths]` via
   `ue_exec.py`; the interpreter persists), and after the save check the export for each `DefaultObject`.
4. They compile and save; read it back with `export_t3d.py` to verify (the export lists deleted-but-not-GC'd nodes
   too: trust each graph's `Nodes(n)` list).

**Big generated graphs: split them over event graph pages** (Looting 2026-11-05: deleting a 3,700-node graph crashed
the editor every second time in a session). `Graph.paginate(roots, default, prefix, self_class)` assigns each exec node
to the first page whose start nodes reach it, turns every exec link between pages into a call (`K2Node_CallFunction`,
self) to a custom event on the target page (synchronous: the order is unchanged), clones shared pure trees per page,
and refuses a data link from an exec node's output to another page (keep both ends on one page, or pass the value
through a variable; a bound event's `OutputDelegate` must sit on its bind node's page). Write one `.txt` per page plus
a `pages.json` of `page_digest`s; `tools/paste_pages.ps1 -Dir <dir>` opens a small always-on-top window for the
tester with one Copy button per CHANGED page (against `pasted.json`, which the agent updates after checking the paste).
Pages are made once by hand (My Blueprint > Graphs > +, named as the page; Python cannot add event graph pages). The
first switch from one graph: on a freshly opened editor delete everything in the old graph FIRST (its custom events
would collide with the pasted ones and get renamed), then paste the pages, the main page (the calls) last, then
File > Refresh All Nodes, Compile, Save. Aim for pages of ~200-800 nodes.

**Readable paste layout (tester-approved, Looting 2026-10-10: "best layout so far"):** call `graph.layout_tree()`
before writing. It
- clones every pure node that feeds more than one pin (pure nodes are re-evaluated per use anyway), so each data
  input sits right next to the node that uses it;
- inside each comment box runs the exec chain left to right on a row, each exec node's data inputs as a small tree
  directly to its left; Branch false / Sequence then_1.. open rows below; chains longer than `max_row` wrap;
- places the boxes along the flow: a box entered from another box sits to its right, boxes fed by one box are
  stacked in the order of the pins that feed them, unfed boxes (events) start new groups; boxes are resized to fit.
Generator rules that keep it readable: put every exec node inside a comment box (hand coordinates only choose the
box; an input event and its chain need a box of their own), and never wire one exec output (a cast's `As X`, a
spawn's `Return Value`) to many places: store it in a variable right after the exec node and read the variable at
each use (`self_get` creates one getter per use), or the wires fan out across the whole graph. `layout()` (a plain
column grid) is kept only for comparison; it was harder to follow.

Put `NodeComment` labels and comment boxes in the generated text (see `collaboration.md`). Keep mod-specific
generators in the mod's `zonekit/tools/gen_*.py`; lift reusable node builders into `bp_graph.py` here.

- **Delegate binding pastes fine**: `K2Node_AddDelegate` (`DelegateReference=(MemberParent=<class>,MemberName=...)`,
  a `Delegate` pin whose `PinSubCategoryMemberReference` names the `..._DelegateSignature` in its package) linked to a
  `K2Node_CustomEvent` whose parameters come from `CustomProperties UserDefinedPin (PinName=...,PinType=(...),
  DesiredPinDirection=EGPD_Output)`. Bind once per target object (keep the bound object in a variable and compare).
  Campfires binds `AnimInstance.OnMontageStarted` this way.
- **Don't call a custom event of the same graph from pasted text**: the paste asks to "Fix Self Context Function
  References" and the compile fails ("In use pin no longer exists"). Drive the follow-up from the tick (a flag or a
  timestamp checked each tick) instead.

- **ForEachLoop paste**: `K2Node_MacroInstance` with `MacroGraphReference=(MacroGraph="/Script/Engine.EdGraph'/Engine/
  EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop'",GraphBlueprint=...StandardMacros'",
  GraphGuid=99DBFD5540A796041F72A5A9DA655026)` (GUID read from the kit's `Engine/Content/EditorBlueprintResources/
  StandardMacros.uasset`), `ResolvedWildcardType=(PinCategory="object",PinSubCategoryObject=<class>)`, pins `Exec`,
  `Array` (container Array), `LoopBody`, `Array Element`, `Array Index`, `Completed`.
- Function purity after a paste comes from the UFunction (`bDefaultsToPureFunc`), not the pasted `bIsPureFunc`:
  write `const` getters (BlueprintCallable const = pure) without exec pins and static library calls with them, or the
  reconstructed node drops the exec links.
- **A pasted call to a function that does not exist on the named class is silently dropped too**, and the graph
  still compiles: its consumers read the pin default (ImmersiveLooting v1.1.0: `SelectString` named on
  `KismetStringLibrary`; it lives in `KismetMathLibrary`. The asset path came out empty and every hold-to-use loaded the
  fallback animation for seven builds). Before handing over a paste, check every `FunctionReference` resolves in the
  editor (`unreal.find_object(None, "/Script/Engine.<Class>:<Function>")`; inherited functions such as
  `GetSocketLocation` resolve only on the declaring class), and after the paste compare function counts of the export
  with the paste.
- **An asset export also contains the nodes deleted in this editor session** (the undo buffer keeps them; a garbage
  collection does not drop them): they come out with the graph's path like live nodes, so counting `Begin Object`
  lines per graph overcounts after every Ctrl+A / Delete / paste (ImmersiveLooting: a 754-node page "had" 2968). Count
  the graph's own `Nodes(<n>)=` list instead (the live nodes) and read compiler messages only from nodes in it.
- `Actor.AddComponentByClass` is BlueprintInternalUseOnly: write the `K2Node_AddComponentByClass` node (pins `self`
  (the actor), `Class` (DefaultObject = the component class), `bManualAttachment`, `RelativeTransform`, `ReturnValue`,
  plus execute / then, like `K2Node_SpawnActorFromClass`); its ReturnValue comes back typed by the Class pin, so a cast
  after it only draws an "already a ..." note.
- **A pasted call to a BlueprintInternalUseOnly function is silently dropped** (no error, its links vanish): e.g.
  `KismetMathLibrary` `Ease` / `VEase` / `REase` belong to the `K2Node_EaseFunction` node. Ease by hand
  (`alpha * alpha` + `VLerp`). After every paste, export the graph and compare node and link counts with the
  generated text (match by function + comment, not node name: the editor renames nodes that collide with deleted,
  not yet garbage-collected ones).
- Static library functions are impure unless declared BlueprintPure: e.g. `KismetMaterialLibrary.GetScalarParameterValue`
  pasted without exec pins compiles with "was pruned because its Exec pin is not connected" and reads 0. Put such calls
  in the exec chain and keep their results in variables.
- **Two nodes with the same `Name=` in one paste: one is silently dropped** and the exec chain through it ends there
  (ImmersiveBattleFixes 2026-11-06: lifted MCM nodes numbered 920+k / 930+k / 940+k collided past 10 settings; the
  register chain stopped at setting 11, `AddUniqueModID` never ran and the mod was missing from the MCM menu). Assert
  unique names in the generator, and after the paste count the calls in the export or the cooked bytecode
  (`zen_kismet.py`).
- **A struct pin default on a game struct came through empty** (ImmersiveBattleFixes 2026-11-06:
  `CppMediator.StartQuestNode`'s `SID` pin, struct `/Script/Stalker2.PrototypeSID`, text form `(Value="X")`, pasted as
  `DefaultValue="(Value=\"X\")"` where the editor writes it; after the paste + Refresh All Nodes the export showed
  `(Value=\"\")`, while string defaults on the same nodes survived; the pin is const-ref). Feed such pins from a
  member variable of that struct type whose default is set on the CDO from Python
  (`v = unreal.PrototypeSID(); v.import_text('(Value="X")')`), and check the export / CDO after.
- **Cast output pin names use the class display name with spaces**: `AsInput Mapping Context`,
  `AsInteractable Item Container`, `AsDead Body` (a misspelled pin silently drops its links).
- From Git Bash, `ue_exec.py --arg ASSET=/Mod/...` gets its path rewritten to `C:/Program Files/Git/Mod/...` (MSYS
  path conversion): run it from PowerShell or with `MSYS_NO_PATHCONV=1`.
- `ue_exec.py`: UE's remote execution treats a command as a FILE path when its text contains `<something>.py`
  early (e.g. a docstring saying "run with ue_exec.py ..."): "Could not load Python file". Keep `.py` names out of
  the first lines of scripts sent with it. A script that raises leaves its previous output file in place: delete the
  output before the run, or you read stale results.
- `UUserWidget::GetWidgetFromName` is not Blueprint-callable in 5.5; native widget members bound with BindWidget are
  usually not BP-visible either. Find a child widget by `GetAllWidgetsOfClass(<its class>, TopLevelOnly=false)` +
  `GetPathName` contains `<Parent>.WidgetTree.<Child>` (once, on an edge).

Blueprint "Float" variables are doubles. `BlueprintEditorLibrary.add_member_variable` adds variables from Python;
`reparent_blueprint` reparents; Blueprint graphs themselves cannot be authored from Python (only pasted).

## Editor Python
- **Remote execution** (Project Settings → Plugins → Python → Enable Remote Execution; not in Editor Preferences)
  lets `tools/ue_exec.py <file|code>` run scripts in the tester's open editor in seconds. The harness prelude gives
  scripts `MOD`, `MOD_ROOT`, `UPLUGIN`, `SCRATCH`, `ARGS`.
- In the live editor, `EditorAssetLibrary.duplicate_asset` and `AssetTools.duplicate_asset` return **None for /Game
  sources**; run duplication headless (`run_headless.ps1 tools/editor/duplicate_asset.py`) or edit existing mod
  assets in place.
- Never edit an asset headless while the tester's editor is running (check with `ue_exec.py` first, not by process
  name): the editor keeps its loaded copy, and its next save overwrites the headless one. A variable added headless
  then shows on paste as "Could not find a variable named ..." / "The property associated with ... could not be
  found"; add it again in the live editor (`ue_exec.py`, `add_member_variable`), then Refresh All Nodes / Compile.
- `unreal.new_object(cls, outer)` works for small sub-objects (e.g. `PlayerMappableKeySettings`). Setting properties
  on freshly created modifier/trigger objects fails with "cannot be edited on templates": **move** the real objects
  from a duplicated source instead (`rename(outer=...)`, see `input.md`).
- A SoftClassProperty only accepts a real class object from Python (`tools/editor/set_bp_default.py`).
- CDO flags such as `AutoReceiveInput = Player0` on an actor Blueprint can be set from Python.

## Replacing a big graph: never Ctrl+A / Delete it in the editor (ImmersiveLooting 2026-10-30)
- Deleting a ~3,700-node / 14,000-pin event graph in one go made the editor reach ~118 GB of virtual memory and die
  ("Ran out of memory ... paging file is too small"), twice; at ~3,400 nodes it still went through.
- Instead, with editor Python: `EditorAssetLibrary.rename_asset(<BP>, <BP>_Old)` (when its referencers are not
  loaded, no redirector is written and they keep pointing at the original path), create a fresh Blueprint at the
  original path with the mod's setup script (variables, defaults, class settings), have the tester delete its 3
  default event nodes and paste into it, verify the graph, then `delete_asset(<BP>_Old)`. Keep a file copy of the
  old `.uasset` first.
- In practice (3 times) the tester still pasted into `<BP>_Old`: the editor kept serving the renamed asset when the
  original name was opened. The paste itself is what matters: wherever it lands, finish with the swap back (delete
  the empty fresh asset, rename `_Old` to the original name, setup script, recompile referencers).
- **Have the tester close that Blueprint's editor tab BEFORE the rename**: an open tab follows the renamed asset, and
  twice the paste went into `<BP>_Old`. If it did, swap back: delete the empty fresh asset, rename `_Old` to the
  original name, run the setup script again (variables added after the rename are missing on `_Old`), recompile the
  referencers (their path references stay valid).

## Widgets (UMG) from Python (ImmersiveLooting 2026-10-18)
- Python cannot edit a Widget Blueprint's tree (`WidgetTree` protected; `WidgetBlueprintFactory.RootWidgetClass`
  protected, a Python-made WBP has no root), and Blueprint cannot `Construct Object` a UWidget
  (`DontUseGenericSpawnObject`). Build the tree from transient widgets in editor Python (`unreal.new_object`,
  `add_child_to_vertical_box`, `add_child_to_canvas`, set properties), export each with an `AssetExportTask` +
  `unreal.ObjectExporterT3D()`, strip `ExportPath=`, concatenate: that is the Widget Designer's clipboard format. The
  tester pastes it into the empty Hierarchy (the first block, e.g. a Canvas Panel, becomes the root). Add
  `bIsVariable=True` to widgets another Blueprint reads (TextBlocks default to false, Sliders to true); read them
  with a variable get whose MemberParent is the widget class. Example: ImmersiveLooting `zonekit/tools/dev_panel.py`.
- Stalker 2's `PC` class is the player CHARACTER: `IsInputKeyDown`, `CreateWidget`'s Owning Player, input modes and
  `bShowMouseCursor` need `GetPlayerController(0)` (PlayerController), not a `PC` reference.

## Editor traps
- **Save before Compile** on big edits; a compiler crash loses unsaved work. Wait ~10 s after a save before cooking.
- After any asset rename: Compile every referencer (bytecode is stale until then) and re-check pins; use
  `tools/editor/move_asset.py`, which also deletes the redirector (a redirector in Content gets cooked).
- **Property Access nodes only inside AnimGraphs / transition rules**; in an event graph one crashed the compiler.
- The editor crashed when it auto-reopened an overridden `AnimBP_Player` at startup (compile-on-load before mod
  classes exist). Open such assets by hand; if a crash loop starts, delete the `OpenAssetsAtExit=` lines from
  `%LOCALAPPDATA%\Stalker2\Saved\Config\WindowsEditor\EditorPerProjectUserSettings.ini` (editor closed).
- Opening the pawn Blueprint once crashed while a modified `AnimBP_Player` sat in the same mod (the pawn editor
  previews the anim class); move the anim asset out temporarily if it recurs.
- **Overridden assets exist twice at runtime** (`/Game/...` and `/<Mod>/...`), and the editor redirects every `/Game`
  pick of an overridden asset to the mod path. Only the game-path object gets the game's runtime treatment (e.g. the
  player's rebinds), so load it by path string when it matters (`input.md`).
- **A pasted `0.0` on a function pin whose C++ default is non-zero comes back as the default** (e.g.
  `Montage_SetPlayRate.NewPlayRate` = 1.0); feed such values from a node output. Blueprint T3D exports also carry
  deleted nodes, so verify pin values in game (probe), not in an export.
- A pasted pure `K2Node_DynamicCast` (`bIsPureCast=True`) comes in as an exec cast; wire its exec pins.
- `Print String` is stripped in Shipping: trace with visible side effects or a dev-box probe (`diagnostics.md`).
- Anim notify / linked-layer pins: a Linked Anim Graph node only exposes an `In Pose` pin if the target's AnimGraph
  function has one; our pass-through ABP never offered it (dead end, `animation.md`).
