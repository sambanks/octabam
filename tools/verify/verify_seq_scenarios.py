#!/usr/bin/env python3
"""SEQ port scenarios from docs/site/usage/seq.md (MenuPort, MKII).

Primes track bank/plock state, presses YES / FUNC+BANK / CUE, checks pattern
bytes. Requires out/mainos_bus.bin + ot_emu (REMIX with SEQ, e.g. cx).
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools/verify"), str(ROOT / "tools/panel")]

from stems_panel import MenuPort  # noqa: E402
from seq_port_fixture import stage_project  # noqa: E402
from panel_server import popup_geometry  # noqa: E402

IMAGE = ROOT / "out/mainos_bus.bin"
CARD = ROOT / "out/_seq_scenarios_card.img"
MAP = ROOT / "out/platform/runtime/runtime.map"

DBPTR_ADDR = 0x46c82456
UI_PTN = 0x100b14d0
UI_TRACK = 0x100b14cc
PTN_STR = 0x8ed8
TRK_STR = 0x91a
LOCK0 = 0x59
LOCK_PTCH = 0
LOCK_VOL = 15
M_OBJ = 0x460e5e30
M_LAB = 0x460e5e2c
NV_SCALE = 0x100b14ec
NV_ROOT = 0x100b14ee
# Stock confirm dialog owns keys while ARE YOU SURE? is up (store.s / DIALOG).
DIALOG_OPEN = 0x460e5cd0
UI_WINDOW = 0x460d175c
POPUP = 0x46c7d34c
HELD = 0x460fab40          # stock track-held bitmask (TRK_STOCK press)
MUTE_CUE = 0x80000008      # mute bit 8+t, cue bit 16+t (MIDI.md)
POOL = 0x460e70e0          # machine / sample chooser pool (double-tap QA)

FAILS = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global FAILS
    if ok:
        print(f"  [PASS] {name}" + (f" ({detail})" if detail else ""))
    else:
        FAILS += 1
        print(f"  [FAIL] {name}" + (f": {detail}" if detail else ""))


def sym(name: str) -> int:
    text = MAP.read_text()
    for line in text.splitlines():
        if line.rstrip().endswith(name) and "0x" in line:
            return int(line.split()[0], 16)
    raise SystemExit(f"symbol missing in runtime.map: {name}")


def sym_opt(name: str) -> int | None:
    text = MAP.read_text()
    for line in text.splitlines():
        if line.rstrip().endswith(name) and "0x" in line:
            return int(line.split()[0], 16)
    return None


def u8(p, a: int) -> int:
    return p.peek(a, 1)[0]


def poke32(p, a: int, v: int) -> None:
    p.poke(a, int(v).to_bytes(4, "big"))


def poke8(p, a: int, v: int) -> None:
    p.poke(a, bytes([v & 0xFF]))


def ensure_card() -> None:
    stage_project(IMAGE, CARD, ROOT / "out/_seq_scenarios_tree")


def trac(p, trk: int = 0) -> int:
    return p.long(DBPTR_ADDR) + u8(p, UI_PTN) * PTN_STR + trk * TRK_STR


def mask_of(p, trk: int = 0) -> bytes:
    return p.peek(trac(p, trk), 8)


def tl_of(p, trk: int = 0) -> bytes:
    return p.peek(trac(p, trk) + 0x10, 8)


def locks_of(p, dest: int, n: int = 16, trk: int = 0) -> list[int]:
    t = trac(p, trk)
    return [u8(p, t + LOCK0 + s * 32 + dest) for s in range(n)]


def live(vals: list[int]) -> int:
    return sum(1 for v in vals if v != 0xFF)


def popcount_mask(m: bytes) -> int:
    return sum(bin(b).count("1") for b in m)


def mask_bit(m: bytes, step: int) -> bool:
    """Same packing as ef_bit_addr: byte 7-(step>>3), bit (step&7)."""
    return bool(m[7 - (step >> 3)] & (1 << (step & 7)))


def locks_have_trig_or_tl(p, dest_locks: list[int], trk: int = 0) -> bool:
    m = mask_of(p, trk)
    tl = tl_of(p, trk)
    for step, v in enumerate(dest_locks):
        if v == 0xFF:
            continue
        if not (mask_bit(m, step) or mask_bit(tl, step)):
            return False
    return True


def ptch_only_on_trigs(p, trk: int = 0) -> bool:
    m = mask_of(p, trk)
    for step, v in enumerate(locks_of(p, LOCK_PTCH, trk=trk)):
        if v != 0xFF and not mask_bit(m, step):
            return False
    return True


class SeqPort:
    def __init__(self, p: MenuPort):
        self.p = p
        self.ef = sym("ef_win")
        self.bank = sym("ef_bank")
        self.dep = sym("ef_dep_mem")
        self.plk = sym("ef_plk_mem")
        self.lane_mem = sym("ef_lane_mem")
        # Layout after lane_mem: dirty, ask, unlocked (see seq.s .data).
        # Prefer exported symbols when the map was rebuilt with .globl.
        self.ask = sym_opt("ef_ask") or (self.lane_mem + 12)
        self.unlocked = sym_opt("ef_unlocked") or (self.lane_mem + 16)
        self.free = sym_opt("ef_free") or (self.ef + 0x54)
        self.from_cue = sym_opt("ef_from_cue") or (self.ef + 0x58)
        self.cue_chord = sym_opt("ef_cue_chord") or (self.from_cue + 4)
        self.cue_snap = sym_opt("ef_cue_snap") or (self.cue_chord + 4)
        # ef_mask follows ef_cue_snap.
        self.ef_mask = sym_opt("ef_mask") or (self.cue_snap + 4)
        self.ef_pmask = sym_opt("ef_pmask") or (self.ef_mask + 8)

    def open_seq(self, track: str = "t1") -> None:
        self.p.chord(track, "page", settle=500)
        check(f"SEQ opens on {track} (ef_win nonzero)", self.p.long(self.ef) != 0,
              f"ef_win={self.p.long(self.ef):#x}")

    def close_seq(self) -> None:
        self.p.press("no", settle=400)

    def prime(self, *, lane: int, dest: int, depth: int, pulses: int,
              rot: int = 0, trig_pulses: int = 5, trig_rot: int = 0,
              trk: int = 0) -> None:
        """Write bank + plock/dep/lane so YES load_slot sees it.

        On TRIG lane, pulses/rot are the sample-trig rhythm (and also seed
        the current DEST's PLCK copy the way a panel bake would). On PLCK
        lane, pulses/rot are that DEST's lock rhythm; trig_pulses/trig_rot
        stay on the TRIG bank slot.
        """
        if lane == 0:
            trig_pulses = pulses
            trig_rot = rot
        b = self.bank + trk * 28
        poke32(self.p, b + 0, trig_pulses)
        poke32(self.p, b + 4, trig_rot)
        poke32(self.p, b + 8, dest)
        poke32(self.p, b + 12, depth)
        poke32(self.p, b + 16, 0)
        self.p.poke(b + 20, bytes(8))
        poke8(self.p, self.lane_mem + trk, lane)
        poke8(self.p, self.dep + trk * 36 + dest, depth & 0xFF)
        off = (trk * 36 + dest) * 12
        poke8(self.p, self.plk + off, pulses & 0xFF)
        poke8(self.p, self.plk + off + 1, rot & 0xFF)
        poke8(self.p, self.plk + off + 2, 0)
        self.p.poke(self.plk + off + 4, bytes(8))
        for a, v in (
            (self.ef + 0x18, lane),
            (self.ef + 0x28, dest),
            (self.ef + 0x2c, depth),
            (self.ef + 0x10, pulses),
            (self.ef + 0x14, rot),
            (self.ef + 8, trig_pulses),
            (self.ef + 0xC, trig_rot),
            (self.ef + 0x1C, 0),
            (self.from_cue, 0),
            (self.free, 0),
        ):
            poke32(self.p, a, v)

    def yes(self) -> None:
        self.p.press("yes", settle=900)

    def clear_labels(self) -> list[str]:
        obj = self.p.long(M_OBJ)
        lab = self.p.long(M_LAB)
        if not obj or not lab:
            return []
        out = []
        for i in range(3):
            lp = self.p.long(lab + 4 * i)
            out.append(self.p.cstr(lp, 24) if lp else "")
        return out


def run_scenarios() -> int:
    global FAILS
    if not IMAGE.exists():
        print("SEQ scenarios: FAIL (no out/mainos_bus.bin)")
        return 1
    if not MAP.exists():
        print("SEQ scenarios: FAIL (no runtime.map)")
        return 1
    emu = ROOT / "out/emu/ot_emu"
    if not emu.exists():
        print("SEQ scenarios: FAIL (no out/emu/ot_emu)")
        return 1

    ensure_card()
    print("SEQ port scenarios (usage/seq.md):")

    with MenuPort(IMAGE, CARD, "OCTABAM", "A", mkii=True) as port:
        port.settle()
        for _ in range(3):
            port.press("no", settle=80)
        s = SeqPort(port)

        # --- open ---
        s.open_seq()

        # --- Place sample trigs (TRIG, PTCH, DPTH 0) ---
        poke8(port, NV_SCALE, 0)
        s.prime(lane=0, dest=0, depth=0, pulses=5, trig_pulses=5)
        s.yes()
        m = mask_of(port)
        check("TRIG DPTH0 places sample trigs", popcount_mask(m) >= 1, m.hex())
        check("TRIG DPTH0 clears PTCH locks", live(locks_of(port, LOCK_PTCH)) == 0)

        # --- Lock pitch on those trigs (TRIG, PTCH, DPTH>0, SCALE OFF) ---
        s.prime(lane=0, dest=0, depth=64, pulses=5, trig_pulses=5)
        s.yes()
        pt = locks_of(port, LOCK_PTCH)
        check("TRIG+PTCH+DPTH writes PTCH on trig steps", live(pt) >= 1)
        check("TRIG+PTCH keeps sample trigs", mask_of(port) != bytes(8))
        check("TRIG+PTCH locks only on sample trigs", ptch_only_on_trigs(port))

        # --- Add volume locks on another rhythm (PLCK VOL) ---
        trig_before = mask_of(port)
        pt_before = locks_of(port, LOCK_PTCH)
        s.prime(lane=1, dest=LOCK_VOL, depth=64, pulses=7, trig_pulses=5)
        s.yes()
        vol = locks_of(port, LOCK_VOL)
        check("PLCK+VOL writes VOL locks", live(vol) >= 1, f"live={live(vol)}")
        check("PLCK+VOL leaves sample trigs alone", mask_of(port) == trig_before)
        check("PLCK+VOL leaves PTCH alone", locks_of(port, LOCK_PTCH) == pt_before)
        check("PLCK+VOL locks sit on sample trig or trigless",
              locks_have_trig_or_tl(port, vol),
              f"tl={tl_of(port).hex()} vol_live={live(vol)}")

        # --- Change sample-trig rhythm (TRIG reshape; usage figure) ---
        vol_before = locks_of(port, LOCK_VOL)
        s.prime(lane=0, dest=0, depth=64, pulses=3, trig_pulses=3)
        s.yes()
        m = mask_of(port)
        pt = locks_of(port, LOCK_PTCH)
        vol = locks_of(port, LOCK_VOL)
        check("TRIG reshape writes fewer sample trigs",
              popcount_mask(m) == 3, m.hex())
        check("TRIG reshape rewrites PTCH only on new trigs",
              ptch_only_on_trigs(port) and live(pt) == 3,
              f"pt_live={live(pt)} m={m.hex()}")
        # Other DEST kept; silent steps with VOL become trigless.
        kept = sum(1 for a, b in zip(vol_before, vol) if a != 0xFF and a == b)
        check("TRIG reshape keeps other DEST (VOL) values",
              kept >= 1 and live(vol) >= 1,
              f"kept={kept} vol_live={live(vol)}")
        orphan_tl_ok = True
        for step, v in enumerate(vol):
            if v == 0xFF:
                continue
            if not mask_bit(m, step) and not mask_bit(tl_of(port), step):
                orphan_tl_ok = False
                break
        check("TRIG reshape sets TL where VOL survives without trig",
              orphan_tl_ok, f"tl={tl_of(port).hex()}")

        # --- Rewrite one destination via PLCK (overwrite; usage figure) ---
        trig_before = mask_of(port)
        vol_before = locks_of(port, LOCK_VOL)
        pt_before = locks_of(port, LOCK_PTCH)
        s.prime(lane=1, dest=0, depth=64, pulses=5, rot=1, trig_pulses=3)
        s.yes()
        pt = locks_of(port, LOCK_PTCH)
        check("PLCK overwrite changes PTCH pattern", pt != pt_before,
              f"before_live={live(pt_before)} after_live={live(pt)}")
        check("PLCK overwrite leaves sample trigs alone", mask_of(port) == trig_before)
        check("PLCK overwrite leaves other DEST (VOL)",
              locks_of(port, LOCK_VOL) == vol_before)
        check("PLCK overwrite locks sit on trig or TL",
              locks_have_trig_or_tl(port, pt))

        # --- PLCK PTCH SCALE OFF = base Part pitch, no new trigs ---
        trig_before = mask_of(port)
        poke8(port, NV_SCALE, 0)
        s.prime(lane=1, dest=0, depth=64, pulses=5, trig_pulses=0)
        s.yes()
        pt = locks_of(port, LOCK_PTCH)
        vals = {v for v in pt if v != 0xFF}
        check("PLCK+PTCH SCALE OFF writes trigless PTCH", live(pt) >= 1)
        check("PLCK+PTCH SCALE OFF uses one base pitch",
              len(vals) == 1, f"vals={vals}")
        check("PLCK+PTCH leaves sample trigs alone", mask_of(port) == trig_before)

        # --- PLCK PTCH SCALE ON still writes ---
        poke8(port, NV_SCALE, 1)
        poke8(port, NV_ROOT, 0)
        s.prime(lane=1, dest=0, depth=64, pulses=5, trig_pulses=0)
        s.yes()
        check("PLCK+PTCH SCALE ON writes PTCH locks", live(locks_of(port, LOCK_PTCH)) >= 1)
        poke8(port, NV_SCALE, 0)

        # --- Clear one destination (PLCK PULS 0); orphan TL drops ---
        s.prime(lane=1, dest=LOCK_VOL, depth=64, pulses=9, trig_pulses=3)
        s.yes()
        check("preclear VOL live", live(locks_of(port, LOCK_VOL)) >= 1)
        trig_before = mask_of(port)
        s.prime(lane=1, dest=LOCK_VOL, depth=64, pulses=0, trig_pulses=3)
        s.yes()
        check("PLCK PULS0 clears that DEST", live(locks_of(port, LOCK_VOL)) == 0)
        check("PLCK PULS0 leaves sample trigs", mask_of(port) == trig_before)
        tl = tl_of(port)
        pt = locks_of(port, LOCK_PTCH)
        vol_gone_orphan = False
        for step in range(16):
            if mask_bit(tl, step) and pt[step] == 0xFF and not mask_bit(mask_of(port), step):
                # TL with neither sample trig nor PTCH after VOL clear — orphan.
                vol_gone_orphan = True
                break
        check("PLCK PULS0 drops orphan TL (no PTCH/trig)",
              not vol_gone_orphan, f"tl={tl.hex()}")

        # --- TRIG DPTH0 clears current DEST only ---
        s.prime(lane=1, dest=LOCK_VOL, depth=64, pulses=5, trig_pulses=3)
        s.yes()
        s.prime(lane=0, dest=0, depth=64, pulses=5, trig_pulses=5)
        s.yes()
        check("pre DPTH0 has PTCH+VOL",
              live(locks_of(port, LOCK_PTCH)) >= 1 and live(locks_of(port, LOCK_VOL)) >= 1)
        s.prime(lane=0, dest=0, depth=0, pulses=5, trig_pulses=5)
        s.yes()
        check("TRIG DPTH0 clears current DEST (PTCH)", live(locks_of(port, LOCK_PTCH)) == 0)
        check("TRIG DPTH0 keeps other DEST (VOL)",
              live(locks_of(port, LOCK_VOL)) >= 1)
        check("TRIG DPTH0 keeps sample trigs", popcount_mask(mask_of(port)) >= 1)

        # --- ROT mutation: same PULS, different ROT → different mask ---
        s.prime(lane=0, dest=0, depth=0, pulses=5, rot=0, trig_pulses=5)
        s.yes()
        m0 = mask_of(port)
        s.prime(lane=0, dest=0, depth=0, pulses=5, rot=3, trig_pulses=5)
        s.yes()
        m1 = mask_of(port)
        check("TRIG ROT change keeps popcount",
              popcount_mask(m0) == popcount_mask(m1) == 5,
              f"{m0.hex()} vs {m1.hex()}")
        check("TRIG ROT change moves which steps", m0 != m1)

        # --- FUNC+BANK clear list (SEQ soft-closes; list on top) ---
        port.chord("func", "bank", settle=700)
        labs = s.clear_labels()
        check("FUNC+BANK opens CLEAR DEST list",
              labs[:1] == ["CLEAR DEST"] and "CLEAR ALL DEST" in labs
              and "CLEAR ALL+TRIGS" in labs,
              str(labs))
        check("clear list stays up (no Detour+layer toggle)",
              port.long(M_OBJ) != 0)
        check("SEQ soft-closed while CLEAR up", port.long(s.ef) == 0)

        port.chord("func", "bank", settle=700)
        check("FUNC+BANK toggle dismisses clear list", port.long(M_OBJ) == 0)
        check("FUNC+BANK toggle restores SEQ", port.long(s.ef) != 0)

        port.chord("func", "bank", settle=700)
        check("FUNC+BANK reopens CLEAR list", "CLEAR DEST" in s.clear_labels())
        check("SEQ soft-closed again", port.long(s.ef) == 0)
        port.press("no", settle=500)
        check("NO dismisses clear list", port.long(M_OBJ) == 0)
        check("NO restores SEQ", port.long(s.ef) != 0)
        port.press("no", settle=400)
        check("after NO-restore, next NO closes SEQ", port.long(s.ef) == 0)
        s.open_seq()

        # CLEAR DEST via list YES → wipe + restore SEQ
        s.prime(lane=1, dest=0, depth=64, pulses=5, trig_pulses=0)
        s.yes()
        check("preclear PTCH live", live(locks_of(port, LOCK_PTCH)) >= 1)
        port.chord("func", "bank", settle=600)
        check("SEQ soft-closed before CLEAR DEST YES", port.long(s.ef) == 0)
        port.press("yes", settle=800)
        check("CLEAR DEST dismisses list", port.long(M_OBJ) == 0)
        check("CLEAR DEST restores SEQ", port.long(s.ef) != 0)
        check("CLEAR DEST wipes PTCH locks", live(locks_of(port, LOCK_PTCH)) == 0)
        check("CLEAR DEST resets DPTH/PULS/ROT working",
              port.long(s.ef + 0x2C) == 0 and port.long(s.ef + 0x10) == 0
              and port.long(s.ef + 0x14) == 0,
              f"dep={port.long(s.ef+0x2C)} pp={port.long(s.ef+0x10)} prot={port.long(s.ef+0x14)}")

        # CLEAR ALL DEST via list YES
        s.prime(lane=1, dest=LOCK_VOL, depth=64, pulses=5, trig_pulses=5)
        s.yes()
        s.prime(lane=1, dest=0, depth=64, pulses=5, trig_pulses=5)
        s.yes()
        check("preclear ALL DEST has PTCH+VOL",
              live(locks_of(port, LOCK_PTCH)) >= 1 and live(locks_of(port, LOCK_VOL)) >= 1)
        trig_before_all = mask_of(port)
        port.chord("func", "bank", settle=600)
        port.press("down", settle=200)
        port.press("yes", settle=800)
        check("CLEAR ALL DEST dismisses list", port.long(M_OBJ) == 0)
        check("CLEAR ALL DEST restores SEQ", port.long(s.ef) != 0)
        check("CLEAR ALL DEST wipes PTCH+VOL",
              live(locks_of(port, LOCK_PTCH)) == 0 and live(locks_of(port, LOCK_VOL)) == 0)
        check("CLEAR ALL DEST leaves sample trigs", mask_of(port) == trig_before_all)

        # CLEAR ALL+TRIGS via list YES
        s.prime(lane=0, dest=0, depth=0, pulses=5, trig_pulses=5)
        s.yes()
        check("preclear ALL+TRIGS has sample trigs", popcount_mask(mask_of(port)) >= 1)
        s.prime(lane=1, dest=LOCK_VOL, depth=64, pulses=5, trig_pulses=5)
        s.yes()
        port.chord("func", "bank", settle=600)
        port.press("down", settle=200)
        port.press("down", settle=200)
        port.press("yes", settle=900)
        check("CLEAR ALL+TRIGS dismisses list", port.long(M_OBJ) == 0)
        check("CLEAR ALL+TRIGS restores SEQ", port.long(s.ef) != 0)
        check("CLEAR ALL+TRIGS wipes VOL locks", live(locks_of(port, LOCK_VOL)) == 0)
        check("CLEAR ALL+TRIGS clears sample trigs", mask_of(port) == bytes(8))

        # --- ARE YOU SURE? (CUE gated while baked) ---
        s.prime(lane=0, dest=0, depth=0, pulses=5, trig_pulses=5)
        s.yes()
        baked = mask_of(port)
        check("dialog setup: baked trigs", popcount_mask(baked) >= 1, baked.hex())
        check("dialog setup: locked after bake", port.long(s.unlocked) == 0)
        port.press("cue", settle=700)
        check("CUE while baked opens ARE YOU SURE? (ef_ask)",
              port.long(s.ask) != 0, f"ask={port.long(s.ask)}")
        check("CUE while baked soft-hides SEQ (dialog not under SEQ)",
              port.long(s.ef) == 0, f"ef_win={port.long(s.ef):#x}")
        check("CUE while baked: stock DIALOG_OPEN owns keys",
              port.long(DIALOG_OPEN) != 0, f"dlg={port.long(DIALOG_OPEN):#x}")
        geo = popup_geometry(port.rt.uc)
        check("CUE while baked: popup geometry on screen (above SEQ)",
              geo is not None and port.long(UI_WINDOW) == POPUP,
              f"geo={geo} ui_win={port.long(UI_WINDOW):#x}")
        check("CUE while baked does not change trigs yet", mask_of(port) == baked)
        check("CUE while baked leaves from_cue clear", port.long(s.from_cue) == 0)
        # Knob poll must not recreate SEQ on top of the dialog (the HW bug).
        port.proc.command(f"knob {0x30:#x} 1", "ok")
        port.run(200)
        port.proc.command(f"knob {0x31:#x} 1", "ok")
        port.run(200)
        check("knob while dialog keeps SEQ soft-hidden",
              port.long(s.ask) != 0 and port.long(s.ef) == 0,
              f"ask={port.long(s.ask)} win={port.long(s.ef):#x}")
        check("knob while dialog keeps DIALOG_OPEN + popup",
              port.long(DIALOG_OPEN) != 0
              and popup_geometry(port.rt.uc) is not None
              and port.long(s.ef) == 0,
              f"dlg={port.long(DIALOG_OPEN):#x} geo={popup_geometry(port.rt.uc)} "
              f"win={port.long(s.ef):#x}")
        # Dialog YES unlocks only.
        port.press("yes", settle=700)
        check("dialog YES clears ef_ask", port.long(s.ask) == 0)
        check("dialog YES clears DIALOG_OPEN", port.long(DIALOG_OPEN) == 0)
        check("dialog YES sets ef_unlocked", port.long(s.unlocked) != 0)
        check("dialog YES restores SEQ", port.long(s.ef) != 0,
              f"ef_win={port.long(s.ef):#x}")
        check("dialog YES leaves sample trigs untouched", mask_of(port) == baked)
        # Second CUE now randomizes free mask.
        port.press("cue", settle=700)
        check("CUE after unlock sets from_cue", port.long(s.from_cue) != 0)
        check("CUE after unlock sets free", port.long(s.free) != 0)
        free_bits = popcount_mask(port.peek(s.ef_mask, 8))
        check("CUE free mask has PULS hits",
              free_bits == 5, f"bits={free_bits} mask={port.peek(s.ef_mask, 8).hex()}")
        s.yes()
        check("YES after CUE writes free mask popcount",
              popcount_mask(mask_of(port)) == 5, mask_of(port).hex())
        check("YES after CUE re-locks", port.long(s.unlocked) == 0)

        # Dialog NO cancels; still locked.
        baked = mask_of(port)
        port.press("cue", settle=700)
        check("CUE re-opens dialog when re-locked", port.long(s.ask) != 0)
        port.press("no", settle=700)
        check("dialog NO clears ef_ask", port.long(s.ask) == 0)
        check("dialog NO leaves unlocked clear", port.long(s.unlocked) == 0)
        check("dialog NO leaves trigs untouched", mask_of(port) == baked)
        port.press("cue", settle=700)
        check("CUE after NO still gated (ask again)", port.long(s.ask) != 0)
        port.press("no", settle=500)

        # --- PLCK CUE skips dialog even when baked ---
        # Dismiss any leftover ask first.
        if port.long(s.ask):
            port.press("no", settle=400)
        if port.long(s.ef) == 0:
            s.open_seq()
        s.prime(lane=1, dest=LOCK_VOL, depth=64, pulses=4, trig_pulses=5)
        # Ensure baked trigs still present and locked.
        poke32(port, s.unlocked, 0)
        poke32(port, s.ask, 0)
        port.press("cue", settle=700)
        check("PLCK CUE skips ARE YOU SURE?", port.long(s.ask) == 0,
              f"ask={port.long(s.ask)}")
        check("PLCK CUE sets from_cue", port.long(s.from_cue) != 0)
        pfree_bits = popcount_mask(port.peek(s.ef_pmask, 8))
        check("PLCK CUE pmask has PULS hits",
              pfree_bits == 4, f"bits={pfree_bits}")
        trig_before = mask_of(port)
        s.yes()
        check("PLCK CUE YES writes VOL locks", live(locks_of(port, LOCK_VOL)) >= 1)
        check("PLCK CUE YES leaves sample trigs", mask_of(port) == trig_before)
        check("PLCK CUE VOL on trig or TL",
              locks_have_trig_or_tl(port, locks_of(port, LOCK_VOL)))

        # --- Track switch: SEQ on T2 writes track 1, not track 0 ---
        # Wipe T0 trigs so the T2 write is obvious, then open T2.
        port.chord("func", "bank", settle=600)
        port.press("down", settle=200)
        port.press("down", settle=200)
        port.press("yes", settle=900)  # CLEAR ALL+TRIGS on focus (T1)
        s.close_seq()
        s.open_seq("t2")
        s.prime(lane=0, dest=0, depth=0, pulses=6, trig_pulses=6, trk=1)
        # Working vars already primed for lane/dest; focus must be track 1.
        # Re-prime working after open may have loaded T2 slot; force fill knobs.
        poke32(port, s.ef + 8, 6)
        poke32(port, s.ef + 0xC, 0)
        poke32(port, s.ef + 0x18, 0)
        poke32(port, s.ef + 0x2c, 0)
        poke32(port, s.from_cue, 0)
        poke32(port, s.free, 0)
        s.yes()
        check("T2 YES writes sample trigs on track 1",
              popcount_mask(mask_of(port, 1)) == 6, mask_of(port, 1).hex())
        check("T2 YES leaves track 0 empty",
              mask_of(port, 0) == bytes(8), mask_of(port, 0).hex())

        # Close SEQ; FUNC+BANK must not open our CLEAR list
        s.close_seq()
        port.chord("func", "bank", settle=700)
        labs = s.clear_labels()
        check("FUNC+BANK outside SEQ is not CLEAR list",
              "CLEAR DEST" not in labs, str(labs))

        # --- Stock TRACK / CUE chords while SEQ is open ---
        if port.long(s.ef) == 0:
            s.open_seq("t1")
        # TRK_STOCK sets HELD on press (needed for TRACK+PLAY/STOP/BANK).
        port.key("t1", True)
        port.run(120)
        held = port.long(HELD)
        check("TRACK press while SEQ sets stock HELD bit",
              held & 1, f"HELD={held:#x}")
        port.key("t1", False)
        port.run(120)

        # FUNC+TRACK mute (bit 8+t of 0x80000008).
        before = port.long(MUTE_CUE)
        port.chord("func", "t2", settle=500)
        after = port.long(MUTE_CUE)
        check("FUNC+TRACK while SEQ mutes that track",
              (after ^ before) & (1 << (8 + 1)),
              f"before={before:#x} after={after:#x}")

        # CUE+TRACK cues without SEQ random.
        poke32(port, s.from_cue, 0)
        poke32(port, s.cue_chord, 0)
        before = port.long(MUTE_CUE)
        port.chord("cue", "t1", settle=500)
        after = port.long(MUTE_CUE)
        check("CUE+TRACK while SEQ sets cue bit",
              (after ^ before) & (1 << 16),
              f"before={before:#x} after={after:#x}")
        check("CUE+TRACK leaves from_cue clear (no random)",
              port.long(s.from_cue) == 0)

        # Bare CUE release still randomizes when unlocked.
        poke32(port, s.unlocked, 1)
        poke32(port, s.ask, 0)
        poke32(port, s.from_cue, 0)
        poke32(port, s.free, 0)
        s.prime(lane=0, dest=0, depth=0, pulses=5, trig_pulses=5)
        poke32(port, s.unlocked, 1)
        port.press("cue", settle=700)
        check("bare CUE release sets from_cue", port.long(s.from_cue) != 0)
        check("bare CUE release sets free", port.long(s.free) != 0)

        # Double-tap TRACK → QUICK ASSIGN (stock steals UI_WINDOW).
        seq_win = port.long(s.ef)
        port.key("t2", True)
        port.run(50)
        port.key("t2", False)
        port.run(160)
        port.key("t2", True)
        port.run(50)
        port.key("t2", False)
        port.run(600)
        ui = port.long(UI_WINDOW)
        pool = port.long(POOL)
        check("double-tap TRACK while SEQ opens QUICK ASSIGN",
              ui != seq_win or pool != 0 or port.long(M_OBJ) != 0,
              f"ui={ui:#x} seq={seq_win:#x} pool={pool:#x} m_obj={port.long(M_OBJ):#x}")
        # Leave chooser; SEQ should still retarget to T2.
        port.press("no", settle=400)
        if port.long(s.ef) == 0:
            s.open_seq("t1")
        port.press("t2", settle=400)
        check("TRACK tap while SEQ still retargets UI_TRACK",
              u8(port, UI_TRACK) == 1, f"UI_TRACK={u8(port, UI_TRACK)}")

    print(f"SEQ scenarios: {FAILS} failed checks")
    return FAILS


def main() -> int:
    # Static gate still accepts remix arg; ignore it.
    return 0 if run_scenarios() == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
