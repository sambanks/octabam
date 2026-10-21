"""octabam-inserts -- the core ColdFire modules plus effects that run on any track.

CORE (BRAIN, STORE, KITS, MIDI SCENES, SCENES P2, PLOCKS P2, CC MAP, CC FEEDBACK,
USB at MAIN CUE, the recorder and bug fixes, MUTE_MODES from
DRAM, PATTERN MUTE, SCALE QUANTIZER, TUNER, DIRECT_JUMP_KYOTI, RELOAD_FROM_PROJECT, RLEN PLEN,
LOAD METER) with the effects that are inserts rather than bus servers:
SPECTRUM, CHARACTER and MODULATION (SLOTS = FX1+FX2: live on both menus),
TRANSIENT, EUCLID and LOFI2, the stock DELAY and GATE VERB (FX2). No bus and no SEND (fallback NONE). The other stock
DSP effects give up their words. No SIDECHAIN_COMPRESSOR: overlaps CHARACTER
(stock COMPRESSOR keeps its own id, undisturbed).
"""

from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES", "PATTERN MUTE",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD",
        "LOAD METER")
INSERTS = ("TRANSIENT", "EUCLID")
STATIONS = ("SPECTRUM", "CHARACTER", "MODULATION")

REMIX = Remix(
    name="octabam-inserts",
    family="mods", proof=Proof.HARDWARE, proof_note="cursory testing on Sam's MKII (owner report, 16 Oct 2026), before PATTERN MUTE was added; this selection not flashed",
    doc="CORE + SPECTRUM, CHARACTER, MODULATION, TRANSIENT and EUCLID on FX1 and FX2, LOFI2 (FX2), the stock DELAY and GATE VERB on FX2.",
    modules=STATIONS + ("MODE DEFAULTS", "DELAY", "GATE VERB") + INSERTS + ("LOFI2",) + CORE,
    fallback="NONE",
    fx1=STATIONS + INSERTS,
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM"),
              **{(f"octabam.{k.lower()}", "SLOTS"): Pin("FX1+FX2") for k in STATIONS}},
)
