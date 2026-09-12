# recorder-spacing

A ColdFire code cave, no DSP code. It makes a fixed-RLEN recording exactly
as long as the gap to the next arm — derived from the **current** arm, with
no lane lookahead, no prediction and no stored state.

Why: the length converter returns one constant length for a whole loop
(82,687 at 128 BPM / RLEN 16) while the sequencer arms at `floor(k × period)`
of an exact fractional period, so consecutive arms are alternately 82,687 and
82,688 samples apart. Where they disagree the buffer's wrap splices two input
moments two samples apart instead of one, and OCTABAM82's free-running read
head walks through it — the −26 dB, ~1 ms scuff on alternate bars measured on
Sam's unit and confirmed by the tempo test. See
`docs/firmware/RTOS_FORK.md` §10.53 and §10.56.

Not the same as `recorder-seam`, which asks the lane for the next event and
is **falsified** (§10.55: on a one-trig-per-bar lane the event resolves to the
past, its `L'` comes out 0 and its guard refuses every call). This cave never
asks:

    q, r = divmod(RLEN × 15,876,000, tempo24)
    k    = arm / q                                 arm = 0x46c7fa84[track]
    L'   = q + floor((k+1)r/D) − floor(k·r/D)

with RLEN recovered from the stock length so nothing has to be kept between
passes.

Hook: `0x40006e0c` (the converter's last three instructions, replayed).
Reads: `0x80001814` (tempo24), `0x46c7fa84[track]`, `164(%sp)` (the track).
Writes: nothing but `d4`, the length.

Status: **UNFLASHED, and not yet measured on hardware or under the port.**
What is established:
- `L'` equals the sequencer's own next spacing on **115,200** (tempo, RLEN,
  pass) triples — 12 tempi × 8 RLENs × 1,200 consecutive passes — both as the
  model (`out/hw/softretrig/lever_e.py`) and as an instruction-accurate
  simulation of this cave's assembled bytes.
- Over all **11,208** (tempo, RLEN) pairs in 60.0–200.0: at every tempo whose
  period is an integer `q` equals the stock length, so the cave writes back
  the value already there and the golden case cannot regress; and
  `|L' − L| ≤ 1` everywhere, so the ±1 guard is kept as a safety net.
- The route to the reader is measured: the bind copies the voice's data-END
  bound from the write-position table at `0x4000f89e`, and that still runs
  under 82's caves (§10.56).

Owed before a flash: the port gate — the substitute path must be taken with
`L'` alternating 82,687/82,688 on `n128_card` (the same site scored 0/1,200
for `recorder-seam`), and the golden card must come out byte-identical to
stock. Then the self-loop hardware take at 128 with `gaps.py` and the per-bar
maximum, 65.6 as the control.

⚠️ objdump prints every `divu.l` in the source as `remul` — 0x4c4x is one
encoding family and GNU names it after the remainder form. With the extension
word's Dq and Dr fields equal, ColdFire writes the quotient. Do not "fix" it;
the long note in `spacing_cave.s` has the references.

Assemble: `m68k-elf-as -mcpu=5475 -o spacing.o spacing_cave.s` and pin the
`.text` bytes in `manifest.py`; the build re-assembles and compares.
