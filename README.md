# Stalker 2 modding harness

Make your own **S.T.A.L.K.E.R. 2: Heart of Chornobyl** mods with an AI coding agent, even if you have never modded
anything before.

This repository is a ready-made workspace for [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview)
(an AI assistant that can read files, run programs and write code on your computer). It holds:

- **The agent's instructions**: how to work with you, what to check before building anything, what never to do.
- **What we learned the hard way** while shipping real mods: how the game and GSC's official modding editor (the
  *Zone Kit*) behave, which approaches crash the game, and how to stay compatible with other popular mods.
- **Tools** that build your mod, install it into the game for testing, and package it for Nexus Mods.

Mods made with it: [Immersive Dialogue](https://github.com/noahsemus/stalker2-immersive-dialogue),
[Immersive Campfires](https://github.com/noahsemus/stalker2-immersive-campfires),
[Immersive Reloading](https://github.com/noahsemus/stalker2-immersive-reloading).

---

## Contents
1. [How it works](#1-how-it-works)
2. [What you need](#2-what-you-need)
3. [One-time setup](#3-one-time-setup)
4. [Create your first mod](#4-create-your-first-mod)
5. [Working on your mod](#5-working-on-your-mod)
6. [Testing in the game](#6-testing-in-the-game)
7. [Publishing your mod](#7-publishing-your-mod)
8. [Keeping the harness up to date](#8-keeping-the-harness-up-to-date)
9. [Words you will see](#9-words-you-will-see)
10. [When something goes wrong](#10-when-something-goes-wrong)
11. [What's in this repository](#11-whats-in-this-repository)

---

## 1. How it works

You and the agent split the work:

| You (the "tester") | The agent |
|---|---|
| Decide what the mod should do | Researches how the game does it today |
| Play the game and say what you see ("it worked", "nothing happened", "it crashed when I sat down") | Reads the game's logs and crash reports itself |
| Click and paste in the Zone Kit editor when asked (it gives you exact steps, or text to paste with Ctrl+V) | Writes the scripts and Blueprint logic, builds ("cooks") the mod, installs it into your game |
| Say when to publish | Packages the release, writes the notes, puts the zip in your Downloads folder |

You never have to write code or type build commands after setup. You talk to the agent in plain language.

Every mod gets its own folder and GitHub repository, created from this one. Each mod carries an identical copy of
the `harness` folder, so every lesson learned on one mod is available to all the others (see
[section 8](#8-keeping-the-harness-up-to-date)).

## 2. What you need

- **A Windows 10/11 PC** that runs the game.
- **S.T.A.L.K.E.R. 2: Heart of Chornobyl**, installed and patched to the latest version (the default paths assume
  Steam; other stores may work but are untested).
- **The S.T.A.L.K.E.R. 2 Zone Kit**, GSC's official mod editor, from the **Epic Games Store** (search for
  "S.T.A.L.K.E.R. 2 Zone Kit"). It is huge: plan for **about 600 GB of free disk space**, ideally on an SSD.
- **A Claude plan that includes Claude Code** (a paid Claude subscription or an Anthropic API account).
- **A free GitHub account** ([github.com/signup](https://github.com/signup)). Your mods are stored there.
- **A free Nexus Mods account** if you want to publish ([nexusmods.com](https://www.nexusmods.com)).
- An afternoon for setup (downloads and the editor's first start take a while).

## 3. One-time setup

You will type a few commands into **PowerShell**, Windows' command window. To open it: press the **Start** button,
type `PowerShell`, press **Enter**. Copy each command below, paste it into PowerShell with a right-click, and press
**Enter**. After installing a program, close PowerShell and open a new one so it notices the program.

### 3.1 Install the programs

1. **Git** (keeps the history of your files):
   ```powershell
   winget install --id Git.Git -e
   ```
2. **GitHub CLI** (lets the tools talk to GitHub):
   ```powershell
   winget install --id GitHub.cli -e
   ```
3. **Claude Code**: follow the Windows instructions at
   [docs.anthropic.com/en/docs/claude-code/setup](https://docs.anthropic.com/en/docs/claude-code/setup). If you use
   Visual Studio Code, the Claude Code extension works too.
4. Open a **new** PowerShell and tell Git who you are (use your own name and email):
   ```powershell
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
5. Log in to GitHub:
   ```powershell
   gh auth login
   ```
   Choose **GitHub.com**, then **HTTPS**, then **Login with a web browser**, and follow the prompts.

### 3.2 Install the Zone Kit and start it once

1. In the Epic Games launcher, install the **S.T.A.L.K.E.R. 2 Zone Kit**. Write down the folder you install it to
   (the harness assumes `G:\Epic Games\STALKER2ZoneKit`; you will correct that in 3.4 if yours differs).
2. Launch it from the Epic launcher. **The first start compiles shaders and takes a long time.** Let it finish.
3. Turn on remote Python (this is how the agent talks to the editor): in the editor's menu choose
   **Edit → Project Settings**, find **Plugins → Python** in the left list, tick **Enable Remote Execution**, then
   close and reopen the editor.

### 3.3 Get your own copy of the harness

In PowerShell, go to the folder where you want your mod projects to live (for example your Documents folder) and
"fork" this repository (makes your own copy on GitHub and downloads it):
```powershell
cd $HOME\Documents
gh repo fork noahsemus/stalker2-modding-harness --clone
cd stalker2-modding-harness
```
Keep all your mod folders next to this one (the tools create them there).

### 3.4 Make it yours

Open `harness\config.json` in Notepad (`notepad harness\config.json`) and change:
- `"github_owner"` to your GitHub user name,
- `"harness_remote_url"` to `https://github.com/<your user name>/stalker2-modding-harness.git`.

Then save that change to your fork:
```powershell
git commit -am "Point the harness at my GitHub account"
git push
```

If your Zone Kit or game is not in the default folder, create a file `harness\local.json` (it stays on your PC and
is never uploaded) with your real folders. Use forward slashes:
```json
{
  "kit": "D:/Epic Games/STALKER2ZoneKit",
  "game": "D:/SteamLibrary/steamapps/common/S.T.A.L.K.E.R. 2 Heart of Chornobyl"
}
```
Not sure where the game is? In Steam: right-click the game → **Manage** → **Browse local files**; use the folder
that opens (the one that contains the `Stalker2` folder).

Optional: the agent's instructions call the tester "Noah" (the author). Replace that name with yours in
`harness\CLAUDE.md` and `harness\docs\collaboration.md` if you like; it works either way.

> Shortcut: after 3.1 and 3.2 you can open Claude Code in this folder (see 5.1) and say *"Set this harness up for
> my GitHub account and my folders"*. It will do 3.4 for you.

### 3.5 Check everything

```powershell
powershell -ExecutionPolicy Bypass -File harness\tools\check_setup.ps1
```
Every line should say **OK** (open the Zone Kit editor first so the last check can run). Anything marked **FIX**
comes with the fix. Run it again until it says **All set.**

## 4. Create your first mod

1. Pick a name. You need three versions of it:
   - **Name**: one word, no spaces, capitals for each part, e.g. `BetterFlashlight`. This becomes the mod's name in
     the Zone Kit and in the files players install.
   - **Short**: a short prefix for the mod's own files, e.g. `BetFlash`.
   - **RepoName**: the GitHub repository name, lowercase with dashes, e.g. `stalker2-better-flashlight`.
2. Close the game. In PowerShell, inside the `stalker2-modding-harness` folder, run (with your names and a one-line
   description):
   ```powershell
   powershell -ExecutionPolicy Bypass -File harness\tools\new_mod.ps1 -Name BetterFlashlight -Short BetFlash -RepoName stalker2-better-flashlight -Description "A brighter, wider flashlight."
   ```
   This takes a minute or two. It creates the folder `..\stalker2-better-flashlight` with everything filled in,
   creates the mod inside the Zone Kit, and creates a **public** GitHub repository for it (add `-Private` to the
   command if you want it private).
3. **Restart the Zone Kit editor.** In its top toolbar there is a **mod selector** (a drop-down listing mods). Pick
   your new mod once. The editor needs this before it will load the mod.
4. Open your new mod folder in Claude Code (5.1) and say: *"I picked the mod in the Zone Kit selector. Mirror it into
   the repo and commit."*

## 5. Working on your mod

### 5.1 Start a session

Open PowerShell in your **mod's** folder (not the harness folder) and start Claude Code:
```powershell
cd $HOME\Documents\stalker2-better-flashlight
claude
```
(Or in VS Code: **File → Open Folder**, pick the mod folder, open the Claude Code panel.)

The agent automatically reads the harness instructions and your mod's files when it starts.

### 5.2 Your first conversation

Describe what you want in your own words, like you would to a friend who knows the game:

> *"I want the flashlight to be brighter and cover a wider area. Research how the game's flashlight works and write
> a plan in PLAN.md. Keep it compatible with other mods."*

The agent will research the game's data in the Zone Kit, write a plan, and ask you questions only you can answer.
Read the plan and tell it what you think. Then: *"Go ahead with step 1."*

### 5.3 A typical build-and-test round

1. The agent may ask you to **do something in the Zone Kit editor**: open an asset and take a screenshot, or paste
   prepared text into a Blueprint. It tells you exactly which window, which button and which name. For a paste, it
   has already put the text on your clipboard: click into the graph and press **Ctrl+V**, then **Compile** and
   **Save**. Tell it when you're done.
2. The agent **cooks** the mod (builds the game-ready files, about 5-6 minutes) and **installs** it into your game as
   a test copy. If the game is running, it waits until you close it.
3. It tells you **what to do in the game** and what success looks like ("load a save at night, turn on the
   flashlight, it should light the whole room").
4. You play and report back in plain words, including anything odd.
5. Repeat. One change per round, so when something breaks you always know what caused it.

When something works the way you want, say *"That works, save this as a checkpoint."* The agent saves the working
state (with the built files) so it can always go back to it.

### 5.4 Good habits

- Tell the agent what you **see**, not what you think the cause is. It reads the logs itself.
- If a test goes wrong, say exactly what you did ("I sat down, pressed P, the game froze").
- The agent never publishes or makes version numbers on its own; say when.
- Save in the Zone Kit before telling the agent you're done.
- Before starting a new session, it's fine to just say *"Where were we?"*: the mod's `CLAUDE.md` keeps the current
  state.

## 6. Testing in the game

- Test builds are installed to
  `<game folder>\Stalker2\Content\Paks\~mods\zzz_<YourMod>_PakTest\`. The game loads everything inside `~mods`.
- To play without your test build, ask the agent *"remove the test pak"* (or delete that folder with the game
  closed).
- If you also use a mod manager (Vortex), the test copy is named so it wins over a Vortex-installed copy of the same
  mod. Remove the test copy when you want to play the released version.
- The game must be closed before a new test build can be installed.

## 7. Publishing your mod

1. Play through everything in your plan's test list (keyboard, controller, with your other mods installed).
2. Tell the agent: *"Cut a release, version 1.0.0."* It removes test-only bits, rebuilds, saves the version on
   GitHub, writes player-friendly release notes, puts a ready-to-upload zip in your **Downloads** folder, and removes
   the test copy from your game.
3. On [nexusmods.com](https://www.nexusmods.com), go to the S.T.A.L.K.E.R. 2 section, choose **Upload a mod**, fill in
   the page (name, description, screenshots), and upload the zip from Downloads as the main file. Paste the release
   notes into the changelog. Give the mod ID to the agent so it can record it.

Players install the zip with Vortex or by unpacking it into `Stalker2\Content\Paks\~mods\`.

## 8. Keeping the harness up to date

Each mod has its own copy of the `harness` folder. Two tools keep all copies the same:

- **Get the latest harness** into a mod (the agent usually does this at the start of a session):
  ```powershell
  powershell -ExecutionPolicy Bypass -File harness\tools\sync_harness.ps1
  ```
- **Share a lesson** a mod taught you with all your other mods: ask the agent *"Promote what we learned about X to the
  harness."* It updates the central harness (your fork on GitHub) and the other mods pick it up next time they sync.

To get improvements from the original harness into your fork, run this in your `stalker2-modding-harness` folder
(`gh repo fork` set up the `upstream` link for you), then sync your mods as above:
```powershell
git pull upstream main
git push
``` Contributions back are welcome as
pull requests.

## 9. Words you will see

| Word | Meaning |
|---|---|
| **Zone Kit** | GSC's official mod editor for S.T.A.L.K.E.R. 2 (a version of Unreal Engine 5.5). |
| **Asset** | A game file inside the editor: a Blueprint, an animation, a texture, an input setting. |
| **Blueprint** | Unreal's visual scripting: boxes ("nodes") connected by wires. The agent writes them as text you paste. |
| **Override** | Replacing one of the game's own assets with an edited copy. Two mods overriding the same asset can't both work, so the agent avoids it. |
| **New content** | Assets that only your mod has (e.g. the mod's own logic). Can't clash with other mods. |
| **Cook** | Turning editor assets into the compact files the game loads. Takes 5-6 minutes. |
| **Pak** | The finished mod files (`.pak`, `.ucas`, `.utoc`, always together) that go into `~mods`. |
| **`~mods`** | The folder inside the game where mods are installed. |
| **Load order** | When two mods change the same thing, the one loaded last wins. File names like `_20_P` set the order. |
| **cfg / cfg patch** | The game's text data files (damage, prices, speeds). A patch changes single values without replacing the whole file. |
| **UE4SS / probe** | A separate tool the agent may use on your PC to look inside the running game while testing. Never part of a published mod. |
| **Repository (repo)** | A project folder whose history is saved with Git and uploaded to GitHub. |
| **Fork** | Your own copy of someone else's repository. |
| **Checkpoint** | A saved, known-good state of your mod the agent can return to. |
| **MCM** | Mod Configuration Menu, a popular community mod that adds an in-game settings screen for other mods. |

## 10. When something goes wrong

| Problem | What to do |
|---|---|
| PowerShell says "running scripts is disabled" | Use the commands exactly as written here, with `powershell -ExecutionPolicy Bypass -File ...`. |
| `winget` is not recognised | Install "App Installer" from the Microsoft Store, then open a new PowerShell. |
| `check_setup` says a path is wrong | Create or fix `harness\local.json` (3.4). |
| The editor doesn't show your mod in the selector | Close and reopen the editor; new mods only appear after a restart. |
| "A conflicting instance of AutomationTool is already running" | Another build is running (maybe another mod's). The tools wait for it; just let it finish. |
| The mod does nothing in the game | Tell the agent exactly what you did. It checks the game's log to see whether the mod loaded and whether another mod overrides the same thing. |
| The game crashes | Tell the agent when it crashed and what you were doing. It reads the crash reports itself. |
| The editor crashes every time it starts | Tell the agent; there is a known fix (the editor reopening a broken asset at startup). |
| The game updated and the mod broke | Update the Zone Kit in the Epic launcher too, then ask the agent to rebuild the mod. |
| You want to undo everything since the last good state | *"Roll back to the last checkpoint."* |

## 11. What's in this repository

- [harness/CLAUDE.md](harness/CLAUDE.md): the agent's standing instructions (every mod's `CLAUDE.md` loads it).
- [harness/docs/](harness/docs/): the knowledge base: working with the tester, the Zone Kit as a research tool, the
  build/install/release pipeline, Blueprint paste text, input and key bindings, running logic without replacing game
  files, animation, cfg data, diagnostics, compatibility with popular mods, verified game behaviour, and how the
  harness itself is kept in sync.
- [harness/tools/](harness/README.md): the tools (setup check, new mod, cook and install, editor scripting, package
  readers, installed-mod conflict scan, release zips, harness sync).
- [harness/templates/](harness/templates/): the starting files of every new mod.

## License
MIT (see [LICENSE](LICENSE)). S.T.A.L.K.E.R. 2 and its assets belong to GSC Game World; this repository contains no
game files. Mods you make are yours; check GSC's modding terms and Nexus Mods' rules before publishing.
