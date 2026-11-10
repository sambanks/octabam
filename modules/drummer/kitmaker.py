#!/usr/bin/env python3
"""DRUMMER's kit maker: a folder of one-shots -> one sliced sample and its kit, ready for the unit.

    .venv/bin/python3 modules/drummer/kitmaker.py IN_DIR OUT_DIR/NAME [--order zone|name] [--bits 16|24]
        [--mono|--stereo] [--no-trim] [--max-ms N] [--gap-ms N] [--dry-run]

Writes, side by side (copy the three to the card's AUDIO folder, together):

  NAME.wav   the one-shots end to end, 44.1 kHz (ffmpeg converts any other rate or format;
             without it, 16/24-bit PCM WAVs at 44.1 kHz only)
  NAME.ot    the unit's attributes file: one slice per sound, trim = the whole file, no
             timestretch, no loop. The firmware's reader (0x4008b8d0) copies its 64 slices x 12 bytes
             to the FLEX slot's record +312 and its count to +1092, and refuses a wrong checksum
             (the 16-bit sum of bytes 20..829).
  NAME.drk   DRUMMER's kit file (kit.c DrkFile, version 1): zone, role and ALIGN for every slice,
             with the slices it fits (their count and the CRC-32 of the .ot's slice table, which is
             what store.c drk_sig measures in RAM). DRUMMER loads it with no question when a
             DRUMMER track gets NAME.wav.

Each sound's ZONE comes, first found, from:
  1. its sub-folder's name (IN_DIR/KICK/..., SNARE, GHOST, HATC, HATO, RIDE, CRASH, TOM, PERC);
  2. a word of its file name (kick/bd, snare/sd/clap, ghost, hh/chh/closed hat, oh/open hat, ride,
     crash/cymbal, tom, perc/shaker/conga/rim/cowbell...);
  3. AUTO: the firmware's own analysis (autokit.c, the code the KIT's AUTO runs).
ROLE: a word (accent/hard/loud -> ACCENT, soft/light -> SOFT), else AUTO's rule: by level inside the
zone, the top third ACCENT, the bottom third SOFT. ALIGN: AUTO's (the hit's place when 15 ms in or
later; 0 for a trimmed one-shot). GAIN 0, no SIMILAR groups (SIMILAR's tolerance kept at its default
6, OUT, for a later AUTO on the unit).

One WAV holding every sound (kitmaker.py CHAIN.wav OUT_DIR/NAME [--names kick,snare,hh,...]):
its slices are, first found, those of the .ot beside it (the WAV and the .ot then copied as they are,
only the .drk new), --grid N equal slices, its cue points, or a cut at each silence (--split-db,
--split-ms); the slices keep the file's order; zones from --names (one word per slice, in order),
else AUTO.

Nothing here touches the card; the files are the user's own.
"""
import argparse, ctypes, json, pathlib, re, shutil, struct, subprocess, sys, wave, zlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import verify_autokit as VA  # noqa: E402

RATE = 44100
EXTS = {".wav", ".wave", ".aif", ".aiff", ".flac", ".mp3", ".ogg"}
OUT, COMBO, ACCENT, NORMAL, SOFT = 15, 9, 0, 1, 2
TEMPO24 = 120 * 24                     # the .ot's tempo, BPM x 24 (unused: no timestretch)
DRK_MAGIC, DRK_VERSION, DRK_SIZE = 0x44524B54, 1, 468
SIM_TOL_DEFAULT = 6
PRIO = (0, 1, 6, 4, 3, 5, 7, 8, 2)     # drummer.c PRIO, the zones' default priority (kit.c dr_kit_init)

# file-name words -> zone; checked in this order (an open hat before a hat, a ghost before a snare)
WORDS = [
    ("HATO", {"oh", "ohh", "hho", "ohat", "openhat", "openhh", "open"}),
    ("HATC", {"ch", "chh", "hhc", "hh", "hat", "hats", "hihat", "hihats", "chat", "closedhat", "closed", "hhat"}),
    ("RIDE", {"ride", "rd", "bell"}),
    ("CRASH", {"crash", "cr", "cym", "cymbal", "splash", "china"}),
    ("KICK", {"kick", "kik", "kck", "bd", "bassdrum", "kicks"}),
    ("GHOST", {"ghost", "gh"}),
    ("SNARE", {"snare", "snr", "sd", "sn", "clap", "clp", "cp", "snares"}),
    ("TOM", {"tom", "toms", "lt", "mt", "ht", "lowtom", "midtom", "hitom", "floortom", "floor"}),
    ("PERC", {"perc", "percussion", "shaker", "shk", "conga", "bongo", "cowbell", "cb", "tamb", "tambourine",
              "clave", "rim", "rimshot", "rs", "wood", "block", "cabasa", "guiro", "tri", "triangle", "fx", "zap"}),
]
ROLE_WORDS = {ACCENT: {"acc", "accent", "hard", "loud", "strong"}, SOFT: {"soft", "light", "quiet", "weak"}}


