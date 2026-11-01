"""Unpack, inspect and repack S.T.A.L.K.E.R. 2 .sav files (docs/saves.md).

A .sav is a little-endian uint32 uncompressed size + one Oodle Kraken stream. The decompressed save ends with the
quest-node name table: uint16 count, then count x (uint16 length + chars, no NUL) up to EOF. Past 65,535 names the
count wraps and the save no longer loads.

    python s2sav.py list [dir]                      saves, newest first: time, size, name count, file
    python s2sav.py unpack <sav>... [-o dir]        write <file>.sav.raw (next to the save, or into dir)
    python s2sav.py names <sav|raw>... [--dump]     name-table count; --dump prints "index<TAB>name"
    python s2sav.py pack <raw> -o <sav>             compress a .raw back into a .sav (untested in game)
    python s2sav.py strings <sav|raw> [-n 6] [--grep RE] [--offsets]   ASCII + UTF-16LE text in file order
    python s2sav.py diff <a> <b> [-n 6] [--grep RE] text only in a ("- ") or only in b ("+ ")

Oodle: --oodle <path to oo2core_9_win64.dll>, else env OODLE_LIB, else the kit's
<kit>\\Engine\\Binaries\\DotNET\\AutomationTool\\oo2core_9_win64.dll (kit path from the harness settings).
Default saves dir: %LOCALAPPDATA%\\Stalker2\\Saved\\STEAM\\SaveGames\\Data. Linux / Proton: Oodle defaults to the kit's
liboo2corelinux64.so.9 (same folder); saves default to <prefix>/drive_c/users/steamuser/AppData/Local/Stalker2/Saved/
STEAM/SaveGames/Data with <prefix> = harness setting game_prefix, env S2_PROTON_PREFIX, or ~/.steam/steam/steamapps/compatdata/1643320/pfx.
Python 3.11+, stdlib only. Never writes into the saves folder unless you point -o there.
"""
import argparse
import ctypes
import datetime
import os
import re
import struct
import sys

TABLE_MARKER = b"GlassToy_14_Christmas\0\0"   # last bytes before the table in the saves checked (2026-10-31)
TABLE_WINDOW = 8 << 20                        # scan this far back from EOF when the marker is missing
KRAKEN, LEVEL_NORMAL = 8, 4
OODLE_REL = os.path.join("Engine", "Binaries", "DotNET", "AutomationTool",
                         "oo2core_9_win64.dll" if os.name == "nt" else "liboo2corelinux64.so.9")

_oodle = None


def oodle(path=None):
    global _oodle
    if _oodle:
        return _oodle
    path = path or os.environ.get("OODLE_LIB")
    if not path:
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
            from hconf import KIT  # noqa: E402
            path = os.path.join(KIT, OODLE_REL) if KIT else None
        except ImportError:
            path = None
    if not path or not os.path.exists(path):
        raise SystemExit(f"Oodle library not found ({path}); pass --oodle <oo2core_9_win64.dll>")
    lib = ctypes.CDLL(path)
    i64, i32, vp = ctypes.c_int64, ctypes.c_int, ctypes.c_void_p
    lib.OodleLZ_Decompress.restype = i64
    lib.OodleLZ_Decompress.argtypes = [vp, i64, vp, i64, i32, i32, i32, vp, i64, vp, vp, vp, i64, i32]
    lib.OodleLZ_Compress.restype = i64
    lib.OodleLZ_Compress.argtypes = [i32, vp, i64, vp, i32, vp, vp, vp, vp, i64]
    lib.OodleLZ_GetCompressedBufferSizeNeeded.restype = i64
    lib.OodleLZ_GetCompressedBufferSizeNeeded.argtypes = [i32, i64]
    _oodle = lib
    return lib


def decompress(sav):
    if len(sav) < 5:
        raise ValueError("file too short for a save")
    size = struct.unpack_from("<I", sav, 0)[0]
    src = ctypes.create_string_buffer(sav[4:], len(sav) - 4)
    out = ctypes.create_string_buffer(max(size, 1))
    got = oodle().OodleLZ_Decompress(src, len(sav) - 4, out, size, 1, 0, 0, None, 0, None, None, None, 0, 3)
    if got != size:
        raise ValueError(f"Oodle decompress failed: got {got}, header says {size}")
    return out.raw[:size]


def compress(raw, level=LEVEL_NORMAL):
    lib = oodle()
    cap = lib.OodleLZ_GetCompressedBufferSizeNeeded(KRAKEN, len(raw))
    src = ctypes.create_string_buffer(raw, len(raw))
    out = ctypes.create_string_buffer(cap)
    n = lib.OodleLZ_Compress(KRAKEN, src, len(raw), out, level, None, None, None, None, 0)
    if n <= 0:
        raise ValueError("Oodle compress failed")
    return struct.pack("<I", len(raw)) + out.raw[:n]


def load(path):
    data = open(path, "rb").read()
    return data if path.lower().endswith(".raw") else decompress(data)


def read_table_at(d, offset):
    """Names of the table whose uint16 count sits at offset, or None unless its entries end exactly at EOF."""
    if offset + 2 > len(d):
        return None
    count = struct.unpack_from("<H", d, offset)[0]
    names, p = [], offset + 2
    for _ in range(count):
        if p + 2 > len(d):
            return None
        ln = struct.unpack_from("<H", d, p)[0]
        if p + 2 + ln > len(d):
            return None
        names.append(d[p + 2:p + 2 + ln].decode("latin1").rstrip("\0"))
        p += 2 + ln
    return names if p == len(d) else None


