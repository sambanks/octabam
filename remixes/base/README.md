# `base` — stock, whole, plus the switcher

Every stock FX2 effect, nothing given up, and **MAIN MENU > OS**. This is
the smallest change to 1.40C that can boot another image: flash it once and
every later build is a file on the card, not a flash cycle.

## What is in it

- the 14 stock FX2 effects, so the chooser is stock's, note for note;
- **OS SWITCH** — boot a `.OBI` from the card root without writing the
  flash; a power-cycle comes back here. `modules/os-switch/README.md`.

## What it costs stock

Nothing that plays. The switcher's ColdFire code lives in the OS image's
free zero runs and the DRAM platform, and its DSP park — the 39 words that
put both cores in a boot ROM before the reset — lives **entirely in stock's
dead interrupt vectors**, the slots 1.40C leaves as `jmp *`
(`docs/remixer/PLACEMENT.md`, "Pinned DSP section"). So the effect region is
untouched: `used 0`.

That is what makes this a base rather than a compromise. Harvesting an
effect is now something you do when you want words for a MODULE, not
something you do to afford the switcher.

## Status

Port-gated: `python3 tools/verify/verify_osswitch.py base` and
`verify_dspvectors`. The identical park ran on an MKII on 29 Sep 2026 inside
`bottleservice-ret` — booted, played a session with the park resident in the
vector table, and switched away — but in its two-run form this exact image
has not been on a unit yet.

## Build

```bash
make check REMIX=base
make image REMIX=base BUILD=<nn>     # flash this once
make obi REMIX=<any other> OBI=NAME  # ... then everything else is a file
```
