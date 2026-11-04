"""Offline query tool for a (possibly stale) MSVC PDB, via llvm-pdbutil.

Needs `llvm-pdbutil` (ships with an LLVM install) on PATH. No DIA needed: `llvm-pdbutil pretty` requires DIA
and refuses to run without it, but `dump --types` uses LLVM's native reader and works everywhere.
Python 3.11+, stdlib only.

    python3 pdbq.py index  <pdb>              # one-time cache build (~2-4 min)
    python3 pdbq.py grep   <pdb> <regex>      # find type names
    python3 pdbq.py class  <pdb> <Name>       # layout + methods + vtable slots
    python3 pdbq.py enum   <pdb> <Name>       # enumerators and values
    python3 pdbq.py bases  <pdb> <Name>       # inheritance chain

Cache lives in ~/.cache/ue-pdb-index/<pdb-stem>.tsv and is built automatically.

READ docs/reverse-engineering.md (stale PDB section) FIRST. Names transfer across builds; offsets, sizeof,
enum values and vtable slot indices do NOT. The target binary is the source of
truth in both directions: this tool cannot see anything added after the PDB's
build, so nothing it fails to print is evidence of absence.
"""
import os, re, subprocess, sys, bisect

CACHE = os.path.expanduser('~/.cache/ue-pdb-index')
HDR = re.compile(r'^\s*(0x[0-9A-Fa-f]+) \| (LF_\w+)(?: \[size = \d+\])?(?: `(.*?)`)?\s*$')

# Only these record kinds are cached. LF_MFUNCTION/ARGLIST/METHODLIST/PROCEDURE/
# FIELDLIST are ~80% of a UE PDB's records and are never needed for lookups --
# field lists get re-queried live per class for ~1s. Dropping them took the cache
# for a 2.1 GB PDB from 2.1 GB to ~150 MB, so it fits comfortably in RAM.
KEEP = {'LF_CLASS', 'LF_STRUCTURE', 'LF_ENUM', 'LF_UNION',
        'LF_POINTER', 'LF_MODIFIER', 'LF_ARRAY', 'LF_BITFIELD'}
# ...and only these fragments of each record's detail text are worth keeping.
WANT = re.compile(r'forward ref \(-> 0x[0-9A-Fa-f]+\)|sizeof \d+|'
                  r'field list: 0x[0-9A-Fa-f]+|'
                  r'(?:referent|element type|pointee) = 0x[0-9A-Fa-f]+|\([\w :]+\)')


def cache_path(pdb):
    return os.path.join(CACHE, os.path.basename(pdb).replace('.pdb', '') + '.tsv')


def build(pdb):
    """Stream `dump --types` once, keep one compact row per record."""
    os.makedirs(CACHE, exist_ok=True)
    out = cache_path(pdb)
    tmp = out + '.part'
    p = subprocess.Popen(['llvm-pdbutil', 'dump', '--types', pdb],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, errors='replace', bufsize=1 << 20)
    n = 0
    with open(tmp, 'w') as f:
        def emit(idx, kind, name, detail):
            if kind not in KEEP:
                return 0
            keep = ' '.join(WANT.findall(' '.join(detail)))
            f.write('%s\t%s\t%s\t%s\n' % (idx, kind, name or '', keep))
            return 1

        idx = kind = name = None
        detail = []
        for line in p.stdout:
            m = HDR.match(line)
            if m:
                if idx:
                    n += emit(idx, kind, name, detail)
                idx, kind, name = m.group(1), m.group(2), m.group(3)
                detail = []
            elif idx and kind in KEEP and line.strip():
                detail.append(line.strip())
        if idx:
            n += emit(idx, kind, name, detail)
    p.wait()
    os.replace(tmp, out)
    sys.stderr.write('indexed %d records -> %s\n' % (n, out))
    return out


