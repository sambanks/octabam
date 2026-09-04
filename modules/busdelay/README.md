# BusDelay

A multi-mode delay — CLEAN, GRAIN (a pitched granular cloud over the delay
lines: Nimbus's grain readers, four per line, one continuous pitch) and
REVERSE — with tape-style wow/flutter (DPTH/RATE), drive (DRV, doubling as
GRAIN's scatter depth) and a FREEZE hold available in **every** mode. PITCH
mode was retired in v5 (3 Sep 2026): GRAIN's pitch is the harmoniser now. Its wet can be sent on into BusVerb over the bus (`-VRB`),
which is the series topology the stock firmware has no path for.

Hosted on payload B (core 1), which serves **tracks 1–4**.

MODE still counts five positions; the retired TAPE slot aliases CLEAN now
that the tape character is global.

TIME is a free dial with a sticky snap: near a division it snaps, holds that
division through tempo changes, and lets go when the knob moves. The panel
label comes from the [`tempo-sync`](../tempo-sync/) module's formatter cave.

## Local rendering

`dsp_host` cannot boot payload B, so this module renders only through the DEV
hatch (`make render-delay`), which places it out of region in payload A.
`DFRZAT=n` engages FREEZE after n blocks so a render can catch it mid-flight.

## The knob map since v5.1 (3 Sep 2026) — one meaning per knob per mode

Sam's redesign, done in one pass after a day of piecemeal fixes: IN is
retired (the host track's own send into the delay is its FX1 station's
→DEL, or SEND on FX1), GRAIN's pitch moves onto the scene page in its place,
and the two tape-modulation knobs are named for what they are.

| | CLEAN | GRAIN | REVERSE |
|---|---|---|---|
| **page 1** TIME · FDBK · TONE · PING · →VRB | the same everywhere | | |
| **PTCH** (page 1, was IN) | no effect | pitch, ±2 oct, 64 = unison; a held MIDI note overrides | no effect |
| MDEP | tape mod depth | **scatter** | tape mod depth |
| MODE | CLEAN | GRAIN | REVRS |
| MRAT | tape mod rate, 64 = 1× | **density** | tape mod rate |
| SIZE | unused | grain size | segment |
| DRV | drive | drive | drive |

**v6 (4 Sep 2026): MODE is page-2 slot 6 and MDEP slot 7** — swapped so
MODE sits on a slot the panel's page-2 knob editor writes, which a main-menu
bus screen needs (`docs/MAINMENU.md` §9c-ii). Locally bit-identical in every
mode. A part saved before v6 loads its old MDEP byte as MODE (48 clamps to
REVRS): re-select the effect or stamp defaults.
| FRZE | freeze | freeze | freeze |

GRAIN carries a **fixed gentle wow** (knob 12's worth at exactly 1×) that no
knob touches: the grains read the lines the repeats recirculate through, and
at MDEP 127 they used to wobble by ±254 samples ("modulating heavily"). The
per-mode label cave on the backlog will print SCAT / DENS in GRAIN. The IN
arithmetic is still in the loop, pinned to exactly zero (bit-identical to
every IN=0 render); removing it is a cycle trim.

⚠️ Old parts store IN's value in slot 5, which is PTCH now: the project
stamper (plan A6) writes fresh defaults.

## GRAIN v5 (3 Sep 2026) — Nimbus's readers over the delay lines, pitched; PITCH mode retired

The v2 GRAIN was the delay's cost centre (eight lerped heads, per-grain
rates, a rolled builder: 1,385 of 2,372 worst-path cycles). v5 is
`modules/nimbus/`'s engine over the delay lines with two things put back
that the first cut (v4, the same day) lost by Sam's ear: **four overlapping
grains per line** (two buzzed at the grain rate with scatter up) and
**pitch** — one continuous rate for all eight grains, on the RATE knob, ±2
octaves, 64 = unison. With that, PITCH mode was redundant (GRAIN at full
density, scatter 0, RATE 96 is a granular +12 on the same non-cascading
topology) and it is gone: **MODE is CLEAN / GRAIN / REVRS**, three positions.
The PTCH switch is **SIZE** (46 / 93 / 23 ms, XTRM = 186 ms grains or 12 ms
REVERSE segments — REVERSE's own order, one select for both modes).

Knobs in GRAIN (v5.1 names): TIME = position, SIZE = grain length, PTCH =
pitch (page 1), MDEP = scatter (up to 4,095 samples), MRAT = density (R61 law
and makeup), DRV = drive, FREEZE holds the lines and the grains keep grazing
them. A held MIDI note (the tempo cave's `r6+$9`, latched) replaces PTCH with
2^((note−84)/12), ±24 semitones — the same law the retired mode drove.

**Cost:** delay 2,469 → **2,151 words** (payload B FREE 5 → **323**); worst
path 2,372 → **1,757 cycles** (GRAIN, rolled: 345 words + 718 of roll).

**Two defects found on the way, both measured:**

- **The grain read geometry played an octave up at "unity".** Nimbus's
  `W − (base + s + G − phase)` moves with the write head AND the phase, so
  the absolute read advances two samples per sample. Measured: 955 Hz out for
  438 in, and 3× at +12. Invisible to the DC gate (rate has no DC signature).
  Fixed with a `+ phase` term (unity = a fixed tap behind the head) and
  per-sample distance clamps to `[2, 16383]`. The standalone Nimbus very
  likely carries it — noted in its README, unverified there.
- **The latched MIDI note slot is boot garbage in `dsp_host`**, so every
  local GRAIN render ran its pitch from a garbage note until the RATE knob
  visibly did nothing. The warm-up now clears `y:>$090a` (the build's
  core-private census went 2 → 3 for a source with the clear).

Measured (`make render-delay` hatch, 438 Hz tone, 93 ms grains, TIME 127):

| PTCH | measured | expected | note | measured | expected |
|---|---|---|---|---|---|
| 64 | 438.7 | 438 | 84 | = PTCH 64, bit-identical | |
| 96 | 869.4 | 876 | 96 | 869.4 | 876 |
| 32 | 223.4 | 219 | 91 | 654.1 | 656 |
| 48 | 309.5 | 310 | 72 | 223.4 | 219 |
| 127 | 1709 | 1714 | 60 | 94 | 110 (see below) |

Peaks are read off a comb at the grain rate (10.8 Hz at 93 ms), so ±1 line
is the finder, not the engine. Below about −1.5 octaves the finder reads
10–25 % low on both paths (RATE 16 → 137 for 155, note 60 → 94 for 110):
**unverified** whether that is the engine or the measurement; a longer FFT
on a lower tone would settle it. The pitch ceiling behaves as derived:
186 ms grains at TIME 100 clamp RATE 127 to 2.5× (1106 Hz measured).

- **DC gate** (0.25 FS DC, full density, unison): p-p 0 across scatter 0/64/127
  and every size — four windows a quarter period apart sum to exactly 2.
- **Bit-identity vs v3:** CLEAN in every case (defaults, PING 0/127, TIME
  0/127, FDBK+TONE, split, MIX 0), REVERSE at both sizes, CLEAN with wow at
  DPTH 100 and 127/FDBK 127, and the unknown-mode fallback — all identical
  (`verify_delay` for CLEAN; REVERSE/wow by hand with the mode numbers mapped).
- **Density law** (0.5 FS tone, DRV 64, 93 ms): −14.6 / −11.2 / −10.7 /
  −11.3 / −12.0 dBFS at DPTH 0/32/64/96/127 — flat within 1.3 dB from 32 up,
  sparse end 3.9 dB down. Peaks touch 0.86 FS at DPTH 32 (the +6 dB makeup
  on a lone grain).
- **Level vs v3** on real material at matched settings: v5 is ~6 dB quieter
  (four decorrelated grains sum less coherently than their DC normalisation;
  the `_lm` copies in `out/ab/grain_v4/` are level-matched). A voicing item.

⬜ **Ear pass pending** (Sam): `out/ab/grain_v4/{glow_intro,guitar_dry}_v3.wav`
vs `_v5_r64_lm.wav` (unison) and `_v5_r96_lm.wav` (+12).

## Open

- GRAIN v5's ear pass and the level offset (a makeup decision).
- Pitch accuracy below −1.5 octaves: finder or engine, unverified.
- The delay return is ~4 dB quieter than the reverb at equal send.
