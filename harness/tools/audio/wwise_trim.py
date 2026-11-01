"""Make a trial-licence-sized copy of a Zone Kit Wwise project (see docs/audio-wwise.md).

    python wwise_trim.py <SRC project dir> <DST project dir> --keep {GUID} [{GUID} ...] [--events REGEX]

Copies SRC to DST (DST is deleted first) and drops every AudioFileSource (and the owning Sound's
ActiveSourceList) except those under the objects whose GUIDs are given with --keep. Pass the GUID
of each Actor-Mixer / container your events play (a Work Unit's own GUID keeps nothing). Every
other object keeps its GUID and ShortID, so banks generated from the copy match the full project.

--events drops every Event whose name does not match REGEX, so auto-defined SoundBank generation
builds only those events' banks (seconds) and skips the ~55k others (about 30 min).
Stdlib only; reads and writes the .wwu work units as UTF-8 text.
"""
import argparse, re, shutil
from pathlib import Path

EVENT_TAG = re.compile(r'^(\s*)<Event Name="([^"]*)"[^>]*?(/?)>\s*$')
OPEN_TAG = re.compile(r'^(\s*)<(\w+)\s[^>]*ID="(\{[0-9A-Fa-f-]+\})"[^>]*?(/?)>\s*$')


def trim_file(f, keep, events):
    kept = dropped = dropped_events = 0
    out, keep_end, skip_end = [], None, None
    for line in f.read_text(encoding="utf-8").splitlines(keepends=True):
        if skip_end is not None:
            if line.startswith(skip_end):
                skip_end = None
            continue
        if keep_end is not None and line.startswith(keep_end):
            keep_end = None
        e = events and EVENT_TAG.match(line)
        if e and not events.search(e.group(2)):
            dropped_events += 1
            if not e.group(3):
                skip_end = f"{e.group(1)}</Event>"
            continue
        m = OPEN_TAG.match(line)
        if m and keep_end is None and m.group(3).upper() in keep and not m.group(4):
            keep_end = f"{m.group(1)}</{m.group(2)}>"
        stripped = line.lstrip()
        is_source = stripped.startswith("<AudioFileSource ")
        if keep_end is None and (is_source or stripped.startswith("<ActiveSourceList>")):
            if is_source:
                dropped += 1
            if not stripped.rstrip().endswith("/>"):
                indent = line[:len(line) - len(stripped)]
                skip_end = f"{indent}</{'AudioFileSource' if is_source else 'ActiveSourceList'}>"
            continue
        if keep_end is not None and is_source:
            kept += 1
        out.append(line)
    f.write_text("".join(out), encoding="utf-8")
    return kept, dropped, dropped_events


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--keep", nargs="+", required=True, help="GUIDs ({...}) whose sources stay")
    ap.add_argument("--events", help="regex; Events whose name does not match are dropped")
    a = ap.parse_args()
    src, dst = Path(a.src), Path(a.dst)
    keep = {k.upper() for k in a.keep}
    events = re.compile(a.events) if a.events else None
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".cache", "*.validationcache", "*.wsettings"))
    totals = [0, 0, 0]
    for f in dst.rglob("*.wwu"):
        for i, n in enumerate(trim_file(f, keep, events)):
            totals[i] += n
    print(f"kept {totals[0]} sources, dropped {totals[1]}, dropped {totals[2]} events")


if __name__ == "__main__":
    main()
