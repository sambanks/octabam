"""octatrick -- SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP on the stock
effects, no octabam DSP code.

Tim Hastie's three ColdFire modules (github.com/timhastie/octatrick-modules,
the submodule under each wrapper) ported onto upstream octabam (25 Sep 2026):
the SYNTH machine (a FLEX track whose sample is named SYNTH*.wav plays a
two-operator FM voice; its LFO page's VOIC slot makes it paraphonic, chord
shapes from CHRD snapped onto SCALE), the SCALE and GLIDE rows in PROJECT >
CONTROL > SEQUENCER (the PTCH knob and CHROMATIC keys quantized to a scale;
the synth's glide time and 303-style legato on the keys), and the pattern
change option (CHAIN AFTER = DIRECT, its unused value 1). The voice engine is
a DRAM unit in the platform reserve (10 MB off the audio page arena); the
page, the quantizer and direct-jump caves are ROM.

The fourteen stock effects are listed as modules with fallback NONE, the
way usb-lean keeps a stock chooser: both DSP payloads, their dispatch and
the chooser's rows stay stock (the list is rebuilt at the long-list address
with the same fifteen rows), so every stock effect stays selectable and
every existing project plays as it did. Build with `make image
REMIX=octatrick BUILD=N`. octatrick-usb adds USB MIDI + USB AUDIO.
"""

from remix.schema import Remix

REMIX = Remix(
    name="octatrick",
    doc="SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP on the stock effects.",
    modules=("DIRECT JUMP", "SCALE QUANTIZER", "SYNTH MACHINE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
