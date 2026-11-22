# `vca160` — VCA160 alone

VCA160 (modelled on the dbx 160) on FX1 and FX2 with an id of its own
(`0x1b` preferred, no `replaces`), beside the stock effects but PLATE REV:
its code and table run in PLATE REV's 594 words, as TRANSIENT, SHATTER and
STUTTR do; the other 13 stay, EQUALIZER and COMPRESSOR included. KEY takes
the detector from any track over the side-chain bus, so a kick on T1 can
duck a bass on T5 in two knobs.

`make check REMIX=test/vca160`. Gate: `tools/verify/verify_vca160.py`.

Worst core: 8 VCA160 (FX1 and FX2 on four tracks), priced in
`modules/vca160/README.md` ("Cost"); the code has no branch on a knob.

**Hardware:** this remix has not run on a unit. The module has, in the
author's own images, under its earlier name dB666 (module README
"On the unit").
