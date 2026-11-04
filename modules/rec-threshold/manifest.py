"""REC THRESHOLD -- recorder TRIG value 3 (THR): a REC press arms, the input level starts the recording.

`thresh.s` (one DRAM unit) has the detail; README.md the use, the
measurements and what is open. Ten detours:

- both recorder key handlers (0x40083544, and 0x400836d8, the one TRACK +
  REC reaches): the idle branch (0x4008364e, 0x40083836), where a press
  under THR holds stock's start word (keys + 0x8000) | 0x10 and the
  track's level instead of posting it; the TRIG decode (0x400835e2,
  0x400837b6), reached only while recording, where THR takes ONE2's path;
- the frame interrupt's input page advance (0x4000ab72): the newest
  complete page's peak against each armed track's level; at or over it,
  and with the track's TRIG still THR and its recorder idle, the held word
  goes to the immediate mailbox; the arm is spent either way. It also runs
  the IN meter while RECORDING SETUP 2 draws, and the blink clock while a
  track is armed;
- RECORDING SETUP 1's push of the TRIG formatter (0x4002fb8e): THR drawn;
- RECORDING SETUP 2's cell loop (0x4002fdbe): on a THR track QREC's cell is
  LEV and QPL's is IN; the editor (0x4002ef60) leaves QPL alone there, and
  after its store (0x4002f0b4) TRIG becoming THR sets an unset LEV to -40;
- the track status icon renderer's state-cache load (0x4004bee2): an armed
  track's icon blinks, whatever it shows, and an armed track no longer on
  THR loses its arm there (REC_TRIG_MUTE replaces the same load: beside it,
  HOOKS owns the site and calls REC_TRIG_MUTE's fold, then this; modules/hooks,
  status_icon).

Three pokes: the TRIG count 3 -> 4, which the setup editor clamps by, and
the Part validator's hard-coded TRIG maximum 2 -> 3, which otherwise
rewrites a stored 3 to HOLD on every bank load.

LEV is the QREC byte under THR (raw -1 .. 16, QREC's own range, so the
editor and the validator need nothing) through lev_db: -60 .. 0 dB, 4 dB
steps to -8, then 2 dB. Raw -1 (OFF, never set) becomes -40 (raw 4) when
TRIG is set to THR, in the Part, its SRAM mirror and the published copy.
IN is the peak of inputs A-D, held ~0.5 s, then falling ~29 dB/s.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof

H = bytes.fromhex

TRIG_COUNT = 0x400D3C74 + 0xD2 + 3 * 4               # descriptor entry 8, slot 3, u32
VALIDATOR_CMP = 0x40002C92                           # moveq #2,d1 (TRIG max)
VALIDATOR_SET = 0x40002C98                           # moveq #2,d3 (written over a larger value)

MODULE = Module(
    name="rec-threshold",
    key="REC THRESHOLD",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES, author="Chupitnik", author_url="https://github.com/Chupitnik",
    proof=Proof.HARDWARE, proof_note="Chupitnik's MKII, 11-13 Oct 2026, THR1 to THR9 from the card: armed with TRACK 1 + REC AB, silence never records, the input starts the take, a second press cancels, LEV and IN on RECORDING SETUP 2, TRIG moved off THR while armed drops the arm and the blink, an armed track's icon blinks, armed inside RECORDING SETUP 1 it records; THR9 is this code",
    doc="Recorder TRIG value THR: a REC press arms, and recording starts when the input passes the track's LEV (RECORDING SETUP 2, beside a live IN meter).",
    linked=(Linked("thresh", "modules/rec-threshold/thresh.s", dram=True),),
    detours=(
        Detour(0x4008364E, H("7001b086667a"), "thresh", "idle_gate",
               "recorder key handler, idle recorder: under THR the start word is held"),
        Detour(0x400835E2, H("7001b085663a"), "thresh", "trig_gate",
               "recorder key handler, running recorder: THR behaves as ONE2"),
        Detour(0x40083836, H("7001b08b6674"), "thresh", "idle_gate_trk",
               "TRACK + REC handler, idle recorder: under THR the start word is held"),
        Detour(0x400837B6, H("7201b286662e"), "thresh", "trig_gate_trk",
               "TRACK + REC handler, running recorder: THR behaves as ONE2"),
        Detour(0x4000AB72, H("23c046104d00"), "thresh", "frame_check",
               "frame interrupt, input page advance: the level check while armed"),
        Detour(0x4002FDBE, H("224520514a88"), "thresh", "draw_gate",
               "RECORDING SETUP 2's cells: on a THR track QREC is drawn LEV, QPL IN (the meter)"),
        Detour(0x4002EF60, H("77b9100b14cc"), "thresh", "edit_gate",
               "RECORDING SETUP's editor: QPL (shown as IN) is not edited on a THR track"),
        Detour(0x4002F0B4, H("71b9100b14cc"), "thresh", "trig_init",
               "RECORDING SETUP's editor, after the store: TRIG set to THR with LEV unset -> LEV -40 dB"),
        Detour(0x4004BEE2, H("41f9400c0cb8"), "thresh", "blink_gate",
               "track status icons: an armed track's icon blinks", kind="jsr"),
        Detour(0x4002FB8E, H("2e84487af642"), "thresh", "trig_screen",
               "RECORDING SETUP: the TRIG formatter push, THR drawn", kind="jsr"),
    ),
    pokes=(
        Poke(TRIG_COUNT, (3).to_bytes(4, "big"), (4).to_bytes(4, "big"), "TRIG count 3 -> 4"),
        Poke(VALIDATOR_CMP, H("7202"), H("7203"), "part validator: TRIG max 2 -> 3"),
        Poke(VALIDATOR_SET, H("7602"), H("7603"), "part validator: TRIG max 2 -> 3"),
    ),
    gates=tuple(Gate(f"modules/rec-threshold/verify_rec_threshold_{g}.py", remix_arg=False, venv=True, stage="image")
                for g in ("arming", "inputs", "level")),
)
