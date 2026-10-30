# The trap register

The traps that have already cost real work, moved here from `AGENTS.md` on
14 Oct 2026. `AGENTS.md` keeps a one-line index with a link into each entry.
`docs/contributing/FAILURE_MODES.md` is the register of hardware failures on
a unit (symptom -> cause -> fix); this is the register for the code, the
build, the emulators, the harness and the measurement instrument. Each entry
states the symptom, what it cost, the fix, and what now gates it.

Add a new trap here the moment it costs real work, and add its one-line
index entry in `AGENTS.md`'s trap index.

<a id="trap-detour-interior"></a>
### A branch can enter the middle of a displaced instruction span

**Seen:** BUKKAKEBOREALIS's MKII, octabam-core, 15 Oct 2026 (#741):
MIDI TRACK → CHROMATIC raised VEC 04 at `0x400bf10a`, the LCD surface.
Reproduced under the port: stock's MIDI branch at `0x400449b6` enters
`0x400449be`, a `movel d0,sp@-` shared with the audio drawer. The quantizer's
eight-byte detour at `0x400449b8` replaced that push with a NOP; its runtime
replays it for audio, but MIDI bypasses the runtime. The formatter then
pops four bytes too many, and the drawer returns into its surface argument.

**Cost:** the hook assembled and booted, and audio CHROMATIC worked, while
the MIDI path lost its return address. Whole instructions at a hook's
edges do not prove that every branch enters at those edges.

**Fix and gate:** the integration installs a six-byte jump over only the
audio load, leaving the shared push stock and claiming it with `Keep`.
The author's runtime is unchanged. `verify_quantizer_ui` selects CHROMATIC
through the panel in audio and MIDI on both models. Inspect incoming
branches before taking any instruction span for a detour.

## Traps that have already cost real work

<a name="trap-asm"></a>

### The assembler mis-encodes instructions, silently

**The assembler mis-encodes instructions, silently.** `dsp_asm` encodes
`tfr a,b` as `rnd b`, and **any `mpy` operand order it doesn't know as
`mpysu`** — found with `mpy x0,y0`, confirmed 9 Aug 2026 for `mpy x1,y1`
and `mpy x0,x1` too (every shipping site is audited safe because its second
operand is always positive, which is the only reason the engine works; the
sites are counted per module in `build_bus.MPYSU_AUDITED`, and since 23 Sep
2026 every `assemble()` round-trips its bytes through the disassembler and
stops on any other mismatch or on a count that differs from the table). `mpysu` treats the SECOND operand as unsigned, so
a negative multiplier there is silently corrupted. `mpy x0,y1` and
`mpy y0,x0` encode signed. Both assemble clean and do the wrong thing.
**Disassemble what you assemble** when a result surprises you — and always
for a new `mpy` whose second operand can go negative. A related family bit
us in shipping code: `cmp a,b` had encoded as `max a,b`, which updates only
the C bit while `blt` tests N^V. **Until 4 Oct 2026 it had no encoding
for a data-ALU op with two parallel moves** (XY, X:R, R:Y, class II):
`clr`/`add`/... with one were InvalidInstruction, and `mpy`/`mac` fell
to the non-parallel `mpysu`/`macsu` with both moves dropped (`mac
x1,y0,b x:(r1)+,x1 y:(r7)+,y0` -> `0126a6`; the chip word is `f4f9ea`).
`move x:(r1)-n1,x0 y:(r7)+,y0` encoded `(r1)` (`f0e100`): the XY form
has no `(Rn)-Nn`. Against the stock payloads (A+B) the old `dsp_asm` got
0 of 688 ALU+XY lines right (605 wrong, 83 refused) and 0 of 258 X:R/R:Y
lines; the patch makes all 946 the stock word and leaves the result for
the other 12,079 stock lines unchanged. A move token with no encoding is now
InvalidInstruction, and the round-trip compares every operand field,
parallel moves included. **And until 14 Sep 2026 it emitted only
the TWO-WORD displaced move**: `move x:(r7+$15),a` assembled to
`0a77ce 000015` where the chip (and every Elektron payload, 533 sites in A)
has the one-word `0257de` for displacements −64..63 with a data-ALU
register. `tools/patches/dsp56300.patch` adds the one-word form; every
word or cycle number recorded for a displaced move before that date is 2
where the assembler now emits 1 (the emulator's own cycle table prices the
forms 3 and 2; hardware timing of the one-word form under OUR code is
unmeasured — stock runs it every frame). **THE BINARY IS NOT THE SOURCE:**
the encoder lives in the vendored `assembler.cpp` behind that patch, and
a `dsp_asm` built before it silently emits the two-word form for every
site — five images (8–12, 14 Sep 2026) and every price quoted with them
were ~800 words / ~500 cycles heavier than the tree said, found only when
another session's FREE table did not match. After any change under
`tools/patches/`: `make dsp-repatch` (`scripts/setup.sh` does not
re-patch a built tree; it stops when the tree lacks the current patch),
then `make emu-cf`; after one under `tools/harness/dsp_host/`:
`scripts/setup.sh`. `make check-asm` expects `0257de` for `move
x:(r7+$15),a` and `f4f9ea` for `mac x1,y0,b x:(r1)+,x1 y:(r7)+,y0`.

<a name="trap-a0"></a>

### Reading `a0` exposes the fractional left shift that reading `a1` hides

**READING `a0` EXPOSES THE FRACTIONAL LEFT SHIFT THAT READING `a1` HIDES.**
`mpy` aligns the Q46 product into Q47, so `a1` is the plain fractional
product — which is why "mpy does not double here" is true, and stays true,
for every module that reads a1 (all of them until 29 Aug 2026). Read the LOW
word instead — the idiom for turning an integer product into a wrapping
ramp — and you see the RAW 48-bit content, shift included, so the effective
integer scale is **2× your multiplier**. Nimbus's grain window is one
`mpy phase,2^(23-k)` plus `abs`; written with the arithmetically obvious
`2^(24-k)` it assembled, rendered, and made a perfectly plausible granular
noise while running the window at DOUBLE RATE, which put the two grains of
each pair in phase instead of interleaving. Found by a DC gate, not by ear
and not by any existing check: two triangle windows a half period apart sum
to exactly 1, so **DC in must come back flat** — it came back with 2×-DC
ripple, and went flat (−122 dB) when the multiplier was halved. If you use
a0 for anything, pin it with a test whose arithmetic you can predict exactly.

<a name="trap-asr-a0"></a>

### `asr #n,a,a` shifts the low bits into `a0`, and Z is set only when all 56 bits are zero

