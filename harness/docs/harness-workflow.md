# Harness lifecycle: new mods, syncing, promoting

One central harness (github.com/noahsemus/stalker2-modding-harness), one copy of `harness/` inside every mod repo,
never edited independently. Mod repos are created from the harness and keep it as a git remote named `harness`.

## Ownership
| Path | Owner | Changes by |
|---|---|---|
| `harness/**` | upstream harness | `push_harness.ps1` (promote) and `sync_harness.ps1` (pull) only |
| machine settings `%LOCALAPPDATA%\stalker2-modding-harness\settings.json` | this PC | `setup.ps1`; shared by every repo, never committed |
| `harness/local.json` | this repo on this PC | rare per-repo override (gitignored) |
| `AGENTS.md`, `CLAUDE.md` / `GEMINI.md` shims, `mod.json`, `PLAN.md`, `BUILD.md`, `README.md`, `zonekit/**`, `.gitignore` | the mod | normal commits |
| `.harness-sync` | tools | the upstream commit `harness/` was last synced to |

The mod's `AGENTS.md` tells any agent to read `harness/AGENTS.md` first; `CLAUDE.md` / `GEMINI.md` import both for
tools that read those names instead. So every session in every mod, with any agent, loads the shared rules.

## New mod
From the harness repo (or any mod repo):
```
powershell -File harness\tools\new_mod.ps1 -Name ImmersiveFoo -Short ImmFoo -RepoName stalker2-immersive-foo -Description "..."
```
Clones the harness into a sibling folder, renames the remote to `harness`, writes the templates
(`harness/templates/`), `mod.json`, empty classifier lists and `.harness-sync`, runs `CreatePlainMod.bat` and fixes
the `.uplugin`, mirrors the plugin into the repo, commits, and creates + pushes the public GitHub repo (`-Private`,
`-NoGitHub`, `-NoKit` to change that). Then the tester restarts the editor and picks the mod in the toolbar selector
once (creates the GameFeatureData); mirror again and commit.

Other users: `setup.ps1 -Fork` (see `setup.md`) forks the harness and records their GitHub name and fork URL in the
machine settings, so `new_mod.ps1` publishes under their account and promotes to their fork.

## Pull harness updates into a mod
`powershell -File harness\tools\sync_harness.ps1` at the start of a session (and whenever another mod promoted
something). It replaces `harness/` with upstream `main` (deleting files removed upstream), updates `.harness-sync`,
commits "Sync harness to <sha>". It refuses if `harness/` has changes that were never promoted.

"Update the harness" from the user means: if their harness clone has an `upstream` remote (a fork), first
`git pull upstream main` and `git push` in the harness clone (`harness_clone` in config), then `sync_harness.ps1` in
each mod repo.

## Promote a learning from a mod
1. Sync first.
2. Edit `harness/docs/*.md` (or a tool) in the mod repo. Write for any mod: game/kit/pipeline facts, tester workflow,
   tools. Mod-only history stays in the mod's log.
3. `powershell -File harness\tools\push_harness.ps1 -Message "docs: <what>"`: applies the diff to the local harness
   clone (`..\stalker2-modding-harness`, cloned if missing), commits, pushes, then syncs this repo.
Do it in the same session. A mod with unpromoted harness edits is exactly the fracture this setup prevents.

## Working in the harness repo itself
It has no `mod.json`; tools that need a mod take `-Mod`. Commit and push normally; then run `sync_harness.ps1` in
each active mod repo (or let the next session do it). Keep `harness/templates/` in step with how the mods are really
laid out.

## Adopting an existing mod repo
Add the remote, check out the harness, record the sync point, move the repo's generic tools/docs out (they now live
in `harness/`), move the mod's agent instructions into `AGENTS.md` (starting with "First read `harness/AGENTS.md`")
and add the two shims from `harness/templates/`:
```
git remote add harness https://github.com/noahsemus/stalker2-modding-harness.git
git fetch harness main
git checkout harness/main -- harness
git rev-parse harness/main > .harness-sync
```
Then add `mod.json` (see `templates/`), delete the repo's copies of tools now in `harness/tools/`, and keep only
mod-specific generators in `zonekit/tools/`.