def words(name):
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    s = re.sub(r"(\d+)", r" \1 ", s).lower()
    return [w for w in re.split(r"[^a-z0-9]+", s) if w]


def zone_of_name(path, root):
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:
        if part.upper() in E.ZONES:
            return part.upper(), "folder"
    ws = words(path.stem)
    joined = "".join(ws)
    for z, keys in WORDS:
        if any(w in keys for w in ws):
            return z, "name"
    for z, keys in WORDS:                          # "openhat", "hihat" written as one word
        if any(len(k) >= 4 and k in joined for k in keys):
            return z, "name"
    return None, "auto"


def role_of_name(path):
    ws = set(words(path.stem))
    for r, keys in ROLE_WORDS.items():
        if ws & keys:
            return r
    return None


def natural(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(p))]


# ---- audio in --------------------------------------------------------------------------------------------

def probe(path):
    """(channels, bits) of the file as it is: the output's format follows the richest input."""
    if shutil.which("ffprobe"):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                            "stream=channels,bits_per_raw_sample,bits_per_sample,sample_fmt", "-of", "json", str(path)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            st = json.loads(r.stdout)["streams"][0]
            bits = int(st.get("bits_per_raw_sample") or 0) or int(st.get("bits_per_sample") or 0)
            if not bits:
                bits = 24 if st.get("sample_fmt", "").startswith(("s32", "flt", "dbl")) else 16
            return int(st["channels"]), bits
    with wave.open(str(path)) as w:
        return w.getnchannels(), 8 * w.getsampwidth()


def decode(path):
    """float32 frames x 2 (mono doubled), 44.1 kHz."""
    if shutil.which("ffmpeg"):
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le",
                            "-ac", "2", "-ar", str(RATE), "-"], capture_output=True)
        if r.returncode:
            sys.exit(f"kitmaker: ffmpeg cannot read {path}: {r.stderr.decode()[-300:]}")
        return np.frombuffer(r.stdout, "<f4").reshape(-1, 2).copy()
    with wave.open(str(path)) as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if rate != RATE or sw not in (2, 3):
        sys.exit(f"kitmaker: {path}: {rate} Hz, {8 * sw} bit -- install ffmpeg to convert it")
    if sw == 2:
        x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    else:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = ((b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)) << 8 >> 8).astype(np.float32) / 8388608
    x = x.reshape(-1, ch)
    return np.repeat(x, 2, axis=1) if ch == 1 else x[:, :2].copy()


