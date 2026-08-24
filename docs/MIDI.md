# MIDI — plan (branch `midi`, opened 24 Aug 2026)

Three things, all hanging off one question: **how does a value get from a MIDI
CC, a scene, or a MIDI note into a parameter slot the DSP reads — and does that
path reach OUR descriptors and the page-2 companion bits (8–15 of `r6+$c/$d/$e`)?**

Confidence markers as in `docs/CHIP.md`: ✅ measured / decompiled, 🟡 inferred,
⬜ not yet looked at.

## Decisions (Sam, 24 Aug 2026)

1. **Tier 1 — CC → knobs.** Page 1 (slots 0–5) is expected to work already via
   the stock FX2 map (CC 40–45 🟡, manual). Page-2 shortlist that MUST become
   reachable: **FRZE, MODE (both effects), SHMR, GATE, DRV**. DPTH/RATE/DIFF/
   PTCH/SHFT are nice-to-have.
2. **Tier 2 — crossfader.** Prefer a **published fader value** the DSP reads
   (one cave, like tempo in R56) over scene-locking companion fields: the DSP
   thresholds FREEZE itself (with hysteresis, no zipper on a 0/1 field) and the
   fader becomes a general modulation source. Scene coverage of page 2 is a
   bonus if it is free.
3. **Tier 3 — notes.** **Note → BongDelay PITCH interval** is the one to build
   first ("funnest"). Semantics: last note-on on the host track's channel,
   root MIDI 60 = unison, `interval = note − 60` clamped ±24, **HOLD** on
   note-off (last note sticks; retune by tapping). Word = 0 (never received)
   → the PTCH select behaves exactly as today.
4. Branch discipline: `midi` off `main` @ `1a1929b`; caves in `cf/`; the
   level-voicing session stays on `main` (parked, `tools/level_cap.py`).

## DSP side of tier 3 — costed, not built

The PITCH decode (`dsp/delay_server.asm` "PITCH interval select") writes one
per-block age-step word to `r7+$6a/$6b`: `step = $1000 × (rate − 1)`, so
+12 → `$1000`, +7 → `$800`, −12 → `$fff800` ✅. An arbitrary semitone `n` is
`step = $1000 × (2^(n/12) − 1)`: a 12-entry ratio table + octave shift
(`asl`/`asr` of the ratio, then subtract `$1000`), one new branch in that
decode, ~30–40 words 🟡. **Payload B FREE 87** (24 Aug build) ✅. Never
init-build the table in Y via `(r1)+` (`docs/DSP.md` §6c) — constants belong
in P or as immediates. Renderable locally by poking the note halfword from
`dsp_host` before any flash.

## ColdFire findings

⬜ Pending: `docs/midi_re_cc.md`, `docs/midi_re_scene.md`, `docs/midi_re_note.md`
(RE scouts, 24 Aug). To be merged here with markers; the scout files are then
deleted.

## Work order

⬜ Written once the findings land.