**`asr #n,a,a` SHIFTS THE LOW BITS INTO a0, AND Z IS SET ONLY WHEN ALL 56
BITS ARE ZERO.** A ramp step written as `sub x0,a / asr #6,a,a / teq y1,b`
("a step that rounds to 0 snaps the run value onto its target") never
snapped: a1 was 0, a0 held the shifted-out remainder, Z stayed clear, and
every ramp sat up to 63 LSB under its knob for good (26 Sep 2026, found
by `make verify-one-bus`: a host's send at 100 was not bit-identical to a
SEND's at 100). The same a0 remainder breaks `add x0,a / cmp x0,a / teq`
(a 56-bit compare). Reload the step clean before testing it — `move a,x1 /
move x1,a / tst a` — the one-word `move a,x1` drops a0. Sister of the
"reading a0" trap above: the low word carries what a1 hides.

<a name="trap-a2-stale"></a>

### A logical op on an accumulator leaves the extension byte stale, and the next store saturates

**A logical op (`and`/`or`/`not`/`asr`-as-mask) on an accumulator leaves the
extension byte (A2/B2) STALE, and the next `move a,x:` SATURATES to full
scale.** Building a sign mask with `move a,b / asr #$17,b,b / not b` and
storing the result writes `0x7FFFFF`, not the bits you computed — the
store's limiter sees A2 inconsistent with A1's sign and clamps. This cost a
long session on the gated-reverb envelope: a branchless mask-select looked
correct and disassembled correctly but pinned the gate open, because every
masked value saturated on store. **Fix: don't hand-roll sign masks. Use the
conditional-transfer ops** — `tmi x0,a` (floor to 0 if negative), `teq x0,a`,
`tpl`/`tge` — which move a CLEAN register into the accumulator, so no A2
staleness. A plain `move #imm,reg` does NOT disturb the condition codes, so
the `sub`/`tst` that sets the flag survives to the Tcc. (This is also why the
sample loop stays branch-free: Tcc replaces the branch AND avoids the trap.)

<a name="trap-tcc-pair"></a>

### A Tcc pair that shares one compare is broken by any arithmetic between them

**A Tcc pair that shares ONE compare is broken by ANY arithmetic between
them — and nothing at the second site looks wrong.** The branch-free idiom
here is `cmp`/`tst` once, then several `Tcc`s that all read the same
condition codes, relying on the fact that MOVES do not disturb them. That
holds until someone inserts real work in the middle. GRAIN's two scatter
latches (line L, line R) shared one wrap flag; adding a density gate
containing `clr b` and `tst a` between them left line R testing garbage, so
it re-latched a random read position EVERY SAMPLE instead of once per grain.
That is broadband noise, and it was audible as a hiss **on the right channel
only** — found by ear (13 Aug), not by any check, because `make check` and
the bit-identity gate were both green: the code was deterministic and every
mode still assembled. Fix: park the compare's RESULT in a scratch slot and
restore the flag with `tst` before each Tcc that needs it. **When you add
anything to a block, check what the code BELOW it assumed about the
condition codes** — the dependency is invisible at the point you edit, and
`clr`, `and`, `abs`, `tst` and every arithmetic op all set them. Same family
as the A2-staleness trap: legal instructions, correct-looking source, wrong
machine behaviour.

<a name="trap-move-tfr"></a>

### An accumulator-to-accumulator `move a,b` limits; `tfr a,b` moves all 56 bits

**AN ACCUMULATOR-TO-ACCUMULATOR `move a,b` LIMITS; `tfr a,b` MOVES ALL 56
BITS.** A parallel `tfr x1,a  a,x:(r3)+` written to replace `move a,x:(r3)+ /
move a,b` differed on the bit-identity gate whenever `a` exceeded 24 bits
(23 Sep 2026, Modulation's LINE loop; encodings confirmed by disassembly,
found by bisecting one item). The two are interchangeable only when the
source is known to fit.

<a name="trap-tcc-operands"></a>

### `Tcc` takes a register source, never an accumulator, and `clr` takes an accumulator, never a register

**`Tcc` takes a REGISTER source, never an accumulator, and `clr` takes an
accumulator, never a register.** `tpl b,a` and `clr x0` are both
InvalidInstruction — caught at assembly, which is the cheap case, but they
look plausible enough to write repeatedly. Move the value through `x0`.

<a name="trap-lua"></a>

### `lua (rN+d),rM` takes d in −64..63, and `dsp_asm` wraps anything larger silently

**`lua (rN+d),rM` TAKES d IN −64..63, AND `dsp_asm` WRAPS ANYTHING LARGER
SILENTLY.** `lua (r7+$46),r5` assembled to `0x042765`, the same word as
`lua (r7-$3a),r5`, and the round-trip disassembly cannot object (a `lua`
is a `lua`): Modulation's TONE glide read and wrote 58 words BELOW its
block for one build (26 Sep 2026, caught by `verify_modulation`'s
reference gates, not by the build). Past ±63 use `move r7,r5 / move
#$46,n5 / move (r5)+n5`, the form the streams already use.

<a name="trap-label-prefix"></a>

### `dsp_asm` resolves labels by prefix, so no new label may have an existing label as its prefix

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

Gate: `tools/build/nolabelprefix.py` (called by `build_bus.assemble_syms`; test `tools/verify/tests/test_label_prefix.py`) refuses a source that defines a label that is a prefix of another. It sees only labels at the start of a line, and only within one `assemble_syms` source; the disassembly check cannot see this trap (it decodes the bytes `dsp_asm` wrote). Issue #815 item 5, 21 Oct 2026.

<a name="trap-markers"></a>

### Build-time markers and base literals count when they appear in comments

**Build-time markers and base literals count when they appear in COMMENTS.**
`build_bus.py` census-checks the number of `$30000` literals in the delay
source and requires exactly one `; DMODE_OVERRIDE` / `; DINT_OVERRIDE`
marker — and the substitution is a blanket text replace over the whole file.
Writing *about* either in a comment trips the guard: both happened while
documenting stage 5/6 (a comment explaining why mode 3's immediate must be
decimal spelled the hex out; another explaining the override marker spelled
the marker out). The build refuses, loudly, which is the guard working —
describe them in prose instead of spelling them. The same goes for
`; ROTLATCH` and `; ROTINIT`: the build substitutes a body at the FIRST
occurrence, and on 21 Sep 2026 a housekeeping comment that said "the
ROTLATCH check" took the tracker body while the real marker stayed a
comment -- no client on either payload resolved its write offset, and
`verify-bus` read it as every server's client count changing.
`_marker_once` refuses a second occurrence of `; ROTLATCH`, `; ROTINIT` and
`; XBUS_GATE`; the `; HOSTGUARD`, mode-override and delay-override markers are
counted to exactly one before they are replaced.

<a name="trap-chip-form"></a>

### An instruction form the chip has never run is not proven by the port

**A DSP FORM SHIPS ONLY IF A STOCK PAYLOAD RUNS IT OR A ROW IN THE
INSTRUCTION-FORM REGISTER (`docs/firmware/CHIP.md`, section 1) APPROVES
IT.** The assembler encodes it, the vendored emulator decodes it the same
way, and the chip may not — the port proves nothing about a form the chip
has never run. Image 44 (21 Sep 2026) wedged on its first block on four
one-word displaced Y stores (`move a,y:(r3+$1)`), a form with no site in
either stock payload; the X form has 533. The pin is not to the form
alone: image 45 used `move a,y:(r3)+`, which stock runs, and wedged the
same way (FAILURE_MODES "Sequencer stuck on step 1", cause 🟡 inferred) —
which is the point: the port showed it for neither form. Before using a
form, grep it in `out/dsp/payload_*.asm`
(`tools/build/dsp_disasm_all.py`); no precedent means a hardware probe
first and then a PR adding the register row with the evidence, or the form
everything else uses.

<a name="trap-rep-dma"></a>

### No `rep` in an effect's `init` or `proc`, and no dense X work in a DMA's 8K block

**NO `rep` IN AN EFFECT'S `init` OR `proc`, AND NO DENSE X WORK IN A DMA'S
8K BLOCK.** Neither stock payload contains a `rep`. A `rep` cannot be
interrupted, and the host-command handlers that arm the ColdFire's DMA must
answer at once: JamCones' BBD delay on T1 crackled core B and then silenced
tracks 1-4 (11 Oct 2026), and Zac's MKI voice tore the read-back and wrote
ColdFire RAM out of place; `do #n,>l / div x0,a / l:` is bit-identical and
fixed both. Separately, core work that hammers the memory partition a DMA
channel uses stalls the DMA (core 0: `X:$0000-$1cf`, `$2000` and `$4000`
host buffers, `$8000` ESAI): a muted track leaking into MAIN, outputs stuck
one-sided. The port models neither. `docs/contributing/FAILURE_MODES.md`
has both entries; `tools/build/norep.py` makes the build refuse a `rep` in any DSP source.

<a name="trap-spec-xbus"></a>

### `SPEC=1` requires `XBUS=1`

**`SPEC=1` requires `XBUS=1`.** Without it the accumulators stay in core-private
memory and each half of the tracks can reach only its own core's server — worse
than today, **and it still makes sound.** The build guards this. Do not ungate it.

<a name="trap-track-core"></a>

### The track↔core mapping is inverted from old assumptions

**The track↔core mapping is INVERTED from old assumptions**: payload A serves
**tracks 5-8** (BusVerb), payload B serves **tracks 1-4** (BusDelay).
Measured 10 Aug 2026 via the MrkVerb32 marker flash, after the assumption cost
two flashes and a session chasing "R13 is dead" (it was alive on tracks 5-8).
Kept deliberately: delay on low tracks, reverb downstream. Test the reverb on
**track 5**, not track 1.

<a name="trap-send-knobs"></a>

### SEND's `DEL` and `REV` are separate knobs

**SEND's `DEL` and `REV` are separate knobs**: `x:(r6+0)` and `x:(r6+1)`
(again since 25 Sep 2026; one knob from 6 Sep). Driving the wrong one
renders silence, which reads as a broken algorithm.

<a name="trap-formatter"></a>

### A descriptor's display formatter overrides its value count, and a cloned descriptor inherits the donor's

**A DESCRIPTOR'S DISPLAY FORMATTER OVERRIDES ITS VALUE COUNT, and a cloned
descriptor inherits the DONOR's.** A slot can carry a correct count, default,
name and enable bit and still draw as something else entirely — or as nothing
at all. Found on the 17 Aug flash: BusDelay clones SPRING REV, the formatter
fix-up in `build_bus.py` was gated to the reverb, and three of six page-2
slots drew wrong. WOW inherited SPRING TYPE's word-label renderer whose table
has THREE entries, was asked to draw 0..127, and **drew no knob at all**;
MODE inherited SPRING BAL's bipolar pair and drew as a balance dial reading
−64…−60 instead of a 5-way select. Every existing check passed, because every
field they checked was right. `verify_menu` now checks the renderer against
the count (`count < 128` → the enumerated pair with `0x12a` zero; `128` → both
formatters zero). **The general form: when you clone a descriptor, every field
you did not explicitly write is the donor's, and some of them outrank the ones
you did.** Same family as "a slot can draw a knob and publish nothing" — the
panel and the DSP are separate mechanisms and neither validates the other.

<a name="trap-unicorn-frac"></a>

### Stock Unicorn halves every ColdFire fractional-mode multiply and adds where `msac` subtracts

**STOCK UNICORN HALVES EVERY ColdFire FRACTIONAL-MODE MULTIPLY AND ADDS
WHERE `msac` SUBTRACTS, and the firmware runs its EMAC in fractional mode
(`MACSR = 0x20`).** Unicorn 2.1.4 computes `macl`/`macw` under `F/I = 1` as
an UNSIGNED product `>> 32` where the MCF5445x does a SIGNED product `>> 31`
(the 2.62 product shifted left one bit, upper 40 bits accumulated), and it
reads the MAC/MSAC bit from the opcode word where ColdFire keeps it in the
extension word, so every `msac` accumulated with the wrong sign (the
sequencer's frame builder is one). One defect, three symptoms that were each
investigated as firmware behaviour for a day (7 Sep 2026, RTOS_FORK
section 10.16): the recorder length converter wrote 10,336 for Bryan's 20,672
(explained away as "2-sample units"), the recorder's block walk stalled at
3,072 samples ("needs a DSP position feed"), and the sequencer's per-frame
timing byte advanced 8 per 16-sample frame, which dropped half the tempos'
recorder trigs ("nothing re-locks the step clock", plus a compensation
lever). The firmware's own reciprocal tables (`0x80003c20`: 2^31 / block
size) said which side was wrong. `emu_bringup.emac_selftest` pins the
semantics; `scripts/build_unicorn.sh` builds the fixed
library (`tools/patches/unicorn_emac_fractional.patch`). The general rule is the
same as "disassemble what you assemble": when firmware arithmetic comes out
exactly 2× or ½ off, suspect the INSTRUMENT before inventing a unit, and
find a site in the firmware whose constants only make sense one way.

<a name="trap-unicorn-macload"></a>

### Stock Unicorn's MAC-with-load decode has three defects, which is why tier-0 shims it per site

**STOCK UNICORN'S MAC-WITH-LOAD DECODE HAS THREE DEFECTS, WHICH IS WHY
TIER-0 SHIMS IT PER SITE RATHER THAN THE FORM BEING ABSENT.** Found 22 Sep
2026 by reading markandrus/octemu's independent fix against QEMU 11.1 and
confirming the identical lines are present, verbatim, in Unicorn 2.1.4's
own vendored QEMU 5.0.1 `target/m68k/translate.c`. In `DISAS_INSN(mac)`:
(1) `rx = (ext & 0x8000) ? AREG(ext, 12) : DREG(insn, 12)` reads Rx from
the OPCODE word instead of the extension word; (2)
`dual = ((insn & 0x30) != 0 && (ext & 3) != 0)` reads Ry's own register
field (ext bits 3-0, ANY MAC-with-load) as a dual-accumulate flag, and
`cfv4e` has no `M68K_FEATURE_CF_EMAC_B`, so this `disas_undef`s an ordinary
multiply into an illegal-instruction trap whenever Ry's low bits are set;
(3) the EMAC address MASK register resets to zero instead of CFPRM's
all-ones, and MAC-with-load ANDs its effective address with it, so every
load reads address 0 regardless of the real operand. **Fixing (3) in
`cpu.c`'s `m68k_cpu_reset` does nothing under Unicorn**: `src/uc.c` never
calls `cc->reset()`, only `uc->reg_reset()` (`unicorn.c`), a separate,
minimal function that clears `aregs`/`dregs`/`pc` and nothing else — found
by a `UC_ERR_READ_UNMAPPED` on a `macl ...,%a0@,...` whose `a0` was a
valid mapped address (the AND with a zeroed mask folded it to 0 first).
The fix belongs in `unicorn.c`'s `reg_reset`, not `cpu.c` (kept there too,
for documentation, since a future Unicorn version might wire up the real
reset path). All three are in `tools/patches/unicorn_emac_fractional.patch`;
`emu_bringup.emac_selftest` gained cases for them (fails on stock, passes
fixed). The MAIN OS has zero true dual-accumulate instructions
(`maaac`/`masac`/`msaac`/`mssac`), so forcing `dual = 0` is unconditionally
safe for it. The per-site shim (`emu_bringup._emac_load_shim`) stays:
the only differential against native decode ran route A with no project
on the card, which executes none of the 435 hooked sites (0 shim calls
either way), and route A was retired on 26 Sep 2026.

<a name="trap-macsr"></a>

### MACSR S/U is bit 6, and in fractional mode it selects 16-bit rounding on the accumulator read-out

