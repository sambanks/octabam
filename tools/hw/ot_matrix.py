#!/usr/bin/env python3
"""A remix in many configurations, stamped in advance, stepped over USB MIDI, measured over USB audio.

One USB cable to the unit and nothing else: program change selects a
layout, MIDI START plays it, the unit's own USB audio stream is the
capture, and LOAD METER (vendor request 0xc0/0x57, tools/hw/load_meter.py)
is the load readout where the image carries it.

    python3 tools/hw/ot_matrix.py plan REMIX [--pairs]
    python3 tools/hw/ot_matrix.py proj SRC DEST_PREFIX REMIX [--pairs] [--pattern A2]
                                  [--stimuli hits,pink,...] [--stim-tracks 1-8]
    python3 tools/hw/ot_matrix.py run PROJECT_DIR LABEL [--midi Octatrack] [--audio Octatrack]
                                  [--pc-channel 1] [--bpm 121] [--play 12] [--tail 3] [--only 0,4-9]
    python3 tools/hw/ot_matrix.py audit PROJECT_DIR      # trigs, locks, odd part records, LFOs, sample paths: none in a fresh project
    python3 tools/hw/ot_matrix.py report out/hw/matrix/<label>/report.json ...   # a Markdown table per run
    python3 tools/hw/ot_matrix.py switch PROJECT LABEL (--pairs A:B,... | --report REPORT.json)
                                                 # program change DURING play; load spikes and gaps at the switch
    python3 tools/hw/ot_matrix.py predict REMIX --reports R1 R2 ... [--threshold 0.85] [--select pick.json]
                                                 # per-core busy of pair/split layouts from the single-effect runs
    python3 tools/hw/ot_matrix.py selftest      # the detectors on synthetic audio; no unit

LAYOUTS. Effect selection cannot be driven over MIDI, but every effect id
and knob byte lives in the project and a pattern selects a part
(tools/hw/ot_ladder.py). A project here holds 32 layouts: 8 banks, and in
each bank patterns 1-4 playing parts 1-4, one layout per part. Program
change `16 * bank + (pattern - 1)` selects one. `plan` prints the layouts a
remix gets; `proj` writes them to DEST_PREFIX_01, _02, ... (32 to a
project), each with OCTABAM_MATRIX.json beside the project files.

  Layout 0 of every project is BASE: no effect of ours, the baseline every
  other layout's level, high band and click count are compared with.
  octabam / octabam-bus: each FX2 effect on all eight tracks
    alone, then each FX1 effect on all eight alone, each at its manifest
    defaults, at its `dear` settings, and in each MODE (with and without
    `dear`). --pairs adds every FX1 x FX2 pair on all eight tracks at `dear`.
  octabam-bus: the bus rig as the ladder's RIG rung has it on FX2 (BusDelay
    on T1, BusVerb on T5, SEND elsewhere), then each FX1 station on all
    eight tracks in the same variants, and the stock DELAY on T8's FX2.

MATERIAL. By default every pattern plays SRC's pattern A2 (--pattern). With
--stimuli the project plays synthetic material instead (tools/hw/ot_stimuli.py):
the WAVs are written beside the project files, FLEX slots 1..N name them
(PATH is the bare file name) with their trim records in markers.work, the
--stim-tracks tracks (default all eight) take them round-robin as looping FLEX
machines, and each pattern is one trig on step 1 of 64 steps at 1X, so at 120
BPM (recorded in OCTABAM_MATRIX.json as `bpm`, which `run` uses) a stimulus
restarts exactly when its 2, 4 or 8 s ends. The stimuli's expected levels and
events are in OCTABAM_STIMULI.json. The project has no .ot attribute files.

SETTINGS. Every project gets the [SETTINGS] and [STATES] keys a run depends on
stamped as text (STORAGE.md section 5): CLOCK and TRANSPORT RECEIVE on, SEND off,
PROGRAM CHANGE RECEIVE on at --pc-channel (default 1) and SEND off, MIDI_TRIG_CH1-8
= channels 1-8, auto channel and soft thru off, per-pattern tempo off, metronome off,
TEMPOx24 = 120 BPM with --stimuli; the project opens on A01 with no mute, solo or cue
mask. --setting KEY=INT stamps any other key (MAIN_LEVEL, MASTER_TRACK, GAIN_AB, ...);
the keys that changed, with their old and new values, are in OCTABAM_MATRIX.json as
`settings_changed`. Audio-level keys not named here keep the template's values.

CLEAN. With --clean, SRC is a project the unit created and nobody edited, and
nothing of the template's content survives except its first pattern and first part
as the container: all 16 banks are rebuilt, every pattern empty but the stamped ones
(trigs and locks cleared, LEN 64 at 1X), every part record the template's with
only the stamped layouts on top, banks I-P and the unused patterns left empty.
`audit PROJECT` lists what is not default (trigs, parameter locks, part records
that differ from bank A's first, LFO depths, sample paths); --clean refuses a
template it finds edited unless --allow-dirty-template. Every project on this
machine's ~/octa fails the audit (they descend from one working project), so
a fresh one has to be created on the unit (PROJECT > NEW) and copied off.
BASE keeps the bus remix's SEND on FX2 at level 0 rather than id 0 (an FX2 stored as 0
gets no page from the firmware, ot_project.make_clean_project).

THE RUN. For each layout: STOP, program change, the page-1 CCs of the
layout's modules asserted over MIDI (the ladder's rule), START with a
continuous 24 ppqn clock, `--play` s, STOP, `--tail` s. One CoreAudio input
stream stays open for the whole run (a stream opened and closed per layout
is the churn usb_probe.py chases); each layout's samples are analysed and
dropped, and kept as a WAV only when flagged. LOAD METER is polled every
0.25 s through the play phase.

FLAGS per layout, against BASE of the same project, all thresholds initial
and not validated on a unit (constants at the top of this file):

  CRASH     no channel above -80 dBFS in the first 2 s of play where BASE had audio:
            the sequencer stuck on step 1. The run stops: only a power cycle clears it.
  FREEZE    every channel at or below -80 dBFS for 1 s or more at times BASE had audio;
            reported with its second; the transport is restarted and the run goes on.
  CLICKS    discontinuity events (|second difference| far above its neighbourhood's
            median) more than BASE's by CLICK_EXTRA and CLICK_RATIO.
  STATIC    8-16 kHz power up STATIC_DB or more over BASE's.
  LEVEL     rms differs from BASE's by LEVEL_DB or more.
  CLIP      samples at full scale.
  RINGS     the last half second of the tail is above SETTLE_DBFS and BASE's is not: the layout is still
            sounding 2.5-3 s after STOP.
  DROPS     LOAD METER's DSP record failed its checks more than DROPS_BAD times in the play window (frames were
            skipped): 0 in every layout but EUCLID FX1 + LOFI2 FX2, where the median frame rate was only 7 % low.
  OVERLOAD  the frame interrupt ran under 80 % of 2,756 a second in the play window: the DSP missed its frames
            (the load was past its budget) and the unit stays degraded; the run stops. Power-cycle.
  LOAD      LOAD METER's frame-interrupt share or a DSP core's busy/period above LOAD_FRAC, from
            LOAD_SKIP_S into the play phase (the first seconds carry the previous layout's load).

What it cannot see: what the material is (a gap in a loop looks like a
dropout only when BASE has none at that time), a fault that BASE has too,
anything the USB stream hides (the module's rate and fill are in
usb_counters.py), and the unit's analog outputs.
"""
import argparse
import json
import pathlib
import re
import shutil
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent)); import toolpath  # noqa: E402,F401
import ot_events  # noqa: E402

DEAD_DBFS = -80.0
WIN_S = 0.25
FREEZE_S = 1.0
CRASH_S = 2.0
CLICK_EXTRA, CLICK_RATIO = 10, 3.0
ROUGH_BLOCKS = 0.10       # events in more than this share of 512-sample blocks: a rough signal, not isolated clicks
PLAY_SKIP_S = 1.0         # audio figures start here: the new layout's effects arrive 0.26-0.77 s after START
CLICK_SKIP_S = 0.2        # the segment's first samples are a cut, not a click (all 255 'clicks' of layout 2, 24 Oct 2026, were in the first 12 ms)
DROPS_BAD = 20            # LOAD METER bad records in the play window: 0 in 150+ layouts, ~2,950 in EUCLID FX1 + LOFI2 FX2 (24 Oct 2026)
NOMINAL_IRQ_PER_S, OVERLOAD_IRQ_FRAC = 2756.0, 0.8   # the frame interrupt runs 2,756 a second; far fewer means frames are being skipped
LOAD_SKIP_S = 2.0         # the first seconds after START still carry the previous layout's load (BASE read 26% mean and 77% max, 24 Oct 2026)
SETTLE_DBFS, SETTLE_MAX_S = -70.0, 15.0   # wait for the previous layout's tail to fade before the next segment
STATIC_DB, LEVEL_DB = 6.0, 3.0
LOAD_FRAC = 0.90
BANKS = "ABCDEFGH"
PER_PROJECT = 32


