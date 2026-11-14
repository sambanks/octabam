#!/usr/bin/env python3
"""LAZY CHOP under the ColdFire port: slice a sample by tapping the trig keys.

    python3 tools/verify/verify_lazy_chop.py [REMIX] [scenario ...]
    make check REMIX=<a remix with LAZY CHOP>   # runs this as the module gate

Reads out/mainos_bus.bin (an image gate: `make bus REMIX=...` first) and its
runtime map. The project is the firmware's own empty one (tools/hw/ot_fresh.py,
cached) with a 2 s FLEX sample on T1 (slot 1) holding four slices; the
recorder scenario sets T1 FLEX on R1 instead. Scenarios, each on its own boot
and card (MKI unless named):

  chop     the row arms; TRIG 2 before TRIG 1 and an out-of-order key do
           nothing; 17 taps 100 ms apart across the page turn -> 18 slices
           (in the table, shown, while chopping),
           chained, at the tap times, trim start to trim end, no loops; YES
           ends the mode; stock LEVEL selects a new slice and encoder A edits
           it; a trig afterwards is stock; NO mid-chop and leaving the page
           mid-chop restore the old slices
  cap      63 taps 25 ms apart: 64 slices, the mode ends by itself, a 65th tap
           adds nothing
  save     chop, PROJECT > SAVE (markers.strd), a stock edit, PROJECT > RELOAD
           brings the chopped slices back
  leds     the trig LEDs: armed TRIG 1 green; slices made red, the next
           key green; set again after ids 0-31 are cleared and after a short
           stock flash expires; the page turn: TRIG 1 green; stock's after
           YES and NO
  mkii     as MKII, the editor from the AED key: arm, chop 6, YES
  rec      (BUFFER SAVER in the remix) a HOLD take in R1, [REC AB]+[BANK],
           chop 6, SAVE PROJECT, SAVE SAMPLES? YES: the take's .ot holds them
  seq      the sequencer running: PLAY while armed; 7 taps and their LEDs;
           once the playhead wraps (the loop, or T1's step-1 trig) taps
           behind the last marker are refused (LOOPED); YES; PLAY and STOP
           mid-chop; NO restores
  recnew   (BUFFER SAVER in the remix) a new take into R1 while chopping it
           ends the chop and leaves the slices as stock does over a new take
           (kept; the last one ends at the take's end)
  slic     (the F5 unit report) T1 SLIC ON with trigs on steps 1 and 9,
           sequencer running: 10 taps land; a faked running light (a blink
           bit every 10 ms) costs under 150 LED messages; YES: 10 slices
  snap     SCALE (MKI; PAGE on an MKII) turns ZERO SNAP on: every marker on a zero crossing
           of the sample's left channel; again: off
  static   ZERO SNAP on a STATIC sample (T1 STATIC; a stereo tone whose sum
           crosses zero elsewhere than its left channel): every marker on a
           crossing of the sum, read from the card's stream buffer
  undo     a short hold on the last red trig auditions; 0.7 s undoes it;
           the green trig resumes from the last marker, the next press cuts;
           undoing slice 16 (holding TRIG 16, or the green TRIG 1 at the
           page start) goes back to page 1; YES keeps the trim
  aud      a red trig plays its slice as a slice (live SLIC on, STRT 0, for
           the moment: no timestretch), the trim untouched; green resumes; YES
           (the live SLIC/STRT and entry 0 back)
  audslic  aud on the SLIC ON card
  cost     LAZY CHOP closed: its hooks' calls over 1 s of playback; ZERO SNAP's
           instructions per tap on FLEX, against fixed limits
  coststatic  the same per tap on STATIC
  ptn      [PTN]+trig selects a pattern and places no marker; MIDI program
           changes stopped and playing; the chop goes on; YES

  live     LIVE CHOP on a recorder buffer: TRIG 1 starts the take, cuts at the head,
           YES stops it; silent chop on a sample slot
  tstr     timestretch on: slice 1 no earlier than frame 384; off: at the trim start

This file is also the harness for LOCK EDIT, ZOOM KEEP and SRC3 KEY: their gates
(verify_lock_edit.py, verify_zoom_keep.py, verify_src3_key.py) run the scenarios
in GROUPS below (lockedit, lock, aedview, midi) through main(). Each module's
scenarios run without the others and check the interplay when they are in the
image. SKIPs without the port, the .venv, or the gate's module in the image.
"""
from __future__ import annotations

import concurrent.futures as cf
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel", "tools/emu"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa: E402,F401

IMAGE = ROOT / "out/mainos_bus.bin"
MAP = ROOT / "out/platform/runtime/runtime.map"
EMU = ROOT / "out/emu/ot_emu"
VENV = ROOT / ".venv/bin/python3"
OUT = ROOT / os.environ.get("LAZY_CHOP_OUT", "out/lazy_chop_verify")   # a separate one per parallel run

FLEX1 = 0x100B14F0                       # FLEX slot 1's record (1096-byte stride)
STATIC1 = 0x100D5B30                     # STATIC slot 1's record
R1 = FLEX1 + 128 * 1096                  # recorder buffer 1 = FLEX 129
SEL = 0x400CEB3C                         # the slice under the editor's marker
EDITOR_SLOT, EDITOR_KIND = 0x46C8D19C, 0x46C8D1A0
VOICES, VSTRIDE = 0x800049D8, 0xA8
ROW_OFF, ROW_ON = 0, 0                   # LAZY CHOP is the first row of both slice menus

# Each module's gate runs its own scenarios (tools/verify/verify_<module>.py imports this harness); each works without
# the other modules, and checks the interplay when they are in the image too.
GROUPS = {
    "lazy_chop": ("chop", "cap", "save", "leds", "mkii", "rec", "seq", "recnew", "ptn", "slic", "snap", "static", "undo",
                  "aud", "audslic", "cost", "coststatic", "live", "tstr"),
    "lock_edit": ("lockedit", "lock"),
    "zoom_keep": ("aedview",),
    "src3_key": ("midi",),
}
NEEDS = {"lazy_chop": ("lc_state", "LAZY CHOP"), "lock_edit": ("le_bank", "LOCK EDIT"),
         "zoom_keep": ("zk_fitkeep", "ZOOM KEEP"), "src3_key": ("sk_press", "SRC3 KEY")}
SCENARIOS = tuple(n for g in GROUPS.values() for n in g)
GATE = "lazy_chop"


def skip(why):
    print(f"  [SKIP] verify_{GATE}: {why}")
    return 0


class Run:
    """One scenario on one boot: the port, the helpers, the checks."""

    def __init__(self, name, card, set_name, project, mkii=False):
        from stems_panel import MenuPort
        m = MAP.read_text()
        self.sym = lambda n: int(re.search(rf"(0x[0-9a-f]+)\s+{n}\n", m).group(1), 16)
        self.LC = " lc_state\n" in m              # LAZY CHOP in the image (the other modules' gates run without it)
        self.ST, self.NXT, self.LREC = ((self.sym("lc_state"), self.sym("lc_next"), self.sym("lc_rec"))
                                        if self.LC else (None, None, None))
        self.name, self.card, self.fails, self.notes = name, card, [], []
        self.p = MenuPort(IMAGE, card, set_name, project, mkii=mkii, log_path=card.parent / f"{name}.port.log")

    def check(self, ok, what):
        self.notes.append(("PASS " if ok else "FAIL ") + what)
        if not ok:
            self.fails.append(what)

    def slices(self, rec=FLEX1):
        p = self.p
        n = p.long(rec + 1092)
        return n, [struct.unpack(">IIi", p.peek(rec + 312 + 12 * k, 12)) for k in range(min(n, 64))]

    def tap(self, key, gap=100):
        p = self.p
        p.key(key, True); p.run(20); p.key(key, False); p.run(gap - 20)

    def editor(self, chord=("t1", "bank")):
        p = self.p
        if chord == "aed":
            p.press("t1", settle=200); p.press("aed", settle=600)
        else:
            p.chord(*chord, settle=600)
        p.press("pg_amp", settle=400)

    def arm(self):
        p = self.p
        row = ROW_ON if p.long(SEL) < 0x80000000 else ROW_OFF
        p.chord("func", "bank", settle=500)
        for _ in range(11):
            p.press("up", settle=80)              # the list stops at its top
        for _ in range(row):
            p.press("down", settle=120)
        p.press("yes", settle=400)

    def chop(self, n, gap=100):
        self.tap("trig1", gap)
        for k in range(1, n):
            self.tap(f"trig{k % 16 + 1}", gap)

    def project_row(self, row):
        p = self.p
        p.open_menu(); p.press("left")
        for _ in range(6):
            p.press("up")
        p.press("right", settle=300)              # PROJECT: CHANGE SAVE RELOAD SYNC TO CARD ...
        for _ in range(8):
            p.press("up", settle=80)              # it remembers its row
        for _ in range(row):
            p.press("down", settle=120)
        p.press("yes", settle=800)


MIN_START = 384                          # LAZY CHOP: slice 1 / the take not before frame 384 (the DSP stretch)


def stretching(p, t=0):
    """T(t+1)'s SETUP TSTR (live lane byte 28) is AUTO, NORM or BEAT."""
    return p.peek(0x80000510 + 48 * t + 28, 1)[0] in (1, 2, 3)


