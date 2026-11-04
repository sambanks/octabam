#!/usr/bin/env python3
"""SCALES: the catalogue, the chooser, ARP SETUP's KEY, the snapped notes and
the CHROMATIC trig keys.

The model here is built from music, not from the module's tables: each
family's modes are the rotations of its parent scale's semitones (MAJOR,
MELODIC MINOR, HARMONIC MINOR, HARMONIC MAJOR, DOUBLE HARMONIC, PENTATONIC),
the others are their semitone lists; SCALE QUANTIZER's 24 scales are the
lists of its README. The KEY values are stock's (1..24: tonic (v-1)/2,
Minor when v is even) and MIDI SCALES' (25..84: DOR PHR LYD MIX LOC per
tonic).

1. The linked code (unicorn, the image's own bytes): every ID's mask,
   family, names; sc_snap for every ID x tonic x note (nearest, ties
   downward); sc_track for every KEY x sc_lib ID (an ID holds while the
   KEY is OFF or the Major / Minor that stands for it); the installed output
   detour on eight tracks; the installed encoder's change for every KEY x
   ID x movement; the formatter's two strings.
2. Under the port, MKI and MKII:
   - the trig LEDs (panel stream) for every KEY 0..84, every ID 8..52 on a
     tonic, SCALE QUANTIZER's SCALE / ROOT on an audio track when the remix
     has it, a KEY / ROOT turned while CHROMATIC is shown;
   - the chooser from ARP SETUP's keys: encoder F pushed opens its window on
     the families, DOWN / YES pick each of the 52 scales, RIGHT enters a
     family and LEFT goes back; the KEY in the Part, the CS1 mirror and
     the live copy, the ID in sc_lib, the setup record's +0x12 untouched;
     reopened, YES YES keeps the scale; NO keeps it; F turned while pushed
     opens nothing; CTRL1 SETUP's YES keeps the scale.
   - scales.work (MKII): a scale picked and SAVE PROJECT write scales.work
     and scales.strd (header, CRC-32, the ID in bank 1 Part 1 track 1); the
     saved card booted again gives the ID back; a run with no save writes
     no scales.work.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "panel"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
from panel_link import PanelLink  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIVE = 0x46c76de0                         # MIDI track t's live setup record: + 68 * t
KEY, EXT = 0x11, 0x12                     # EXT: a native byte SCALES must leave alone (MIDI HARMONY's)
BANK0 = 0x400e21e0
PART_SETUP = 0x400e21e0 + 0x8f262         # bank 1, Part 1, track 1's setup record
CS1_SETUP = 0x100a53b0
NV_SCALE, NV_ROOT = 0x100b14ec, 0x100b14ee  # SCALE QUANTIZER's SCALE (0 OFF, 1..24) and ROOT (0..11)
QZ_SCALES = ((0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 9, 10), (0, 1, 3, 5, 7, 8, 10),
             (0, 2, 4, 6, 7, 9, 11), (0, 2, 4, 5, 7, 9, 10), (0, 2, 3, 5, 7, 8, 10),
             (0, 1, 3, 5, 6, 8, 10), (0, 3, 5, 7, 10), (0, 2, 4, 7, 9), (0, 2, 3, 5, 7, 9, 11),
             (0, 2, 3, 5, 7, 8, 11), (0, 2, 4, 6, 8, 10), (0, 3, 5, 6, 7, 10),
             (0, 1, 4, 5, 7, 8, 10), (0, 2, 3, 5, 6, 8, 9, 11), (0, 1, 3, 4, 6, 7, 9, 10),
             (0, 2, 3, 6, 7, 8, 11), (0, 2, 3, 7, 8), (0, 1, 5, 7, 10), (0, 1, 5, 6, 10),
             (0, 1, 3, 7, 8), (0, 1, 4, 5, 7, 8, 11), (0, 1, 3, 4, 6, 8, 10),
             (0, 2, 4, 6, 7, 9, 10))       # SCALE 1..24, upstream/quantizer/README.md's table


def modes(parent, names):
    """A parent scale's modes: mode k starts on its k-th degree."""
    return [(name, short, tuple(sorted((p - parent[k]) % 12 for p in parent)))
            for k, (name, short) in enumerate(names)]