**MACSR S/U IS BIT 6, AND IN FRACTIONAL MODE IT IS NOT SIGNED/UNSIGNED:
it selects 16-BIT ROUNDING ON THE ACCUMULATOR READ-OUT.** The ColdFire port
had S/U as bit 4 (that is R/T) and returned every `movclrl` as `ACC[39:8]`;
the firmware's level chain at `0x4000ccae` runs at MACSR `0x60` and keeps the
LOW words of two reads as a voice record's mode:level, which the CFPRM's
pseudocode (`OMC,S/U == 01`: `ACC[39:24]` rounded into `Rx[15:0]`, upper half
zero) puts there and a plain `>> 8` leaves at zero — every voice rendered
silent for a whole session (8 Sep 2026, O9b). The self-test never exercised
S/U. Read the CFPRM's MOVCLR pseudocode before touching `accRead`. The ACCext
registers have two layouts as well (fractional: eight extension + eight
low bits per accumulator; integer: sixteen extension bits), and the frame
ISR saves and restores them in INTEGER mode every frame (`0x4000ac96`,
`0x4000d968`); the port's write knew only the fractional layout until 23
Sep 2026 and put the saved word's low byte into ACCn[7:0] on every restore
-- invisible to a stock A/A (deterministic), found by Jannik Aßfalg's A/B/A
of a ColdFire patch. `test_emac.cpp` holds both layouts now.

<a name="trap-agu-modulo"></a>

### The vendored DSP AGU left a modulo buffer on a pre-decrement from its base

**THE VENDORED DSP AGU LEFT A MODULO BUFFER ON A PRE-DECREMENT FROM ITS
BASE.** `x:-(r2)` with r2 = 0 and m2 = 0x3f gave `0xffffbf` where the chip
gives `0x3f`, the next sixteen sample writes walked the peripheral registers,
a timer interrupt came alive whose vector in payload B is `move x0,y:(r4)+`,
and the corruption surfaced as a 196,608-iteration voice loop thirteen frames
after the first trig. Found with a one-word write watch, a DSP PC watch with
registers and an interrupt-vector histogram (O9b); fixed in `agu.h`. It is
the eleventh vendored-emulator defect and `dsp_host` renders every effect on
that AGU — `make check`'s bit-identity gates are the audit.

<a name="trap-trampoline"></a>

### A rewritten trampoline is not retranslated

**A REWRITTEN TRAMPOLINE IS NOT RETRANSLATED.** The ColdFire emulator's
EMAC-with-load shim ran every shimmed instruction from one scratch address,
rewriting its bytes each time; in a long-running Unicorn the address kept
its first translation, so the trampoline executed whichever instruction had
been translated there LAST — `msacl ..,%acc1` ran as the previous `msacl
..,%acc0` and corrupted the sequencer's timing byte (RTOS_FORK section 10.16.2,
7 Sep 2026). Fresh-Uc micro-tests could not show it; a per-instruction
trace of the real run did. Rule: never rewrite emulated code in place — give
each distinct instruction its own slot (`r.emac_slots`), and when a
micro-test disagrees with the running emulator, the difference is state,
so trace the running emulator.

<a name="trap-blind-instrument"></a>

### A measurement can be structurally blind to the thing you are using it to rule out

**A MEASUREMENT CAN BE STRUCTURALLY BLIND TO THE THING YOU ARE USING IT TO
RULE OUT — and it will report "clean" with total confidence.** Two instances,
both on 17 Aug 2026, both costing hours:
- `send_probe`'s THD metric sums harmonics **2f..9f of a 438 Hz tone**. A
  block-rate discontinuity (~2940 Hz) is not a harmonic of 438 Hz, so the
  metric cannot see it. It reported −45 dB ("clean") on audio that hardware
  measurement later showed carrying +22 to +31 dB of inharmonic hash. Every
  "no change" conclusion drawn from it that day was worthless.
- XBUS step 3 concluded "synchronisation not needed" from a cross-core send
  measured **through the reverb** — the one consumer that smears per-sample
  damage into a multi-second tail. It shipped a cross-core race for months.
**Before trusting a null result, ask what the instrument physically cannot
see.** A reverb cannot show you a discontinuity. A harmonic metric cannot show
you an inharmonic one. A lock-step emulator cannot show you a race between
two cores — `dsp_host` boots both payloads since 7 Sep 2026 and `-skew` can
interleave them, but that is a fuzz of the hardware's timing, not the
timing, so a local "clean" is still NOT evidence a bus timing defect is
gone (a local red IS a defect). When local says clean and hardware says
broken, believe the hardware and go looking for what the harness omits.

<a name="trap-bus-zero-client"></a>

### A bus client that registers but contributes nothing steals everyone else's level

**A BUS CLIENT THAT REGISTERS BUT CONTRIBUTES NOTHING STEALS EVERYONE ELSE'S
LEVEL.** The auto-gain divides the accumulator by the number of registered
clients, so a writer that registers unconditionally and then writes zero
dilutes the real senders by N/(N+1) — **−6 dB with a single sender.** Two
instances found the same day, 17 Aug: BusVerb registered for its `→DEL` send
even when `→DEL` was off (since gated on the knob, measured −6.02 → +0.00 dB;
the send itself was later retired), and BusDelay's own `IN` knob would have
done it too if its default
had stayed non-zero on a return track with no audio to send. **Gate the
registration on the knob, and remember the level knob is usually decoded
LATER in the block than the registration runs** — read it from `r6` directly,
or use the previous block's value and accept one block of latency. Symptom to
watch for: a level that is flat across sender count in one layout and drifts
in another. It surfaced as an "unexplained residual" in a completely
different effect's send level, and the effect being blamed was innocent.

<a name="trap-r7-scratch"></a>

### r7 scratch `$00..$83` is the per-instance block; `$84+` hangs the unit

**r7 scratch `$00..$83` is the per-instance block; `$84+` hangs the unit**
(a host track's own state lives there between calls, images 39–42). Each
module's header maps its own block; a slot census of the source is the
truth, not the map (23 Sep 2026: BusVerb's map said full and 14 slots had
no reference; BusDelay's map listed nine slots the code never touches, and
one it used twice — the PITCH decode's park on grain 3's scatter record).
New per-track state goes in a free slot of the module's own block or the
Y state table. (Do not scan for these with `"\$$s"` in a shell — it expands.)

<a name="trap-dump-alias"></a>

### A dump can resolve a perfectly plausible dispatch entry for an effect it does not contain

**A dump can resolve a perfectly plausible dispatch entry for an effect it
does not contain.** `SPEC=1` (which `make render` sets) aliases the absent
server's id to the SEND client — deliberately, so a wrong chooser pick
becomes a send. Locally that alias renders a dry passthrough: silence over
the bus, dry in a `--direct` control, no error anywhere. This produced the
12 Aug "BusDelay outputs nothing in any config" session — the delay was
never instantiated; every measurement ran a SEND. Delay work needs the
hatch (`make render-delay`), and `send_probe.py` now dies when a D layout's
DELAY entry equals SEND's. The general rule: before believing a *negative*
result, check which code the dispatch entry actually points at — same
family as "disassemble what you assemble".

<a name="trap-shared-window"></a>

### In the shipping remix, payload A's half of the shared window is fully owned

**IN THE SHIPPING REMIX, payload A's half of the shared window is FULLY
OWNED** (a remix without the reverb frees it, which is how the insert
collection has room to stack): stock's staging at `0x30000-0x30047`,
BusVerb's buffers at `0x30800-0x357FF` (its `Claims.dsp_ranges`),
stock's core 1 -> core 0 mailbox at `0x37F00-0x37F0F` (moved there from
`0x38000` by every build; `docs/firmware/DSP.md` section 5), bus
scratch at `0x36000-0x36157`
(grew 12 Aug for the DELAY send counts + reciprocal table, 17 Aug when the
accumulators went to FOUR buffers for the cross-core race fix, and 22 Sep
2026 to EIGHT buffers plus the chain at `0x360d8..`).
There is no free ground in it for delay lines — the DEV build places the
delay at its shipping base `0x38000` (payload B's half) for exactly this
reason. A delay based at `0x30000` sweeps the rotation word, all four ACC
buffers and both role locks every 16,384 samples and blows up any
multi-server layout (found 12 Aug, RDS full-scale garbage).

<a name="trap-fx2-id"></a>

### An FX2 id is also an FX1 id: the DSP dispatch tables are indexed by the raw id and shared by both menus

**AN FX2 ID IS ALSO AN FX1 ID: the DSP dispatch tables are indexed by the
raw id and shared by both menus.** A module on a stock effect's id replaces
that effect's code wherever it is selected, FX1 included, and a remix that
omits the module then aliases the id to SEND and takes the stock effect
away from FX1 too. Rungs sat on EQUALIZER's `0x0c` and Nimbus on DJ EQ's
`0x0d` from 29 Aug to 2 Sep 2026, in every local image, unflashed. The
schema now refuses `STOCK_FX2_IDS`; the stock effects themselves are kept
in a chooser by listing them in the remix (`tools/remix/stock.py`). The
same table makes FX1's NONE (id 0) run the FALLBACK's code: SEND ran on
every empty FX1 slot at r7 0x6100/0x6400/0x6700/0x6a00, sent from an
unseen page byte and, on core 1, compared the rotation tracker before
position 0's advance — one step ahead for good on the unit (images 40–47,
21 Sep 2026; `modules/send/README.md` "An FX1 slot is not a client"). A client keys its slot on r7, never
on X:$213 (stale at proc time), and `dsp_host` places FX2 slots at
0x6200 + 0x300·pos (`verify_two_core` had 0x200·pos until image 48).

<a name="trap-module-id"></a>

### A module's id is the remix's, not the manifest's: `registry.modules()` reads the preferred one