def s0(p, rec=FLEX1):
    """Where LAZY CHOP starts slice 1: the trim start, not before MIN_START while T1 stretches."""
    ts, te = p.long(rec + 300), p.long(rec + 304)
    return ts if ts >= MIN_START or te <= MIN_START or not stretching(p) else MIN_START


def chained(s, end):
    return all(s[i][1] == s[i + 1][0] and s[i][0] < s[i + 1][0] for i in range(len(s) - 1)) and s[-1][1] == end


def mono(s):
    return all(s[i][0] < s[i + 1][0] and s[i][1] == s[i + 1][0] for i in range(len(s) - 1))


def sc_chop(r):
    p, ST, NXT = r.p, r.ST, r.NXT
    r.editor()
    _, old = r.slices()
    r.arm()
    r.check(p.long(ST) == 1, "the LAZY CHOP row arms the mode")
    r.tap("trig2")
    r.check(p.long(ST) == 1, "TRIG 2 before TRIG 1 does nothing")
    r.tap("trig1")
    r.check(p.long(ST) == 2 and p.long(FLEX1 + 1092) == 2, "TRIG 1 plays T1 (entry 0 the whole take, entry 1 slice 1)")
    r.tap("trig5")
    r.check(p.long(NXT) == 1, "an out-of-order key places nothing")
    for k in list(range(2, 17)) + [1, 2]:
        r.tap(f"trig{k}")
    r.check(p.long(NXT) == 18, "17 taps across the page turn place 17 markers")
    n, s = r.slices()
    r.check(n == 19 and s[0][:2] == (s0(p), p.long(FLEX1 + 304)) and s[1][0] == s0(p) and mono(s[1:]) and s[-1][1] == p.long(FLEX1 + 304),
            f"the markers show while chopping: the whole take + 18 slices in the table ({n})")
    p.press("yes", settle=400)
    n, s = r.slices()
    r.check(p.long(ST) == 0 and n == 18, f"YES writes 18 slices and ends the mode ({n})")
    r.check(n == 18 and s[0][0] == s0(p) and chained(s, p.long(FLEX1 + 304)),
            f"chained from frame {s0(p)} (the trim start, not before {MIN_START}) to the trim end")
    r.check(n == 18 and all(abs((s[i + 1][0] - s[i][0]) - 4410) < 400 for i in range(2, 17)),
            "markers at the tap times (100 ms = 4,410 samples)")
    r.check(all(x[2] == -1 for x in s), "no loop points")
    for _ in range(40):
        p.proc.command("knob 0x36 3", "ok"); p.run(120)
        if 0 < p.long(SEL) < 0x80000000:
            break
    sel = p.long(SEL)
    r.check(0 < sel < n, "stock LEVEL moves the marker onto a new slice")
    before = r.slices()[1]
    p.proc.command("knob 0x30 3", "ok"); p.run(300)
    after = r.slices()[1]
    r.check(sel < n and before[sel] != after[sel], "stock encoder A edits it")
    r.tap("trig3", 300)
    r.check(p.long(ST) == 0 and r.slices()[1] == after, "a trig after YES is stock")
    keep = r.slices()
    r.arm(); r.chop(3)
    p.press("no", settle=400)
    r.check(p.long(ST) == 0 and r.slices() == keep, "NO while chopping restores the slices")
    r.arm(); r.chop(2)
    p.press("pg_playback", settle=400)
    r.check(p.long(ST) == 0 and r.slices() == keep, "leaving the SLICE page mid-chop restores them")


def sc_cap(r):
    p = r.p
    r.editor(); r.arm()
    r.chop(64, gap=25)
    n, s = r.slices()
    r.check(p.long(r.ST) == 0 and n == 64, f"64 slices end the mode by itself ({n})")
    r.check(n == 64 and chained(s, p.long(FLEX1 + 304)), "64 slices chained to the trim end")
    r.tap("trig1", 300)
    r.check(r.slices()[0] == 64, "a 65th tap adds nothing")


def sc_save(r):
    import emu_card
    p = r.p
    r.editor(); r.arm(); r.chop(7, gap=150)
    p.press("yes", settle=400)
    chopped = r.slices()
    r.check(chopped[0] == 7, "7 slices chopped")
    p.press("no", settle=400)
    r.project_row(1)                             # SAVE
    p.press("yes", settle=600); p.run(5000)
    p.card_flush()
    files = emu_card.extract_image(r.card.read_bytes())
    strd = [d for k, d in files.items() if k.endswith("markers.strd")]
    got = None
    if strd:
        body = strd[0][0x16:0x16 + 784]
        cnt = struct.unpack(">I", body[780:784])[0]
        got = (cnt, [struct.unpack(">IIi", body[12 + 12 * k:24 + 12 * k]) for k in range(min(cnt, 64))])
    r.check(got == chopped, "SAVE PROJECT writes them to markers.strd")
    for _ in range(3):
        p.press("no", settle=300)
    r.editor()
    for _ in range(3):
        p.proc.command("knob 0x30 5", "ok"); p.run(300)
    edited = r.slices()
    r.check(edited != chopped, "a later stock edit changes them")
    p.press("no", settle=400); p.press("no", settle=300)
    r.project_row(2)                             # RELOAD
    p.press("yes", settle=600)
    for _ in range(30):
        p.run(1000)
        if r.slices() != edited:
            break
    p.run(2000)
    r.check(r.slices() == chopped, "RELOAD brings the chopped slices back")


def lit(p):
    b = p.peek(0x460BA9AE, 4)                    # the LED state array; ids 0-31 are the trig pairs
    return {i for i in range(32) if b[i >> 3] >> (i & 7) & 1}


def page(k):
    """LAZY CHOP's trig LEDs with k keys tapped on this page: red 2i for
    the slices made, green 2k+1 for the next key, the rest off (8thmyth, 10 Nov)."""
    return {2 * i for i in range(k)} | {2 * k + 1}


def sc_leds(r):
    p = r.p
    r.editor(); r.arm()
    r.check(lit(p) == page(0), f"armed: TRIG 1 green ({sorted(lit(p))})")
    r.tap("trig1", 80); p.run(40)                # stock flashes id 16 for 10 ticks when T1 triggers
    r.check(lit(p) == page(1), f"TRIG 1 tapped: red, TRIG 2 green ({sorted(lit(p))})")
    for k in range(2, 9):
        r.tap(f"trig{k}", 80)
    r.check(lit(p) == page(8), f"TRIG 1-8 red, TRIG 9 green ({sorted(lit(p))})")
    p.run(200)
    r.check(lit(p) == page(8), "they stay lit")
    p.poke(0x460BA9AE, b"\0\0\0\0"); p.run(100)
    r.check(lit(p) == page(8), "ids 0-31 cleared behind LAZY CHOP's back: set again within 100 ms")
    p.poke(0x460BA9CC, (6).to_bytes(4, "big")); p.run(300)
    r.check(lit(p) == page(8), "a stock-style short flash on TRIG 1's red (6 ticks): still red after it expires")
    for k in range(9, 17):
        r.tap(f"trig{k}", 80)
    r.check(lit(p) == page(0), f"the page turn: only TRIG 1, green ({sorted(lit(p))})")
    r.tap("trig1", 80)
    r.check(lit(p) == page(1), f"slice 17 on TRIG 1: red, TRIG 2 green ({sorted(lit(p))})")
    p.press("yes", settle=400)
    r.check(not lit(p), f"YES: back to stock ({sorted(lit(p))})")
    r.arm(); r.tap("trig1", 80); r.tap("trig2", 80)
    p.press("no", settle=400)
    r.check(not lit(p), f"NO: back to stock ({sorted(lit(p))})")


def sc_mkii(r):
    p = r.p
    r.editor("aed")
    r.check(p.long(EDITOR_SLOT) == 0 and p.long(EDITOR_KIND) == 1, "AED opens the editor on T1's FLEX slot 1")
    r.arm(); r.chop(6, gap=150)
    p.press("yes", settle=400)
    n, s = r.slices()
    r.check(p.long(r.ST) == 0 and n == 6 and chained(s, p.long(FLEX1 + 304)), f"6 slices chopped ({n})")
    if " sk_press\n" in MAP.read_text():          # SRC3 KEY is MKI only: the MKII keeps stock [MIDI]
        p.press("midi", settle=400)
        r.check(p.peek(VOICES + 1, 1)[0] == 0 and (p.long(0x460E5E4C) == 0 or p.long(0x80000012) != 0),
                "MKII: [MIDI] in the editor is stock's (no SRC3 recording; the MKII has [REC3])")


