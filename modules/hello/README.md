# HELLO WORLD

A linear volume knob, and the reference minimal insert: the smallest complete
module the contract can express — one page-1 knob, 27 words of DSP, no state.
It exists to be read (the worked example `modules/_template` points at) and to
stay permanently buildable as a canary: if this stops building or stops
nulling at GAIN=127, the build system moved under everyone.

Contributed by **Bryan T**, 2 Sep 2026, to fill the gap the module docs left:
`_template` had a manifest skeleton and no engine, and the smallest shipping
insert was ~300 lines.

## Status

**Hardware-confirmed by its author** (2 Sep 2026, OS 1.40C base, Bryan T's
unit — not Sam's): GAIN=64 measures −6 dB against GAIN=127; GAIN=127 is
level-identical to SEND (the de facto NONE in this remix) on the same source;
sequencer and project load normal, including a pre-existing project saved
under stock.

One anomaly on record, **not reproduced**: the first flash of this image
froze the sequencer ~2 steps after play (the classic DSP-stall signature).
A reflash of the byte-identical image ran clean — same unit, same project.
Suspected bad flash; unproven. If it recurs, note that this is the first
remix ever flashed with NO bus server (SEND housekeeps alone), and check
that layout before blaming the 27 words.

**Measured here** (`tools/verify_hello.py`, dsp_host, payload A, entries
resolved from the dispatch tables of the built image; input a full-scale
bipolar ramp), reproducing the author's numbers exactly:

- GAIN=127 is a **bit-exact** passthrough — the early-out returns before any
  arithmetic, and inserts process in place, so unity is "touch nothing".
- GAIN=0 is exact silence.
- GAIN 32/64/96/126: every output sample is exactly `(in × GAIN<<16) >> 23`,
  0 LSB error, negative half included — which also confirms behaviourally
  (not just by disassembly) that the one `mpy` encodes signed. A silent
  `mpysu` here would corrupt exactly the negative half; it doesn't.
- L and R identical for identical input.

**Disassembled** (2 Sep 2026, out of the built image at `P:0x10d8`, not out
of the source): the compare encodes `cmp x0,a` and not `max a,b`, and both
multiplies encode `mpy x0,y1,a` and not `mpysu` — the two mis-encodings that
would each leave this file assembling clean and doing the wrong thing.

**Inferred**: nothing load-bearing remains inferred. The mpy-scaling question
(plain product vs an extra `asl`) was settled by the gain-law gate — the
factor-2 alternative misses by ~2²¹ LSB.

Remaining unchecked by ear: GAIN=0 silence (verified exact in the emulator).

The original falsification protocol, kept for re-runs: flash `hello`, put
HELLO WORLD on any track's FX2, play a source. GAIN=127 must be
indistinguishable from NONE; GAIN=64 must be −6 dB; the knob must be silent
at 0 and clickless in between (the coefficient updates per block, ~0.34 ms —
a full-throw sweep may zipper slightly, which a taper/slew is the eventual
answer to, not a bug in v1).

## Parameters

| slot | name | what it does |
|---|---|---|
| 0 | GAIN | linear level, out = in × GAIN/128; 127 = exact passthrough, 0 = silence. Default 127. |

The 126→127 step is 0.984→1.0 (~0.14 dB): the price of a bit-exact top.

## Running the gates

```bash
make check REMIX=hello
python3 tools/remix/audition.py hello out/dry/drums_110.wav GAIN=64
python3 tools/verify_hello.py            # expects ALL GATES PASSED, 0 LSB
```

The audition builds the scratch image the gates measure, so it comes first.

⚠️ `verify_hello.py` derives the fx2 id and the GAIN slot from this manifest
and refuses to run if they resolve to SEND's entry points. That is not
defensive decoration. As contributed it hardcoded `FXID = 0x17`; hello moved
to `0x1b` on integration (0x17 became Rungs's on 2 Sep), and the tool then
measured **the send client** for all six gains — and its `GAIN=127 bit-exact
passthrough` gate PASSED, because a dry passthrough is exactly what unity
gain looks like. Only the gain-law gates dissented. Same family as the 12 Aug
2026 "BusDelay outputs nothing" session: an id an image does not implement
aliases to the fallback and renders plausible, wrong audio.

## The 5-char abbr crash (found on hardware by Bryan T, 2 Sep 2026)

The first cut used `abbr=b"HELLO"` — 5 characters. The descriptor's abbr field
is **5 bytes, NUL-terminated** (`docs/PARAM_PAGES.md` §2), i.e. 4 characters
plus a terminator. "HELLO" filled all 5 bytes with no NUL. Manual knob use
never showed anything wrong, but **LFO-modulating a parameter** threw a
line-F exception (VEC:0B) whose faulting address was `0x48454C4C` — "HELL".

It presented as "custom effects can't be modulated," and looked at first like
a bug in the descriptor-clone mechanism. It is not. Confirmed on hardware by
modulating WarpFold and BodeShift (no crash) against hello (crash), then
fixed by shortening the abbr to 4 chars.

**The rule is measured; the mechanism is partly inferred.** What is measured:
all 30 of the firmware's own page descriptors carry an abbr of 4 characters
or fewer with byte 5 zero (audited across the pristine image, 2 Sep 2026),
every shipping module already did, and hello at 5 was the sole crash.

What is inferred: the author's account is that a C-string read ran past the
field into `fullname`. That alone does not explain the *faulting PC*, which
is the field's own ASCII — an overrunning read yields a wrong string, not a
jump. A PC made of the copied bytes is the signature of a **smashed return
address**: something copies the abbreviation into a fixed 5-byte destination
and the extra characters land past it. The copy has not been located in the
disassembly. Falsifier: a 5-char abbr whose overrun stays printable and does
not fault. Either way the remedy is the same, and it is now a build refusal
rather than a convention — `schema.MenuEntry` rejects an abbr over 4
characters and a fullname over 12, and `build_bus.py` re-checks the string it
actually writes, tag included.

## Open

- **Taper select** (page-2 slot 7, LIN/LOG/…): planned, not started. The
  stepped-control budget puts it on 7, 9 or 11 only.
- **FX1 availability**: the module contract is FX2-only. `tools/build_fx1.py`
  proved the FX1 chooser can be extended (relocated to a cave — it cannot
  grow in place), but that machinery is not in the manifest schema. A
  bufferless insert has neither of the reasons DELAY/reverbs can't be FX1,
  so this is schema work, not a hardware wall.
- **Per-block coefficient step**: no slew. Fine for a gain; a future taper
  pass could add one if knob sweeps zipper audibly on hardware.
- **`dsp_host -dispatch` (faithful mode) is broken, and it is TWO faults,
  not one.** Reported with the module as "wedges with wild memory reads on
  any image, on two machines"; reproduced here 2 Sep 2026 and taken apart.

  **Measured:** block 0 always completes; block 1 never does. The process
  sits at **0% CPU**, sleeping — it is not a runaway. A stack sample puts
  it inside `HDI08::writeTX` → `ConditionVariable::wait`: faithful mode runs
  the firmware's own host writes, the emulator's TX ring is 8192 words and
  **blocking**, and dsp_host models no ColdFire to read them, so once the
  ring fills `movep a,x:<<M_HTX` parks forever. It is not the image and not
  the DSP code — the 400,000-step ceiling cannot catch it, because the
  process is stuck inside a single instruction. Draining the ring between
  instructions does **not** fix it: the writes happen inside a hardware DO
  loop that the emulator runs to completion in one `execInterpreter()` call,
  so the harness never gets a turn.

  `setTransmitDataAlwaysEmpty(false)` (now set, scoped to dispatch mode
  only — every other path is byte-for-byte unaffected, `make check` and the
  gates above confirm) makes the write overwrite and return instead of
  waiting. The wedge is gone. **Faithful mode then SIGSEGVs on block 1**,
  `KERN_INVALID_ADDRESS`, which is the "wild memory reads" half of the
  original report — a second, separate defect the hang had been masking.

  **FALSIFIED, 2 Sep 2026 — it is not the register file.** The standing
  guess was that each block inherits block 0's registers, because the
  dispatcher is entered per audio interrupt on hardware while we break at
  `0x53e` and force the PC back, leaving every AGU modifier, loop register
  and stack word live. Restoring the **entire** `SRegs` struct to its
  post-init state before each block changes nothing: still SIGSEGV on block
  1, at 1 track and at 4. The experiment was reverted rather than left in —
  it bought no behaviour and would have read as a fix.

  So the state that kills block 1 is in **memory**, not registers: the
  dispatcher mutates `x:0x20a`, `x:0x213`, `x:0x418`, `x:0x420` and the
  pending/current track blocks, and one of those does not survive being
  re-entered. Next falsifier for whoever picks this up: snapshot and restore
  X/Y alongside the registers; if block 1 then survives, bisect the restored
  range to name the word. Until then faithful mode is unusable — which
  matters, because it is the only thing that would validate the hand-rolled
  calling convention the rest of the harness assumes.