def scan_table(d, window=TABLE_WINDOW):
    """Longest run of (uint16 len + chars) entries ending at EOF, preceded by its own count mod 65,536."""
    n, lo = len(d), max(0, len(d) - window)
    run = [-1] * (n - lo + 1)
    run[n - lo] = 0
    for p in range(n - 2, lo - 1, -1):
        e = p + 2 + (d[p] | (d[p + 1] << 8))
        if e <= n and run[e - lo] >= 0:
            run[p - lo] = run[e - lo] + 1
    best = None
    for p in range(lo + 2, n - 1):
        k = run[p - lo]
        if k > 0 and (d[p - 2] | (d[p - 1] << 8)) == (k & 0xFFFF) and (best is None or k > best[1]):
            best = (p - 2, k)
    if not best:
        return None
    names = read_table_at(d, best[0])
    return (best[0], names) if names is not None else None


def name_table(d):
    i = d.rfind(TABLE_MARKER)
    if i >= 0:
        names = read_table_at(d, i + len(TABLE_MARKER))
        if names is not None:
            return i + len(TABLE_MARKER), names
    return scan_table(d)


_ASCII = re.compile(rb"[\x20-\x7e\t]{%d,}")
_UTF16 = re.compile(rb"(?:[\x20-\x7e\t]\x00|[\x00-\xff]\x04){%d,}")   # printable ASCII or Cyrillic block


def strings(d, n=6):
    """(offset, 'a'|'u', text) in file order. Length prefixes stuck to the text are not trimmed."""
    out = [(m.start(), "a", m.group().decode("latin1")) for m in re.finditer(_ASCII.pattern % n, d)]
    rx = re.compile(_UTF16.pattern % n)
    for align in (0, 1):
        buf, pos = d[align:], 0
        while m := rx.search(buf, pos):
            if m.start() % 2:            # keep 2-byte alignment within this pass
                pos = m.start() + 1
                continue
            out.append((m.start() + align, "u", m.group().decode("utf-16-le", "replace")))
            pos = m.end()
    return sorted(out)


STEAM_APP_ID = "1643320"
SAVES_REL = os.path.join("Stalker2", "Saved", "STEAM", "SaveGames", "Data")


def default_dir():
    try:  # harness settings: game_prefix on Linux
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from hconf import GAME_USER_DIR  # noqa: E402
        if GAME_USER_DIR and (os.name == "nt" or os.environ.get("S2_PROTON_PREFIX") is None):
            if os.path.isdir(os.path.join(GAME_USER_DIR, "Saved")):
                return os.path.join(GAME_USER_DIR, "Saved", "STEAM", "SaveGames", "Data")
    except ImportError:
        pass
    if os.name == "nt":
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), SAVES_REL)
    prefix = os.environ.get("S2_PROTON_PREFIX") or os.path.expanduser(
        f"~/.steam/steam/steamapps/compatdata/{STEAM_APP_ID}/pfx")
    return os.path.join(prefix, "drive_c", "users", "steamuser", "AppData", "Local", SAVES_REL)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--oodle", help="path to oo2core_9_win64.dll")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("dir", nargs="?")
    s = sub.add_parser("unpack"); s.add_argument("files", nargs="+"); s.add_argument("-o", "--out")
    s = sub.add_parser("names"); s.add_argument("files", nargs="+"); s.add_argument("--dump", action="store_true")
    s = sub.add_parser("pack"); s.add_argument("raw"); s.add_argument("-o", "--out", required=True)
    s = sub.add_parser("strings"); s.add_argument("file"); s.add_argument("-n", type=int, default=6)
    s.add_argument("--grep"); s.add_argument("--offsets", action="store_true")
    s = sub.add_parser("diff"); s.add_argument("a"); s.add_argument("b"); s.add_argument("-n", type=int, default=6)
    s.add_argument("--grep")
    a = ap.parse_args()
    oodle(a.oodle)

    if a.cmd == "list":
        d = a.dir or default_dir()
        if not os.path.isdir(d):
            raise SystemExit(f"no saves folder at {d}; pass the folder (Linux: or set S2_PROTON_PREFIX)")
        files = sorted((os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".sav")),
                       key=os.path.getmtime, reverse=True)
        for f in files:
            t = name_table(load(f))
            when = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            print(f"{when}  {os.path.getsize(f):>10,}  {len(t[1]) if t else '?':>7}  {os.path.basename(f)}")
    elif a.cmd == "unpack":
        for f in a.files:
            dst = os.path.join(a.out, os.path.basename(f) + ".raw") if a.out else f + ".raw"
            if a.out:
                os.makedirs(a.out, exist_ok=True)
            raw = load(f)
            open(dst, "wb").write(raw)
            print(f"{dst}  {len(raw):,} bytes")
    elif a.cmd == "names":
        for f in a.files:
            t = name_table(load(f))
            if not t:
                print(f"{f}: no name table found"); continue
            print(f"{f}: {len(t[1]):,} names at offset 0x{t[0]:x}")
            if a.dump:
                for i, nm in enumerate(t[1]):
                    print(f"{i}\t{nm}")
    elif a.cmd == "pack":
        sav = compress(open(a.raw, "rb").read())
        open(a.out, "wb").write(sav)
        print(f"{a.out}  {len(sav):,} bytes")
    elif a.cmd == "strings":
        rx = re.compile(a.grep) if a.grep else None
        for off, enc, text in strings(load(a.file), a.n):
            if rx and not rx.search(text):
                continue
            print(f"{off:08x} {enc} {text}" if a.offsets else text)
    elif a.cmd == "diff":
        rx = re.compile(a.grep) if a.grep else None
        sa = {t for _, _, t in strings(load(a.a), a.n)}
        sb = {t for _, _, t in strings(load(a.b), a.n)}
        for prefix, items in (("- ", sa - sb), ("+ ", sb - sa)):
            for t in sorted(items):
                if not rx or rx.search(t):
                    print(prefix + t)


if __name__ == "__main__":
    main()
