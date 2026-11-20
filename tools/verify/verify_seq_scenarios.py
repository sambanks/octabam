#!/usr/bin/env python3
"""SEQ port scenarios from docs/site/usage/seq.md (MenuPort, MKII).

Primes track bank/plock state, presses YES / FUNC+BANK / CUE, checks pattern
bytes. Requires out/mainos_bus.bin + ot_emu (REMIX with SEQ, e.g. cx).
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools/verify"), str(ROOT / "tools/panel")]

from stems_panel import MenuPort  # noqa: E402
from seq_port_fixture import stage_project  # noqa: E402
from panel_server import popup_geometry  # noqa: E402
from verify_seq_tonal import on_scale  # noqa: E402

IMAGE = ROOT / "out/mainos_bus.bin"
CARD = ROOT / "out/_seq_scenarios_card.img"
MAP = ROOT / "out/platform/runtime/runtime.map"

DBPTR_ADDR = 0x46c82456
UI_PTN = 0x100b14d0
UI_TRACK = 0x100b14cc
UI_PART = 0x100b14cf
MIDI_BANK_TRACKS = 0x8000666e
MIDI_PART_TRACKS = MIDI_BANK_TRACKS + 8
PTN_STR = 0x8ed8
PART_STR = 0x18B2
BANK_STR = 0x9B340
PARTS_BASE = 0x400E21E0 + 0x8ED80
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


def local_sym(name: str) -> int:
    output = subprocess.check_output(
        ["m68k-elf-nm", "-a", str(ROOT / "out/platform/runtime/runtime.elf")],
        text=True)
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] == name:
            return int(fields[0], 16)
    raise SystemExit(f"local symbol missing in runtime.elf: {name}")


def u8(p, a: int) -> int:
    return p.peek(a, 1)[0]


def poke32(p, a: int, v: int) -> None:
    p.poke(a, int(v).to_bytes(4, "big"))


def poke8(p, a: int, v: int) -> None:
    p.poke(a, bytes([v & 0xFF]))


def ensure_card() -> None:
    # CI has no template_project: the image makes its own project (seq_port_fixture, main a6a4b3e).
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
        self.pulses = sym("ef_pulses")
        self.rot = sym("ef_rot")
        self.ppulses = sym("ef_ppulses")
        self.prot = sym("ef_prot")
        self.lane = sym("ef_lane")
        self.pfree = local_sym("ef_pfree")
        self.dest = sym("ef_dest")
        self.depth = sym("ef_depth")
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
            (self.lane, lane),
            (self.dest, dest),
            (self.depth, depth),
            (self.ppulses, pulses),
            (self.prot, rot),
            (self.pulses, trig_pulses),
            (self.rot, trig_rot),
            (self.pfree, 0),
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
        print("SEQ scenarios: skip (no out/mainos_bus.bin)")
        return 0
    if not MAP.exists():
        print("SEQ scenarios: skip (no runtime.map)")
        return 0
    emu = ROOT / "out/emu/ot_emu"
    if not emu.exists():
        print("SEQ scenarios: skip (no out/emu/ot_emu)")
        return 0

    ensure_card()
    print("SEQ port scenarios (usage/seq.md):")

    with MenuPort(IMAGE, CARD, "OCTABAM", "A", mkii=True) as port:
        port.settle()
        for _ in range(3):
            port.press("no", settle=80)
        s = SeqPort(port)

        # --- open ---
        s.open_seq()
        s.close_seq()
        port.press("proj", settle=400)
        project_geo = popup_geometry(port.rt.uc)
        project_open = project_geo is not None and project_geo[1] == 0 and project_geo[3] == 0x40
        check("PROJECT opens directly after closing SEQ (key layer released)",
              project_open, f"geometry={project_geo}")
        if project_open:
            port.press("right", settle=150)
            port.press("down", settle=150)
            check("Project stays navigable after SEQ closes",
                  popup_geometry(port.rt.uc) == project_geo
                  and port.long(local_sym("ef_win")) == 0,
                  f"geometry={popup_geometry(port.rt.uc)} ef_win={port.long(local_sym('ef_win')):#x}")
            port.press("no", settle=400)
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
        decoded = [int((value - 64) / 5) for value in vals]
        check("SEQ's built-in scale still shapes PTCH when SCALE QUANTIZER is off",
              bool(decoded) and all(on_scale(note, 0, 0x0AB5) for note in decoded),
              f"raw={vals} semitones={decoded}")
        check("PLCK+PTCH leaves sample trigs alone", mask_of(port) == trig_before)

        # JUMP is shared by audio and MIDI Harmony: keep the phrase, DEPTH,
        # scale, root, Part pitch, and trig placement fixed across both fills.
        audio_part_ptch = PARTS_BASE + BANK_STR + 0x8EDAA
        part_ptch_before = u8(port, audio_part_ptch)
        poke8(port, audio_part_ptch, 65)  # +0.2 st: sample PTCH is raw 64+5*n
        poke8(port, NV_SCALE, 1)
        poke8(port, NV_ROOT, 0)
        poke32(port, local_sym("ef_tone_phrase"), 1)  # UP
        audio_jump_notes = {}
        audio_jump_masks = {}
        for jump_value in (0, 127):
            poke32(port, local_sym("ef_tone_jump"), jump_value)
            s.prime(lane=0, dest=LOCK_PTCH, depth=127,
                    pulses=5, trig_pulses=5)
            s.yes()
            values = locks_of(port, LOCK_PTCH)
            audio_jump_masks[jump_value] = mask_of(port)
            check(f"audio JUMP {jump_value} sample PTCH locks are whole semitones",
                  all(v == 0xFF or (v - 64) % 5 == 0 for v in values),
                  f"raw-locks={values}")
            audio_jump_notes[jump_value] = [int((v - 64) / 5) for v in values
                                            if v != 0xFF]
        audio_close = audio_jump_notes[0]
        audio_wide = audio_jump_notes[127]
        check("sample audio UP starts on the rounded Part pitch",
              len(audio_close) == 5 and audio_close[0] == 0,
              f"notes={audio_close}")
        check("sample audio max JUMP spreads UP to the DEPTH limit",
              len(audio_wide) == 5
              and audio_wide[0] == 0 and min(audio_wide) == -12
              and len(set(audio_wide)) == 5
              and all(-12 <= note <= 12 and on_scale(note, 0, 0x0AB5)
                      for note in audio_wide)
              and audio_jump_masks[0] == audio_jump_masks[127],
              f"close={audio_close} wide={audio_wide}")
        audio_rand_rolls = {}
        sample_scale_offsets = [-12, -10, -8, -7, -5, -3, -1,
                                0, 2, 4, 5, 7, 9, 11, 12]
        for jump_value in (0, 64, 127):
            poke32(port, local_sym("ef_tone_phrase"), 0)  # RAND
            poke32(port, local_sym("ef_tone_jump"), jump_value)
            poke32(port, local_sym("ef_rng_state"), 1)
            s.prime(lane=0, dest=LOCK_PTCH, depth=127, pulses=16,
                    trig_pulses=16)
            s.yes()
            raw = locks_of(port, LOCK_PTCH)
            notes = [int((value - 64) / 5) for value in raw if value != 0xFF]
            audio_rand_rolls[jump_value] = notes
            ranks = [sample_scale_offsets.index(note) for note in notes]
            stride = 1 + jump_value * 3 // 127
            check(f"sample audio RAND JUMP {jump_value} sets neighboring pitch spacing",
                  len(ranks) == 16
                  and all(abs(b - a) == stride
                          for a, b in zip(ranks, ranks[1:]))
                  and all(-12 <= note <= 12 and on_scale(note, 0, 0x0AB5)
                          for note in notes),
                  f"notes={notes} ranks={ranks} stride={stride}")
        check("sample audio RAND retains random direction and JUMP changes spacing",
              len({tuple(roll) for roll in audio_rand_rolls.values()}) == 3
              and all({b - a for a, b in zip(
                  [sample_scale_offsets.index(n) for n in roll],
                  [sample_scale_offsets.index(n) for n in roll][1:])}
                      == {-(1 + jump * 3 // 127), 1 + jump * 3 // 127}
                      for jump, roll in audio_rand_rolls.items()),
              f"rolls={audio_rand_rolls}")
        poke32(port, local_sym("ef_tone_phrase"), 1)  # restore UP for following tests
        poke32(port, local_sym("ef_tone_jump"), 127)
        s.prime(lane=0, dest=LOCK_PTCH, depth=127, pulses=16,
                trig_pulses=16)
        s.yes()
        audio_wrap = [int((v - 64) / 5) for v in locks_of(port, LOCK_PTCH)
                      if v != 0xFF]
        check("sample audio JUMP wraps within DPTH when trigs exceed the range",
              len(audio_wrap) == 16 and audio_wrap[0] == 0
              and audio_wrap[1] == -12 and audio_wrap[15] == 0
              and all(-12 <= note <= 12 and on_scale(note, 0, 0x0AB5)
                      for note in audio_wrap),
              f"notes={audio_wrap}")
        audio_plock_notes = {}
        audio_trigs_before_plock = mask_of(port)
        for jump_value in (0, 127):
            poke32(port, local_sym("ef_tone_jump"), jump_value)
            s.prime(lane=1, dest=LOCK_PTCH, depth=127,
                    pulses=5, trig_pulses=5)
            s.yes()
            values = locks_of(port, LOCK_PTCH)
            audio_plock_notes[jump_value] = [int((v - 64) / 5) for v in values
                                             if v != 0xFF]
        check("audio PLCK JUMP widens generated pitches without changing trigs",
              len(audio_plock_notes[0]) == len(audio_plock_notes[127]) == 5
              and max(audio_plock_notes[127]) - min(audio_plock_notes[127])
              > max(audio_plock_notes[0]) - min(audio_plock_notes[0])
              and mask_of(port) == audio_trigs_before_plock,
              f"close={audio_plock_notes[0]} wide={audio_plock_notes[127]} "
              f"trigs-unchanged={mask_of(port) == audio_trigs_before_plock}")
        poke32(port, local_sym("ef_tone_jump"), 0)
        poke8(port, audio_part_ptch, part_ptch_before)

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
              port.long(s.depth) == 0 and port.long(s.ppulses) == 0
              and port.long(s.prot) == 0,
              f"dep={port.long(s.depth)} pp={port.long(s.ppulses)} prot={port.long(s.prot)}")

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
        poke32(port, local_sym("ef_rng_state"), 1)
        port.press("cue", settle=700)
        check("CUE after unlock sets from_cue", port.long(s.from_cue) != 0)
        check("CUE after unlock sets free", port.long(s.free) != 0)
        free_bits = popcount_mask(port.peek(s.ef_mask, 8))
        check("CUE free mask has PULS hits",
              free_bits == 5, f"bits={free_bits} mask={port.peek(s.ef_mask, 8).hex()}")
        first_cue_mask = port.peek(s.ef_mask, 8)
        # Regenerating the same PULSE count should advance the random sequence,
        # rather than returning the same placement (DEPTH only changes locks).
        port.press("cue", settle=700)
        second_cue_mask = port.peek(s.ef_mask, 8)
        check("repeated CUE regenerates a different TRIG placement",
              second_cue_mask != first_cue_mask,
              f"first={first_cue_mask.hex()} second={second_cue_mask.hex()}")
        check("repeated CUE keeps the requested PULSE count",
              popcount_mask(second_cue_mask) == 5,
              f"bits={popcount_mask(second_cue_mask)} mask={second_cue_mask.hex()}")
        s.yes()
        check("YES after CUE writes free mask popcount",
              popcount_mask(mask_of(port)) == 5, mask_of(port).hex())
        check("YES after CUE re-locks", port.long(s.unlocked) == 0)

        # RAND (PHRS=0) should randomize generated pitch locks as well as
        # CUE's trigger placement. Keep every generation parameter fixed
        # across the reroll; only the RNG state advances.
        tone_phrase = local_sym("ef_tone_phrase")
        poke32(port, tone_phrase, 0)  # RAND
        s.prime(lane=0, dest=0, depth=127, pulses=5, trig_pulses=5)
        poke32(port, s.unlocked, 1)
        poke32(port, s.ask, 0)
        poke32(port, local_sym("ef_rng_state"), 1)
        port.press("cue", settle=700)
        s.yes()
        rand_trigs_1 = mask_of(port)
        rand_pitch_1 = locks_of(port, LOCK_PTCH)
        rand_values_1 = [v for v in rand_pitch_1 if v != 0xFF]
        check("PHRS RAND creates varied PTCH locks",
              len(rand_values_1) == 5 and len(set(rand_values_1)) > 1,
              f"values={rand_values_1}")

        poke32(port, s.unlocked, 1)
        poke32(port, s.ask, 0)
        port.press("cue", settle=700)
        s.yes()
        rand_trigs_2 = mask_of(port)
        rand_pitch_2 = locks_of(port, LOCK_PTCH)
        rand_values_2 = [v for v in rand_pitch_2 if v != 0xFF]
        check("same-settings CUE reroll changes TRIG placement",
              rand_trigs_2 != rand_trigs_1
              and popcount_mask(rand_trigs_2) == 5,
              f"first={rand_trigs_1.hex()} second={rand_trigs_2.hex()}")
        check("same-settings RAND reroll changes generated pitches",
              rand_pitch_2 != rand_pitch_1
              and len(rand_values_2) == 5
              and len(set(rand_values_2)) > 1
              and port.long(tone_phrase) == 0
              and port.long(s.depth) == 127,
              f"first={rand_values_1} second={rand_values_2} "
              f"phrase={port.long(tone_phrase)} "
              f"depth={port.long(s.depth)}")

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
        poke32(port, s.pulses, 6)
        poke32(port, s.rot, 0)
        poke32(port, s.lane, 0)
        poke32(port, s.depth, 0)
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

        # --- MIDI-mode note trigs use the MIDI mask and keep audio data ---
        s.close_seq()
        port.press("midi", settle=300)
        port.press("t1", settle=300)
        midi_bank = sym("ef_midi_bank")
        midi_dep = sym("ef_midi_dep_mem")
        midi_plk = sym("ef_midi_plk_mem")
        midi_lane = sym("ef_midi_lane_mem")
        poke32(port, midi_bank, 3)
        poke32(port, midi_bank + 4, 0)
        poke32(port, midi_bank + 8, 20)  # CTRL1 CC1 flat
        poke32(port, midi_bank + 0xC, 4)
        poke8(port, midi_dep + 20, 4)
        s.open_seq("t1")
        check("MIDI mode opens SEQ on the MIDI track",
              port.long(0x80000012) != 0 and port.long(s.ef) != 0)
        poke32(port, local_sym("ef_tone_midi"), 1)
        poke32(port, sym("ef_dest"), 20)
        poke32(port, sym("ef_depth"), 4)
        poke32(port, s.lane, 0)
        poke32(port, s.from_cue, 0)
        poke32(port, s.free, 0)
        pattern = port.long(DBPTR_ADDR) + u8(port, UI_PTN) * PTN_STR
        midi_record = pattern + 0x48D0
        midi_mask = midi_record + 7
        audio_before = mask_of(port, 0)
        midi_lock_base = pattern + 0x4900
        # MIDI playback keeps a per-track Part context independent of the UI.
        # Seed T1 on bank 1 / Part 2 while the UI shows Part 3: a UI-based
        # read silently uses the wrong zero-filled Part and makes NOTE C-1,
        # VEL 0. STORE's MIDI context must select the values used for locks.
        poke8(port, MIDI_BANK_TRACKS, 1)
        poke8(port, MIDI_PART_TRACKS, 2)
        poke8(port, UI_PART, 3)
        midi_part = PARTS_BASE + BANK_STR + 2 * PART_STR + 0x3e2
        port.poke(midi_part + 20, bytes((64,)))  # CC1 Part value
        midi_lock_span = 7 * 0x8B0 + 0x800
        midi_locks_before = bytearray(port.peek(midi_lock_base, midi_lock_span))
        for step in range(64):
            midi_locks_before[step * 32 + 20] = 0xFF
        port.poke(midi_lock_base, bytes(midi_locks_before))
        port.poke(midi_record, bytes(8))
        port.poke(midi_record + 0x28, bytes((16,)))
        port.proc.command(f"watchmem {midi_lock_base:#x} 0x800", "ok")
        port.proc.command(f"watch {local_sym('ef_midi_lock_store'):#x}", "ok")
        s.yes()
        midi_lock_trace = port.proc.command("writes", "writes")
        midi_lock_calls = port.proc.command("hits", "hits")
        midi_bytes = port.peek(midi_mask - 7, 8)
        midi_bits = sum(bool(midi_bytes[7 - (step >> 3)] & (1 << (step & 7))) << step
                        for step in range(16))
        expected = (1 << 0) | (1 << 6) | (1 << 11)
        check("MIDI PULS writes note trigs at steps 1, 7, 12",
              midi_bits == expected, f"mask={midi_bits:#018x}")
        check("MIDI fill leaves audio sample trigs alone",
              mask_of(port, 0) == audio_before)
        cc_locks = port.peek(midi_lock_base, 0x800)
        cc_ok = True
        for step in range(64):
            value = cc_locks[step * 32 + 20]
            if step < 16 and (expected >> step) & 1:
                cc_ok &= 60 <= value <= 68
            else:
                cc_ok &= value == 0xFF
        check("MIDI CC1 locks follow note hits around the Part value", cc_ok,
              f"hits={[cc_locks[step * 32 + 20] for step in range(16) if (expected >> step) & 1]} "
              f"depth={port.long(sym('ef_depth'))} dest={port.long(sym('ef_dest'))} "
              f"dep={u8(port, midi_dep + 20)} part={u8(port, midi_part + 20)} "
              f"mode={port.long(0x80000012)} focus={port.long(sym('ef_focus'))} "
              f"lockbase={midi_lock_base:#x} calls={midi_lock_calls[:700]} "
              f"writes={midi_lock_trace[:700]}")
        locks_after_all = port.peek(midi_lock_base, midi_lock_span)
        cc_other_ok = all(
            locks_after_all[i] == midi_locks_before[i]
            for i in range(midi_lock_span)
            if i not in {step * 32 + 20 for step in range(64)})
        check("MIDI CC1 fill preserves other lock flats and MIDI tracks", cc_other_ok)

        # MIDI PLOCK has its own rhythm and must not alter note trigs.
        midi_plk_slot = midi_plk + 20 * 12
        poke8(port, midi_plk_slot, 3)
        poke8(port, midi_plk_slot + 1, 0)
        poke8(port, midi_plk_slot + 2, 0)
        poke8(port, midi_lane, 1)
        poke32(port, sym("ef_lane"), 1)
        poke32(port, sym("ef_dest"), 20)
        poke32(port, sym("ef_depth"), 4)
        poke32(port, local_sym("ef_ppulses"), 3)
        poke32(port, local_sym("ef_prot"), 0)
        poke32(port, local_sym("ef_pfree"), 0)
        note_mask_before_plk = port.peek(midi_mask - 7, 8)
        s.yes()
        check("MIDI PLOCK fill leaves note trigs unchanged",
              port.peek(midi_mask - 7, 8) == note_mask_before_plk)
        plk_values = port.peek(midi_lock_base, 0x800)
        plk_ok = True
        for step in range(64):
            value = plk_values[step * 32 + 20]
            if step in (0, 6, 11):
                plk_ok &= 60 <= value <= 68
            else:
                plk_ok &= value == 0xFF
        check("MIDI PLOCK writes its own 3-pulse CC rhythm", plk_ok,
              f"hits={[plk_values[step * 32 + 20] for step in (0, 6, 11)]}")

        note_dest_ok = True
        poke8(port, midi_lane, 0)
        poke32(port, sym("ef_lane"), 0)
        poke32(port, local_sym("ef_tone_mode"), 0)
        poke32(port, local_sym("ef_tone_midi"), 1)
        poke32(port, local_sym("ef_tone_harm"), 4)  # VOIC 4
        poke32(port, local_sym("ef_tone_style"), 4)  # FM SYNTH MAJ
        for flat, base in ((0, 60), (1, 100), (18, 64), (19, 67), (29, 72)):
            port.poke(midi_part + flat, bytes((base,)))
            poke32(port, sym("ef_dest"), flat)
            poke32(port, sym("ef_depth"), 2)
            poke8(port, midi_dep + flat, 2)
            # The TRIG lane's first baked pattern raises the normal MIDI
            # confirmation. This fixture is testing flat coverage, so seed
            # the existing unlock that a confirmed user edit would set.
            poke32(port, s.unlocked, 1)
            poke32(port, s.ask, 0)
            s.yes()
            locks = port.peek(midi_lock_base, 0x800)
            for step in range(64):
                value = locks[step * 32 + flat]
                if flat == 0:
                    if step < 16 and (expected >> step) & 1:
                        note_dest_ok &= on_scale(value, 0, 0x0AB5)
                    else:
                        note_dest_ok &= value == 0xFF
                elif step < 16 and (expected >> step) & 1:
                    note_dest_ok &= base - 2 <= value <= base + 2
                else:
                    note_dest_ok &= value == 0xFF
        chord_values = [u8(port, midi_lock_base + step * 32 + flat)
                        for flat in (3, 4, 5) for step in (0, 6, 11)]
        check("VOIC 4 NOTE fills add NOTE2/NOTE3/NOTE4 locks",
              len(chord_values) == 9 and all(value != 0xFF for value in chord_values), str(chord_values))
        note_vals = {
            flat: [u8(port, midi_lock_base + step * 32 + flat) for step in (0, 6, 11)]
            for flat in (0, 3, 4, 5)
        }
        check("NOTE and MIDI parameter locks remain available on TRIG fills",
              note_dest_ok, f"hit-values={note_vals}")
        # JUMP changes melodic spacing while DEPTH, PHRS, Part NOTE, and
        # trigger placement stay fixed. Both fills must remain in scale/range.
        poke32(port, sym("ef_dest"), 0)
        poke32(port, sym("ef_depth"), 127)
        poke8(port, midi_dep, 127)
        poke32(port, local_sym("ef_tone_scale"), 0)
        poke32(port, local_sym("ef_tone_root"), 0)
        poke32(port, local_sym("ef_tone_jump"), 0)
        poke32(port, midi_bank, 16)
        poke32(port, midi_bank + 4, 0)
        poke32(port, s.pulses, 16)
        poke32(port, local_sym("ef_tone_phrase"), 1)  # UP
        poke32(port, s.unlocked, 1)
        poke32(port, s.ask, 0)
        s.yes()
        up_notes = [u8(port, midi_lock_base + step * 32)
                    for step in range(16)]
        up_notes = [note for note in up_notes if note != 0xFF]
        check("MIDI UP starts on Part NOTE, varies scale intervals, and wraps",
              up_notes == [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83, 84, 86]
              and len({b-a for a, b in zip(up_notes, up_notes[1:])}) > 1,
              f"notes={up_notes}")
        poke32(port, local_sym("ef_tone_phrase"), 2)  # DOWN
        poke32(port, s.unlocked, 1)
        poke32(port, s.ask, 0)
        s.yes()
        down_notes = [u8(port, midi_lock_base + step * 32)
                      for step in range(16)]
        down_notes = [note for note in down_notes if note != 0xFF]
        check("MIDI DOWN starts on Part NOTE, varies scale intervals, and wraps",
              down_notes == [60, 59, 57, 55, 53, 52, 50, 48, 47, 45, 43, 41, 40, 38, 36, 35]
              and len({a-b for a, b in zip(down_notes, down_notes[1:])}) > 1,
              f"notes={down_notes}")
        # ALT reflects without repeating the top candidate; TRI repeats it
        # once. Their distinct cycle lengths also produce different JUMP strides.
        poke32(port, sym("ef_depth"), 32)
        poke8(port, midi_dep, 32)
        phrase_roll_expected = {
            (3, 0): [48, 50, 52, 53, 55, 57, 59, 60,
                     62, 64, 65, 67, 69, 71, 72, 71],
            (4, 0): [48, 50, 52, 53, 55, 57, 59, 60,
                     62, 64, 65, 67, 69, 71, 72, 72],
            (3, 64): [48, 57, 65, 71, 62, 53, 52, 60,
                      69, 67, 59, 50, 55, 64, 72, 64],
            (4, 64): [48, 60, 72, 62, 50, 57, 69, 65,
                      53, 53, 65, 69, 57, 50, 62, 72],
        }
        phrase_roll_actual = {}
        for (phrase, jump), expected_notes in phrase_roll_expected.items():
            poke32(port, local_sym("ef_tone_phrase"), phrase)
            poke32(port, local_sym("ef_tone_jump"), jump)
            poke32(port, s.unlocked, 1)
            poke32(port, s.ask, 0)
            s.yes()
            actual_notes = [u8(port, midi_lock_base + step * 32)
                            for step in range(16)]
            phrase_roll_actual[(phrase, jump)] = actual_notes
            check(f"MIDI {'ALT' if phrase == 3 else 'TRI'} roll matches JUMP {jump}",
                  actual_notes == expected_notes,
                  f"notes={actual_notes}")
        check("MIDI ALT and TRI rolls differ at JUMP 0 and JUMP 64",
              phrase_roll_actual.get((3, 0)) != phrase_roll_actual.get((4, 0))
              and phrase_roll_actual.get((3, 64)) != phrase_roll_actual.get((4, 64)))
        midi_rand_rolls = {}
        c_major_range = [48, 50, 52, 53, 55, 57, 59, 60,
                         62, 64, 65, 67, 69, 71, 72]
        for jump_value in (0, 64, 127):
            poke32(port, local_sym("ef_tone_phrase"), 0)  # RAND
            poke32(port, local_sym("ef_tone_jump"), jump_value)
            poke32(port, local_sym("ef_rng_state"), 1)
            poke32(port, s.unlocked, 1)
            poke32(port, s.ask, 0)
            s.yes()
            values = [u8(port, midi_lock_base + step * 32)
                      for step in range(16)]
            notes = [value for value in values if value != 0xFF]
            midi_rand_rolls[jump_value] = notes
            ranks = [c_major_range.index(note) for note in notes]
            stride = 1 + jump_value * 3 // 127
            check(f"MIDI RAND JUMP {jump_value} sets neighboring pitch spacing",
                  len(ranks) == 16
                  and all(abs(b - a) == stride
                          for a, b in zip(ranks, ranks[1:]))
                  and all(48 <= note <= 72 and on_scale(note, 0, 0x0AB5)
                          for note in notes),
                  f"notes={notes} ranks={ranks} stride={stride}")
        check("MIDI RAND retains random direction and JUMP changes spacing",
              len({tuple(roll) for roll in midi_rand_rolls.values()}) == 3
              and all({b - a for a, b in zip(
                  [c_major_range.index(n) for n in roll],
                  [c_major_range.index(n) for n in roll][1:])}
                      == {-(1 + jump * 3 // 127), 1 + jump * 3 // 127}
                      for jump, roll in midi_rand_rolls.items()),
              f"rolls={midi_rand_rolls}")
        poke32(port, midi_bank, 3)
        poke32(port, s.pulses, 3)
        poke32(port, local_sym("ef_tone_phrase"), 1)  # UP
        close_jump_notes = None
        wide_jump_notes = None
        for jump_value in (0, 127):
            poke32(port, local_sym("ef_tone_jump"), jump_value)
            poke32(port, s.unlocked, 1)
            poke32(port, s.ask, 0)
            s.yes()
            values = [u8(port, midi_lock_base + step * 32) for step in (0, 6, 11)]
            if jump_value == 0:
                close_jump_notes = values
            else:
                wide_jump_notes = values
        check("JUMP 0 keeps successive MIDI notes close",
              close_jump_notes is not None
              and len(close_jump_notes) == 3
              and close_jump_notes[0] == 60
              and max(close_jump_notes) - min(close_jump_notes) < 16,
              f"notes={close_jump_notes}")
        check("JUMP 127 wraps MIDI UP through DEPTH while staying in scale",
              wide_jump_notes is not None and close_jump_notes is not None
              and wide_jump_notes[0] == 60
              and len(set(wide_jump_notes)) == 3
              and max(wide_jump_notes) - min(wide_jump_notes)
                  > max(close_jump_notes) - min(close_jump_notes)
              and all(12 <= note <= 108 and on_scale(note, 0, 0x0AB5)
                      for note in wide_jump_notes),
              f"close={close_jump_notes} wide={wide_jump_notes}")
        # More generated notes than candidates must cycle rather than clamp.
        poke32(port, midi_bank, 8)
        poke32(port, s.pulses, 16)
        poke32(port, sym("ef_depth"), 16)
        poke8(port, midi_dep, 16)
        poke32(port, local_sym("ef_tone_jump"), 127)
        poke32(port, local_sym("ef_tone_phrase"), 1)  # UP
        poke32(port, s.unlocked, 1)
        poke32(port, s.ask, 0)
        s.yes()
        wrap_notes = [u8(port, midi_lock_base + step * 32) for step in range(16)]
        wrap_notes = [note for note in wrap_notes if note != 0xFF]
        check("MIDI UP wraps repeatedly at the DEPTH maximum with many trigs",
              len(wrap_notes) == 16 and wrap_notes[0] == 60
              and wrap_notes[:7] == [60, 55, 62, 57, 64, 59, 65]
              and wrap_notes[7:14] == wrap_notes[:7]
              and wrap_notes[14:] == wrap_notes[:2],
              f"notes={wrap_notes}")
        poke32(port, local_sym("ef_tone_phrase"), 2)  # DOWN
        poke32(port, s.unlocked, 1)
        poke32(port, s.ask, 0)
        s.yes()
        down_wrap_notes = [u8(port, midi_lock_base + step * 32)
                           for step in range(16)]
        down_wrap_notes = [note for note in down_wrap_notes if note != 0xFF]
        check("MIDI DOWN wraps repeatedly at the DEPTH minimum with many trigs",
              len(down_wrap_notes) == 16
              and down_wrap_notes[:7] == [60, 65, 59, 64, 57, 62, 55]
              and down_wrap_notes[7:14] == down_wrap_notes[:7]
              and down_wrap_notes[14:] == down_wrap_notes[:2],
              f"notes={down_wrap_notes}")
        poke32(port, midi_bank, 3)
        poke32(port, s.pulses, 3)
        poke32(port, local_sym("ef_tone_phrase"), 1)  # UP
        poke32(port, sym("ef_depth"), 16)
        poke8(port, midi_dep, 16)
        poke32(port, s.unlocked, 1)
        poke32(port, s.ask, 0)
        s.yes()
        narrow_notes = [u8(port, midi_lock_base + step * 32) for step in (0, 6, 11)]
        check("maximum JUMP stays inside a narrow DEPTH span",
              narrow_notes[0] == 60
              and all(54 <= note <= 66 and on_scale(note, 0, 0x0AB5)
                  for note in narrow_notes),
              f"notes={narrow_notes} Part=60 DEPTH=16")
        poke32(port, sym("ef_depth"), 0)
        poke8(port, midi_dep, 0)
        poke32(port, s.unlocked, 1)
        poke32(port, s.ask, 0)
        s.yes()
        check("DEPTH 0 still clears MIDI NOTE locks with JUMP enabled",
              all(u8(port, midi_lock_base + step * 32) == 0xFF
                  for step in range(16)))
        port_mask = port.peek(midi_mask - 7, 8)
        poke32(port, sym("ef_depth"), 127)
        poke8(port, midi_dep, 127)
        poke8(port, midi_lane, 1)
        poke32(port, s.lane, 1)
        poke32(port, sym("ef_dest"), 0)
        poke32(port, sym("ef_depth"), 127)
        poke8(port, midi_dep, 127)
        poke8(port, midi_plk, 3)
        poke8(port, midi_plk + 1, 0)
        poke8(port, midi_plk + 2, 0)
        poke32(port, local_sym("ef_ppulses"), 3)
        poke32(port, local_sym("ef_prot"), 0)
        poke32(port, local_sym("ef_pfree"), 0)
        plck_notes = {}
        for jump_value in (0, 127):
            poke32(port, local_sym("ef_tone_jump"), jump_value)
            poke32(port, s.unlocked, 1)
            poke32(port, s.ask, 0)
            s.yes()
            plck_notes[jump_value] = [u8(port, midi_lock_base + step * 32)
                                      for step in (0, 6, 11)]
        check("JUMP also spaces MIDI NOTE locks on the independent PLCK lane",
              all(value != 0xFF for value in plck_notes[127])
              and max(plck_notes[127]) - min(plck_notes[127])
              > max(plck_notes[0]) - min(plck_notes[0])
              and all(on_scale(value, 0, 0x0AB5) for value in plck_notes[127])
              and port.peek(midi_mask - 7, 8) == port_mask,
              f"close={plck_notes[0]} wide={plck_notes[127]} "
              f"note-mask-unchanged={port.peek(midi_mask - 7, 8) == port_mask}")
        poke8(port, midi_lane, 0)
        poke32(port, s.lane, 0)
        poke32(port, local_sym("ef_tone_jump"), 0)
        # Refill existing four-note chords at each smaller voice count.
        # Unused intervals must be 0xff (empty), not raw 0 (-64).
        for voices in (2, 3, 1, 4):
            poke32(port, sym("ef_dest"), 0)
            poke32(port, sym("ef_depth"), 2)
            poke8(port, midi_dep, 2)
            poke32(port, local_sym("ef_tone_harm"), voices)
            poke32(port, s.unlocked, 1)
            poke32(port, s.ask, 0)
            s.yes()
            intervals = {
                flat: [u8(port, midi_lock_base + step * 32 + flat)
                       for step in (0, 6, 11)]
                for flat in (3, 4, 5)
            }
            check(f"VOIC {voices} leaves unused MIDI voices empty",
                  all(all(value == 0xff for value in values)
                      if flat - 2 >= voices else
                      all(value not in (0, 0xff) for value in values)
                      for flat, values in intervals.items()), str(intervals))
            check(f"VOIC {voices} mirrors all generated and cleared intervals",
                  all(u8(port, 0x1001614E + u8(port, UI_PTN) * PTN_STR
                         + 0x4900 + step * 32 + flat) ==
                      u8(port, midi_lock_base + step * 32 + flat)
                      for step in (0, 6, 11) for flat in (3, 4, 5)))

        mirror = 0x1001614E + u8(port, UI_PTN) * PTN_STR + 0x48D0
        check("MIDI note-trig mask reaches the battery mirror",
              port.peek(mirror, 8) == midi_bytes)
        check("MIDI CC and NOTE locks reach the battery mirror",
              port.peek(mirror + (0x4900 - 0x48D0), 0x800)
              == port.peek(midi_lock_base, 0x800))

        # Exercise the user's CUE -> YES gesture. The free-rhythm reader
        # uses a0; the MIDI writer must retain its destination address.
        for depth in (0, 4):
            s.close_seq()
            port.poke(midi_record, bytes(8))
            s.open_seq("t1")
            poke32(port, s.pulses, 5)
            poke32(port, s.rot, 0)
            poke32(port, s.depth, depth)
            poke32(port, s.lane, 0)
            poke32(port, s.unlocked, 1)
            poke32(port, s.ask, 0)
            port.proc.command("knob 0x31 -63", "ok")
            port.run(250)
            port.proc.command("knob 0x34 -127", "ok")
            port.run(250)
            if depth:
                port.proc.command(f"knob 0x34 {depth}", "ok")
                port.run(250)
            port.press("cue", settle=400)
            free_before = port.peek(local_sym("ef_mask"), 8)
            count = port.long(sym("ef_steps"))
            expected_free = sum(
                ((free_before[step >> 3] >> (step & 7)) & 1) << step
                for step in range(count))
            s.yes()
            actual_free = int.from_bytes(port.peek(midi_record, 8), "big")
            check(f"MIDI panel CUE then YES creates trigs at DPTH {depth}",
                  actual_free == expected_free and actual_free.bit_count() > 0,
                  f"expected={expected_free:#x} actual={actual_free:#x} count={count} "
                  f"mask={free_before.hex()} pulses={port.long(s.pulses)} "
                  f"unlocked={port.long(s.unlocked)} ask={port.long(s.ask)} "
                  f"from_cue={port.long(s.from_cue)} free={port.long(s.free)}")
            check(f"MIDI CUE fill preserves its preview mask at DPTH {depth}",
                  port.peek(local_sym("ef_mask"), 8) == free_before)
            check(f"MIDI CUE trigs reach battery mirror at DPTH {depth}",
                  port.peek(mirror, 8) == port.peek(midi_record, 8))

    print(f"SEQ scenarios: {FAILS} failed checks")
    return FAILS


def main() -> int:
    # Static gate still accepts remix arg; ignore it.
    return 0 if run_scenarios() == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
