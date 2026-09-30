# Building {{MOD}} (Zone Kit pak)

For anyone who wants to rebuild, modify or extend the mod: what it changes, exactly how, and how to cook it.
Toolchain, cook rules and traps shared by all our mods are in [harness/docs/pipeline.md](harness/docs/pipeline.md)
and [harness/docs/blueprints.md](harness/docs/blueprints.md).

## 1. Prerequisites
- S.T.A.L.K.E.R. 2 Zone Kit (Epic Games Store), ~600 GB free. First launch compiles shaders for a long time.
- Git. No Python install needed (the kit ships 3.11).
- Paths: `harness/config.json`; run `harness\tools\setup.ps1` to detect yours.

## 2. What the mod is
A Zone Kit plain-mod plugin `{{MOD}}`.

| File (under `Content/`) | Kind | Container | What it does |
|---|---|---|---|
| _(none yet)_ | | | |

## 3. Build from the committed source
1. `powershell -File harness\tools\deploy_to_kit.ps1` (plugin + classifier lists into the kit).
2. Start the editor once and pick `{{MOD}}` in the toolbar mod selector (mounts the plugin).
3. `powershell -File harness\tools\cook_and_install.ps1` (cook, then install as `~mods\zzz_{{MOD}}_PakTest\`).
Release zips ship the override container as `zzz_{{MOD}}_20_P.*` and the NewContent container under the kit name.

## 4. The edits, asset by asset
_(every node, pin and setting, so each edit can be reproduced from this document alone)_

## 5. Traps specific to this mod
_(shared traps are in harness/docs/)_