# ---------------------------------------------------------------------------
# layouts
# ---------------------------------------------------------------------------
def _variants(m):
    """[(label, knobs)]: the manifest defaults, `dear`, and each MODE, with and without `dear`."""
    out = [("def", {})]
    dear = dict(getattr(m, "dear", None) or {})
    if dear:
        out.append(("dear", dear))
    slot = getattr(m, "mode_slot", None)
    if slot is not None:
        for k in range(m.params[slot].count or 0):
            out.append((f"mode{k}", {slot: k}))
            if dear:
                out.append((f"mode{k}+dear", {**dear, slot: k}))
    return out


def _unique(m, variants):
    """Drop variants whose stamped bytes are the same as an earlier one's."""
    import ot_project as P
    seen, out = set(), []
    for label, knobs in variants:
        b = P.module_defaults(m, knobs)
        if b not in seen:
            seen.add(b)
            out.append((label, knobs))
    return out


def layouts(remix_name, pairs=False, split=False):
    """-> [(name, kind, {track: (fx1 spec, fx2 spec)})]; a spec is (module key, knobs) or None."""
    import ot_ladder as L
    from remix import registry, stock
    remix, mods = registry.remix(remix_name), registry.modules()
    is_bus = "REVERB SERVER" in remix.modules
    # an FX2 stored as 0 gets no page from the firmware and SEND reads a stale word (ot_project.make_clean_project)
    none = {t: (None, L._sends({}).get(t)) for t in range(1, 9)} if "SEND" in remix.modules else \
        {t: (None, None) for t in range(1, 9)}
    out = [("BASE", "base", none)]

    fx1_keys = remix.fx1 or tuple(k for k in stock.p_spans("A") if mods[k].menu.fx2_id in stock.fx1_ids())
    if is_bus:
        rig = L._sends(L._RIG_AUX, verb=True, delay=True)
        fx2_keys = []
    else:
        fx2_keys = [k for k in remix.modules if mods.get(k) is not None and mods[k].menu is not None
                    and k not in remix.hidden]
        rig = {}

    def all_tracks(fx1=None, fx2=None):
        return {t: (fx1, fx2 if fx2 is not None else rig.get(t)) for t in range(1, 9)}

    if is_bus:
        out.append(("RIG", "base", all_tracks()))
        if "DELAY" in remix.modules:
            out.append(("RIG + T8 DELAY", "fx2", {**all_tracks(), 8: (None, ("DELAY", {}))}))
    for k in fx2_keys:
        for label, knobs in _unique(mods[k], _variants(mods[k])):
            out.append((f"{k} FX2 {label}", "fx2", all_tracks(fx2=(k, knobs))))
    for k in fx1_keys:
        for label, knobs in _unique(mods[k], _variants(mods[k])):
            out.append((f"{k} FX1 {label}", "fx1", all_tracks(fx1=(k, knobs))))
    if pairs and not is_bus:
        for k1 in fx1_keys:
            for k2 in fx2_keys:
                d1, d2 = dict(getattr(mods[k1], "dear", None) or {}), dict(getattr(mods[k2], "dear", None) or {})
                out.append((f"{k1} FX1 + {k2} FX2 dear", "pair", all_tracks(fx1=(k1, d1), fx2=(k2, d2))))
    if split and not is_bus:
        # one effect on tracks 1-4 (core 1) and another on 5-8 (core 0), same slot, both at `dear`
        for slot, keys, col in (("FX1", fx1_keys, 0), ("FX2", fx2_keys, 1)):
            for k1 in keys:
                for k2 in keys:
                    if k1 == k2:
                        continue
                    d1, d2 = dict(getattr(mods[k1], "dear", None) or {}), dict(getattr(mods[k2], "dear", None) or {})
                    lo = {t: ((k1, d1) if t <= 4 else (k2, d2), None) if col == 0 else (None, (k1, d1) if t <= 4 else (k2, d2))
                          for t in range(1, 9)}
                    out.append((f"{k1} {slot} T1-4 + {k2} {slot} T5-8 dear", "split", lo))
    return out


def _spec_text(spec):
    return "-" if spec is None else spec[0] + (f" {spec[1]}" if spec[1] else "")


def cmd_plan(a):
    lay = layouts(a.remix, a.pairs, a.split)
    n = len(lay)
    print(f"{a.remix}: {n} layouts, {-(-n // PER_PROJECT)} project(s) of up to {PER_PROJECT}; "
          f"~{n * (a.play + a.tail + 4) / 60:.0f} min at --play {a.play:g} --tail {a.tail:g}")
    for i, (name, kind, lo) in enumerate(lay):
        print(f"  {i:3d}  {kind:5s} {name}")


# ---------------------------------------------------------------------------
# proj
# ---------------------------------------------------------------------------
def _program(i):
    """Layout slot i (0..31) -> (bank number 1..8, pattern 1..4, program change)."""
    bank, k = divmod(i, 4)
    return bank + 1, k + 1, bank * 16 + k


# ---------------------------------------------------------------------------
# stimuli: samples, sample slots and trigs written into the project
# ---------------------------------------------------------------------------
STIM_BPM = 120            # 64 sixteenth steps = 8 s, a whole number of every stimulus' length
STIM_LEN, STIM_SCALE = 64, 2                       # LEN 64, SCALE 1X (ot_project.SCALE_NAMES)
SLOT_REC = 784                                     # a markers.work record; FLEX slot n is record n - 1 from 0x16


def stim_assign(names, tracks):
    """[(track 0..7, slot 1..N)]: the stimuli round-robin over `tracks` (1-based)."""
    return [(t - 1, 1 + i % len(names)) for i, t in enumerate(tracks)]


def _stim_text(dest, names, frames):
    """FLEX slots 1..N in project.work / .strd name the stimuli (PATH beside the project files)."""
    import re
    blocks = b""
    for i, n in enumerate(names):
        bars = frames[n] * 100 * STIM_BPM // (FS_STIM * 60 * 4)
        blocks += (f"[SAMPLE]\r\nTYPE=FLEX\r\nSLOT={i + 1:03d}\r\nPATH={n}.wav\r\nTRIM_BARSx100={bars}"
                   f"\r\nLOOP_BARSx100={bars}\r\nBPMx24={STIM_BPM * 24}\r\nTSMODE=0\r\nLOOPMODE=1\r\nGAIN=48"
                   f"\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n").encode()
    used = {f"{i + 1:03d}".encode() for i in range(len(names))}
    for path in (dest / "project.work", dest / "project.strd"):
        if not path.exists():
            continue
        raw = path.read_bytes()
        raw = re.sub(rb"\[SAMPLE\]\r?\nTYPE=FLEX\r?\nSLOT=(\d+)\r?\n.*?\[/SAMPLE\]\r?\n\r?\n",
                     lambda m: b"" if m.group(1) in used else m.group(0), raw, flags=re.S)
        at = raw.find(b"[SAMPLE]")
        if at < 0:
            sys.exit(f"{path}: no [SAMPLE] section to put the stimuli before")
        path.write_bytes(raw[:at] + blocks + raw[at:])


