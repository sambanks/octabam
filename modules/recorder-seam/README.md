# recorder-seam

A ColdFire code cave, no DSP code. It changes how long a fixed-RLEN
recording is: instead of `round(RLEN × 15,876,000 / tempo24)` computed once
per pass, the length is re-derived every frame from the sequencer's own next
step event, quantised exactly the way the frame builder will place the next
trig, and substituted only when it is within one sample of the stock value.

Why: a looping recorder trig fires at `floor(event)` of an exact fractional
event, so consecutive arms are alternately `floor` and `ceil` of the period
apart while the recording is always the same integer length. Once every
1/ε passes the recording is one sample short (a hole) or long (an overlap)
at the seam — the click at 128 BPM / RLEN 4 that started the RTOS fork's
recorder work. See `docs/RTOS_FORK.md` §10.16.4–10.17.

Hook: `0x40006e0c` (the converter's last three instructions, replayed).
Reads: `0x80001904[track]` (lane table), `0x46104cf0` (lookahead),
`0x46104cf8` (dispatcher sample clock), `0x80001820` (−2³¹/tempo24),
`0x46c7fa84[track]` (arm sample). Writes: nothing but `d4`, the length.

Status: measured in route A (emulator); **flashed on Bryan's unit 7–8 Sep
2026 (tag 21) and FALSIFIED as the click fix** — 128 BPM still clicks at
RLEN 4, RLEN 16 and RLEN MAX (where this cave never runs), 120 is clean
(`docs/RTOS_FORK.md` §10.18, `docs/FLASHPLAN.md` tag 19). The length
seam it removes is real (§10.16.4–5) but is not what is heard. Kept as a
module because it is correct for what it does; not part of any remix by
default. Remaining falsifiers of the cave itself: a PER TRACK scale
pattern (is the lane index really the track?) and a recorder trig whose
next step is not its re-trig (the ±1 guard must keep RLEN).

Assemble: `m68k-elf-as -mcpu=5475 -o seam.o seam_cave.s` and pin the
`.text` bytes in `manifest.py`; the build re-assembles and compares.
