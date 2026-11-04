r"""Shared config for the harness Python tools that run OUTSIDE the editor (kit Python or any Python 3).

    from hconf import CFG, REPO, MOD, KIT, GAME, MODS_DIR

CFG = harness/config.json < machine settings < harness/local.json; MOD = mod.json (or {}).
Machine settings: %LOCALAPPDATA%\stalker2-modding-harness\settings.json on Windows,
$XDG_CONFIG_HOME (~/.config)/stalker2-modding-harness/settings.json on Linux (docs/linux-proton.md).
Editor-side scripts do not import this: ue_exec.py / run_headless.ps1 prepend a prelude with the same values. On Linux
the editor runs under Wine, so the prelude's paths are Wine paths (win_path).
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


ON_LINUX = sys.platform.startswith("linux")
if ON_LINUX:
    HARNESS_HOME = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "stalker2-modding-harness")
else:
    HARNESS_HOME = os.path.join(os.environ.get("LOCALAPPDATA", ""), "stalker2-modding-harness")

CFG = _read(os.path.join(REPO, "harness", "config.json"))
CFG.update(_read(os.path.join(HARNESS_HOME, "settings.json")))
CFG.update(_read(os.path.join(REPO, "harness", "local.json")))
if not CFG.get("harness_remote_url") and CFG.get("github_owner"):
    CFG["harness_remote_url"] = f"https://github.com/{CFG['github_owner']}/stalker2-modding-harness.git"
MOD = _read(os.path.join(REPO, "mod.json"))
KIT = CFG.get("kit", "")
GAME = os.path.join(CFG.get("game", ""), "Stalker2")
MODS_DIR = os.path.join(GAME, "Content", "Paks", "~mods")
SCRATCH = os.environ.get("HARNESS_SCRATCH") or os.path.join(os.environ.get("TEMP", "/tmp"), "stalker2-harness")
# The game's %LOCALAPPDATA%\Stalker2 (logs, crashes, saves); on Linux inside the game's Proton prefix.
GAME_USER_DIR = (os.path.join(CFG.get("game_prefix", ""), "drive_c", "users", "steamuser", "AppData", "Local", "Stalker2")
                 if ON_LINUX else os.path.join(os.environ.get("LOCALAPPDATA", ""), "Stalker2"))


def _wine_drives():
    """(target, letter) pairs of the kit prefix's dosdevices, longest target first (z: -> / is the fallback)."""
    d = os.path.join(CFG.get("kit_prefix", ""), "dosdevices")
    out = []
    if os.path.isdir(d):
        for name in os.listdir(d):
            link = os.path.join(d, name)
            if len(name) == 2 and name[1] == ":" and os.path.islink(link):
                out.append((os.path.normpath(os.path.join(d, os.readlink(link))).rstrip("/"), name.upper()))
    return sorted(out, key=lambda t: len(t[0]), reverse=True)


def win_path(p):
    """A path as a program inside Wine sees it (U:/games/x for /media/games/x when u: -> /media). On Windows, or for a
    path that is not an absolute Linux path, it is returned unchanged. Forward slashes; Unreal accepts them."""
    if not ON_LINUX or not p or not p.startswith("/"):
        return p
    for target, letter in _wine_drives():
        if target == "" or p == target or p.startswith(target + "/"):
            return letter + p[len(target):]
    return "Z:" + p


def prelude(mod_name=None, args=None):
    """Python source defining the values editor scripts rely on (MOD, MOD_ROOT, UPLUGIN, KIT, SCRATCH, REPO)
    plus ARGS, a dict of the caller's --arg KEY=VALUE pairs (scripts read e.g. ARGS["SRC"])."""
    name = mod_name or MOD.get("name", "")
    vals = {
        "MOD": name,
        "MOD_ROOT": "/" + name if name else "",
        "SHORT": MOD.get("short", name),
        "UPLUGIN": win_path(f"{KIT}/Stalker2/Mods/{name}/{name}.uplugin".replace("\\", "/")),
        "KIT": win_path(KIT.replace("\\", "/")),
        "REPO": win_path(REPO.replace("\\", "/")),
        "SCRATCH": win_path(SCRATCH.replace("\\", "/")),
        "ARGS": dict(args or {}),
    }
    return "".join(f"{k} = {v!r}\n" for k, v in vals.items()) + "# ---- end harness prelude ----\n"


def require(*keys):
    """Exit with a clear message when this PC has not been set up (config.json ships empty per-user values)."""
    missing = [k for k in keys if not CFG.get(k)]
    if missing:
        raise SystemExit(f"Not set up on this PC yet ({', '.join(missing)} missing). "
                         + ("Run: pwsh -File harness/tools/setup.ps1" if ON_LINUX else
                            "Run: powershell -ExecutionPolicy Bypass -File harness/tools/setup.ps1"))
