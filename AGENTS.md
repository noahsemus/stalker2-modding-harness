# Working in the harness repo itself

**First read `harness/AGENTS.md`**: the shared rules for every Stalker 2 mod. They apply here too.

This repo is the upstream of `harness/` for every Stalker 2 mod repo (see `harness/docs/harness-workflow.md`). There is
no mod here and no `mod.json`; tools that need a mod take `-Mod`.

- If the user is new or asks to be set up, follow `harness/docs/setup.md`. If they ask for a new mod, follow
  `harness/docs/harness-workflow.md` § New mod.
- Commit and push harness changes directly here, then run `harness\tools\sync_harness.ps1` in each active mod repo
  (sibling folders next to this one).
- Keep everything generic: no mod-specific history (that goes in the mod's `zonekit/README.md`), no user- or
  machine-specific values anywhere in the repo (paths and accounts belong in the machine settings `setup.ps1` writes), and nothing specific to one AI tool (instructions live in `AGENTS.md`
  files; `CLAUDE.md` / `GEMINI.md` are two-line shims that import them).
- The repo is public: nothing private (credentials, emails, personal files) in docs, tools or commit messages.
- Root `README.md` / `AGENTS.md` / shims / `.gitignore` belong to this repo only; mods get theirs from
  `harness/templates/`.
