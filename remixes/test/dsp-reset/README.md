# `dsp-reset` — does RSTOUT reset the DSP?

One probe and the stock effects. For one question: whether the ColdFire can
reset the DSP in hardware, which would let OS SWITCH drop the 40 words of
park code it needs in both payloads (and with them the reason
`bottleservice-ret`'s stage-B builds can only be switched *into*).

## What is in it

- **DSP RESET PROBE** — at boot, after the DSP upload: a control probe with
  no pulse, then RSTOUT (RCR bit 6) pulsed two ways, then the boot ROM's own
  protocol asked whether either core is listening. The result goes out on
  MIDI OUT. `modules/dsp-reset-probe/README.md` is the procedure and how to
  read it.
- all 14 stock FX2 effects: the probe places no DSP words, so the chooser
  is stock's entire list and nothing is given up.

Nothing else, and `os_switch=False`: the question is the DSP's reset line,
and every variable that is not that one is left at stock. The image is still
a switch **target** — a target needs no OS SWITCH of its own — so trying it
costs no flash cycle.

## Status

Port-gated, never run on a unit. `python3 tools/verify/verify_dspreset.py
dsp-reset` boots it twice and shows the probe reporting **no** reset on the
plain port and **both cores in their boot ROM** when the port models a reset
line on that register bit — the instrument answers either way, and the boot
reaches the RTOS handoff in both. The candidate itself is unmeasured: only
the unit can answer it.

## Build and run

```bash
make check REMIX=dsp-reset                  # every gate, no hardware
make obi REMIX=dsp-reset OBI=DSPRESET       # -> out/DSPRESET.OBI: a switch target, no flash
```

Copy the `.OBI` to the card root, boot it from a flashed image with MAIN MENU
> OS, and watch MIDI OUT (`python3 tools/hw/ot_midi.py listen 60`). A
power-cycle comes back to the flashed image whatever happens — and after a
"no" it is also how the unit gets its audio back (the module's README says
why).
