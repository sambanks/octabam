#!/usr/bin/env python3
"""DRUMMER's KIT BALANCE through PAGES under the port (MKII): SRC pressed again on a DRUMMER track's LIVE page.

    .venv/bin/python3 modules/drummer/verify_live2.py [--image out/mainos_bus.bin]
        [--card out/drummer/port/groove/card.img] [--flex-card out/drummer/slices/card.img]

The cards are verify_port.py's groove (T1 a DRUMMER track) and probe_slices.py's (T1 a plain FLEX track).
Each run answers the date prompt (YES), selects T1, then:

  page1     T1 selected: its SRC page is shown (0x460d1684 = 0), so SRC once is the press again
  open      SRC: KIT BALANCE's window is up (dr_l2), its six Part bytes seeded at 64, marked 'M'
  turn      open, A -64, C +30: KICK 0, HATS 94 in the Part (STATIC's PLAYBACK bytes of T1)
  again     open, SRC again: NEXT in the same window (view 1; FILLS left SRC for the KIT window's page 4)
  again2    open, SRC twice more: the window closed, the LIVE page back
  next      NEXT, B +1 (STOP), C +3 (FILL+CR), D +1 (TRIP), E +5, F +9 (BRK, clamped at STUTTER), A +8 detents (WHEN BAR, 4 a value, armed once the knob rests):
            B-F in the Part (THRU's SETUP column of T1), marked 'N'; WHEN armed in RAM, not in the Part
  fills     KIT window page 4 (TRIG 1 + BANK, RIGHT x3): A +2 (RUDI), D +3 (PARA), B +9 (PHRS, the last), C +2
            (2BT), E +1 (TOMS), F -1 (AUTO)
  stik      KIT page 4, D +3 with FILL AUTO: nothing (STIK needs a family)
  save      next and fills, then PROJECT > SAVE PROJECT; boot2 boots the saved card: the bytes kept (validator, file)
  amp       open, AMP: the window closed
  double    SRC, SRC again 60 ms later (stock's double press): SRC SETUP (CONFIG), KIT BALANCE closed under it
  func      FUNC held 1 s on LIVE: no KIT BALANCE (image 56's FUNC view is gone)
  flex      the FLEX card: SRC: no window
  kit       TRIG 1 held, BANK: the KIT window (dr_kw; image 57, TRIG + UP before)
  bank      BANK alone: no KIT window (a plain FLEX track does what stock does: nothing)

Screens are written beside the logs (out/drummer/live2/<case>.png).
"""
import argparse
import concurrent.futures as cf
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EMU = ROOT / "out/emu/ot_emu"
OUT = ROOT / "out/drummer/live2"
PART = 0x40170F60                     # bank 1's Part 1 in RAM (the cards' working Part)
MIX_AT, MARK = 0x2A, 0x3F             # T1: STATIC's PLAYBACK column, the mark after "DR",1
FILLS_AT, FMARK = 0x1EC, 0x40         # T1: NEIGHBOR's SETUP column, the mark after 'M'
NX_AT, NMARK = 0x1E6, 0x41            # T1: NEXT's B-F, THRU's SETUP column, the mark after 'F'
PROJ, RIGHT, DOWN = 0x1C, 0x21, 0x20
PART_LEN = 0x200
SRC, AMP, FUNC, YES, T1 = 0x22, 0x23, 0x2D, 0x31, 0x10
FAILS = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def symbol(name):
    for line in (ROOT / "out/platform/runtime/runtime.map").read_text().splitlines():
        w = line.split()
        if len(w) == 2 and w[1] == name and w[0].startswith("0x"):
            return int(w[0], 16)
    sys.exit(f"verify_live2: {name} not in the runtime map (build the image first)")


def tap(code, gap=0.5, hold=0.06):
    return [(gap, f"key {code:#x} down"), (hold, f"key {code:#x} up")]


BASE = tap(YES, 0.3) + tap(T1, 1.2)
OPEN = BASE + tap(SRC, 0.6)          # T1's selection shows its SRC page: one press is "again"
KIT4 = BASE + [(0.6, "key 0x0 down"), (0.1, "key 0x2f down"), (0.1, "key 0x2f up"), (0.3, "key 0x0 up")] \
    + tap(RIGHT, 0.5) + tap(RIGHT, 0.4) + tap(RIGHT, 0.4)      # the KIT window's page 4: FILLS