def sc_rec(r):
    import emu_card
    p = r.p
    before = {k for k in emu_card.extract_image(r.card.read_bytes()) if k.lower().endswith(".ot")}
    p.chord("func", "recab", settle=400)         # RECORDING SETUP: TRIG ONE -> HOLD
    p.proc.command("knob 0x33 8", "ok"); p.run(300)
    p.press("no", settle=300)
    p.key("t1", True); p.run(40); p.key("recab", True); p.run(1500)
    p.key("recab", False); p.run(40); p.key("t1", False); p.run(500)
    take = p.long(R1 + 304)
    r.check(20000 < take < 120000, f"a HOLD take in R1 ({take} samples)")
    r.editor(("recab", "bank"))
    r.check(p.long(EDITOR_SLOT) == 128, "[REC AB]+[BANK] opens the editor on R1")
    r.arm()
    r.check(p.long(r.LREC) == R1, "LAZY CHOP arms on R1's record")
    r.chop(6, gap=150)
    p.press("yes", settle=400)
    chopped = r.slices(R1)
    r.check(chopped[0] == 6 and chained(chopped[1], take), "6 slices on the take")
    p.press("no", settle=400); p.press("no", settle=300)
    r.project_row(1)                             # SAVE: BUFFER SAVER asks first
    p.press("yes", settle=1500); p.run(4000)
    p.press("yes", settle=1000); p.run(6000)
    r.check(r.slices(R1) == chopped, "R1 keeps them after the save")
    p.card_flush()
    ots = {k: d for k, d in emu_card.extract_image(r.card.read_bytes()).items()
           if k.lower().endswith(".ot") and k not in before and len(d) >= 832}
    got = [(struct.unpack(">I", d[826:830])[0],
            [struct.unpack(">IIi", d[58 + 12 * k:70 + 12 * k]) for k in range(min(struct.unpack(">I", d[826:830])[0], 64))])
           for d in ots.values()]
    r.check(chopped in got, f"the saved take's .ot holds them ({', '.join(sorted(ots)) or 'no .ot'})")


def led_msgs(p, fn):
    """LED messages (bitmap rows, levels) LAZY CHOP and stock put on the panel link during fn()."""
    from panel_link import PanelLink
    a = len(p.rt.uart64.tx); fn(); raw = bytes(p.rt.uart64.tx[a:len(p.rt.uart64.tx)])
    L, n = PanelLink(), [0]
    orig = L._message

    def m(x):
        if x and (0x20 <= x[0] <= 0x3f or 0xa0 <= x[0] <= 0xaf):
            n[0] += 1
        orig(x)
    L._message = m
    L.feed(raw)
    return n[0]


def sc_slic(r):
    """The F5 unit report: T1 with SLIC on and trigs on steps 1 and 9, chopped
    with the sequencer running; stock's running light faked (a blink bit every 10 ms)."""
    p = r.p
    r.editor(); p.press("play", settle=200); r.arm()
    r.tap("trig1", 200)
    for k in range(2, 11):
        r.tap(f"trig{k}", 200)
    r.check(p.long(r.NXT) == 10, f"SLIC on, sequencer running (a T1 trig every second): 10 taps over 2 s land ({p.long(r.NXT)})")

    def fake():
        for _ in range(100):
            b = bytearray(p.peek(0x460BA98C, 1)); b[0] |= 0x30
            p.poke(0x460BA98C, bytes(b)); p.run(10)
    n = led_msgs(p, fake)
    r.check(n < 150 and lit(p) == page(10 % 16), f"a running light faked for 1 s: {n} LED messages (F5: 337), the LEDs right")
    p.press("yes", settle=400)
    n, s = r.slices()
    r.check(p.long(r.ST) == 0 and n == 10 and s[0][0] == s0(p) and mono(s) and s[-1][1] == p.long(FLEX1 + 304),
            f"YES: 10 slices, entry 0 moved out ({n})")
    p.press("stop", settle=300)


def wav_left_of(name):
    import wave
    wf = wave.open(str(OUT / "_projects" / name))
    raw = wf.readframes(wf.getnframes()); step = wf.getsampwidth() * wf.getnchannels()
    return [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), step)]


def wav_left():
    """The test sample's left channel, as LAZY CHOP's ZERO SNAP reads it (16-bit)."""
    import wave
    wf = wave.open(str(OUT / "_projects" / "LC_440_120.wav"))
    raw = wf.readframes(wf.getnframes()); step = wf.getsampwidth() * wf.getnchannels()
    return [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), step)]


def sc_snap(r):
    p = r.p
    left = wav_left()
    crossing = lambda i: 0 < i < len(left) and (left[i - 1] < 0) != (left[i] < 0)
    r.editor(); r.arm()
    SN = r.sym("lc_snap")
    r.check(p.long(SN) == 0, "ZERO SNAP is off by default")
    p.press("page", settle=300)
    r.check(p.long(SN) == 1 and p.long(r.ST) == 1, "SCALE (MKI; PAGE on an MKII) while armed: ZERO SNAP on, still armed")
    BV = re.search(r"(0x[0-9a-f]+)\s+brain_v_octabam_lazy_chop_1\n", MAP.read_text())
    if BV:                                       # with BRAIN: the setting follows [SCALE] (kept across power-off)
        r.check(p.long(int(BV.group(1), 16)) == 1, "with BRAIN: the ZERO SNAP setting follows [SCALE] (on)")
    r.chop(7, gap=150)
    p.press("yes", settle=400)
    n, s = r.slices()
    starts = [x[0] for x in s[1:]]
    r.check(n == 7 and all(crossing(i) for i in starts), f"every marker on a zero crossing of the left channel ({starts})")
    r.check(mono(s) and s[-1][1] == p.long(FLEX1 + 304), "still chained to the trim end")
    r.arm()
    r.check(p.long(SN) == 1, "ZERO SNAP is still on when LAZY CHOP opens again (the popup says SNAP ON)")
    p.press("page", settle=300)
    r.check(p.long(SN) == 0, "SCALE again: off")
    if BV:
        r.check(p.long(int(BV.group(1), 16)) == 0, "with BRAIN: the setting follows it off")
    r.chop(7, gap=150)
    p.press("yes", settle=400)
    starts = [x[0] for x in r.slices()[1][1:]]
    r.check(not all(crossing(i) for i in starts), f"off: the markers where tapped, not all on crossings ({starts})")


def hold(p, key, ms):
    p.key(key, True); p.run(ms); p.key(key, False); p.run(120)


def sc_undo(r):
    p = r.p
    trim = (p.long(FLEX1 + 300), p.long(FLEX1 + 304))
    r.editor(); r.arm(); r.chop(5, gap=150)
    r.check(p.long(r.NXT) == 5, "5 slices")
    hold(p, "trig5", 150)
    r.check(p.long(r.NXT) == 5 and p.long(r.sym("lc_aud")) == 1, "a short hold on the last red trig only auditions")
    hold(p, "trig5", 700)
    n, s = r.slices()
    r.check(p.long(r.NXT) == 4 and n == 5 and s[4][1] == trim[1], f"a 0.7 s hold undoes slice 5: 4 slices, the last runs to the end ({p.long(r.NXT)})")
    r.check(lit(p) == page(4), f"the LEDs: TRIG 1-4 red, TRIG 5 green ({sorted(lit(p))})")
    r.check((p.long(FLEX1 + 300), p.long(FLEX1 + 304)) == trim, "the trim is the take's")
    m4 = s[4][0]
    r.tap("trig5", 60)
    pos = p.long(VOICES + 68)
    r.check(p.long(r.NXT) == 4 and p.peek(VOICES, 1)[0] and m4 <= pos < m4 + 8000, f"the green trig resumes from the last marker ({m4} -> {pos})")
    r.tap("trig5", 150)
    n, s = r.slices()
    r.check(p.long(r.NXT) == 5 and s[5][0] > m4, "and the next press cuts")
    for k in list(range(6, 17)):
        r.tap(f"trig{k}", 100)
    r.check(p.long(r.NXT) == 16 and lit(p) == page(0), f"16 slices: page 2, TRIG 1 green ({p.long(r.NXT)})")
    hold(p, "trig16", 700)
    r.check(p.long(r.NXT) == 15 and lit(p) == page(15), f"holding TRIG 16 undoes slice 16: back to page 1, TRIG 16 green ({sorted(lit(p))})")
    r.tap("trig16", 300)                         # the hold auditioned: this press resumes
    r.tap("trig16", 100)                         # and this one cuts
    r.check(p.long(r.NXT) == 16 and lit(p) == page(0), f"slice 16 again (resume, then cut): page 2, TRIG 1 green ({p.long(r.NXT)})")
    hold(p, "trig1", 700)
    r.check(p.long(r.NXT) == 15 and lit(p) == page(15),
            f"holding the green TRIG 1 at a page start: back to page 1, slice 16 undone (and the press's cut) ({p.long(r.NXT)}, {sorted(lit(p))})")
    p.press("yes", settle=400)
    n, s = r.slices()
    r.check(p.long(r.ST) == 0 and n == 15 and mono(s) and s[-1][1] == trim[1] and (p.long(FLEX1 + 300), p.long(FLEX1 + 304)) == trim,
            f"YES: 15 slices, chained, the trim the take's ({n})")


