# Analog BD

One native Octatrack track machine with **808 / 909** selection in its
sample-pool-style engine browser. Both original fixed-point synthesis engines run on
the DSP, upstream of stock AMP and both track FX slots. No recordings are
embedded. Earlier image ANALOGBD1 was auditioned on an MK1; the current
engine browser and eight-track changes: cursory testing on Sam's MKII
(owner report, 16 Oct 2026).

| Model / page | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| 808 SRC | PITCH | DECAY | TONE | ATK | SWEEP | SAT |
| 909 SRC | PITCH | DECAY | TUNE | ATK | TDEP | SAT |
| Both SRC SETUP | — | ACCNT | LPF | LOW | HIGH | — |

Both models use the same Mackie desk stage and output LPF. SAT controls
drive; LOW/HIGH are neutral at 64. LPF is OFF at 0, 500 Hz at 1, **ORIG**
(~6.57 kHz) at 64, and **18 kHz at the new-assignment default of 127**.
Stored patches retain their bytes, including when changing engines. Volume
remains on stock AMP. Old patches with both desk bands at zero need them
raised to hear the source.

Both models have a fixed +12.04 dB output boost after the desk, before stock
AMP and FX. The 808's balancing trim is now 0.86 of its original output;
the 909 multiplies its original output by four. With the shared assignment
defaults, peaks are −7.31/−1.59 dBFS and 500 ms RMS is −20.19/−20.21 dBFS
for 808/909. Their first-100-ms RMS differs by 0.24 dB. Existing patches
also become louder. Oscillator, envelope, filter and saturation states are
unchanged; boosted 909 samples above full scale are limited at the source
output. Stock AMP still controls track volume.

The 808 is calibrated against the user's 32 clean `_Orig.wav` recordings;
Tape/TapeSat, X/X2 and unlabeled special effects are excluded. Its body
starts near 49 Hz, with a falling pitch envelope and approximately
16–340 ms exponential decay times. ATK sets the transient, TONE shapes it,
and SWEEP controls the pitch excursion. See [DSP808.md](DSP808.md) for the
model, measurements and limits.

The user-approved 909 is calibrated against Drumazon 2 Init. PITCH maps
30–100 Hz, TUNE sets pitch-envelope duration, and TDEP sets its amount.
ATK controls the shaped pulse/noise transient. The release spans about
9–454 ms after an approximately 60 ms initial body stage. See
[DSP909.md](DSP909.md). The comparison patch is PITCH 64, DECAY 32,
TUNE 64, ATK 32, TDEP 64, SAT 0, ACCNT 100, LPF OFF, LOW/HIGH 64.
Selecting a model keeps the existing knobs rather than loading a preset.

## Native integration

The chooser and Part storage follow the measured Machinedrum registration
seams. Parts store FLEX plus `AB\x01` in unused NEIGHBOR page bytes. All eight
tracks can store and run independent patches; the two-instance admission
ceiling has been removed. Stock Part save/copy/reload carries the twelve bytes.
The engine id remains stored internally; its former page-2 control is hidden
and its encoder is ignored. Double-tapping an
Analog BD track opens a sample-pool-style engine browser with 808 and 909
rows. UP/DOWN or LEVEL browses, YES selects, and NO cancels. LEFT returns
to the machine chooser; RIGHT on ANALOG BD opens the engine pool. Both
headers use the stock sample-pool chevrons to show the direction. Ordinary
tracks keep the stock sample picker.

ColdFire sends control records through the existing source transport; DSP
glue recognizes the signature and renders either engine into the stock
source audio block. Other FLEX tracks call their unmodified renderer. Each
model retains separate state. Both payloads use the already harvested
SPRING REV code region and private X tables/state. Both track FX slots are
available; SPRING REV is excluded from this standalone remix. Its shared
35-word DARK reverb routine is preserved, with stock/patched audio identity
checked on both cores. The optimized kick engines are also held to exact
pre-optimization internal-state hashes. Both models' audio is checked against
the original with exact fixed-point output scaling and limiting.
MACHINEDRUM, SYNTH MACHINE and POLY still conflict with the registration
seams and require a shared registry before composition. OCTA303 shares an
image through [HOOKS](../hooks/README.md) (`machine_rows`, 28 Oct 2026),
and so does CX OSC (31 Oct 2026): ANALOG BD keeps row 5 and every hook, and,
built with `HK_MACHINE_ROWS`, hands each row not its own to the next
machine's routine (`MC_NEXT_*`); OCTA-303 and CX OSC take rows 6 and 7 of a
list that scrolls. Its renderer is the last of the FLEX kind entry's chain.
Its own bytes alone are unchanged.

Current load evidence and remaining hardware qualification are in [CPU.md](CPU.md).
Generic DSP pressure acceptance is explicitly blocked until the pricer supports
source engines; the standalone and full-chain benchmarks remain required.

## Reproduce

```
python3 modules/analog-bassdrum/generate.py --check
python3 tools/harness/bd808.py --wav
python3 tools/harness/bd909.py --wav
OT_PROJECT=<stock-project> make check REMIX=analog-bassdrum
OT_PROJECT=<stock-project> AB_SAMPLE808=1 python3 tools/verify/verify_analog_bassdrum_port.py
```

Repeat the port checks with `AB_REVERSE=1` for the opposite core assignment.
WAVs, firmware and reference analysis remain under `out/`, never in commits.
The retired ColdFire synthesis, its coefficient tables and audio gates
have been removed. ColdFire retains only control transport and UI helpers. [CPU.md](CPU.md),
[SCHEMATIC.md](SCHEMATIC.md) and [REFERENCE.md](REFERENCE.md) retain the earlier
ColdFire research, not the current DSP algorithm specification.

## Hardware report and compatibility

mathgonzlez reported on 28 September 2026 that ANALOGBD1 worked on an MK1:
all parameters worked, with no glitches or unexpected sounds while tweaking.
They also noted labels close to the edge of the parameter area. The tested
flash file SHA256 is
`3672634dedb8ce0138d7cf4216bd051a47afac6601dcd2a3c1830def24f39704`.
This report does not specify a save/reload test, eight voices, or every effect
combination; it predates this review revision.

Loading an AB project in pristine 1.40C succeeds under the port, but stock
sees FLEX and clamps the setup controls to FLEX ranges. In the measured
fixture, ACCNT/LPF/LOW/HIGH become 1/1/1/3; the AB signature remains. Saving
that project on stock can therefore overwrite the synth settings. Keep a
separate project copy for stock or remixes without ANALOG BD. No claim of
transparent backward compatibility is made.

Eight voices are selectable, but effects still share each core's budget.
All eight 808s, all eight 909s and mixed models passed FILTER + DARK locally.
Eight 909s with DJ EQ in both slots failed with silent output. See [CPU.md](CPU.md)
for the measured envelope; eight voices does not guarantee every FX combination.