FILL_TURNS = [(0.4, "enc 0 2"), (0.3, "enc 3 3"), (0.3, "enc 1 9"), (0.3, "enc 2 2"), (0.3, "enc 4 1")]
NEXT_TURNS = [(0.4, "enc 1 1"), (0.3, "enc 2 3"), (0.3, "enc 3 1"), (0.3, "enc 4 5"), (0.3, "enc 5 9"), (0.3, "enc 0 8")]   # WHEN: 4 detents a value
CASES = {
    "open": (OPEN + [(0.6, "quit")], "card"),
    "turn": (OPEN + [(0.4, "enc 0 -64"), (0.3, "enc 2 6"), (0.3, "enc 1 3"), (0.3, "enc 1 -5"), (0.3, "enc 3 -2"), (0.6, "quit")], "card"),
    "again": (OPEN + tap(SRC, 0.6) + [(0.6, "quit")], "card"),
    "again2": (OPEN + tap(SRC, 0.6) + tap(SRC, 0.6) + [(0.6, "quit")], "card"),
    "next": (OPEN + tap(SRC, 0.6) + NEXT_TURNS + [(1.0, "quit")], "card"),   # WHEN arms 0.5 s after it rests
    "fills": (KIT4 + FILL_TURNS + [(0.3, "enc 5 -1"), (0.6, "quit")], "card"),
    "stik": (KIT4 + [(0.4, "enc 3 3"), (0.6, "quit")], "card"),
    "save": (OPEN + tap(SRC, 0.6) + NEXT_TURNS + tap(SRC, 0.6) + [(0.4, "key 0x0 down"), (0.1, "key 0x2f down"),
             (0.1, "key 0x2f up"), (0.3, "key 0x0 up")] + tap(RIGHT, 0.5) + tap(RIGHT, 0.4) + tap(RIGHT, 0.4)
             + FILL_TURNS + tap(YES, 0.5) + tap(PROJ, 1.0) + tap(RIGHT, 0.7) + tap(DOWN, 0.5)
             + tap(YES, 1.1) + tap(YES, 30.0) + [(1.5, "quit")], "card"),
    "boot2": ([(0.3, f"key {YES:#x} down"), (0.06, f"key {YES:#x} up"), (1.5, "quit")], "saved"),
    "amp": (OPEN + tap(AMP, 0.6) + [(0.6, "quit")], "card"),
    "double": (BASE + tap(SRC, 0.6) + tap(SRC, 0.06) + [(0.8, "quit")], "card"),
    "page1": (BASE + [(0.8, "quit")], "card"),
    "kit": (BASE + [(0.6, "key 0x0 down"), (0.1, "key 0x2f down"), (0.1, "key 0x2f up"), (0.3, "key 0x0 up"),
                    (0.6, "quit")], "card"),
    "bank": (BASE + tap(0x2F, 0.6) + [(0.6, "quit")], "card"),
    "func": (BASE + [(0.6, f"key {FUNC:#x} down"), (1.0, "quit")], "card"),
    "flex": (OPEN + [(0.6, "quit")], "flex_card"),
}