FAMILIES = (
    ("MAJOR", modes((0, 2, 4, 5, 7, 9, 11), (
        ("IONIAN (MAJOR)", "MAJ"), ("DORIAN", "DOR"), ("PHRYGIAN", "PHR"), ("LYDIAN", "LYD"),
        ("MIXOLYDIAN", "MIX"), ("AEOLIAN (MINOR)", "MIN"), ("LOCRIAN", "LOC")))),
    ("MELODIC MINOR", modes((0, 2, 3, 5, 7, 9, 11), (
        ("MELODIC MINOR", "MMIN"), ("DORIAN b2", "DOb2"), ("LYDIAN AUGMENTED", "LYD+"),
        ("LYDIAN DOMINANT", "LYDD"), ("MIXOLYDIAN b6", "MXb6"), ("LOCRIAN #2", "LC#2"),
        ("SUPERLOCRIAN", "ALT")))),
    ("HARMONIC MINOR", modes((0, 2, 3, 5, 7, 8, 11), (
        ("HARMONIC MINOR", "HMIN"), ("LOCRIAN #6", "LC#6"), ("IONIAN #5", "IO#5"),
        ("DORIAN #4", "DO#4"), ("PHRYGIAN DOMINANT", "PHRD"), ("LYDIAN #2", "LY#2"),
        ("ALTERED bb7", "ALT7")))),
    ("HARMONIC MAJOR", modes((0, 2, 4, 5, 7, 8, 11), (
        ("HARMONIC MAJOR", "HMAJ"), ("DORIAN b5", "DOb5"), ("PHRYGIAN b4", "PHb4"),
        ("LYDIAN b3", "LYb3"), ("MIXOLYDIAN b2", "MXb2"), ("LYDIAN AUG #2", "LA#2"),
        ("LOCRIAN bb7", "LCb7")))),
    ("DOUBLE HARMONIC", modes((0, 1, 4, 5, 7, 8, 11), (
        ("DOUBLE HARMONIC", "DHAR"), ("LYDIAN #2 #6", "L#26"), ("ULTRAPHRYGIAN", "UPHR"),
        ("HUNGARIAN MINOR", "HUNG"), ("ORIENTAL", "ORNT"), ("IONIAN #2 #5", "I#25"),
        ("LOCRIAN bb3 bb7", "LC37")))),
    ("PENTATONIC", modes((0, 2, 4, 7, 9), (
        ("MAJOR PENTATONIC", "PMAJ"), ("EGYPTIAN", "EGYP"), ("MAN GONG", "MGNG"),
        ("RITUSEN", "RITU"), ("MINOR PENTATONIC", "PMIN")))),
    ("BLUES", [("BLUES", "BLUS", (0, 3, 5, 6, 7, 10)), ("MAJOR BLUES", "BMAJ", (0, 2, 3, 4, 7, 9))]),
    ("JAPANESE", [("HIRAJOSHI", "HIRA", (0, 2, 3, 7, 8)), ("IN-SEN", "INSN", (0, 1, 5, 7, 10)),
                  ("IWATO", "IWAT", (0, 1, 5, 6, 10)), ("KUMOI", "KUMO", (0, 2, 3, 7, 9)),
                  ("PELOG", "PELG", (0, 1, 3, 7, 8))]),
    ("SYMMETRIC", [("WHOLE TONE", "WHOL", (0, 2, 4, 6, 8, 10)),
                   ("DIMINISHED W-H", "DWH", (0, 2, 3, 5, 6, 8, 9, 11)),
                   ("DIMINISHED H-W", "DHW", (0, 1, 3, 4, 6, 7, 9, 10)),
                   ("AUGMENTED", "AUG", (0, 3, 4, 7, 8, 11)),
                   ("CHROMATIC", "CHRM", tuple(range(12)))]),
)
# ID -> (family index, row, name, short, semitones); IDs from 1 in the chooser's order
CATALOGUE = {}
for _f, (_fam, _rows) in enumerate(FAMILIES):
    for _r, (_name, _short, _notes) in enumerate(_rows):
        CATALOGUE[len(CATALOGUE) + 1] = (_f, _r, _name, _short, _notes)
DIATONIC = {"MAJ": 0, "DOR": 1, "PHR": 2, "LYD": 3, "MIX": 4, "MIN": 5, "LOC": 6}
ADDED = ("DOR", "PHR", "LYD", "MIX", "LOC")
TONICS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def mask(notes):
    return sum(1 << p for p in notes)


def decode(key):
    """KEY -> (tonic, ID of its own mode); None for OFF or past 84."""
    if key == 0 or key > 84:
        return None
    if key <= 24:
        return (key - 1) // 2, (1, 6)[(key - 1) % 2]
    return (key - 25) // 5, DIATONIC[ADDED[(key - 25) % 5]] + 1


def encode(tonic, ident):
    """(tonic, ID) -> the KEY the module writes: the ID's own mode for 1..7,
    else Minor when the scale has a minor third and no major one, else Major."""
    if ident > 7:
        notes = CATALOGUE[ident][4]
        ident = 6 if 3 in notes and 4 not in notes else 1
    m = ident - 1
    if m in (0, 5):
        return 1 + 2 * tonic + (m == 5)
    return 25 + 5 * tonic + (1, 2, 3, 4, 6).index(m)