def sc_aud(r):
    p = r.p
    trim = (p.long(FLEX1 + 300), p.long(FLEX1 + 304))
    live = p.peek(0x80000810, 0x22)                # T1's live lane: STRT +1, SLIC +0x21
    r.editor(); r.arm(); r.chop(4, gap=200)
    n, s = r.slices()
    a, b = s[2][:2]
    r.tap("trig2", 60)
    pos = p.long(VOICES + 68)
    r.check(p.long(r.sym("lc_aud")) == 1 and a <= pos < b, f"a red trig auditions its slice ({a}..{b}: {pos})")
    r.check((p.long(FLEX1 + 300), p.long(FLEX1 + 304)) == trim and p.long(VOICES + 56) == a,
            "played as a slice (the voice's slice start set), the trim untouched (no timestretch)")
    p.run(800)
    r.check(not p.peek(VOICES, 1)[0] or p.long(VOICES + 68) <= b + 64, f"and stops at its end ({p.long(VOICES + 68)})")
    m4 = s[4][0]
    r.tap("trig5", 60)
    pos = p.long(VOICES + 68)
    r.check(p.long(r.sym("lc_aud")) == 0 and m4 <= pos < m4 + 8000, f"the green trig resumes from the last marker ({m4} -> {pos})")
    r.check((p.long(FLEX1 + 300), p.long(FLEX1 + 304)) == trim, "the trim untouched while resuming")
    r.tap("trig5", 150)
    r.check(p.long(r.NXT) == 5 and r.slices()[1][5][0] > m4, "the next press cuts")
    keep5 = None
    p.press("yes", settle=400)
    n, s = r.slices()
    keep5 = r.slices()
    r.check(p.long(r.ST) == 0 and n == 5 and mono(s) and (p.long(FLEX1 + 300), p.long(FLEX1 + 304)) == trim,
            f"YES: 5 slices, the trim the take's ({n}; trim {p.long(FLEX1 + 300)}..{p.long(FLEX1 + 304)} vs {trim}; {[x[:2] for x in s]})")
    now = p.peek(0x80000810, 0x22)
    r.check(now[1] == live[1] and now[0x21] == live[0x21], f"the live STRT and SLIC are the track's again ({now[1]}/{now[0x21]} vs {live[1]}/{live[0x21]})")
    r.arm(); r.chop(3, gap=200); r.tap("trig2", 60)       # an audition in place, then leave the page
    p.press("pg_playback", settle=400)
    r.check(p.long(r.ST) == 0 and r.slices() == keep5, "leaving the page during an audition restores the slices (stress seed 22, G3)")
    p.press("pg_amp", settle=300)


SNAP_TAP_LIMIT = 100000                  # ColdFire instructions for one tap's ZERO SNAP, interrupts that fire meanwhile included (~0.4 ms; the snap alone measured ~32,500)
HOOK_INSN_PER_CALL = 8                   # a closed hook: the jsr, a load or test, a branch, the rts
HOOK_LIMIT = 300000                      # instructions a second for all hooks, LAZY CHOP closed (~0.15 %)


def snap_costs(r, taps):
    """Instructions from lc_snapfix to lc_snapdone for each tap (interrupts included: an upper bound)."""
    p = r.p
    a, b = r.sym("lc_snapfix"), r.sym("lc_snapdone")
    p.proc.command(f"watch {a:#x},{b:#x}", "ok"); p.proc.command("hits", "hits")
    taps()
    out = p.proc.command("hits", "hits").split()[2:]
    p.proc.command("watch off", "ok")
    costs, start = [], None
    for rec in out:
        f = rec.split(":")
        n, pc = int(f[0], 16), int(f[1], 16)
        if pc == a: start = n
        elif pc == b and start is not None: costs.append(n - start); start = None
    return costs


def sc_cost(r):
    p = r.p
    hooks = [r.sym(x) for x in ("lc_tick", "lc_ledpass", "lc_cmdgate")]
    p.press("play", settle=300)
    p.proc.command("watch " + ",".join(f"{h:#x}" for h in hooks), "ok"); p.proc.command("hits", "hits")
    p.run(1000)
    n = int(p.proc.command("hits", "hits").split()[1][2:])
    p.proc.command("watch off", "ok")
    r.check(n * HOOK_INSN_PER_CALL < HOOK_LIMIT,
            f"LAZY CHOP closed, sequencer playing: hooks called {n} times a second, about {n * HOOK_INSN_PER_CALL} instructions (limit {HOOK_LIMIT})")
    p.press("stop", settle=300)
    r.editor(); r.arm(); p.press("page", settle=300)
    costs = snap_costs(r, lambda: r.chop(7, gap=150))
    r.check(len(costs) == 6 and max(costs) < SNAP_TAP_LIMIT, f"ZERO SNAP per tap, FLEX: {costs} instructions (limit {SNAP_TAP_LIMIT})")
    p.press("yes", settle=300)


def sc_coststatic(r):
    p = r.p
    r.editor(); r.arm(); p.press("page", settle=300)
    costs = snap_costs(r, lambda: r.chop(7, gap=150))
    r.check(len(costs) == 6 and max(costs) < SNAP_TAP_LIMIT, f"ZERO SNAP per tap, STATIC: {costs} instructions (limit {SNAP_TAP_LIMIT})")
    p.press("yes", settle=300)


def trac_ram(p, track):
    return p.long(0x46C82456) + p.peek(0x80000004, 1)[0] * 0x8ED8 + track * 0x91A


def sc_live(r):
    """LIVE CHOP / STUDIO CHOP ([CUE]) on a recorder buffer: LIVE's TRIG 1 starts the recorder and the
    cuts land at the record head with nothing played; [MIDI] stops a LIVE take and does nothing in STUDIO."""
    p = r.p
    p.chord("func", "recab", settle=400)         # RECORDING SETUP: TRIG ONE -> HOLD
    p.proc.command("knob 0x33 8", "ok"); p.run(300)
    p.press("no", settle=300)
    p.key("t1", True); p.run(40); p.key("recab", True); p.run(1500)
    p.key("recab", False); p.run(40); p.key("t1", False); p.run(500)
    take = p.long(R1 + 304)
    r.check(20000 < take < 120000, f"a first take in R1 ({take} samples)")
    rec = lambda: p.peek(VOICES + 1, 1)[0]      # T1's recorder running
    plays = lambda: p.peek(VOICES, 1)[0]        # T1's voice playing
    pos = lambda: p.long(0x46C802C8)            # R1's record head (frames)
    LV, LT = r.sym("lc_live"), r.sym("lc_ltk")
    BV = re.search(r"(0x[0-9a-f]+)\s+brain_v_octabam_lazy_chop_2\n", MAP.read_text())
    r.editor(("recab", "bank")); r.arm()
    r.check(p.long(r.ST) == 1 and p.long(LV) == 0, "LAZY CHOP opens in STUDIO CHOP by default")
    SK = " sk_press\n" in MAP.read_text()       # SRC3 KEY: [MIDI] records SRC3 (scenario midi)
    if not SK:
        p.press("midi", settle=300)
        r.check(rec() == 0 and p.long(0x460E5E4C) != 0 and p.long(r.ST) == 1 and p.long(0x80000012) == 0,
                "STUDIO: [MIDI] does nothing (no recording, the editor stays, LAZY CHOP stays armed)")
    p.press("cue", settle=300)
    r.check(p.long(LV) == 1 and p.long(r.ST) == 1, "[CUE]: LIVE CHOP, still armed")
    if BV:
        r.check(p.long(int(BV.group(1), 16)) == 1, "with BRAIN: the LIVE CHOP setting follows [CUE]")
    r.tap("trig1", 120)
    r.check(rec() != 0 and p.long(r.ST) == 2 and p.long(LT) == 1, "LIVE: TRIG 1 starts R1's recorder (its RECORDING SETUP)")
    r.check(plays() == 0, "LIVE: nothing plays")
    p.run(400); h2 = pos(); r.tap("trig2", 60)
    p.run(400); h3 = pos(); r.tap("trig3", 60)
    n, s = r.slices(R1)
    m1, m2 = s[1][1], s[2][1]
    r.check(p.long(r.NXT) == 3 and s[1][0] == (MIN_START if stretching(p) else 0) and 0 <= m1 - h2 < 1500 and 0 <= m2 - h3 < 1500,
            f"LIVE: slice 1 from frame {MIN_START if stretching(p) else 0}, cuts at the record head ({m1}~{h2}, {m2}~{h3})")
    r.check(plays() == 0, "LIVE: still nothing plays after the cuts")
    r.tap("trig1", 120)
    r.check(plays() == 0 and p.long(r.sym("lc_aud")) == 0, "LIVE take: a red trig does not audition")
    if not SK:
        p.press("midi", settle=300)
        r.check(rec() != 0 and p.long(r.ST) == 2, "LIVE: [MIDI] does nothing (the take goes on)")
    p.press("yes", settle=400)
    n, s = r.slices(R1)
    r.check(rec() == 0 and n == 3 and mono(s) and s[0][0] == (MIN_START if stretching(p) else 0), f"YES stops the take and writes 3 slices ({n})")
    # armed first, the take started by stock's REC key: TRIG 1 joins it at the head
    r.arm()
    r.check(p.long(r.ST) == 1 and p.long(LV) == 1, "LIVE kept at the next open")
    p.poke(0x46C7E9FA, (0xF010).to_bytes(4, "big")); p.run(500)   # a start as a recorder trig posts it
    started = rec() != 0
    h = pos(); r.tap("trig1", 60)
    n, s = r.slices(R1)
    r.check(started and rec() != 0 and p.long(r.ST) == 2 and s[1][0] >= h > 0,
            f"a take started elsewhere (a recorder trig's start): TRIG 1 joins it at the head (started {started}; {s[1][0] if n > 1 else None} >= {h})")
    p.press("yes", settle=300)
    r.check(rec() == 0 and p.long(r.ST) == 0, "YES ends the joined take")
    # YES during a LIVE take stops the recording and writes the slices
    r.arm()
    r.tap("trig1", 120); p.run(500); r.tap("trig2", 60); p.run(400)
    p.press("yes", settle=600)
    n, s = r.slices(R1)
    tl = p.long(R1 + 304)
    r.check(rec() == 0 and p.long(r.ST) == 0 and n == 2 and s[-1][1] <= tl and tl < 200000,
            f"LIVE: YES stops the take and writes the slices ({n}, last ends {s[-1][1] if n else None} <= take {tl})")
    # QREC: the start waits for the quantized step; taps before it are ignored
    p.press("no", settle=200); p.press("no", settle=200)
    p.chord("func", "reccd", settle=500)
    p.proc.command("knob 0x33 20", "ok"); p.run(300)
    p.press("no", settle=300)
    p.press("play", settle=500)
    r.editor(("recab", "bank")); r.arm()
    r.tap("trig1", 20); waited = rec() == 0
    r.tap("trig2", 20)
    early = p.long(r.NXT)
    for _ in range(250):
        if rec(): break
        p.run(40)
    started = rec() != 0
    p.run(300); h = pos(); r.tap("trig2", 40)
    n, s = r.slices(R1)
    r.check(waited and early == 1 and started and plays() == 0, f"LIVE with QREC: the start waits for the step, a tap before it is ignored (waited {waited}, next {early}, started {started})")
    r.check(p.long(r.NXT) == 2 and 0 <= s[1][1] - h < 1500, f"after the start, cuts at the head of the quantized take ({s[1][1]}~{h})")
    p.key("yes", True); p.run(30); p.key("yes", False); p.run(60)
    r.check(rec() == 0, "LIVE with QREC: YES stops the take at once (no wait for the quantize)")
    p.run(300); p.press("stop", settle=300)
    # every input off: LIVE is silent chop (the take plays muted, nothing records)
    p.press("no", settle=200); p.press("no", settle=200)
    p.chord("func", "recab", settle=500)
    for k in (0x30, 0x31, 0x34):
        for _ in range(6):
            p.proc.command(f"knob {k:#x} -8", "ok"); p.run(150)
    p.press("no", settle=300)
    r.editor(("recab", "bank")); r.arm()
    mute0 = p.peek(0x8000000A, 1)[0]
    r.tap("trig1", 60)
    muted = p.peek(0x8000000A, 1)[0] & 1
    r.check(rec() == 0 and plays() != 0 and muted and p.long(LT) == 0,
            f"LIVE with every input off: no recording; the take plays muted (silent chop; mute {mute0:#x} -> {p.peek(0x8000000A, 1)[0]:#x})")
    r.tap("trig2", 60); r.tap("trig3", 60)
    r.check(p.long(r.NXT) == 3, f"silent chop cuts at the playhead ({p.long(r.NXT)}; the take {p.long(R1 + 304)} frames)")
    p.press("yes", settle=400)
    n, s = r.slices(R1)
    r.check(n == 3 and p.peek(0x8000000A, 1)[0] & 1 == mute0 & 1, f"YES writes them and the mute goes back ({n}, {p.peek(0x8000000A, 1)[0]:#x})")
    r.arm(); p.press("cue", settle=300)
    r.check(p.long(LV) == 0, "[CUE] again: STUDIO CHOP")
    p.press("no", settle=300)


