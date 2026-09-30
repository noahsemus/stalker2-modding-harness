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
4. They compile and save; read it back with `export_t3d.py` to verify (the export lists deleted-but-not-GC'd nodes
   too: trust each graph's `Nodes(n)` list).

Put `NodeComment` labels and comment boxes in the generated text (see `collaboration.md`). Keep mod-specific
generators in the mod's `zonekit/tools/gen_*.py`; lift reusable node builders into `bp_graph.py` here.

Blueprint "Float" variables are doubles. `BlueprintEditorLibrary.add_member_variable` adds variables from Python;
`reparent_blueprint` reparents; Blueprint graphs themselves cannot be authored from Python (only pasted).

## Editor Python
- **Remote execution** (Project Settings → Plugins → Python → Enable Remote Execution; not in Editor Preferences)
  lets `tools/ue_exec.py <file|code>` run scripts in the tester's open editor in seconds. The harness prelude gives
  scripts `MOD`, `MOD_ROOT`, `UPLUGIN`, `SCRATCH`, `ARGS`.
- In the live editor, `EditorAssetLibrary.duplicate_asset` and `AssetTools.duplicate_asset` return **None for /Game
  sources**; run duplication headless (`run_headless.ps1 tools/editor/duplicate_asset.py`) or edit existing mod
  assets in place.
- `unreal.new_object(cls, outer)` works for small sub-objects (e.g. `PlayerMappableKeySettings`). Setting properties
  on freshly created modifier/trigger objects fails with "cannot be edited on templates": **move** the real objects
  from a duplicated source instead (`rename(outer=...)`, see `input.md`).
- A SoftClassProperty only accepts a real class object from Python (`tools/editor/set_bp_default.py`).
- CDO flags such as `AutoReceiveInput = Player0` on an actor Blueprint can be set from Python.

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
- `Print String` is stripped in Shipping: trace with visible side effects or a dev-box probe (`diagnostics.md`).
- Anim notify / linked-layer pins: a Linked Anim Graph node only exposes an `In Pose` pin if the target's AnimGraph
  function has one; our pass-through ABP never offered it (dead end, `animation.md`).
