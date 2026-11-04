"""Call Wwise Authoring's WAAPI over HTTP (see docs/audio-wwise.md). Stdlib only.

    python waapi.py <uri> [args-json] [--return id,name,path] [--port 8090] [--timeout 600]
    python waapi.py ak.wwise.core.getInfo
    python waapi.py ak.wwise.core.object.get "{\"from\":{\"ofType\":[\"Event\"]}}" --return id,name

Wwise (GUI or `WwiseConsole.exe waapi-server`) must be running; WAAPI HTTP listens on 8090 by
default. Prints the JSON reply; exits 1 when it is an `ak.wwise.error...` reply. `args-json` may
also be `@file.json` (handy for PowerShell, whose quoting mangles inline JSON).
"""
import argparse, json, sys, urllib.error, urllib.request


def call(uri, args=None, options=None, port=8090, timeout=600):
    body = json.dumps({"uri": uri, "args": args or {}, "options": options or {}}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/waapi", body,
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:     # WAAPI answers errors with a non-200 and a JSON body
        return json.loads(e.read() or b"{}")
    except urllib.error.URLError as e:
        sys.exit(f"WAAPI not reachable on port {port} ({e.reason}): is Wwise open with the project?")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("uri")
    ap.add_argument("args", nargs="?", default="{}")
    ap.add_argument("--return", dest="ret", help="comma-separated options.return fields")
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--timeout", type=float, default=600)
    a = ap.parse_args()
    raw = open(a.args[1:], encoding="utf-8").read() if a.args.startswith("@") else a.args
    opts = {"return": a.ret.split(",")} if a.ret else {}
    res = call(a.uri, json.loads(raw), opts, a.port, a.timeout)
    print(json.dumps(res, indent=1, ensure_ascii=False))
    sys.exit(1 if str(res.get("uri", "")).startswith("ak.wwise.error") else 0)


if __name__ == "__main__":
    main()
