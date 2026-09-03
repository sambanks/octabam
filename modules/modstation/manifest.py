"""MODULATION STATION -- one modulated line, seven modes, FX1 only.

The third BamSep26 station. It REPLACES stock CHORUS (id 0x12) and covers
what stock spreads over CHORUS, FLANGER, PHASER and COMB, plus the three the
box never had -- tremolo, vibrato and auto-pan:

    CHOR  a 10 ms line swept slowly, no feedback: the classic
    FLNG  a 0.3 ms line swept wide, with feedback: the jet
    PHSR  four allpass stages swept together, no line at all (STGS taps
          the chain at 2, 4, 6 or 8 poles)
    COMB  a short line tuned by DLY with heavy feedback: a resonator
    TREM  the LFO on amplitude
    VIB   the line, wet only: pitch modulation
    PAN   the LFO on amplitude, opposite in the two channels

⚠️ **FX1 ONLY, and it enforces that itself.** It needs a per-track delay line,
and beside the servers the only free per-track buffer is the FX1 slot: every
FX2 instance buffer is ChonVerb's tank on core 0 or BongDelay's line on
tracks 3-4. It reads its base from the host's bump allocator at INIT (never
in proc -- docs/DSP.md section 10), and if that base is an FX2 slot
(>= 0x4000) it runs as a dry pass and writes NOTHING. That promise is what
`Claims(fx1_only=True)` declares and what its render gate proves.

Two lines of 1,024 words, L and R, out of the 3,072 an FX1 slot gives: 23 ms
each, enough for chorus, flanger, vibrato and a comb down to 43 Hz. The FX1
bases (0x1000 0x1c00 0x2800 0x3400) are all multiples of 1,024, but nothing
here depends on that -- the read offset is masked, not the address.

It is a BUS CLIENT on the other two stations' terms: ->DEL / ->VRB on page 1,
registration gated on each knob, and it never housekeeps.

DEFAULTS ARE A PASSTHROUGH (MIX 0), because a part that stored CHORUS runs
this after the flash. ⚠️ A part's STORED bytes are stock CHORUS's -- the
stamper (plan A6) writes ours.
"""

from remix.schema import (BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, ModeView, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="modstation",
    key="MODULATION STATION",
    kind=Kind.DSP_EFFECT,
    doc="BamSep26 station: chorus/flanger/phaser/comb/trem/vib/pan, FX1 only.",
    menu=MenuEntry(
        fx2_id=0x12,
        replaces="CHORUS",
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects 7/9/11
        abbr=b"MODS",
        fullname=b"ModStn",
        build_tag=True,
    ),
    params=(
        # ---- page 1: the performance surface, scene/CC-reachable -----------
        Param(b"RATE", 40, active=True, formatter=_PLAIN,
              doc="LFO speed, ~0.05 Hz to ~8 Hz on a squared taper"),
        Param(b"DPTH", 48, active=True, formatter=_PLAIN,
              doc="how far the LFO sweeps the line (or the amplitude, in TREM/PAN)"),
        Param(b"FDBK", 0, active=True, formatter=_PLAIN,
              doc="feedback around the line: the flanger's jet, the comb's ring; 0 = none"),
        Param(b"MIX", 0, active=True, formatter=_PLAIN,
              doc="dry/wet; 0 = exact passthrough, 64 = classic chorus, 127 = vibrato"),
        Param(b"-DEL", 0, active=True, formatter=_PLAIN,
              doc="send the processed signal onto the DELAY bus; 0 = not a client"),
        Param(b"-VRB", 0, active=True, formatter=_PLAIN,
              doc="send the processed signal onto the REVERB bus; 0 = not a client"),
        # ---- page 2: knob / select / knob / select / knob / select ----------
        Param(b"DLY", 30, 128, active=True, formatter=_PLAIN,
              doc="the line's centre time, 0.2..23 ms -- in COMB it is the pitch"),
        Param(b"MODE", 0, 7, active=True, formatter=_STEP,
              labels=("CHOR", "FLNG", "PHSR", "COMB", "TREM", "VIB", "PAN"),
              doc="which engine: three line modes, a phaser, and three amplitude ones"),
        Param(b"TONE", 100, 128, active=True, formatter=_PLAIN,
              doc="one-pole damping inside the feedback path; lower = darker each pass"),
        Param(b"SHPE", 0, 4, active=True, formatter=_STEP,
              labels=("TRI", "SIN", "SQR", "SAW"),
              doc="LFO shape: TRI, SIN, SQR (steps the line: a chorus that jumps), SAW (a ramp)"),
        Param(b"WID", 64, 128, active=True, formatter=_PLAIN,
              doc="how far the right channel's LFO lags the left, 0 = mono, 64 = quarter"),
        Param(b"STGS", 1, 4, active=True, formatter=_STEP,
              labels=("2P", "4P", "6P", "8P"),
              doc="PHSR only: where the allpass chain is tapped, 2 to 8 poles"),
    ),
    # ---- what each MODE renames and re-defaults ---------------------------
    # DLY is the line's centre time in the line modes, the comb's PITCH, and
    # dead in the amplitude ones; FDBK is the flanger's jet and the comb's
    # ring and nothing at all in TREM/PAN; STGS is the phaser's alone.
    mode_slot=7,
    mode_views=(
        ModeView(mode=0,                        # CHOR
                 defaults={0: 30, 1: 48, 2: 0, 3: 64, 6: 30, 10: 64}),
        ModeView(mode=1,                        # FLNG
                 defaults={0: 24, 1: 90, 2: 90, 3: 64, 6: 10, 10: 64}),
        # ⚠️ ONLY SLOTS WHOSE MEANING CHANGES ARE RENAMED. Marking a knob
        # dead with "----" in the four modes that ignore it read well and
        # cost 56 bytes of a cave with 4 to spare -- the doc line says it
        # instead. Renaming is for a knob that does something ELSE.
        ModeView(mode=2,                        # PHSR
                 names={2: b"RES"},
                 defaults={0: 30, 1: 90, 2: 40, 3: 64, 11: 1}),
        ModeView(mode=3,                        # COMB
                 names={2: b"RING", 6: b"PTCH"},
                 defaults={0: 8, 1: 20, 2: 110, 3: 64, 6: 20}),
        ModeView(mode=4,                        # TREM
                 defaults={0: 70, 1: 90, 2: 0, 3: 127}),
        ModeView(mode=5,                        # VIB
                 defaults={0: 45, 1: 40, 2: 0, 3: 127, 6: 20, 10: 64}),
        ModeView(mode=6,                        # PAN
                 defaults={0: 55, 1: 100, 2: 0, 3: 127}),
    ),
    dsp=DspSection(
        asm="modules/modstation/mod_station.asm",
        priority=14,                  # after the character station
        bus_role=BusRole.NONE,        # an insert that also WRITES the bus
        ybase=YBase.NEVER,
        r7_latch_slot=0x69,           # ROTLATCH parks this block's offset here
        gate_label=None,              # no housekeeping: a station never elects
    ),
    # The FX1-only allocator buffer: two 1,024-word lines out of the 3,072 an
    # FX1 slot gives. `fx1_only` is the promise that an FX2 instance writes
    # nothing -- the ledger admits it beside a server on that basis, and
    # tools/verify_modstation.py is what proves it.
    claims=Claims(stock_instance_buffer=True, buffer_words=2048, fx1_only=True),
    harness=Harness(layout_char="3", is_server=False, bus_client=True),
)
