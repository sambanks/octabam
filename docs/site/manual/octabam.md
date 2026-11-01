### About Octabam

Octabam is Octatrack OS 1.40C with more built in. It keeps what you know:
all 14 stock effects, both effect menus and the way a project is laid out.
On top of that it adds features for sequencing, Kits and scenes, MIDI and
USB, and three new effects. Every feature is credited to the person who wrote
it, and each has its own page in this manual. This is version 0.1.

### What changes on the unit

- **BRAIN.** A new **PROJ → BRAIN** menu holds templates, shared settings,
  effect defaults, performance views and a switcher that boots another
  image from the card. See [BRAIN](brain/index.md).
- **Kits.** 255 Kits per project; each pattern plays the Kit assigned to it.
  See [Kits](parts/kits.md).
- **Page 2 of FX1 and FX2.** The second effect page gets
  [parameter locks](parts/plocks-p2.md), [scene locks](parts/scenes-p2.md) and
  CC control, in ([CC map](midi-usb/cc-map.md)) and out
  ([CC feedback](midi-usb/cc-feedback.md)), so a controller's encoders follow
  the unit.
- **MIDI tracks.** [Scene locks](parts/midi-scenes.md) for the eight MIDI
  tracks, as the audio tracks have.
- **USB.** MIDI both ways and audio to a computer: the 16 track channels,
  MAIN and CUE by default, with the computer's channels able to stand in
  for the inputs. The settings are in BRAIN and take effect at the next
  boot. See [USB](midi-usb/usb.md).
- **Effects.** [Spectrum](effects/spectrum.md), [Character](effects/character.md)
  and [Modulation](effects/modulation.md) on FX1 and FX2. The stock effects
  stay as they were.
- **A machine.** [OCTA-303](machines/octa303.md), a TB-303 voice, in the
  machine list.
- **Sequencing and recording.** A clock-locked
  [direct jump](sequencer/direct-jump-kyoti.md) between patterns,
  [reloading one track](sequencer/reload-from-project.md) from the card, a
  recording length of [one pattern pass](sequencer/rlen-plen.md),
  [recorder trig mute](sequencer/rec-trig-mute.md),
  [mute modes](sequencer/mute-modes.md),
  [per-pattern mutes](sequencer/pattern-mute.md), a
  [scale quantizer](sequencer/quantizer.md) and a [tuner](sequencer/tuner.md).
  Also [track patterns](sequencer/trackpatterns.md) (each track plays its own
  pattern), [Euclidean fills](sequencer/euclid-fill.md),
  [varispeed](sequencer/varispeed.md) for STATIC and FLEX tracks, a track's scene
  [morph](parts/morph.md) played on its own, and a recorder TRIG mode that
  waits for the input ([rec threshold](sequencer/rec-threshold.md)).
- **Utilities.** [Copy a project](utilities/copy-project.md) without loading
  it and [save the recorder buffers](utilities/buffer-saver.md) with the project.
- **Fixes.** The recorder loop click, stock LO-FI's AMF knob and a few
  sequencer and card-write faults are [corrected](fixes/recorder-loop-fix.md).

SPECTRUM, CHARACTER and MODULATION are copied into the audio processor only
while a track uses them. Until the code arrives, about 25 ms after you choose
the effect, it passes the audio through. A pattern change that puts one of
them on all eight tracks, or takes it off them, leaves about 0.34 s of silence
at the switch. See
[Effect loader (sender)](inside/dlpump.md).

### Before you install

Back up the CF card first. Kits write a file into each project they load.
A project made on the unit after installing needs no preparation. To return
to stock OS, follow [Safety and Recovery](../../../safety.md).
