"""Fit audio -> face-channel regression on one vanilla speaker's face anims and predict tracks for new lines.

    <kit python> harness/tools/voice/fit_lipsync.py <facedump_dir> <voices_root> <new_lines_dir> <out_json>

Runs on the Zone Kit's embedded Python (needs only numpy, which that interpreter ships) or any Python 3.11 + numpy.
facedump_dir:  JSONs from dump_face_anim.py (one vanilla speaker; speaker read from AS_FAC_<EN|UA>_<speaker>_<key>)
voices_root:   <kit>\\O\\Voices (holds English(US)\\S2_Live\\VO_<speaker>_<key>.wav, Ukrainian(UA)\\...)
new_lines_dir: en\\VO_<speaker>_<PhraseSID>.wav and uk\\VO_<speaker>_<PhraseSID>.wav, the new takes as they go to
               Wwise (padding included). Speaker `pc` (the player) is skipped: the player has no face anims.
out_json:      overwritten: {"fps", "channels": {name: held-out corr},
               "anims": {asset_name: {"length", "frames", "base", "base_path", "tracks": {channel: [v per frame]}}}}
               Channel names: "curve:<name>" or "bone:<bone>:<tx|ty|tz|roll|pitch|yaw>".
WAVs must be integer PCM (16/24/32-bit), any rate, mono or stereo.

Method: 40-band log-mel frames (16 kHz, n_fft 1024, hop = one anim frame) with +-6 frames of context, ridge
regression to every face channel; channels whose held-out correlation (every 5th line left out) is > 0.35 are kept
as "driven"; every other channel later comes from a base anim (the shortest vanilla line at least as long).
"""
import glob
import json
import os
import sys
import wave

import numpy as np

if len(sys.argv) != 5:
    sys.exit(__doc__)
dump_dir, voices_root, new_dir, out_json = sys.argv[1:5]
LANG = {"EN": "English(US)", "UA": "Ukrainian(UA)"}
CTX = 6  # frames of audio context on each side
DOF = ["tx", "ty", "tz", "roll", "pitch", "yaw"]
SR, NFFT, NMELS = 16000, 1024, 40
CORR_MIN, LAMBDA = 0.35, 30.0


def read_wav(path):
    with wave.open(path, "rb") as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        x = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        x = np.where(x >= 1 << 23, x - (1 << 24), x).astype(np.float32) / (1 << 23)
    elif width in (2, 4):
        x = np.frombuffer(raw, np.int16 if width == 2 else np.int32).astype(np.float32) / (1 << (8 * width - 1))
    elif width == 1:
        x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    else:
        raise ValueError(f"{path}: {width}-byte samples")
    x = x.reshape(-1, ch).mean(1)
    return x, rate, n / rate


def mel_fbank(n_freqs):
    hz2mel = lambda f: 2595.0 * np.log10(1.0 + f / 700.0)
    mel2hz = lambda m: 700.0 * (10 ** (m / 2595.0) - 1.0)
    freqs = np.linspace(0, SR // 2, n_freqs)
    pts = mel2hz(np.linspace(hz2mel(0.0), hz2mel(SR / 2), NMELS + 2))
    diff = np.diff(pts)
    slopes = pts[None, :] - freqs[:, None]
    down = -slopes[:, :-2] / diff[:-1]
    up = slopes[:, 2:] / diff[1:]
    return np.maximum(0, np.minimum(down, up))  # n_freqs x n_mels


FB = mel_fbank(NFFT // 2 + 1)
WIN = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(NFFT) / NFFT)  # periodic Hann


def features(wav, n_frames, length):
    audio, rate, _ = read_wav(wav)
    if rate != SR:
        t_new = np.arange(int(len(audio) * SR / rate)) / SR
        audio = np.interp(t_new, np.arange(len(audio)) / rate, audio).astype(np.float32)
    hop = max(1, int(round(SR * length / max(1, n_frames - 1))))
    x = np.pad(audio, NFFT // 2, mode="reflect") if len(audio) > NFFT // 2 else np.pad(audio, NFFT // 2)
    count = 1 + (len(x) - NFFT) // hop
    idx = np.arange(NFFT)[None, :] + hop * np.arange(count)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * WIN, axis=1)) ** 2
    f = np.log(spec @ FB + 1e-5)  # frames x 40
    f = np.pad(f, ((0, max(0, n_frames - len(f))), (0, 0)), mode="edge")[:n_frames]
    pad = np.pad(f, ((CTX, CTX), (0, 0)), mode="edge")
    return np.hstack([pad[i:i + n_frames] for i in range(2 * CTX + 1)])