**A MODULE'S ID IS THE REMIX'S, NOT THE MANIFEST'S.** `MenuEntry.fx2_id` is the
id a module prefers; `registry.assign_ids` (called by `registry.bound(remix)`)
settles the id in a remix, and in a 64-id image the FX2 tables are elsewhere
too (`idspace.fx2_ids(remix)`). A tool, gate or module that reads
`registry.modules()[k].menu.fx2_id`, a literal id or `0x400d5fdc` is right only
for the stock layout. On `remixes/test/ids64` (BBD pinned to `0x25`) that cost
a run of gates one at a time, 22 Oct 2026: `verify_dirty_state` ("not placed on
either payload": it asked for `0x1b`), `verify_labels` and `verify_mode_names`
(a vector-4 trap in the emulated formatter call), `verify_menu` (the panel
printed PHASER for BBD: stock's table read past its 32 entries),
`verify_replaces` (it read B's dispatch tables at stock's address, which B had
left). The fix in each is `registry.bound(remix)` for ids and `idspace` for
addresses (`fx2_ids`, `id2pos`, `layout_of`, `dispatch_word`,
`payloads`; `dsp_modmap.payloads_of` for the payload locations). Left on the
preferred ids: `tools/hw/ot_project.py` after the first two functions,
`ot_spec.py`, `rig_render.py`, `remix/app.py`, `harness/stress_project.py`.

<a name="trap-audio-block"></a>

### `dsp_host`'s default audio block (X:0x80) sits inside the scratch the stock effects use

**`dsp_host`'S DEFAULT AUDIO BLOCK (X:0x80) SITS INSIDE THE SCRATCH THE
STOCK EFFECTS USE.** On hardware the dispatcher passes `r0 = 0`: the audio
block is at X:0 and stock code scratches X:0x20–0xff every block. Our
modules never touch low X, so the default was harmless for months and then
made the stock FLANGER render as Nyquist-rate hash and five other stock
effects 5–17 dB dirtier while passing as "credible" (2 Sep 2026). Eight
instruction probes were spent clearing the emulator first. `send_probe`
passes `-audio 0` for a stock render; if a stock effect sounds wrong
locally, suspect the harness before the effect.

<a name="trap-stock-tables"></a>

### An absolute stock-table address is right in payload A and 13 words off in B, and the audition render cannot show it

**AN ABSOLUTE STOCK-TABLE ADDRESS IS RIGHT IN PAYLOAD A AND 13 WORDS OFF IN
B, AND THE AUDITION RENDER CANNOT SHOW IT.** The payloads are linked
separately: the 6,305-word curve bank is `X:0x438` in A and `X:0x42b` in B
(the block below it is 23 words on A and 10 on B), and the Y tables shift by
16. Stock code carries a different extension word per payload; a module is
one source assembled into both, so a bare literal into a stock table is
correct on tracks 5–8 and mistuned on 1–4, and past the end of the relocated
table it reads garbage. Bryan T's LOFI2 shipped that way through a week of
renders and several flashes (13 Sep 2026, `docs/firmware/TABLES.md`
"Payload-relative addresses";
measured here from our own image). `send_probe`'s single-payload render dumps
payload A. Declare stock table addresses so the build rewrites them per
payload, or read through a build-supplied base; and audit any stock-table
read on BOTH payloads under `rig_render.py`. Our own modules were scanned
14 Sep 2026 and read none.

<a name="trap-lfo-word"></a>

### A knob word under an LFO is not a clean word: bits 8-15 are non-zero, and no local render writes them

**A KNOB WORD UNDER AN LFO IS NOT A CLEAN WORD: BITS 8-15 ARE NON-ZERO, AND
NO LOCAL RENDER WRITES THEM.** Each ColdFire halfword is one DSP word `<< 8`,
and the firmware's LFO store (`movew %d0,%a1@` at `0x4000d07a`,
`docs/firmware/LFO.md` section 5) writes the modulated value with its low byte
free. Measured under the port (`ot_emu --watch-pc 0x4000d07a`, bottleservice
with `tools/harness/stress_project.py`, 24 LFOs per part, depth 18-28 on
FX1/FX2 knobs, 900 frames, 5 Oct 2026): 21,088 stores, 21,011 with a
non-zero low byte (e.g. `d0 = 0x22fe` for knob 34); 147 stores had knob
byte 0 and all 147 carried a non-zero low byte (largest knob byte seen
0x7d), so a knob at 0 under an LFO is not a zero word. The gate project at
LFO depth 0: 19,843 stores, all with a zero low byte. A knob at rest is
clean; `dsp_host -params` takes 0..127 and writes clean words, so no render
shows it. Two modules read the raw word: WAVE's `asr #$10` on OCT left a
remainder in b0, `neg b` borrowed from b1 (one octave off at any OCT) and at
OCT 4 `do n3` ran with LC = 0xffff (65,535 `asr` a block); SEND's
registration `tst` on the raw DEL/REV word counted a track at knob 0 as a
sender (N/(N+1) dilution of every other sender, -6.02 dB with one). Rule:
mask a page word with `and #>$7f0000` before any shift, compare, select or
`tst` use (the form the servers, Spectrum and BusVerb use); the
`asr` then leaves a clean low word. After `and`, store from `a1`/`b1`
(`move a1,x:`), not `move a,x:` (the A2-staleness trap above). The
`dsp_host -pword k:off=hex` option writes a raw word after `-params`, and
`verify_wave` / `verify_one_bus` render dirty words.

<a name="trap-name-nul"></a>

### A descriptor name that exactly fills its field leaves no NUL, and the crash lands somewhere else entirely

**A DESCRIPTOR NAME THAT EXACTLY FILLS ITS FIELD LEAVES NO NUL, AND THE
CRASH LANDS SOMEWHERE ELSE ENTIRELY.** `abbr` is a 5-byte field holding FOUR
characters plus a terminator; `fullname` is 13 bytes holding TWELVE (and the
build tag is appended after your string). A 5-character abbr assembled,
built, drew correctly on the panel and behaved normally under manual knob
use — and threw a line-F exception (VEC:0B) the moment a parameter was
**LFO-MODULATED**, faulting PC `0x48454C4C` = `"HELL"`. It presented as
"custom effects can't be modulated", which points at the clone mechanism,
not at a string. Found 2 Sep 2026 by Bryan T contributing `modules/hello/`,
after the build accepted it silently. A faulting PC made of the field's own
ASCII is a smashed return address, so the copy destination is fixed-size —
INFERRED, the copy is not located; the rule itself is measured (all 30 stock
page descriptors are ≤4 chars with byte 5 zero). `schema.MenuEntry` now
refuses both over-lengths and `build_bus.py` re-checks the string it writes,
tag included — which caught two diagnostic delay names (`BusDlyRPLY`,
`BusDlyNOCF`) that had been filling all 13 bytes since 24 Aug 2026.

<a name="trap-part-layout"></a>

### A part saved under an older slot layout feeds the new layout its old bytes, and the sequencer stalls on the first play

**A PART SAVED UNDER AN OLDER SLOT LAYOUT FEEDS THE NEW LAYOUT ITS OLD
BYTES, AND THE SEQUENCER STALLS ON THE FIRST PLAY.** Moving MODE from slot 7
to slot 6 (4 Sep 2026) passed every local check and both hardware claims —
then pressing play went 1, 2, 1 and froze, because every other track's part
still held a 0–127 SHMR/MDEP byte in what was now a count-3 select, the
"value outside its count is used as an index" trap in stored form. The
schema cannot see stored data. Re-selecting the effect on the track you are
looking at is NOT enough; the sequencer runs every track of the part. After
any change to a slot's count, position or meaning: `tools/hw/ot_project.py
stamp-defaults <project> <remix>` on the card BEFORE play, and say so in the
flash notes. (Cause inferred from the symptom and a refreshed project
running clean; not measured.) Measured against it under the port (6 Oct
2026): stock's Part validator `0x40002318` rewrites every FX page byte
outside its descriptor's `[min, min + count - 1]` to the nearer end during
the load, in all 16 banks x 8 Parts (`tools/verify/verify_brain.py`, "stock
clamps"), so a stored byte loaded from the card does not reach play outside
its count; and with such bytes stamped, the page drawn and the DSPs
running, the sequencer advanced as on a clean project. What stalled the
unit is open; the stamp before play stays the rule.

<a name="trap-otemu-part"></a>

### The part the emulated load applies is not the part that plays

**THE PART THE EMULATED LOAD APPLIES IS NOT THE PART THAT PLAYS.** `ot_emu`'s
load applies bank 1 part 1; its transport start re-applies the SAVED bank's
pattern part and the refresher at `0x4000c19c` rewrites the live lane from
it. A fixture that edited "part 1 and its saved copy" measured a track whose
FX2 was still SEND — for a whole O9c session (8 Sep 2026): "the THRU monitor
is pre-FX2", "the page-2 select never crosses" and "X:0x2c0 is the FX2
instance" were all this one fixture, and the last was `stamp-slot` landing in
the track's FX1 (it stamps both slots). Write fixtures into EVERY part of
EVERY bank (`ot_project.py set-fx`, `stamp-slot`), and before believing a
DSP-side "byte-identical" between two cards, run both with `--block-dump`
and `tools/harness/blockdump.py diff`: if no host-port block differs, the
cards did not differ where it matters.

<a name="trap-dispatcher-model"></a>

### The harness's model of the dispatcher is not the dispatcher

**THE HARNESS'S MODEL OF THE DISPATCHER IS NOT THE DISPATCHER.** `dsp_host`
handed every effect r7 = 0x6100 + 0x100·(2·pos + fx−1); the stock
dispatcher bumps r7 THREE times per track (the third unconditional, after
FX2), so from position 1 on every r7 the harness used was wrong, and two
modules that pinned a track by its r7 (the one-aux return on T8, the
track-8 send refusal) matched in the harness and never on the unit — flash
6's "the return never reaches T8", with `make verify-one-bus` green on
exactly that property. Found 8 Sep 2026 by running the shipping image from
the card under the ColdFire port (`git show 3ceba41:docs/history/COLDFIRE_PORT.md` O11). Any module
logic keyed on a dispatcher fact (r7, r6, X:0x213, instance blocks) is
measured under the port (`ot_emu --dsp-pcwatch`), never modelled in
`dsp_host`; and a hardware failure the lock-step harness cannot show goes to
the port before it goes to a guess.

<a name="trap-init-r1"></a>

### An effect's `init` must preserve r1: the FX1 dispatcher keeps the effect id there across the init call

**AN EFFECT'S `init` MUST PRESERVE r1: THE FX1 DISPATCHER KEEPS THE EFFECT
ID THERE ACROSS THE INIT CALL.** `P:0x4c8..0x4d7`: `move b,r1`, `jsr
INIT_TABLE[r1]`, then `move x:(r1+$235),r2 / jsr (r2)` for proc — so an init
that returns with r1 moved sends the proc call through a garbage word to
P:0 = the reset vector, and the core dies AT PROJECT LOAD, before a frame.
Image 99 (13 Sep 2026) did this on every core that loaded a Spectrum on FX1:
its new init zeroed 24 state slots with `move a,x:(r1)+`. It looked like the
step-1 DSP hang and was found under the ColdFire port's last-PC ring in an
hour; `dsp_host` cannot see it because it calls init and proc itself and
never reads r1 between them. Proc may use r1 (the dispatcher reloads it
after proc). `tools/verify/verify_init_regs.py` refuses an init that writes
r1/n1/m1 and runs in `make check`. Zero through r5.

<a name="trap-knob-publish"></a>

### A parameter slot can draw a knob and publish nothing

**A parameter slot can draw a knob and publish nothing.** The page descriptor
and the DSP-side read are separate mechanisms; `dsp_host` pokes r6 directly, so
everything looks live locally even when the real unit would publish nothing.
See `docs/firmware/PARAM_PAGES.md`.

<a name="trap-flash"></a>

### Flash cycles are expensive

**Flash cycles are expensive** — each one is a manual firmware write. Render
locally and measure instead of guessing. This is why the emulator path exists.

<a name="trap-failure-modes"></a>

### When the unit misbehaves, check `docs/contributing/FAILURE_MODES.md` first

**When the unit misbehaves, check `docs/contributing/FAILURE_MODES.md` first** — the
register of hardware failure modes (symptom -> cause -> fix). Add any new one
the moment it is seen; do not let it live only in a commit message.

<a name="trap-dirty-state"></a>

### A persistent slot that init does not clear holds whatever the effect before ours left in the block

**A PERSISTENT SLOT THAT INIT DOES NOT CLEAR HOLDS WHATEVER THE EFFECT
BEFORE OURS LEFT IN THE BLOCK — AND NO LOCAL RENDER CAN SEE IT, BECAUSE THE
PORT AND `dsp_host` BOOT ZEROED RAM.** Spectrum's init cleared `$00..$17`;
filter B's two HP poles at `$38/$39` (`$3c/$3d` R) sat at cHP = 0 on the
passthrough stamp, FROZEN, and `hp2 = yB − h2` subtracted a stale h2 from
every sample forever: up to a full-scale DC on a station's output. An
AC-coupled capture cannot see DC, so it surfaced as something else entirely
— "the master compressor collapses the RIGHT channel above COMP 40" (the
makeup clipped DC + audio to a constant on the channel whose offset was
larger) — and cost 13–14 Sep 2026: three diagnostic images and 40 hardware
taps rewriting a compressor block that was correct. Found by a LEVEL bisect
across the tracks (post-FX mute cleared it, pre-FX mute did not: the station
made it from state), then reproduced in one run once the instance block was
pre-filled with garbage. Rules: (1) init zeroes EVERY slot the sample loop
reads before it writes — `tools/verify/verify_dirty_state.py` (in `make
verify`) renders each module from a garbage block on silence and refuses any
output; (2) a channel-asymmetric failure in channel-symmetric code is a DATA
asymmetry — go looking for what the instrument cannot see (DC, ultrasonics)
before rewriting the code; a limiter ladder (×2/×4/×8 with the limiting
store) makes DC visible through an AC-coupled capture; (3) when "which knob"
does not localise a fault, "which TRACK" (LEVEL 0 per track, then AMP VOL vs
MUTE) does.

<a name="trap-brclr"></a>

### `dsp_asm` puts a label's absolute address in `brclr`'s displacement word

**`DSP_ASM` PUTS A LABEL'S ABSOLUTE ADDRESS IN `BRCLR`'S DISPLACEMENT
WORD.** `brclr #0,x1,usbi_nocd` at P:$1098 assembled to `0cc580 00109c`;
the chip reads the extension word as a displacement from the brclr (stock
payload A P:$63e: `brclr #$c,x1` is `0cc58c 00001d`, a branch to P:$65b).
The branch went to P:$2134 and core 0 ran off the end of P memory (the port's
FAULT: PC 0x80000). `bsr` and `do` encode right (`0d1080 000008` is +8).
The build's roundtrip did not stop it: a decoded label operand matches any
number in the listing. Fix: write `brclr`'s operand as the displacement, a
number (`brclr #0,x1,$4`), and check it against the listing's addresses.
Cost: one in-gate run (16 Oct 2026, USB inject). Gate: `verify_usb_in`'s
runtime rows (the DSP faults and no host sample lands).

<a name="trap-cs1-zero"></a>

### A zero CS1 with a valid settings tail boots stock's settings as zeros

**A ZERO CS1 WITH A VALID SETTINGS TAIL BOOTS STOCK'S SETTINGS AS ZEROS.**
`verify_usb`'s `cs1_block` wrote the early block into zeros and added the
valid tail, so the boot skipped its wipe and read every stock setting held
in CS1 as 0: on octabam-bus the input gain the ColdFire sends the DSP
(X:$x823, written at P:$369) was `030000` where a fresh boot sends
`030040`, and stock's input stage (P:$166-$1ff, the RX block times that
gain, back in place) wrote zeros over every injected block. `cs1_boot`
(16 Oct 2026) boots the image once with no CS1 file and dumps CS1 (the
boot writes 584,212 non-zero bytes of defaults); `cs1_block(...,
template=cs1_boot(image))` lays the early block over it. Cost: the
in-gate's runtime rows, a day of the USB merge. Gate: `verify_usb_in`'s
runtime rows (bit-exact RX blocks).