def _stim_markers(dest, names, frames):
    import struct
    for path in (dest / "markers.work", dest / "markers.strd"):
        if not path.exists():
            continue
        data = bytearray(path.read_bytes())
        for i, n in enumerate(names):
            off = 0x16 + i * SLOT_REC
            data[off:off + SLOT_REC] = struct.pack(">III", 0, frames[n], 0) + bytes(SLOT_REC - 12)
        data[-2:] = (sum(data[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        path.write_bytes(data)


FS_STIM = 44100


def write_stimuli(dest, names):
    """The WAVs beside the project files, their FLEX slots and trim records; -> {name: frames}."""
    import ot_stimuli as S
    frames = {}
    for n in names:
        if n not in S.STIMULI:
            sys.exit(f"no stimulus {n!r}; have {', '.join(S.STIMULI)}")
        q, extra = S.render(n)
        S.write_wav(dest / f"{n}.wav", q)
        frames[n] = len(q)
    _stim_text(dest, names, frames)
    _stim_markers(dest, names, frames)
    (dest / "OCTABAM_STIMULI.json").write_text(json.dumps(
        {n: S.describe(n, *S.render(n)) for n in names}, indent=1))
    return frames


def stim_part(data, off, assign):
    """One part record: the assigned tracks are FLEX machines on their slot, looping, no stretch, neutral pitch."""
    for t, slot in assign:
        data[off + 0x02b + t] = 1                       # machine type FLEX (ot_project.MTYPE_OFF)
        data[off + 0x2d3 + t * 5 + 1] = slot - 1        # the track's flex slot
        data[off + 0x01b + t * 2] = 55                  # mix headroom, as stress_project.py
        setup, vals = off + 0x1e3 + t * 30 + 6, off + 0x033 + t * 30 + 6
        data[setup] = 1                                 # LOOP
        data[setup + 4] = 0                             # TSTR off
        data[vals] = 64                                 # PTCH neutral
        data[vals + 3] = 127                            # RATE forward


def stim_pattern(data, pat, assign):
    """Pattern `pat` (0-based): no trigs or locks, then step 1 on the assigned tracks, LEN 64 at 1X."""
    import ot_project as P
    for t in range(8):
        off = P.trac_off(pat, t)
        data[off:off + 64] = bytes(64)
        data[off + 0x59:off + 0x59 + 64 * 32] = bytes([0xff]) * (64 * 32)
    for t, _slot in assign:
        data[P.trac_off(pat, t) + 7] |= 1               # mask 0, step 1
    tail = P.PTRN0 + pat * P.PTRN_FSTRIDE + P.PTRN_FSTRIDE - 11
    data[tail + 2], data[tail + 3] = STIM_LEN, STIM_SCALE


# ---------------------------------------------------------------------------
# project settings: the MIDI setup and the start state, written as text
# ---------------------------------------------------------------------------
def test_settings(pc_channel=1):
    """[SETTINGS] keys a run depends on (docs/firmware/STORAGE.md section 5). Channel keys are 0-based."""
    s = {"MIDI_CLOCK_RECEIVE": 1, "MIDI_TRANSPORT_RECEIVE": 1,
         "MIDI_CLOCK_SEND": 0, "MIDI_TRANSPORT_SEND": 0,
         "MIDI_PROGRAM_CHANGE_RECEIVE": 1, "MIDI_PROGRAM_CHANGE_RECEIVE_CH": pc_channel - 1,
         "MIDI_PROGRAM_CHANGE_SEND": 0,
         "MIDI_AUTO_CHANNEL": -1, "MIDI_SOFT_THRU": 0,
         "PATTERN_TEMPO_ENABLED": 0, "METRONOME_ENABLED": 0}
    s.update({f"MIDI_TRIG_CH{t}": t - 1 for t in range(1, 9)})
    return s


# [STATES]: the project opens on A01 with nothing muted, soloed or cued.
TEST_STATES = {"BANK": 0, "PATTERN": 0, "PART": 0, "TRACK": 0, "ARRANGEMENT": 0, "ARRANGEMENT_MODE": 0,
               "TRACK_MUTE_MASK": 0, "TRACK_SOLO_MASK": 0, "TRACK_CUE_MASK": 0}


def stamp_text(dest, settings, states):
    """Set keys inside [SETTINGS] and [STATES] of project.work and project.strd.
    -> {key: [old, new]} for the keys that changed. A key the file does not have is an error."""
    import re
    changed = {}
    for name in ("project.work", "project.strd"):
        path = dest / name
        if not path.exists():
            continue
        raw = path.read_bytes().decode("latin1")
        for block, kv in (("SETTINGS", settings), ("STATES", states)):
            m = re.search(rf"\[{block}\]\r?\n(.*?)\[/{block}\]", raw, re.S)
            if not m:
                sys.exit(f"{path}: no [{block}] block")
            body = m.group(1)
            for key, val in kv.items():
                hit = re.search(rf"^{re.escape(key)}=(-?\d+)(\r?)$", body, re.M)
                if not hit:
                    sys.exit(f"{path}: no {key}= line in [{block}]")
                if hit.group(1) != str(val):
                    changed.setdefault(key, [int(hit.group(1)), int(val)])
                body = body[:hit.start()] + f"{key}={val}{hit.group(2)}" + body[hit.end():]
            raw = raw[:m.start(1)] + body + raw[m.end(1):]
        path.write_bytes(raw.encode("latin1"))
    return changed


# ---------------------------------------------------------------------------
# audit: what in a project is not a fresh unit-created one
# ---------------------------------------------------------------------------
def audit(src):
    """-> dict of findings for the project at `src`: trigs and locks anywhere, part records that differ from
    bank A part 1, LFO depths, project-local sample paths. A project the unit created and nobody edited has none."""
    import ot_project as P
    import ot_bank as B
    import ot_ladder as L
    src = pathlib.Path(src)
    out = {"trigs": [], "locks": [], "parts": [], "lfo": [], "samples": 0, "banks": 0}
    ref = None
    for n in range(1, 17):
        f = src / f"bank{n:02d}.work"
        if not f.is_file():
            continue
        d = f.read_bytes()
        B.check_tags(d)
        out["banks"] += 1
        for pt in range(16):
            for t in range(8):
                off = P.trac_off(pt, t)
                if any(d[off:off + 64]):
                    out["trigs"].append(f"{BANKS[(n - 1) % 8] if n <= 8 else n}{pt + 1:02d} T{t + 1}")
                if any(x != 0xff for x in d[off + 0x59:off + 0x59 + 64 * 32]):
                    out["locks"].append(f"{n}:{pt + 1} T{t + 1}")
        for r in range(P.NPARTS_ALL):
            off = P.PART_BASE + r * P.PART_STRIDE
            rec = bytearray(d[off:off + P.PART_STRIDE])
            rec[L.PART_INDEX_OFF] = 0
            if ref is None:
                ref = bytes(rec)
            elif bytes(rec) != ref:
                out["parts"].append(f"bank {n} record {r + 1}")
            for t in range(8):
                if any(d[off + P.LFO_P1_OFF + t * 24 + 3:off + P.LFO_P1_OFF + t * 24 + 6]):
                    out["lfo"].append(f"bank {n} record {r + 1} T{t + 1}")
    import re
    txt = (src / "project.work").read_bytes().decode("latin1")
    out["samples"] = len([m for m in re.findall(r"^PATH=(.+?)\r?$", txt, re.M) if m.strip()])
    return out


def fresh_findings(a):
    f = []
    for key, what in (("trigs", "tracks with trigs"), ("locks", "tracks with parameter locks"),
                      ("parts", "part records differing from bank A's first"), ("lfo", "tracks with an LFO depth")):
        if a[key]:
            f.append(f"{len(a[key])} {what} (first: {a[key][0]})")
    if a["samples"]:
        f.append(f"{a['samples']} sample slots with a file path")
    return f


def cmd_audit(a):
    r = audit(a.project)
    f = fresh_findings(r)
    print(f"{a.project}: {r['banks']} banks")
    for line in f or ["nothing: every pattern empty, every part record equal, no LFO, no sample path"]:
        print("  " + line)
    return 1 if f else 0


def make_project(src, dest, remix_name, chunk, pattern="A2", stimuli=None, stim_tracks=range(1, 9),
                 pc_channel=1, extra_settings=None, clean=False, allow_dirty=False):
    """Copy SRC to DEST and write `chunk` (a list of layouts, at most 32; the rest BASE).
    With `stimuli` (names from ot_stimuli) the tracks in `stim_tracks` play them on FLEX slots 1..N, one trig
    on step 1 of a 64-step pattern, instead of SRC's own pattern content.
    `clean`: SRC is a project the unit created and nobody edited. All 16 banks are rebuilt from its first
    pattern and first part: every pattern empty but the ones stamped, every part record the template's with only
    the stamped layouts on top. Refused unless `audit` finds SRC fresh (`allow_dirty` overrides)."""
    import ot_ladder as L
    import ot_project as P
    from remix import registry
    src, dest = pathlib.Path(src), pathlib.Path(dest)
    if dest.exists():
        sys.exit(f"{dest} exists -- refusing to overwrite. Pick a new name.")
    if not (src / "project.work").is_file():
        sys.exit(f"{src} is not an Octatrack project directory")
    remix, mods = registry.remix(remix_name), registry.modules()
    if clean:
        if not stimuli:
            sys.exit("--clean needs --stimuli: a clean project has nothing else to play")
        found = fresh_findings(audit(src))
        if found and not allow_dirty:
            sys.exit(f"{src} is not a fresh project:\n  " + "\n  ".join(found)
                     + "\nCreate a new project on the unit and use that, or pass --allow-dirty-template.")
        pattern = "A1"
    sbank, spat = L._pattern_ref(pattern)
    sdata = (src / f"bank{sbank:02d}.work").read_bytes()
    p0 = P.PTRN0 + (spat - 1) * P.PTRN_FSTRIDE
    ptrn = sdata[p0:p0 + P.PTRN_FSTRIDE]
    if ptrn[:4] != b"PTRN":
        sys.exit(f"bank{sbank:02d} pattern {spat}: no PTRN chunk at {p0:#x}")
    spart = ptrn[P.PTRN_FSTRIDE - 5]
    if spart > 3:
        sys.exit(f"pattern {pattern} names part {spart}, not 0..3")
    part_cur = sdata[P.PART_BASE + spart * P.PART_STRIDE:][:P.PART_STRIDE]
    part_sav = sdata[P.PART_BASE + (spart + 4) * P.PART_STRIDE:][:P.PART_STRIDE]

    base = chunk[0] if chunk and chunk[0][0] == "BASE" else None
    slots = list(chunk) + [base or chunk[0]] * (PER_PROJECT - len(chunk))
    plans = []
    for name, kind, lo in slots:
        plans.append([(t, L._slot_bytes(f1, remix, mods), L._slot_bytes(f2, remix, mods))
                      for t, (f1, f2) in lo.items()])

    shutil.copytree(src, dest)
    settings = test_settings(pc_channel)
    if stimuli:
        settings["TEMPOx24"] = STIM_BPM * 24
    settings.update(extra_settings or {})
    changed = stamp_text(dest, settings, TEST_STATES)
    assign = []
    if stimuli:
        write_stimuli(dest, stimuli)
        assign = stim_assign(stimuli, list(stim_tracks))
    for b in range(16 if clean else 8):
        num = b + 1
        used = b < 8                                  # program change reaches banks A-H
        bank_plans = plans[b * 4:b * 4 + 4] if used else [[], [], [], []]

        def mut(data, bank_plans=bank_plans, used=used):
            for j in range(16 if clean else 4):      # pattern j+1 plays part j+1 (j < 4)
                d0 = P.PTRN0 + j * P.PTRN_FSTRIDE
                data[d0:d0 + P.PTRN_FSTRIDE] = ptrn
                data[d0 + P.PTRN_FSTRIDE - 5] = j if j < 4 else 0
                if clean:
                    stim_pattern(data, j, assign if used and j < 4 else [])
                elif assign:
                    stim_pattern(data, j, assign)
            for p in range(P.NPARTS_ALL):
                off = P.PART_BASE + p * P.PART_STRIDE
                data[off:off + P.PART_STRIDE] = part_cur if p < 4 else part_sav
                data[off + L.PART_INDEX_OFF] = p % 4      # a record's own index (FAILURE_MODES "PARSE ERROR")
                if assign and used:
                    stim_part(data, off, assign)
                for t, (id1, v1), (id2, v2) in bank_plans[p % 4]:
                    i = t - 1
                    data[off + P.FX1_OFF + i] = id1
                    data[off + P.FX2_OFF + i] = id2
                    a = off + P.P1_OFF + i * P.TRACK_STRIDE
                    bb = off + P.P2_OFF + i * P.P2_STRIDE
                    data[a:a + 6] = v1[:6]; data[a + 6:a + 12] = v2[:6]
                    data[bb:bb + 6] = v1[6:]; data[bb + 6:bb + 12] = v2[6:]
            if used:
                for p in range(4):
                    o = len(data) - 2 - 4 * 7 + p * 7
                    field = f"{b * 4 + p:03d}".encode("latin1")
                    data[o:o + 7] = field + b"\x00" * (7 - len(field))

        P._bank_write(dest, num, mut, guard=False)
        data = (dest / f"bank{num:02d}.work").read_bytes()
        if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
            sys.exit(f"bank{num:02d}: checksum did not take -- do NOT use this")
        for j in range(16 if clean else 4):
            d0 = P.PTRN0 + j * P.PTRN_FSTRIDE
            if data[d0:d0 + 4] != b"PTRN" or data[d0 + P.PTRN_FSTRIDE - 5] != (j if j < 4 else 0):
                sys.exit(f"bank{num:02d} pattern {j + 1}: read-back disagrees")
        for p in range(P.NPARTS_ALL):
            off = P.PART_BASE + p * P.PART_STRIDE
            if data[off:off + 4] != b"PART" or data[off + L.PART_INDEX_OFF] != p % 4:
                sys.exit(f"bank{num:02d} part {p + 1}: record header/index read-back disagrees")
            for t, (id1, v1), (id2, v2) in bank_plans[p % 4]:
                i = t - 1
                a = off + P.P1_OFF + i * P.TRACK_STRIDE
                bb = off + P.P2_OFF + i * P.P2_STRIDE
                got = (data[off + P.FX1_OFF + i], data[off + P.FX2_OFF + i],
                       bytes(data[a:a + 12]), bytes(data[bb:bb + 12]))
                if got != (id1, id2, v1[:6] + v2[:6], v1[6:] + v2[6:]):
                    sys.exit(f"bank{num:02d} part {p + 1} T{t}: read-back disagrees")
    P.write_stored(dest)
    entries = []
    for i, (name, kind, lo) in enumerate(chunk):
        bank, pat, prog = _program(i)
        entries.append({"slot": i, "bank": BANKS[bank - 1], "pattern": pat, "program": prog, "name": name,
                        "kind": kind, "layout": {str(t): [_spec_text(f1), _spec_text(f2)] for t, (f1, f2) in lo.items()}})
    (dest / "OCTABAM_MATRIX.json").write_text(json.dumps(
        {"remix": remix_name, "layouts": entries, "bpm": STIM_BPM if stimuli else None,
         "pc_channel": pc_channel, "settings_changed": changed, "clean": clean,
         "stimuli": {n: [t + 1 for t, sl in assign if sl == i + 1] for i, n in enumerate(stimuli)} if stimuli else None},
        indent=1))
    return len(entries)


def cmd_proj(a):
    lay = layouts(a.remix, a.pairs, a.split)
    base, rest = lay[0], lay[1:]
    if a.select:
        want = set(json.loads(pathlib.Path(a.select).read_text())["run"])
        rest = [l for l in rest if l[0] in want]
        if len(rest) != len(want):
            sys.exit(f"--select names {len(want)} layouts, {len(rest)} exist for this remix and flags")
    stimuli = [x for x in a.stimuli.split(",") if x] if a.stimuli else None
    tracks = _span(a.stim_tracks)
    extra = {}
    for kv in a.setting:
        key, _, val = kv.partition("=")
        if not re.fullmatch(r"-?\d+", val):
            sys.exit(f"--setting {kv!r} is KEY=INTEGER")
        extra[key] = int(val)
    per = PER_PROJECT - 1                     # BASE takes slot 0 of every project
    n = 0
    for k in range(0, len(rest), per):
        dest = f"{a.dest}_{k // per + 1:02d}"
        n += make_project(a.src, dest, a.remix, [base] + rest[k:k + per], a.pattern, stimuli, tracks,
                          a.pc_channel, extra, a.clean, a.allow_dirty_template) - 1
        print(f"{dest}: {len(rest[k:k + per]) + 1} layouts (slot 0 BASE)")
    print(f"{n} layouts in {-(-len(rest) // per)} project(s); "
          + (f"clean rebuild from {a.src}" if a.clean else f"material {a.src} {a.pattern}"))


# ---------------------------------------------------------------------------
# analysis (numpy; the selftest runs it on synthetic audio)
# ---------------------------------------------------------------------------
def _db(x):
    import numpy as np
    return 20.0 * np.log10(max(float(x), 1e-12))


def window_alive(x, fs):
    """Per WIN_S window: any channel above DEAD_DBFS."""
    import numpy as np
    w = int(WIN_S * fs)
    n = len(x) // w
    rms = np.sqrt((x[:n * w].reshape(n, w, -1) ** 2).mean(axis=1))        # (windows, channels)
    return (20 * np.log10(np.maximum(rms, 1e-12)) > DEAD_DBFS).any(axis=1)


def click_events(x, fs):
    """Per channel: (events, blocks that hold one, blocks): samples whose second difference is far above
    their neighbourhood's median. Isolated clicks are few events in few blocks; a rough or heavily modulated
    signal puts events in most blocks."""
    import numpy as np
    out = []
    blk = 512
    for c in range(x.shape[1]):
        d2 = np.abs(np.diff(x[:, c], 2))
        n = len(d2) // blk
        if n < 3:
            out.append((0, 0, n))
            continue
        b = d2[:n * blk].reshape(n, blk)
        med = np.median(b, axis=1)
        ref = np.maximum.reduce([np.roll(med, 1), med, np.roll(med, -1)])
        ref[0], ref[-1] = med[0], med[-1]
        hit = b > np.maximum(1e-3, 50 * ref)[:, None]
        out.append((int(hit.sum()), int(hit.any(axis=1).sum()), n))
    return out


def hf_power_db(x, fs):
    """8-16 kHz power of all channels summed, dB."""
    import numpy as np
    n = 8192
    win = np.hanning(n)
    f = np.fft.rfftfreq(n, 1 / fs)
    sel = (f >= 8000) & (f < min(16000, fs / 2))
    acc, k = 0.0, 0
    for c in range(x.shape[1]):
        for i in range(0, len(x) - n, n):
            acc += (np.abs(np.fft.rfft(x[i:i + n, c] * win)) ** 2)[sel].mean()
            k += 1
    return 10 * np.log10(max(acc / max(k, 1), 1e-30))


def measure(x, fs, play_s):
    """x[:, channels], the play phase first, then the tail. -> metrics dict."""
    import numpy as np
    x = x[:, np.abs(x).max(axis=0) > 0] if (np.abs(x).max(axis=0) > 0).any() else x
    full = x[:int(play_s * fs)]
    # the program change sent while stopped lands 0.26 to 0.77 s after START (24 Oct 2026, 48 layouts), so the first
    # second still plays the previous layout's effects: the figures below start at PLAY_SKIP_S; `alive` keeps the whole
    # phase so it lines up with BASE's
    play = full[int(PLAY_SKIP_S * fs):] if len(full) > int((PLAY_SKIP_S + 2.0) * fs) else full
    ce = click_events(play[int(CLICK_SKIP_S * fs):], fs)
    return {"rms_db": _db(np.sqrt(np.mean(play ** 2))), "peak_db": _db(np.abs(play).max()),
            "dc": float(np.abs(play.mean(axis=0)).max()), "clip": int((np.abs(play) >= 0.9999).sum()),
            "clicks": int(sum(e for e, _b, _n in ce)),
            "click_block_frac": float(sum(b for _e, b, _n in ce) / max(sum(n for _e, _b, n in ce), 1)),
            "hf_db": float(hf_power_db(play, fs)),
            "alive": window_alive(full, fs).tolist(), "channels": int(x.shape[1]),
            "tail_end_db": (float(_db(np.sqrt(np.mean(x[-int(0.5 * fs):] ** 2))))
                            if len(x) >= int((play_s + 1.0) * fs) else None),
            "tail_dc_frac": (float(np.abs(x[-int(0.5 * fs):].mean(axis=0)).max()
                                   / max(np.sqrt(np.mean(x[-int(0.5 * fs):] ** 2)), 1e-12))
                             if len(x) >= int((play_s + 1.0) * fs) else None)}


def runs(mask):
    """[(start, length)] of True runs."""
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j < len(mask) and mask[j]:
                j += 1
            out.append((i, j - i))
            i = j
        else:
            i += 1
    return out


def judge(m, base, load=None):
    """Flags for measurement m against the project's BASE measurement."""
    flags = []
    bal, al = base["alive"], m["alive"]
    n = min(len(bal), len(al))
    need = int(CRASH_S / WIN_S)
    if n >= need and any(bal[:need]) and not any(al[:need]):
        return ["CRASH"], None
    dead = [not al[i] and bal[i] for i in range(n)]
    fr = [(s, l) for s, l in runs(dead) if l * WIN_S >= FREEZE_S]
    if fr:
        flags.append("FREEZE")
    if m["clicks"] - base["clicks"] > CLICK_EXTRA and m["clicks"] > CLICK_RATIO * max(base["clicks"], 1):
        flags.append("ROUGH" if m["click_block_frac"] > ROUGH_BLOCKS else "CLICKS")
    if m["hf_db"] - base["hf_db"] >= STATIC_DB:
        flags.append("STATIC")
    if abs(m["rms_db"] - base["rms_db"]) >= LEVEL_DB:
        flags.append("LEVEL")
    if m["clip"]:
        flags.append("CLIP")
    if m.get("tail_end_db") is not None and m["tail_end_db"] > SETTLE_DBFS and (base.get("tail_end_db") or -240.0) <= SETTLE_DBFS:
        # still sounding in the last half second of the tail, BASE is not; a held constant is a DC offset
        flags.append("DC" if (m.get("tail_dc_frac") or 0.0) > 0.9 else "RINGS")
    if load and load.get("irq_per_s_median") and load["irq_per_s_median"] < OVERLOAD_IRQ_FRAC * NOMINAL_IRQ_PER_S:
        flags.append("OVERLOAD")
    elif load and (load.get("bad_records") or 0) > DROPS_BAD:
        flags.append("DROPS")                # the DSP meter's per-frame record failed its checks: frames were skipped
    if load and load.get("windows"):
        top = max(load["cf_share_max"], load["dsp_core0_max"], load["dsp_core1_max"])
        if top >= LOAD_FRAC:
            flags.append("LOAD")
    return flags, ([round(s * WIN_S, 2) for s, _ in fr] or None)


def cmd_selftest(_a):
    import numpy as np
    fs = 44100
    rng = np.random.default_rng(1)
    t = np.arange(fs * 12) / fs
    env = np.exp(-((t * 2) % 1) * 6)                      # a hit every 0.5 s
    base_sig = (0.3 * np.sin(2 * np.pi * 220 * t) * env + 1e-4 * rng.standard_normal(len(t))).astype(np.float32)
    mk = lambda s: np.stack([s, s], axis=1)               # noqa: E731
    base = measure(mk(base_sig), fs, 12)
    fails = []

    def expect(what, got, want):
        ok = got == want
        print(f"  [{'ok' if ok else 'FAIL'}] {what}: {got}")
        if not ok:
            fails.append(what)

    expect("clean copy of BASE has no flags", judge(measure(mk(base_sig.copy()), fs, 12), base)[0], [])
    s = base_sig.copy()
    for i in range(20):
        s[fs + i * 4000] += 0.4                            # a step click
    expect("20 injected clicks", "CLICKS" in judge(measure(mk(s), fs, 12), base)[0], True)
    s = base_sig + (0.02 * rng.standard_normal(len(t))).astype(np.float32)
    expect("added broadband noise", "STATIC" in judge(measure(mk(s), fs, 12), base)[0], True)
    s = base_sig.copy(); s[5 * fs:7 * fs] = 0
    f, at = judge(measure(mk(s), fs, 12), base)
    expect("a 2 s dropout is a FREEZE at 5 s", ("FREEZE" in f, at), (True, [5.0]))
    s = base_sig * 0.2
    expect("14 dB quieter", "LEVEL" in judge(measure(mk(s), fs, 12), base)[0], True)
    s = np.zeros_like(base_sig)
    expect("silence from the start is a CRASH", judge(measure(mk(s), fs, 12), base)[0], ["CRASH"])
    s = np.clip(base_sig * 4, -1, 1)
    expect("clipping", "CLIP" in judge(measure(mk(s), fs, 12), base)[0], True)
    print(f"selftest: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
def _span(text):
    """'1-4,7' -> [1, 2, 3, 4, 7]."""
    out = []
    for part in text.split(","):
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part.strip())
        if not m:
            sys.exit(f"{part!r} is not N or N-M")
        out += range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1)
    return out


def parse_only(s, n):
    if not s:
        return list(range(n))
    out = []
    for part in s.split(","):
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part.strip())
        if not m:
            sys.exit(f"--only: {part!r} is not N or N-M")
        out += range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1)
    return [i for i in out if i < n]


