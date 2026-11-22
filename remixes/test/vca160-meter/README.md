# `vca160-meter` — VCA160 with LOAD METER

`stock-meter-b`'s image (the core modules, LOAD METER, the stock effects but
SPATIALIZER, whose words hold the meter's DSP half) with VCA160 on its own id
in PLATE REV's words. The image for reading VCA160's slot cost on a unit with
`tools/hw/ot_matrix.py` (`docs/contributing/HARDWARE_TESTING.md`): layouts
`VCA160 FX1/FX2 def` and `dear` against BASE, and COMPRESSOR beside it as a
check of the rig against the catalog (2.18 % a slot). Its BASE against
`stock-meter-b`'s carries the side-chain tap asleep.

`make check REMIX=test/vca160-meter`.

**Hardware:** not flashed yet.
