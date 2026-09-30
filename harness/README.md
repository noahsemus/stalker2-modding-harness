# harness/

Shared agent instructions, knowledge and tools for S.T.A.L.K.E.R. 2 Zone Kit mods. Start with
[AGENTS.md](AGENTS.md); knowledge is in [docs/](docs/). This folder is identical in every mod repo; see
[docs/harness-workflow.md](docs/harness-workflow.md) before changing it.

## Tools
Python = the kit's embedded interpreter `<kit>\Engine\Binaries\ThirdParty\Python3\Win64\python.exe`.
PowerShell tools default `-Mod` to `mod.json` "name". Paths: `config.json` defaults < machine settings `%LOCALAPPDATA%\stalker2-modding-harness\settings.json` (written by `setup.ps1`) < gitignored `harness/local.json`.

| Tool | Runs | Does |
|---|---|---|
| `tools/check_setup.ps1` | shell | read-only check of paths, Git, GitHub login, fork settings, editor remote Python; prints fixes |
| `tools/setup.ps1 [-Install] [-Fork]` | shell | does the automatable setup: finds the kit and game, writes the machine settings, installs Git / GitHub CLI, forks the harness, turns on editor remote Python |
| `tools/cook_and_install.ps1 [-Mod] [-Suffix N] [-NoInstall]` | shell | `GSCCookMod` (5-6 min), classifier-list sanity check + mirror, waits for the game to close, installs |
| `tools/install_paktest.ps1 [-Mod] [-Suffix N]` | shell, game closed | staged OverrideContent → `~mods\zzz_<Mod>_PakTest\zzz_<Mod>_<N>_P.*` (default 30), NewContent under its kit name |
| `tools/revert_paktest.ps1 [-Mod] [-Park]` | shell, game closed | removes (or parks outside `Content\Paks`) the dev test pak |
| `tools/mirror_from_kit.ps1 [-Mod]` | shell | kit plugin (`.uplugin`, `Content`, `Resources`) + classifier lists → repo |
| `tools/deploy_to_kit.ps1 [-Mod] [-Force]` | shell | repo → kit; refuses to clobber newer kit files |
| `tools/ue_exec.py <file\|code> [--arg K=V]` | shell → open editor | Python in the tester's editor via remote execution; prepends the prelude (`MOD`, `MOD_ROOT`, `UPLUGIN`, `SCRATCH`, `ARGS`) |
| `tools/run_headless.ps1 -Script f.py [-Arg K=V,..]` | shell → commandlet | same prelude, headless editor (~4.5 min); editor closed for asset moves |
| `tools/editor/duplicate_asset.py` | headless | `SRC` → `DST` duplicate (Blueprint graphs survive) |
| `tools/editor/move_asset.py` | headless, editor closed | rename with referencer fix-up, deletes the redirector |
| `tools/editor/set_bp_default.py` | either | one class-default value (`BP`, `PROP`, `VALUE`) |
| `tools/editor/dump_imc.py` | either | mapping-context rows, mappable names, modifiers, triggers → JSON |
| `tools/editor/export_t3d.py` | open editor | full T3D export of any asset (read Blueprints back) |
| `tools/editor/create_marker.py` | headless | permanent compatibility marker asset |
| `tools/t3d/bp_t3d.py`, `bp_graph.py` | library | write Blueprint paste text (nodes, pins, both-ended links, comment boxes) |
| `tools/t3d/t3d_lift.py` | library | lift nodes from an exported T3D into paste text |
| `tools/pak/zen_names.py <dir> [--imports] [--filter RE]` | shell | names / imports of cooked (Zen) packages |
| `tools/pak/dump_names.py <uasset>` | shell | FName table of an uncooked package (keys, actions, modifiers) |
| `tools/pak/extract_from_pak.py` | shell | single uncooked assets out of the kit's editor pak by index offset |
| `tools/pak/scan_mods.py <Name>...` | shell | which installed mod containers mention an asset, with mount order |
| `tools/make_release.py X.Y.Z [--downloads]` | shell | release zip from the last cook |
| `tools/new_mod.ps1`, `sync_harness.ps1`, `push_harness.ps1` | shell | harness lifecycle (`docs/harness-workflow.md`) |
| `probe/` | dev box | UE4SS C++/Lua probe examples and build notes |
