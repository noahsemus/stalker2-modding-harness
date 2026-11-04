---
name: adversarial-review
description: Run an adversarial review loop on a generated test build (Blueprint paste text, generator scripts, asset builders) with a fresh subagent before the tester pastes or a cook runs. Only when the tester invokes it by name.
disable-model-invocation: true
---

# Adversarial review loop (only on the tester's request)

Use this **only when the tester asks for it** (types `/adversarial-review`, or says "run the adversarial review" /
"get a fresh agent to review it"). Never start it on your own initiative: each round costs minutes and tokens, and the
tester decides when a build is worth it. Agents without a skill system: same rule, run the steps below only when asked.

## When it runs
After a build is fully generated (paste text written, `check_paste.py` clean or unchanged, assets built in the kit) and
**before** the tester pastes or you cook. If the tester asked for the review together with a change ("fix everything in
one go and get a fresh agent to review it"), finish the change first, then review.

## Steps
1. **Freeze the baseline.** Copy the previous paste (the one the tester last pasted) to a temp file before regenerating,
   so the reviewer can diff old vs new (`%TEMP%\paste_<build>.txt`).
2. **Spawn a fresh reviewer** (a new subagent with no prior context; Claude Code: the Agent tool, general-purpose,
   in the background). Its brief must stand alone:
   - repo path, which files changed and how to find the changes (the build tag in comments, e.g. "v1.3.2 ab");
   - what the build is meant to do, item by item, in a few lines each (cause found, fix chosen);
   - **read-only**: no edits to the repo, no editor calls (`ue_exec.py`), no cook, no game; it may run the generator
     with the kit's Python into its own temp file and `check_paste.py` on it;
   - what to hunt (adapt to the build):
     - exec wiring: an exec output linked twice, re-linked pins that lost an old link, dead ends, paths that skip state
       later steps rely on (compare the new path with the existing path it was copied from);
     - pin names on casts / break-struct / function nodes against an existing working use in the same generator;
     - leftovers: references to names the build removed;
     - logic: every consumer of a variable whose meaning changed, the order of family / branch selection;
     - asset builders: notifies (HandIK on / off), additive type and reference frame, track sets, frame counts, slot;
   - the report format: numbered concrete defects (file:line, what breaks in game, how to fix, confidence), then a short
     list of what it checked and found fine. No style nits.
3. **Verify every finding yourself** before acting (read the code, regenerate, or check in the kit). Reject the wrong
   ones with a reason; fix the real ones.
4. **Regenerate** (paste text, `check_paste.py`, assets if a builder changed) and run **another round with a new fresh
   agent** (never re-use the previous reviewer: it would review its own suggestions). Brief it on the original goals
   plus what round N changed.
5. **Stop** when a round finds no defect that would break or visibly change the build in game, or after 3 rounds (then
   tell the tester what is still open). Do not loop on cosmetic findings.
6. **Record** in the mod's log (`zonekit/README.md`): rounds run, defects found and fixed, findings rejected and why,
   risks accepted (they go on the test list).
7. **Tell the tester** in game terms: review done (N rounds), what it caught, what the test run must cover because of
   it. Then hand over the paste / cook as usual.

## Notes
- The reviewer finds wiring and logic slips; it cannot see the game. A clean review is not a tested build: the tester's
  run still decides (`docs/collaboration.md`).
- Keep the editor claim (`coord.ps1`) while the review runs if you will rebuild assets after it.
