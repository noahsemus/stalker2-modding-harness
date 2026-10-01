r"""Disassemble the Blueprint bytecode of a cooked (Zen / IoStore) package: what another mod's Blueprint actually does.

Extract the container first (UnrealPak <mod>.utoc -Extract <dir>), then:
    python zen_kismet.py <dir>/<Asset>.uheader [--fn REGEX]
Prints every function export's bytecode as one statement per line with memory offsets (jump targets).
Object references: `exp:Name` = an export of the same package, `pkg:/Path#n` = an export of another package,
`script:<hash>` = a native class / function (unnamed in Zen; the temp variable it writes, `CallFunc_<Fn>_...`,
usually says which). Run with the kit's Python.
"""
import re, struct, sys

def name_batch(d, o):
    num = struct.unpack_from("<I", d, o)[0]; o += 4
    if num == 0:
        return []
    o += 4 + 8 + 8 * num
    hdrs = [struct.unpack_from(">H", d, o + 2 * i)[0] for i in range(num)]; o += 2 * num
    out = []
    for h in hdrs:
        ln = h & 0x7FFF
        if h & 0x8000:
            if o % 2: o += 1
            out.append(d[o:o + 2 * ln].decode("utf-16-le")); o += 2 * ln
        else:
            out.append(d[o:o + ln].decode("latin1")); o += ln
    return out

