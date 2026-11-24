"""VERBERATION -- rooms, plates, halls and a desk-gated reverb for FX2, by sambanks, built on the reverb
stage of Mutable Instruments Clouds (Emilie Gillet: the algorithm, not code). GATE VERB until 6 Nov 2026, then briefly STUDIO VERB (`git log -- modules/gateverb modules/studioverb`).

Clouds' reverb stage (clouds/dsp/fx/reverb.h, MIT, Emilie Gillet 2014): a
Griesinger/Dattorro plate of four input allpasses and a loop of two halves,
each two allpasses and a delay, with the first allpass smeared by an LFO and the
second delay modulated. The delay lengths are scaled by 0.9682 and the six tank
lines by a further 0.9, so the ring is 14,366 words and ends below slot offset
0x3820, where octabam's demand-loaded window code starts in the four window
slots; the module declares that extent (Claims.buffer_words) and never writes
past it, which is what lets octabam-verbs carry it beside the loader.

The five knobs follow Clouds' setters: AMNT (the mix), GAIN (input gain), TIME
(reverb time), DIFF (the allpass coefficient), TONE (the damping lowpass).
AMNT holds the dry at unity while the wet rises to full (0 to 64), then fades the
dry out (64 to 127); Clouds crossfades. A sixth knob, GATE, holds the wet
output for 2048 + 256 k samples after the input falls quiet, then releases it as
a desk gate does (the gain falls 1/2048 a sample, -60 dB in about 320 ms) and,
once shut, empties the tank so the next hit starts from silence (0 is off).
Page 2 (this port's): SIZE moves the tank's read taps in, LCUT high-passes the
tank, MOD and RATE set the long delay's swing and both LFOs' speed (to about four
times the original at 127), PRE a predelay that takes its room from the long delay.

MODE is the algorithm: ROOM injects the input diffuser's output as early reflections,
HALL swings delay 1 against the long delay, 80S keys the gate on transients; turning it
also lands the other knobs on the mode's values (mode_views).

The stop kill (STOP, STOP) reaches VERBERATION and its rows as it reaches the stock
reverbs: kill.s marks MODE's field 127 in the frame's DSP record, and the DSP cuts
to dry and clears its tank. kill.s detours the stock site BBD's kill.s detours, so
the two cannot share a remix until the site is bridged in HOOKS.
"""
from remix.schema import (BusRole, Category, Claims, Detour, DspSection, Formatter, Gate, Harness, ModeView,
                          Kind, Linked, MenuEntry, Module, Param, Evidence, Level, YBase)

_KEYS = ("VERBERATION", "VERB PLATE", "VERB ROOM", "VERB HALL")


def id_inc(modules, remix):
    """VB_IDS for kill.s: a `beq.s 2f` on each id this remix gave VERBERATION and its rows."""
    ids = sorted({modules[k].menu.fx2_id for k in _KEYS if k in modules})
    body = "".join(f"        moveq   #{i},%d1\n        cmp.l   %d1,%d0\n        beq.s   2f\n" for i in ids)
    return f"        .macro  VB_IDS\n{body}        .endm\n"


