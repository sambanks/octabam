"""cxosc-core -- CORE + REMIX SWITCH + CX OSC + SEQ on the 14 stock effects.

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
    family="mods", evidence=(Evidence(Level.UNIT, unit="MKII", who="ilia-murzinov",
        image="CXOSC C28.RMX", date="2026-11-17",
        commit="f4b11964534b48d0428e3ff303d75d7063f8d878",
        note="Earlier CORE + CX OSC handoff, before SEQ was added; marker-less "
             "machine list, mono, stock LFOs. Ilia reports CX OSC sounds good "
             "on the MKII. The ColdFire emulator boots the image to the RTOS "
             "handoff. This does not measure the current SEQ combination."),
        Evidence(Level.UNIT, who="ilia-murzinov", image="CXSEQ CV.RMX (BUILD 79)",
            date="2026-11-20", commit="5e737dc4bddd27d2e6c02dc54b8de341493dbc08",
            note="Ilia confirms INDX changes the saw and triangle carrier waveforms on this build.")),
    doc="CORE + REMIX SWITCH + CX OSC and SEQ on the 14 stock effects.",
    modules=CORE + ("REMIX SWITCH", "CX OSC", "LOFI AMF FIX", "SEQ") + STOCK14,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): Pin("OFF"),
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