class Pkg:
    def __init__(self, hdr, body):
        self.h, self.b = hdr, body
        has_ver = struct.unpack_from("<I", hdr, 0)[0]
        o = 52
        if has_ver:
            o += 4 + 8 + 4
            n = struct.unpack_from("<i", hdr, o)[0]; o += 4 + 20 * n
        self.names = name_batch(hdr, o)
        imp_off, exp_off, bundle_off = struct.unpack_from("<iii", hdr, 28)
        self.pkgnames = name_batch(hdr, struct.unpack_from("<i", hdr, 48)[0])
        self.imports = [struct.unpack_from("<Q", hdr, imp_off + 8 * i)[0] for i in range((exp_off - imp_off) // 8)]
        self.exports = []
        for i in range((bundle_off - exp_off) // 72):
            e = exp_off + 72 * i
            off, size = struct.unpack_from("<QQ", hdr, e)
            ni, nn = struct.unpack_from("<II", hdr, e + 16)
            self.exports.append(dict(off=off, size=size, name=self.nm(ni, nn)))
        # export data is laid out in serial-offset order right after the header
        pos = 0
        for ex in sorted(self.exports, key=lambda x: x["off"]):
            ex["data"] = body[pos:pos + ex["size"]]; pos += ex["size"]

    def nm(self, i, n=0):
        i &= 0x3FFFFFFF
        s = self.names[i] if i < len(self.names) else f"?name{i}"
        return f"{s}_{n - 1}" if n else s

    def obj(self, idx):
        if idx == 0:
            return "null"
        if idx > 0:
            return "exp:" + self.exports[idx - 1]["name"]
        v = self.imports[-idx - 1]
        kind = v >> 62
        if kind == 1:
            return "script:%x" % (v & ((1 << 62) - 1))
        if kind == 2:
            p = (v >> 32) & 0x3FFFFFFF
            return "pkg:%s#%d" % (self.pkgnames[p] if p < len(self.pkgnames) else p, v & 0xFFFFFFFF)
        return "null"

class Dis:
    def __init__(self, pkg, data, start, storage, fname_mem):
        self.p, self.d, self.o, self.end = pkg, data, start, start + storage
        self.mem = 0; self.fn = fname_mem
    def u8(self): v = self.d[self.o]; self.o += 1; self.mem += 1; return v
    def u16(self): v = struct.unpack_from("<H", self.d, self.o)[0]; self.o += 2; self.mem += 2; return v
    def u32(self): v = struct.unpack_from("<I", self.d, self.o)[0]; self.o += 4; self.mem += 4; return v
    def i32(self): v = struct.unpack_from("<i", self.d, self.o)[0]; self.o += 4; self.mem += 4; return v
    def i64(self): v = struct.unpack_from("<q", self.d, self.o)[0]; self.o += 8; self.mem += 8; return v
    def f32(self): v = struct.unpack_from("<f", self.d, self.o)[0]; self.o += 4; self.mem += 4; return v
    def f64(self): v = struct.unpack_from("<d", self.d, self.o)[0]; self.o += 8; self.mem += 8; return v
    def name(self):
        i, n = struct.unpack_from("<II", self.d, self.o); self.o += 8; self.mem += self.fn
        return self.p.nm(i, n)
    def objref(self):
        v = struct.unpack_from("<i", self.d, self.o)[0]; self.o += 4; self.mem += 8
        return self.p.obj(v)
    def field(self):
        n = struct.unpack_from("<i", self.d, self.o)[0]; self.o += 4
        parts = []
        for _ in range(n):
            i, k = struct.unpack_from("<II", self.d, self.o); self.o += 8
            parts.append(self.p.nm(i, k))
        self.o += 4                      # owner
        self.mem += 8
        return ".".join(parts) if parts else "None"
    def cstr(self):
        e = self.d.index(b"\0", self.o); s = self.d[self.o:e].decode("latin1"); self.mem += e + 1 - self.o; self.o = e + 1; return s
    def wstr(self):
        e = self.o
        while self.d[e:e + 2] != b"\0\0": e += 2
        s = self.d[self.o:e].decode("utf-16-le"); self.mem += e + 2 - self.o; self.o = e + 2; return s

    def args(self, stop=0x16):
        out = []
        while self.d[self.o] != stop:
            out.append(self.expr())
        self.u8()
        return out

    def expr(self):
        t = self.u8()
        E = self.expr
        if t == 0x00: return self.field()
        if t == 0x01: return "this." + self.field()
        if t == 0x02: return "default." + self.field()
        if t == 0x48: return "out." + self.field()
        if t == 0x6C: return "sparse." + self.field()
        if t == 0x04: return "return " + E()
        if t == 0x06: return "goto %d" % self.u32()
        if t == 0x07: off = self.u32(); return "if not (%s) goto %d" % (E(), off)
        if t == 0x09: self.u16(); self.u8(); return "assert " + E()
        if t == 0x0B: return "nop"
        if t == 0x0C: self.i32(); return "nop"
        if t == 0x0F: self.field(); a = E(); b = E(); return f"{a} = {b}"
        if t == 0x11: f = self.field(); self.u8(); return "bitfield " + f
        if t in (0x12, 0x19, 0x1A):
            ob = E(); self.u32(); self.field(); return f"{ob}->{E()}"
        if t in (0x13, 0x2E, 0x52, 0x54, 0x55):
            c = self.objref(); return f"cast<{c}>({E()})"
        if t in (0x14, 0x5F, 0x60, 0x43, 0x44): a = E(); b = E(); return f"{a} = {b}"
        if t == 0x15: return "endparm"
        if t == 0x16: return ")"
        if t == 0x17: return "self"
        if t == 0x18: self.u32(); return E()
        if t in (0x1B, 0x45): n = self.name(); return f"{n}({', '.join(self.args())})"
        if t in (0x1C, 0x46, 0x68): f = self.objref(); return f"{f}({', '.join(self.args())})"
        if t == 0x63: f = self.objref(); return f"broadcast {f}({', '.join(self.args())})"
        if t == 0x1D: return str(self.i32())
        if t == 0x1E: return repr(self.f32())
        if t == 0x1F: return '"%s"' % self.cstr()
        if t == 0x34: return 'u"%s"' % self.wstr()
        if t == 0x20: return self.objref()
        if t == 0x21: return "'%s'" % self.name()
        if t in (0x22, 0x23): return "(%g,%g,%g)" % (self.f64(), self.f64(), self.f64())
        if t == 0x41: return "(%g,%g,%g)" % (self.f32(), self.f32(), self.f32())
        if t == 0x2B: return "xform(" + ",".join("%g" % self.f64() for _ in range(10)) + ")"
        if t in (0x24, 0x2C): return str(self.u8())
        if t == 0x25: return "0"
        if t == 0x26: return "1"
        if t == 0x27: return "true"
        if t == 0x28: return "false"
        if t == 0x29:
            k = self.u8()
            if k == 0: return 'text""'
            if k == 1: a = E(); E(); E(); return "text " + a
            if k in (2, 3): return "text " + E()
            if k == 4: self.objref(); E(); return "text " + E()
            return "text?"
        if t in (0x2A, 0x2D): return "None"
        if t == 0x2F:
            s = self.objref(); self.i32(); return f"{s}{{{', '.join(self.args(0x30))}}}"
        if t == 0x31: a = E(); return f"{a} = [{', '.join(self.args(0x32))}]"
        if t == 0x33: return "prop " + self.field()
        if t in (0x35, 0x36): return str(self.i64())
        if t == 0x37: return repr(self.f64())
        if t == 0x38: self.u8(); return E()
        if t in (0x39, 0x3B): a = E(); self.i32(); return f"{a} = {{{', '.join(self.args(0x3A if t == 0x39 else 0x3C))}}}"
        if t == 0x3D: self.field(); self.i32(); return "{" + ", ".join(self.args(0x3E)) + "}"
        if t == 0x3F: self.field(); self.field(); self.i32(); return "{" + ", ".join(self.args(0x40)) + "}"
        if t == 0x65: self.field(); self.i32(); return "[" + ", ".join(self.args(0x66)) + "]"
        if t == 0x42: f = self.field(); return f"{E()}.{f}"
        if t == 0x4B: return "delegate " + self.name()
        if t == 0x4C: return "push %d" % self.u32()
        if t == 0x4D: return "pop"
        if t == 0x4E: return "goto " + E()
        if t == 0x4F: return "pop if not " + E()
        if t in (0x50, 0x5A, 0x5E): return "trace"
        if t == 0x51: return E()
        if t == 0x53: return "end"
        if t == 0x5B: return "skip %d" % self.u32()
        if t in (0x5C, 0x62): a = E(); b = E(); return f"{a} {'+=' if t == 0x5C else '-='} {b}"
        if t == 0x5D: return "clear " + E()
        if t == 0x61: n = self.name(); a = E(); b = E(); return f"bind {a} = {b}.{n}"
        if t == 0x64: f = self.field(); return f"frame.{f} = {E()}"
        if t in (0x67, 0x6D): return E()
        if t == 0x69:
            n = self.u16(); self.u32(); idx = E(); cases = []
            for _ in range(n):
                cv = E(); self.u32(); cases.append(f"{cv}: {E()}")
            return f"switch({idx}){{{'; '.join(cases)}; default: {E()}}}"
        if t == 0x6A: self.u8(); return "instr"
        if t == 0x6B: a = E(); b = E(); return f"{a}[{b}]"
        raise ValueError("token 0x%02x at %d" % (t, self.o - 1))

def find_scripts(data):
    for i in range(0, len(data) - 9):
        mem, st = struct.unpack_from("<ii", data, i)
        if 0 < st and 0 < mem <= 4 * st + 64 and i + 8 + st <= len(data) and data[i + 8 + st - 1] == 0x53:
            yield i + 8, st, mem

def disassemble(p, data):
    """First (offset, storage size) candidate that parses exactly to its stated memory size."""
    best = None
    for start, st, mem in find_scripts(data):
        for fn in (12, 8):
            d = Dis(p, data, start, st, fn); out = []
            try:
                while d.o < d.end:
                    m = d.mem; out.append((m, d.expr()))
            except Exception as e:
                out.append((d.mem, f"!! {e}"))
                if best is None: best = (mem, out)
                continue
            if d.mem == mem and d.o == d.end:
                return mem, out
    return best

def main():
    a = sys.argv[1:]
    flt = None
    if "--fn" in a:
        k = a.index("--fn"); flt = re.compile(a[k + 1]); del a[k:k + 2]
    hp = a[0]
    p = Pkg(open(hp, "rb").read(), open(hp[:-len(".uheader")] + ".uexp", "rb").read())
    for ex in p.exports:
        if flt and not flt.search(ex["name"]):
            continue
        r = disassemble(p, ex["data"])
        if not r:
            continue
        mem, lines = r
        print(f"\n===== {ex['name']}  (bytecode {mem} B)")
        for m, s_ in lines:
            print(f"{m:6d}  {s_}")

main()
