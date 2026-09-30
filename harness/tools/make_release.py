"""Build the release zip of a mod from the last cook (run only when the tester says "cut a release").

    <kit python> harness/tools/make_release.py X.Y.Z [--readme <file>] [--downloads]

Layout: README.txt + the main plugin's paks (OverrideContent renamed zzz_<Mod>_<release suffix>_P.*, NewContent
under the kit's own name). With mod.json "optional_plugins" ([{"plugin": "...", "folder": "Optional-Foo"}]) the main
paks go under Main/ and each optional plugin's under its folder; the STALKER 2 Vortex extension then shows its file
chooser (more than three pak-type files in one archive), so no FOMOD is needed.
Written with zipfile (forward slashes); Compress-Archive writes backslash entries that some tools mis-extract.
Output: zonekit/builds/vX.Y.Z/<Mod>-vX.Y.Z.zip (+ a copy in Downloads with --downloads).
"""
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(__file__))
from hconf import CFG, KIT, MOD, REPO, require  # noqa: E402
require("kit")


def paks(plugin, suffix):
    base = os.path.join(KIT, "Stalker2", "SavedMods", "Staged", plugin, "Windows")
    out = []
    for kind, rename in (("OverrideContent", f"zzz_{plugin}_{suffix}_P"), ("NewContent", None)):
        d = os.path.join(base, kind, "Windows", "Stalker2", "Mods", plugin, "Content", "Paks", "Windows")
        stem = f"{plugin}Stalker2-Windows-{kind}"
        if os.path.exists(os.path.join(d, stem + ".utoc")):
            for ext in ("pak", "ucas", "utoc"):
                out.append((os.path.join(d, f"{stem}.{ext}"), f"{rename or stem}.{ext}"))
    if not out:
        raise SystemExit(f"nothing staged for {plugin}; cook it first")
    return out


args = sys.argv[1:]
version = args[0].lstrip("v")
readme = args[args.index("--readme") + 1] if "--readme" in args else os.path.join(REPO, "zonekit", "release", "README.txt")
name, suffix = MOD["name"], MOD.get("release_pak_suffix", 20)
opts = MOD.get("optional_plugins") or []
out_dir = os.path.join(REPO, "zonekit", "builds", f"v{version}")
os.makedirs(out_dir, exist_ok=True)
zpath = os.path.join(out_dir, f"{name}-v{version}.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    if os.path.exists(readme):
        z.write(readme, "README.txt")
    else:
        print("WARNING: no README.txt at", readme)
    main_dir = "Main/" if opts else ""
    for src, arc in paks(name, suffix):
        z.write(src, main_dir + arc)
    for o in opts:
        for src, arc in paks(o["plugin"], suffix):
            z.write(src, f'{o["folder"]}/{arc}')
for i in zipfile.ZipFile(zpath).infolist():
    print(f"  {i.file_size:>12}  {i.filename}")
print("->", zpath)
if "--downloads" in args:
    dl = os.path.expanduser(CFG.get("downloads", "~/Downloads"))
    shutil.copy2(zpath, dl)
    print("copied to", dl)
