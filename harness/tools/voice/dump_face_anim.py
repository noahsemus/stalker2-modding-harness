"""Dump one vanilla speaker's face anims (AS_FAC_*: float curves + per-frame bone transforms) to JSON. Read-only.

Input for fit_lipsync.py. Run in the open editor:
    <kit python> harness/tools/ue_exec.py harness/tools/voice/dump_face_anim.py \\
        --arg VANILLA=/Game/_STALKER2/Animations/CharacterHead/Hubs/<Hub>/<speaker> --arg OUT=<work>\\facedump
or paste into the Output Log (Python mode):
    VANILLA = "/Game/.../<speaker>"; OUT = r"<work>\\facedump"; exec(open(r"<repo>\\harness\\tools\\voice\\dump_face_anim.py").read())
VANILLA: content folder holding the speaker's AS_FAC_* anims (searched recursively, EN and UA).
"""
import json
import os
import unreal


def _inp(key, default=None):
    args = globals().get("ARGS") or {}
    return args.get(key, globals().get(key, default))


VANILLA, OUT = _inp("VANILLA"), _inp("OUT")
if not VANILLA or not OUT:
    raise RuntimeError("dump_face_anim.py: set VANILLA and OUT (see the header)")
lib = unreal.AnimationLibrary
NAMES = sorted(
    str(a.package_name)[len(VANILLA) + 1:]
    for a in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(VANILLA, recursive=True)
    if str(a.asset_name).startswith("AS_FAC_")
)
unreal.log(f"[FaceDump] {len(NAMES)} anims under {VANILLA}")


def tr(t):
    r = t.rotation.rotator()
    return [round(v, 4) for v in (t.translation.x, t.translation.y, t.translation.z, r.roll, r.pitch, r.yaw)]


os.makedirs(OUT, exist_ok=True)
for name in NAMES:
    anim = unreal.load_asset(f"{VANILLA}/{name}")
    if not anim:
        unreal.log_warning(f"[FaceDump] missing {name}")
        continue
    frames = lib.get_num_frames(anim)
    out = {
        "name": name,
        "length": lib.get_sequence_length(anim),
        "frames": frames,
        "skeleton": anim.get_editor_property("skeleton").get_path_name(),
        "curves": {},
        "bones": {},
    }
    for c in lib.get_animation_curve_names(anim, unreal.RawCurveTrackTypes.RCT_FLOAT):
        times, values = lib.get_float_keys(anim, c)
        out["curves"][str(c)] = [[round(t, 4), round(v, 4)] for t, v in zip(times, values)]
    for b in lib.get_animation_track_names(anim):
        out["bones"][str(b)] = [tr(lib.get_bone_pose_for_frame(anim, b, f, False)) for f in range(frames)]
    path = os.path.join(OUT, name.replace("/", "_") + ".json")
    with open(path, "w") as fh:
        json.dump(out, fh)
    unreal.log(f"[FaceDump] {name}: {frames} frames, {len(out['curves'])} curves, {len(out['bones'])} bones")
