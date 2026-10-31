"""LOAD METER -- the frame interrupt's share of the ColdFire and each DSP
core's busy time per frame, published for BRAIN's LOAD view (modules/brain:
TOOLS > LOAD, FUNC + LEVEL push on an MKII). The DSP half: dsp_meter.asm
and README.md "The DSP cores".

Two detours on the frame interrupt (vector 0x41, ~2,756 a second): its
entry 0x4000aad0, where the stub replays the prologue and stamps DMA timer
3's count, and its epilogue 0x4000d9a6, where the duration is summed and
the longest kept; every 0.5 s the window is published to lm_stats
{seq, window, sum, count, longest} in DMA timer 3 counts (132 MHz). The
sites are CF METER's epilogue and BOOT TRACE's entry: beside either, HOOKS
owns them and calls lm_in and lm_out built to return (modules/hooks,
frame_entry and frame_tail). meter.s has the arithmetic.
"""

import os
import pathlib

from remix.schema import (Category, Claims, Detour, DspHook, DspRange, DspSection, Gate, Kind, Linked,
                          Module, Proof, YBase)

H = bytes.fromhex
ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = "modules/load-meter/dsp_meter.asm"


def _dsp_asm():
    """The DSP source; for tools/verify/verify_load_meter.py's builds a copy
    under out/: LM_BURN=N burns N iterations of a one-cycle `nop` DO loop at
    each core's frame end, before the busy stamp (the calibration); LM_NOPUB=1
    leaves out core 0's publish and LM_NOOT=1 OTOP's stamps (the bit-identity references);
    LM_FRAME0=N starts core 0's frame count at N (the wrap at 2^23)."""
    n = int(os.environ.get("LM_BURN", "0") or 0)
    nopub = os.environ.get("LM_NOPUB") == "1"
    noot = os.environ.get("LM_NOOT") == "1"
    frame0 = int(os.environ.get("LM_FRAME0", "0") or 0)
    if not n and not nopub and not noot and not frame0:
        return SOURCE
    if n and not 0 < n < 4096:
        raise ValueError(f"LM_BURN={n}: 1..4095 (the short DO count)")
    src = (ROOT / SOURCE).read_text()
    if n:
        src = src.replace("; LM_BURN\n", f"        do      #{n},lm_burned\n        nop\nlm_burned:\n", 1)
    if frame0:
        if not 0 < frame0 < 1 << 23:
            raise ValueError(f"LM_FRAME0={frame0}: 1..2^23-1")
        src = src.replace("; LM_FRAME0\n", f"        move    #>{frame0},x0\n        move    x0,x:(r1+6)\n", 1)
    if nopub:
        src = src.replace("; LM_PUB\n", "        bra     lmp_x\n", 1)
    if noot:
        # OTOP's four hooks replay their displaced instruction and return (the bit-identity reference)
        src = src.replace("; OT_S\n", "        rts\n", 1)
        src = src.replace("; OT_E1\n        bsr     otop_end\n", "", 1)
        src = src.replace("; OT_E2\n        bsr     otop_end\n", "", 1)
    out = ROOT / "out/lm_variant/dsp_meter.asm"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(src)
    return str(out.relative_to(ROOT))


def _hooks_inc(modules, remix):
    """HOOKS's flags (modules/hooks): beside another module on one of its
    frame interrupt or boot sites, the routine returns and HOOKS replays the
    stock instructions once; alone, its own bytes."""
    from remix import hooks_flags
    return hooks_flags.inc("LOAD METER", modules)

MODULE = Module(
    name="load-meter", key="LOAD METER", kind=Kind.HYBRID,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); " "the window and both DSP cores' figures under the port (verify_load_meter, verify_brain)",
    doc="The frame interrupt's share of the ColdFire, each DSP core's busy time per frame and each effect call's cost, for BRAIN's OTOP screen.",
    linked=(Linked("loadmeter", "modules/load-meter/meter.s", cpu="5475", dram=True, include=_hooks_inc),),
    # Each core's busy time per frame (dsp_meter.asm): stamps of timer 0 at
    # its frame start and frame end, published by core 0 in MAIN's low bytes.
    dsp=DspSection(
        asm=_dsp_asm(),
        priority=21,
        payloads=frozenset({"A", "B"}),
        ybase=YBase.ALWAYS,                 # the per-payload base literal is the core switch
        hooks=(DspHook({"A": 0x8C, "B": 0x74}, (0x657000, 0x000206), "lm_start",
                       "frame start, just after the frame wait: the timer-0 start stamp and the period"),
               DspHook({"A": 0x54B, "B": 0x340}, (0x66F400, 0x000421), "lm_end",
                       "frame end, before the jump back to the wait: busy"),
               DspHook({"A": 0x2EC}, (0x60F000, 0x000205), "lm_pub",
                       "core 0, after the MAIN pack and before the pull: the bytes into MAIN's low bytes"),
               # OTOP: each effect slot's calls timed (dsp_meter.asm). The FX1 and
               # FX2 starts replay `move a,x:>$20a`, the ends `move x:>$213,b`
               # and `move x:>$206,r0`
               DspHook({"A": 0x4B2, "B": 0x2A7}, (0x567000, 0x00020A), "otop_s1",
                       "FX1 slot, before its calls: the start stamp"),
               DspHook({"A": 0x4D8, "B": 0x2CD}, (0x57F000, 0x000213), "otop_e1",
                       "FX1 slot, after its process call: the cost"),
               DspHook({"A": 0x4E8, "B": 0x2DD}, (0x567000, 0x00020A), "otop_s2",
                       "FX2 slot, before its calls: the start stamp"),
               DspHook({"A": 0x50E, "B": 0x303}, (0x60F000, 0x000206), "otop_e2",
                       "FX2 slot, after its process call: the cost")),
    ),
    claims=Claims(dsp_ranges=(DspRange("x", 0x37F10, 0x20, "both cores' meter figures and core 0's publish"),
                              DspRange("x", 0x37F40, 0x10, "both cores' OTOP cost cells"))),
    detours=(
        Detour(0x4000AAD0, H("4fefff0448d77fff"), "loadmeter", "lm_in",
               "the frame interrupt's entry: its prologue replayed, then the entry stamp", pad_to=8),
        Detour(0x4000D9A6, H("4cd77fff4fef00fc4e73"), "loadmeter", "lm_out",
               "the frame interrupt's epilogue, every exit path: the duration summed, the window published", pad_to=10),
        Detour(0x4000D310, H("4ab9800018fe"), "loadmeter", "lm_scrub",
               "the frame interrupt, before the recorder reads MAIN: the DSP meter's bytes taken and zeroed"),
    ),
    # STEM REC reads MAIN at its frame hook in the transfer routine (0x40004b12),
    # outside the order lm_scrub runs in. It needs no order: the meter's bytes are
    # only in the low byte of MAIN's longs, which STEM REC never writes to a file
    # (stems_bus16 keeps the top 16 bits, stems_bus24 shifts the low byte off), so
    # either order gives the same files. verify_stems checks MAIN.wav against the
    # DSP's own output on an image with both (28 Oct 2026; the conflict is gone).
    gates=(Gate("tools/verify/verify_load_meter.py", remix_arg=False, venv=True, stage="image"),
           Gate("tools/verify/verify_dsp_vectors.py"),
           Gate("tools/verify/verify_usb_load_meter.py", venv=True, stage="image"),),
)