<a name="trap-in-slot"></a>

### `in_slot` lost its `lsll #5`: four packet buffers 3 bytes apart

**`IN_SLOT` LOST ITS `LSLL #5`: FOUR PACKET BUFFERS 3 BYTES APART.** When
INPUTS became a run-time setting, `in_slot` (usbaudio_in.s) kept the
`slot * 3` adds and dropped the `slot * 32` before them, so the four
queued 96-byte EP3 OUT buffers sat at SRAM_BUFS + 3n and each packet
overwrote the others. The RX blocks showed runs of samples a byte off
(`001158` where `01580x` belonged), some frames right: it looked like a
host-port or bank fault. Found by building the merged commit 1915559f in
a second worktree and running the same gate on the same remix: it passed,
so the cause was in the branch's image. Rule: when a gate that passed
fails after a refactor, run the old commit under today's tools before
reasoning about the hardware model. Gate: `verify_usb_in`.

<a name="trap-region7"></a>

### The stock echo-freeze mix rewrites the arena's region 7 every frame, from staging the tap check did not zero

**THE STOCK ECHO-FREEZE MIX REWRITES THE ARENA'S REGION 7 (THE TRACK-8
BLOCK OF BOTH BANKS) EVERY FRAME, FROM STAGING THE TAP CHECK DID NOT
ZERO.** The producer's t7 and MASTER read arena region 7; the stock frame
routine's mix writes it from its own staging at 0x800039a0/0x80003a40
every frame (byte stores at pc 0x400035c2, 96 a frame; halfword stores at
0x4000375e/0x40003764, 32 each; read back at 0x40003738). A gate that
pokes region 7 full of tap identities sees them overwritten before the
producer reads them, so the wire's t7/MASTER channels carry the mix's
values, not the poked taps, and the tap-identity check reports every src-7
position wrong. Fix: poke region 7 AND the staging zero — zero in, zero
out — and expect zero on the src-7 wire positions; tracks 0-6 keep full
tap identity. Cost: verify_usb's tap check failed until the overwrite was
measured (the watch told us exactly who writes the block). Rule: before a
poked-input check, ask what else in the frame writes the same block; the
write log answers it.

<a name="trap-post-cs1"></a>

### A gate that models a setting must boot that setting, and an empty run must report, not crash

**A GATE THAT MODELS A SETTING MUST BOOT THAT SETTING, AND AN EMPTY RUN
MUST REPORT, NOT CRASH.** verify_usb_post models TRACKS POST, but the
image under test (octabam-bus) resolves TRACKS PRE, and the gate's session
booted no CS1 early block — the producer never runs the POST path, so
post_state is never written, every frame's state is empty, `blocks` comes
out empty, and the SUM line crashed on `min()` of no diffs (a ValueError
traceback, which also hid the real failure: the RUN line never printed).
Two defects, both fixed: (1) the session boots a CS1 block holding
TRACKS=2 via `--cs1-in` (cs1_block from verify_usb, the same mechanism
the runtime rows already used — the mechanism existed and the gate just
was not using it); (2) an empty `blocks` reports the producer/MAIN/state
frame counts and fails the RUN line instead of crashing. Rule: a gate's
emulated session serves the image's resolved settings unless it boots an
early block; when a prerequisite watch captures nothing, the gate must
say which one, not die in analysis.

<a name="trap-bench-socket"></a>

### The bench socket is non-blocking: writeSocket dropped the rest of a large reply on EAGAIN

**THE BENCH SOCKET IS NON-BLOCKING: WRITESOCKET DROPPED THE REST OF A
LARGE REPLY ON EAGAIN.** A `writes` reply (449,543 records here) exceeds
the socket send buffer; `write()` returns EAGAIN and the old loop broke,
truncating the reply the gate then parsed. Fix: on EAGAIN/EWOULDBLOCK/
EINTR poll POLLOUT and continue (tools/emu/ot_emu/usb.cpp). Also: Emu.cmd
logs `r[:300]` — that truncation is display-only, the returned reply is
full; a short line in the port log is not a short reply. Rule: a socket
write loop that breaks on `n <= 0` truncates under load; poll POLLOUT.

<a name="trap-window-zero"></a>

### Window code above `0x37f00` is wiped at boot, and below `0x33da3` DARK REV can write it

**Seen:** 26 Oct 2026, the first demand-loading `octabam` under the port: both DSP cores faulted
at boot (`PC 0x80000 is outside P memory`, after a slide through zeros from the stub's first
dispatch) with the reverb guards and LOAD METER's DSP half at `0x3bda3..0x3ff00`.

**Cause:** payload B's boot zero loop clears `Y:0x37f00..0x3ffff` after the pre-boot upload
(`dsp_ranges.STOCK_PATCHES`), so an uploaded record there is zeros when the frame loop reaches it.
DARK REV on the slot at `0x30000` writes up to `0x33da2` (`stock.SLOT_EXTENT`), so words below
`0x33da3` in that block are not safe either.

**Fix and gate:** resident window code goes in `0x33da3..0x37eff` clear of the stock extents; the
build refuses an uploaded window record above `0x37f00`. The two clear gaps are `0x33da3..0x33fff`
and `0x37da3..0x37eff`.

<a name="trap-host-mask"></a>

### A host write at the frame interrupt's entry is lost on every other frame

**Seen:** 26 Oct 2026, the demand loader's pump under the port: a block sent 100 halfwords a frame
arrived in alternate chunks; sent only when `0x800000e0` is 0 it arrived whole.

