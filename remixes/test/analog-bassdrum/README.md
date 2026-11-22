# Analog Bassdrum development remix

Adds one native track machine with a switchable 808/909 bass drum engine.
Includes the stock track effects except SPRING REV, whose code region
holds both DSP engines. SAT is on SRC F; LOW and HIGH are on SETUP D/E (64 flat). Based on the Machinedrum branch's machine
registration research, with its own `AB` signature and source renderer.

Build: `make check REMIX=analog-bassdrum`.
Standalone DSP auditions: `python3 tools/harness/bd808.py --wav` and
`python3 tools/harness/bd909.py --wav`. Both share the Mackie stage and LPF;
new assignments default to 18 kHz.

Earlier ANALOGBD1 was auditioned on an MK1 by mathgonzlez:
all parameters worked, with no glitches while tweaking. The current browser
and eight-track revision has not been flashed. See [the module](../../../modules/analog-bassdrum/README.md) for
controls, integration limits and the authenticity qualification still open.
