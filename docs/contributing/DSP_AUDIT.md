# DSP audit: shorter, cheaper code for the same output

This register checks every module's DSP code for changes that make it
shorter or cheaper and leave its output **bit-identical**. It records three
things: the techniques to look for, how each module is built, and what each
module's audit found. It grows as the audit goes: a technique found in one
module becomes a check for all of them.

- **Started:** 19 Nov 2026, on main at `cc7cffc1`.
- **Instruments:** the cycle model `tools/build/interlock_scan.py`
  ([CYCLE_SCAN.md](CYCLE_SCAN.md)), `dsp_host`'s instruction count, and
  `dsp_asm`'s word count. The model reads 3.0 % above the unit on average
  (CYCLE_SCAN.md section 1). Every cycle figure here is **modelled** unless it
  says otherwise.
- **The identity gate:** `tools/verify/verify_ident.py`, widened for this
  audit (branch `ident-wide`): the module's own slot, the other slot, payload
  B, 16-sample blocks, a 2 s run, a knob ramp, stereo, the split call, and the
  instance block compared after every block.

## 1. Method

### The procedure, per module

1. **Profile.** Read the manifest and the source. Fill the module's row of the
   construction matrix (section 3).
2. **Scan.** Take the dearest setting's sites from the baseline scan
   (section 7). Place each site on its label and source line.
3. **Checklist.** Run every row of section 2. Rows marked S come from the
   scan, rows marked G from a search of the source, and rows marked R from
   reading the sample loop end to end.
4. **Record.** Write one finding per site, or per family of sites, in
   section 4. Give the row id, the saving, the proof class and the risk.
5. **A new technique.** When a saving fits no row, add a row to section 2,
   raise the checklist version, and carry on with the current module.
6. **Stamp.** Write the checklist version the module was audited against.

**Pass 2.** When the checklist has grown, every module with an older stamp
is checked against the new rows only. Passes repeat until one adds no row.

### What a finding records

- **Saving:** cycles a sample at the dearest setting (the model), and words.
  Instructions a sample are given too, because the module READMEs use them.
- **Accept rule:** a change is taken when it saves cycles and adds no words,
  or saves words and adds no cycles. A change that trades one for the other
  is "not taken", with both numbers; Yves decides those.
- **Proof class:**
  - **I** (identical): the same arithmetic in another order or spelling. The
    identity gate proves it.
  - **F** (new form): as I, but the change needs an instruction form no stock
    site runs. It needs a ⏳ row in the instruction-form register
    (`docs/firmware/CHIP.md`), as #1080's forms had.
  - **U** (needs the unit): the output is the same only if the chip behaves as
    the port does, such as an offset past a modulo buffer. Not taken in this
    round.
  - **O** (changes the output): a bug or a better design. Reported to the
    author, not fixed here.
- **Status:** open, taken (with the PR), not taken (a trade), needs the unit,
  or reported.

### Rules every rewrite keeps

From MODULATION's parallel-move pass (`86f76efd`) and
[MODULES.md](MODULES.md) "Rules for DSP code":

- No dependency broken, and no address-register write moved closer to its use.
- Two data moves between writing an address register and using it; no M
  write in the sample loop.
- `x:(rN+d)` is never a parallel move; an XY dual move needs X through R0 to R3
  and Y through R4 to R7.
- The traps that bite a rewrite: `trap-asm` (disassemble what you assemble),
  `trap-move-tfr`, `trap-a2-stale`, `trap-tcc-pair`, `trap-lua` (a `lua`
  displacement is -64 to 63), `trap-label-prefix`, `trap-bra-back`,
  `trap-rep-dma`, `trap-chip-form`, `trap-init-r1`, `trap-dirty-state`
  ([TRAPS.md](TRAPS.md)).

## 2. The checklist

**Version 1, 19 Nov 2026.** Costs are Table A-1's, as CYCLE_SCAN.md "The
remedies" gives them.

### From #1080 (MODULATION, 10 Nov 2026)

