# `extprobe` -- EXT PROBE

A measurement instrument: how far into its FX2 slot does a stock reverb (or any buffered effect) write?
It matters because the demand loader ([`docs/contributing/DEMAND_LOADER.md`](../../docs/contributing/DEMAND_LOADER.md))
puts effect code at offset `0x1000` of a slot and trusts the figures in `tools/remix/stock.py`
(`SLOT_EXTENT`: PLATE REV `0x37ff`, DARK REV `0x3da2`, SPRING REV `0xfff`, CHORUS `0xbfd`, COMB `0xbff`,
SPATIALIZER `0xa5f`, FLANGER `0x7ff`), which were measured under the port at default settings.

It is an insert that replaces its track's audio with a status word per 16-sample frame (the layout of
[DLPROBE](../dlprobe/README.md)). It works on the words `0x34000..0x37da2`, the window view of the FX2 slot
of **T8** (core A), stopping short of LOAD METER's code at `0x37da3`. It ships in no remix but
`remixes/test/ext-probe`, which is `octabam` without the demand loader and without EQUALIZER (the probe takes its id).

GO is a select: **OFF** touches nothing; **FILL** writes a pattern over the region (128 words a frame, 1 s of
frames) and then scans it; **SCAN** counts without filling. A scan pass reads 128 words a frame (124 frames) and counts
the words that are not the pattern: in total, in each 1,024-word bucket, and the highest offset since the restart.
Setting GO to OFF and back to FILL refills and restarts the figures.

## Files

`extprobe.asm`, `decode.py`, `manifest.py`; gate `tools/verify/verify_extprobe.py` (`dsp_host`: a seeded region
reads back its exact count, highest offset and buckets; a fill leaves nothing differing).