def stands(ident):
    """The KEY mode's ID that stands for a scale past the seven: Minor (6) for a
    minor third and no major one, else Major (1)."""
    notes = CATALOGUE[ident][4]
    return 6 if 3 in notes and 4 not in notes else 1


def holds(key, ext):
    """An ID in sc_lib holds while the KEY is OFF or the mode that stands for it."""
    if not 8 <= ext <= len(CATALOGUE):
        return False
    d = decode(key)
    return key == 0 or (d is not None and d[1] == stands(ext))


def track_scale(key, ext):
    """What a MIDI track plays: (tonic, ID) or None."""
    d = decode(key)
    if d is None:
        return None
    return d[0], ext if holds(key, ext) else d[1]


def snap(note, tonic, ident):
    notes = CATALOGUE[ident][4]
    inside = [n for n in range(128) if (n - tonic) % 12 in notes]
    return min(inside, key=lambda n: (abs(n - note), n))


# ---- 1. the linked code ------------------------------------------------------

def machine_gate(remix):
    import midi_scales_machine as h
    from unicorn.m68k_const import UC_M68K_REG_A0, UC_M68K_REG_D5, UC_M68K_REG_D7, UC_M68K_REG_A2
    from unicorn.m68k_const import UC_M68K_REG_A6

    def symbols():
        raw = subprocess.check_output(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                                      text=True)
        return {n: int(a, 16) for a, n in re.findall(r"^([0-9a-f]+) [TtBbDd] ((?:sc|kl)_\w+)$", raw, re.M)}

    m = h.Machine(symbol_loader=symbols)
    u = m.uc
    bad = []
    # bank 1, Part 1 for the UI and both engines (STORE's contexts 0); a track's
    # KEY in the native Part (STORE reads it) and the live copy, its ID in sc_lib.
    u.mem_write(0x46c82456, BANK0.to_bytes(4, "big"))
    u.mem_write(0x100b14cf, b"\0")
    u.mem_write(0x80000002, b"\0")
    u.mem_write(0x80001828, b"\0\0")
    u.mem_write(0x8000666e, b"\xff" * 16)
    lib = m.sym["sc_lib"]

    def set_track(track, key, ext):
        m.set_key(track, key)
        u.mem_write(BANK0 + 0x8f262 + 36 * track + KEY, bytes((key,)))
        u.mem_write(lib + track, bytes((ext,)))
    for site, name in ((0x4007a3e2, "sc_encoder"), (0x4009fb58, "sc_output"),
                       (0x400442e2, "kl_chromatic"), (0x40056ab8, "kl_tick")):
        if bytes(u.mem_read(site, 6)) != b"\x4e\xf9" + m.sym[name].to_bytes(4, "big"):
            bad.append(f"{site:#x} is not jmp {name}")
    if int.from_bytes(u.mem_read(0x400d40c6, 4), "big") != m.sym["sc_format"]:
        bad.append("the KEY formatter is not sc_format")
    if int.from_bytes(u.mem_read(0x400d4096, 4), "big") != 85:
        bad.append("the KEY count is not 85")
    if m.call("sc_count") != len(CATALOGUE):
        bad.append(f"sc_count {m.call('sc_count')} != {len(CATALOGUE)}")

    def text(addr, n=24):
        raw = bytes(u.mem_read(addr, n))
        return raw.split(b"\0")[0].decode()

    for ident, (fam, _row, name, short, notes) in CATALOGUE.items():
        if m.call("sc_mask", ident) != mask(notes):
            bad.append(f"ID {ident} {name}: mask {m.call('sc_mask', ident):#05x} != {mask(notes):#05x}")
        if m.call("sc_family", ident) != fam:
            bad.append(f"ID {ident}: family")
        m.call("sc_name", ident)
        if text(u.reg_read(UC_M68K_REG_A0)) != name:
            bad.append(f"ID {ident}: name {text(u.reg_read(UC_M68K_REG_A0))!r}")
        m.call("sc_short", ident)
        if text(u.reg_read(UC_M68K_REG_A0), 4) != short:
            bad.append(f"ID {ident}: short {text(u.reg_read(UC_M68K_REG_A0), 4)!r}")
    for ident in (0, len(CATALOGUE) + 1, 127, 255, 0xffffffff):
        if m.call("sc_mask", ident) != 0 or m.call("sc_family", ident) != 0xffffffff:
            bad.append(f"ID {ident:#x} is not refused")
        if m.call("sc_name", ident) != 0:
            bad.append(f"sc_name {ident:#x} is not refused")
    if set(map(tuple, QZ_SCALES)) - {v[4] for v in CATALOGUE.values()}:
        bad.append("a SCALE QUANTIZER scale is missing from the catalogue")
    order = sorted(CATALOGUE, key=lambda i: CATALOGUE[i][:2])
    if list(u.mem_read(m.sym["sc_order"], len(order))) != order:
        bad.append("sc_order is not the model's chooser order")
    print(f"  [{'FAIL' if bad else 'ok'}] catalogue: {len(CATALOGUE)} IDs in {len(FAMILIES)} families, "
          f"masks, families, names, refusals, the chooser's order; SCALE QUANTIZER's 24 included")

    # The chooser's rows come from sc_order, not from the IDs: with every
    # family's IDs reversed in it, entering a family finds the shown ID on its
    # reversed row and YES gives that row's ID (no window: sc_draw draws nothing).
    n_bad = len(bad)
    rev = []
    for f in range(len(FAMILIES)):
        rev += reversed([i for i in order if CATALOGUE[i][0] == f])
    u.mem_write(m.sym["sc_order"], bytes(rev))
    got = m.scratch + 0x410                                   # the client stores the ID there
    u.mem_write(m.scratch + 0x400, b"\x23\xc0" + got.to_bytes(4, "big") + b"\x4e\x75")
    def put(name, v):
        u.mem_write(m.sym[name], (v & 0xffffffff).to_bytes(4, "big"))
    def get(name):
        return int.from_bytes(u.mem_read(m.sym[name], 4), "big")
    put("sc_win", 0)
    for ident, (fam, row, *_rest) in CATALOGUE.items():
        size = sum(1 for v in CATALOGUE.values() if v[0] == fam)
        put("sc_level", 0); put("sc_sel", fam); put("sc_top", 0); put("sc_shown", ident)
        m.call("sc_enter")
        if get("sc_level") != 1 or get("sc_fam") != fam or get("sc_sel") != size - 1 - row:
            bad.append(f"ID {ident}: entered on row {get('sc_sel')}, not {size - 1 - row}")
        put("sc_client", m.scratch + 0x400); put("sc_sel", row); u.mem_write(got, bytes(4))
        m.call("sc_key_yes")
        want = rev[sum(1 for v in CATALOGUE.values() if v[0] < fam) + row]
        if int.from_bytes(u.mem_read(got, 4), "big") != want:
            bad.append(f"family {fam} row {row}: YES gave {int.from_bytes(u.mem_read(got, 4), 'big')}, not {want}")
    put("sc_shown", 0)                                        # an ID in no family: the first row
    put("sc_level", 0); put("sc_sel", 0); m.call("sc_enter")
    if get("sc_sel") != 0:
        bad.append("an ID in no family does not open on the first row")
    u.mem_write(m.sym["sc_order"], bytes(order))
    put("sc_client", 0); put("sc_level", 0); put("sc_sel", 0); put("sc_top", 0)
    print(f"  [{'FAIL' if len(bad) > n_bad else 'ok'}] chooser order: every family reversed in "
          f"sc_order, each ID entered on its reversed row and picked back by YES")

    snaps = 0
    for ident in CATALOGUE:
        for tonic in range(12):
            for note in range(128):
                got = m.call("sc_snap", note, (ident << 4) | tonic)
                if got != snap(note, tonic, ident):
                    bad.append(f"sc_snap {note} in {TONICS[tonic]} ID {ident}: {got}")
                snaps += 1
    print(f"  [{'FAIL' if bad else 'ok'}] sc_snap: {snaps} notes (every ID x tonic x note)")

    for key in range(256):
        for ext in (0, 1, 7, 8, 19, 52, 53, 127, 255):
            set_track(2, key, ext)
            got = m.call("sc_track", 2)
            want = track_scale(key, ext)
            want = 0xffffffff if want is None else (want[1] << 4) | want[0]
            if got != want:
                bad.append(f"sc_track KEY {key} ID {ext}: {got:#x} != {want:#x}")

    installed = 0
    for track in range(8):
        for key in (0, 1, 2, 24, 25, 30, 84, 85):
            for ext in (0, 8, 41, 47, 53):
                set_track(track, key, ext)
                for note in (0, 37, 60, 61, 66, 127):
                    u.mem_write(m.scratch - 1, bytes((0xa5, note, 0xa5)))
                    stock = key == 0 or key > 84 or not holds(key, ext) and key <= 24
                    for flag in (0, 1):     # stock's -64(fp): a KEY to quantize
                        u.mem_write(m.scratch + 0x100 - 64, flag.to_bytes(4, "big"))
                        dest = (0x4009fb5e if flag else 0x4009fb80) if stock else 0x4009fb80
                        m.call("sc_output", 0x12345678, 0xabcdef01, stop=dest,
                               regs={UC_M68K_REG_D7: track, UC_M68K_REG_A2: m.scratch,
                                     UC_M68K_REG_A6: m.scratch + 0x100})
                        ts = track_scale(key, ext)
                        want = note if stock or ts is None else snap(note, *ts)
                        if bytes(u.mem_read(m.scratch - 1, 3)) != bytes((0xa5, want, 0xa5)):
                            bad.append(f"output t{track} KEY {key} ID {ext} note {note}")
                        if m.uc.reg_read(h.UC_M68K_REG_D0) != 0x12345678:
                            bad.append("output: d0 not kept")
                        installed += 1
    print(f"  [{'FAIL' if bad else 'ok'}] sc_track: 256 KEY x 9 IDs; output: {installed} notes on 8 tracks")

    turns = 0
    for key in range(85):
        for ext in (0, 8, 15, 36, 41):
            for move in (-12, -4, -1, 0, 1, 4, 12):
                u.mem_write(0x100b14cc, b"\0")
                set_track(0, key, ext)
                u.mem_write(0x46c7d244 + 5 * 20, bytes(4))      # the accumulator's state
                m.call("sc_encoder", 5, stop=0x4007a3ea,
                                regs={UC_M68K_REG_D5: move & 0xffffffff})
                change = u.reg_read(UC_M68K_REG_D5)
                change = change - (1 << 32) if change & 0x80000000 else change
                d = decode(key)
                step = (move >= 4) - (move <= -4)
                new = max(0, min(12, (0 if d is None else d[0] + 1) + step))
                if new == 0:
                    want = 0
                elif d is not None:
                    want = encode(new - 1, d[1])                      # the KEY's mode kept
                else:
                    want = encode(new - 1, ext if holds(0, ext) else 1)  # from OFF: sc_lib's scale
                if key + change != want:
                    bad.append(f"encoder KEY {key} ID {ext} move {move}: {key + change} != {want}")
                turns += 1
    for slot in range(5):
        m.call("sc_encoder", slot, stop=0x4007a4cc)
    print(f"  [{'FAIL' if bad else 'ok'}] encoder F: {turns} turns (KEY x ID x movement), "
          f"the other encoders stock's")

    buf = m.scratch + 0x200
    for key in (0, 1, 2, 23, 25, 84):
        for ext in (0, 8, 47, 52):
            u.mem_write(0x100b14cc, b"\3")
            set_track(3, key, ext)
            u.mem_write(buf - 4, b"\xa5" * 18)
            u.mem_write(m.stack + 4, buf.to_bytes(4, "big"))
            m.call("sc_format")
            raw = bytes(u.mem_read(buf - 4, 18))
            ts = track_scale(key, ext)
            want = (b"OFF\0\0", b"\0" * 5) if ts is None else (
                TONICS[ts[0]].encode().ljust(5, b"\0"), CATALOGUE[ts[1]][3].encode().ljust(5, b"\0"))
            if raw[:4] != b"\xa5" * 4 or raw[14:] != b"\xa5" * 4 or (raw[4:9], raw[9:14]) != want:
                bad.append(f"formatter KEY {key} ID {ext}: {raw.hex()}")
    print(f"  [{'FAIL' if bad else 'ok'}] formatter: tonic and short name, bounded to 10 bytes")
    for line in bad[:12]:
        print(f"      {line}")
    return bool(bad)


