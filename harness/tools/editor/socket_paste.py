"""Print a skeleton's sockets as the Mod Editor's socket clipboard text (select a bone, Ctrl+V).

    python socket_paste.py <SKEL.uasset> [--baseline <vanilla SKEL.uasset>] [--out <file>]

With --baseline, only sockets whose name is missing from the baseline are printed: pass the
vanilla checkout to recover what a mod (or an older copy of the asset) added. Reads uncooked
editor packages in both property tag formats: legacy (FileVersionUE5 < 1012, e.g. 1008 from the
pre-2.0 kit) and complete type names (1012+, the 2.0 kit writes 1013). Stdlib only.
"""
import argparse, struct, sys

TAG = 0x9E2A83C1
UE5_SOFTOBJECTPATH_LIST = 1008
UE5_COMPLETE_TYPE_NAME = 1012
F_ARRAY_INDEX, F_GUID, F_EXT, F_NATIVE, F_BOOL_TRUE = 1, 2, 4, 8, 16


class R:
    def __init__(self, d, o=0):
        self.d, self.o = d, o

    def i32(self):
        self.o += 4
        return struct.unpack_from("<i", self.d, self.o - 4)[0]

    def u32(self):
        self.o += 4
        return struct.unpack_from("<I", self.d, self.o - 4)[0]

    def i64(self):
        self.o += 8
        return struct.unpack_from("<q", self.d, self.o - 8)[0]

    def u8(self):
        self.o += 1
        return self.d[self.o - 1]

    def fstring(self):
        n = self.i32()
        if n < 0:
            s = self.d[self.o:self.o - 2 * n].decode("utf-16-le"); self.o += -2 * n
        else:
            s = self.d[self.o:self.o + n].decode("utf-8", "replace"); self.o += n
        return s.rstrip("\0")

    def name(self, names):
        i, n = self.u32(), self.u32()
        return f"{names[i]}_{n - 1}" if n else names[i]


def parse(path):
    d = open(path, "rb").read()
    r = R(d)
    if r.u32() != TAG:
        sys.exit(f"{path}: not an uncooked .uasset")
    legacy = r.i32()
    if legacy != -4:
        r.i32()                                  # LegacyUE3Version
    r.i32()                                      # FileVersionUE4
    ue5 = r.i32() if legacy <= -8 else 0
    r.i32()                                      # licensee
    n = r.i32()
    r.o += 20 * n                                # custom versions
    r.i32()                                      # TotalHeaderSize
    r.fstring()                                  # package name
    r.u32()                                      # package flags
    name_count, name_off = r.i32(), r.i32()
    if ue5 >= UE5_SOFTOBJECTPATH_LIST:
        r.i32(); r.i32()                         # SoftObjectPaths count/offset
    r.fstring()                                  # LocalizationId
    r.i32(); r.i32()                             # gatherable text
    exp_count, exp_off = r.i32(), r.i32()
    imp_count, imp_off = r.i32(), r.i32()
    depends_off = r.i32()

    r.o, names = name_off, []
    for _ in range(name_count):
        names.append(r.fstring()); r.o += 4      # two uint16 hashes

    imports = []
    stride = (exp_off - imp_off) // imp_count if imp_count else 0
    for i in range(imp_count):
        r.o = imp_off + i * stride
        r.name(names); r.name(names); r.i32()    # class package, class name, outer
        imports.append(r.name(names))            # object name (an export's class is an import)

    exports = []
    stride = (depends_off - exp_off) // exp_count if exp_count else 0
    for i in range(exp_count):
        r.o = exp_off + i * stride
        cls = r.i32(); r.i32(); r.i32(); r.i32() # class, super, template, outer
        obj = r.name(names)
        r.u32()                                  # object flags
        size, off = r.i64(), r.i64()
        cname = imports[-cls - 1] if cls < 0 else None
        exports.append((obj, cname, off, size))
    return d, ue5, names, exports


