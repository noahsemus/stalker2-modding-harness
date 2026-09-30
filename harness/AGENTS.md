# Stalker 2 modding harness: agent instructions (shared by every mod)

For any AI coding agent (Claude Code, Codex, Gemini CLI, Copilot, Cursor, ...). Each mod repo's root `AGENTS.md`
sends the agent here first (`CLAUDE.md` / `GEMINI.md` are shims importing both). Everything under `harness/` is
**shared and owned upstream** (the public project, or the user's fork of it: `harness_remote_url`): the same copy lives
in every mod repo. Mod-specific facts go in the mod's own files (`AGENTS.md`, `PLAN.md`, `BUILD.md`,
`zonekit/README.md`).
Edit `harness/` only for knowledge that holds for any Stalker 2 mod, and then promote it the same session
(`docs/harness-workflow.md`). Never let a mod's copy drift.

The game is **S.T.A.L.K.E.R. 2: Heart of Chornobyl** (Unreal Engine 5.5, game patch 2.0.x). Mods are built in the
official **Zone Kit** (GSC's UE 5.5 mod editor) and ship as **paks only**. UE4SS is a dev-box diagnostic tool and
never ships.

## Session start
- **New user or new machine** (no machine settings file `%LOCALAPPDATA%\stalker2-modding-harness\settings.json`, or `check_setup.ps1` reports problems, or the user asks to be
  set up): follow `docs/setup.md`. Do every step yourself; the user only answers questions and clicks where a program
  insists on a human.
- **In a mod repo**: run `harness/tools/sync_harness.ps1` first (gets harness updates other mods promoted), then read
  the mod's `AGENTS.md` "Current state" so "where were we?" has an answer.
- **The user wants a new mod**: `docs/harness-workflow.md` § New mod (choose the names with them).

## Roles (read `docs/collaboration.md` before the first reply of a session)
- **The tester** (the person you work with: the user) plays the game, does the clicks and pastes in the Zone Kit editor, and
  decides scope, releases and when to stop. Assume they do not read code or run commands.
- **The agent** owns everything else: research in the kit, scripts, Blueprint paste text, cooks, installs, log and
  crash reading, mirroring assets into the repo, docs, commits they ask for, releases.
- Never hand the tester build/install commands or ask them to paste files or logs you can read yourself.
- Talk in game terms: which place, which keys, what success looks like, what a run must contain.

## Hard rules
1. **Kit first.** Grep the kit's dumps and cfgs (`docs/zonekit.md`) and ask the tester to open assets in the editor
   before any blind build/test cycle. Most `/Script/Stalker2` classes are native with no graph; look for the assets
   that USE them.
2. **One change per cook** (5-6 min), tested by the tester before the next. At the first regression, roll back to
   the last checkpoint. Don't bundle a cleanup with a behaviour change.
3. **No versions, candidate commits, tags or releases unless the tester says so.** Test builds stay uncommitted;
   harness/doc commits are fine. Releases only on "cut a release" (`docs/pipeline.md` § Release).
4. **Prove a diagnostic captures before asking for a run**, and say exactly what the run must contain
   (`docs/diagnostics.md`). The tester's patience is the scarce resource.
5. **Don't park or defer work on your own.** If stuck, say what blocks and ask; iterate until they say stop.
6. **Trust what the tester sees.** When data contradicts them, suspect the mod's own stalls or the probe first.
7. **Override as little as possible** (`docs/compatibility.md`): per asset the last-mounted pak wins outright, so
   every overridden asset is a conflict with every other mod touching it. Prefer NewContent hosts
   (`docs/runtime-host.md`) and cfg *patches*; never ship a whole-file `.cfg` override.
   Never override `BP_Stalker2Character`, `AnimBP_Player`, `AnimBP_player_bh` or `IMC_Exploration` without the
   tester's explicit decision after hearing the conflict cost.
8. **Canary.** Every test build of an input change keeps one extra, harmless key on a known action so
   "override not loaded" and "action vetoed natively" are distinguishable. Remove it for release.
9. **Checkpoints**: once the tester confirms a working state and agrees, commit it tagged with the cooked paks in
   `zonekit/builds/<checkpoint>/`. Mirror `.uasset`s from the kit into the repo after every editor save they report.
10. **After a release, remove the dev test pak** (`revert_paktest.ps1`) so they play on the Nexus/Vortex copy.

## Where things are
| Need | Read |
|---|---|
| How to work with the tester, instruction style, test runs | `docs/collaboration.md` |
| Kit layout, dumps, cfgs, what to grep, what to ask them to open | `docs/zonekit.md` |
| Plugin creation, classifier lists, cook rules, mount order, install, release | `docs/pipeline.md` |
| Blueprint paste text (T3D), reading graphs back, editor Python, editor traps | `docs/blueprints.md` |
| Input mapping contexts, rebinds, key sync | `docs/input.md` |
| Running Blueprint logic without overriding anything (ModWorldSubsystem + actor) | `docs/runtime-host.md` |
| Player animation, montages, anim layers, known crash families | `docs/animation.md` |
| Game `.cfg` data, patch files | `docs/config-files.md` |
| UE4SS probes, logs, crash dumps | `docs/diagnostics.md` |
| Other popular mods, shared assets, inspecting other paks, MCM | `docs/compatibility.md` |
| Verified game behaviour (native vetoes, flags, functions) | `docs/game-facts.md` |
| Setting up a new user's machine | `docs/setup.md` |
| New mod, syncing and promoting the harness | `docs/harness-workflow.md` |
| Tool list | `README.md` (this folder) |

## Tools in one line each (details in `README.md`)
`tools/cook_and_install.ps1` cook + install as dev pak · `install_paktest.ps1` / `revert_paktest.ps1` ·
`mirror_from_kit.ps1` kit → repo · `deploy_to_kit.ps1` repo → kit · `ue_exec.py` Python in the open editor ·
`run_headless.ps1` Python in a commandlet · `editor/*.py` asset helpers · `t3d/*.py` Blueprint paste text ·
`pak/*.py` read cooked/uncooked packages, scan installed mods · `make_release.py` release zip ·
`setup.ps1` / `check_setup.ps1` machine setup · `new_mod.ps1` / `sync_harness.ps1` / `push_harness.ps1` harness lifecycle.
All PowerShell tools default `-Mod` to `mod.json` "name". Per-user values (kit and game folders, GitHub account) are never in the repo: `harness/config.json` ships them empty, and they come from
the machine settings `%LOCALAPPDATA%\stalker2-modding-harness\settings.json` (written by `setup.ps1`, shared by every
repo on the PC) and, rarely, a gitignored `harness/local.json` in one repo. Python = the kit's embedded 3.11
(`<kit>\Engine\Binaries\ThirdParty\Python3\Win64\python.exe`); no separate Python install is needed.

## Keeping knowledge where it belongs
- A fact about the game, the kit, the pipeline, another mod, or how to work with the tester → `harness/docs/`,
  promoted with `push_harness.ps1` in the same session.
- A fact about this mod (what we tried, what each build showed) → the mod's `zonekit/README.md` log; the reproducible
  edit → the mod's `BUILD.md`; status → the mod's `AGENTS.md` "Current state" (one line per checkpoint).
- Whatever memory your agent tool keeps is per machine / per folder and does not travel. Put anything every mod
  needs here, not in tool memory.
