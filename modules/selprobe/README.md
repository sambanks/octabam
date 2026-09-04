# SELECT PROBE — settling the select-array formula on hardware

`docs/MAINMENU.md` §9c-ii decoded where a page-2 SELECT's value lives:

```
DB + part*6322 + 0x8f04a + track*30 + page*6 + slot
```

The **track term is confirmed** (4 Sep 2026, build 80: T3 and T4 read
different bytes at the same slot). The page and slot terms are what this
build tests. It writes nothing — it prints the byte the formula addresses.

## What the panel does, and why three builds failed

- **A knob's value is shown only while that knob turns.** A readout on GAIN
  is visible only while GAIN moves — and GAIN is also what chooses the row.
  So the bands are ten values wide: wiggle GAIN, read, stay in the band.
- **Turning another knob redraws only its own label.** A "refresh" knob
  cannot refresh anything. Build 82's RDRW is gone.
- **The byte must dominate the number.** Build 81 put it in the last digit;
  a MODE step moved a five-digit number by one.
- **The remix hides every FX2 effect with a page-2 select**, so the turnable
  selects are on FX1. This build reads both pages.

## Reading it

Registered on HELLO WORLD's GAIN. Number = `byte*100 + page*10 + slot`.

| GAIN | page | slot |
|---|---|---|
| 0–9 | FX1 (3) | 0 |
| 10–19 | FX1 | 1 — **Spectrum's MODE** |
| 20–29 | FX1 | 2 |
| 30–39 | FX1 | 3 — ROUT |
| 40–49 | FX1 | 4 |
| 50–59 | FX1 | 5 — SRC |
| 60–69 | FX2 (4) | 0 |
| … | … | ten per slot |
| 110–119 | FX2 | 5 |

Only the **odd slots are selects**; even slots are knobs in another array
and read 0 whatever you do.

## The measurement, exactly

1. Flash `OCTATRACK_OCTABAM83.bin`. Power-cycle. Load a project.
2. Pick a track with Spectrum on FX1 — T3. Put **HELLO WORLD on T3's FX2**.
3. Turn GAIN to about **15** and wiggle it between 12 and 18. While it moves
   the display shows a number. It should be **one of 31, 131, 231, 331,
   431** — FX1 MODE's row, and the number says which position MODE is in.
   Write it down.
4. On **T3's FX1** page 2, turn **MODE** up one step.
5. Back on T3's FX2, wiggle GAIN between 12 and 18 again and read.

| you see | it means |
|---|---|
| the number went **up by 100** | ✅ the formula is right, end to end |
| the same number | the page or slot term is wrong |
| a number not in the list | GAIN left the band; wiggle nearer 15 |
| `-` | no project loaded |

The probe reads the track you are viewing. A select turned on any other
track cannot move it.

## Why it only reads

A formatter runs inside a redraw, and the firmware's select editor ends in
redraw calls; a probe that invoked it would re-enter the drawing code. This
one stores nothing but the caller's sprintf buffer.

⚠️ Mutually exclusive with `modules/cfprobe`: both take HELLO WORLD's GAIN.

## Verified locally

Through the booted firmware's own formatter path with planted bytes: FX1
slot 1 holding 2 prints **231**, holding 0 prints **31**; FX2 slot 1 holding
2 prints **241**. `-` with no project.