**Cause (🟡):** payload B's frame loop stores `0x3fff` or `0x5fff` into the host handlers' address
masks (`p:$371`, `p:$380`) every frame from the bank word (`P:0x5f..0x72`). The lost chunks are
not at `X:0..0x3fff` of either core. Sending to core A at the entry also stops the stock ping
words alternating (core A's chain stalls); HC polling and a settle loop did not change it. A
receives the stock `0x8c` frame command and B does not.

**Fix and gate:** DLPUMP sends to core B on ping-0 frames only (`verify_dlload`). Whether the unit
loses the same frames is open.

<a name="trap-stock-x-scratch"></a>

### Payload B's frame routine writes `x:$3f7f..$3fbf` every frame, and the guard's base cells were there

**Seen:** October 2026, a unit (MKII). DARK REV picked on T4's FX2 while MODULATION's code was in T4's
block stopped the DSP frame loop within about 4 ms of the pump's withdrawal: 3 of 3 on the first
three images, and on every later build in which the guard resumed a dry reverb and the stock proc
ran. The port did not reproduce it.

**Cause:** payload B's frame routine calls `func_00034f` at `P:0x7a` every frame with `r0 = $3f80`,
`r1 = $3f00`. It reads `x:$3f00..$3f20` and writes 65 words at `x:$3f7f..$3fbf` (`mpy`/`mac`
results split over `a1`, `a0` and `b0`). The guard kept each instance's buffer base at
`x:$3f90 + idx` (T3 idx 40 = `x:$3fb8`, T4 idx 43 = `x:$3fbb`), so the stock overwrote it every
frame, and the resume ran DARK REV's init and proc with that scratch value as the base. Payload A
writes only `x:$3f80` and `x:$3f81`: T7 and T8 were unaffected.

**Measured on the unit:** with a probe on a core B track, `x:$3fb8` read `$ffb754` after a reboot and
again after the guard's init stored the allocator entry's contents there; the entry (`$25a`)
held `$38000`. With the state words at `x:$3dc0 + idx` and the base cells at `x:$3e00 + idx`, the
probe read T3's base `$038000` and T4's `$03c000` (entry `$25c`), and the sequence that stopped the
DSP on every earlier build ran three times with no stop.

**Fix and gate:** `dlwrap.asm` keeps the state words at `x:$3dc0 + idx` and the base cells at
`x:$3e00 + idx`. `verify_dlwrap` seeds those cells (200 checks). The port cannot show this trap:
`dsp_host` does not run the stock frame routine.

**Not established:** what `func_00034f` computes. The stub's flags at `x:$3f00..$3f3f` are its
input. No search for other writers of `x:$3dc0..$3e3f` beyond the unit runs.

Rule: before putting per-instance state in X, read what the stock frame code writes there, and read
the cells back on a unit.

<a name="trap-bra-back"></a>

### `dsp_asm` does not assemble a backward `bra`, or `jmp` to a window address

**Seen:** 26 Oct 2026: `bra proc` to an earlier label failed (`InvalidInstruction -- "bra -$51"`)
and `jmp proc` at `P:0x33e2b` failed; the sizing pass then drifted.

**Fix:** put trampolines before the code they enter so the branch is forward, or load the address
into a register and `jmp (rN)`. Dispatch entries must keep `init < proc <= init + 256`
(`send_probe.entry_points`).

## Traps on the ColdFire / DRAM side (the platform work, 9–10 Sep 2026)

<a name="trap-part-engine-context"></a>
### Audio and MIDI have independent playing-Part latches

**Symptom:** a MIDI consumer reads the wrong Part while the audio and MIDI
engines are on different track contexts. Fixtures that put both engines on
one Part conceal the error.

**Cost:** the native Part service migration exposed an audio-latch lookup in
the old shared MIDI helper; Loopback had separately implemented the MIDI lookup.

**Fix:** STORE exposes separate `store_part_audio_context` and
`store_part_midi_context` readers. MIDI clients use the latter. Each falls back
to the applied bank/Part only while its own track is unlatched.

**Gate:** `verify_store_part.py` seeds different audio and MIDI contexts,
checks all eight tracks and tests each fallback independently.


<a name="trap-watch-alias"></a>

### A write-watch on cached addresses is blind to a clear through the uncached alias

**A WRITE-WATCH ON CACHED ADDRESSES IS BLIND TO A CLEAR THROUGH THE UNCACHED
ALIAS.** The port mapped `0x4F...` as separate memory, so a watch on
`0x477...` reported "8.8 MB free at 0x47700000" — the region is the stock
delay's eight rings, cleared via the alias ~38 M instructions after the boot
detour returns (Bryan's write-up had the ring base as `0x4F502C10` all
along). Retracted; `machine.h` now folds the alias. The general rule is the
instrument-blindness one: before trusting a null result, ask what the
instrument physically cannot see, and check whether a second reading
(here, Bryan T's delay write-up, `docs/firmware/COLDFIRE_DELAY.md`) already
contradicts it.

<a name="trap-boot-verifier"></a>

### The boot verifier booted the wrong image

**THE BOOT VERIFIER BOOTED THE WRONG IMAGE.** `make verify` runs after the
selftest, which builds every remix in turn and leaves the LAST one at
`out/mainos_bus.bin`; the first in-pipeline run booted `warped` looking for
midi-scenes' loader and reported "loader ran 0x". `verify_dram_boot` now
rebuilds its remix first. Any verifier that reads `out/` must know who wrote
it last.

<a name="trap-pipe-exit"></a>

### `make … | grep | tail` reports tail's exit code, not make's

**`make … | grep | tail` reports tail's exit code, not make's.** Capture
with `> log; echo $?`.

<a name="trap-gnu-as"></a>

### Matching an author's bytes with GNU as

**Matching an author's bytes with GNU as:** a same-unit label makes `lea`
assemble PC-relative (write `lea SYM:l`); small `move.l #imm` becomes
`moveq`; a `-Ttext` that is 2 mod 4 gets a leading `nop`. All correct code,
all oracle failures.

<a name="trap-loader-regs"></a>

### A loader draft clobbered d0 across its copy loop and reused a0 after the hash

**A loader draft clobbered d0 across its copy loop and reused a0 after the
hash.** Register discipline in a boot stub is not checkable by anything but
the port: `verify_dram_boot` watches the loader's entry and its `fatal` hang.

<a name="trap-word-fixture"></a>

### The memory word-count fixture can race reach and shard snapshots

The DSP memory word counter (`tools/remix/state.py`) writes a temporary
`remixes/_words.py` while it builds measurement images. On 16 Oct 2026,
`reach.py` read it as a changed remix and `check_shards.py` copied it into
a shard just as the shared gate removed it. The planned `_words` check then
failed with "no remix '_words'". Ignore that generated path: it is a build
fixture, not a user selection. Its ignore rule keeps it out of both reach's
untracked-file scan and shard snapshots.

<a name="trap-work-file-ram"></a>

### A bank-file fixture edits the file; the firmware parses it into a different RAM layout

**A bank-file fixture edits the file; the firmware parses it into a
different RAM layout (16 Oct 2026).** `verify_scenes` seq fixtures patch
`bankNN.work` (a trig bitmap at file MTRA+9, 8 bytes big-endian, bit 0 =
step 1), and the loader parses the file into a RAM structure whose offsets
differ (the parsed trig mask is at pattern `+0x48d7`;
`docs/firmware/MIDI_SCENES.md` section 12). Reading a RAM-side offset as a
file offset, or the file layout as the RAM layout, writes the wrong bytes
and the scenario plays the project's own trigs: `swd`'s first runs
measured the original trigs, not the fixture's. Anchor every fixture edit
to a known-good write (the `swn` notes fixture) and take RAM addresses
from the routine's own arithmetic (direct_jump.s), not from the file
layout.

<a name="trap-tmp-race"></a>

### Two builds on one machine corrupted each other through fixed `/tmp` names

**TWO BUILDS ON ONE MACHINE CORRUPTED EACH OTHER THROUGH FIXED `/tmp`
NAMES (10 Sep 2026).** `build_bus.assemble()` wrote `/tmp/build_bus_src.asm`,
`.bin` and `.sym` by fixed name, so two sessions' `make check` — or the
selftest's per-remix builds beside anyone else's build — read each other's
assembler output: "STREAMZ overruns the region (2883 > 2724 words)",
"selprobe dsp_asm exit 1", a different remix each time, on a clean checkout
too. Found by a peer session. Scratch is `tempfile.mkdtemp` per process now
(`verify_hello` likewise). A failure that moves between remixes across runs
is a shared-scratch race before it is anything else; and a `make check`
result taken while another build was running is not a result.

<a name="trap-stock-callee"></a>

### A module that replaces a stock routine can make every other caller of it a halt

**A MODULE THAT REPLACES A STOCK ROUTINE CAN MAKE EVERY OTHER CALLER
OF IT A HALT.** Em's Octakit (in octabam until 6 Oct 2026) repointed the
three stock calls to the page-1 writer `0x40054cd8` at her wrapper and
made the writer's dirty store check a token above its arguments; TEMPO
BUS and MODE DEFAULTS called the writer bare, so `bottleservice` halted
under the port at frame 40 of `verify_set` on the first CC 68 (26 Sep
2026; never flashed). Before calling a stock routine from a module, diff
the routine and its callers against stock in the built image
(`tools/build/where.py`): another module may own it.

<a name="trap-fork-shm"></a>

### A forked port shares its DSP memory with its siblings unless it is unshared

**A FORKED PORT SHARES ITS DSP MEMORY WITH ITS SIBLINGS UNLESS IT IS
UNSHARED.** The vendored DSP memory is a `shm` object mapped `MAP_SHARED`
several times (the bridged X/Y/P views, `dsp56kBase/mmuhelper.cpp`), so
`fork()` gives every child the same DSP memory: the first `--scenario`
run (29 Sep 2026) faulted a core in two of three children, PC outside P,
while the third ran clean. `unshareRanges` in `tools/emu/ot_emu/main.cpp`
copies each backing object into a private one after the fork. Anything
new the port maps shared (a window, a ring for the host) needs the same
treatment, or the children interfere and the failure moves between runs.

<a name="trap-rosetta"></a>

### The port ran under Rosetta in every shard, and nothing said so

**THE PORT RAN UNDER ROSETTA IN EVERY SHARD, AND NOTHING SAID SO.** `make
reach` and `check_shards.py` run under `python3`; on this machine that is
Intel Homebrew's (`/usr/local/bin`), and under it `uname -m` and
`os.uname().machine` both say `x86_64`, so cmake built an x86_64 `ot_emu`
that ran translated: 1.27x slower to the handoff, 1.75x on DSP frames
(6 Oct 2026, both binaries side by side under the same load). The
Makefile's `HOST_ARCH` and `check_shards.host_arch()` ask the kernel
(`sysctl -n hw.optional.arm64`, the same answer under Rosetta; Linux keeps
`uname -m`). `file out/emu/ot_emu` is the check; `make check-asm` prints
the binaries' architecture.

<a name="trap-report-api"></a>

### The report is API, and it prints paths

**The report is API, and it prints paths.** Moving a tool changed the build
report (the hints name `tools/harness/send_probe.py`), which refhash
correctly flagged with every artifact identical. Re-save only after proving
the artifact lines match.

A module that gains or loses `replaces` moves between the build report's
"not in this remix, LEFT STOCK" and "not in this remix" lines in every case.
The cases that exit non-zero (`plain`, `marker`) have the report as their only
line, so `tools/verify/refhash_compare.py` compares their logs with those two
lines masked; any other difference in a refusal still fails.

<a name="trap-stock-fallback"></a>

### Id 0 is FX1 NONE too: a stock fallback ran on every empty FX1 slot

**ALIASING ID 0 TO AN EFFECT RUNS IT ON EVERY EMPTY FX1 SLOT, NOT ONLY ON A
FRESH FX2.** `fallback="FILTER"` passed the schema, then crashed the build
(`fb_init` unbound) once a registry module was left out. A fix that pointed id
0 and the omitted ids at FILTER's stock entries built, and on the unit the
sequencer held its first step at play (27 Oct 2026); the same selection with
`fallback="NONE"` played. SEND had the same exposure and needed its FX1
guard (`FAILURE_MODES.md`, "id 0 is SEND"); a stock effect has none. Rule:
the fallback is `NONE`, `SEND` or a module written for an FX1 r7;
`registry.remix` refuses a stock effect. Gate: `selftest.py` probes the
refusal.

<a name="trap-nm-order"></a>

### Same-named labels across DRAM units resolve by nm table order

**Same-named labels across DRAM units resolve by nm table order.** The
platform runtime served every unit's refs and detours from one flat symbol
table of the whole link; `_nm` collapsed same-named symbols by nm output
order, so three units each defining `cave` (TEMPO SYNC's global, RECORDER
LOOP FIX's local, RLEN PLEN's local) resolved to whichever definition the
merge happened to leave last. Merging the four USB modules into one (15
Oct 2026) flipped that order and the record writer's per-frame `jsr` was
wired into RECORDER LOOP FIX's spacing code; verify_brain stormed to the
auto-map limit (busiest pc 0x40004c40 x4194177). The base image was
correct by table-order luck. The fix: `link_runtime` builds a per-unit
symbol table from each unit's own object (`objdump -t`) placed by the
link's `-Map`; a detour or ref naming a symbol its unit does not define
is refused. `test_linked_defsyms.UnitTableTests` pins the scoping;
`scripts/refhash.sh` proves the change moved no image.
<a name="trap-first-sector-irq"></a>

### A completion interrupt in the first-sector write window polls DRQ on a count the producer has not updated yet

**A COMPLETION INTERRUPT IN THE FIRST-SECTOR WRITE WINDOW POLLS DRQ ON A
COUNT THE PRODUCER HAS NOT UPDATED YET.** Stock's first-sector PIO write
saves SR in d0 and raises the mask to 7 (`0x40014cdc`), issues the WRITE
(`0x40014ce4`), then restores SR at `0x40014cf2` — before sending the 256
data words and before the `0x40014d38..52` update of the buffer pointer
`0x46c8c594` (+512) and the remaining-sector byte `0x46c8c592` (−−).
Preempt the engine after the final word (observed exception PC
`0x40014d34`, TCB `0x460ddde4`) and the completion IRQ runs in sys with
count 1 and the old pointer: the card already finished the command (status
`0x50`, DRQ clear), so the handler polls DRQ at `0x4001551e/24/26` forever
and the lower-priority engine never resumes to fix the bookkeeping. Cost:
the octabam-inserts loadmeter gate hang on 14–15 Oct 2026 and days of
falsified leads — server-name parser, packed-stage residue in BRAIN
scratch, lazy DSP batching, card latency — each measured and dismissed
under the port. Fix: retain the saved SR in d3 at `0x40014cf2` and detour
the first-sector return `0x40014d58` to a ten-byte DRAM stub that restores
SR and replays the stock epilogue, keeping the sector and its bookkeeping
inside the mask that was already there (the ATA WRITE GUARD module).
`verify_ata_write` runs the actual routine in the ColdFire Machine with a
level-5 interrupt forced at the final data word, and gates the stock
control against the guarded bookkeeping at caller masks 0/1/3/5/7.
Measured under the port; whether the window occurs with real card timing
is NOT measured — the guard is not hardware-proven. Rule: an
interrupt-mask restore that precedes the data it protects is a window;
before blaming names or parsers, ask what the IRQ handler reads while the
producer is mid-update.


<a name="trap-id-clamp"></a>

### The stock Part validator clamps a stored FX2 id to 31

**THE STOCK PART VALIDATOR CLAMPS A STORED FX2 ID TO 31.** The 64-id layout
moved the dispatch tables and the ColdFire id and position tables, and the port
passed with an id of `0x25` poked into the live slot (`make check REMIX=ids64`).
A project that stored `0x25` for BBD loaded on an MKII (image `ids64-usb`, 27 Oct
2026) with nothing on FX2. The Part validator at `0x40002318` runs as the project
loads and clamps each track's FX1 and FX2 id byte with `moveq #31`: FX1's at
`0x400023b6` and `0x400023bc`, FX2's at `0x400023de` and `0x400023e4`. `0x25` became
`0x1f`, an id no module holds, which shows as an empty slot. A poke goes
straight to the live id and never meets the validator; the same project under the
port read `0x1f` too, so the port would have shown it from the start with a
project and not a poke. Cost: two image builds and two flashes. Fix:
`idspace.convert` rewrites the two FX2 immediates to 63 (the table lookup the
validator does next, `0x40002406`, was already one of the repointed `lea` sites);
FX1's stay at 31 because FX1's tables keep 32 entries. `verify_ids64_load` loads a
project file that stores `0x25` under the port and reads the live id (it skips
when there is no project, as `verify_dlload` does). Measured on the unit after
the fix: BBD shows on FX2 and runs on core A and core B. Rule: an id or any index
that a layout change makes legal must be run through the project load, not
poked, because the load validates every stored byte.

<a id="trap-popup-redraw"></a>
### A nonzero popup pointer is not an open FX SETUP window

PLOCKS page-two edits changed the lock bytes without repainting SETUP;
the memory/persistence gate passed while the hardware display remained
stale (16 Oct 2026). Native trig-down only conditionally redraws the main
page, and that redraw does not repaint the SETUP popup. Refresh the native
FX window after trig bookkeeping and edits, not just after a page redraw.

`0x460d175c` points at a shared popup object used by MIXER, TEMPO and
other dialogs too. Check its active pointer, open flag and SETUP geometry
before calling the FX draw callback. `verify_plocks_p2` now compares UART
LCD pixels with normal-value references, exercises reholding without a
knob turn, and checks the other windows. A lock-byte assertion alone
cannot establish that a user can see the edit.

<a name="trap-movem-sp"></a>

### `moveml %sp@` is the mode-2 form: it stores at sp and leaves sp unchanged

**`MOVEML %SP@` IS THE MODE-2 FORM: IT STORES AT SP AND LEAVES SP
UNCHANGED — A SAVE/RESTORE PAIR WRITES OVER THE CALLER'S LIVE FRAME.**
GNU as encodes `%sp@` (address-register indirect) as mode 2, no
pre-decrement, so `moveml %d0-%d7/%a0-%a2,%sp@` stores the 44 bytes AT
sp: [sp+12] is the caller's return address, clobbered by d3's slot, and
the restore reads the same wrong place. The four cfgsel responder stubs
(usbaudio.s) saved registers this way across the cfgsel re-run
(usb_cfg_ready 0: brain, block not valid yet) and corrupted the
control-transfer handler's frame. The fix is the module's lea-framed
idiom (usbmidi_rx.s): `lea %sp@(-44),%sp` before the moveml pair and
`lea %sp@(44),%sp` after — the movem writes into the reserved space and
sp round-trips. verify_usb's runtime rows exercise cfgsel with the block
invalid (the brain rows) and valid. Rule: a register-save movem through
sp needs either `%sp@-`/`%sp@+` or the lea frame; `%sp@` alone is a write
over the live frame.

<a name="trap-cfgsel-nch"></a>

### cfgsel served one MAIN and one CUE short of the declared channel count

**CFGSEL SERVED ONE MAIN AND ONE CUE SHORT OF THE DECLARED CHANNEL
COUNT.** The sum over the six settings added usb_main and usb_cue ONCE
each, so nch = 16 × TRACKS + MAIN + CUE + 2 × MASTER: the 20-channel
combo (TRACKS MAIN CUE) served 18 channels' worth of frame bytes while
AS_GENERAL declared 20, and the 22-channel combo 20. usb_nch is the single
source for the frame bytes (nch × 4), the high-speed cap and step
(≤ 20 channels polls at 250 µs, 22 at 125 µs), and the interface set, so
the descriptor shape and the frame loop disagreed on every channel-count
dependent word. Fix: nch = 16 × TRACKS + 2 × (MAIN + CUE + MASTER).
verify_usb's runtime rows pin the served geometry per row (geom), the
22-channel row the bInterval-1 endpoint. Rule: when a sum over the six
settings feeds descriptors AND a frame loop, the per-setting factor is the
one thing every consumer must agree on — check each term against the
descriptor it builds.

<a name="trap-producer-stride"></a>

### At .Lf_nomaster the branch was inverted: TRACKS OFF advanced 24 bytes of an 88-byte slot

**AT .LF_NOMASTER THE BRANCH WAS INVERTED: TRACKS OFF ADVANCED 24 BYTES
OF AN 88-BYTE SLOT.** The slot is the tracks field (64 bytes, written
only when trk != 0, through %a3@+ stores that advance a3 as they go) plus
the rest (24: MAIN/CUE/MASTER). trk != 0: a3 already sits at +64 from the
stores, so the walk adds the rest. trk == 0: nothing advanced a3, so the
walk must add 64 + 24. The old `beqs 2f` skipped the 64-byte lea exactly
when nothing had been written, landing every following frame's ring
writes 64 bytes early — tap identity garbage across the whole stream. Fix:
`bnes 2f`. Related, in the same producer: TRACKS OFF fell through into
PRE's bounds/gain pointer setup; the early return is `beq.w 7f`. verify_usb's
tap-identity check and verify_usb_post's per-frame ring reads both pin the
slot layout. Rule: a conditional slot advance is a walk of WHAT WAS
WRITTEN — the branch condition must name the write, not the setting.

<a name="trap-watchmem"></a>

### `--watch-mem` is one string: a second flag replaces the first

**`--WATCH-MEM` IS ONE STRING: A SECOND FLAG REPLACES THE FIRST.** The
argument parser stores the flag's value into one slot
(`watchMem = _argv[++i]`, tools/emu/ot_emu/main.cpp), and Rtos::watchMem
only ever adds ranges — nothing removes one. A batch run passing
`--watch-mem` twice silently watches only the last range, and the gate
reports on a range it never watched. Rule: one comma-joined
`--watch-mem addr,len;addr,len` argument; when a watch captures nothing,
check what the command line actually watched before suspecting the
runtime.

<a name="trap-frame-count"></a>

### A frame count past $7fffff reaches `move a,n1` with A2 stale, and a frame engine that stops after 50.7 minutes

**A COUNT WITH BIT 23 SET, LOADED INTO A AND MASKED, LEAVES A2 AT $FF AND
`move a,n1` LIMITS.** Core 0's frame count in `dsp_meter.asm` indexed the 16
OTOP cost cells (`move x:(r1+6),a / and #>$f,a / move a,n1`, then
`move x:(r1+n1),a`). At 8,388,608 frames the load sign-extends A2 to $FF,
`and` leaves it (`trap-a2-stale`), and the move limits n1 to $800000: the
cost read goes to a wild address. The unit's frame interrupt and every
counter on it stopped 8,388,607 frames after power-up (3,043.6 s at
2,756.25 a second), on an idle unit, twice (24 Oct 17:23, 25 Oct 07:41). The
port reads zero at the wild address and goes on; the OTOP costs after the
crossing are zero. Inferred, not measured: that the read stalls the core on
the unit (an image with the count preset, Q1, stopped within seconds of boot;
Q2, with the wrap below, did not).
- Fix: `and #>$7fffff,a` after the add keeps the count below bit 23 (2^23 is
  a multiple of 16, so the slot index continues).
- Located by presetting: the ColdFire seq preset to 8,388,000 (P1) stopped at
  8,388,607 records from boot, so the stop followed the DSP count and not the
  ColdFire seq.
**Gate:** `verify_load_meter` `wrap` (`LM_FRAME0` = 2^23 - 1000; `--wrap-only`
runs just it): every OTOP slot sampled and the costs read (heaviest slots 1
and 9, core 0 sum above zero). Without the `and` the sum is 0. A counter
that must outlive 50 minutes at 2,756 a second needs a preset test.

<a name="trap-ep0-dma"></a>

### An EP0 reply is DMA'd from memory the CPU's cache may not have written, and one of 64 bytes breaks the next request

**A CELL THE CPU STORES RARELY STAYS STALE FOR THE USB DMA, AND A CONTROL REPLY
OF A MULTIPLE OF 64 BYTES MAKES THE NEXT REQUEST RETURN 0 BYTES.** Both found
on the first unit run of vendor request `0xc0/0x57` (24 Oct 2026), both clean
under the port.
- `lm_stats` is stored once in 0.5 s; the controller reads RAM, not the
  copyback cache, so the request returned the same window for minutes and then
  jumped 100 windows at once, while `lm_dsp` and `lm_ot` (stored every frame)
  looked live. The reply is now copied into `lm_reply` through the uncached
  alias (`+UNCACHED`) and sent from there, the rule `usbaudio.s` states at the
  rings.
- A reply of 64, 128, 192 or 256 bytes left the next control request returning
  0 bytes once (63, 100, 252, 255 did not): `tools/hw/load_meter.py` alternated
  success and failure per process. The request now sends a byte short and the
  host resumes from `wIndex`.
**Gate:** `verify_usb_load_meter` checks the lengths and the offset; the port
cannot see the cache or the stale status, so a unit run (`load_meter.py`
repeated, `--for 10`: `windows` near 20) is the check.


<a name="trap-cave-round"></a>

### A floating cave rounded past the clone window landed on the chooser list

**THE OVERFLOW FALLBACK ASKED WHETHER THE CAVE STARTED INSIDE THE WINDOW, AND
THE ROUNDING HAD ALREADY MOVED IT OUT.** A floating cave starts at the clone
window's cursor rounded up to 128 bytes. `build_bus` sent one that ran past
`cave_limit` to the overflow run at `0x400d24d0`, but only if its rounded start
was still inside the window. A 57-module selection (26 Oct 2026) left the
cursor at `0x400d7b9e` with the long chooser list at `0x400d7bbc`; the round
put BATCH_BUGFIXES' 402-byte `PART_CHANGE_CARRYOVER_FIX` at `0x400d7c00`, on
the list, so it was neither moved nor bounds-checked and the build stopped at
`PART_CHANGE_CARRYOVER_FIX not free`, which names the victim and not the
cause. Fix: a floating cave goes to the overflow run when it ends past the
limit, wherever it starts, and one that fits neither region is refused with
both regions' ends. Past `0x400d7c3c` the stock image is data (the first byte
is nonzero), so no image that built before should move (inferred; `refhash`
is the measurement, and a 64-id build is the case to watch: its
`idspace.CAVE` limit sits below zero bytes the id tables fill only at the
end). Gate: none of its own; the refusal names both regions.

The run's own first bytes are not free either: the stock DELAY reads the 16
past its coefficient table (`stock.DELAY_TABLE_END`, issue #771), and the
first form of this fix put the cave on them in a selection listing DELAY (the
kept-bytes check refused it: `DELAY keeps 0x400d24d0`). The overflow cursor
now starts past every byte a selected module keeps stock in the run.

<a name="trap-dram-clone-stage"></a>

### A DRAM clone's `CLONE_<key>` export is its staging address

**WITH A DRAM RUNTIME, `_exports["CLONE_<key>"]` IS WHERE THE CLONE IS BUILT,
NOT WHERE IT LIVES.** The clones are written at a staging address past the
image and every staged pointer is repointed to the runtime's `CLONE_<key>` at
the end (`_rt_patch`). The MODE-renames formatters are DRAM units linked
against the runtime's symbol, but the check that each equals its `emit()`
resolved the descriptor from `_exports`: STUTTR's `lea` was `0x40ae6f4e` in
the runtime and `0x40130836` in the emit, and the build refused with `the
linked label formatter ... differs`. No committed remix carries MODE renames
with DRAM clones; a selection with STUTTR, SPECTRUM and CHARACTER TXTR beside
MEMORY and KITS (26 Oct 2026) was the first. Fix: the check resolves a
module's own clone from `_psyms`, the runtime link. Rule: before comparing an
address from `_exports` with one from the runtime, ask whether the staging
repoint has run yet. Gate: the comparison itself, now that both sides are the
runtime's.

<a name="trap-machine-clamp"></a>

### The machine list's key handlers clamp the cursor to 5

**A SIXTH MACHINE ROW FITS BY ACCIDENT; A SEVENTH NEEDS TEN MORE POKES.** The
track's machine list (`0x460e7386`) has a row count (`pea 5` at
`0x40079248`), a draw bound, a highlight bound and a commit bound, and ANALOG
BD, OCTA303 and BLACKPYRAMIDS_303 each poke those four from 5 rows to 6. With
seven rows (HOOKS `machine_rows`, ANALOG BD and OCTA303 together, 28 Oct
2026) the list drew and scrolled, but the cursor stopped on row 5: each of
the list's five key handlers (`0x40078c22`, `0x40078cb0`, `0x40078d2e`,
`0x40078dee`, `0x40078e7c`) clamps the cursor to 0..5 after moving
(`moveq #5,%d1 ; cmp.l %d0,%d1 ; bge.s ; moveq #5,%d0`), one past stock's
last row, so a single added machine never met it. The search was confused
by a second effect: a port script's key held for 0.25 s auto-repeats, so a
single UP moved two rows and landed on PICKUP. Fix: HOOKS pokes both
`moveq`s in each handler to 6; the gate presses UP for 0.06 s. Rule: when a
list grows, find every constant near its old size in the code that touches
the list (a byte search for the clamp found all five), and in a port script
hold a key only as long as you mean it to repeat. Gate: `verify_hooks`
(installed: the ten pokes) and `verify_analog_bassdrum_ui` on
`hooks-machines` (row 5 reached from the bottom of seven).

