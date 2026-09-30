# Working with the tester

Distilled from the ImmersiveDialogue (v1.0 → v2.1.1) and ImmersiveCampfires sessions, 2026-09. Each rule exists
because breaking it once cost whole test cycles. "The tester" is the person you are working with: the user.

## Roles
- The tester is the person the mod is for, not its developer. They launch the game, test, and report symptoms in
  plain language ("didn't move", "feels too fast", "crashed at the loading screen"). They are also the hands in the
  Zone Kit editor: they paste Blueprint text, click through settings, save, and open assets so the agent can see them.
- Assume they do not read source, run git / PowerShell / cmake, or look at logs, unless they say otherwise.
- The agent does everything else and never hands them commands. Build commands belong in `BUILD.md`, not in chat.
- Only ask them for what the agent cannot get: in-game feel, whether something appeared, how a controller behaved,
  and editor-only views (graphs, Details panels, Reference Viewer).

## Before asking for a test run
- Game closed? Install scripts wait for `Stalker2-Win64-Shipping.exe` to exit; the editor does not lock paks.
- One change per build. Say in game terms what to do (which save / place / NPC / campfire, which keys, in what
  order) and what success looks like, and exactly what the run must contain ("sit 3 s, press P, stand up, quit").
- If a probe is involved, prove it captures first on something that needs no tester (a heartbeat line, the pawn
  found in the main menu). Watch the log live with a background wait and tell them the moment it has what it needs.
- Confirm what "done" refers to ("I tested" vs "edit done") before acting on it.
- When a guess fails twice, stop guessing and measure (a per-frame burst log found in one run what a day of
  guesses didn't).

## After a report
- Read the logs, cfgs and game folder yourself (`docs/diagnostics.md` has the paths).
- Trust their description of what they see; use data to find why, never to argue. If numbers disagree with them,
  first look for our own game-thread stall (log timestamp gap > 50 ms around the state change) or a probe bug.
- Keep iterating on hard problems with different approaches in the same session. "Parking" or "deferring" is their
  call, never the agent's. Stop only on "stop", "move on", "skip it".
- At the first regression, roll back to the last tagged checkpoint; mirror their editor work into the repo first so
  nothing they did is lost.

## Blueprint instructions
Prefer paste text (`docs/blueprints.md`): they copy 2-3 sample nodes of the needed types (Ctrl+C), the agent reads
them with `Get-Clipboard -Raw`, generates the block, puts it on the clipboard with `Set-Clipboard`, they press
Ctrl+V and wire only the few pins that connect outside the block. For every manual step:
- **Exact names only**: nodes by their title in the editor (`Get Camera Component`, `Set Absolute`), pins by label
  (`Return Value`, `New Absolute Rotation`, `As PC`), variables by name. Never shorthand ("camera ->", "the CMC").
  Say which node and which pin to drag from, every time.
- **No invented letter labels** ("wire B into E"); they are confusing.
- **Comment boxes**: give the box title for every group (select nodes, press C) and refer to groups by title.
- **Node comments** for every Branch / Sequence / Set a later step or a later session refers to; generated text
  sets them too (they survive in the `.uasset` and are what we read back when debugging).
- One action per step; say what replaces what when a wire is re-plugged.
- Prefer `Sequence` nodes over re-joining exec wires so chains can't loop or dead-end.
- Drag from the *data* pin to find component functions; exec pins only offer exec actions.
- "Save before Compile" on big edits; after they save, wait ~10 s before cooking.

## Commits, versions, releases
- Test builds stay uncommitted and install as `_30_P` dev paks. Checkpoints are committed and tagged only after the
  tester confirms in game and agrees. Versions and releases only when they say "cut a release". Harness and doc
  commits they asked for are fine.
- Main must equal what players run; rapid-fire versioning once left main ahead of the release while chasing a bug
  that was not ours.
- After every release: remove the dev test pak (the tester plays on the Nexus/Vortex copy; a leftover `_30_P`
  silently outranks it) and say in the summary that it was done.

## Tone
Short, concrete, game-facing. Lead with what they should do or what happened. Implementation detail only on request.