def load_anim(path):
    with open(path) as fh:
        d = json.load(fh)
    n, length = d["frames"], d["length"]
    t = np.linspace(0, length, n)
    ch = {}
    for name, keys in d["curves"].items():
        k = np.array(keys) if keys else np.zeros((0, 2))
        if len(k):
            ch[f"curve:{name}"] = np.interp(t, k[:, 0], k[:, 1])
    for bone, frames in d["bones"].items():
        a = np.array(frames)
        for i, dof in enumerate(DOF):
            ch[f"bone:{bone}:{dof}"] = a[:, i]
    return d, n, length, ch


# ---- training pairs: each vanilla anim + its own voice line
pairs, base_path = [], {}
for p in sorted(glob.glob(os.path.join(dump_dir, "*.json"))):
    d, n, length, ch = load_anim(p)
    asset = os.path.basename(d["name"])  # AS_FAC_EN_<speaker>_<key>
    _, _, lang, speaker, key = asset.split("_", 4)
    wav = os.path.join(voices_root, LANG[lang], "S2_Live", f"VO_{speaker}_{key}.wav")
    if not os.path.exists(wav):
        print("no wav for", asset)
        continue
    base_path[asset] = d["name"]
    pairs.append((asset, n, length, ch, features(wav, n, length)))
print(len(pairs), "training pairs")
if len(pairs) < 5:
    sys.exit("too few training pairs (need the speaker's vanilla WAVs under voices_root)")
fps = float(np.median([(n - 1) / l for _, n, l, _, _ in pairs]))

names = sorted(set.intersection(*[set(c) for _, _, _, c, _ in pairs]))
Y = np.vstack([np.stack([c[k] for k in names], 1) for _, _, _, c, _ in pairs])
X = np.vstack([f for *_, f in pairs])
keep = Y.std(0) > 1e-3
names = [k for k, m in zip(names, keep) if m]
Y = Y[:, keep]
mx, sx = X.mean(0), X.std(0) + 1e-6
my, sy = Y.mean(0), Y.std(0) + 1e-6


def ridge(X, Y, lam=LAMBDA):
    Xn = np.hstack([(X - mx) / sx, np.ones((len(X), 1))])
    return np.linalg.solve(Xn.T @ Xn + lam * np.eye(Xn.shape[1]), Xn.T @ ((Y - my) / sy))


def predict(W, X):
    return (np.hstack([(X - mx) / sx, np.ones((len(X), 1))]) @ W) * sy + my


# ---- held-out validation: every 5th line left out
test = set(range(0, len(pairs), 5))
tr = [i for i in range(len(pairs)) if i not in test]
idx = np.cumsum([0] + [p[1] for p in pairs])
rows = lambda ids: np.concatenate([np.arange(idx[i], idx[i + 1]) for i in ids])
W = ridge(X[rows(tr)], Y[rows(tr)])
P, T = predict(W, X[rows(sorted(test))]), Y[rows(sorted(test))]
corr = np.array([np.corrcoef(P[:, j], T[:, j])[0, 1] if T[:, j].std() > 1e-6 else 0 for j in range(len(names))])
print("best-predicted channels (held-out corr):")
for j in np.argsort(-corr)[:25]:
    print(f"  {corr[j]:.2f}  {names[j]}")
driven = [j for j in range(len(names)) if corr[j] > CORR_MIN]
print(len(driven), "of", len(names), "channels driven by audio")

# ---- final fit on all lines, predict the new ones
W = ridge(X, Y)
out = {"fps": fps, "channels": {names[j]: float(corr[j]) for j in driven}, "anims": {}}
for lang_dir, lang in (("en", "EN"), ("uk", "UA")):
    for wav in sorted(glob.glob(os.path.join(new_dir, lang_dir, "VO_*.wav"))):
        speaker, key = os.path.basename(wav)[3:-4].split("_", 1)
        if speaker == "pc":
            continue
        length = read_wav(wav)[2]
        n = int(round(length * fps)) + 1
        pred = predict(W, features(wav, n, length))
        cands = sorted([(l, a) for a, _, l, _, _ in pairs if a.split("_")[2] == lang and l >= length]) or \
            sorted([(-l, a) for a, _, l, _, _ in pairs if a.split("_")[2] == lang])
        if not cands:
            print(f"skip {wav}: no {lang} base anim in the dump")
            continue
        out["anims"][f"AS_FAC_{lang}_{speaker}_{key}"] = {
            "length": length, "frames": n, "base": cands[0][1], "base_path": base_path[cands[0][1]],
            "tracks": {names[j]: [round(float(v), 4) for v in pred[:, j]] for j in driven},
        }
        print(f"AS_FAC_{lang}_{speaker}_{key}: {length:.2f}s, base {cands[0][1]}")
with open(out_json, "w") as fh:
    json.dump(out, fh)
print("->", out_json)