| id | technique | how found | proof | saving a site | first candidates elsewhere |
|---|---|---|---|---|---|
| T01 | The frame advance in one step: `lua (r0+$2),r0` for two `move (r0)+n0`, or for `#>$2,n0` / step / `#>$1,n0`. Price it in cycles: a `lua` is 3, a step 1. | G | I | three-move form: 4 words, 2 or more cycles; two-move form: 1 word, **+1 cycle** | EUCLID `filter.asm:277,328`, LOFI2 `:1112`, VOID `:510` |
| T02 | `move y0,a` then `move a1,nN` becomes `move y0,nN`. | G | I | 1 word, 1 to 2 cycles | VIBRATO `:383,406` |
| T03 | A helper's entry reload dropped when every caller enters clean (a0 = 0). The header states the contract. | R | I | 2 words, 2 cycles a call | VIBRATO `vb_tap :631` |
| T04 | An inline copy of a helper's work replaced by a call; a duplicate helper removed. | R | I | words saved, **a call's 7 cycles added**: a trade | none found yet |
| T05 | A `move #imm,nN` inside the sample loop, hoisted above it. | G | I | 1 to 2 cycles a sample | RESONATOR `:206-272`, SPECTRUM `:1182` |
| T06 | A register set the same way at every mode's loop head, set once before the dispatch; a copy of the mode removed. | G | I | words; cycles per block only | SPECTRUM m1/m2, DISTORX m3 |
| T07 | A per-sample mode test (`cmp #`, `bne`) made a one-word `tst` on a flag the dispatch sets. | G | I | 0 to 1 word, 0 to 1 cycle | CHARACTER `:746`, CHARACTER TXTR `:815` |
| T08 | An ALU operation followed by `move #$0,R`: the move rides in the operation's parallel slot. | G | I or F | 1 word, 1 cycle | SPECTRUM `:164` |
| T09 | `move a,x:(rN)+` then `move a,y0` made one X:R move (`move a,x:(rN)+ a,y0`). | G | I or F | 1 word, 1 cycle | DELAY SERVER `:1643-1753` |
| T10 | Two channels share one helper; a value kept in a register instead of stored and reloaded. | R | I | sharing: words for a call's cycles (a trade); keeping: 1 to 2 words and cycles | about 38 store-then-reload sites to read |
| T11 | A reload of a value still in a register. | G, R | I | 1 to 2 words, 1 to 2 cycles | VIBRATO `:393,416` |
| T12 | `move r7,rN` / `move #n,nN` / `move (rN)+nN` made `lua (r7+n),rN`, for n up to 63. | G | I | 2 words, 0 to 3 cycles | RESONATOR (five a sample), SPECTRUM, CHARACTER, BBD |
| T13 | A table listed by hand in the manifest, generated from the module's reference instead. | G | I (same words) | none at run time; one source of truth | SPECTRUM (3 tables), CHARACTER's TAPE_D8, DELAY SERVER's RECIP |

Not taken in #1080, kept as known trades: PHSR's four `bsr mo_apst` inlined
(8 instructions a sample fewer, 20 words more); `and #>$3ff,a` dropped in
`mo_tap` and `mo_herm` (class U: it relies on the modulo AGU wrapping an
offset); MODULATION's MIX and COMB loops reworked.

### From MODULATION's earlier passes, other modules and the scan

