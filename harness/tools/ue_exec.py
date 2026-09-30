"""Run a Python file or snippet inside the OPEN Zone Kit editor via UE remote execution (seconds, not minutes).

    <kit python> harness/tools/ue_exec.py <file.py | "code"> [--mod ModName] [--arg KEY=VALUE ...] [--no-prelude]

Needs Project Settings -> Plugins -> Python -> Enable Remote Execution (it is not in Editor Preferences).
The script gets the harness prelude first (MOD, MOD_ROOT, SHORT, UPLUGIN, KIT, REPO, SCRATCH; see hconf.prelude).
Known limit: EditorAssetLibrary/AssetTools.duplicate_asset return None here for /Game sources; use run_headless.ps1.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from hconf import KIT, prelude, require  # noqa: E402
require("kit")

sys.path.insert(0, os.path.join(KIT, "Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"))
import remote_execution as re_  # noqa: E402


def main():
    args = sys.argv[1:]
    mod = None
    if "--mod" in args:
        i = args.index("--mod"); mod = args[i + 1]; del args[i:i + 2]
    kv = {}
    while "--arg" in args:
        i = args.index("--arg"); k, _, v = args[i + 1].partition("="); kv[k] = v; del args[i:i + 2]
    use_prelude = "--no-prelude" not in args
    args = [a for a in args if a != "--no-prelude"]
    src = args[0]
    code = open(src, encoding="utf-8").read() if src.endswith(".py") else src
    if use_prelude:
        code = prelude(mod, kv) + code
    r = re_.RemoteExecution()
    r.start()
    deadline = time.time() + 5.0
    while time.time() < deadline and not r.remote_nodes:
        time.sleep(0.1)
    if not r.remote_nodes:
        print("NO_EDITOR_NODE (editor not open, or remote execution not enabled in Project Settings)")
        r.stop()
        sys.exit(2)
    r.open_command_connection(r.remote_nodes[0]["node_id"])
    res = r.run_command(code, exec_mode=re_.MODE_EXEC_FILE, raise_on_failure=False)
    for o in res.get("output", []):
        print(f"[{o['type']}] {o['output']}")
    ok = res.get("success", False)
    if not ok:
        print("FAILED:", res.get("result"))
    r.stop()
    sys.exit(0 if ok else 1)


main()
