# `sos-capture` — the recorder loop fix with a test signal in and the track outputs out over USB

RECORDER LOOP FIX on [`usb-io-tracks-ab`](../usb-io-tracks-ab/README.md):
the computer plays a test signal into inputs A/B and records the sixteen
track channels, digital end to end, so a sound-on-sound loop can be captured
sample-exact on a unit and compared with the port running the same project
on the same signal.

- **RECORDER LOOP FIX**: the loop click fix,
  [`modules/recorder-loop-fix`](../../../modules/recorder-loop-fix/README.md).
- **USB MIDI**, **USB AUDIO OUT TRACKS**, **USB CROSSBAR**, **USB AUDIO IN AB**:
  as in `usb-io-tracks-ab`. SPATIALIZER is on neither menu (its words hold
  the IN module's inject).

`tools/hw/sos_capture.py` is the procedure (fixture project, signal,
capture, port run, compare, wraps); its docstring has the commands. On
macOS the terminal needs Microphone access, or CoreAudio records digital
zero with no error (`capture` stops on it).

```
make check REMIX=sos-capture
make image REMIX=sos-capture BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

On Bryan T's MKII as BUILD=94 (`f6ce41d6`) and BUILD=95 (`cd017851`), [`CHANGELOG.md`](../../../CHANGELOG.md).
