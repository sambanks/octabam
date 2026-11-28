"""TUNED COMB -- stock COMB's page with the pitch kept in tune at any LP and FB.

A per-track insert: a feedback comb with a one-pole lowpass in the loop,
stereo, MIX blends. Stock COMB's loop is SR/f0 samples with the lowpass
inside it, so closing LP pulls the note flat (up to a semitone and more
in the settings that ring). Here the loop length is solved so the loop's
pole sits on the sounding fundamental (f0, or f0/2 with FB below 64, stock's
octave down), and the 4-point Hermite read's own phase error is taken out at
it. FB is a decay time (T60 the same at every note), so the solve is
closed-form on a change; where LP closes so far that holding the decay would
need a per-pass gain over 0.998, the gain is capped and an iteration solves
the pitch instead. Held knobs cost nothing for the solve.

FX1 or FX2. Two 1,536-word lines out of its slot (L at the allocator base,
R at +1,536), read at init. The SLOTS build setting (the stations' own,
tools/remix/stations.py) decides FX2: `FX1` (the default) makes an FX2
instance a dry pass that writes nothing (`Claims(fx1_only=True)`); `FX1+FX2`
runs it live on both. tuned_comb_ref.py is the float reference and the
source of the P table (175 words). Prototyped in Faust (comb.dsp).
"""

import importlib.util
import pathlib

from remix import stations
from remix.schema import (BusRole, Category, Claims, DspSection, Formatter, Gate, Harness,
                          Kind, Linked, MenuEntry, Module, Param, Evidence, Level, Store, YBase)

_spec = importlib.util.spec_from_file_location("tuned_comb_ref",
                                               pathlib.Path(__file__).with_name("tuned_comb_ref.py"))
_ref = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ref)

_INH = Formatter.INHERIT
_BLANK = Param(b"", 0)
_KN = "tuned_comb_knob"            # func_stops.s: the knob handlers (P+0x12a)

MODULE = Module(
    name="tuned-comb",
    key="TUNED COMB",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="Bryan T", author_url="https://github.com/bryantysinger",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="Bryan T", image="_bt_daily BUILD 98", date="2026-11-27",
        note="TUNED COMB on FX1 of all eight tracks, LOAD METER: sounds as intended, FUNC stops "
             "walk as documented; 4.6 % a slot held, 5.8-5.9 % with an LFO on LP and the crossfader on FB, "
             "different trigs on every track"),
              Evidence(Level.UNIT, unit="MKII", who="Bryan T", image="_bt_daily BUILD 99", date="2026-11-27",
        note="with the input's DC blocker, on FX1 of all eight tracks: a re-recorded looped phrase has its "
             "DC at -78 dBFS (it was -17 dBFS) and symmetric peaks; LOAD METER 6.5 % a slot with a "
             "triangle LFO on LP, settled (5.9 % on build 98)"),),
    doc="Stock COMB's page with the pitch held in tune at any LP and FB, on FX1, or FX1 and FX2 (SLOTS).",
    menu=MenuEntry(
        # 0x1e: a free-pool id; RESONATOR prefers it too, and the registry
        # settles a remix carrying both (registry.assign_ids).
        fx2_id=0x1e,
        donor_desc=0x400d5402,        # COMB FILTER: its page, PTCH's note names
        abbr=b"TCMB",
        fullname=b"TUNED COMB",
        build_tag=False,
    ),
    params=(
        # ---- page 1: stock COMB's slots and renderers, stock's defaults ----
        # FUNC: an octave a detent (the note's name kept); stock COMB's
        # handler jumped to the ends. The words not given stay COMB's.
        Param(b"PTCH", 26, 96, active=True, word_12a=(_KN, "tc_knob_ptch"),
              doc="the note, A#0 to A8 (stock's names); in tune at any LP and FB"),
        # FUNC stops: -100 -50 0 +50 +98 cents
        Param(b"FINE", 64, active=True, word_12a=(_KN, "tc_knob_fine"),
              doc="fine tune, +-1 semitone (64 is none)"),
        # FUNC stops: 81 Hz, then octaves 125 Hz .. 8 kHz, open
        Param(b"LP", 127, active=True, word_12a=(_KN, "tc_knob_lp"),
              doc="the lowpass in the loop: 81 Hz at 0 to open at 127, 16 steps an octave"),
        # FUNC stops: T60 30 10 5 2 1 0.5 s each side of 64 (none)
        Param(b"FB", 96, active=True, word_12a=(_KN, "tc_knob_fb"),
              doc="decay time, 0.05 s by 64 to 30 s at the ends; below 64 the note drops an octave"),
        _BLANK,
        # FUNC stops: quarters
        Param(b"MIX", 0, active=True, word_12a=(_KN, "tc_knob_mix"),
              doc="dry/wet; 127 is the comb alone, 0 is exact passthrough"),
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/tuned-comb/tuned_comb.asm",
        ptable=_ref.TABLE,            # E2 (65), LG2, ATN, BLP (33 each), SH (11)
        priority=33,
        bus_role=BusRole.NONE,        # an insert; it writes nothing to the bus
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    # Two 1,536-word lines, the whole 3,072 an FX1 slot gives; `fx1_only` is
    # the promise that an FX2 instance writes nothing (verify_tuned_comb).
    claims=Claims(stock_instance_buffer=True, buffer_words=3072, fx1_only=True),
    harness=Harness(layout_char="5", is_server=False, bus_client=False),
    store=Store("octabam.tuned-comb"),
    settings=(stations.setting(),),
    variant=stations.variant(lambda: MODULE),
    gates=(Gate("tools/verify/verify_tuned_comb.py", remix_arg=False),
           # the FUNC-stop handlers under Unicorn: assembled alone, no image
           Gate("tools/verify/verify_tuned_comb_knobs.py", remix_arg=False, venv=True)),
    # ColdFire: FUNC + turn walks per-knob stops (P+0x12a handlers).
    linked=(Linked(_KN, "modules/tuned-comb/func_stops.s"),),
    dear={"PTCH": 95, "FINE": 127, "LP": 0, "FB": 0, "MIX": 64},
)