def trim(x, db=-60.0):
    """Leading and trailing silence under db off, with 1 ms kept before the first sound and a 2 ms fade at
    the end."""
    level = np.abs(x).max(axis=1)
    loud = np.nonzero(level >= 10 ** (db / 20))[0]
    if not len(loud):
        return x[:1]
    a, b = max(0, loud[0] - RATE // 1000), min(len(x), loud[-1] + 1)
    x = x[a:b].copy()
    fade = min(len(x), RATE * 2 // 1000)
    x[len(x) - fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    return x


# ---- files out -------------------------------------------------------------------------------------------

def write_wav(path, x, bits, stereo):
    if not stereo:
        x = x.mean(axis=1, keepdims=True)
    full = 2 ** (bits - 1)
    q = np.clip(np.round(x * full), -full, full - 1).astype(np.int32)
    if bits == 16:
        data = q.astype("<i2").tobytes()
    else:
        u = q.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3]
        data = u.tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2 if stereo else 1)
        w.setsampwidth(bits // 8)
        w.setframerate(RATE)
        w.writeframes(data)


def ot_bytes(frames, slices):
    """The .ot (docs/firmware/SAMPLE_SAVE.md section 8): 832 bytes, big endian."""
    bars100 = round(frames * TEMPO24 * 100 / (RATE * 60 * 4 * 24))
    d = bytearray(b"FORM\0\0\0\0DPS1SMPA\0\0\0\0")
    d += struct.pack(">HBIIIIIHBIII", 2, 1, TEMPO24, bars100, bars100, 0, 0, 48, 0xFF, 0, frames, 0)
    for i in range(64):
        s, e = slices[i] if i < len(slices) else (0, 0)
        d += struct.pack(">III", s, e, 0xFFFFFFFF if i < len(slices) else 0)
    d += struct.pack(">I", len(slices))
    d += struct.pack(">H", sum(d[20:]) & 0xFFFF)
    assert len(d) == 832
    return bytes(d)


def drk_bytes(n, sig, zone, role, align, simtol=SIM_TOL_DEFAULT, simmode=0):
    """The .drk (kit.c DrkFile, store.c dr_job): head magic, version, size, CRC-32; then the payload."""
    z = list(zone) + [OUT] * (64 - len(zone))
    r = list(role) + [NORMAL] * (64 - len(role))
    a = list(align) + [0] * (64 - len(align))
    body = struct.pack(">BBBBI", n, simtol, simmode, 0, sig) + bytes(z) + bytes(r) + bytes(128) + bytes(a) \
        + bytes(PRIO) + bytes(3) + bytes(64) + bytes(64)
    assert len(body) == DRK_SIZE
    return struct.pack(">4I", DRK_MAGIC, DRK_VERSION, DRK_SIZE, zlib.crc32(body)) + body


def ot_sig(ot):
    n, = struct.unpack(">I", ot[0x33A:0x33E])
    return n, zlib.crc32(ot[0x3A:0x3A + 12 * n])


# ---- the kit ---------------------------------------------------------------------------------------------

def analyse(mono16, slices):
    """autokit.c on the joined sample: features per slice, then AUTO's kit (SIMILAR off)."""
    L = VA.lib()
    read = VA.READ(lambda ctx, frame: int(mono16[frame]) if frame < len(mono16) else 0)
    feats = (VA.Features * 64)()
    for i, (s, e) in enumerate(slices):
        L.ak_features(read, None, s, e, ctypes.byref(feats[i]))
    kit, align, link = E.Kit(), (ctypes.c_uint8 * 64)(), (ctypes.c_uint8 * 64)()
    L.dr_kit_init(ctypes.byref(kit), len(slices))
    L.ak_kit(feats, len(slices), ctypes.byref(kit), align, 0, 0, link)
    return feats, kit, align


def roles(zone, level, forced):
    """autokit.c's rule over the final zones: rank by level inside a zone, top third ACCENT, bottom SOFT."""
    n, out = len(zone), []
    for i in range(n):
        if forced[i] is not None:
            out.append(forced[i])
            continue
        same = [j for j in range(n) if zone[j] == zone[i]]
        louder = sum(1 for j in same if level[j] > level[i] or (level[j] == level[i] and j < i))
        c = len(same)
        out.append(NORMAL if c < 2 else ACCENT if louder * 3 < c else SOFT if louder * 3 >= 2 * c else NORMAL)
    return out


# ---- one WAV holding every sound -----------------------------------------------------------------------

def wav_cues(path):
    """The cue points of a RIFF WAV (sample offsets at its own rate) and that rate; [] when none."""
    d = path.read_bytes()
    if d[:4] != b"RIFF" or d[8:12] != b"WAVE":
        return [], 0
    at, cues, rate = 12, [], 0
    while at + 8 <= len(d):
        cid, size = d[at:at + 4], struct.unpack("<I", d[at + 4:at + 8])[0]
        body = d[at + 8:at + 8 + size]
        if cid == b"fmt " and len(body) >= 8:
            rate = struct.unpack("<I", body[4:8])[0]
        elif cid == b"cue " and len(body) >= 4:
            n = struct.unpack("<I", body[:4])[0]
            for i in range(min(n, (len(body) - 4) // 24)):
                cues.append(struct.unpack("<I", body[4 + 24 * i + 20:4 + 24 * i + 24])[0])
        at += 8 + size + (size & 1)
    return sorted(set(cues)), rate


def onsets_after_silence(x, db, gap_ms):
    level = np.abs(x).max(axis=1)
    loud = np.nonzero(level >= 10 ** (db / 20))[0]
    if not len(loud):
        return []
    gap = RATE * gap_ms // 1000
    firsts = [int(loud[0])] + [int(loud[k + 1]) for k in np.nonzero(np.diff(loud) > gap)[0]]
    return [max(0, f - RATE // 1000) for f in firsts]


def bounds(starts, frames, from_zero=True):
    """Contiguous slices from the sounds' starts, each to the next start, the last to the end. from_zero
    (cue points): the first slice from frame 0; else (a cut at silences) from the first sound."""
    starts = sorted(set(int(v) for v in starts if 0 <= v < frames))
    if from_zero and (not starts or starts[0] > 0):
        starts = [0] + starts
    return [(s0, e0) for s0, e0 in zip(starts, starts[1:] + [frames])]


def write_preview(d, x, slices, zones, bits, stereo):
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("[0-9][0-9]_*.wav"):
        f.unlink()
    for i, (s0, e0) in enumerate(slices):
        write_wav(d / f"{i + 1:02d}_{zones[i]}.wav", x[s0:e0], bits, stereo)
    print(f"preview: {len(slices)} slices in {d}")


def one_wav(a):
    """One WAV holding every sound. Its slices: the .ot beside it (the WAV and the .ot kept as they are, only
    the .drk written), else --grid, else its cue points, else a cut at each silence. Zones: --names, else
    AUTO; slices kept in the file's order."""
    src = pathlib.Path(a.indir).expanduser().resolve()
    out = pathlib.Path(a.out).expanduser().resolve()
    if out.suffix.lower() in (".wav", ".ot", ".drk"):
        out = out.with_suffix("")
    if not re.fullmatch(r"[A-Za-z0-9 _\-.()]{1,60}", out.name):
        sys.exit(f"kitmaker: '{out.name}': letters, digits, space and _-.() only, 60 at most (the unit's names)")
    ch, bits0 = probe(src)
    x = decode(src)
    frames = len(x)
    keep_ot = src.with_suffix(".ot").is_file() and not a.grid
    if keep_ot:
        ot = src.with_suffix(".ot").read_bytes()
        if len(ot) != 832 or ot[:16] != b"FORM\0\0\0\0DPS1SMPA":
            sys.exit(f"kitmaker: {src.with_suffix('.ot')}: not a .ot file")
        n, = struct.unpack(">I", ot[0x33A:0x33E])
        slices = [struct.unpack(">II", ot[0x3A + 12 * i:0x42 + 12 * i]) for i in range(min(n, 64))]
        how = "its .ot"
    elif a.grid:
        if not 1 <= a.grid <= 64:
            sys.exit("kitmaker: --grid 1..64")
        slices = [(frames * i // a.grid, frames * (i + 1) // a.grid) for i in range(a.grid)]
        how = f"{a.grid} equal slices"
    else:
        cues, rate = wav_cues(src)
        if cues:
            slices = bounds([round(c * RATE / rate) for c in cues], frames)
            how = f"its {len(cues)} cue points"
        else:
            db = a.split_db
            if db is None:                         # a chain's sounds apart by (near) zeros: a decay's dip is no cut;
                # -84, not -90: a gap's 1-bit noise passes -90 once resampled (a 48 kHz pack, 8 Nov 2026)
                db = -84.0 if len(onsets_after_silence(x, -84.0, a.split_ms)) >= 2 else -50.0
            slices = bounds(onsets_after_silence(x, db, a.split_ms), frames, from_zero=False)
            how = f"cut at silences ({db:g} dB, {a.split_ms} ms)"
    if not slices:
        sys.exit(f"kitmaker: no sound found in {src}")
    if len(slices) > 64:
        sys.exit(f"kitmaker: {len(slices)} slices ({how}), 64 at most: try --split-ms higher or --grid")
    labels = [w.strip() for w in a.names.split(",")] if a.names else []
    if labels and len(labels) != len(slices):
        print(f"kitmaker: --names gives {len(labels)} names for {len(slices)} slices: the rest by AUTO")
    named = []
    for i in range(len(slices)):
        z = None
        if i < len(labels) and labels[i]:
            fake = pathlib.Path(labels[i] + ".wav")
            if labels[i].upper() in E.ZONES:
                z = labels[i].upper()
            else:
                z, _ = zone_of_name(fake, fake.parent)
            if z is None and labels[i].lower() not in ("auto", "?", "-"):
                print(f"kitmaker: '{labels[i]}' (slice {i + 1}) names no zone: AUTO decides")
        named.append((z, "name") if z else (None, "auto"))

    m = np.clip(np.round(x.mean(axis=1) * 32768), -32768, 32767).astype(np.int32)
    feats, kit, align = analyse(m, slices)
    zone = [E.ZONES.index(z) if z else kit.zone[i] for i, (z, _) in enumerate(named)]
    forced = [role_of_name(pathlib.Path(labels[i] + ".wav")) if i < len(labels) else None for i in range(len(slices))]
    role = roles(zone, [feats[i].level for i in range(len(slices))], forced)
    al = [align[i] for i in range(len(slices))]
    stereo = a.stereo or (not a.mono and ch > 1)
    bits = a.bits or (24 if bits0 > 16 else 16)

    print(f"{out.name}: {len(slices)} slices from {src.name} ({how}), {frames / RATE:.2f} s")
    print(" sl  zone   (from)  role    align  length  name")
    names = E.ZONES + ["COMBO"] + ["?"] * 5 + ["OUT"]
    for i, (s0, e0) in enumerate(slices):
        print(f" {i + 1:2d}  {names[zone[i]]:6s} {named[i][1]:7s} {E.ROLES[role[i]]:6s} {al[i]:4d}ms "
              f"{(e0 - s0) * 1000 // RATE:5d}ms  {labels[i] if i < len(labels) else ''}")
    if a.preview:
        write_preview(pathlib.Path(a.preview).expanduser(), x, slices, [names[z] for z in zone], bits, stereo)
    if a.dry_run:
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    if keep_ot:                                    # the unit's own files: copied as they are
        if src.with_suffix("") != out:
            shutil.copyfile(src, out.with_suffix(".wav"))
            shutil.copyfile(src.with_suffix(".ot"), out.with_suffix(".ot"))
    else:
        write_wav(out.with_suffix(".wav"), x, bits, stereo)
        ot = ot_bytes(frames, slices)
        out.with_suffix(".ot").write_bytes(ot)
    n, sig = ot_sig(ot)
    out.with_suffix(".drk").write_bytes(drk_bytes(n, sig, zone, role, al))
    print(f"wrote {out.with_suffix('.drk')}" + ("" if keep_ot and src.with_suffix("") == out else
          f" with {out.name}.wav and .ot") + f" (slices CRC-32 {sig:#010x}): copy them to the card's AUDIO folder")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("indir", help="the folder of one-shots (sub-folders read too), or one WAV holding them all")
    ap.add_argument("out", help="OUT_DIR/NAME: writes NAME.wav, NAME.ot and NAME.drk there")
    ap.add_argument("--order", choices=("zone", "name"), default="zone",
                    help="slices by zone (KICK first) then name (default), or by name only")
    ap.add_argument("--bits", type=int, choices=(16, 24), help="default: 24 if any sound is over 16 bits")
    ch = ap.add_mutually_exclusive_group()
    ch.add_argument("--mono", action="store_true")
    ch.add_argument("--stereo", action="store_true", help="default: stereo if any sound is")
    ap.add_argument("--no-trim", action="store_true", help="keep each sound's leading and trailing silence")
    ap.add_argument("--max-ms", type=int, default=0, help="cut each sound to this length (2 ms fade)")
    ap.add_argument("--gap-ms", type=int, default=0, help="silence after each sound, inside its slice")
    ap.add_argument("--dry-run", action="store_true", help="print the kit, write nothing")
    ap.add_argument("--preview", metavar="DIR", help="also write each slice as DIR/NN_ZONE.wav, to listen and name")
    one = ap.add_argument_group("one WAV holding every sound")
    one.add_argument("--names", help="the slices' names in order, comma-separated (kick,snare,hh,...): their zones")
    one.add_argument("--grid", type=int, default=0, help="N equal slices (an evenly spaced chain)")
    one.add_argument("--split-db", type=float, help="no .ot, no cue: silence under this level (default: -84 dB, two "
                     "16-bit steps, when the file is that quiet between its sounds; else -50)")
    one.add_argument("--split-ms", type=int, default=50, help="... lasting this long between two sounds")
    a = ap.parse_args()
    if pathlib.Path(a.indir).expanduser().is_file():
        return one_wav(a)

    root = pathlib.Path(a.indir).expanduser().resolve()
    files = sorted((p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith(".")),
                   key=natural)
    out = pathlib.Path(a.out).expanduser().resolve()
    if out.suffix.lower() in (".wav", ".ot", ".drk"):
        out = out.with_suffix("")
    if not files:
        sys.exit(f"kitmaker: no sound in {root}")
    if len(files) > 64:
        sys.exit(f"kitmaker: {len(files)} sounds, 64 slices at most")
    if not re.fullmatch(r"[A-Za-z0-9 _\-.()]{1,60}", out.name):
        sys.exit(f"kitmaker: '{out.name}': letters, digits, space and _-.() only, 60 at most (the unit's names)")

    named = [zone_of_name(p, root) for p in files]
    info = [probe(p) for p in files]
    stereo = a.stereo or (not a.mono and any(c > 1 for c, _ in info))
    bits = a.bits or (24 if any(b > 16 for _, b in info) else 16)
    sounds = []
    for p in files:
        x = decode(p)
        if not a.no_trim:
            x = trim(x)
        if a.max_ms and len(x) > RATE * a.max_ms // 1000:
            x = x[:RATE * a.max_ms // 1000].copy()
            fade = min(len(x), RATE * 2 // 1000)
            x[len(x) - fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
        if a.gap_ms:
            x = np.concatenate([x, np.zeros((RATE * a.gap_ms // 1000, 2), np.float32)])
        sounds.append(x)

    def layout(sounds):
        slices, at = [], 0
        for x in sounds:
            slices.append((at, at + len(x)))
            at += len(x)
        joined = np.concatenate(sounds)
        # AUTO sees what the unit will read: the WAV's mono (left + right) / 2 at the 16-bit scale
        m = np.clip(np.round(joined.mean(axis=1) * 32768), -32768, 32767).astype(np.int32)
        feats, kit, align = analyse(m, slices)
        zone = [E.ZONES.index(z) if z else kit.zone[i] for i, (z, _) in enumerate(named)]
        return slices, joined, feats, align, zone

    slices, joined, feats, align, zone = layout(sounds)
    if a.order == "zone":                          # by the final zone (AUTO's too), then name: analysed again
        order = sorted(range(len(files)), key=lambda i: (zone[i], natural(files[i])))
        files, named, sounds = [files[i] for i in order], [named[i] for i in order], [sounds[i] for i in order]
        slices, joined, feats, align, zone = layout(sounds)
    frames = len(joined)
    peak = float(np.abs(joined).max())
    if peak > 1.0:
        print(f"kitmaker: a sound peaks at {20 * np.log10(peak):+.1f} dBFS: clipped in the WAV")
    forced = [role_of_name(p) for p in files]
    role = roles(zone, [feats[i].level for i in range(len(files))], forced)
    al = [align[i] for i in range(len(files))]

    print(f"{out.name}: {len(files)} sounds, {frames / RATE:.2f} s, {RATE} Hz, {bits} bit, "
          f"{'stereo' if stereo else 'mono'}")
    print(" sl  zone   (from)  role    align  length  sound")
    names = E.ZONES + ["COMBO"] + ["?"] * 5 + ["OUT"]
    for i, p in enumerate(files):
        src = named[i][1] if named[i][0] else "auto"
        print(f" {i + 1:2d}  {names[zone[i]]:6s} {src:7s} {E.ROLES[role[i]]:6s} {al[i]:4d}ms "
              f"{(slices[i][1] - slices[i][0]) * 1000 // RATE:5d}ms  {p.relative_to(root)}")
    if a.preview:
        write_preview(pathlib.Path(a.preview).expanduser(), joined, slices, [names[z] for z in zone], bits, stereo)
    if a.dry_run:
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    write_wav(out.with_suffix(".wav"), joined, bits, stereo)
    ot = ot_bytes(frames, slices)
    out.with_suffix(".ot").write_bytes(ot)
    n, sig = ot_sig(ot)
    out.with_suffix(".drk").write_bytes(drk_bytes(n, sig, zone, role, al))
    with wave.open(str(out.with_suffix(".wav"))) as w:
        assert w.getnframes() == frames
    print(f"wrote {out.with_suffix('.wav')}, .ot and .drk (slices CRC-32 {sig:#010x}): "
          f"copy the three to the card's AUDIO folder")
    return 0


if __name__ == "__main__":
    sys.exit(main())