def sc_midi(r):
    """SRC3 KEY: [MIDI] in the audio editor starts / stops a SRC3 recording on the track's recorder; outside
    the editor, or with the setting off, it is stock's; inside LAZY CHOP (LIVE) TRIG 1 joins that take."""
    p = r.p
    m = MAP.read_text()
    if " sk_press\n" not in m:
        r.check(True, "SRC3 KEY is not in the image (nothing to check)")
        return
    rec = lambda: p.peek(VOICES + 1, 1)[0]
    AED = lambda: p.long(0x460E5E4C)
    BS = re.search(r"(0x[0-9a-f]+)\s+brain_v_octabam_src3_key_1\n", m)
    rset = lambda: p.peek(p.long(0x46C82456) + 0x8ED80 + p.peek(0x100B14CF, 1)[0] * 0x18B2 + 0x602, 6)
    p.chord("func", "recab", settle=500)          # RECORDING SETUP: SRC3 on
    for _ in range(6):
        p.proc.command("knob 0x34 8", "ok"); p.run(150)
    p.press("no", settle=300)
    r.check(rset()[4] != 0, f"the project: T1's RECORDING SETUP has SRC3 ({rset().hex()})")
    r.editor(("recab", "bank"))
    r.check(AED() != 0 and rec() == 0, "the editor is open, R1 idle")
    l0 = p.long(R1 + 304)
    p.press("midi", settle=300)
    r.check(rec() != 0 and AED() != 0 and p.long(0x80000012) == 0,
            "[MIDI] in the editor: R1 records (SRC3), the editor stays, no MIDI page")
    p.run(1500)
    p.press("midi", settle=300)
    l1 = p.long(R1 + 304)
    r.check(rec() == 0 and AED() != 0 and l1 > 20000 and l1 != l0, f"[MIDI] again: the take stops ({l1} samples), the editor stays")
    if r.LC:
        # inside LAZY CHOP, LIVE: TRIG 1 joins the SRC3 take; YES stops it
        r.arm()
        if p.long(r.sym("lc_live")) == 0:
            p.press("cue", settle=300)
        p.press("midi", settle=300)
        started = rec() != 0
        p.run(400); r.tap("trig1", 60); p.run(400); r.tap("trig2", 60)
        r.check(started and rec() != 0 and p.long(r.ST) == 2 and p.long(r.sym("lc_ltk")) == 1 and AED() != 0,
                f"LAZY CHOP LIVE: [MIDI] starts the SRC3 take, TRIG 1 joins it (started {started}, state {p.long(r.ST)})")
        p.press("yes", settle=400)
        n, s = r.slices(R1)
        r.check(rec() == 0 and n == 2 and p.long(r.ST) == 0, f"YES stops it and writes 2 slices ({n})")
        r.arm(); p.press("cue", settle=300); p.press("no", settle=300)   # back to STUDIO
    # SRC3 "-": nothing records
    p.press("no", settle=200); p.press("no", settle=200)
    p.chord("func", "recab", settle=500)
    for _ in range(6):
        p.proc.command("knob 0x34 -8", "ok"); p.run(150)
    p.press("no", settle=300)
    r.editor(("recab", "bank"))
    p.press("midi", settle=300)
    r.check(rec() == 0 and AED() != 0, f"SRC3 off in RECORDING SETUP: [MIDI] records nothing, the editor stays ({rset().hex()})")
    # the setting off: stock's [MIDI] (the MIDI page shuts the editor)
    if BS:
        p.poke(int(BS.group(1), 16), (0).to_bytes(4, "big"))
        p.press("midi", settle=400)
        r.check(AED() == 0 or p.long(0x80000012) != 0, "MIDI = SRC3 off: [MIDI] is stock's (the MIDI page)")
        p.poke(int(BS.group(1), 16), (1).to_bytes(4, "big"))
        if p.long(0x80000012):
            p.press("midi", settle=400)
    # outside the editor: stock's
    for _ in range(3):
        p.press("no", settle=200)
    if AED() == 0:
        p.press("midi", settle=400)
        r.check(p.long(0x80000012) != 0 and rec() == 0, "outside the editor: [MIDI] is stock's (MIDI tracks)")
        p.press("midi", settle=400)


def sc_tstr(r):
    """T1 TSTR NORM: LAZY CHOP starts the take and slice 1 at MIN_START (the DSP stretch stalls on
    restarts within ~300 frames of frame 0 on the unit, H2), and the cuts land; TSTR OFF keeps frame 0."""
    p = r.p
    r.check(stretching(p), f"the project: T1 TSTR NORM (lane {p.peek(0x80000510 + 28, 1)[0]})")
    r.editor(); r.arm(); r.tap("trig1", 120)
    n, s = r.slices()
    a = p.long(VOICES + 68); p.run(300); b = p.long(VOICES + 68)
    r.check(p.long(r.ST) == 2 and s[0][0] == MIN_START and s[1][0] == MIN_START and b != a,
            f"TRIG 1: the take plays from frame {MIN_START} (entry 0 {s[0][0]}, slice 1 {s[1][0]}, position {a} -> {b})")
    for k in (2, 3, 4):
        r.tap(f"trig{k}", 200)
    p.press("yes", settle=400)
    n, s = r.slices()
    r.check(p.long(r.ST) == 0 and n == 4 and s[0][0] == MIN_START and mono(s), f"YES: 4 slices, slice 1 from {MIN_START} ({n}; {s[0][:2] if n else None})")
    for k in range(3):
        p.press("no", settle=200)
    p.poke(0x80000510 + 28, b"\0")           # TSTR OFF for the next open (the lane, as the Part sets it)
    p.run(100)
    if not stretching(p):
        r.arm(); r.tap("trig1", 120)
        n, s = r.slices()
        r.check(s[1][0] == p.long(FLEX1 + 300), f"TSTR OFF: slice 1 at the trim start ({s[1][0]})")
        p.press("no", settle=300)