# ---- 2. under the port -------------------------------------------------------

def keyboard(tonic, notes, key1):
    """Key k sounds pitch class key1 + k: the tonic yellow, the scale red, the rest dark."""
    out = ""
    for k in range(16):
        degree = (key1 + k - tonic) % 12
        out += "Y" if degree == 0 else "R" if degree in notes else "."
    return out


def expected_midi(key, ext):
    ts = track_scale(key, ext)
    if ts is None:
        return keyboard(0, CATALOGUE[1][4], 0)          # OFF: stock's C major
    return keyboard(ts[0], CATALOGUE[ts[1]][4], 0)      # key 1 = C on a MIDI track


def expected_audio(qz_scale, root):
    if not qz_scale:
        return keyboard(0, CATALOGUE[1][4], 0)          # SCALE OFF: stock
    return keyboard(root, set(QZ_SCALES[qz_scale - 1]), root)


def shown(stream):
    link = PanelLink()
    link.feed(stream.read_bytes())
    colours = {(15, 15): "Y", (15, 0): "R", (0, 0): ".", (0, 15): "G"}
    return "".join(colours.get((link.leds.get(2 * k, 0), link.leds.get(2 * k + 1, 0)), "?")
                   for k in range(16))


class Script:
    def __init__(self):
        self.lines, self.t = [], 1500

    def send(self, text, gap=150):
        self.lines.append(f"{self.t} {text}")
        self.t += gap

    def tap(self, key, gap=300):
        self.send(f"key {key:#x} down", 40)
        self.send(f"key {key:#x} up", gap)

    def write(self, path):
        self.send("quit")
        path.write_text("\n".join(self.lines) + "\n")


