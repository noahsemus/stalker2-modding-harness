"""Pull UNCOOKED game assets out of the kit's editor pak (FullEditor-WindowsModEditor.pak, ~388 GB) by index offset,
e.g. to read a vanilla asset's name table with dump_names.py without opening the editor.

1. Once, list the pak index (index only, slow; -Filter does not filter the listing):
       <kit>/Engine/Binaries/Win64/UnrealPak.exe "<kit>/Stalker2/Content/Paks/FullEditor-WindowsModEditor.pak" -List > <SCRATCH>/pak_index.txt
2.     <kit python> harness/tools/pak/extract_from_pak.py <SCRATCH>/pak_index.txt <out dir> InputMappingContexts/IMC_Dialog.uasset ...
   Each argument is a path suffix matched against the index. Only uncompressed entries are handled.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hconf import KIT, require  # noqa: E402
require("kit")

PAK = os.path.join(KIT, "Stalker2/Content/Paks/FullEditor-WindowsModEditor.pak")
MAGIC = bytes.fromhex("C1832A9E")
index_file, out_dir, want = sys.argv[1], sys.argv[2], sys.argv[3:]
idx = open(index_file, encoding="utf-8", errors="replace").read()
os.makedirs(out_dir, exist_ok=True)
with open(PAK, "rb") as f:
    for w in want:
        m = re.search(r'"([^"]*%s)" offset: (\d+), size: (\d+) bytes, sha1: [0-9A-F]+, compression: (\w+)' % re.escape(w), idx)
        if not m:
            print("MISSING", w); continue
        path, off, size, comp = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        f.seek(off); head = f.read(128)
        k = head.find(MAGIC)
        if comp != "None" or k < 0:
            print(f"SKIP {w}: compression={comp} magic_at={k}"); continue
        f.seek(off + k); data = f.read(size)
        out = os.path.join(out_dir, os.path.basename(path))
        open(out, "wb").write(data)
        print(f"OK {out} ({size} bytes)")
