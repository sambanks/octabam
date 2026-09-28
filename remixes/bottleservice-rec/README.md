# `bottleservice-rec` -- bottleservice with 20 USB channels and the recorder click fixes

[`bottleservice`](../bottleservice/README.md) with two changes:

- **USB AUDIO OUT TRACKS MAIN CUE** in place of USB AUDIO OUT MASTER: twenty
  24-bit channels (tracks 1-8 as L/R pairs post-FX pre-fader, MAIN, CUE)
  instead of track 8's pair. T8 is still on channels 15/16, so nothing
  OUT MASTER carried is lost at high speed. This is the module image 88
  (bottleservice at `d6867bd`) carried on Sam's MKII, under its old name
  USB AUDIO. USB AUDIO IN CD stays: it needs a 250 us OUT layout and this
  is one.
- **The recorder click fixes**: [FLEX SEEK BIND](../../modules/flex-seekbind/README.md),
  [FLEX SEEK BIND CTR](../../modules/flex-seekbind-ctr/README.md),
  [RECORDER SPACING](../../modules/recorder-spacing/README.md) -- a FLEX
  track re-trigged every bar on its own recorder buffer seeks instead of
  restarting, and a fixed-RLEN take is exactly the gap to the next arm.
  Pinned in the tail of the 338 B zero run (0x400c460c..0x400c46c6): the
  rig's clones and label formatters leave no room in the floating window.

The first of two staged images; [`bottleservice-rec-plen`](../bottleservice-rec-plen/README.md)
adds RLEN PLEN, so a fault on the second is RLEN PLEN's.

## Where it has run

- **Hardware:** an MKII, OCTABAM1 (this remix at `074a4ff`, BUILD=1),
  28-29 Sep 2026, flashed over stock 1.40C, with a project converted by
  `ot_project.py host`. Reported working by its owner: the bus (DEL/REV
  sends, delay and reverb returns, the TEMPO window), a FLEX take
  re-trigged every bar on its own recorder buffer at 128 BPM with no
  bar-line click, an ordinary FLEX loop with slices / STRT locks as stock,
  twenty USB channels into macOS, and a Kit save plus FUNC + CUE reload.
  The USB counters were not read.
- `make check` with a stress_project.py project under the port: every gate
  passes except verify_set's stray MIDI CC (0, 0), which unmodified
  bottleservice fails identically on the same project.

## On the unit

- A 10-minute USB take on a busy project: `tools/hw/usb_counters.py`
  before and after, `bad`/`underruns`/`overruns` 0.
- A FLEX take of the input re-trigged every bar at 128 BPM: no bar-line click.
- An ordinary FLEX loop with slices and STRT locks behaves as stock (FLEX
  SEEK BIND acts on every same-sample re-bind).
- Kit save and FUNC + CUE reload.

## Build

```bash
make image REMIX=bottleservice-rec BUILD=1
```
