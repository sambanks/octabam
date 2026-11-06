"""STUDIO VERB -- rooms, plates, halls and a desk-gated reverb for FX2, built on the reverb stage of
Mutable Instruments Clouds. GATE VERB until 6 Nov 2026 (`git log -- modules/gateverb`).

Clouds' reverb stage (clouds/dsp/fx/reverb.h, MIT, Emilie Gillet 2014): a
Griesinger/Dattorro plate of four input allpasses and a loop of two halves,
each two allpasses and a delay, with the first allpass smeared by an LFO and the
second delay modulated. The delay lengths are scaled by 0.9682 so the ring is
15,862 words, under the FX2 rule (+$3DFD, #785) that keeps the slot's last $202
words for SIDECHAIN_COMPRESSOR's window; the allocator gives an FX2 instance 16,384, and the top 256 words
of the slot carry the stock mailbox and LOAD METER, so the module declares its
extent (Claims.buffer_words) and never writes them.

The five knobs are Clouds' own setters: AMNT (amount), GAIN (input gain), TIME
(reverb time), DIFF (the allpass coefficient), TONE (the damping lowpass).
Defaults are the Clouds module's values. A sixth knob, GATE, holds the wet
output for 2048 + 256 k samples after the input falls quiet, then releases it as
a desk gate does (the gain falls 1/2048 a sample, -60 dB in about 320 ms) and,
once shut, empties the tank so the next hit starts from silence (0 is off).
Page 2 (this port's): SIZE moves the tank's read taps in, LCUT high-passes the
tank, MOD and RATE set the long delay's swing and both LFOs' speed. At their
defaults (127, 0, 64, 64) the module is exactly as it was without them.
"""
from remix.schema import (BusRole, Category, Claims, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, Module, Param, Proof, YBase)

MODULE = Module(
    name="studioverb", key="STUDIO VERB", kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="Emilie Gillet (Mutable Instruments), ported here",
    author_url="https://github.com/pichenettes/eurorack",
    proof=Proof.RENDER, proof_note="`verify_studioverb` (dsp_host, against a float model); not run on a unit. Its predecessor GATE VERB had cursory testing on Sam's MKII (owner report, 16 Oct 2026)",
    doc="A plate reverb (Griesinger topology, after Mutable Instruments Clouds) for rooms to halls, with a desk-style gate: amount, gain, time, diffusion, tone, gate; size, low cut, modulation depth and rate. One FX2 slot per instance.",
    menu=MenuEntry(fx2_id=0x1a, donor_desc=0x400d5594,
                   abbr=b"STVB", fullname=b"Studio Verb", build_tag=False),
    params=(
        Param(b"AMNT", 40, active=True, formatter=Formatter.PLAIN, doc="dry/wet; 0 is exactly dry"),
        Param(b"GAIN", 51, active=True, formatter=Formatter.PLAIN, doc="input gain; 51 matches the original Clouds reverb"),
        Param(b"TIME", 64, active=True, formatter=Formatter.PLAIN, doc="decay: loop gain 0.35 to 0.98"),
        Param(b"DIFF", 100, active=True, formatter=Formatter.PLAIN, doc="diffusion; 100 matches Clouds"),
        Param(b"TONE", 90, active=True, formatter=Formatter.PLAIN, doc="damping low-pass: lower is darker; 90 matches Clouds"),
        Param(b"GATE", 0, active=True, formatter=Formatter.PLAIN,
              doc="0 off; holds the tail 52-784 ms after the input goes quiet, then a desk-gate release"),
        Param(b"SIZE", 127, count=128, active=True, formatter=Formatter.PLAIN,
              doc="room size: the tank's delays from 20 % (0) to full (127); 127 is the original"),
        Param(b"LCUT", 0, count=128, active=True, formatter=Formatter.PLAIN,
              doc="low cut inside the tank: 0 off, up to about 1 kHz at 127 (250 Hz at 64)"),
        Param(b"MOD", 64, count=128, active=True, formatter=Formatter.PLAIN,
              doc="depth of the long delay's modulation: 0 static, 64 the original, 127 twice it"),
        Param(b"RATE", 64, count=128, active=True, formatter=Formatter.PLAIN,
              doc="speed of both modulation LFOs: 0 frozen, 64 the original, 127 twice it"),
        Param(),
        Param(b"PRE", 0, count=128, active=True, formatter=Formatter.PLAIN,
              doc="predelay, 0 to 92 ms, in the room SIZE leaves: none at 127, about 24 ms at 90, 44 ms at 60"),
    ),
    dsp=DspSection(asm="modules/studioverb/studioverb.asm", priority=11,
                   bus_role=BusRole.NONE, ybase=YBase.NEVER,
                   r7_latch_slot=None, gate_label=None),
    claims=Claims(stock_instance_buffer=True, buffer_words=15862),
    harness=Harness(layout_char="H", is_server=False),
    dear={'AMNT': 127, 'GAIN': 127, 'TIME': 127, 'DIFF': 127, 'TONE': 127, 'GATE': 127},   # every knob at its maximum: the hardware matrix's dearest layout
    gates=(Gate('tools/verify/verify_studioverb.py', remix_arg=False, venv=True),),
)
