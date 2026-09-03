# BongDelay

A multi-mode delay — CLEAN, PITCH (a once-per-repeat harmoniser), GRAIN (a
granular cloud: since v4, Nimbus's unity-rate grain readers over the delay
lines) and REVERSE — with tape-style wow/flutter (DPTH/RATE), drive (DRV,
doubling as GRAIN's scatter depth) and a FREEZE hold available in **every**
mode. Its wet can be sent on into ChonVerb over the bus (`-VRB`),
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

## GRAIN v4 (3 Sep 2026) — Nimbus's readers over the delay lines

The v2 GRAIN was the delay's cost centre: eight lerped heads with per-grain
rate accumulators and a rolled builder, priced at 1,385 cycles and the worst
path of the whole engine. v4 is `modules/nimbus/`'s engine instead: four
unity-rate grains, two per line at a half-period offset so each line's two
triangle windows sum to exactly 1, integer reads, one multiply per window,
a latch at each grain's own wrap. The delay's worst path is now PITCH's:
**2,372 → 1,255 cycles** (`make cycles`), and the module shrank 2,469 → 2,308
words (payload B FREE 5 → 166).

Knobs in GRAIN: TIME = position (read-back distance), PTCH = grain SIZE
(23 / 46 / 93 / 186 ms — the select REVERSE already reads as a size), DRV =
scatter depth (up to 4,095 samples), DPTH = density (the R61 full-dial law and
makeup, kept verbatim), FREEZE holds the lines and the grains keep grazing
them. ⚠️ The PTCH select still prints its PITCH-mode words (`+12 +7 -12 det`);
per-mode labels are a rig backlog item.

**What v4 gives up: the pitched grains.** Every grain plays at unity, so the
+12 / −19 / −12 / +5 / −5 / +7 set is gone. The planned v4.1 puts a
continuous grain PITCH on the RATE knob (free in GRAIN, since wow depth is
density there): one rate for all four grains, Clouds-style, ~+100 cycles.

Measured (local, `make render-delay` hatch):

- **DC gate** — 0.25 FS DC through GRAIN at full density: −124 dB ripple in
  the steady window, with scatter 0 and 64 and at the 186 ms grain. The two
  windows per line sum to exactly 1, so the a0 multiplier is right (the trap
  Nimbus found — see its header).
- **Bit-identity** — CLEAN, PITCH, TAPE, REVERSE and the unknown-mode fallback
  render bit-identical to v3 (`tools/verify_delay.py` against the v3 source);
  only the three GRAIN cases differ, by design.
- **Density law** — 0.5 FS tone, DPTH 0/32/64/96/127: −12.3 / −8.7 / −7.8 /
  −8.0 / −8.8 dBFS. Flat within ~1 dB from 32 up; the sparse end is 3.5 dB
  down (two grains per line now, so sparse is more silence). Peaks reach
  1.0 FS at the sparse end on that tone: the +6 dB makeup headroom v3 had.
- **Level vs v3** — at matched settings (DPTH 64, DRV 64, PTCH 1, FDBK 40)
  v4 is 3.3–3.6 dB quieter on real material (`out/ab/grain_v4/`; the `_lm`
  copies are v4 raised by 3.45 dB for a level-matched A/B). A voicing item:
  the makeup law can absorb it once the ear pass says the texture is right.

⬜ **Ear pass pending** (Sam): `out/ab/grain_v4/{glow_intro,guitar_dry}_{v3,v4_lm}.wav`.

## Open

- GRAIN v4's ear pass, the −3.4 dB level offset, and v4.1 (PITCH on RATE).
- The delay return is ~4 dB quieter than the reverb at equal send.
