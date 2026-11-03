#!/usr/bin/env python3
"""CX OSC gates under Unicorn: voice knobs + the one-track-per-Part guard.

1. Voice: FOLD / bipolar SYMM half-wave skew / RATO / DEC move the output;
   center vs high/low skew differ; FOLD=SYMM=DEC=127 stays bounded.
   Calls `sy_render` with a planted Part.
2. Guard: `ml_guard_p` refuses a second CX OSC track in a Part ("CX OSC: 1 MAX")
   and allows the track's own machine again / a first choice / a stock row.
3. AMP 2.20: with the live lane fixed at ATK 0, a slow ATK in the DSP voice
   record (scene/LFO stand-in) changes the attack vs a fast DSP ATK — proving
   `po_amp_snap` / `po_amp_at`, not CURVALS alone.

ColdFire, not dsp_host. Instruction counts are diagnostics, not hardware cycles.

    python3 tools/verify/verify_cxosc.py          # after make bus REMIX=cxosc
    make check REMIX=cxosc                        # Gate on the module
"""
from __future__ import annotations

import math
import pathlib
import struct
import subprocess
import sys

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED
from unicorn.m68k_const import (
    UC_CPU_M68K_CFV4E,
    UC_M68K_REG_A0,
    UC_M68K_REG_A7,
    UC_M68K_REG_D0,
    UC_M68K_REG_D1,
    UC_M68K_REG_D2,
    UC_M68K_REG_PC,
    UC_M68K_REG_SR,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "out/platform/runtime"
OS_BIN = ROOT / "out/raw/section_3_MAIN_OS.bin"

# Addresses from modules/cxosc/poly.s
VOICE_BASE, VOICE_STRIDE = 0x800049D8, 0xA8
CURSOR_AT, FP_PTR_AT, RS_PTR_AT = 0x80001C80, 0x800062A8, 0x800062A4
PART_PTR_AT, PART_IDX_AT = 0x46C82456, 0x100B14CF
NIBBLE, PING_AT = 0x46104D0C, 0x800000E0
STOCK_RENDER, PITCH_TAB = 0x40004008, 0x400AA294
KEYS_AT, GLIDE_AT = 0x400D2CB0, 0x100B14ED
MACH_OFF, SIG_OFF = 0x8EDA2, 0x8EDBC
CURVALS = 0x80000810
DSP_REC = 0x80000110

BANK = 0x42000000
HEADER = 0x80010000
FP_REC = 0x80011000
RS_REC = 0x80012000
STOP, STACK = 0x10000, 0x20000

Q14_PEAK = 0x4000
RAIL = 0x7FFFF0  # top-24 sample near full scale
FM_ROW = 5  # machine.s: sixth list row = CX OSC; after ANALOG BD / OCTA303 when the image has them (main)
MSG_FM_MAX = b"CX OSC: 1 MAX"


def die(msg):
    print(f"  [FAIL] verify_cxosc: {msg}", file=sys.stderr)
    sys.exit(1)


def check(label, ok, detail=""):
    if not ok:
        die(f"{label}" + (f" ({detail})" if detail else ""))
    print(f"  [PASS] {label}" + (f" — {detail}" if detail else ""))


def clear_part(uc):
    """Eight tracks: FLEX, no CX signature."""
    uc.mem_write(PART_PTR_AT, struct.pack(">I", BANK))
    uc.mem_write(PART_IDX_AT, b"\x00")
    for t in range(8):
        uc.mem_write(BANK + MACH_OFF + t, b"\x01")
        uc.mem_write(BANK + SIG_OFF + 30 * t, bytes(3))


def sign_cx(uc, track):
    uc.mem_write(BANK + MACH_OFF + track, b"\x01")
    uc.mem_write(BANK + SIG_OFF + 30 * track, b"CX\x01")


def call_ml_guard_p(uc, symbols, row, track):
    """ml_guard_p(a0=Part, d1=row, d2=track) -> d0 (0 = allow, else message ptr)."""
    if "ml_guard_p" not in symbols:
        die("ml_guard_p missing from runtime.elf")
    uc.reg_write(UC_M68K_REG_A7, STACK)
    uc.mem_write(STACK, struct.pack(">I", STOP))
    uc.reg_write(UC_M68K_REG_A0, BANK)  # part 0 = bank base
    uc.reg_write(UC_M68K_REG_D1, row)
    uc.reg_write(UC_M68K_REG_D2, track)
    try:
        uc.emu_start(symbols["ml_guard_p"], STOP, count=100_000)
    except Exception as e:
        die(f"ml_guard_p fault at pc={uc.reg_read(UC_M68K_REG_PC):#x}: {e}")
    if uc.reg_read(UC_M68K_REG_PC) != STOP:
        die(f"ml_guard_p did not return (pc={uc.reg_read(UC_M68K_REG_PC):#x})")
    return uc.reg_read(UC_M68K_REG_D0)


def read_cstr(uc, addr, n=32):
    if addr == 0:
        return b""
    raw = bytes(uc.mem_read(addr, n))
    return raw.split(b"\0", 1)[0]


def check_guard(uc, symbols):
    """One CX OSC per Part: refuse a second choice; allow first / own / stock."""
    clear_part(uc)
    d0 = call_ml_guard_p(uc, symbols, FM_ROW, 0)
    check("guard: first CX OSC on T1 allowed", d0 == 0, f"d0={d0:#x}")

    sign_cx(uc, 0)
    d0 = call_ml_guard_p(uc, symbols, FM_ROW, 0)
    check("guard: choosing CX OSC again on the same track allowed", d0 == 0)

    d0 = call_ml_guard_p(uc, symbols, FM_ROW, 1)
    msg = read_cstr(uc, d0)
    check(
        "guard: second track refused with CX OSC: 1 MAX",
        d0 != 0 and msg == MSG_FM_MAX,
        f"d0={d0:#x} msg={msg!r}",
    )

    # Stock row (FLEX = 1): always allowed even with one CX OSC present
    d0 = call_ml_guard_p(uc, symbols, 1, 1)
    check("guard: stock row on a free track allowed beside one CX OSC", d0 == 0)

    # Paste-style: destination Part already has CX on T1; choosing CX on T3
    clear_part(uc)
    sign_cx(uc, 0)
    d0 = call_ml_guard_p(uc, symbols, FM_ROW, 2)
    msg = read_cstr(uc, d0)
    check(
        "guard: paste onto another track refused (same ml_guard_p)",
        d0 != 0 and msg == MSG_FM_MAX,
        f"msg={msg!r}",
    )


def map_page(uc, addr, size=0x1000):
    base = addr & ~0xFFF
    end = (addr + size + 0xFFF) & ~0xFFF
    try:
        uc.mem_map(base, end - base)
    except Exception:
        pass


def map_range(uc, addr, size):
    base = addr & ~0xFFF
    end = (addr + size + 0xFFF) & ~0xFFF
    cur = base
    while cur < end:
        try:
            uc.mem_map(cur, 0x1000)
        except Exception:
            pass
        cur += 0x1000


def load_runtime():
    if not (RUNTIME / "runtime.bin").is_file():
        print("  [SKIP] verify_cxosc: no out/platform/runtime (build the remix first)")
        return None
    if not OS_BIN.is_file():
        print("  [SKIP] verify_cxosc: no stock MAIN OS (make os && make recon)")
        return None
    nm = subprocess.check_output(["m68k-elf-nm", str(RUNTIME / "runtime.elf")], text=True)
    symbols = {f[2]: int(f[0], 16) for f in (line.split() for line in nm.splitlines()) if len(f) == 3}
    if "sy_render" not in symbols:
        die("sy_render missing from runtime.elf")
    if "ml_guard_p" not in symbols:
        die("ml_guard_p missing from runtime.elf")
    headers = subprocess.check_output(
        ["m68k-elf-objdump", "-h", str(RUNTIME / "runtime.elf")], text=True
    )
    base = int(
        next(
            line.split()[3]
            for line in headers.splitlines()
            if len(line.split()) > 3 and line.split()[1] == ".text"
        ),
        16,
    )
    data = (RUNTIME / "runtime.bin").read_bytes()
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    mapped = base & ~4095
    uc.mem_map(mapped, (base - mapped + len(data) + 4095) & ~4095)
    uc.mem_write(base, data)

    # Stock ROM: pitch table + stub STOCK_RENDER (rts) + KEYS_AT page
    os_bytes = OS_BIN.read_bytes()
    map_range(uc, 0x40000000, 0x100000)
    uc.mem_write(0x40000000, os_bytes[:0x100000])
    uc.mem_write(STOCK_RENDER, bytes.fromhex("4e75"))  # rts
    # Unicorn's ColdFire EMAC path faults on stock po_rate (macl). Stub it:
    # always C4_INC — pitch is fixed; FOLD/SYMM/RATO/DEC still run in sy_loop.
    if "po_rate" in symbols:
        # move.l #25480119,%d0; rts  (C4_INC — Unicorn EMAC faults on the real curve)
        uc.mem_write(symbols["po_rate"], bytes.fromhex("203c0184cbb74e75"))

    map_range(uc, 0x10000, 0x20000)
    map_range(uc, 0x100B0000, 0x2000)
    map_range(uc, 0x42000000, 0xA0000)  # Part blob through SIG_OFF (~0x8edbc) + stride
    map_range(uc, 0x46000000, 0x2000)
    map_range(uc, 0x46104000, 0x2000)
    map_range(uc, 0x46C82000, 0x2000)
    map_range(uc, 0x80000000, 0x20000)

    def on_unmap(uc_, access, address, size, value, data):
        print(f"  [FAIL] unmapped access {access} @ {address:#x} size {size}", file=sys.stderr)
        return False

    uc.hook_add(UC_HOOK_MEM_UNMAPPED, on_unmap)
    uc.reg_write(UC_M68K_REG_SR, 0x2000)
    return uc, symbols, base


def plant_part(uc, track=0):
    """FLEX + signature CX\\x01 on `track` in part 0."""
    uc.mem_write(PART_PTR_AT, struct.pack(">I", BANK))
    uc.mem_write(PART_IDX_AT, b"\x00")
    uc.mem_write(BANK + MACH_OFF + track, b"\x01")  # FLEX
    uc.mem_write(BANK + SIG_OFF + 30 * track, b"CX\x01")


def plant_fp(uc, ptch=64, rato=32, indx=40, fold=0, symm=0, dec=127):
    """PLAYBACK halfwords as the packer leaves them (raw << 8). DEC 127 = HOLD."""
    words = [ptch, rato, indx, fold, symm, dec]
    blob = b"".join(struct.pack(">H", (v & 0xFF) << 8) for v in words)
    uc.mem_write(FP_REC, blob + bytes(64))
    uc.mem_write(FP_PTR_AT, struct.pack(">I", FP_REC))
    uc.mem_write(RS_REC, bytes(64))
    uc.mem_write(RS_PTR_AT, struct.pack(">I", RS_REC))


def plant_amp(uc, track=0, atk=0, hold=127, rel=64, dsp_atk=None, dsp_hold=None, dsp_rel=None):
    """Live-lane AMP bytes + optional DSP voice-record halfwords (value << 8).

    Tim 2.20: scenes/LFOs write the DSP record; po_amp_snap reads it before
    sy_ison overrides. Re-plant the DSP halfwords every frame in the harness
    (no frame builder). Defaults: DSP mirrors the live lane.
    """
    lane = CURVALS + 72 * track
    uc.mem_write(lane + 12, bytes([atk & 0xFF, hold & 0xFF, rel & 0xFF]))
    uc.mem_write(PING_AT, b"\x00")
    da = atk if dsp_atk is None else dsp_atk
    dh = hold if dsp_hold is None else dsp_hold
    dr = rel if dsp_rel is None else dsp_rel
    # ping 0, track t: DSP_REC + 64*t; halfwords 0/1/2 = ATK/HOLD/REL
    base = DSP_REC + 64 * track
    uc.mem_write(
        base,
        struct.pack(
            ">HHH",
            (da & 0xFF) << 8,
            (dh & 0xFF) << 8,
            (dr & 0xFF) << 8,
        ),
    )


def plant_voice(uc, track=0, active=True, **amp):
    uc.mem_write(VOICE_BASE + VOICE_STRIDE * track, b"\xff" if active else b"\x00")
    plant_amp(uc, track, **amp)


def render_frames(uc, symbols, knobs, frames=64, track=0, amp=None):
    """Cold-start then run `frames` second-calls; return interleaved L samples (signed 24)."""
    amp = dict(amp or {})
    plant_part(uc, track)
    plant_fp(uc, **knobs)
    plant_voice(uc, track, True, **amp)
    uc.mem_write(HEADER, bytes(16 + 16 * 8 * 2))  # header + stereo pairs
    uc.mem_write(CURSOR_AT, struct.pack(">I", HEADER))
    uc.mem_write(GLIDE_AT, b"\x00")
    uc.mem_write(KEYS_AT + track, b"\x00")
    # Start bit on the second-call path
    uc.mem_write(NIBBLE + track, bytes([0x10]))

    samples = []
    insn = [0]

    def count(_uc, _a, _s, _d):
        insn[0] += 1

    hook = uc.hook_add(UC_HOOK_CODE, count)
    sy = symbols["sy_render"]

    def call_render(start, end):
        # Frame builder stand-in: effective AMP in the DSP record before snap.
        plant_amp(uc, track, **amp)
        uc.reg_write(UC_M68K_REG_A7, STACK)
        # sy_render frame: return, then d2-d7/a2-a6 park is inside the routine;
        # ABI args after the 48-byte frame: track, ping, start, end at 52..64
        # Call convention here: push args then jsr — mirror verify_analog_bassdrum_cf
        # which puts stop + args on stack and starts at symbol (callee sees args at 4(sp)+).
        # sy_render does lea -48(sp) then movem, so args land at 52(sp)=track when
        # called with (track, ping, start, end) above the return address.
        uc.mem_write(
            STACK,
            struct.pack(">IIIII", STOP, track, 0, start, end),
        )
        insn[0] = 0
        try:
            uc.emu_start(sy, STOP, count=500_000)
        except Exception as e:
            pc = uc.reg_read(UC_M68K_REG_PC)
            die(f"sy_render fault at pc={pc:#x}: {e}")
        if uc.reg_read(UC_M68K_REG_PC) != STOP:
            die(f"sy_render did not return (pc={uc.reg_read(UC_M68K_REG_PC):#x})")
        return insn[0]

    # Frame 0: cold start (end==16, start bit set)
    cost0 = call_render(0, 16)
    uc.mem_write(NIBBLE + track, bytes([0x00]))  # no further starts

    costs = [cost0]
    for _ in range(frames):
        uc.mem_write(CURSOR_AT, struct.pack(">I", HEADER))
        uc.mem_write(HEADER, bytes(16 + 16 * 8))
        costs.append(call_render(0, 16))
        # 16 stereo pairs at HEADER+16; take L (every other long)
        raw = bytes(uc.mem_read(HEADER + 16, 16 * 8))
        for i in range(16):
            word = struct.unpack_from(">I", raw, i * 8)[0]
            # sample << 16 in the long; top 24 bits are the DSP word
            s24 = word >> 8
            if s24 >= 0x800000:
                s24 -= 0x1000000
            samples.append(s24)

    uc.hook_del(hook)
    return samples, costs


def rms(xs):
    return math.sqrt(sum(x * x for x in xs) / max(len(xs), 1))


def main():
    global FM_ROW
    loaded = load_runtime()
    if loaded is None:
        return 0
    uc, symbols, _base = loaded
    sys.path.insert(0, str(ROOT / "tools"))
    from remix import hooks_flags
    FM_ROW = hooks_flags.image_row("CX OSC", ROOT)     # beside other machines (modules/hooks machine_rows)
    if FM_ROW != 5:
        print(f"  CX OSC is row {FM_ROW} of this image's machine list (machine_rows)")

    check_guard(uc, symbols)

    # SYMM default 64 = even; plant fold-alone at even so bias variants differ.
    base = dict(ptch=64, rato=32, indx=48, fold=0, symm=64, dec=127)
    variants = {
        "base": base,
        "fold": {**base, "fold": 96},
        "symm": {**base, "fold": 96, "symm": 112},
        "symm_lo": {**base, "fold": 96, "symm": 16},
        "rato": {**base, "rato": 96},
        "dec": {**base, "dec": 32},
        "rails": {**base, "fold": 127, "symm": 127, "dec": 127, "indx": 127},
    }

    outs = {}
    costs = {}
    for name, knobs in variants.items():
        # Fresh sy_state: zero the BSS-ish records by re-loading is heavy;
        # clear sy_state via symbol if present.
        if "sy_state" in symbols:
            uc.mem_write(symbols["sy_state"], bytes(128 * 8))
        samples, frame_costs = render_frames(uc, symbols, knobs, frames=48)
        outs[name] = samples
        costs[name] = frame_costs
        peak = max(abs(x) for x in samples) if samples else 0
        check(f"{name}: produces audio", peak > 100, f"peak={peak}")

    # Each knob must change the waveform vs the baseline it shares.
    def differ(a, b, label, min_frac=0.02):
        n = min(len(a), len(b))
        diff = sum(1 for i in range(n) if a[i] != b[i]) / max(n, 1)
        check(label, diff >= min_frac, f"{diff * 100:.1f}% samples differ")

    differ(outs["base"], outs["fold"], "FOLD changes the output")
    differ(outs["fold"], outs["symm"], "SYMM high bias ≠ even (vs FOLD alone)")
    differ(outs["fold"], outs["symm_lo"], "SYMM low bias ≠ even (vs FOLD alone)")
    differ(outs["symm_lo"], outs["symm"], "SYMM low bias ≠ high bias")
    differ(outs["base"], outs["rato"], "RATO changes the output")
    differ(outs["base"], outs["dec"], "DEC (not HOLD) changes the output")

    # Boundedness at full FOLD/SYMM/DEC HOLD: count samples at both rails.
    rails = outs["rails"]
    pos = sum(1 for x in rails if x >= RAIL)
    neg = sum(1 for x in rails if x <= -RAIL - 1)
    frac = (pos + neg) / max(len(rails), 1)
    peak = max(abs(x) for x in rails)
    check(
        "FOLD=SYMM=DEC=127 stays bounded (not stuck on the rails)",
        frac < 0.25 and peak <= 0x7FFFFF,
        f"rail {frac * 100:.2f}% ({pos}+/{neg}-), peak={peak:#x}",
    )
    # Non-silent at the extreme
    check("extreme settings still sound", rms(rails) > 100, f"rms={rms(rails):.1f}")

    # Tim 2.20 AMP path: live lane ATK stays 0; DSP record carries the effective ATK.
    # A slow DSP ATK must change early frames vs a fast DSP ATK (snap, not CURVALS).
    if "sy_state" in symbols:
        uc.mem_write(symbols["sy_state"], bytes(128 * 8))
    if "po_amp" in symbols:
        uc.mem_write(symbols["po_amp"], bytes(8 * 4))
    fast, _ = render_frames(
        uc,
        symbols,
        base,
        frames=24,
        amp=dict(atk=0, hold=127, rel=64, dsp_atk=0),
    )
    if "sy_state" in symbols:
        uc.mem_write(symbols["sy_state"], bytes(128 * 8))
    if "po_amp" in symbols:
        uc.mem_write(symbols["po_amp"], bytes(8 * 4))
    slow, _ = render_frames(
        uc,
        symbols,
        base,
        frames=24,
        amp=dict(atk=0, hold=127, rel=64, dsp_atk=100),
    )
    early = 16 * 8  # first ~8 steady frames after cold start
    differ(fast[:early], slow[:early], "DSP-record ATK (2.20 snap) shapes the attack", min_frac=0.05)
    if "po_amp" in symbols:
        # After the last slow frame, snap kept DSP ATK=100 in po_amp[0]
        snap = bytes(uc.mem_read(symbols["po_amp"], 4))
        check("po_amp snapshot holds DSP ATK", snap[0] == 100, f"po_amp={snap.hex()}")

    # Cost: mean instructions of steady frames (skip cold start).
    steady = costs["base"][1:]
    mean = sum(steady) / len(steady)
    peak_c = max(steady)
    # ColdFire frame is 16 samples; headroom vs a naive 132e6/44100≈2993 insn/sample
    # budget is not claimed — report instructions/frame only.
    per_sample = mean / 16
    print(
        f"  [INFO] CX OSC sy_render cost (Unicorn insn, mono, base knobs): "
        f"mean {mean:.0f}/frame ({per_sample:.1f}/sample), peak {peak_c}/frame"
    )
    (ROOT / "out/cxosc").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/cxosc/cost.txt").write_text(
        f"mean_insn_per_frame={mean:.1f}\n"
        f"peak_insn_per_frame={peak_c}\n"
        f"mean_insn_per_sample={per_sample:.2f}\n"
        f"frames={len(steady)}\n"
        f"note=Unicorn executed instructions, not hardware cycles\n"
    )
    check("cost measured", mean > 100, f"{mean:.0f} insn/frame")
    print("  [PASS] verify_cxosc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