class Index:
    def __init__(self, pdb):
        self.pdb = pdb
        path = cache_path(pdb)
        if not os.path.exists(path):
            sys.stderr.write('building index (one-time, few minutes)...\n')
            path = build(pdb)
        self.by_idx = {}
        self.by_name = {}
        for line in open(path, errors='replace'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 4:
                continue
            idx, kind, name, detail = parts[0], parts[1], parts[2], parts[3]
            self.by_idx[idx] = (kind, name, detail)
            if name:
                fwd = 'forward ref' in detail
                prev = self.by_name.get(name)
                # a real definition always beats a forward reference
                if prev is None or (self.by_idx[prev][2].find('forward ref') >= 0 and not fwd):
                    self.by_name[name] = idx

    def rec(self, idx):
        return self.by_idx.get(idx, ('?', '', ''))

    def resolve(self, name):
        """Name -> definition index, following forward refs."""
        idx = self.by_name.get(name)
        if not idx:
            return None
        for _ in range(4):
            kind, nm, detail = self.rec(idx)
            m = re.search(r'forward ref \(-> (0x[0-9A-Fa-f]+)\)', detail)
            if not m:
                return idx
            idx = m.group(1)
        return idx

    def typename(self, idx, depth=0):
        """Human-readable name for a type index, resolving pointers/modifiers."""
        kind, name, detail = self.rec(idx)
        if name:
            return name
        if depth > 6:
            return idx
        m = re.search(r'(?:referent|element type|pointee) = (0x[0-9A-Fa-f]+)', detail)
        if m:
            inner = self.typename(m.group(1), depth + 1)
            if kind == 'LF_POINTER':
                return inner + '*'
            if kind == 'LF_MODIFIER':
                return 'const ' + inner
            if kind == 'LF_ARRAY':
                return inner + '[]'
            return inner
        m = re.search(r'\((\w[\w :]*)\)', detail)   # basic types print as (int) etc
        if m:
            return m.group(1)
        return '%s %s' % (kind, idx)

    def fieldlist(self, idx):
        """Raw expanded field list text for a class/struct/enum index."""
        kind, name, detail = self.rec(idx)
        m = re.search(r'field list: (0x[0-9A-Fa-f]+)', detail)
        if not m:
            return ''
        return subprocess.run(
            ['llvm-pdbutil', 'dump', '--types', '--type-index=' + m.group(1), self.pdb],
            capture_output=True, text=True, errors='replace').stdout


MEMBER = re.compile(r'LF_(?:STMEMBER|MEMBER) \[name = `(.+?)`, Type = (0x[0-9A-Fa-f]+), offset = (\d+)')
METHOD = re.compile(r'LF_ONEMETHOD \[name = `(.+?)`\]')
MATTRS = re.compile(r'vftable offset = (-?\d+), attrs = (.*)')
BCLASS = re.compile(r'type = (0x[0-9A-Fa-f]+), offset = (\d+), attrs')
ENUMER = re.compile(r'LF_ENUMERATE \[(.+?) = (-?\d+)\]')


def cmd_class(ix, name):
    idx = ix.resolve(name)
    if not idx:
        print('not found: ' + name)
        return
    kind, nm, detail = ix.rec(idx)
    sz = re.search(r'sizeof (\d+)', detail)
    print('%s  %s  index=%s  sizeof(PDB build)=%s' % (nm, kind, idx, sz.group(1) if sz else '?'))
    print('  !! sizeof/offsets are from the PDB build only -- re-derive for your target\n')
    txt = ix.fieldlist(idx)
    lines = txt.splitlines()

    bases = []
    for i, l in enumerate(lines):
        if 'LF_BCLASS' in l and i + 1 < len(lines):
            m = BCLASS.search(lines[i + 1])
            if m:
                bases.append((ix.typename(m.group(1)), int(m.group(2))))
    if bases:
        print('bases:')
        for b, o in bases:
            print('  %-50s @ %d' % (b, o))

    mem = [(int(m.group(3)), m.group(1), ix.typename(m.group(2)))
           for m in (MEMBER.search(l) for l in lines) if m]
    if mem:
        print('\nmembers (declaration order preserved; offsets advisory):')
        for off, n, t in sorted(mem):
            print('  %6d  %-42s %s' % (off, n, t))

    intro, override, plain = [], [], []
    for i, l in enumerate(lines):
        m = METHOD.search(l)
        if not m:
            continue
        a = MATTRS.search(lines[i + 1]) if i + 1 < len(lines) else None
        vo, attrs = (int(a.group(1)), a.group(2)) if a else (-1, '')
        # A vftable offset is only recorded for the class that INTRODUCES the
        # virtual. An override reuses the base's slot and reports -1, so
        # "vo < 0" does not mean non-virtual -- check the attrs too.
        if vo >= 0:
            intro.append((vo, m.group(1), attrs))
        elif 'virtual' in attrs:
            override.append((m.group(1), attrs))
        else:
            plain.append((m.group(1), attrs))
    if intro:
        print('\nvirtuals introduced by this class (byte offset / slot index):'
              '\n  slot indices shift across builds when a BASE class gains a virtual --'
              '\n  the contiguous ORDER of this run is what transfers, not the numbers:')
        for vo, n, a in sorted(intro):
            print('  +%-6d slot %-5d %-44s %s' % (vo, vo // 8, n, a))
    if override:
        print('\noverrides of inherited virtuals (occupy the base class slot):')
        for n, a in sorted(override):
            print('  %-46s %s' % (n, a))
    if plain:
        print('\nnon-virtual / static methods:')
        for n, a in sorted(plain):
            print('  %-46s %s' % (n, a))


def cmd_enum(ix, name):
    idx = ix.resolve(name)
    if not idx:
        print('not found: ' + name)
        return
    print('%s  index=%s' % (name, idx))
    print('  !! enumerator VALUES shift when entries are inserted/removed;'
          ' verify against the target\n')
    for m in ENUMER.finditer(ix.fieldlist(idx)):
        print('  %-46s = %s' % (m.group(1), m.group(2)))


def cmd_bases(ix, name):
    seen = set()
    cur = name
    while cur and cur not in seen:
        seen.add(cur)
        idx = ix.resolve(cur)
        if not idx:
            print('  (unresolved: %s)' % cur)
            return
        print(('  ' * len(seen)) + cur)
        txt = ix.fieldlist(idx)
        lines = txt.splitlines()
        nxt = None
        for i, l in enumerate(lines):
            if 'LF_BCLASS' in l and i + 1 < len(lines):
                m = BCLASS.search(lines[i + 1])
                if m and int(m.group(2)) == 0:      # primary base only
                    nxt = ix.typename(m.group(1))
                    break
        cur = nxt


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, pdb = sys.argv[1], sys.argv[2]
    if cmd == 'index':
        build(pdb)
        return 0
    ix = Index(pdb)
    arg = sys.argv[3] if len(sys.argv) > 3 else ''
    if cmd == 'grep':
        rx = re.compile(arg)
        for n in sorted(ix.by_name):
            if rx.search(n):
                k, _, d = ix.rec(ix.by_name[n])
                sz = re.search(r'sizeof (\d+)', d)
                print('%-70s %-14s %s' % (n, k, sz.group(1) if sz else ''))
    elif cmd == 'class':
        cmd_class(ix, arg)
    elif cmd == 'enum':
        cmd_enum(ix, arg)
    elif cmd == 'bases':
        cmd_bases(ix, arg)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
