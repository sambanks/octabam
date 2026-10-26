# Slot costs: what each effect costs on a unit

`tools/remix/slot_costs.json` holds the DSP cost of one effect slot as a share
of a frame, read from the LOAD METER on a unit. `tools/remix/costs.py` merges
new measurements into it and bounds a remix against it. Measured figures are
marked as such; the bound is arithmetic over them.

```bash
python3 tools/remix/costs.py table                                  # every effect: worst slot cost, settings read
python3 tools/remix/costs.py check stock-meter-a                    # worst-case core load of a remix
python3 tools/remix/costs.py check stock-meter-a --without FILTER   # the same with effects left out
python3 tools/remix/costs.py import out/hw/matrix/<label>/report.json ...   # merge new reports
```

## How a figure is made

A matrix layout (the hardware matrix, `tools/hw/ot_matrix.py run` on the
hardware branch) puts one effect on all 8 tracks of one
slot, FX1 or FX2, so a core carries 4 instances of it. Slot cost =
(core busy - BASE core busy) / 4, both from the LOAD METER's DSP record.

- Resolution: the busy readings are to 0.1 point, so a slot figure is good to
  about 0.03.
- Core 0 and core 1 agree to 0.1 point and FX1 and FX2 agree to 0.1 point for
  every effect read so far, so the catalog keeps both cores and takes the
  dearer.
- Pair and split layouts, layouts flagged CRASH, FREEZE, OVERLOAD or DROPS, and
  the bus remix's reports (its FX2 slots hold the rig) are not read.
- A new report replaces the entries for the same (effect, slot): a later run
  is a later build of the effect. The base of a remix is the dearest one seen
  across its reports.
- Settings: `def` is the module's default settings (MIX at 0 skips MODULATION's
  processing; each other effect has MIX or a wet path on). `dear` is every knob
  at its dearest. The stock effects were read at `def` only, so a stock effect
  whose cost moves with a knob or a select is not covered.

## How a remix is bounded

A core has 4 FX1 slots and 4 FX2 slots. The worst layout fills the FX1 slots
with the dearest FX1-capable effect of the remix and the FX2 slots with the
dearest effect of the remix, each at its dearest measured setting:

    worst core = base + 4 * max(FX1 effects) + 4 * max(FX2 effects)

A remix whose worst core is at or under the limit (95 % of a frame) cannot
overload the DSP in any configuration. `check` exits 0 on PASS, 1 on OVER or
UNKNOWN. UNKNOWN means an effect has no measured cost or the remix has no
measured base (a remix without LOAD METER, such as `cxosc-core`, has none).

What the bound does not cover:

- The ColdFire's share. EUCLID adds 6.8 points to the frame-interrupt share
  and its pair with LOFI2 dropped frames at 95.8 % DSP busy
  (`HARDWARE_MATRIX.md` on the hardware branch); the `table` marks it `*`.
- The limit. 98.2 % ran clean three times, 95.8 % with EUCLID dropped frames,
  105.3 % and 112 % overloaded the unit until a power-cycle; 95 % is the limit
  chosen, not a measured edge.
- Servers (BusVerb, BusDelay, SEND): the bus remixes are not bounded.

## What it holds, 25 Oct 2026

Slot costs from `octabam-inserts` (base 22.4 / 14.9 %: image I1, and a hardware-branch build carrying the MODULATION pass, I4),
`stock-meter-a` and `stock-meter-b` (base 22.4 / 14.9 %). Free everywhere =
at or under (limit - base) / 8 on both cores, 9.07 % on core 0 and 10.0 % on
core 1.