| id | technique | how found | proof | saving a site | source, first candidates |
|---|---|---|---|---|---|
| T14 | State walked by a pointer (`x:(r3)+`) instead of displaced from r7 (`x:(r7+d)`). | S (displaced moves), G | I | 1 cycle an access (2 for a two-word displacement); a pointer setup a block | MODULATION 22 Sep (`42524baf`); VIBRATO has 11 displaced and 0 walked in its loop, VOID 107, LOFI2 93, STUTTR 92 |
| T15 | Read and step in one move (`move y:(r5)-n5,b`). | R | I | 1 word, 1 cycle | `3ee27fba` |
| T16 | Independent moves folded into parallel slots. | R | I or F | 1 word, 1 cycle each | `86f76efd` |
| T17 | A modulo ring with post-step reads, in place of add, and, `move a1,nN`, `(rN)+nN`. | R | I, or U when an offset can pass the buffer | 4 or more words, 5 or more cycles a tap | `7e6afd08`; DELAY SERVER `modtap :2045`; STUTTR's wrap by compare and branch (`:162-168`) |
| T18 | R reuses L's address; a fraction kept in `nN`. | R | I | a recomputation a sample | `55daca93` |
| T19 | The frame advance folded into the last stores (`(r0)+n0` on the store). | G | I | the `lua`'s 3 cycles and word | CHARACTER `:952`, SPECTRUM `:710` |
| T20 | The coefficient and x loaded by one X:R move, the multiply's operands swapped. | R | I | 1 word, 1 cycle | SPECTRUM `fs_ccore` (its README, lines 81-86) |
| T21 | Hot state words moved into the one-word displacement range (-64 to 63). | S (two-word forms) | I | 1 word, 1 cycle an access | BusVerb's README, lines 70-90 |
| T22 | An output written straight into the next stage's slot, so a copy loop goes. | R | I | the copy | BusVerb, 5 Oct |
| T23 | A zero offset through `nN` (`move #>$0,n5` then `(r5+n5)`) made `(r5)`. | G | I | 2 words, 4 to 6 cycles | MINIVERB `:152` |
| T24 | An immediate tap offset loaded into `n5` just before `(r5+n5)`, made one displaced move `y:(r5+off)`. | S (agu), G | F (check the two-word displaced Y form) | 1 word, about 4 cycles | MINIVERB (about 30 taps a sample), VERBERATION |
| T25 | An ALU result moved at once (an arithmetic stall): move independent work between them. | S (arith) | I | 1 cycle a site | RESONATOR `rs_one`, REVERB SERVER `lfrol`, VOCODER `vc_gend` |
| T26 | An address register written just before its use (an AGU stall): write it 3 cycles earlier. | S (agu) | I | 1 to 3 cycles a site | `mo_tap`, `vb_tap`, MODULATION LINE's `move r2,r5` |
| T27 | A `lua` followed at once by a read through its register. | S (agu-lua) | I | up to 3 cycles, if a `lua` interlocks (the manual does not say) | CHARACTER, CHARACTER TXTR, BBD |
| T28 | A P read (`movem`) every sample, copied into X or Y once a block. | S (movem) | I | up to 5 cycles a read, if Table A-1's 6 holds (CYCLE_SCAN.md section 1 doubts it) | VOCODER, CHARACTER TXTR |
| T29 | A short `do` inside the sample loop, unrolled where the words allow. | S (do/rep) | I | 5 cycles a loop entered, for words: often a trade | the scan's remedies |

## 3. How each module is built

Seeded on 19 Nov 2026 from a first read of every DSP module; each module's
audit checks its row and corrects it. Counts are inside the sample loop
(`do n7`), callees not included.

