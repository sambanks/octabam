"""cxosc-core -- CORE + REMIX SWITCH + CX OSC on the 14 stock effects.

Unit handoff for the complex-oscillator machine. Not folded into ilia/latest.
Conflicts with SYNTH MACHINE (not included).
"""

from remix.schema import Pin, Evidence, Level, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2", "EVENTS",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD")
STOCK14 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")

REMIX = Remix(
    name="cxosc-core",
    family="mods", evidence=(Evidence(Level.EMULATOR,
        note="unit handoff: CORE + CX OSC; marker-less machine list, mono, stock LFOs"),),
    doc="CORE + REMIX SWITCH + CX OSC on the 14 stock effects.",
    modules=CORE + ("REMIX SWITCH", "CX OSC", "LOFI AMF FIX") + STOCK14,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): Pin("OFF"),
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