def chromatic(midi, later=()):
    s = Script()
    s.tap(0x32)
    if midi:
        s.tap(0x35)                       # MIDI mode
    s.send("key 0x2d down")
    s.tap(0x20)                           # the trig-mode list
    s.tap(0x20)                           # CHROMATIC
    s.send("key 0x2d up", 1500)
    for line in later:                    # after CHROMATIC is drawn, no key after it
        s.send(line, 2000)
    return s


def arp(s):
    s.tap(0x32)
    s.tap(0x35)                           # MIDI mode
    s.send("key 0x2d down")
    s.tap(0x23)                           # FUNC + AMP: ARP SETUP
    s.send("key 0x2d up", 800)


def choose(s, ident):
    """F pushed, the family's row, YES, the scale's row, YES (the lists open on row 0 from OFF)."""
    fam, row = CATALOGUE[ident][:2]
    s.tap(0x3d, 600)
    for _ in range(fam):
        s.tap(0x20)
    s.tap(0x31, 600)
    for _ in range(row):
        s.tap(0x20)
    s.tap(0x31, 800)


def chooser_runs(out):
    """(tag, script, want (KEY, sc_lib's ID), want the list open)."""
    runs = []
    for ident in CATALOGUE:
        s = Script()
        arp(s)
        choose(s, ident)
        s.write(out / f"choose-{ident}.script")
        runs.append((f"choose-{ident}", (encode(0, ident), 0 if ident <= 7 else ident), False))
    s = Script()                          # reopened on the scale: YES YES keeps it
    arp(s)
    choose(s, 32)
    s.tap(0x3d, 600)
    s.tap(0x31, 600)
    s.tap(0x31, 800)
    s.write(out / "reopen.script")
    runs.append(("reopen", (encode(0, 32), 32), False))
    s = Script()                          # NO closes, nothing written
    arp(s)
    choose(s, 41)
    s.tap(0x3d, 600)
    s.tap(0x20)
    s.tap(0x32, 800)
    s.write(out / "no.script")
    runs.append(("no", (encode(0, 41), 41), False))
    s = Script()                          # F turned while pushed: a quick edit, no list
    arp(s)
    s.send("key 0x3d down", 300)
    s.send("enc 5 4", 300)
    s.send("key 0x3d up", 800)
    s.write(out / "turned.script")
    runs.append(("turned", (1, 0), False))
    s = Script()                          # the window stays open after a plain push
    arp(s)
    s.tap(0x3d, 800)
    s.write(out / "open.script")
    runs.append(("open", (0, 0), True))
    s = Script()                          # RIGHT enters a family, LEFT goes back on it
    arp(s)
    s.tap(0x3d, 600)
    s.tap(0x20)
    s.tap(0x20)
    s.tap(0x21, 600)                      # HARMONIC MINOR's scales
    s.tap(0x20)
    s.tap(0x34, 600)                      # back on HARMONIC MINOR
    for _ in range(3):
        s.tap(0x20)                       # PENTATONIC
    s.tap(0x21, 600)
    for _ in range(4):
        s.tap(0x20)                       # MINOR PENTATONIC
    s.tap(0x31, 800)
    s.write(out / "rightleft.script")
    runs.append(("rightleft", (encode(0, 40), 40), False))
    s = Script()                          # CTRL1 SETUP's YES (its commit-all writes +0x12..+0x17)
    arp(s)
    choose(s, 47)
    s.send("key 0x2d down")
    s.tap(0x23)                           # close ARP SETUP
    s.send("key 0x2d up", 600)
    s.send("key 0x2d down")
    s.tap(0x25)                           # FUNC + FX1: CTRL1 SETUP
    s.send("key 0x2d up", 800)
    s.tap(0x31, 800)
    s.write(out / "ctrl1.script")
    runs.append(("ctrl1", (encode(0, 47), 47), False))
    return runs


