"""List the phrase keys the editor sees in one DialogRuntimeData asset (`<ChainSID>_Voiceover` / `_FaceAnimation`).

Read-only. Fewer keys than the file was written with = the editor dropped them on load (unknown TextTool speaker,
docs/dialog-voiceover.md); the cook keeps only what the editor kept.

    <kit python> harness/tools/ue_exec.py harness/tools/voice/probe_voiceover_keys.py --arg PKG=/<Mod>/Dialogs/<ChainSID>_Voiceover [--arg RELOAD=1]
or paste into the editor's Output Log (Python mode):
    PKG = "/<Mod>/Dialogs/<ChainSID>_Voiceover"; exec(open(r"<repo>\\harness\\tools\\voice\\probe_voiceover_keys.py").read())

RELOAD=1 lists the keys, reloads the package from disk, lists them again (tells a stale editor copy apart).
Optional OUT=<folder>: also writes <OUT>\\vo_keys.txt.
"""
import os
import unreal


def _inp(key, default=None):
    args = globals().get("ARGS") or {}
    return args.get(key, globals().get(key, default))


PKG = _inp("PKG")
if not PKG:
    raise RuntimeError("probe_voiceover_keys.py: set PKG (see the header)")
RELOAD = str(_inp("RELOAD", "0")) in ("1", "true", "True")
OUT = _inp("OUT")
lines = []


def log(s):
    lines.append(str(s))
    print(s)


def dump(tag):
    obj = unreal.load_asset(PKG)
    if not obj:
        log(f"{tag}: {PKG} did not load")
        return
    log(f"{tag}: {obj.get_name()} class {obj.get_class().get_name()}")
    try:
        log(f"  AssetType {obj.get_editor_property('asset_type')}")
    except Exception as e:
        log(f"  asset_type: {e!r}"[:200])
    container = obj.get_editor_property("asset_container")
    log(f"  container class {container.get_class().get_name() if container else None}")
    if not container:
        return
    try:
        assets = container.get_editor_property("assets")
    except Exception as e:  # FaceAnimation containers use another layout
        log(f"  assets: {e!r}"[:300])
        return
    items = list(assets.items()) if hasattr(assets, "items") else list(assets)
    log(f"  {len(items)} keys")
    for it in items:
        if isinstance(it, tuple):
            k, v = it
            try:
                v = v.export_text()
            except Exception:
                pass
            log(f"    {k} -> {v}")
        else:
            log(f"    {it}")


try:
    dump("loaded")
    if RELOAD:
        pkg = unreal.find_package(PKG) if hasattr(unreal, "find_package") else unreal.load_package(PKG)
        unreal.EditorLoadingAndSavingUtils.reload_packages([pkg], unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
        dump("after reload")
except Exception as e:
    log(f"FAILED: {e!r}")
if OUT:
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "vo_keys.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
unreal.log(f"probe_voiceover_keys: {len(lines)} lines")
