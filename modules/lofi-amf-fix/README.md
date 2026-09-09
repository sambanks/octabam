# LOFI AMF fix

One correctness fix, ported from
[bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt) —
a parameter-default patch tool for 1.40C. `Kind.CF_PATCH`, two DSP-word
pokes, no cave, no menu, no FX2 id.

Stock LO-FI's AMF coefficient computation runs `mpysu x0,y0,a` (signed ×
unsigned) at DSP `P:0x01bef` (payload A) / `P:0x019af` (payload B), where
the two operands are both magnitudes — the correct op is `mpyuu`
(unsigned × unsigned). This is the exact defect class `CLAUDE.md` already
documents for this project's own assembler (`mpy x0,y0` → `mpysu`), just
found in Elektron's shipped, compiled code instead of anything octabam
assembles. `mpysu` treats its first operand as signed; upstream reports
"LO-FI's AMF knob currently jumps the pitch backward at certain values" —
consistent with a magnitude occasionally reading as negative.

## What was and wasn't ported

octa-bt-pt is mostly a *preference generator*, not a fixed patch set: a
Streamlit UI lets you pick your own default value for any parameter on any
of the 14 stock effects, and your own default effect for FX1/FX2. There is
no canonical answer to any of that, so none of it is here — porting an
arbitrary chosen default as if it were "the" fix would be dishonest. The
AMF fix is the one thing in the tool that's an objective bug fix rather
than a preference, so it's the only thing ported.

(Two more fixed-but-opinionated pieces exist upstream and were deliberately
left out: a FLEX/STATIC playback `TSTR: AUTO → OFF` default, and the
original — pre-generalization — "FX1/FX2 default = NONE" choice, which
happens to match this project's own `NO_FALLBACK` convention already.
Neither is a bug fix the way AMF is; ask if you want either added.)

## Measured vs inferred

**Measured, independently of upstream's claim:** both 3-byte words
disassembled with this project's own
`vendor/dsp56300/build/source/disassemble/dsp56kDisassemble` against
octabam's own stock firmware copy —

```
001bef: mpysu   x0,y0,a   ; 01278d   (stock, both payloads)
001bef: mpyuu   x0,y0,a   ; 0127cd   (the fix)
```

— and both resolved addresses (via this project's own `tools/dsp_modmap.py`,
which upstream vendors an identical copy of) hold exactly those stock
bytes in the shared firmware. `make check REMIX=lofi-amf-fix` and
`REMIX=ported` (combined with `midi-scenes`) both pass.

**Inferred, not reproduced here:** upstream's own verification — a full
128×128 (AMF × Fine) sweep, zero monotonicity violations after the fix.
No harness was built this pass to re-run that sweep against LO-FI's DSP
code; the claim is upstream's, not independently re-measured.

## Open

⚠️ **Never flashed**, same as `midi-scenes`.

⚠️ **The address is fixed, not re-resolved per build.** If a future remix
ever harvests LO-FI's own P-region as donor space for new code, this
module's poke would be pointed at stale bytes — but the poke's `expect`
assertion catches that and refuses the build rather than silently
overwriting whatever landed there instead.