def trig_led_msgs(p, ms):
    """Trig-row LED bitmap messages (rows 0-3) put on the panel link over ms."""
    from panel_link import PanelLink
    a = len(p.rt.uart64.tx); p.run(ms); raw = bytes(p.rt.uart64.tx[a:])
    L, n = PanelLink(), [0]
    orig = L._message

    def m(x):
        if x and 0x20 <= x[0] <= 0x23:
            n[0] += 1
        orig(x)
    L._message = m
    L.feed(raw)
    return n[0]


def sc_lockedit(r):
    """LOCK EDIT: [TRIG]+[BANK] opens the editor on the SLICE page with the held step's slice selected
    (STRT lock: SLIC on STRT/2, SLIC off the slice at STRT/128 of the trim; none: the Part's STRT); the
    encoders edit that slice while the trig is held; p-locked steps do not flicker in LAZY CHOP."""
    p = r.p
    F2 = FLEX1 + 1096
    trk = trac_ram(p, 0)
    p.press("rec", settle=300)
    p.key("trig3", True); p.run(150); p.press("bank", settle=400); p.key("trig3", False); p.run(400)
    if r.LC:
        p.press("pg_amp", settle=400); r.arm()
        n = trig_led_msgs(p, 1500)
        r.check(n == 0, f"LAZY CHOP open on a pattern with p-locked steps: no trig LED changes in 1.5 s ({n}; the H5 flicker sent pairs)")
        r.chop(4, gap=200); p.press("yes", settle=400)
    else:                                     # without LAZY CHOP: four slices written as a 200 ms chop would place them
        L = p.long(F2 + 304)
        cuts = [0, 8820, 17640, 26460, L]
        for k in range(4):
            p.poke(F2 + 312 + 12 * k, struct.pack(">IIi", cuts[k], cuts[k + 1], -1))
        p.poke(F2 + 1092, (4).to_bytes(4, "big"))
    n, s = r.slices(F2)
    r.check(n == 4, f"FLEX slot 2: 4 slices ({n})")
    for _ in range(4):
        p.press("no", settle=200)
    p.poke(trk + 0x59 + 2 * 32 + 1, bytes([64]))      # step 3: STRT 64 (the byte is STRT itself, as the knob stores it)
    p.key("trig3", True); p.run(150); p.press("bank", settle=500)
    marker = lambda: p.long(p.long(0x400CEB40))
    r.check(p.long(0x460E5E5C) == 1 and p.long(0x400CEB3C) == 3 and marker() == s[3][0],
            f"SLIC off, STRT 64: the SLICE page, slice 4 (STRT/128 of the take) selected (page {p.long(0x460E5E5C)}, slice {p.long(0x400CEB3C)})")
    sgn = lambda x: x - 0x100000000 if x > 0x7FFFFFFF else x
    off, zoom, width = sgn(p.long(0x400CEB2C)), p.long(0x400CEB24), p.long(0x400CEB1C)
    r.check(off <= s[3][0] - (s[3][1] - s[3][0]) // 5 and s[3][1] <= off + zoom * width,
            f"the whole slice in view with room before it: start {s[3][0]}, end {s[3][1]} within {off}..{off + zoom * width} ({zoom} frames a pixel, {width} px)")
    p.proc.command("knob 0x30 3", "ok"); p.run(250)
    n2, s2 = r.slices(F2)
    r.check(s2[3][0] > s[3][0] and s2[:3] == s[:3], f"trig held: knob A moves slice 4's start ({s[3][0]} -> {s2[3][0]})")
    p.key("trig3", False); p.run(300)
    for _ in range(4):
        p.press("no", settle=200)
    part = p.long(0x46C82456) + 0x8ED80 + p.peek(0x100B14CF, 1)[0] * 0x18B2
    p.poke(part + 0x1DA + 6 * 1 + 1, b"\x01")       # T1 FLEX SETUP SLIC ON
    for strt, want in ((4, 2), (8, 3), (9, 3)):            # stock plays slice STRT >> 1 (measured), capped
        p.poke(trk + 0x59 + 2 * 32 + 1, bytes([strt]))
        p.key("trig3", True); p.run(150); p.press("bank", settle=500)
        r.check(p.long(0x460E5E5C) == 1 and p.long(0x400CEB3C) == want, f"SLIC on, STRT {strt}: slice {want + 1} selected ({p.long(0x400CEB3C)})")
        p.key("trig3", False); p.run(300)
        for _ in range(4):
            p.press("no", settle=200)
    p.poke(F2 + 1092, (0).to_bytes(4, "big"))         # the sample without slices, SLIC still on:
    p.poke(trk + 0x59 + 2 * 32 + 1, bytes([64]))       # stock plays STRT 64 from 44100 (measured)
    p.key("trig3", True); p.run(150); p.press("bank", settle=500)
    off, zoom, width = sgn(p.long(0x400CEB2C)), p.long(0x400CEB24), p.long(0x400CEB1C)
    mid, fr = off + zoom * width // 2, p.long(F2 + 304) // 2
    r.check(off < fr < off + zoom * width and abs(mid - fr) < p.long(F2 + 304) // 16 and zoom * width >= p.long(F2 + 304) // 5,
            f"SLIC on, no slices, STRT 64: the view centred on frame {fr} ({off}..{off + zoom * width})")
    p.key("trig3", False); p.run(300)
    for _ in range(4):
        p.press("no", settle=200)
    p.poke(F2 + 1092, (n2).to_bytes(4, "big"))
    p.poke(part + 0x1DA + 6 * 1 + 1, b"\x00")       # SLIC off again
    for _ in range(4):
        p.press("no", settle=200)
    p.poke(trk + 0x59 + 2 * 32 + 1, b"\xff")
    p.key("trig3", True); p.run(150); p.press("bank", settle=500)
    r.check(p.long(0x460E5E5C) == 1 and p.long(0x400CEB3C) == 0, f"no STRT lock: the Part's STRT (0), slice 1 ({p.long(0x400CEB3C)})")
    p.key("trig3", False); p.run(300)


def sc_aedview(r):
    """The editor's zoom survives an audition: a trig in SLICES trig mode selects the slice and only
    scrolls its start into view (stock zoomed out to fit the whole slice)."""
    p = r.p
    r.editor()
    zoom = lambda: p.long(0x400CEB24)
    z0 = zoom()
    for _ in range(3):
        p.proc.command("knob 0x35 4", "ok"); p.run(150)
    z1 = zoom()
    r.check(z1 < z0, f"knob F zooms in ({z0:#x} -> {z1:#x})")
    p.poke(0x460D16F0, (3).to_bytes(4, "big")); p.run(100)    # SLICES trig mode
    r.tap("trig2", 150)
    off, step = p.long(0x400CEB2C) - 0x100000000 if p.long(0x400CEB2C) > 0x7FFFFFFF else p.long(0x400CEB2C), zoom()
    n, s = r.slices()
    r.check(p.long(0x400CEB3C) == 1 and step == z1, f"SLICES mode TRIG 2: slice 2 selected, the zoom kept ({z1:#x} -> {step:#x})")
    r.check(off <= s[1][0] <= off + step * 120, f"slice 2's start in view (view from {off}, {step} frames a pixel; start {s[1][0]})")
    r.tap("trig1", 150)
    r.check(p.long(0x400CEB3C) == 0 and zoom() == z1, f"TRIG 1: slice 1, the zoom still kept ({zoom():#x})")
    p.poke(0x460D16F0, (0).to_bytes(4, "big")); p.run(100)