class LmFeed:
    """LOAD METER readings with their times: in this process when libusb loads, else from
    `load_meter.py --jsonl` under /usr/local/bin/python3 (the Intel Homebrew libusb does not load in an arm64 python)."""

    def __init__(self):
        self.rows, self.proc, self.dev, self.err = [], None, None, None
        try:
            import load_meter
            self.lm = load_meter
            self.dev = load_meter.libusb_device()
            load_meter.read(self.dev)
            return
        except (SystemExit, Exception) as e:  # noqa: BLE001
            self.err = str(e) or type(e).__name__
            self.dev = None
            if getattr(e, "errno", None) == 32:         # STALL: the image answers but carries no LOAD METER
                self.err = "the image has no LOAD METER (0xc0/0x57 STALLs)"
                return
        import os
        import subprocess
        if os.path.exists("/usr/local/bin/python3"):
            self.proc = subprocess.Popen(["/usr/local/bin/python3", str(HERE / "load_meter.py"), "--jsonl", "--interval", "0.25"],
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            try:
                self.rows.append(json.loads(line))
            except ValueError:
                pass

    def ok(self):
        return self.dev is not None or self.proc is not None

    def window(self, t0, t1):
        """Decoded readings taken between wall times t0 and t1."""
        if self.proc is not None:
            return [r for r in list(self.rows) if t0 <= r["t"] <= t1]
        return []

    def poll(self):
        """In-process mode: take a reading now (the feed does its own polling otherwise)."""
        if self.dev is None:
            return None
        try:
            r = self.lm.read(self.dev)
        except Exception:  # noqa: BLE001
            return None
        r["t"] = time.time()
        self.rows.append(r)
        return r

    def close(self):
        if self.proc is not None:
            self.proc.terminate()


def cmd_run(a):
    import numpy as np
    import ot_ladder as L
    import sounddevice as sd
    plan = json.loads((pathlib.Path(a.project) / "OCTABAM_MATRIX.json").read_text())
    entries = plan["layouts"]
    out_dir = pathlib.Path("out/hw/matrix") / a.label
    out_dir.mkdir(parents=True, exist_ok=True)
    import usb_transport_probe as U
    dev, nch = U.find_input(a.audio)
    fs = 44100

    lm = LmFeed()
    print("LOAD METER: " + ("reading" if lm.ok() else f"unavailable ({lm.err})"))

    seg, lock = {"chunks": None}, threading.Lock()   # the callback fills seg while a layout plays

    live = {"db": 0.0}

    def cb(indata, frames, t, status):
        live["db"] = float(_db(np.sqrt(np.mean(indata.astype(np.float64) ** 2))))
        with lock:
            if seg["chunks"] is not None:
                seg["chunks"].append(indata.copy())
    bpm = a.bpm or plan.get("bpm") or 121.0
    pc_ch = a.pc_channel or plan.get("pc_channel") or 1
    clock = L.Clock(bpm, a.midi)
    results, base_m, no_audio = [], None, 0
    sd_stream = sd.InputStream(device=dev, channels=nch, samplerate=fs, dtype="float32", callback=cb)
    try:
        with sd_stream:
            todo = parse_only(a.only, len(entries))
            if entries[0]["name"] == "BASE" and 0 not in todo:
                todo.insert(0, 0)                   # every other layout is judged against BASE
                print("BASE added to the run: layouts are compared with it")
            for i in todo:
                e = entries[i]
                if lm.dev is not None:
                    ok, why = lm.lm.healthy(lm.dev)
                    if not ok:
                        print(f"The unit is not running normally before {e['name']}: {why}. Stopping; power-cycle it.")
                        results.append({"slot": e["slot"], "program": e["program"], "name": e["name"], "flags": ["UNHEALTHY"],
                                        "metrics": {}, "load": None, "why": why})
                        break
                clock.stop(); ot_events.wait_stopped(clock.remote, 0.3)
                clock.pc_wait(pc_ch, e["program"], 0.8)
                t_settle = time.time()
                while live["db"] > SETTLE_DBFS and time.time() - t_settle < SETTLE_MAX_S:
                    time.sleep(0.25)  # waits for: audio level settling
                settled = round(time.time() - t_settle, 1)
                with lock:
                    seg["chunks"] = []
                clock.start()
                t_play = time.time()
                while time.time() - t_play < a.play:
                    lm.poll()
                    time.sleep(0.25)  # waits for: LOAD METER poll cadence
                clock.stop()
                time.sleep(a.tail)  # waits for: the audio tail
                with lock:
                    chunks, seg["chunks"] = seg["chunks"], None
                x = np.concatenate(chunks).astype(np.float64) if chunks else np.zeros((0, nch))
                m = measure(x, fs, a.play) if len(x) >= int((a.play + 0.5) * fs) else None
                allr = [r for r in lm.rows if t_play <= r["t"] <= t_play + a.play]
                readings = [r for r in allr if r["t"] >= t_play + LOAD_SKIP_S]
                import load_meter as _lmod
                load = _lmod.summarise(readings) if len(readings) > 1 else None
                series = [[round(r["t"] - t_play, 2), round(r["cf"]["share"] or 0, 4),
                           round(_lmod.ratio(r["dsp"]["core0"]) or 0, 4), round(_lmod.ratio(r["dsp"]["core1"]) or 0, 4),
                           round(r["cf"]["longest_us"], 1)]
                          for r in allr]
                if m is None:
                    flags, at = ["NO AUDIO CAPTURED"], None
                    if load and load.get("irq_per_s_median") and load["irq_per_s_median"] < OVERLOAD_IRQ_FRAC * NOMINAL_IRQ_PER_S:
                        flags.append("OVERLOAD")             # judge() is not reached without audio; the frame rate says it
                    elif load and (load.get("bad_records") or 0) > DROPS_BAD:
                        flags.append("DROPS")
                elif e["name"] == "BASE":
                    base_m, flags, at = m, [], None
                else:
                    flags, at = judge(m, base_m or m, load)
                row = {"slot": e["slot"], "program": e["program"], "name": e["name"], "flags": flags, "settle_s": settled,
                       "freeze_at_s": at, "load_series": series, "metrics": {k: v for k, v in (m or {}).items() if k != "alive"}, "load": load}
                results.append(row)
                print(f"{i:3d} PC{e['program']:3d} {e['name']:34s} "
                      + (f"rms {m['rms_db']:6.1f} hf {m['hf_db']:6.1f} clicks {m['clicks']:4d} " if m else "")
                      + (f"settle {settled:4.1f}s cf {100 * load['cf_share_max']:4.1f}% dsp {100 * load['dsp_core0_max']:4.1f}/{100 * load['dsp_core1_max']:4.1f}% " if load and load.get("windows") else "")
                      + (" ".join(flags) or "ok"), flush=True)
                if flags and x is not None and len(x):
                    wav = out_dir / f"{i:03d}_{re.sub(r'[^A-Za-z0-9]+', '_', e['name'])}.wav"
                    import wave
                    w = wave.open(str(wav), "wb")
                    w.setnchannels(x.shape[1]); w.setsampwidth(2); w.setframerate(fs)
                    w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
                    w.close()
                if "CRASH" in flags:
                    print("CRASH: the sequencer is stuck; power-cycle the unit. Stopping.")
                    break
                if "OVERLOAD" in flags:
                    print(f"OVERLOAD: the frame interrupt ran {load['irq_per_s_median']:.0f} a second (nominal {NOMINAL_IRQ_PER_S:.0f}) "
                          f"under {e['name']}: frames are being skipped and the unit has not recovered by itself "
                          f"(24 Oct 2026). Power-cycle it. Stopping.")
                    break
                no_audio = no_audio + 1 if "NO AUDIO CAPTURED" in flags else 0
                if no_audio >= 2:
                    print("NO AUDIO CAPTURED twice running: the unit or its USB stream is not delivering. Stopping.")
                    break
                if "FREEZE" in flags:
                    clock.stop(); ot_events.wait_stopped(clock.remote, 0.5)
    finally:
        clock.stop()
        clock.close()
        lm.close()
        (out_dir / "report.json").write_text(json.dumps({"remix": plan["remix"], "project": a.project, "args": vars(a),
                                                        "results": results}, indent=1))
    bad = [r for r in results if r["flags"]]
    print(f"{len(results)} layouts run, {len(bad)} flagged; report {out_dir / 'report.json'}")
    return 1 if bad else 0


# ---------------------------------------------------------------------------
# predict: per-core DSP busy of a layout nobody ran, from the single-effect runs
# ---------------------------------------------------------------------------
FRAME_COUNTS = 36256


def _variant_name(key, kind, knobs, mods):
    """The name `layouts` gave the single-effect run whose stamped bytes equal this spec's, or None."""
    import ot_project as P
    m = mods[key]
    want = P.module_defaults(m, knobs)
    for label, kn in _unique(m, _variants(m)):
        if P.module_defaults(m, kn) == want:
            return f"{key} {kind} {label}"
    return None


def build_costs(report_paths):
    """-> {"base": {core0, core1 busy fractions}, "base_slots": {slot: counts}, "costs": {name: {slot: counts over
    the report's own BASE}}}. BASE (layout 0) of the first report is the reference for the busy figures."""
    out = {"base": None, "base_slots": None, "costs": {}}
    for path in report_paths:
        res = json.loads(pathlib.Path(path).read_text())["results"]
        b = res[0]
        if b["name"] != "BASE" or not b.get("load"):
            sys.exit(f"{path}: layout 0 is not a BASE with LOAD METER figures")
        bs = {k: v["mean_counts"] for k, v in b["load"]["slots"].items()}
        if out["base"] is None:
            out["base"] = {"core0": b["load"]["dsp_core0_mean"], "core1": b["load"]["dsp_core1_mean"]}
            out["base_slots"] = bs
        for r in res[1:]:
            if not r.get("load"):
                continue
            sl = r["load"]["slots"]
            out["costs"][r["name"]] = {k: sl[k]["mean_counts"] - bs[k] for k in sl if k in bs}
    return out


def predict_layout(lo, table, mods):
    """-> (core0, core1 busy fractions, [what had no single-effect run]). Slot A<n> is track 4+n, B<n> track n
    (BusVerb's host T5 is A1 and BusDelay's T1 is B1 in LOAD METER's slots)."""
    busy = {"A": table["base"]["core0"], "B": table["base"]["core1"]}
    missing = []
    for t in range(1, 9):
        core, pos = ("A", t - 4) if t >= 5 else ("B", t)
        for idx, kind in ((0, "FX1"), (1, "FX2")):
            spec = lo[t][idx]
            if spec is None:
                continue
            name = _variant_name(spec[0], kind, spec[1], mods)
            c = table["costs"].get(name or "", {}).get(f"{core}{pos}.{kind}")
            if c is None:
                missing.append(f"{spec[0]} {kind} T{t}")
            else:
                busy[core] += c / FRAME_COUNTS
    return busy["A"], busy["B"], missing


def cmd_predict(a):
    from remix import registry
    mods = registry.modules()
    if "REVERB SERVER" in registry.remix(a.remix).modules:
        sys.exit("predict: the bus remix's FX2 slots hold its rig; only inserts and core layouts are predicted")
    table = build_costs(a.reports)
    lay = [l for l in layouts(a.remix, True, True) if l[1] in ("pair", "split")]
    rows = []
    for name, kind, lo in lay:
        c0, c1, miss = predict_layout(lo, table, mods)
        rows.append((max(c0, c1), name, kind, c0, c1, miss))
    rows.sort(key=lambda r: -r[0])
    over = [r for r in rows if not r[5] and r[0] >= 1.0]            # past the frame budget: skipped frames (24 Oct 2026)
    risky = [r for r in rows if not r[5] and a.threshold <= r[0] < 1.0]
    ok = [r for r in rows if not r[5] and r[0] < a.threshold]
    # a spread across the predicted range checks the sum on the unit, whatever the load
    step = max(len(ok) // a.validate, 1) if a.validate else 0
    validate = ok[::step][:a.validate] if a.validate else []
    chosen = {r[1]: ("RUN" if r in risky else "CHECK") for r in risky + validate}
    if a.include_overload:
        chosen.update({r[1]: "OVERLOAD" for r in over})
    print(f"{a.remix}: {len(rows)} combination layouts; {len(risky)} predicted at or above {100 * a.threshold:.0f} % "
          f"on a core (and under 100 %), {len(validate)} chosen across the rest to check the sum, {len(over)} predicted at 100 % or "
          f"more ({'included' if a.include_overload else 'left out: --include-overload'}), "
          f"{sum(1 for r in rows if r[5])} unpredictable (no single-effect run)")
    print(f"{'predicted core0/core1 %':>24}  {'':5} layout")
    for mx, name, kind, c0, c1, miss in rows[:a.top]:
        tag = "UNKNOWN" if miss else chosen.get(name, "OVER" if mx >= 1.0 else "skip")
        print(f"{100 * c0:11.1f} / {100 * c1:5.1f}  {tag:7s} {kind:5s} {name}")
    if a.select:
        pathlib.Path(a.select).write_text(json.dumps({"remix": a.remix, "threshold": a.threshold,
                                                       "run": list(chosen), "why": chosen}, indent=1))
        print(f"{len(chosen)} layouts written to {a.select} (proj --select)")
    return 0


# ---------------------------------------------------------------------------
# switch: a program change while the transport plays
# ---------------------------------------------------------------------------
SW_PC_AT_S, SW_RUN_S = 2.0, 14.0     # PC two seconds into play; the pattern ends at 8 s (64 steps, 120 BPM)
SW_GAP_MS, SW_GAP_DBFS = 40, -80.0   # a silence this long inside the switch window is a GAP
SW_CF_FACTOR, SW_CF_MIN_US = 1.25, 150.0
SW_DSP_POINTS = 0.03


def switch_metrics(rows, x, fs, t0):
    """rows: [{t, cf: {longest_us, ...}, dsp: {core0: {busy, period}, core1: {...}, bad}}] polled during the run,
    x: the audio (samples, channels) from t0 on. -> the switch's time, A's and B's steady levels, and what
    the window around the switch held (ColdFire longest run, DSP busy, bad records, the longest silence)."""
    import numpy as np
    import load_meter as lm
    t = np.array([r["t"] - t0 for r in rows])
    c0 = np.array([lm.ratio(r["dsp"]["core0"]) or 0.0 for r in rows])
    c1 = np.array([lm.ratio(r["dsp"]["core1"]) or 0.0 for r in rows])
    lon = np.array([r["cf"]["longest_us"] for r in rows])
    bad = np.array([r["dsp"]["bad"] for r in rows])
    a = (t >= SW_PC_AT_S - 1.0) & (t < SW_PC_AT_S)
    b = t >= t.max() - 2.0
    la, lb = float(np.median(c0[a])), float(np.median(c0[b]))
    nominal = 8.0                                    # START to the end of the 64-step pattern
    if abs(la - lb) >= 0.05:
        mid = (la + lb) / 2.0
        crossed = np.flatnonzero((t > SW_PC_AT_S) & ((c0 - mid) * np.sign(lb - la) > 0))
        t_sw = float(t[crossed[0]]) if len(crossed) else nominal
    else:
        t_sw = nominal
    w = (t >= t_sw - 0.3) & (t <= t_sw + 1.2)
    steady = ((t >= SW_PC_AT_S - 1.0) & (t < t_sw - 0.5)) | (t >= t_sw + 1.5)
    out = {"t_switch_s": round(t_sw, 2), "level_a": la, "level_b": lb, "readings": int(len(rows)), "window_readings": int(w.sum()),
           "longest_us_window": float(lon[w].max()) if w.any() else None,
           "longest_us_steady": float(lon[steady].max()) if steady.any() else None,
           "dsp_window_max": float(max(c0[w].max(), c1[w].max())) if w.any() else None,
           "dsp_steady_max": float(max(c0[steady].max(), c1[steady].max())) if steady.any() else None,
           "bad_in_window": int(bad[w].max() - bad[w].min()) if w.any() else None}
    if x is not None and len(x):
        step = int(0.020 * fs)
        i0, i1 = max(int((t_sw - 0.3) * fs), 0), min(int((t_sw + 1.2) * fs), len(x))
        seg = x[i0:i1, :2]
        n = len(seg) // step
        if n:
            lv = 20 * np.log10(np.maximum(np.sqrt((seg[:n * step].reshape(n, step, -1) ** 2).mean(axis=1)).max(axis=1), 1e-12))
            dead = lv < SW_GAP_DBFS
            run = best = 0
            for d in dead:
                run = run + 1 if d else 0
                best = max(best, run)
            out["longest_silence_ms"] = int(best * 20)
    return out


def switch_flags(m):
    f = []
    if m.get("longest_us_window") and m.get("longest_us_steady") and m["longest_us_window"] > max(SW_CF_FACTOR * m["longest_us_steady"], SW_CF_MIN_US):
        f.append("SPIKE_CF")
    if m.get("dsp_window_max") is not None and m.get("dsp_steady_max") is not None and m["dsp_window_max"] > m["dsp_steady_max"] + SW_DSP_POINTS:
        f.append("SPIKE_DSP")
    if (m.get("bad_in_window") or 0) > DROPS_BAD:
        f.append("DROPS")
    if (m.get("longest_silence_ms") or 0) >= SW_GAP_MS and m["level_a"] > 0 and m["level_b"] > 0:
        f.append("GAP")
    return f


def unapplied(results):
    """Indexes of the transitions whose DSP busy after the switch stays at the previous layout's figure
    (FAILURE_MODES.md, "Program changes left unapplied in a loader soak"). A layout's figure is the median of its
    DSP busy in the second before each switch away from it; a transition is unapplied when the median from 2.5 s
    after the switch is nearer the previous layout's figure than the new one's. Needs each layout to be left at
    least once, and layouts whose figures differ by more than the noise (about 0.3 point).
    Series rows are [t, cf us, dsp core 0, dsp core 1, ...]."""
    import statistics
    pre, post = {}, []
    for i, r in enumerate(results):
        s, t = r.get("series") or [], r.get("t_switch_s")
        before = [p[2] for p in s if t is not None and p[0] < t - 1]
        after = [p[2] for p in s if t is not None and p[0] > t + 2.5]
        if before and after:
            pre.setdefault(r["from"], []).append(statistics.median(before))
            post.append((i, r["from"], r["to"], statistics.median(after)))
    level = {k: statistics.median(v) for k, v in pre.items()}
    return [i for i, f, t, b in post if t in level and abs(b - level[t]) >= abs(b - level[f])]


def _switch_pairs(a, entries):
    """[(slot A, slot B)]: --pairs 'A:B,...', else from --report the lightest, heaviest and second heaviest layouts
    that did not drop frames: light to heavy, heavy to light, heavy to second heaviest and back."""
    if a.pairs:
        return [tuple(int(v) for v in p.split(":")) for p in a.pairs.split(",")]
    if not a.report:
        sys.exit("switch needs --pairs A:B,... or --report <report.json of a run of this project>")
    res = json.loads(pathlib.Path(a.report).read_text())["results"]
    good = [r for r in res if r.get("load") and not ({"OVERLOAD", "DROPS", "NO AUDIO CAPTURED", "CRASH"} & set(r["flags"]))]
    good.sort(key=lambda r: r["load"]["dsp_core0_mean"])
    base, heavy, heavy2 = good[0]["slot"], good[-1]["slot"], good[-2]["slot"]
    mid = good[len(good) // 2]["slot"]
    return [(base, heavy), (heavy, base), (heavy, heavy2), (heavy2, heavy), (mid, heavy), (heavy, mid)]


def cmd_switch(a):
    import numpy as np
    import ot_ladder as L
    import sounddevice as sd
    import load_meter
    import usb_transport_probe as U
    plan = json.loads((pathlib.Path(a.project) / "OCTABAM_MATRIX.json").read_text())
    entries = plan["layouts"]
    pairs = _switch_pairs(a, entries)
    out_dir = pathlib.Path("out/hw/matrix") / a.label
    out_dir.mkdir(parents=True, exist_ok=True)
    dev, nch = U.find_input(a.audio)
    usb = load_meter.libusb_device()
    fs = 44100
    bpm = a.bpm or plan.get("bpm") or 120.0
    pc_ch = a.pc_channel or plan.get("pc_channel") or 1
    clock = L.Clock(bpm, a.midi)
    seg, lock, rows, stop_poll = {"chunks": None}, threading.Lock(), [], threading.Event()

    def cb(indata, frames, t, status):
        with lock:
            if seg["chunks"] is not None:
                seg["chunks"].append(indata.copy())

    def poll():
        while not stop_poll.is_set():
            try:
                r = load_meter.read_fast(usb)
                r["t"] = time.time()
                rows.append(r)
            except Exception:  # noqa: BLE001
                time.sleep(0.05)  # waits for: retry back-off

    th = threading.Thread(target=poll, daemon=True)
    th.start()
    results = []
    expected = {}
    if a.report:
        for r in json.loads(pathlib.Path(a.report).read_text())["results"]:
            if r.get("load"):
                expected[r["slot"]] = r["load"]["dsp_core0_mean"]
    print(f"{len(pairs)} transitions: {pairs}")
    try:
        with sd.InputStream(device=dev, channels=nch, samplerate=fs, dtype="float32", callback=cb):
            for sa, sb in pairs:
                ea, eb = entries[sa], entries[sb]
                ok, why = load_meter.healthy(usb)
                if not ok:
                    print(f"The unit is not running normally: {why}. Stopping; power-cycle it.")
                    results.append({"from": ea["name"], "to": eb["name"], "flags": ["UNHEALTHY"], "why": why})
                    break
                clock.stop(); ot_events.wait_stopped(clock.remote, 0.5)
                clock.pc_wait(pc_ch, ea["program"], 1.0)
                n0 = len(rows)
                with lock:
                    seg["chunks"] = []
                t0 = time.time()
                clock.start()
                time.sleep(a.pc_at)  # waits for: the instant of the switch inside the run
                clock.pc(pc_ch, eb["program"])
                time.sleep(SW_RUN_S - a.pc_at)  # waits for: the rest of the run
                clock.stop()
                with lock:
                    chunks, seg["chunks"] = seg["chunks"], None
                x = np.concatenate(chunks).astype(np.float64) if chunks else None
                rr = [r for r in rows[n0:] if t0 <= r["t"] <= t0 + SW_RUN_S]
                row = {"from": ea["name"], "to": eb["name"], "slot_from": sa, "slot_to": sb}
                if len(rr) > 20:
                    m = switch_metrics(rr, x, fs, t0)
                    row.update(m)
                    row["flags"] = switch_flags(m)
                    row["rate_hz"] = round(len(rr) / SW_RUN_S, 1)
                    row["series"] = [[round(r["t"] - t0, 3), round(r["cf"]["longest_us"], 1), round(load_meter.ratio(r["dsp"]["core0"]) or 0, 4),
                                      round(load_meter.ratio(r["dsp"]["core1"]) or 0, 4), r["dsp"]["bad"], r["dsp"]["seq"]] for r in rr[::10]]
                    if x is not None and "GAP" in row["flags"]:
                        import wave
                        i0, i1 = int((m["t_switch_s"] - 1.0) * fs), int((m["t_switch_s"] + 2.0) * fs)
                        w = wave.open(str(out_dir / f"{sa:02d}_{sb:02d}_{len(results):02d}.wav"), "wb")
                        w.setnchannels(2); w.setsampwidth(2); w.setframerate(fs)
                        w.writeframes((np.clip(x[i0:i1, :2], -1, 1) * 32767).astype("<i2").tobytes())
                        w.close()
                    exp = expected.get(sb)
                    if exp is not None and abs(m["level_b"] - exp) > 0.05:
                        row["flags"].append("NO_SWITCH")        # the load after the change is not the target layout's
                    if m["level_a"] and expected.get(sa) is not None and abs(m["level_a"] - expected[sa]) > 0.05:
                        row["flags"].append("WRONG_START")
                else:
                    row["flags"] = ["NO READINGS"]
                results.append(row)
                print(f"{ea['name'][:34]:34s} -> {eb['name'][:34]:34s} switch at {row.get('t_switch_s', '-')} s  "
                      f"cf longest {row.get('longest_us_window', 0) or 0:5.0f}/{row.get('longest_us_steady', 0) or 0:5.0f} us (window/steady)  "
                      f"dsp max {100 * (row.get('dsp_window_max') or 0):4.1f}/{100 * (row.get('dsp_steady_max') or 0):4.1f} %  "
                      f"bad {row.get('bad_in_window')}  silence {row.get('longest_silence_ms')} ms  "
                      + (" ".join(row["flags"]) or "ok"), flush=True)
                if not rr or "DROPS" in row["flags"] and (row.get("bad_in_window") or 0) > 1000:
                    print("The unit looks overloaded or not answering; stopping. Power-cycle it.")
                    break
    finally:
        stop_poll.set()
        clock.stop()
        clock.close()
        (out_dir / "report.json").write_text(json.dumps({"remix": plan["remix"], "project": a.project, "mode": "switch",
                                                        "args": vars(a), "results": results}, indent=1))
    bad = unapplied(results)
    print(f"{len(results)} transitions; unapplied {len(bad)} {bad}; bad records {sum(r.get('bad_in_window') or 0 for r in results)}; "
          f"report {out_dir / 'report.json'}")
    return 1 if any(r["flags"] for r in results) else 0


def cmd_report(a):
    """A Markdown table from one or more report.json files: a row per layout, BASE-relative flags and load."""
    for path in a.reports:
        rep = json.loads(pathlib.Path(path).read_text())
        print(f"### {rep['remix']}  {pathlib.Path(rep['project']).name}  ({path})\n")
        print("| # | PC | layout | rms dB | tail dBFS | CF max % | DSP0 mean/max % | DSP1 mean/max % | flags |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in rep["results"]:
            m, l = r["metrics"], r["load"] or {}
            tail = m.get("tail_end_db")
            cf = f"{100 * l['cf_share_max']:.1f}" if l.get("windows") else "-"
            d0 = f"{100 * l['dsp_core0_mean']:.1f}/{100 * l['dsp_core0_max']:.1f}" if l.get("windows") else "-"
            d1 = f"{100 * l['dsp_core1_mean']:.1f}/{100 * l['dsp_core1_max']:.1f}" if l.get("windows") else "-"
            print(f"| {r['slot']} | {r['program']} | {r['name']} | {m.get('rms_db', float('nan')):.1f} | "
                  f"{'-' if tail is None else f'{tail:.1f}'} | {cf} | {d0} | {d1} | {' '.join(r['flags']) or 'ok'} |")
        print()
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("remix"); p.add_argument("--pairs", action="store_true")
    p.add_argument("--split", action="store_true", help="also one effect on tracks 1-4 and another on 5-8")
    p.add_argument("--play", type=float, default=12.0); p.add_argument("--tail", type=float, default=3.0)
    p = sub.add_parser("proj"); p.add_argument("src"); p.add_argument("dest"); p.add_argument("remix")
    p.add_argument("--pairs", action="store_true"); p.add_argument("--pattern", default="A2")
    p.add_argument("--split", action="store_true", help="include the split layouts (needs the same flag as `predict`)")
    p.add_argument("--select", help="a JSON from `predict --select`: only those layouts (plus BASE)")
    p.add_argument("--stimuli", default="", help="ot_stimuli names, comma-separated: played on FLEX slots 1..N instead of SRC's pattern")
    p.add_argument("--stim-tracks", default="1-8", help="tracks that play them, round-robin (default 1-8)")
    p.add_argument("--clean", action="store_true", help="SRC is a fresh unit-created project: rebuild all 16 banks from its first "
                   "pattern and part (needs --stimuli); refused if `audit` finds SRC edited")
    p.add_argument("--allow-dirty-template", action="store_true", help="with --clean: use SRC although audit finds it edited")
    p.add_argument("--pc-channel", type=int, default=1, help="MIDI channel (1-16) the project receives program change on")
    p.add_argument("--setting", action="append", default=[], metavar="KEY=INT",
                   help="another [SETTINGS] key to stamp, e.g. MAIN_LEVEL=64 (repeatable); the keys are in project.work")
    p = sub.add_parser("run"); p.add_argument("project"); p.add_argument("label")
    p.add_argument("--midi", default="Elektron Octatrack DPS-1"); p.add_argument("--audio", default="Octatrack")
    p.add_argument("--pc-channel", type=int, default=None, help="default: the project's (see proj), else 1")
    p.add_argument("--bpm", type=float, default=None, help="default: the project's (120 for a stimuli project), else 121")
    p.add_argument("--play", type=float, default=12.0); p.add_argument("--tail", type=float, default=3.0)
    p.add_argument("--only", default="")
    p = sub.add_parser("audit"); p.add_argument("project")
    p = sub.add_parser("predict"); p.add_argument("remix")
    p.add_argument("--reports", nargs="+", required=True, help="report.json files of the single-effect runs, BASE first")
    p.add_argument("--threshold", type=float, default=0.85, help="predicted core busy fraction above which a layout is run (0.85)")
    p.add_argument("--validate", type=int, default=6, help="layouts picked across the rest to check the sum on the unit (6)")
    p.add_argument("--top", type=int, default=25); p.add_argument("--select", help="write the chosen layouts here")
    p.add_argument("--include-overload", action="store_true",
                   help="also pick layouts predicted at 100 %% or more: the first one the unit ran (105 %%) left it with the frame "
                        "interrupt at half rate until a power-cycle")
    p = sub.add_parser("switch"); p.add_argument("project"); p.add_argument("label")
    p.add_argument("--pairs", help="transitions as slotA:slotB,... (layout numbers in the project)")
    p.add_argument("--report", help="a report.json of a run of this project: pick light, heavy and second-heaviest from it")
    p.add_argument("--midi", default="Elektron Octatrack DPS-1"); p.add_argument("--audio", default="Octatrack")
    p.add_argument("--pc-channel", type=int, default=None); p.add_argument("--bpm", type=float, default=None)
    p.add_argument("--pc-at", type=float, default=SW_PC_AT_S, help="seconds after START at which the program change is sent (2)")
    p = sub.add_parser("report"); p.add_argument("reports", nargs="+", help="report.json files from `run`")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"plan": cmd_plan, "proj": cmd_proj, "run": cmd_run, "selftest": cmd_selftest, "audit": cmd_audit, "report": cmd_report, "predict": cmd_predict, "switch": cmd_switch}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)