| module | author | source of record | state in the loop: displaced from r7 / walked | calls a sample | `do` in the loop | tables | reference model | identity gate |
|---|---|---|---|---|---|---|---|---|
| MODULATION | sambanks | hand-written | 4 / 88 | `mo_tap` 2 to 3, `mo_itrd`, `mo_apst` 2, `mo_herm` | PHSR `do #4` | generated from the reference | `modulation_ref.py` | `verify_ident` |
| VIBRATO | Bryan T | hand-written | 11 / 0 | `vb_tap` 2 | none | generated from the reference | `vibrato_ref.py` | `verify_ident` |
| SPECTRUM | sambanks | hand-written | 7 / 82 | `fs_r3`, `fs_lcore`, `fs_ccore` | `do #2` | 3 listed by hand | `capacitor2_ref.py` (helper only) | `verify_spectrum_ident` |
| CHARACTER | sambanks | hand-written | 0 / 61 | `chtube` or `chtape` 2 | none | TUBE_UP computed, TAPE_D8 by hand | none | `verify_ident` |
| CHARACTER TXTR | sambanks | hand-written: CHARACTER plus 191 lines | 4 / 63 | as CHARACTER, plus `chtx2` 2 | none | as CHARACTER, plus POCKEY computed | `pockey2_ref.py` | `verify_ident` |
| DISTORX | MaMarko | **generated** by `generate_asm.py` from `distorx.tmpl.asm` | 6 small loops; the work is in callees | `sod_stage` or `dtx_rstage`, `dtx_out` | none | computed | `distorx_ref.py` | `verify_ident` |
| LOFI2 | Bryan T | hand-written | 93 / 85 | none (inline) | none | computed in the manifest | none | `verify_ident` |
| VOID | ilia-murzinov | hand-written | 107 / few | none | none | computed in the manifest | `void_ref.py` | `verify_ident` |
| STUTTR | ilia-murzinov | hand-written | 92 / few | none | none | none | none | `verify_ident` |
| SHATTER | ilia-murzinov | hand-written; limiter spliced from `peak_limiter.py` | 48 / few | none | none | none | none | `verify_ident` |
| RESONATOR | ilia-murzinov | hand-written; limiter spliced from `peak_limiter.py` | 28 / 2 | `rs_one` 8 | none | computed in the manifest | `resonator_ref.py` | `verify_ident` |
| EUCLID | repeat98 | hand-written | 56 / few | `eu_denominator` (conditional) | none | computed in the manifest | none | `verify_ident` |
| MINIVERB | repeat98 | hand-written; its comments read machine-made, no generator in the repo | 58 / few | none | none | none | none | `verify_ident` |
| TRANSIENT | Ignorato | hand-written | 26 / few | none | none | computed in the manifest | `transient_ref.py` | `verify_ident` |
| VOCODER | Ignorato | hand-written | 35 / 36 | `vc_blep` 2 | `do #10` | from `vocoder_law.py` | `vocoder_ref.py` | `verify_ident` (own slot 5) |
| BBD | JamCones | hand-written | 42 / 111 | `bbhsec` | none | none | `bbd_ref.py` | `verify_ident` |
| VERBERATION | Emilie Gillet, ported | hand-written; three rows from `rows.py` | 44 / few | none | none | none | none | `verify_ident` |
| TESTGEN | Ignorato | hand-written | 34 / few | | | computed in the manifest | `testgen_ref.py` (not imported) | `verify_ident` |
| SEND | sambanks | hand-written | | | | none | none | `verify-bus` |
| REVERB SERVER | sambanks | hand-written | 93 / 80 | `apbody` 4 | `do #8`, `do #4` twice | typed-in mode rows, the rolled LFO table | none | `verify-roll` |
| DELAY SERVER | sambanks | hand-written | 54 / 9 | `modtap`, `smoothw` | `do #4` twice | typed in | none | `verify-delay` |
| SIDECHAIN_COMPRESSOR | Zac Kyoti | in its `upstream/` submodule | | | | | | |
| ANALOG BASSDRUM | repeat98 | written over SPRING REV's words by `ab_image.py` | | | | `tables.inc` | `dsp808.py`, `dsp909.py` | |

Every module decodes its knobs once a block; none reads r6 inside a sample
loop. `dsp_asm` has no includes, macros or `equ`, so modules share code by
copying it, or by Python splicing text in through `subst`.

## 4. Findings by module

Each module's section starts with its stamp: the checklist version it was
audited against, or "not audited".

### MODULATION

Not audited.

### VIBRATO

Not audited.

## 5. Good for all

Constructions that one module does better than the others. These are
proposals for the authors and for MODULES.md. Most would change the output,
so they sit outside this audit's bit-identical rule.

- **Knob smoothing, six ways.** A per-block glide (MODULATION 1/128, VIBRATO
  1/32), a per-sample one-pole (BBD 1/32 on MIX, MINIVERB 1/256), a per-block
  step added each sample (LOFI2, EUCLID). To compare: cost, zipper noise, and
  what each does to a knob under an LFO.
- **LFOs, six ways.** A per-block triangle with a per-sample slope
  (MODULATION), shapes once a block (VIBRATO), a parabola once a block
  (VERBERATION), a corrected parabola a sample (LOFI2), a triangle a sample
  (MINIVERB), a rolled table (REVERB SERVER).
- **Shared code.** `vb_tap` is `mo_tap` plus one move. A shared tap would come
  in the way `tools/remix/peak_limiter.py` serves SHATTER and RESONATOR: one
  Python source, spliced in through `subst`.

## 6. Side findings

Not optimisations. Reported, and fixed only with Yves's OK.

- `modules/character-txtr/manifest.py:143` names `verify_char_key_txtr.py`;
  the file on disk is `verify_charkey_txtr.py`.
- SEND and DEVILISH declare no gate of their own.
- MODULATION's PHSR advances its LFO with a fixed `do #15` a block. The unit's
  block is 16 samples, so PHSR's rate is probably 15/16 of the knob's (#1080's
  deferred note; inferred). The wider identity gate's 16-sample renders see
  the difference.
