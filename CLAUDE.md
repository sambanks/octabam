# Working in this repository

**Read `PLAN.md` first.** It carries the end state, the resource ledger and the
work order. `docs/XBUS.md` is the architecture record, not the plan.

This is a DSP effects project. The firmware reverse engineering in `docs/` is
infrastructure that makes the effects possible — it is not the deliverable.

## Build and check

```bash
make bus        # THE build (XBUS=1 SPEC=1) -> out/mainos_bus.bin
make check      # build + cycle budget + verification, no hardware needed
make render     # hear the bus locally, ~6x real time
make reverb IN=loop.wav ARGS='--wet --mode all'
```

Never claim an effect works because it assembled. `make check` is the floor.

## Traps that have already cost real work

**The assembler mis-encodes two instructions, silently.** `dsp_asm` encodes
`tfr a,b` as `rnd b` and `mpy x0,y0` as `mpysu`. Both assemble clean and do
the wrong thing. **Disassemble what you assemble** when a result surprises
you. A related family bit us in shipping code: `cmp a,b` had encoded as
`max a,b`, which updates only the C bit while `blt` tests N^V.

**`dsp_asm` resolves labels by PREFIX, so no new label may have an existing
label as its prefix.** Adding a loop labelled `warmz2` next to the existing
`warmz` assembled to

```
do #<$40,>$13632     ; 064080 013631      (should have been 001374)
```

— `warmz`'s address `0x1363` with the leftover `2` appended. The loop branched
into hyperspace and `dsp_host` SIGSEGVed with no diagnostic. Same family as the
three above: clean assembly, wrong machine code. Found 9 Aug 2026, after three
wrong guesses (emulator memory limits, buffer alignment, a stale modulo) that
were all *reasoned about* rather than disassembled. **Disassembling first would
have cost one step instead of four** — the rule above is not advice.

**`SPEC=1` requires `XBUS=1`.** Without it the accumulators stay in core-private
memory and you get "reverb serves tracks 1-4, delay serves 5-8" — worse than
today, **and it still makes sound.** The build guards this. Do not ungate it.

**`→DELAY` and `→REVERB` are separate knobs**: `x:(r6+0)` and `x:(r6+1)`.
Driving the wrong one renders silence, which reads as a broken algorithm.

**r7 scratch slots `$10..$83` are all in use.** Only `$00..$0c` is free, and
`$84+` hangs the unit. Check before you allocate. (Do not scan for these with
`"\$$s"` in a shell — it expands.)

**A parameter slot can draw a knob and publish nothing.** The page descriptor
and the DSP-side read are separate mechanisms; `dsp_host` pokes r6 directly, so
everything looks live locally even when the real unit would publish nothing.
See `docs/PARAM_PAGES.md`.

**Flash cycles are expensive** — each one is a manual firmware write. Render
locally and measure instead of guessing. This is why the emulator path exists.

## How claims are written here

The project has been burned by stale confident numbers more than once — a
cycle budget of 1080 that was never a ceiling, a burn probe that measured an
engine we do not ship, a blocker our own bisect had already falsified.

So: **separate measured from inferred.** `docs/CHIP.md` marks every number with
a confidence marker and keeps retracted values beside current ones. Do the
same. Say what would falsify a claim. Do not write "found it" for something
you have inferred, and when a retraction lands, propagate it to every document
that repeated the old number — not just the one you were editing.

## History

The tree was pruned hard in the octabam refactor: ~350 files of ColdFire
archaeology, emulator scratch and 89 `reverbN.asm` voicing snapshots were
removed. They are all still reachable — that is why the history was carried
across rather than starting fresh.

Comments still cite probes like `dsp/baseprobe.asm` or `dsp/ymemprobe.asm` as
the provenance of a measurement. Those statements remain true; the files live
in history. Recover one with:

```bash
git log --all --oneline -- dsp/baseprobe.asm
git show <sha>:dsp/baseprobe.asm
```

Leave those citations alone. Rewriting them to remove a filename would erase
how the number was obtained, which is the opposite of the point.