def run(a, name):
    events, card = CASES[name]
    t, lines = 0.0, []
    for gap, ev in events:
        t += gap
        lines.append(f"{int(t * 1000)} {ev}")
    script = OUT / f"{name}.script"
    script.write_text("\n".join(lines) + "\n")
    l2, kw, view, when = symbol("dr_l2"), symbol("dr_kw"), symbol("dr_l2_view"), symbol("dr_nx_when")
    card_path = str(OUT / "save.img") if card == "saved" else getattr(a, card)
    extra = ["--card-out", str(OUT / "save.img")] if name == "save" else []
    cmd = [str(EMU), "--image", a.image, "--card", card_path, "--set", "OCTABAM", "--project", "RIG", "--mkii",
           "--load-ms", "90000", "--live-script", str(script), "--lcd", str(OUT / f"{name}.lcd"), *extra,
           "--mem-dump", f"{l2:#x},4={OUT}/{name}_l2.bin;{kw:#x},4={OUT}/{name}_kw.bin;{PART:#x},{PART_LEN}={OUT}/{name}_part.bin;"
                         f"0x460d1684,4={OUT}/{name}_page.bin;{view:#x},1={OUT}/{name}_view.bin;{when:#x},1={OUT}/{name}_when.bin"]
    with open(OUT / f"{name}.log", "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    subprocess.run([str(ROOT / ".venv/bin/python3"), str(ROOT / "tools/emu/lcd_view.py"), str(OUT / f"{name}.lcd"),
                    "--png", str(OUT / f"{name}.png")], cwd=ROOT, capture_output=True)
    rd = lambda s: (OUT / f"{name}_{s}.bin").read_bytes() if (OUT / f"{name}_{s}.bin").is_file() else b""
    return name, rc, rd("l2"), rd("part"), rd("page"), rd("kw"), rd("view"), rd("when")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--card", default=str(ROOT / "out/drummer/port/groove/card.img"))
    ap.add_argument("--flex-card", default=str(ROOT / "out/drummer/slices/card.img"))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print("DRUMMER KIT BALANCE, NEXT and KIT FILLS (PAGES, port, MKII)")
    first = [n for n in CASES if n != "boot2"]
    with cf.ThreadPoolExecutor(len(first)) as ex:
        res = {r[0]: r[1:] for r in ex.map(lambda n: run(a, n), first)}
    r = run(a, "boot2")                      # on the card "save" left
    res[r[0]] = r[1:]
    up = lambda n: len(res[n][1]) == 4 and int.from_bytes(res[n][1], "big") != 0
    mix = lambda n: list(res[n][2][MIX_AT:MIX_AT + 6]) if len(res[n][2]) == PART_LEN else []
    fil = lambda n: (list(res[n][2][FILLS_AT:FILLS_AT + 6]), res[n][2][FMARK]) if len(res[n][2]) == PART_LEN else ([], 0)
    view = lambda n: res[n][5][:1].hex()
    nxt = lambda n: (list(res[n][2][NX_AT:NX_AT + 5]), res[n][2][NMARK]) if len(res[n][2]) == PART_LEN else ([], 0)
    for n, (rc, *_r) in res.items():
        check(f"{n}: the port ran", rc == 0, f"exit {rc}")
    check("page1: T1 selected shows its SRC page", res["page1"][3] == bytes(4), res["page1"][3].hex())
    check("open: SRC again opens KIT BALANCE on a DRUMMER track", up("open"))
    check("open: the six bytes seeded at 64 and marked", mix("open") == [64] * 6 and res["open"][2][MARK] == ord("M"),
          f"{mix('open')} mark {res['open'][2][MARK] if res['open'][2] else None}")
    check("turn (5 % detents, the middle stops once): A -64 KICK 0 (OUT), C +6 HATS 83 (+30), B +3 then -5 SNARE 64 (=), D -2 CYMB 58 (-10)",
          mix("turn") == [0, 64, 83, 58, 64, 64], f"{mix('turn')}")
    check("again: SRC again shows NEXT in the window (view 1)", up("again") and view("again") == "01", view("again"))
    check("next: B STOP, C FILL+CR, D TRIP, E 5, F STUTTER (clamped) in the Part, marked 'N'; WHEN BAR armed in RAM",
          nxt("next") == ([1, 3, 1, 5, 4], ord("N")) and res["next"][6] == b"\x02", f"{nxt('next')} when {res['next'][6].hex()}")
    check("again2: SRC once more closes it (the LIVE page)", not up("again2") and res["again2"][3] == bytes(4))
    check("fills: A RUDI, D PARA, B PHRS (clamped, the last), C 2BT, E TOMS, F AUTO (clamped at 0)",
          fil("fills")[0] == [2, 3, 2, 3, 1, 0], str(fil("fills")))
    check("stik: STIK does not move under FILL AUTO", fil("stik")[0] == [0] * 6, str(fil("stik")))
    check("save: the run saved the card", (OUT / "save.img").is_file())
    check("boot2: the saved card's Part keeps FILLS (the Part validator at the load, the bank file)",
          fil("boot2") == ([2, 3, 2, 3, 1, 0], ord("F")) and mix("boot2") == [64] * 6, f"{fil('boot2')} {mix('boot2')}")
    check("boot2: ... and NEXT's B-F (THRU's SETUP column kept), WHEN not (a live gesture)",
          nxt("boot2") == ([1, 3, 1, 5, 4], ord("N")) and res["boot2"][6] == b"\x00", f"{nxt('boot2')} when {res['boot2'][6].hex()}")
    check("amp: AMP closes it", not up("amp"))
    check("double: stock's double press opens SRC SETUP, no KIT BALANCE", not up("double"))
    check("func: FUNC held opens nothing", not up("func"))
    check("flex: a plain FLEX track gets no KIT BALANCE", not up("flex"))
    kit = lambda n: len(res[n][4]) == 4 and int.from_bytes(res[n][4], "big") != 0
    check("kit: TRIG 1 + BANK opens the KIT window", kit("kit"))
    check("bank: BANK alone opens no KIT (stock's SELECT BANK)", not kit("bank"))
    print(f"{'PASS' if not FAILS else 'FAIL'}: DRUMMER KIT BALANCE")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
