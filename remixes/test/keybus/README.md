# `keybus` -- KEYBUS alone

KEYBUS with the stock effects less SPRING REV, PLATE REV and DARK REV (its 17 words go in their space): every
track's key level, the peak of |(L + R) / 2| over its 16-frame block, at X:$37F60 + track in the shared window.

- `tools/verify/verify_keybus.py` runs the tap under dsp_host on both payloads: the hook reaches it, and each
  track's word holds its block's peak, the other seven 0.
- Not flashed.

```bash
make image REMIX=test/keybus BUILD=1
```
