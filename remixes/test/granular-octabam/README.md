# GRANULAR with standard octabam

This optional qualification preset derives from `octabam`, replacing the
mutually exclusive OCTA303 source module with GRANULAR. The upstream standard
preset is unchanged. Every other selection, USB setting, demand-loader home,
reverb guard and FX1 chooser is preserved.

It includes BRAIN/STORE, KITS, MIDI scenes, page-2 scenes/locks and CCs,
USB tracks/MAIN/CUE, the recorder/bug fixes and standard utility modules.
Stock effects remain, with MODULATION, SPECTRUM, CHARACTER, TRANSIENT and the
sidechain compressor loaded on demand as in the base.

## Local qualification

Qualified against upstream `99170b16`: the selected-module ledger is clean
and the base's settings are unchanged. The linked initialization/ABI gate,
actual DRAM boot, menu gate and USB enumeration/settings matrix pass.
Counted new DSP work is 2384 against 3120 usable; neither that count nor
ColdFire emulator instructions is hardware timing qualification.

Newer upstream `b5da2db2` was fetched but is **not integrated or qualified
here**. It adds CX OSC to standard octabam, pinned to DRAM. CX OSC still
shares GRANULAR's renderer/page hooks: adapting this preset to that base
requires removing CX OSC as well as OCTA303, not blindly reusing this
selection. The tested local base remains `99170b16`.

The firmware subset passes 14 cases: two reference tracks, stock-FX2
baseline, isolated FX1, ordinary FLEX identity, octave-up, mono24,
stereo24, pitch locks, scene endpoints, pitch LFO, mixed stock/GRAN,
two dense tracks, four ordinary tracks and four reference clouds.
All captures have zero clipped MAIN samples. Two/four reference clouds
measure 38,461/54,590 average emulator instructions per frame, with about
0.000028 relative RMS tone residual. Two dense tracks measure 43,022,
but their source ends during capture: not a sustained/peak-load bound.

The FX1 fixture uses MODULATION plus stock DELAY on T1 and SPECTRUM plus
DARK REV on T5. It compares against **the same FX2 settings with FX1 NONE**,
not a dry chain that stock reverb alone could change. Both source streams
remain bit-identical and both post-FX streams change. Both demand kernels
have checksum-published entries and their complete built code on both
cores; each reports three copies published and none refused. The stock
DELAY baseline need not change T1 readback within this short capture.

```bash
make bus REMIX=granular-octabam
REMIX=granular-octabam .venv/bin/python3 tools/verify/verify_granular.py
REMIX=granular-octabam .venv/bin/python3 tools/verify/verify_dram_boot.py --existing-image
REMIX=granular-octabam .venv/bin/python3 tools/verify/verify_menu.py
REMIX=granular-octabam .venv/bin/python3 tools/build/cycle_count.py --verify --json
REMIX=granular-octabam .venv/bin/python3 tools/verify/verify_usb.py
.venv/bin/python3 tools/verify/verify_granular_port.py granular-octabam \
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
under `out/granular-octabam/port-gate/`. See
[GRANULAR](../../../modules/granular/README.md) for source, control and
lifecycle limits. Standard presets remain unchanged.

GRANULAR excludes SYNTH MACHINE, OCTA303, BLACKPYRAMIDS_303, ANALOG BD and
CX OSC because they share source hooks. New upstream FREE LOOP is not added:
the standard preset includes REC_TRIG_MUTE, MORPH and REC THRESHOLD, which
FREE LOOP explicitly conflicts with. Pairwise GRANULAR/FREE LOOP compatibility
does not resolve those bundle conflicts.
