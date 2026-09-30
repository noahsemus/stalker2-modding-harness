"""Which installed mod paks contain an asset? (conflict check: per asset, the last-mounted pak wins outright)

    <kit python> harness/tools/pak/scan_mods.py IMC_Exploration AnimBP_Player BP_Stalker2Character [--dir <folder>]

Byte-greps every .utoc / .pak / .ucas under ~mods (or --dir) for each name and prints the file, its mount priority
(3 + 100 * (N + 1) for a `_N_P` suffix, 3 for kit names without one) and a hint whether the hit is in a container
index (.utoc/.pak = the pak ships that package) or only in data (.ucas = something references it).
To see what a hit really is, extract it: <kit>/Engine/Binaries/Win64/UnrealPak.exe <x>.utoc -Extract <scratch dir>
and read names/imports with zen_names.py.
"""
import mmap
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hconf import MODS_DIR, require  # noqa: E402
if "--dir" not in sys.argv:
    require("game")


def priority(fname):
    m = re.search(r"_(\d+)_P\.(pak|utoc|ucas)$", fname, re.I)
    if m:
        return 3 + 100 * (int(m.group(1)) + 1)
    return 103 if re.search(r"_P\.(pak|utoc|ucas)$", fname, re.I) else 3


args = sys.argv[1:]
root = MODS_DIR
if "--dir" in args:
    i = args.index("--dir"); root = args[i + 1]; del args[i:i + 2]
names = [a.encode() for a in args]
hits = []
for dp, _, fs in os.walk(root):
    for f in fs:
        if not f.lower().endswith((".utoc", ".pak", ".ucas")):
            continue
        p = os.path.join(dp, f)
        try:
            with open(p, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                for n in names:
                    if mm.find(n) >= 0 or mm.find(n.decode().encode("utf-16-le")) >= 0:
                        hits.append((n.decode(), priority(f), os.path.relpath(p, root)))
        except (ValueError, OSError):
            pass
for n in args:
    rows = sorted((h for h in hits if h[0] == n), key=lambda h: -h[1])
    print(f"=== {n}: {len(rows)} file(s)")
    for _, pr, rel in rows:
        kind = "data only" if rel.lower().endswith(".ucas") else "index"
        print(f"   order {pr:>5}  {kind:9}  {rel}")
