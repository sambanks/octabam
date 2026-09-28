# `bottleservice-rec-plen` -- bottleservice-rec plus RLEN PLEN

[`bottleservice-rec`](../bottleservice-rec/README.md) plus
[RLEN PLEN](../../modules/rlen-plen/README.md): RLEN value PLEN, past MAX,
records exactly one loop of the track's pattern on the track's own scale
(up to 64 steps at 1/8X = 32 bars), so TRIG ONE + QREC PLEN records the next
pass on one press and stops.

RLEN PLEN is a DRAM unit here (a floating ROM cave until 28 Sep 2026; the
ROM has no 298 B left beside the rig). The build holds the unit to the
ratified cave bytes (position-independent, re-linked alone and compared by
sha256).

RECORDER HOLD is not in it: 328 B of ROM the rig does not have, and it has
not been seen to work on a unit (`docs/firmware/RECORDER_CLICK.md`).

## Where it has run

Not flashed. Flash `bottleservice-rec` first.

## On the unit

- RLEN = PLEN at 1/4X and at 1/8X: one take is exactly one pattern loop.
- PLEN survives a Kit save, a load of another Kit and a FUNC + CUE reload,
  with no fatal (Octakit wraps the recording-setup editor).

## Build

```bash
make image REMIX=bottleservice-rec-plen BUILD=2
```