def sc_lock(r):
    """[TRIG] + [BANK] in grid recording: the editor on the step's sample lock; LAZY CHOP on it."""
    p = r.p
    t1 = trac_ram(p, 0)
    r.check(p.peek(t1 + 0x78 + 2 * 0x20, 1)[0] == 1 and p.peek(t1 + 0x78 + 4 * 0x20, 1)[0] == 0xFF,
            f"the project: T1 step 3 locked to FLEX slot 2, step 5 unlocked ({p.peek(t1 + 0x78 + 2 * 0x20, 1).hex()})")
    flex1 = r.slices(FLEX1)
    p.press("rec", settle=300)
    r.check(p.long(0x460D1736) != 0, "grid recording on")
    p.key("trig3", True); p.run(150); p.press("bank", settle=400); p.key("trig3", False); p.run(400)
    r.check(p.long(EDITOR_KIND) == 1 and p.long(EDITOR_SLOT) == 1, f"[TRIG 3]+[BANK]: the editor on FLEX slot 2 ({p.long(EDITOR_KIND)}/{p.long(EDITOR_SLOT)})")
    r.check(p.peek(0x460D174A, 2) == b"\0\0" and p.peek(t1 + 7, 1)[0] & 4, "the trig released and step 3 keeps its trig")
    r.check(p.long(0x460D175C) == p.long(0x460E5E4C) != 0, "the editor is the top window: no popup over it")
    if r.LC:                                  # LAZY CHOP on the locked slot
        p.press("pg_amp", settle=400); r.arm()
        r.check(p.long(r.sym("lc_rec")) == FLEX1 + 1096 and p.long(r.ST) == 1, "LAZY CHOP arms on FLEX slot 2")
        r.chop(5, gap=150)
        r.check(p.long(VOICES + 8) == FLEX1 + 1096, f"the take that plays is FLEX slot 2 (a sample-lock trigger: {p.long(VOICES + 8):#x})")
        p.press("yes", settle=400)
        n, s = r.slices(FLEX1 + 1096)
        r.check(n == 5 and mono(s) and s[-1][1] == p.long(FLEX1 + 1096 + 304), f"YES: 5 slices in FLEX slot 2 ({n})")
        r.check(r.slices(FLEX1) == flex1, "FLEX slot 1 (T1's own) untouched")
    for _ in range(3):
        p.press("no", settle=200)
    p.key("trig5", True); p.run(150); p.press("bank", settle=400); p.key("trig5", False); p.run(400)
    r.check(p.long(EDITOR_KIND) == 1 and p.long(EDITOR_SLOT) == 0, f"[TRIG 5] (no lock)+[BANK]: T1's own sample ({p.long(EDITOR_SLOT)})")
    if r.LC:
        p.press("pg_amp", settle=400); r.arm()
        r.check(p.long(r.ST) == 1 and p.long(r.sym("lc_rec")) == FLEX1, "the editor is open: LAZY CHOP arms on T1's own slot")
        p.press("no", settle=300)
    for _ in range(3):
        p.press("no", settle=200)
    p.press("t2", settle=300)
    p.key("trig4", True); p.run(150); p.press("bank", settle=400); p.key("trig4", False); p.run(400)
    r.check(p.long(EDITOR_KIND) == 0 and p.long(EDITOR_SLOT) == 2, f"T2 [TRIG 4]+[BANK]: STATIC slot 3 ({p.long(EDITOR_KIND)}/{p.long(EDITOR_SLOT)})")
    if r.LC:
        p.press("pg_amp", settle=400); r.arm()
        r.check(p.long(r.ST) == 1 and p.long(r.sym("lc_rec")) == STATIC1 + 2 * 1096, "the editor is open: LAZY CHOP arms on STATIC slot 3")
        r.chop(3, gap=150)
        r.check(p.long(VOICES + 72 * 0 + 0xA8 + 8) == STATIC1 + 2 * 1096, f"T2 plays STATIC slot 3 ({p.long(VOICES + 0xA8 + 8):#x})")
        p.press("no", settle=300)
    for _ in range(3):
        p.press("no", settle=200)
    # held long enough, a locked trig shows stock's lock popup; [BANK] then swaps it for the editor
    p.key("trig4", True); p.run(1500)
    pop = p.long(0x460BEC60)
    p.press("bank", settle=400)
    r.check(pop != 0 and p.long(0x460BEC60) == 0 and (p.long(EDITOR_KIND), p.long(EDITOR_SLOT)) == (0, 2)
            and p.long(0x460D175C) == p.long(0x460E5E4C) != 0,
            f"T2 [TRIG 4] held to its lock popup, then [BANK]: the popup down, the editor on STATIC slot 3 ({pop:#x})")
    p.key("trig4", False); p.run(400)
    r.check(p.long(0x460E5E4C) != 0 and p.peek(0x460D174A, 2) == b"\0\0" and p.peek(trac_ram(p, 1) + 7, 1)[0] & 8,
            "released: the editor stays, step 4 keeps its trig")
    for _ in range(3):
        p.press("no", settle=200)
    ed = (p.long(EDITOR_KIND), p.long(EDITOR_SLOT))
    p.press("bank", settle=400)
    r.check((p.long(EDITOR_KIND), p.long(EDITOR_SLOT)) == ed and p.long(0x460E73BC) != 0, "[BANK] alone in grid recording: stock's (the bank prompt)")
    p.press("bank", settle=300); p.press("no", settle=200)
    p.press("rec", settle=300)
    p.key("trig3", True); p.run(150); p.press("bank", settle=400); p.key("trig3", False); p.run(300)
    r.check(p.long(0x460D1736) == 0 and (p.long(EDITOR_KIND), p.long(EDITOR_SLOT)) == ed, "outside grid recording, [TRIG]+[BANK] is stock's")


def sc_seq(r):
    p = r.p
    r.editor(); r.arm()
    p.press("play", settle=100)
    r.check(p.long(r.ST) == 1, "PLAY with the mode armed: still armed (the sequencer plays T1)")
    r.tap("trig1", 250)
    for k in range(2, 8):
        r.tap(f"trig{k}", 250)
    r.check(p.long(r.NXT) == 7, f"chopping while the sequencer runs: 7 markers ({p.long(r.NXT)})")
    r.check(lit(p) == page(7), f"the LEDs while playing: 7 red, TRIG 8 green ({sorted(lit(p))})")
    r.tap("trig8", 250); r.tap("trig9", 250); r.tap("trig10", 250)
    r.check(p.long(r.ST) == 2 and p.long(r.NXT) < 10,
            f"after the playhead goes back to the start, taps behind the last marker are refused ({p.long(r.NXT)})")
    p.press("yes", settle=400)
    n, s = r.slices()
    r.check(p.long(r.ST) == 0 and n == p.long(r.NXT) and mono(s) and s[-1][1] == p.long(FLEX1 + 304),
            f"YES writes them chained to the trim end ({n})")
    p.press("stop", settle=300)
    keep = r.slices()
    r.arm(); r.tap("trig1", 200); r.tap("trig2", 200)
    p.press("play", settle=200); r.tap("trig3", 200)
    p.press("stop", settle=300); r.tap("trig4", 200)
    r.check(p.long(r.ST) == 2 and p.long(r.NXT) == 4, "PLAY and STOP mid-chop leave the chop going")
    p.press("no", settle=400)
    r.check(p.long(r.ST) == 0 and r.slices() == keep, "NO afterwards restores the slices")


def sc_recnew(r):
    p = r.p
    p.chord("func", "recab", settle=400)         # RECORDING SETUP: TRIG ONE -> HOLD
    p.proc.command("knob 0x33 8", "ok"); p.run(300)
    p.press("no", settle=300)

    def take(ms):
        p.key("t1", True); p.run(40); p.key("recab", True); p.run(ms)
        p.key("recab", False); p.run(40); p.key("t1", False); p.run(500)
    take(1500)
    r.editor(("recab", "bank")); r.arm(); r.chop(4, gap=150)
    p.press("yes", settle=400)
    keep = r.slices(R1)
    r.check(keep[0] == 4, "4 slices on take 1")
    r.arm(); r.chop(2, gap=150)
    take(800)
    r.check(p.long(r.ST) == 0, "a new recording into the buffer ends the chop")
    n, s = r.slices(R1)
    want = keep[1][:-1] + [(keep[1][-1][0], p.long(R1 + 304), -1)]
    r.check(n == 4 and s == want,
            "and leaves the slices as before the chop, the last one ending at the new take's end, as stock does")
    r.check(not lit(p), f"and the LEDs are stock's ({sorted(lit(p))})")


def sc_ptn(r):
    p = r.p
    r.editor(); r.arm(); r.chop(3, gap=150)
    p.key("pattern", True); p.run(60); r.tap("trig4", 100); p.key("pattern", False); p.run(400)
    r.check(p.peek(0x80000004, 1)[0] == 3 and p.long(r.NXT) == 3 and p.long(r.ST) == 2,
            "[PTN]+TRIG 4 (the next key) selects pattern A04 and places no marker")
    p.proc.command("midi c0 01", "ok"); p.run(300)
    r.check(p.peek(0x80000004, 1)[0] == 1 and p.long(r.ST) == 2, "a MIDI program change (stopped) switches to A02; the chop goes on")
    r.tap("trig4", 150)
    r.check(p.long(r.NXT) == 4, "the next tap places a marker")
    p.press("play", settle=100)
    p.proc.command("midi c0 02", "ok"); p.run(2500)
    r.check(p.peek(0x80000004, 1)[0] == 2 and p.long(r.ST) == 2, "a program change while playing switches at the bar end; the chop goes on")
    p.press("yes", settle=400)
    n, s = r.slices()
    r.check(p.long(r.ST) == 0 and n >= 4 and mono(s) and s[-1][1] == p.long(FLEX1 + 304), f"YES writes them chained ({n})")
    p.press("stop", settle=300)


def make_stereo_tone(path, n):
    """110 Hz, the right channel at half level and 1 rad later: the sum's zero
    crossings are not the left channel's (ZERO SNAP must use the sum)."""
    import math, wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(b"".join(struct.pack("<hh", int(12000 * math.sin(2 * math.pi * 110 * i / 44100)),
                                           int(6000 * math.sin(2 * math.pi * 110 * i / 44100 + 1.0))) for i in range(n)))


def wav_sum(name):
    import wave
    wf = wave.open(str(OUT / "_projects" / name))
    raw = wf.readframes(wf.getnframes())
    return [int.from_bytes(raw[i:i + 2], "little", signed=True) + int.from_bytes(raw[i + 2:i + 4], "little", signed=True)
            for i in range(0, len(raw), 4)]


