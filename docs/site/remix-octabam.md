# Octabam v0.5

![BRAIN in the main menu, added by Octabam](img/brain/pane.png)

*BRAIN in the main menu, added by Octabam*

Octabam adds core workflow features, four new effects, and two new machines to
Octatrack OS 1.40C. All 14 stock effects stay in both effect menus as usual,
with stock LO-FI's AMF knob fixed. The
[Octabam Manual](reference/manual/index.md) documents every feature across all
three remixes.

!!! warning "Known fault: DARK REV while MODULATION is loaded"
    The DSP can freeze if a program change loads DARK REV on several tracks
    while MODULATION is loaded (either active on a track, or within 10 seconds
    after the last track stops using it), followed by pressing PLAY. Audio
    stops while the front panel and USB keep responding; power-cycling clears
    the fault. The root cause is not yet known. Avoid using DARK REV across
    multiple tracks in a song that also uses MODULATION.

## The effects

SPECTRUM, CHARACTER, and MODULATION are available on both FX1 and FX2, and
SHATTER is available on FX2 alongside the stock effects. COMPRESSOR also gains
a sidechain input: set KEY on page 2 to choose the trigger track
([side-chain compressor](reference/manual/effects/sidechain-compressor.md)).

| Effect | Description |
|---|---|
| [SPECTRUM](reference/manual/effects/spectrum.md) | Multimode filter: Moog ladder, SEM, isolator, and formants |
| [CHARACTER](reference/manual/effects/character.md) | Channel strip: wavefolder, saturation, tilt EQ, compressor, and stereo width |
| [MODULATION](reference/manual/effects/modulation.md) | Juno chorus, Dimension chorus, flanger, phaser, and comb filter |
| [SHATTER](reference/manual/effects/shatter.md) | Wavefolder, clipper, bit and sample-rate crusher, and chaotic feedback |

These effects load into the DSP on demand only while a track uses them. When
you select one, audio passes through dry for roughly 25 ms while its code
loads. A pattern change that adds or removes a loaded effect across all eight
tracks causes about 0.34 s of silence during the switch
([effect loader](reference/manual/inside.md#effect-loader-sender)). Because
stock reverbs and on-demand effects share the same FX2 memory region, the menu
prevents selecting both at once and shows a warning message.

## What else you get

- [BRAIN](reference/manual/brain/index.md): a **PROJ → BRAIN** menu for
  templates, shared settings, effect defaults, performance monitoring, and
  switching between firmware images stored on the CF card.
- [Kits](reference/manual/parts/kits.md): 255 named Kits per project, assignable
  to individual patterns.
- [Page 2 parameter locks](reference/manual/parts/plocks-p2.md) and
  [scene locks](reference/manual/parts/scenes-p2.md): lock parameters on both
  effect pages, paired with [CC map](reference/manual/midi-usb/cc-map.md) for
  MIDI input and [CC feedback](reference/manual/midi-usb/cc-feedback.md) for
  MIDI output so external controllers stay in sync.
- [MIDI scenes](reference/manual/parts/midi-scenes.md): scene locks for the
  eight MIDI tracks.
- [MIDI loopback](reference/manual/midi-usb/midi-loopback.md): route MIDI tracks
  to the Octatrack's audio tracks, external gear, or both without an external
  MIDI cable.
- [USB](reference/manual/midi-usb/usb.md): bidirectional USB MIDI plus USB audio
  to a computer (16 track channels, MAIN, and CUE enabled by default).
- [SCOPE](reference/manual/utilities/scope.md) (**[DOWN]** + **[TEMPO]**) and
  [TUNER](reference/manual/utilities/tuner.md) (**[UP]** + **[TEMPO]**):
  full-screen oscilloscope and note tuner.
- [OCTA-303](reference/manual/machines/octa303.md): a TB-303 synth machine.
- [WAVE](reference/manual/machines/wavecf.md): a 4-voice wavetable synth machine
  with chords. A Part can hold up to two OCTA-303 or WAVE machines in total.
- [SEQ](reference/manual/sequencer/seq.md) (**[TRACK]** + **[PAGE]**):
  Euclidean rhythm, parameter-lock, and melody generator.
- [Pattern mute](reference/manual/sequencer/pattern-mute.md): double-press FUNC
  to toggle between global mutes and per-pattern mutes.
- [Scales](reference/manual/midi-usb/scales.md) and
  [Chords factory](reference/manual/midi-usb/chords.md): 52 scales for MIDI
  tracks and the scale quantizer, plus chord progressions for MIDI tracks.
- [Slow LFO](reference/manual/sequencer/slow-lfo.md) (LFO MULT down to 1/8X) and
  [bar LED](reference/manual/sequencer/bar-led.md) (blinks the tempo LED green
  on beat 1).
- [Screen](reference/manual/midi-usb/screen.md): capture screenshots over MIDI
  using Elektron's screenshot request.
- Additional sequencer tools, recording helpers, utilities, and
  [fixes to stock behaviour](reference/manual/fixes.md). See the manual's
  [feature comparison table](reference/manual/index.md#which-remix-has-what) for
  the complete list.

## Install

1. **Back up your CF card.** KITS writes a `kits.work` file into every project
   it loads.
2. Open [Build and Install](web-builder.md) to patch your copy of OS 1.40C in
   the browser and download the output files.
3. Follow [Install the image](web-builder.md#install-the-image), then check
   **SYSTEM STATUS → OS VERSION** to confirm it displays `OCTABAM` and the build
   number.
4. Projects created on the unit after installation need no extra setup.
5. To return to stock OS, see [Safety and Recovery](safety.md).

## Everything in the image

??? note "Full list of features and authors"

    --8<-- "reference/_remix-octabam.md"
