"""GATE VERB -- a gated plate reverb for FX2, built on the reverb stage of Mutable Instruments Clouds.

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
output for 2048 + 256 k samples after the input falls quiet and then closes it
over 128 samples; the tank keeps ringing underneath (0 is off).
"""
from remix.schema import (BusRole, Category, Claims, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, Module, Param, Proof, YBase)

MODULE = Module(
    name="gateverb", key="GATE VERB", kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="Emilie Gillet (Mutable Instruments), ported here",
    author_url="https://github.com/pichenettes/eurorack",
    proof=Proof.HARDWARE, proof_note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); " "`verify_gateverb` (dsp_host, against a float model of Clouds' reverb)",
    doc="A gated plate reverb (Griesinger topology, after the reverb stage of Mutable Instruments Clouds): amount, input gain, time, diffusion, tone, gate. One FX2 slot per instance.",
    menu=MenuEntry(fx2_id=0x1a, donor_desc=0x400d5594,
                   abbr=b"GVRB", fullname=b"Gate Verb", build_tag=False),
    params=(
        Param(b"AMNT", 40, active=True, formatter=Formatter.PLAIN, doc="dry/wet; 0 is exactly dry"),
        Param(b"GAIN", 51, active=True, formatter=Formatter.PLAIN, doc="input gain; Clouds' 0.2 at 51"),
        Param(b"TIME", 64, active=True, formatter=Formatter.PLAIN, doc="loop gain 0.35..0.98"),
        Param(b"DIFF", 100, active=True, formatter=Formatter.PLAIN, doc="allpass coefficient 0..0.8; Clouds' 0.625 at 100"),
        Param(b"TONE", 90, active=True, formatter=Formatter.PLAIN, doc="damping lowpass coefficient 0.05..1; Clouds' 0.7 at 90"),
        Param(b"GATE", 0, active=True, formatter=Formatter.PLAIN,
              doc="0 off; k holds the wet 2048 + 256 k samples after the input falls quiet, then closes"),
        *(Param() for _ in range(6)),
    ),
    dsp=DspSection(asm="modules/gateverb/gateverb.asm", priority=11,
                   bus_role=BusRole.NONE, ybase=YBase.NEVER,
                   r7_latch_slot=None, gate_label=None),
    claims=Claims(stock_instance_buffer=True, buffer_words=15862),
    harness=Harness(layout_char="H", is_server=False),
    dear={'AMNT': 127, 'GAIN': 127, 'TIME': 127, 'DIFF': 127, 'TONE': 127, 'GATE': 127},   # every knob at its maximum: the hardware matrix's dearest layout
    gates=(Gate('tools/verify/verify_gateverb.py', remix_arg=False, venv=True),),
)