def sc_static(r):
    """ZERO SNAP on a STATIC sample: the audio comes from the card's stream buffer."""
    p = r.p
    tot = wav_sum("LC_STATIC_110.wav")
    left = wav_left_of("LC_STATIC_110.wav")
    cross = lambda v, i: 0 < i < len(v) and (v[i - 1] < 0) != (v[i] < 0)
    r.editor()
    r.check(p.long(EDITOR_KIND) == 0, f"[T1]+[BANK] opens the editor on T1's STATIC slot ({p.long(EDITOR_KIND)})")
    r.arm(); p.press("page", settle=300)
    r.check(p.long(r.sym("lc_snap")) == 1, "ZERO SNAP on")
    r.chop(7, gap=150)
    p.press("yes", settle=400)
    n, s = r.slices(STATIC1)
    starts = [x[0] for x in s[1:]]
    r.check(n == 7 and all(cross(tot, i) for i in starts), f"every marker on a zero crossing of the mono sum ({starts})")
    r.check(not all(cross(left, i) for i in starts), "not the left channel's crossings (the sum is used)")
    r.check(mono(s) and s[-1][1] == p.long(STATIC1 + 304), "chained to the trim end")


def build_projects(work):
    """The firmware's empty project, a 2 s FLEX sample on T1 with four slices; and T1 FLEX on R1."""
    import verify_repitch as vr
    otp = vr.otp
    fresh = OUT / "fresh"
    r = subprocess.run([str(VENV), str(ROOT / "tools/hw/ot_fresh.py"), "--image", str(IMAGE), "--out", str(fresh)],
                       cwd=ROOT, capture_output=True, text=True)
    src = fresh / "image" / "NOPROJ"
    if r.returncode or not (src / "project.work").is_file():
        sys.exit(f"  [FAIL] verify_lazy_chop: ot_fresh failed\n{(r.stdout + r.stderr)[-1500:]}")
    wav = work / "LC_440_120.wav"
    vr.make_loop(wav)
    n = vr.LOOP_FRAMES
    cards = {}
    swav = work / "LC_STATIC_110.wav"
    make_stereo_tone(swav, n)
    for kind in ("sample", "rec", "slic", "static", "lock", "stretch"):
        proj = work / kind / "project"
        vr.build_project(src, proj, 2 if kind == "stretch" else 0, 0, 120.0, 64, 127, "static" if kind == "static" else "flex")
        if kind in ("sample", "stretch"):
            for suffix in ("work", "strd"):
                pm = proj / f"markers.{suffix}"
                if pm.is_file():
                    d = bytearray(pm.read_bytes()); at = 0x16
                    sl = b"".join(struct.pack(">III", i * n // 4, (i + 1) * n // 4, 0xFFFFFFFF) for i in range(4))
                    d[at:at + 784] = struct.pack(">III", 0, n, 0) + sl + bytes(768 - len(sl)) + struct.pack(">I", 4)
                    d[-2:] = (sum(d[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
                    pm.write_bytes(bytes(d))
        elif kind == "lock":
            # T1 FLEX slot 1 (the sample) with step 3 locked to FLEX slot 2 and step 5 unlocked;
            # T2 STATIC slot 1 with step 4 locked to STATIC slot 3 (both the stereo tone)
            for suffix in ("work", "strd"):
                pw = proj / f"project.{suffix}"
                if not pw.is_file():          # a fresh project from an image without STORE has no .strd yet
                    continue
                raw = pw.read_bytes().decode("latin1")
                add = "".join(f"[SAMPLE]\r\nTYPE={t}\r\nSLOT={sl:03d}\r\nPATH=../AUDIO/LC_STATIC_110.wav\r\n"
                              "TRIM_BARSx100=100\r\nLOOP_BARSx100=100\r\nBPMx24=2880\r\nTSMODE=0\r\nLOOPMODE=0\r\n"
                              "GAIN=48\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n" for t, sl in (("FLEX", 2), ("STATIC", 1), ("STATIC", 3)))
                at = raw.find("[SAMPLE]")
                pw.write_bytes((raw[:at] + add + raw[at:]).encode("latin1"))
                pm = proj / f"markers.{suffix}"
                if pm.is_file():
                    d = bytearray(pm.read_bytes())
                    for rec in (1, 136, 138):
                        o = 0x16 + 784 * rec
                        d[o:o + 784] = struct.pack(">III", 0, n, 0) + bytes(772)
                    d[-2:] = (sum(d[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
                    pm.write_bytes(bytes(d))
            def mut(data):
                for pt in range(otp.NPARTS_ALL):
                    base = otp.PART_BASE + pt * otp.PART_STRIDE
                    data[base + otp.MTYPE_OFF + 1] = 0                       # T2 STATIC
                    data[base + 0x2d3 + 1 * 5 + 0] = 0                       # its slot 1
                t1, t2 = otp.trac_off(0, 0), otp.trac_off(0, 1)
                data[t1 + 7] |= (1 << 2) | (1 << 4)                          # T1 trigs on steps 3, 5
                data[t1 + 0x78 + 2 * 0x20] = 1                               # step 3: FLEX slot 2
                data[t2 + 7] |= 1 << 3                                       # T2 trig on step 4
                data[t2 + 0x78 + 3 * 0x20] = 2                               # step 4: STATIC slot 3
            otp._bank_write(proj, 1, mut, guard=False)
        elif kind == "slic":
            def mut(data):
                for pt in range(otp.NPARTS_ALL):
                    base = otp.PART_BASE + pt * otp.PART_STRIDE
                    data[base + vr.SETUP_OFF + 6 * 1 + 1] = 1                   # T1 FLEX SETUP: SLIC ON
                data[otp.trac_off(0, 0) + 6] |= 1                               # A01 T1: a trig on step 9 too
            otp._bank_write(proj, 1, mut, guard=False)
        else:
            def mut(data):
                for pt in range(otp.NPARTS_ALL):
                    data[otp.PART_BASE + pt * otp.PART_STRIDE + 0x2d3 + 1] = 128   # T1 FLEX slot: R1
            otp._bank_write(proj, 1, mut, guard=False)
        card = work / kind / "card.img"
        r = subprocess.run([str(VENV), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "LC",
                            "--tree", str(work / kind / "tree"), "--out", str(card),
                            "--audio", f"{swav if kind == 'static' else wav}:AUDIO/REPITCH_440_120.wav",
                            "--audio", f"{swav}:AUDIO/LC_STATIC_110.wav"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"  [FAIL] verify_lazy_chop: stage_card failed\n{(r.stdout + r.stderr)[-1500:]}")
        cards[kind] = card
    return cards


def scenario(name, base):
    work = OUT / name
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    card = work / "card.img"
    shutil.copy(base, card)
    r = Run(name, card, "OCTABAM", "LC", mkii=(name == "mkii"))
    try:
        with r.p as p:
            p.settle()
            {"chop": sc_chop, "cap": sc_cap, "save": sc_save, "leds": sc_leds, "mkii": sc_mkii, "rec": sc_rec,
             "seq": sc_seq, "recnew": sc_recnew, "ptn": sc_ptn, "slic": sc_slic, "snap": sc_snap, "static": sc_static, "undo": sc_undo, "aud": sc_aud, "audslic": sc_aud, "cost": sc_cost, "coststatic": sc_coststatic, "lock": sc_lock, "live": sc_live, "midi": sc_midi, "tstr": sc_tstr, "lockedit": sc_lockedit, "aedview": sc_aedview}[name](r)
    except Exception as e:                       # a scenario that dies is a failure, with its reason
        r.fails.append(f"{type(e).__name__}: {e}")
        r.notes.append(f"FAIL {type(e).__name__}: {e}")
    return name, r.fails, r.notes


def main(argv, gate="lazy_chop"):
    global GATE
    GATE = gate
    remix = argv[0] if argv and argv[0] not in SCENARIOS else os.environ.get("REMIX", "")
    only = [a for a in argv if a in SCENARIOS] or list(GROUPS[gate])
    if not EMU.is_file():
        return skip("the ColdFire port is not built (make emu-cf)")
    if not VENV.is_file():
        return skip("no .venv (make emu-setup)")
    sym, key = NEEDS[GATE]
    if not IMAGE.is_file() or not MAP.is_file() or f" {sym}\n" not in MAP.read_text():
        return skip(f"{key} is not in out/mainos_bus.bin (make bus REMIX={remix or f'<a remix with {key}>'})")
    if "bufsave" not in MAP.read_text():
        for n in ("rec", "recnew", "live", "midi"):
            if n in only:
                only.remove(n)
                print(f"  [SKIP] verify_{GATE} {n}: BUFFER SAVER is not in the image")
    OUT.mkdir(parents=True, exist_ok=True)
    cards = build_projects(OUT / "_projects")
    jobs = int(os.environ.get("LAZY_CHOP_JOBS", "2"))
    failed = []
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(scenario, n, cards["rec" if n in ("rec", "recnew", "live", "midi") else n if n in ("slic", "static") else "slic" if n == "audslic" else "static" if n == "coststatic" else "lock" if n in ("lock", "lockedit") else "stretch" if n == "tstr" else "sample"]) for n in only]
        for f in cf.as_completed(futs):
            name, fails, notes = f.result()
            for line in notes:
                print(f"    {name}: {line}")
            print(f"  [{'FAIL' if fails else 'PASS'}] verify_{GATE} {name}" + (f": {len(fails)} failed" if fails else ""))
            failed += [f"{name}: {x}" for x in fails]
    if failed:
        print(f"  [FAIL] verify_{GATE}: {len(failed)} check(s) failed")
        return 1
    print(f"  [PASS] verify_{GATE}: {', '.join(only)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
