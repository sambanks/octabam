# DSP56300

SLEIGH specification for the Motorola/Freescale DSP56300 family of 24-bit
digital signal processors (DSP56301/303/309/311/321/362/364/367/371/372/374,
the Symphony DSP5672x parts, ...).

## Model

* **Memory.** Three word-addressed spaces, `P` (program, the default space),
  `X` and `Y` (data), each `size=3 wordsize=3`: one address is one 24-bit word.
  Words are stored little-endian, three bytes per word, which is how DSP boot
  streams and most dumps lay them out.
* **Registers.** `x`/`y` = `x1:x0`/`y1:y0`; the 56-bit accumulators `a`/`b`
  (`a2:a1:a0`) are 7-byte registers with `a0`, `a1`, `a2` and `a10` aliased
  onto them. Condition codes are separate one-byte registers (`C V Z N U E L S`);
  `sr` holds the mode bits.
* **Parallel moves.** An instruction's ALU operation and its one or two data
  moves read all of their sources before any destination is written, as the
  hardware does: `mac x0,y0,a x:(r0)+,x0` multiplies the *old* x0, and
  `mac x0,y0,a a,x:(r0)+` stores the *old* a.
* **Hardware loops.** `DO`/`DOR` attach context to the loop's last word; the
  root table adds the loop-back there, so the decompiler sees an ordinary loop.
  `LA`/`LC` are saved on the hardware system stack, modelled as the `SS` space
  addressed by the internal register `ssp` (the compiler spec's stack pointer),
  so nested loops restore correctly and the saves fold away. `REP` repeats the
  following instruction the same way.
* **Data ALU.** Multiplies are fractional (`(s1*s2)<<1`). The data limiter
  (moving an accumulator to a 24/48-bit destination) and rounding are the
  user ops `sat24`, `sat48` and `rnd56`. Scaling modes are not modelled.
* **AGU.** The default language updates address registers linearly. The
  `DSP56300:LE:24:modulo` variant routes every update through the user op
  `agu_modulo(Rn, delta, Mn)` for code that relies on modulo or reverse-carry
  addressing.

## Known limitations

* A loop whose last instruction is a two-word instruction starting at `LA-1`
  is not recognised as a loop bottom by SLEIGH alone (the context lands in the
  middle of that instruction). The **DSP56300 Loop End** analyzer finds these
  loops, moves the loop-end context to `LA-1` and re-disassembles it.
* `BRKcc` branches to `LA+1` through a computed target.
* `DIV`, `NORM`, `NORMF`, `CLB` are user ops.

## Regenerating

`dsp56300.sinc` is generated. Edit the templates and run

    python3 tools/gen_sinc.py data/languages/dsp56300.sinc.in \
        data/languages/dsp56300_np.sinc.in data/languages/dsp56300_root.sinc.in \
        data/languages/dsp56300.sinc

The templates use the Family Manual's 24-character bit strings (`{...}`); the
generator turns them into field constraints.