def main():
    remix = sys.argv[1]
    mods = registry.remix(remix).modules
    if "SCALES" not in mods:
        return 0
    quantizer = "SCALE QUANTIZER" in mods
    out = ROOT / "out/scales"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, env=env,
                   stdout=subprocess.DEVNULL, check=True)
    fails = machine_gate(remix)

    image = out / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    empty = out / "empty-project"
    empty.mkdir()
    card = out / "card.img"
    subprocess.run([str(ROOT / ".venv/bin/python3"), "tools/emu/ot_emu/stage_card.py",
                    str(empty), "SCSET", "SCPRJ", "--out", str(card)], cwd=ROOT,
                   stdout=subprocess.DEVNULL, check=True)
    chromatic(True).write(out / "midi.script")
    chromatic(False).write(out / "audio.script")
    chromatic(True, (f"poke {LIVE + KEY:#x}=6;{PART_SETUP + KEY:#x}=6",)).write(out / "midi-later.script")  # C MAJ -> D MIN
    chromatic(False, (f"poke {NV_ROOT:#x}=9",)).write(out / "audio-later.script")        # MINOR on C -> on A
    modes = "0x80000012=00;0x80000013=00;0x80000014=00;0x80000015=00"
    nm = subprocess.check_output(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")], text=True)
    lib = int(re.search(r"^([0-9a-f]+) [Bb] sc_lib$", nm, re.M).group(1), 16)

    def lane(key, ext):
        """Track 1's KEY (the live copy and the native Part, which STORE reads) and its ID."""
        return f"{LIVE + KEY:#x}={key};{PART_SETUP + KEY:#x}={key};{lib:#x}={ext}"

    leds = [(f"midi-{k}", "midi", (k, 0), lane(k, 0)) for k in range(85)]
    leds += [(f"midi-id{i}", "midi", (encode(i % 12, i), i), lane(encode(i % 12, i), i))
             for i in CATALOGUE if i > 7]
    if quantizer:
        audio = sorted({(sc, r) for sc in range(25) for r in (0, 9)} | {(6, r) for r in range(12)})
        leds += [(f"audio-{sc}-{r}", "audio", (sc, r), f"{NV_SCALE:#x}={sc};{NV_ROOT:#x}={r}")
                 for sc, r in audio]
    else:
        leds.append(("audio", "audio", (0, 0), lane(6, 0)))
    leds.append(("refresh-midi", "midi-later", (6, 0), lane(1, 0)))
    if quantizer:
        leds.append(("refresh-audio", "audio-later", (6, 9), f"{NV_SCALE:#x}={6};{NV_ROOT:#x}=0"))
    chooser = chooser_runs(out)
    window = int(re.search(r"^([0-9a-f]+) [Dd] sc_win$", nm, re.M).group(1), 16)
    dumps = (f"{LIVE:#x},{0x24}", f"{PART_SETUP:#x},{0x24}", f"{CS1_SETUP:#x},{0x24}",
             f"{window:#x},4", "0x46c82456,4", "0x100b14cf,1", f"{lib:#x},1")
    for model in ("mki", "mkii"):
        cmd = [str(ROOT / "out/emu/ot_emu"), "--image", str(image), "--card", str(card),
               "--set", "SCSET", "--project", "SCPRJ", "--load-ms", "90000",
               "--scenario-jobs", str(os.cpu_count() or 4)]
        if model == "mkii":
            cmd.append("--mkii")
        for tag, kind, _want, poke in leds:
            base = out / f"{model}-{tag}"
            cmd += ["--scenario", f"{base}.log --live-script {out / kind}.script --serial-out {base} "
                    f"--poke {modes};{poke}"]
        for tag, _want, _open in chooser:
            base = out / f"{model}-{tag}"
            mem = ";".join(f"{d}={base}.m{i}" for i, d in enumerate(dumps))
            cmd += ["--scenario", f"{base}.log --live-script {out / tag}.script --poke {modes} "
                    f"--mem-dump {mem}"]
        with (out / f"{model}.log").open("w") as f:
            subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)
        bad = []
        for tag, kind, want, _poke in leds:
            base = out / f"{model}-{tag}"
            want = expected_midi(*want) if kind.startswith("midi") else expected_audio(*want)
            got = shown(base.with_suffix(".a")) if base.with_suffix(".a").exists() else "(no stream)"
            ended = "ended on quit" in base.with_suffix(".log").read_text()
            if got != want or not ended:
                bad.append(f"{tag}: want {want} got {got}{'' if ended else ' (the script did not end)'}")
        untouched = None                  # +0x12 as the project left it: HARMONY's byte, never SCALES'
        for tag, (key, ext), is_open in chooser:
            base = out / f"{model}-{tag}"
            log = base.with_suffix(".log").read_text()
            try:
                live, part, cs1, lst, bank, p, slot = (pathlib.Path(f"{base}.m{i}").read_bytes() for i in range(7))
            except FileNotFoundError:
                bad.append(f"{tag}: no memory dump")
                continue
            if bank != (0x400e21e0).to_bytes(4, "big") or p != b"\0":
                bad.append(f"{tag}: not bank 1 / Part 1 ({bank.hex()} {p.hex()})")
            for where, rec in (("live", live), ("Part", part), ("CS1", cs1)):
                untouched = rec[EXT] if untouched is None else untouched
                if (rec[KEY], rec[EXT]) != (key, untouched):
                    bad.append(f"{tag}: {where} KEY / +0x12 {rec[KEY]} / {rec[EXT]}, want {key} / {untouched}")
            if slot[0] != ext:
                bad.append(f"{tag}: sc_lib holds {slot[0]}, want {ext}")
            if bool(int.from_bytes(lst, "big")) != is_open:
                bad.append(f"{tag}: the window is {'closed' if is_open else 'open'}")
            if "ended on quit" not in log:
                bad.append(f"{tag}: the script did not end")
        print(f"  [{'FAIL' if bad else 'PASS'}] verify_scales: {model}, {len(leds)} LED runs, "
              f"{len(chooser)} chooser runs (every ID picked from ARP SETUP; reopen, NO, turned, "
              f"RIGHT / LEFT, CTRL1 commit)")
        for line in bad[:10]:
            print(f"      {line}")
        fails += bool(bad)
    fails += persist(out, image, card, lib)
    return int(bool(fails))