- `verify_ident.py` used to render every module on the FX1 slot. VOCODER
  renders on slot 5, so on slot 1 it hashed VOCODER's dry pass and passed any
  change to the vocoder (measured 19 Nov 2026: a one-bit coefficient change,
  7/7 identical). Fixed on branch `ident-wide`.

## 7. Baseline

Main at `cc7cffc1`. Cycles are the scan's figures of 18 Nov 2026 at
`5556a840`; no DSP source changed between the two. Words are `dsp_asm` at
`-org 800` per payload, as `dsp_forms.py --census` assembles them. "New forms"
counts the forms with no stock site, which the chip-form register or the
module's unit evidence must cover.

| module | words | P-table words | new forms | dearest setting | instructions a sample | cycles a sample | % of a frame | stall cycles |
|---|---|---|---|---|---|---|---|---|
| DELAY SERVER | 1,519 (B) | 60 | 64 | GRAIN (min) | 1,424.1 | 1,966.2 | 43.4 | 256.2 |
| REVERB SERVER | 1,967 (A) | 170 | 105 | ROOM (min) | 1,009.4 | 1,593.1 | 35.2 | 261.9 |
| VOCODER | 581 | 166 | 52 | INT (def) | 757.1 | 1,245.8 | 27.5 | 204.8 |
| CHARACTER TXTR | 1,097 | 597 | 128 | SAT=TUBE (max) | 411.1 | 697.9 | 15.4 | 111.8 |
| RESONATOR | 451 | 66 | 29 | defaults (max) | 402.1 | 655.9 | 14.5 | 82.6 |
| LOFI2 | 838 | 516 | 29 | DOWN (max) | 410.6 | 654.2 | 14.4 | 89.6 |
| MINIVERB | 459 | 0 | 12 | RATE=0.34 (max) | 314.6 | 608.8 | 13.4 | 150.3 |
| BBD | 1,112 | 0 | 46 | STGS=1024 (dear) | 365.2 | 528.3 | 11.7 | 54.3 |
| VOID | 513 | 387 | 18 | SHPE=SIN (dear) | 281.9 | 503.9 | 11.1 | 62.4 |
| VERBERATION | 644 | 0 | 16 | ROOM (def) | 238.5 | 455.7 | 10.1 | 107.8 |
| CHARACTER | 967 | 51 | 113 | SAT=TUBE (max) | 258.9 | 428.3 | 9.5 | 76.7 |
| MODULATION | 1,318 | 148 | 89 | FLNG (def) | 245.9 | 398.8 | 8.8 | 61.8 |
| SHATTER | 457 | 0 | 22 | SOFT (max) | 213.9 | 383.1 | 8.5 | 37.0 |
| DISTORX | 1,114 | 515 | 27 | RAT (min) | 232.9 | 375.9 | 8.3 | 40.8 |
| SPECTRUM | 1,345 | 54 | 84 | ISO (def) | 254.2 | 371.1 | 8.2 | 55.2 |
| TRANSIENT | 258 | 99 | 14 | defaults (def) | 169.0 | 270.0 | 6.0 | 33.5 |
| STUTTR | 591 | 0 | 18 | FWD (dear) | 127.7 | 268.4 | 5.9 | 20.6 |
| EUCLID | 362 | 33 | 11 | RATE=1/32 (def) | 141.8 | 232.3 | 5.1 | 25.2 |
| VIBRATO | 593 | 103 | 33 | SHP=TRI (max) | 121.1 | 207.0 | 4.6 | 36.2 |
| SEND | 260 | 0 | 12 | defaults (def) | 37.1 | 57.5 | 1.3 | 6.9 |
| SIDECHAIN_COMPRESSOR | 612 | 65 | 71 | not scanned (hooks into stock COMPRESSOR) | | | | |
| TESTGEN | 418 | 176 | 33 | not scanned (a test generator) | | | | |

Frame hooks, by words: LOAD METER 167, DLCOPY 138 (B), REMIX SWITCH 39, USB
29 (A), KEYBUS 17. Probes and stubs are not audited: PEXT PROBE 963, EXTPROBE
277, CF METER 206, DLPROBE 117, DEVILISH 5, TAPE ECHO 5.
