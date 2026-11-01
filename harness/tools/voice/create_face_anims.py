"""Bake the lip-sync AnimSequences predicted by fit_lipsync.py and save them into the mod. Saves assets.

Paste into the open editor's Output Log (Python mode); this is the route it was verified with:
    PRED = r"<work>\\pred.json"; VANILLA = "/Game/_STALKER2/Animations/CharacterHead/Hubs/<Hub>/<speaker>"; DEST = "/<Mod>/Animations"; exec(open(r"<repo>\\harness\\tools\\voice\\create_face_anims.py").read())
(ue_exec.py --arg PRED=... also passes the inputs, but duplicate_asset of /Game sources returns None over remote
execution, see ue_exec.py.)
PRED: fit_lipsync.py's out_json. VANILLA: the folder dump_face_anim.py dumped (the base anims).
DEST: the mod's content folder. Optional: LIMIT (anims per run, default 10, 0 = all), LOG_DIR (default: PRED's folder).

Each anim is a copy of a vanilla face anim of the fitted speaker (SKEL_fac, same compression), set to 30 fps,
resized to the line's length, with the audio-driven curves and bone channels replaced by the predicted keys.
Saved as <DEST>/<speaker>/<EN|UA>/AS_FAC_<EN|UA>_<speaker>_<PhraseSID>. Runs in chunks: each run builds the next
LIMIT anims not saved yet (paste again until the log says "done; 0 left"); one run over everything slowed to a stall
after ~20 anims. Existing anims are skipped: delete one to rebuild it. Log: face_anims.txt.
"""
import json
import os
import unreal


def _inp(key, default=None):
    args = globals().get("ARGS") or {}
    return args.get(key, globals().get(key, default))


PRED, VANILLA, DEST = _inp("PRED"), _inp("VANILLA"), _inp("DEST")
if not (PRED and VANILLA and DEST):
    raise RuntimeError("create_face_anims.py: set PRED, VANILLA and DEST (see the header)")
LIMIT = int(_inp("LIMIT", 10))
OUT = _inp("LOG_DIR") or os.path.dirname(PRED)
FPS = 30  # fit_lipsync.py predicts at the speaker's median rate (~29.9 for the speakers tried): keyed at exactly 30
lib = unreal.AnimationLibrary
eal = unreal.EditorAssetLibrary
lines = []


def log(line):  # rewritten after every line, so a hang shows where it stopped
    lines.append(line)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "face_anims.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
def controller_of(anim):
    for get in (lambda: anim.controller, lambda: anim.get_controller(), lambda: anim.get_editor_property("controller")):
        try:
            c = get()
            if c:
                return c
        except Exception:
            pass
    return None


def frame_pose(anim, bone, frame):
    t = lib.get_bone_pose_for_frame(anim, bone, frame, False)
    r = t.rotation.rotator()
    return [t.translation.x, t.translation.y, t.translation.z, r.roll, r.pitch, r.yaw]


def build(name, a, fps):
    speaker, lang = name.split("_")[3], name.split("_")[2]
    src = f"{VANILLA}/{a['base_path']}" if "base_path" in a else f"{VANILLA}/{lang}/{a['base']}"
    dst = f"{DEST}/{speaker}/{lang}/{name}"
    if eal.does_asset_exist(dst):
        eal.delete_asset(dst)
    anim = eal.duplicate_asset(src, dst)
    n = a["frames"]
    ctrl = controller_of(anim)
    log(f"{name}: from {src}, {n} frames, controller {ctrl}")
    if ctrl:
        ctrl.open_bracket(unreal.Text("lipsync"), False)
    # Vanilla face anims are 60 fps (EN) or 30 fps (UA); the predictions are per 1/FPS frame, so the copy has to
    # run at FPS before it is resized, or an EN base plays the line at double speed.
    try:
        ctrl.set_frame_rate(unreal.FrameRate(FPS, 1), False)
        log(f"  frame rate {FPS}")
    except Exception as e:
        log(f"  set_frame_rate: {e!r}"[:300])
    # length: whichever resize call this engine build exposes
    for label, call in [("set_number_of_frames", lambda: ctrl.set_number_of_frames(unreal.FrameNumber(n - 1))),
                        ("resize_number_of_frames", lambda: ctrl.resize_number_of_frames(unreal.FrameNumber(n - 1), unreal.FrameNumber(0), unreal.FrameNumber(lib.get_num_frames(anim) - 1))),
                        ("set_play_length", lambda: ctrl.set_play_length(a["length"])),
                        ("resize_play_length", lambda: ctrl.resize_play_length(a["length"], 0.0, lib.get_sequence_length(anim)))]:
        try:
            call()
            log(f"  length via {label}: now {lib.get_num_frames(anim)} frames, {lib.get_sequence_length(anim):.3f}s")
            break
        except Exception as e:
            log(f"  {label}: {e!r}"[:300])
    times = [i / FPS for i in range(n)]
    curves = {k[6:]: v for k, v in a["tracks"].items() if k.startswith("curve:")}
    for c, values in curves.items():
        try:
            lib.remove_curve(anim, c, False)
        except Exception:
            pass
        try:
            lib.add_curve(anim, c, unreal.RawCurveTrackTypes.RCT_FLOAT, False)
            lib.add_float_curve_keys(anim, c, times, values)
        except Exception as e:
            log(f"  curve {c}: {e!r}"[:300])
    log(f"  curves set: {len(curves)}")
    bones = {}
    for k, v in a["tracks"].items():
        if k.startswith("bone:"):
            _, bone, dof = k.split(":")
            bones.setdefault(bone, {})[dof] = v
    dofs = ["tx", "ty", "tz", "roll", "pitch", "yaw"]
    ok = 0
    for bone, driven in bones.items():
        try:
            base = [frame_pose(anim, bone, min(f, lib.get_num_frames(anim) - 1)) for f in range(n)]
            for i, d in enumerate(dofs):
                if d in driven:
                    for f in range(n):
                        base[f][i] = driven[d][f]
            pos = [unreal.Vector(p[0], p[1], p[2]) for p in base]
            rot = [unreal.Rotator(roll=p[3], pitch=p[4], yaw=p[5]).quaternion() for p in base]
            scl = [unreal.Vector(1, 1, 1)] * n
            ctrl.set_bone_track_keys(bone, pos, rot, scl, False)
            ok += 1
        except Exception as e:
            log(f"  bone {bone}: {e!r}"[:300])
    log(f"  bones set: {ok}/{len(bones)}")
    if ctrl:
        ctrl.close_bracket(False)
    log(f"  saved: {eal.save_loaded_asset(anim, False)}")


try:
    with open(PRED) as fh:
        pred = json.load(fh)
    todo = [n for n in sorted(pred["anims"])
            if not eal.does_asset_exist(f"{DEST}/{n.split('_')[3]}/{n.split('_')[2]}/{n}")]
    names = todo[:LIMIT] if LIMIT else todo
    log(f"{len(pred['anims'])} anims in {PRED}, {len(todo)} not built yet, building {len(names)}; fps {pred['fps']}")
    for name in names:
        try:
            build(name, pred["anims"][name], pred["fps"])
        except Exception as e:
            log(f"{name} FAILED: {e!r}")
        unreal.SystemLibrary.collect_garbage()
    log(f"done; {len(todo) - len(names)} left")
except Exception as e:
    log(f"FAILED: {e!r}")
unreal.log(f"create_face_anims: {len(lines)} lines in {OUT}")
