# GRANULAR with octabam-bus

This optional qualification preset adds GRANULAR to `octabam-bus`; no source
machine needs removal. The upstream standard preset is unchanged. All
settings, fixed window homes, hidden/locked FX2 hosts and FX1 rows are
preserved.

It carries BRAIN/STORE, KITS, MIDI scenes, page-2 scenes/locks and CCs,
USB tracks/MAIN/CUE, the recorder/bug fixes and core utilities. BusDelay is
T1 FX2, BusVerb T5 FX2, SEND the other FX2 slots except stock DELAY on T8.
FX1 offers SPECTRUM, CHARACTER, MODULATION and ten stock effects. The three
stock reverbs have no chooser row; BusVerb replaces their bus role.

## Local qualification

Qualified against upstream `99170b16`: the selected-module ledger is clean
and every base setting is preserved. The linked initialization/ABI gate,
actual DRAM boot, menu gate and USB enumeration/settings matrix pass.
Counted new DSP work is 2331 against 3120 usable; neither that count nor
ColdFire emulator instructions is hardware timing qualification.

The firmware subset passes 14 cases: two dry reference tracks, isolated
bus sends, isolated CHARACTER, ordinary FLEX identity, octave-up, mono24,
stereo24, pitch locks, scene endpoints, pitch LFO, mixed stock/GRAN,
two dense tracks, four ordinary tracks and four reference clouds.
All captures have zero clipped MAIN samples. Two/four reference clouds
measure 37,519/53,596 average emulator instructions per frame, with about
0.000028 relative RMS tone residual. Two dense tracks measure 42,081,
but their source ends during capture: not a sustained/peak-load bound.

The dry reference keeps both hosts and SEND with zero sends. `bus-sends`
enables only DEL/REV 50 on the hosts, requiring changed MAIN and post-FX
audio on both cores with bit-identical source streams. `effects` adds
CHARACTER DRV 32/MIX 80 on T1/T5 FX1 against **those same nonzero sends**.
Both post-FX streams change again while their sources remain bit-identical;
the comparison cannot pass merely because a send was enabled.

```bash
make bus REMIX=granular-bus
REMIX=granular-bus .venv/bin/python3 tools/verify/verify_granular.py
REMIX=granular-bus .venv/bin/python3 tools/verify/verify_dram_boot.py --existing-image
REMIX=granular-bus .venv/bin/python3 tools/verify/verify_menu.py
REMIX=granular-bus .venv/bin/python3 tools/build/cycle_count.py --verify --json
REMIX=granular-bus .venv/bin/python3 tools/verify/verify_usb.py
.venv/bin/python3 tools/verify/verify_granular_port.py granular-bus \
  --case effects --case passthrough --case pitch-up --case mono24 --case stereo24 \
  --case locks --case scenes --case lfo --case mixed --case two-dense \
  --case four-stock --case four-tracks
```

Every command above passed locally. JSON cycle mode exits zero even for
an over-budget report: compare `worst_core` with `usable`. The module
registry also runs the firmware gate in the image stage; its `--modules`
reach filter includes dependent utility gates, so it is not an exact
one-gate selector.

This is a bounded GRANULAR qualification, not every utility's full gate,
all module combinations, USB host streaming or a remote CI pass.
Four maximum-density tracks, eight-track use and arbitrary effects are
not qualified; hardware remains unqualified. Private reports/audio are
under `out/granular-bus/port-gate/`. See
[GRANULAR](../../../modules/granular/README.md) for source, control and
lifecycle limits. Standard presets remain unchanged.

GRANULAR excludes SYNTH MACHINE, OCTA303, BLACKPYRAMIDS_303, ANALOG BD and
CX OSC. New upstream FREE LOOP is not added: the base carries REC_TRIG_MUTE,
whose recorder-trig and icon sites it replaces. Removing that conflict
would still require separate FREE LOOP recording qualification.