def persist(out, image, card, lib):
    """scales.work under the port, MKII: written by SAVE PROJECT, read at the next boot."""
    import struct
    import zlib
    from concurrent.futures import ThreadPoolExecutor
    sys.path.insert(0, str(ROOT / "tools/emu"))
    import emu_card
    d = out / "persist"
    d.mkdir()
    ident = 47
    for tag, save in (("saved", True), ("unsaved", False)):
        s = Script()
        arp(s)
        choose(s, ident)
        if save:                          # PROJ: SAVE PROJECT
            s.tap(0x1c, 1000)
            s.tap(0x21, 700)
            s.tap(0x20, 500)
            s.tap(0x31, 1100)
            s.tap(0x31, 30000)
        s.write(d / f"{tag}.script")
    s = Script()
    s.tap(0x32, 400)
    s.write(d / "idle.script")
    modes = "0x80000012=00;0x80000013=00;0x80000014=00;0x80000015=00"

    def boot(tag, card_, script, card_out):
        cmd = [ROOT / "out/emu/ot_emu", "--image", image, "--card", card_, "--set", "SCSET",
               "--project", "SCPRJ", "--load-ms", "90000", "--mkii", "--live-script", script,
               "--poke", modes, "--mem-dump", f"{lib:#x},{0x200}={d / (tag + '.lib')};{LIVE:#x},{0x24}={d / (tag + '.live')}"]
        if card_out:
            cmd += ["--card-out", d / f"{tag}.img"]
        with open(d / f"{tag}.txt", "w") as f:
            return subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode

    bad = []
    with ThreadPoolExecutor(2) as ex:
        rc = list(ex.map(lambda j: boot(*j), (("saved", card, d / "saved.script", True),
                                              ("unsaved", card, d / "unsaved.script", True))))
    if rc != [0, 0]:
        bad.append(f"the save and the unsaved run exited {rc}")
    files = emu_card.extract_image((d / "saved.img").read_bytes())
    for ext in ("work", "strd"):
        f = next((v for k, v in files.items() if k.lower().endswith(f"/scprj/scales.{ext}")), b"")
        if not (len(f) == 16 + 512 and f[:12] == b"SCLS\0\0\0\1\0\0\2\0"
                and struct.unpack(">I", f[12:16])[0] == zlib.crc32(f[16:])
                and f[16] == ident and not any(f[17:])):
            bad.append(f"scales.{ext}: {len(f)} B {f[:16].hex()} ID {f[16] if len(f) > 16 else None}")
    uf = emu_card.extract_image((d / "unsaved.img").read_bytes())
    if any(k.lower().endswith("/scprj/scales.work") for k in uf):
        bad.append("the unsaved run wrote scales.work")
    rc = boot("reboot", d / "saved.img", d / "idle.script", False)
    lib_b, live = (d / "reboot.lib").read_bytes(), (d / "reboot.live").read_bytes()
    if rc or lib_b[0] != ident or live[KEY] != encode(0, ident):
        bad.append(f"reboot: exited {rc}, sc_lib {lib_b[0]}, KEY {live[KEY]} (want {ident}, {encode(0, ident)})")
    print(f"  [{'FAIL' if bad else 'PASS'}] verify_scales: scales.work, MKII (SAVE PROJECT writes .work and "
          f".strd with the ID; the saved card boots it back; no save, no file)")
    for line in bad:
        print(f"      {line}")
    return bool(bad)


if __name__ == "__main__":
    sys.exit(main())
