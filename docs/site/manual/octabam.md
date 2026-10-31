### 1.1 About Octabam

Octabam is Octatrack OS 1.40C with more built in. It keeps what you know:
all 14 stock effects, both effect menus and the way a project is laid out.
On top of that it adds features for sequencing, Kits and scenes, MIDI and
USB, and four new effects. Every feature is a module, credited to its
author, and this manual describes each one.

Octabam has no delay and reverb bus. If you want one, see
[Octabam Bus](../octabam-bus/index.md), which adds it to the same features.

### 1.2 What changes on the unit

- **BRAIN.** A new **PROJ → BRAIN** menu holds templates, shared settings,
  effect defaults, performance views and a switcher that boots another
  image from the card. See [BRAIN](../../../brain.md).
- **Kits.** 255 Kits per project; each pattern plays the Kit assigned to it.
- **Page 2 of FX1 and FX2.** The second effect page gets parameter locks,
  scene locks and CC control, in and out, so a controller's encoders follow
  the unit.
- **MIDI tracks.** Scene locks for the eight MIDI tracks, as the audio
  tracks have.
- **USB.** MIDI both ways and audio to a computer: the 16 track channels,
  MAIN and CUE by default, with the computer's channels able to stand in
  for the inputs. The settings are in BRAIN and take effect at the next
  boot.
- **Sequencing and recording.** A clock-locked direct jump between
  patterns, reloading one track from the card, a recording length of one
  pattern pass (PLEN), recorder trig mute, mute modes, a scale quantizer
  and a tuner window.
- **OCTA-303.** A circuit-modelled TB-303 voice, chosen as a machine
  below PICKUP in the machine list. See [OCTA303](../../../usage/octa303.md).
- **More for the sequencer.** Track patterns (each track plays its own
  pattern of the bank, clip style), Euclidean fills, varispeed for STATIC
  and FLEX tracks, a track's scene morph played on its own (MORPH), and the
  seven diatonic modes for the MIDI tracks' KEY (MIDI SCALES).
- **Recording.** A recorder TRIG mode that waits for the input (REC
  THRESHOLD), and recorder buffers saved with the project (BUFFER SAVER).
- **Utilities.** A full-screen scope, copying a project without loading it,
  random names in the name editor, and FX2 LOCK, which stops the FX2
  chooser changing a track's effect.
- **Effects.** SPECTRUM, CHARACTER and MODULATION on FX1 and FX2,
  TRANSIENT on FX2, and a side-chain on COMPRESSOR. The stock effects stay
  as they were.
- **Fixes.** The recorder loop click, stock LO-FI's AMF knob and a few
  sequencer and card-write faults are corrected.

SPECTRUM, CHARACTER, MODULATION, TRANSIENT and the side-chain are copied
into the audio DSP only while a track uses them. Until the code arrives,
about 25 ms after you choose the effect, it passes the audio through.

### 1.3 Before you install

Back up the CF card first. KITS writes a file into each project it loads.
A project made on the unit after installing needs no preparation; a project
made before needs it once, as described in
[Build and Install](../../../web-builder.md). To return to stock OS, follow
[Safety and Recovery](../../../safety.md).
