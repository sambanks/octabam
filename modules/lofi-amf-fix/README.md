# `lofi-amf-fix` — LOFI AMF FIX

Fixes stock LO-FI's AMF knob jumping the pitch backwards at some settings:
one DSP multiply, in both payloads. Ported from [bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt).
`Kind.CF_PATCH`: two DSP-word pokes, no cave, no menu, no FX2 id.

Stock LO-FI's AMF coefficient computation runs `mpysu x0,y0,a` (signed ×
unsigned) at DSP `P:0x01bef` (payload A) / `P:0x019af` (payload B) on two
operands that are both magnitudes; the correct op is `mpyuu`. His report:
"LO-FI's AMF knob currently jumps the pitch backward at certain values".

The rest of octa-bt-pt generates per-user parameter defaults (any knob of the
14 stock effects, the FX1/FX2 default effect) and is not ported: there is no
canonical value to port. Two fixed-but-opinionated pieces are also left out:
a FLEX/STATIC `TSTR: AUTO → OFF` default, and "FX1/FX2 default = NONE".

## Open

- The addresses are fixed, not re-resolved per build. If a remix ever
  harvests LO-FI's code, each poke's `expect` refuses the build.
