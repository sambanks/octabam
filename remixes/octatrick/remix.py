"""octatrick -- Tim Hastie's four modules (SYNTH MACHINE, SCALE QUANTIZER,
DIRECT JUMP, TUNER) with USB MIDI and USB audio both ways (20 channels out,
four in) on the stock effects less SPATIALIZER, no octabam DSP code.

Tim Hastie's ColdFire modules (github.com/timhastie/octatrick-modules, the
submodule under each wrapper, pinned to v2.9 (525f4b1)): the SYNTH machine
(a FLEX track whose sample is named SYNTH*.wav plays a two-operator FM
voice; its LFO page's VOIC slot makes it paraphonic, chord shapes from CHRD
snapped onto SCALE), the SCALE, ROOT and GLIDE rows in PROJECT > CONTROL >
SEQUENCER (the PTCH knob and CHROMATIC keys quantized to a scale), the
pattern change option (CHAIN AFTER = DIRECT, its unused value 1) and the
TUNER window (UP + TEMPO). markandrus's USB MIDI and USB AUDIO OUT TRACKS
MAIN CUE (a class-compliant MIDI port + a 20-channel 44.1 kHz 24-bit audio
input on the host: tracks 1-16, MAIN 17-18, CUE 19-20), and Bryan T's USB
AUDIO IN ABCD with USB CROSSBAR (four channels from the host onto inputs
A-D in place of the jacks while the stream is open; high speed only). The
synth's engine, the quantizer, the tuner and the USB units share the DRAM
platform reserve; the page and direct jump's cave are ROM.

Thirteen of the fourteen stock effects are listed with fallback NONE, the
way the usb-io-tracks-main-cue-* remixes keep a stock chooser. SPATIALIZER
is on neither chooser: the IN module's RX inject is placed in its words on
payload A (the build places it only in a stock effect's harvested words,
and the usb-io remixes give up SPATIALIZER's), so a project that selects
it runs NONE; every other effect and row stays stock. Build with `make
image REMIX=octatrick BUILD=N`; remixes/test/usb-out-tracks-main-cue/README.md
has the USB use steps. Until 29 Sep 2026 this selection was split three ways (octatrick,
octatrick-usb, octatrick-tuner).
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="octatrick",
    family="mods", proof=Proof.HARDWARE,
    proof_note="Tim's MKI, test build 3.0 b40 (this selection at BUILD 40), 29 Sep 2026: USB AUDIO IN brings the Mac's audio onto the inputs in a one-minute check (long runs not yet tested). The same four modules with the 26 Sep USB AUDIO (out only) ran on the same MKI through the 2.9 test builds; the tuner works on test build 3.0 b40 (UP + TEMPO); the last two 2.9 fixes are not yet confirmed on hardware",
    doc="SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP + TUNER + USB MIDI + USB AUDIO (20 channels out, 4 in onto A-D) on the stock effects less SPATIALIZER.",
    modules=("DIRECT JUMP", "SCALE QUANTIZER", "SYNTH MACHINE", "TUNER",
             "USB MIDI", "USB AUDIO OUT", "USB CROSSBAR", "USB AUDIO IN",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("TRACKS MAIN CUE"),
              ("octabam.usb-audio-in", "INPUTS"): Pin("ABCD")},
)
