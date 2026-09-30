# `dsp-reset-pc` — the DSP reset probe, with its positive control

`dsp-reset` asked whether RSTOUT resets the DSP and the unit said no. This
is the same probe plus **OS SWITCH**, which makes that no worth something:
the probe can now build a listening boot ROM itself and check that it can
see one **on the machine**, not only in the emulator.

## What it adds

Before anything else, on **core 1**: OS SWITCH's park command (`$12`,
`modules/os-switch/dsp_park.asm`) turns that core's running payload into a
boot-ROM loader, and the probe sends it the same seven words. It must
answer. Notes `50` (the core took the command) and `51` (its answer, `1` =
the magic came back) carry it; then the rest of the probe runs on core 0
as before, and core 1 — parked for good — is not probed again.

First, and on the other core, for a measured reason: a probe leaves its
words unread in the host port of a core with no ROM, and a loader parked
afterwards reads *those* as its count and address. Under the port on
29 Sep 2026 it did exactly that, loaded `[7, $31000, …]` over itself,
jumped into it and answered nothing.

## What it would tell you

| notes 50, 51 | what it means for the earlier "no" |
|---|---|
| `50/1`, `51/1` | the probe **can** see a listening ROM on this machine. Every "no answer" above it is a real no, and RSTOUT is settled |
| `50/1`, `51/0` | the core took the park but never answered: the instrument cannot see a ROM on hardware, and every "no" it has reported is void |
| `50/0` | the core never took the park command — an OS SWITCH problem, not a probe result |

## Status

✅ **Ran on an MKII, 29 Sep 2026**: notes 40/1, **50/1, 51/1**, 41/3, 42/1,
43/3, 42/2, 43/3, 47/0x40 -- the parked core answered, the running payload
did not, and RSTOUT did nothing at either pulse width. The probe's negative
result is two-sided on hardware now.

`python3 tools/verify/verify_dspreset.py dsp-reset-pc` boots it twice: plain, the parked core answers with its own
magic (`0x5a3c61`) and nothing else does; with the port modelling a reset
line, core 0 answers too and both payloads are uploaded again.

`verify_boottrace` and `verify_osswitch` skip any image carrying DSP RESET
PROBE — it stops the boot on purpose (`docs/contributing/FAILURE_MODES.md`), so
a gate that asserts a normal boot cannot be run on it.

## Build and run

```bash
make check REMIX=dsp-reset-pc
make obi REMIX=dsp-reset-pc OBI=DSPRESETPC    # a switch target: no flash cycle
```

Copy to the card root, MAIN MENU > OS, and watch MIDI OUT
(`python3 tools/hw/ot_midi.py listen 60`). A power-cycle is the way out, as
with `dsp-reset`.