MODULE = Module(
    name="verberation", key="VERBERATION", kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.RENDER,
        note="`verify_verberation` (dsp_host, against a float model); not run on a unit. Its predecessor GATE VERB"
             " had cursory testing on Sam's MKII (owner report, 16 Oct 2026)"),),
    doc="A plate reverb for rooms to halls, after the reverb stage of Mutable Instruments Clouds (Emilie Gillet; Griesinger topology), with a desk-style gate: amount, gain, time, diffusion, tone, gate; size, low cut, modulation depth and rate. One FX2 slot per instance.",
    menu=MenuEntry(fx2_id=0x1a, donor_desc=0x400d5594,
                   abbr=b"VRBN", fullname=b"Verberation", build_tag=False),
    # Page 1 and the defaults are PLATE's view (MODE 1). Page 2 in slots 6-11: MODE (slot 6, as on every
    # effect), LCUT, MOD on the top row; RATE, SIZE, PRE below.
    params=(
        Param(b"AMNT", 35, active=True, formatter=Formatter.PLAIN,
              doc="mix: to 64 the wet rises to full over the dry; past 64 the dry fades out; 0 is exactly dry"),
        Param(b"GAIN", 51, active=True, formatter=Formatter.PLAIN, doc="input gain; 51 matches the original Clouds reverb"),
        Param(b"TIME", 82, active=True, formatter=Formatter.PLAIN, doc="decay: loop gain 0.35 to 0.98"),
        Param(b"DIFF", 100, active=True, formatter=Formatter.PLAIN, doc="diffusion; 100 matches Clouds"),
        Param(b"TONE", 90, active=True, formatter=Formatter.PLAIN, doc="damping low-pass: lower is darker; 90 matches Clouds"),
        Param(b"GATE", 0, active=True, formatter=Formatter.PLAIN,
              doc="0 off; holds the tail 52-784 ms after the input goes quiet, then a desk-gate release"),
        Param(b"MODE", 1, 4, active=True, formatter=Formatter.STEPPED,
              labels=("ROOM", "PLAT", "HALL", "80S"),
              doc="the algorithm: ROOM early reflections, HALL a second swung line, 80S a gate keyed on hits"),
        Param(b"LCUT", 20, count=128, active=True, formatter=Formatter.PLAIN,
              doc="low cut inside the tank: 0 off, up to about 1 kHz at 127 (250 Hz at 64)"),
        Param(b"MOD", 64, count=128, active=True, formatter=Formatter.PLAIN,
              doc="depth of the long delay's modulation: 0 static, 64 the original, 127 about four times it"),
        Param(b"RATE", 64, count=128, active=True, formatter=Formatter.PLAIN,
              doc="speed of both modulation LFOs: 0 frozen, 64 the original, 127 about four times it"),
        Param(b"SIZE", 127, count=128, active=True, formatter=Formatter.PLAIN,
              doc="room size: the tank's delays from 20 % (0) to full (127); 127 is the original"),
        Param(b"PRE", 0, count=128, active=True, formatter=Formatter.PLAIN,
              doc="predelay, 0 to 69 ms; past the room SIZE leaves it shortens the long delay a little"),
    ),
    # ---- the voicings MODE lands on (MODE DEFAULTS writes them on the panel) --------------------------
    # Chosen from renders of the module (6 Nov 2026, Sam: "those sound pretty good"): slots 0 AMNT, 1 GAIN,
    # 2 TIME, 3 DIFF, 4 TONE, 5 GATE, 7 LCUT, 8 MOD, 9 RATE, 10 SIZE, 11 PRE. AMNT keeps each mode's
    # wet-to-dry balance under the fixed-dry law (45 -> 35, 50 -> 41, 64 -> 64), PRE its time at 24 a step.
    mode_slot=6,
    mode_views=(
        ModeView(mode=0,                        # ROOM: small, bright, short
                 defaults={0: 35, 1: 60, 2: 70, 3: 90, 4: 105, 5: 0, 7: 30, 8: 30, 9: 64, 10: 35, 11: 0}),
        ModeView(mode=1,                        # PLATE: the full tank
                 defaults={0: 35, 1: 51, 2: 82, 3: 100, 4: 90, 5: 0, 7: 20, 8: 64, 9: 64, 10: 127, 11: 0}),
        ModeView(mode=2,                        # HALL: long, dark, more and slower modulation
                 defaults={0: 41, 1: 51, 2: 108, 3: 110, 4: 60, 5: 0, 7: 25, 8: 100, 9: 40, 10: 127, 11: 0}),
        ModeView(mode=3,                        # 80S: the desk-gated burst, the hit 15 ms ahead of it
                 defaults={0: 64, 1: 80, 2: 118, 3: 110, 4: 80, 5: 26, 7: 40, 8: 64, 9: 64, 10: 90, 11: 27}),   # Sam, 6 Nov 2026: AMNT 90 PRE 0 buried the hit
    ),
    dsp=DspSection(asm="modules/verberation/verberation.asm", priority=11,
                   bus_role=BusRole.NONE, ybase=YBase.NEVER,
                   r7_latch_slot=None, gate_label=None),
    claims=Claims(stock_instance_buffer=True, buffer_words=14366),
    linked=(Linked("vb_kill", "modules/verberation/kill.s", include=id_inc),),
    detours=(Detour(0x40004d0c, bytes.fromhex("302a00380680ffffffec"), "vb_kill", "vb_kill",
                    "the stop kill's reverb test: VERBERATION's ids mark MODE 127", pad_to=10),),
    harness=Harness(layout_char="H", is_server=False),
    dear={'AMNT': 127, 'GAIN': 127, 'TIME': 127, 'DIFF': 127, 'TONE': 127, 'GATE': 127},   # every knob at its maximum: the hardware matrix's dearest layout
    gates=(Gate('tools/verify/verify_verberation.py', remix_arg=False, venv=True),),
)