<a id="trap-resident-import-exports"></a>
### Resident relinking must not publish imported staging symbols

A remix combining MIDI Part State and EUCLID failed the linked label-formatter
byte check: EUCLID's final descriptor address was replaced by its earlier
staging address. The resident unit's second link included imported `--defsym`
symbols in its global `nm` output. Publishing those as its own exports overwrote
the runtime provider's final `CLONE_*` addresses.

Keep imported symbols available to the resident link, but exclude them when
publishing its exports. `make check REMIX=midi-follow-events` exercises the
combination, including the build's formatter-byte and installed-image checks.

<a name="trap-dma-arm"></a>

### Narrowing the port's DMA arm rule broke a gate whose image never moved

**A CHANGE TO THE PORT CAN FAIL A GATE THAT CI THEN REPORTS AS A CACHED PASS.**
`716e682` (28 Oct 2026) narrowed `dsp56300.patch`'s arm rule: a DMA channel
armed with its request already raised fired at once only for the two host
interface sources, where `ot_emu` had set `setDmaTriggerOnArm` for every source
(the Octatrack arms its ESAI channels long after the ESAI raised the request).
`verify_remix_switch` passed with both rules; `verify_rec_threshold`'s `late`
scenario did not: the recorder took the input from a stale page, and the take
held no numbered sample within the detection frame (first sample `None`;
10 with the old port, the same image and script). Nothing showed it for a day:
the gate's image and inputs had not moved, so CI reported the gate cached, and
it surfaced only when REC THRESHOLD joined `octabam` (#964). Found by building
the port at `8ccdd843`, at `9490cce` and at main against one image. Fix: the
revert of `716e682`. Rule: a change to `tools/patches/` or `tools/emu/` is a
change to every port gate's instrument -- run the port gates of the modules
whose behaviour leans on the changed rule (here, anything reading the ESAI's
input pages), not only the one the change was made for. Gate:
`verify_rec_threshold` and `verify_remix_switch`, both under the reverted port.

<a name="trap-cf-frame"></a>

### A ColdFire save frame sized for the wrong register count overwrites the return address

**A COLDFIRE SAVE FRAME SIZED FOR THE WRONG REGISTER COUNT OVERWRITES THE
RETURN ADDRESS.** ColdFire `movem` has no pre-decrement or post-increment
form, so a stub opens `lea -N(%sp),%sp / movem.l regs,(%sp)` and closes the
same way, and N is 4 per register. PATTERN MUTE's first build used 28 for
eight registers and 32 for nine: the stub's `rts` returned into data and the
port stopped with `unimplemented opcode 00ff at 401715c1` (odd PC) during
LOAD PROJECT, caught by `verify_set`, not by the stub's own gate. The same
build hit three more ISA-C restrictions the assembler reports as `operands
mismatch`: `eor.l <mem>,Dn` (eor takes Dn as the source), `st <mem>` (Scc
takes Dn) and `move.b #imm,<abs.l>`. Rule: count registers, then multiply by
four, once, in a comment next to the frame.

<a name="trap-unused-bytes"></a>

### An unused-looking project byte can be rewritten on save

**AN UNUSED-LOOKING PROJECT BYTE CAN BE REWRITTEN ON SAVE.** In the test
project the four bytes after the pattern chunk's flag byte were zero in all
256 patterns, and offsets 95, 2150 and 2200 of every audio track record were
zero in all 2,048 records. A SAVE PROJECT round trip with marker bytes there
returned `0xff 0x00 0x00` for the first three (the OS writes them from its own
fields) and `0xff` / `0xe9` / `0xe9` for the others. Offsets 18, 40 and 85 of
the audio track record came back unchanged in all 128 records of the bank.
Rule: zero everywhere is not proof a byte is spare; write a marker into the
file, load, save, and diff (`tools/verify/verify_pattern_mute.py` does it for
byte 40).

<a name="trap-scenario-watch"></a>

### `--watch-mem` given to a `--scenario` child logs nothing

**`--WATCH-MEM` GIVEN TO A `--SCENARIO` CHILD LOGS NOTHING.** A forked scenario
accepted `--watch-mem 0x80000008,4` and reported `0 write(s)` while the same
script run directly logged the writes with their PCs. Measure writer PCs with a
direct run (one script, one process); use scenarios for `--mem-dump` end
states.

<a id="trap-midi-only-frame-fixture"></a>
### A MIDI-only fixture can leave audio frame checks with no playing Part

A short Scenes P2 frame probe on a MIDI-only project read unchanged knob values:
all audio tracks' native playing-Part pointers were `0xff`, so the scene pass
correctly skipped them. The probe ended before its injected step-2 trig. In an
EUCLID composition the old MODE/TIME assumptions also did not describe the
selected effect's page-two controls.

`verify_scenes_p2.py` prepares the disposable EUCLID fixture with T1 active on
step 1 and checks RATE/MIX as its discrete/continuous pair. Knob values are kept
away from the edit clamp. The supplied project is unchanged. Check the playing
Part and the selected module's real parameter layout before interpreting a
constant frame value as a failure of event dispatch or scene interpolation.

The same MIDI-only input exposed an unstated BRAIN fixture dependency: its
save/menu probes expected T1 FX2 to be DELAY SERVER, but only seeded T2 FX1.
Saving T1's actual effect correctly produced no BusDelay record. `verify_brain.py`
now seeds both required effects in its disposable copy. Prepare every effect
whose identity a later assertion assumes, rather than inheriting it from the
operator's project.
Its MIDI logging probe also explicitly enables program-change reception on
channel 1 in a separate copy before asserting that the message queues a pattern.

BRAIN's gate builds its own `octabam-bus` image, so it belongs to the shared
isolated stage. Running it as an image gate replaced the selected Follow image
and made later Scales/Loopback gates fail on missing symbols. Declare gates that
build another image as isolated; `verify-remix` then restores the selected image
before its image gates run.
