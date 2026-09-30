"""Shared config for the harness Python tools that run OUTSIDE the editor (kit Python or any Python 3).

    from hconf import CFG, REPO, MOD, KIT, GAME, MODS_DIR

CFG = harness/config.json < machine settings (%LOCALAPPDATA%\stalker2-modding-harness\settings.json) < harness/local.json; MOD = mod.json (or {}).
Editor-side scripts do not import this: ue_exec.py / run_headless.ps1 prepend a prelude with the same values.
"""
import json
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


CFG = _read(os.path.join(REPO, "harness", "config.json"))
CFG.update(_read(os.path.join(os.environ.get("LOCALAPPDATA", ""), "stalker2-modding-harness", "settings.json")))
CFG.update(_read(os.path.join(REPO, "harness", "local.json")))
MOD = _read(os.path.join(REPO, "mod.json"))
KIT = CFG.get("kit", "")
GAME = os.path.join(CFG.get("game", ""), "Stalker2")
MODS_DIR = os.path.join(GAME, "Content", "Paks", "~mods")
SCRATCH = os.environ.get("HARNESS_SCRATCH") or os.path.join(os.environ.get("TEMP", "/tmp"), "stalker2-harness")


def prelude(mod_name=None, args=None):
    """Python source defining the values editor scripts rely on (MOD, MOD_ROOT, UPLUGIN, KIT, SCRATCH, REPO)
    plus ARGS, a dict of the caller's --arg KEY=VALUE pairs (scripts read e.g. ARGS["SRC"])."""
    name = mod_name or MOD.get("name", "")
    vals = {
        "MOD": name,
        "MOD_ROOT": "/" + name if name else "",
        "SHORT": MOD.get("short", name),
        "UPLUGIN": f"{KIT}/Stalker2/Mods/{name}/{name}.uplugin".replace("\\", "/"),
        "KIT": KIT.replace("\\", "/"),
        "REPO": REPO.replace("\\", "/"),
        "SCRATCH": SCRATCH.replace("\\", "/"),
        "ARGS": dict(args or {}),
    }
    return "".join(f"{k} = {v!r}\n" for k, v in vals.items()) + "# ---- end harness prelude ----\n"