| effect | worst slot cost | at | settings read | ColdFire over base | free everywhere |
|---|---|---|---|---|---|
| LOFI2 | 13.64 % | FX2 mode1+dear | 6 | +0.3 points | no |
| DISTORX | 9.45 % | FX2 dear | 2 | -0.0 points | no |
| MODULATION | 8.96 % | FX2 mode2 | 22 | +0.1 points | yes |
| CHARACTER | 8.90 % | FX2 mode1+dear | 12 | +0.1 points | yes |
| SPECTRUM | 7.90 % | FX2 mode2 | 16 | +0.1 points | yes |
| GATE VERB | 7.76 % | FX2 def | 2 | +0.0 points | yes |
| SHATTER | 7.46 % | FX2 mode1+dear | 6 | +0.1 points | yes |
| DJ EQ | 7.30 % | FX2 def | 2 | +0.0 points | yes |
| LO-FI | 6.66 % | FX2 def | 2 | -0.0 points | yes |
| SPRING REV | 6.38 % | FX2 def | 1 | +0.0 points | yes |
| CHORUS | 6.29 % | FX2 def | 2 | +0.1 points | yes |
| DARK REV | 5.49 % | FX2 def | 1 | -0.0 points | yes |
| TRANSIENT | 5.32 % | FX2 dear | 4 | +0.0 points | yes |
| PLATE REV | 5.27 % | FX2 def | 1 | -0.1 points | yes |
| PHASER | 5.19 % | FX1 def | 2 | +0.0 points | yes |
| FILTER | 5.11 % | FX2 def | 2 | +0.0 points | yes |
| EUCLID | 4.87 % | FX1 def | 6 | +6.8 points | yes* |
| EQUALIZER | 4.10 % | FX2 def | 2 | +0.1 points | yes |
| FLANGER | 3.15 % | FX2 def | 2 | -0.0 points | yes |
| COMB FILTER | 2.74 % | FX2 def | 2 | -0.0 points | yes |
| COMPRESSOR | 2.18 % | FX2 def | 2 | -0.0 points | yes |
| SPATIALIZER | 1.28 % | FX2 def | 2 | +0.0 points | yes |
| DELAY | 0.00 % | FX2 def | 1 | -0.0 points | yes |

`check` on `octabam-inserts`: worst core 112.9 % / 105.3 % (LOFI2 on the FX2
slots, MODULATION on the FX1 slots), OVER. Without LOFI2: 94.1 % / 86.6 %,
PASS. `stock-meter-a` and `-b`: 80.8 % / 73.3 %, PASS. The three overloading
layouts found on the unit (24 Oct 2026, `HARDWARE_MATRIX.md`) all have LOFI2
on FX2.

GATE VERB, SHATTER and DISTORX were read on a unit on 27 Oct 2026 (images `COST-A` and `COST-B`, built from
`remixes/test/cost-a` and `cost-b`; base 22.4 / 14.9 %, the same as above). GATE VERB's dearest layout (every knob at
127, a `dear` the manifest gained for this) costs the same as its default, 7.75 %. SHATTER is 3.4 % at its defaults and
7.46 % at mode1+dear. DISTORX is bypassed at its defaults (about 0 %) and 9.45 % at its dearest, over the 9.07 % that
core 0 allows, so a remix carrying it fails `check`. At every effect's dearest settings these three layouts were
flagged by the matrix for audio (GATE VERB: CLICKS STATIC LEVEL CLIP; SHATTER: ROUGH STATIC LEVEL RINGS; DISTORX:
STATIC LEVEL): RMS rose from about -35 dB to -8 to -14 dB. The static counts of `make cycles` ran 13 to 48 % under the
measured slot costs of the five effects read this way (factor 1.36 to 1.60, mean about 1.5), so estimates from them
carry that spread.

## Not in the catalog yet

No cost: MINIVERB, TAPE ECHO, DEVILISH, STUTTR, VOID,
SIDECHAIN_COMPRESSOR, MULTIBCOMP. Estimated from `make cycles` only (static
price x about 1.4, inferred): WAVE about 33 %, VOCODER about 24 %, RESONATOR
about 14 %, CHARACTER TXTR about 12 %, BBD about 12 %.
P words per effect are not in the catalog.