def triple(d, at):
    return list(struct.unpack_from("<3d", d, at))


def props_modern(d, names, start, end):
    """Complete-type-name tags (UE5 1012+). Vector/Rotator are natively serialised: 3 doubles."""
    r, p = R(d, start + 1), {}                   # +1: serialization control extensions byte

    def type_name():
        n = r.name(names)
        params = [type_name() for _ in range(r.u32())]
        return n, params

    while r.o < end:
        n = r.name(names)
        if n == "None":
            break
        t, params = type_name()
        size, flags = r.i32(), r.u8()
        if flags & F_ARRAY_INDEX:
            r.i32()
        if flags & F_GUID:
            r.o += 16
        if flags & F_EXT:
            ext = r.u8()
            if ext & 1:
                r.o += 2
        if t == "BoolProperty" and size == 0:
            p[n] = bool(flags & F_BOOL_TRUE)
            continue
        at = r.o
        if t == "NameProperty":
            p[n] = r.name(names)
        elif t == "StructProperty" and params and params[0][0] in ("Vector", "Rotator") and size == 24:
            p[n] = triple(d, at)
        r.o = at + size
    return p


def props_legacy(d, names, start, end):
    """Legacy tags: Name, Type, Size, ArrayIndex, type-specific header, HasGuid."""
    r, p = R(d, start), {}
    while r.o < end:
        n = r.name(names)
        if n == "None":
            break
        t, size = r.name(names), r.i32()
        r.i32()                                  # ArrayIndex
        struct_name = ""
        if t == "StructProperty":
            struct_name = r.name(names); r.o += 16
        elif t == "BoolProperty":
            p[n] = r.u8()
        elif t in ("ByteProperty", "EnumProperty", "ArrayProperty", "SetProperty"):
            r.name(names)
        if r.u8():
            r.o += 16                            # property GUID
        at = r.o
        if t == "NameProperty":
            p[n] = r.name(names)
        elif struct_name in ("Vector", "Rotator"):
            p[n] = triple(d, at)
        r.o = at + size
    return p


def sockets(path):
    d, ue5, names, exports = parse(path)
    read = props_modern if ue5 >= UE5_COMPLETE_TYPE_NAME else props_legacy
    out = []
    for obj, cname, off, size in exports:
        if cname != "SkeletalMeshSocket":
            continue
        p = read(d, names, off, off + size)
        out.append(dict(object=obj, SocketName=p.get("SocketName"), BoneName=p.get("BoneName"),
                        loc=p.get("RelativeLocation", [0, 0, 0]),
                        rot=p.get("RelativeRotation", [0, 0, 0]),   # serialised Pitch, Yaw, Roll
                        scale=p.get("RelativeScale", [1, 1, 1])))
    return out


def f(x):
    s = f"{round(x, 6):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("skeleton")
    ap.add_argument("--baseline")
    ap.add_argument("--out", help="write here (UTF-8) instead of stdout")
    a = ap.parse_args()
    skip = {s["SocketName"] for s in sockets(a.baseline)} if a.baseline else set()
    socks = [s for s in sockets(a.skeleton) if s["SocketName"] not in skip]
    v = lambda t: f"(X={f(t[0])},Y={f(t[1])},Z={f(t[2])})"
    lines = ["SocketCopyPasteBuffer", f"NumSockets={len(socks)}"]
    for s in socks:
        lines += ["IsOnSkeleton=1",
                  f'Begin Object Class=/Script/Engine.SkeletalMeshSocket Name="{s["object"]}"',
                  f'   SocketName="{s["SocketName"]}"',
                  f'   BoneName="{s["BoneName"]}"',
                  f"   RelativeLocation={v(s['loc'])}",
                  f"   RelativeRotation=(Pitch={f(s['rot'][0])},Yaw={f(s['rot'][1])},Roll={f(s['rot'][2])})",
                  f"   RelativeScale={v(s['scale'])}",
                  "End Object"]
    text = "\n".join(lines) + "\n"
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
