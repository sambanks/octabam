"""RETURNS -- the bus returns' levels on T8's FX2, independent of the host
tracks (docs/proposals/RETURNS.md; stage A: the reverb).

On T8's FX2 (core 0, r7 == $6b00) it publishes VRB and tells BusVerb to
print its wet into a buffer instead of onto T5; a hook in core 0's mixdown
(P:0x2d5) adds that buffer at (VRB/128)^2, the gain the firmware gives a
track at LEVEL VRB, into T8's input when MASTER TRACK is on (T8's FX1 and
fader then process the returns with the mix) or into MAIN when it is off.
T5 keeps only its own sound. Without RETURNS on T8, BusVerb prints on T5 as
before: an unconverted project plays as it did.

Clones FILTER's descriptor, as SEND does: DLY and VRB are page-1 slots 0
and 1 (the delay's first, as on the SEND page, since 30 Sep 2026), so stock
scene locks, the crossfader, LFOs and CC reach them. DLY is the delay's: BusDelay on core 1 hands its wet to core 0 through the shared
window (y:$36200..$36308, stamped buffers three back of the rotation).

On a unit: BSRET3, 29 Sep 2026 (remixes/bottleservice-ret). Under the port:
tools/verify/verify_returns.py.
"""

from remix.schema import (Category, DspHook, DspSection, Gate, Harness, Kind, MenuEntry,
                          Module, Param, Proof, YBase)

_BLANK = Param(b"", None, active=False)

MODULE = Module(
    name="returns",
    key="RETURNS",
    kind=Kind.DSP_CLIENT,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="an MKII, BSRET3 (bottleservice-ret), 29 Sep 2026: the reverb return off T5, through T8's FX1",
    doc="T8's FX2 carries the bus returns' levels (VRB, DLY); the returns go into T8's input "
        "(MASTER TRACK) or MAIN, not onto T5 and T1.",
    menu=MenuEntry(
        fx2_id=0x1b,              # <= 28: Octakit halts on a pick past stock ids
        donor_desc=0x400d4772,        # FILTER, as SEND
        abbr=b"RETN",
        fullname=b"Returns",
        build_tag=False,
    ),
    params=(
        Param(b"DLY", 108, active=True,
              doc="the delay's return level, as a track LEVEL: into T8's input or MAIN"),
        Param(b"VRB", 108, active=True,
              doc="the reverb's return level, as a track LEVEL: into T8's input or MAIN"),
        _BLANK, _BLANK, _BLANK, _BLANK,
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/returns/returns.asm",
        priority=25,
        payloads=frozenset({"A"}),          # core 0: T8, BusVerb and the mixdown
        ybase=YBase.NEVER,
        hooks=(DspHook(0x2d5, (0x60f000, 0x000206), "mixhook",
                       "mixdown end: the returns into T8's input (MASTER TRACK) or MAIN"),),
    ),
    harness=Harness(layout_char=None, is_server=False),
    requires=("REVERB SERVER",),
    # five cards under the port: flags, the gain law, where the return lands
    gates=(Gate("tools/verify/verify_returns.py"),),
)
