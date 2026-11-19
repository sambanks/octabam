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

### Version 2: rows found in pass 1 (19 Nov 2026)

| id | technique | how found | proof | saving a site | found in, and where it applies |
|---|---|---|---|---|---|
| T30 | A table read from P every sample (`p:(r1+n1)`, `movem`): where the build places the module's `ptable` decides whether the read is P or X (MODULES.md "Declaring DSP code": the stock curve bank, P, or a given-up effect's X). Read the build report before rewriting the reads. | S (movem), G | build placement | up to 5 cycles a read, if Table A-1's 6 holds (doubted) | found in CHARACTER TXTR; VOCODER, CHARACTER, TRANSIENT, DISTORX, LOFI2 |
| T31 | A long immediate in the sample loop. A data-register move of a constant whose low 16 bits are zero (`#>$400000`) is the one-word short form `#$40`, which loads bits 23-16: CHARACTER TXTR already uses it (`:180`, "short immediate: bits 23-16"). Any other constant can live in a register across the loop when one is free. | S (two-word forms), G | I (check the encoding: `trap-asm`) | 1 word, 1 cycle | found in BBD; short-form candidates across the modules: 136 moves in 23 files, and 15 zero loads written long (`#>$0`) in 7 (found in RESONATOR) |
| T32 | Taps through one `nN` in a row: alternate two pointer sets on the same ring (r4/n4 and r5/n5 with the same modulus), so the next tap's offset loads while this tap reads. Hides the AGU stall with stock forms, where T24's displaced move needs a new form. | G | I | about 3 cycles a tap | found in MINIVERB (20 runs of taps); VERBERATION (9) |

T12's shape also covers `move r7,a` / `add #n,a` / `move a1,rN` (found in
VOCODER).

### Version 3: a row found while fixing (19 Nov 2026)

| id | technique | how found | proof | saving a site | found in, and where it applies |
|---|---|---|---|---|---|
| T33 | In a chain of accesses through one `nN`, load each `nN` right after the previous instruction that names it, not just before its own use. The AGU wait then overlaps the work between accesses. Straight-line code only; nothing between the old and the new place names `nN`, so the change is safe by construction (the audit's `t33.py` makes and lists the moves). | G (`t33.py --dry`) | I: the same instructions in another order | up to 3 cycles an access; an arithmetic stall the load used to fill can come back (1) | found in MINIVERB (29 loads, -101 cycles a sample with T31 and T11); VERBERATION 15, LOFI2 1, REVERB SERVER 1 |

**Why T33 and not T24 or T32 in MINIVERB.** The stock payloads address Y
through `(rN+nN)` with no register but MINIVERB's own r5 (its forms run under
its unit evidence), and have no two-word displaced Y move at all
(`move y:(r5+N),b`). So T24 and T32 both need a form with no stock site
(class F); T33 needs none.

**The gate changed during batch 2** (`e4c207a2`: the manifest's `dear`
settings). Batch 1's four branches were proven again with it, the base
stamped and the final source checked: MODULATION 67/67, VIBRATO 58/58,
MINIVERB 56/56, VOCODER 40/40 IDENTICAL.

**Pass 2 for T33** (`t33.py --dry` over every module's sample loops, every
N register): MINIVERB 29 (taken), VERBERATION 15, LOFI2 1 (n0), REVERB SERVER
1 (n5); every other module 0.

**Pass 2: the version 2 rows over every module audited before them** (static
counts inside the sample loops and the routines they call):

| module | T12 | T28/T30 P reads | T31 long immediates | T31 short-form candidates (whole file) | T32 |
|---|---|---|---|---|---|
| MODULATION | 0 | 0 | 22 | 3 | 0 |
| VIBRATO | 0 | 0 | 4 | 3 | 0 |
| VOCODER | 2 | 3 | 11 | 7 | 0 |
| CHARACTER TXTR | 0 | 6 | 10 | 3 | 0 |
| CHARACTER | 0 | 2 | 6 | 3 | 0 |
| RESONATOR | 5 | 0 | 14 | 3 | 0 |
| LOFI2 | 0 | 2 | 31 | 11 | 1 |
| MINIVERB | 0 | 0 | 18 | 9 | 20 |
| BBD | 0 | 0 | 22 | 23 | 0 |
| VOID | 0 | 0 | 19 | 7 | 1 |
| VERBERATION | 0 | 0 | 4 | 3 | 9 |
| DISTORX | 0 | 4 | 29 | 15 | 0 |
| SPECTRUM | 1 | 0 | 7 | 3 | 0 |
| SHATTER | 0 | 0 | 5 | 6 | 0 |
| TRANSIENT | 0 | 4 | 18 | 4 | 0 |
| EUCLID | 0 | 0 | 1 | 3 | 2 |
| STUTTR | 0 | 0 | 58 | 4 | 0 |
| SEND | 0 | 0 | 0 | 0 | 0 |
| REVERB SERVER | 0 | 0 | 44 | 1 | 0 |
| DELAY SERVER | 1 | 0 | 45 | 0 | 0 |

Every module is now stamped with version 2.

## 3. How each module is built

Seeded on 19 Nov 2026 from a first read of every DSP module; each module's
audit checks its row and corrects it. The state counts are the static check's
(T14), checked in pass 1: inside the sample loops and the routines they call.

| module | author | source of record | state in the loop: displaced from r7 / walked | calls a sample | `do` in the loop | tables | reference model | identity gate | frame advance |
|---|---|---|---|---|---|---|---|---|---|
| MODULATION (audited) | sambanks | hand-written | 7 / 102, loops and the routines they call | `mo_tap` 2 to 3, `mo_itrd`, `mo_apst` 4 (PHSR), `mo_herm` 2 (COMB) | PHSR `do #4` twice | generated from the reference | `modulation_ref.py` | `verify_ident` | `lua (r0+$2),r0` |
| VIBRATO (audited) | Bryan T | hand-written | 11 / 4, loops and the routines they call | `vb_tap` 2 | none | generated from the reference | `vibrato_ref.py` | `verify_ident` | two `(r0)+n0` |
| SPECTRUM | sambanks | hand-written | 7 / 90 | `fs_r3`, `fs_lcore`, `fs_ccore` | `do #2` | 3 listed by hand | `capacitor2_ref.py` (helper only) | `verify_spectrum_ident` | post-step stores |
| CHARACTER | sambanks | hand-written | 0 / 66 | `chtube` or `chtape` 2 | none | TUBE_UP computed, TAPE_D8 by hand | none | `verify_ident` | post-step stores |
| CHARACTER TXTR | sambanks | hand-written: CHARACTER plus 191 lines | 5 / 68 | as CHARACTER, plus `chtx2` 2 | none | as CHARACTER, plus POCKEY computed | `pockey2_ref.py` | `verify_ident` | post-step stores |
| DISTORX | MaMarko | **generated** by `generate_asm.py` from `distorx.tmpl.asm` | 2 / 8 | `sod_stage` or `dtx_rstage`, `dtx_out` | none | computed | `distorx_ref.py` | `verify_ident` | post-step stores |
| LOFI2 | Bryan T | hand-written | 93 / 88 | none (inline) | none | computed in the manifest | none | `verify_ident` | `#>$2,n0` / step / `#>$1,n0` |
| VOID | ilia-murzinov | hand-written | 107 / 3 | none | none | computed in the manifest | `void_ref.py` | `verify_ident` | `#>$2,n0` / step / `#>$1,n0` |
| STUTTR | ilia-murzinov | hand-written | 92 / 6 | none | none | none | none | `verify_ident` | post-step stores |
| SHATTER | ilia-murzinov | hand-written; limiter spliced from `peak_limiter.py` | 48 / 2 | none | none | none | none | `verify_ident` | post-step stores |
| RESONATOR | ilia-murzinov | hand-written; limiter spliced from `peak_limiter.py` | 28 / 8 | `rs_one` 8 | none | computed in the manifest | `resonator_ref.py` | `verify_ident` | post-step stores |
| EUCLID | repeat98 | hand-written | 56 / 2 | `eu_denominator` (conditional) | none | computed in the manifest | none | `verify_ident` | `#>$2,n0` / step / `#>$1,n0` |
| MINIVERB | repeat98 | hand-written; its comments read machine-made, no generator in the repo | 58 / 6 | none | none | none | none | `verify_ident` | post-step stores |
| TRANSIENT | Ignorato | hand-written | 26 / 6 | none | none | computed in the manifest | `transient_ref.py` | `verify_ident` | post-step stores |
| VOCODER | Ignorato | hand-written | 35 / 39 | `vc_blep` 2 | `do #10` | from `vocoder_law.py` | `vocoder_ref.py` | `verify_ident` (own slot 5) | post-step stores |
| BBD | JamCones | hand-written | 44 / 67 | `bbhsec` | none | none | `bbd_ref.py` | `verify_ident` | post-step stores |
| VERBERATION | Emilie Gillet, ported | hand-written; three rows from `rows.py` | 44 / 5 | none | none | none | none | `verify_ident` | post-step stores |
| TESTGEN | Ignorato | hand-written | 34 / few | | | computed in the manifest | `testgen_ref.py` (not imported) | `verify_ident` |  |
| SEND | sambanks | hand-written | 6 / 4 | | none | none | `verify-bus` | n/a (the bus) |
| REVERB SERVER | sambanks | hand-written | 108 / 83 | `apbody` 4 | `do #8`, `do #4` twice | typed-in mode rows, the rolled LFO table | none | `verify-roll` | n/a (the bus) |
| DELAY SERVER | sambanks | hand-written | 54 / 13 | `modtap`, `smoothw` | `do #4` twice | typed in | none | `verify-delay` | two `(r0)+n0` |
| SIDECHAIN_COMPRESSOR | Zac Kyoti | in its `upstream/` submodule | | | | | | |  |
| ANALOG BASSDRUM | repeat98 | written over SPRING REV's words by `ab_image.py` | | | | `tables.inc` | `dsp808.py`, `dsp909.py` | |  |

Every module decodes its knobs once a block; none reads r6 inside a sample
loop. `dsp_asm` has no includes, macros or `equ`, so modules share code by
copying it, or by Python splicing text in through `subst`.

## 4. Findings by module

Each module's section starts with its stamp: the checklist version it was
audited against, or "not audited".

### MODULATION

**Stamp: checklist version 1, pass 1, 19 Nov 2026; version 2 rows by pass 2**
(T31: 22 long immediates in the loops, 3 short-form), source at `cc7cffc1`
(the same as #1080's merge). Dearest: FLNG, 398.8 cycles a sample, 8.8 % of a
frame (modelled). Scan: `out/dsp-audit/pilot/modulation_now.json`; the
static checks: the audit's `g_checks.py`.

**The pilot's check.** The procedure was first run on MODULATION's source
from before #1080 (`48b7e4f3`, the merge's first parent):

- The static checks find #1080's sites in that source: T01 (3 frame advances),
  T02 (4 write addresses), T03 (3 entry reloads), T05 (3 `n3` loads), T07 (4
  arm tests), T08 (3 compares) and T09 (5 store-and-copy pairs, of which #1080
  merged the two PHSR ramps). Per block, with `--all`: T11 (`$47` stored and
  read back at once) and T12 (5 `move r7,rN`). In today's source those sites
  are gone, except the ones #1080 left on purpose (T09's three MIX stores, T17).
- **#1080 in cycles** (the model, every mode at its defaults): JUNO 333.5 →
  321.8, DIM 402.5 → 390.9, FLNG 412.5 → 398.8, COMB 368.1 → 360.9, PHSR
  402.2 → 393.1. That is 7.1 to 13.7 cycles a sample, more than its 6.4 to 8.8
  instructions: the stalls and two-word forms it removed count more than the
  cycle its frame-advance `lua` adds (+1.5 a sample on average).

**Findings.** Savings are cycles a sample (modelled) by mode, and words.

| # | row | site | the change | saving | class | status |
|---|---|---|---|---|---|---|
| M1 | T26, T25 | `mo_tap` (`:1347-1359`) | The offset first, in `a`; the fraction in `b`, filling the gap before `n5` is used. Stalls a call 6 → 2. Every form has a stock site (`move a,b`, `and #>N,b`, `asl #N,b,b`, `move b1,y1`); the zero-stall order needs `sub y1,b` and `move b1,n5`, which have none. | -5 a call: JUNO and DIM -10, FLNG -15; -1 word | I | taken: branch `mod-fast` (17dfb0f8), -10 / -15 as modelled |
| M2 | T26, T25 | `mo_herm` (`:1383-1396`) | The same order. | -5 a call: COMB -10; -1 word | I | taken: with M1, COMB -10 |
| M3 | T26, T25 | LINE's two line writes (`:427-429`, `:474-476`); COMB's two (`:1139-1141` and its L twin) | Load `n5` and `r5` just after the tap returns (nothing between uses them); put the step between `add b,a` and the limiting `move a,x0`. Removes the 3-cycle AGU stall and a 1-cycle arithmetic stall. | -4 a site: LINE modes -8; COMB -8 (its sites to be read); 0 words | I | taken: LINE b3e53422 (-8), COMB 4dd05345 (-8) |
| M4 | T19 | the three mix tails (`:634-644`, `:897-907`, `:1163-1173`) | The L store `x:(r0)+`, the dry R read `x:(r0)`, the R store `x:(r0)+`; the `lua` goes. Nothing between uses `r0`. | -5 in every live mode; -1 word each (3 in all) | I | taken: 1aa9c85d, -5 in every mode, -3 words |
| M5 | T09 | the three MIX run stores (`:629`, `:892`, `:1158`) | `move a,x:(r1)` and `move a,y1` as one X:R move. | -1 in every live mode; -1 word each | F: `move a,x:(r1) a,y1` has no stock site | open |
| M6 | T25 | LINE's line writes and LPo (`mo_line+124`, `+153`, `+168`, `+192` in the scan) | Move the next independent load (`move n2,x0`, the next slope) between the `mac` and its store. | about -1 a site, 4 to 6 sites a sample | I | open: design per site |
| M7 | T26 | `move #$3,n3` at `mo_whr` (`:617`), `move #$5,n3` in COMB (`:1146`) | Load `n3` earlier, or reach wet L another way. In FLNG `n3` also holds f. | -1 to -2 | I | open |
| M8 | T17 | `and #>$3ff,a` in `mo_tap` and `mo_herm` | Drop it: the modulo AGU would wrap the offset (#1080's note). | 2 to 3 a call | U | needs the unit |
| M9 | T29 | PHSR's two `do #4` (`:791`, `:851`) | Unroll. | -10, about +20 words | I | not taken: a trade |
| M10 | T27 | a `lua` and a read through it (`mo_whl`, `mo_padv+103`, COMB `+80`) | Separate them. | up to 3 each, only if a `lua` interlocks (the manual does not say) | I | open, low |
| M11 | T25 | the mix tails' five 1-cycle stalls (`mo_whr+7`, `+11`, `+16`, `+21`, `+25`) | The MIX rework #1080 declined (mix L as soon as wet L exists). | about -5 in every live mode | I | open: more surgery |
| M12 | T26 | FLNG's fixed-tap line write (`mo_whl+7`: `move r6,r5` then the step, 3 a sample), found by the scan of the M1 to M4 code | M3's change. | -3 (FLNG) | I | open |

If M1 to M5 hold, the model gives JUNO about -24 (321.8 → 298), DIM -24, FLNG
-29 (398.8 → 370, 8.8 % → 8.2 % of a frame), COMB -24 and PHSR -6. Modelled,
not measured; the gate and a LOAD METER read would confirm them.

**Taken, 19 Nov 2026** (branch `mod-fast`, local, from main `cc7cffc1`): M1 to
M4, each commit IDENTICAL under the wider gate (41 renders, state after every
block), `verify_modulation` ALL PASS, every new form at a stock site. The scan
of the result: JUNO 321.8 → 298.8, DIM 390.9 → 367.9, FLNG 398.8 → 370.8 (8.8 %
→ 8.2 %), COMB 360.9 → 337.9, PHSR 393.1 → 388.1 cycles a sample; words 1,318
→ 1,313, then 1,310 with three short-form constants (T31, `6875d815`). Every
figure matched the finding's estimate.

### VIBRATO

**Stamp: checklist version 1, pass 1, 19 Nov 2026; version 2 rows by pass 2**
(T31: 4 long immediates, 3 short-form), source at `cc7cffc1`.
Dearest: SHP=TRI at its maximum, 207.0 cycles a sample, 4.6 % of a frame
(modelled). Scan: `out/dsp-audit/pilot/vibrato_now.json`.

VIBRATO copies MODULATION's tap (`vb_tap` is `mo_tap` plus a clean reload)
and its line writes, but not the 22 Sep pass: its loop reads all 11 state
words as offsets from `r7`.

| # | row | site | the change | saving | class | status |
|---|---|---|---|---|---|---|
| V1 | T26, T25, T03 | `vb_tap` (`:630-643`) | M1's order, and the clean reload `move x0,a` dropped: both callers enter with a0 = 0 (a delay and its slope, both loaded from memory and added). | -6 a call, -12 a sample; -2 words | I | open |
| V2 | T02, T26, T25 | the two line writes (`:383-388`, `:406-411`) | `move y0,n5` for `move y0,a` / `move a1,n5`; `r5` loaded first, the step after `sub b,a`; the line store `move b,y:(r5)` into the slot after the shift. Removes 6 stall cycles and an instruction a site. | -7 a site, -14 a sample; -2 words | I (`move y0,n5` has a register row) | open |
| V3 | T19 | the frame advance (`:397`, `:410`, `:420-422`) | The stores post-step `r0`; the two steps go. | -4; -2 words | I | open |
| V4 | T14 | the 11 displaced state accesses in the loop | Walk a pointer over the state. The words are not in the order the loop reads them, so the state block would be re-laid. | up to -11 | I, but a re-laid state block shows in the gate's state check: each moved word must be named | open |
| V5 | T25 | `vb_mixd`'s other 1-cycle stalls (`+25`, `+29`, `+43`, `+48`, `+52`, `+66`, `+71`) | Reorder. | about -1 each | I | open |

If V1 to V3 hold: about -30 of 207.0 (4.6 % → 3.9 % of a frame), -6 words.

**Taken, 19 Nov 2026** (branch `vib-fast`, local): V1 (`470c692b`), V2
(`940bba0b`), V3 (`5b495fab`) and three short-form constants (T31,
`5172eb75`), each IDENTICAL under the wider gate (36 renders), `verify_vibrato`
ALL PASS. The scan: 207.0 → 176.9 cycles a sample at SHP=TRI max (4.6 % → 3.9
%), as estimated; words 593 → 584.

### Pass 1, the other modules

**Stamp for each: checklist version 2, 19 Nov 2026,** source at `cc7cffc1`;
scan: `out/dsp-audit/baseline/`, the static checks: `out/dsp-audit/pass1/`.
Every saving is cycles a sample at the dearest setting (modelled) and words.
Status is open for every finding unless it says otherwise. "Design" means the
site is found and priced, and the instruction order is still to be worked
out.

#### VOCODER (Ignorato): 1,245.8 cycles a sample, 27.5 %

Ten bands a sample, each four state-variable filter sections, an envelope and
a VCA. A section is a serial chain, so most of its stalls are intrinsic; these
are the ones that are not.

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| VC1 | T25 | the band loop (`:462-526`) | Load the next section's coefficient (`y:(r3)+`, `p:(r4)+`) and the envelope's 0.00227 and e into the slot after each section's last `macr`. | about -5 a band, -50 | I |
| VC2 | T16 | `sub a,b a,x:(r5)+`, four a band | The low store rides in the next `macr`'s slot. | -4 a band, -40 | F: `macr -y1,x1,b a,x:(r5)+` has no stock site |
| VC3 | T12 | the band setup (`:459-461`) and hp6's (`:532-535`) | `lua (r7+$1b),r5`; `lua (r7+$6),r5` hoisted above `move x:(r7+$4),b`. Both forms stock. | -3; -4 words | I |
| VC4 | T25 | `vc_blep`, 2 calls, 8 stalls a call | Interleave its two independent halves (t_b, t_a). | up to -16 | I, design: registers are tight |
| VC5 | T28, T30 | 3 P reads a band, 30 a sample | Copy BAND's 30 words into X or Y once a block, or have the build place the table in X. | up to -150, if a P read is 6 cycles | needs 30 words of X or Y |
| VC6 | T31 | 7 short-form constants | | -1 word each | I |
| VC7 | T29 | `do #10` | Unroll. | -5, about +600 words | not taken: a trade |

VC1 and VC3: about -53 (27.5 % → 26.3 %); with VC2, -93 (25.4 %).

**Taken, 19 Nov 2026** (branch `voc-fast`, local): VC3 (`f8362081`, -5,
estimated -3), VC1 (`3e359d75`, -50, as estimated), VC6 (`d8c833d8`, seven
short-form constants, -7 words), each IDENTICAL under the wider gate (26
renders on VOCODER's own slot), `verify_vocoder` OK. The scan: 1,245.8 →
1,190.5 cycles a sample (27.5 % → 26.3 %); words 581 → 570.

#### CHARACTER TXTR and CHARACTER (sambanks): 697.9 and 428.3, 15.4 % and 9.5 %

CHARACTER TXTR is CHARACTER plus 191 lines, so CH2, CH3 and CH5 land in both.

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| CH1 | T25 | TXTR's `chtx2`, 2 calls, about 20 one-cycle stalls a call | Reorder within the texture's two halves. | up to -40 (TXTR) | I, design |
| CH2 | T27 | `lua (r5+$2),r5` (or `+$6`), then a read through r5: 3 sites, plus `lua (r4+$3d),r3` and `lua (r4+$2),r3` | Separate each pair. | up to -16 | I, low: only if a `lua` interlocks |
| CH3 | T25 | the coefficient ramps: `add x0,a x:(r3)+,x0` then `move a,x:(r5)+`, 6 sites | Interleave two ramps in a and b. | -6 | I, design |
| CH4 | T28, T30 | 6 P reads a sample in TXTR, 2 in CHARACTER (`p:(r1+n1)`, `p:(r2+n2)`) | Where the build places the 597 and 51 words. | up to -30 (TXTR) | build placement |
| CH5 | T07 | `cmp #1,b` / `bne` a sample (`character.asm:746`, `character_txtr.asm:815`) | A flag test. | 0 to -1 | I |
| CH6 | T08 | `add x1,a` / `move #0,x1` (TXTR `:1119`) | The zero rides in the add's slot. | -1, -1 word | I or F |

#### RESONATOR (ilia-murzinov): 655.9, 14.5 %

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| RS1 | T12 | five `move r7,rN` / `move #n,nN` / `move (rN)+nN` a sample (`:205-210`, `:265-273`) | `lua (r7+n),rN`; every n is under $40. | -3 a site, -15; -10 words | I |
| RS2 | T25 | `rs_one`, 8 calls, 5 stalls a call | Reorder; the four bands are independent. | up to -40 | I, design |
| RS3 | T08, T31 | `cmp x0,a` / `move #>$0,a`, 4 sites (`:183`, `:191`, `:244`, ...) | The one-word `move #0,a` (it keeps the flags the following Tcc needs). | -1, -1 word each | I (check the form) |
| RS4 | T14 | 28 displaced, 8 walked | Walk. | up to -28 | I, re-laid state |

RS1 and RS3: about -19 and -14 words; with RS2, up to -59 (14.5 % → 13.2 %).

**Taken, 19 Nov 2026** (branch `res-fast`, local): RS1 (`a1a6bee4`, -15, as
estimated, -10 words), RS3 (`8193024b`, the five zero loads, -4, -5 words) and
three short-form constants (`e1a3a05c`), each IDENTICAL under the wider gate
(27 renders). The scan: 655.9 → 636.6 cycles a sample (14.5 % → 14.0 %); words
451 → 433. Left: RS2 (the `rs_one` stalls), RS4.

#### LOFI2 (Bryan T): 654.2, 14.4 %

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| LF1 | T01, T19 | the frame advance `move #>$2,n0` / `move (r0)+n0` / `move #>$1,n0` (`:1112-1114`), with an AGU stall, and the next sample's first read waiting on n0 | The stores post-step r0 (T19), or one `lua (r0+$2),r0`. | about -8; -4 words | I |
| LF2 | T26 | `move a1,r5` then `move p:(r5),y0`, twice (`:1010`, `:1016`) | Compute r5 earlier. | -6 | I, design |
| LF3 | T26, T12 | `move r7,r1` / `move (r1)+n1` and `move r1,r2` / `move (r2)+` (DOWN, UP) | `lua`, hoisted. | -6 | I |
| LF4 | T08, T31 | `add x0,a` / `move #>$0,x0` (`:913`) | The zero rides in the add's slot as a short immediate. | -2, -2 words | I or F |
| LF5 | T14 | 93 displaced, 88 walked; every slot already in the one-word range | Walk. | up to -90 | I, re-laid state |
| LF6 | T31 | 31 long immediates in the loop, 11 short-form candidates | | -1 each | I |

LF1, LF3 and LF4: about -16, -6 words (14.4 % → 14.1 %); LF5 is the large one.

**Taken, 19 Nov 2026** (branch `lofi-fast`, local): LF1 as one `lua` (the stores
could not post-step r0 without tracing every mode's stores; `95f022e4`, -5),
LF3 as a reorder (`lua (r1)+,r2` has no stock site, so the parity flip fills
the pointer waits instead; `60962317`, -5 in DOWN and UP), LF4 and LF6 with
t31.py (`dd704f7f`, thirteen constants including two zeros, -5.3), each
IDENTICAL under the wider gate (26 renders), all LOFI2 gates passing. The scan:
DOWN 654.2 → 638.9 cycles a sample (14.4 % → 14.1 %); words 838 → 821.

#### MINIVERB (repeat98): 608.8, 13.4 %

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| MV1 | T24 | 30 taps: `move #>off,n5` then `y:(r5+n5)` | One displaced move, `y:(r5+off)`. | -4 a tap, about -120; -30 words | F: check the two-word displaced Y form |
| MV2 | T32 | the same taps | Alternate r4/n4 and r5/n5 on the ring (m4 = m5 = $3dfd already); load each offset while the other set reads. | -3 a tap, about -90; 0 words | I, design: r4 also serves the modulated taps |
| MV3 | T23 | `move #>$000000,n5` / `y:(r5+n5)` (`:152`) | `y:(r5)`. | -6; -2 words | I |
| MV4 | T31 | 9 short-form constants (`#>$400000,y1`, `#>$600000,y1`, ...) | `#$40`, `#$60`. | -1, -1 word each | I |
| MV5 | T26 | `move a,n5` / `lua (r5+n5),r4`, twice | Hoist. | -6 | I |
| MV6 | T14 | 58 displaced, among them the four per-sample smoothers ($24 to $2d) | Walk. | up to -20 | I |

**Taken, 19 Nov 2026** (branch `mv-fast`, local): T33 over the input diffusers
(`d63191dc`, -36, estimated -46: the writes keep a 1-cycle arithmetic stall the
`n5` load used to fill) and over the branches (`ee755fd4`, -65), with MV3 (the
zero offset), MV4 and T31 (seven short-form gains and a mask), and T11 (two
gains still in y1). Each IDENTICAL under the wider gate (56 renders; the gate
needed a fix first, `ee85d43b` on `ident-wide`: MINIVERB has an unnamed
parameter), 34 `verify_miniverb` gates passed. The scan: 608.8 → 507.7 cycles
a sample (13.4 % → 11.2 %); words 459 → 446. MV1 and MV2 are not needed for
this saving and need new forms (see T33). Still over the 9.07 % cap on the
model; the model reads MINIVERB 8.2 % above its unit figure, so a LOAD METER
read decides. Left: MV5 (the two modulated taps, 3 each), MV6 (the smoothers).

MV2 to MV5: about -110 (13.4 % → 11.0 %); with MV1 in place of MV2 and MV6, about -160 (9.9 %). Neither reaches the 9.07 % cap on the model alone, but the model reads MINIVERB 8.2 % above its unit figure (CYCLE_SCAN.md section 1): a LOAD METER read after the change decides.

#### BBD (JamCones): 528.3, 11.7 % (`dear`)

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| BB1 | T31 | 23 short-form constants (`#>$300000,x0`, `#>$d00000,x0`, ...), 22 long immediates in the loop | Short form, or a register. | -1, -1 word each in the loop | I |
| BB2 | T26, T27 | `move r2,r5` then the XY read (`:733`); `lua (r2+$35),r5` then the XY read (`:626`) | Hoist. | -3 (-6 if a `lua` interlocks) | I |
| BB3 | T08 | `sub x0,a` / `move #0,x0` (`:921`), `asl a` / `move #0,x1` (`:955`) | Ride in the slot. | -1, -1 word each | I or F |
| BB4 | T25 | about 12 one-cycle stalls | Reorder. | about -6 | I, design |
| BB5 | T14 | 44 displaced | Walk. | up to -44 | I, re-laid state |

#### VOID (ilia-murzinov): 503.9, 11.1 % (`dear`)

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| VD1 | T01, T19 | the frame advance (`:510-512`), as LF1 | | about -8; -4 words | I |
| VD2 | T14 | 107 displaced, 3 walked: the most of any module | Walk, with the state block re-laid. | up to -100 | I, re-laid state |
| VD3 | T11 | `$25` and `$26` stored, then read back (`:226`, `:368`) | Keep them in a register. | -2 | I |
| VD4 | T31 | 7 short-form constants | | -7 words | I |
| VD5 | T25 | about 10 one-cycle stalls | Reorder. | about -5 | I, design |

**Taken, 19 Nov 2026** (branch `void-fast`, local): VD1 (`32c1c460`, -5), VD3 at
`$25` only (`e0de4ee5`, -1: the `$26` store and reload have the label
`vd_am_apply` between them, so another path brings its own value), VD4 with
t31.py (`0b0cb062`, -4, -7 words), each IDENTICAL (31 renders), all VOID gates
passing. The scan: 503.9 → 493.8 cycles a sample at `dear`; words 513 → 502.

#### VERBERATION (Emilie Gillet, ported): 455.7, 10.1 %

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| VB1 | T24, T32, T26 | 15 taps through n5: immediate offsets, and offsets read from state (`$2e`, `$47`, `$48`) just before use | Displaced moves (F) or two pointer sets (I) for the immediates; the state offsets loaded 3 cycles earlier (I). | about -3 a tap, up to -50 | I or F |
| VB2 | T23 | `move #>$000000,n5` (`:464`) | `(r5)`. | -6; -2 words | I |
| VB3 | T08 | `sub ...` / `move #0,x0`, three (`:412`, `:419`, `:444`) | Ride in the slot. | -1 each | I or F |
| VB4 | T14 | 44 displaced | Walk. | up to -44 | I, re-laid state |

**Taken, 19 Nov 2026** (branch `verb-fast`, local): T33 over the 15 immediate
offsets (`244e9c14`, -36) and, with `t33.py --mem`, over 6 offsets read from
state (`7f8410d5`, -21: a load moves only past instructions that cannot store
to its word), VB2 (`e25fc47d`, -4, -2 words) and three short-form constants
(`94a393bb`), each IDENTICAL under the wider gate (58 renders). The scan: 455.7
→ 394.5 cycles a sample (10.1 % → 8.7 %, under the 9.07 % cap on the model);
words 644 → 639. Left: the `$2e`, `$48` and `$42` offsets (3 each), VB3 (needs
a parallel-immediate form), VB4.

#### DISTORX (MaMarko): 375.9, 8.3 %

Generated from `distorx.tmpl.asm` by `generate_asm.py`: every fix goes to the
template.

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| DX1 | T31 | 15 short-form constants, 29 long immediates in the loops | | -1 each | I |
| DX2 | T26 | `move r4,r5` / `move (r5)+n5` (`dtx_rstage+133`, `sod_stage+79`), `move r7,r3` / `move (r3)+n3` (`sod_stage+53`) | Hoist, or `lua`. | -2 to -4 | I |
| DX3 | T28, T30 | 4 P reads a stage: the 515-word diode table | Build placement. | | build |
| DX4 | T14, T25 | displaced moves 70 cycles in RAT, about 10 one-cycle stalls, in `dtx_rstage` | Walk; reorder. | up to -40 | I, design |

#### SPECTRUM (sambanks): 371.1, 8.2 %

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| SP1 | T26 | `move r4,r1` / `(r1)+` (`fs_svf`, 6 in SEM), `move #$6,n5` / `(r5)+n5` (`fs_ccore`, 6 in ISO), `move a1,n6` / `x:(r6+n6)` and `move #$c,n3` (`fs_cap`, 3 each in ISO) | Hoist. | -3 to -12 by mode | I |
| SP2 | T25 | the ramps in `fs_r3`, 3 sites | Interleave. | -3 to -9 | I, design |
| SP3 | T12, T29 | `move r7,r3` (`:1181`); `do #2` (`:655`) | `lua`; unroll. | small | I |
| SP4 | T13 | G2, COS and VOWL_ER listed by hand in the manifest | Generate them. | none at run time | construction |

#### SHATTER (ilia-murzinov): 383.1, 8.5 %

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| SH1 | T11 | `$02`, `$03`, `$1c` stored, then read back 2 or 3 later (`:259`, `:361`, `:395`) | Keep them in a register. | -1 to -2 each | I |
| SH2 | T14 | 48 displaced | Walk. | up to -48 | I, re-laid state |
| SH3 | T25 | about 10 one-cycle stalls in `sh00` | Reorder. | about -5 | I, design |
| SH4 | branches | 59 cycles a sample of branches (the scan) | A mode's arms as loops chosen once a block. | | not taken: words |

#### TRANSIENT (Ignorato): 270.0, 6.0 %

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| TR1 | T28, T30 | 4 P reads a sample (`:146-147`, `:259-260`): the 99-word table | Build placement. | up to -20 | build |
| TR2 | T08 | `sub x0,a` / `move #0,x0`, twice (`:219`, `:232`) | Ride in the slot. | -1 each | I or F |
| TR3 | T14 | 26 displaced (27 cycles a sample, its largest extra) | Walk. | up to -26 | I, re-laid state |
| TR4 | T31 | 18 long immediates in the loop, 4 short-form | | -1 each | I |

#### EUCLID (repeat98): 232.3, 5.1 %

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| EU1 | T01, T19 | two frame advances, one a loop (`:277-279`, `:328-330`), as LF1 | | about -8; -4 words each | I |
| EU2 | T11 | `$1d` stored, then read back (`:142`, `:210`) | A register. | -1 | I |
| EU3 | T14 | 56 displaced (53 cycles a sample) | Walk. | up to -50 | I, re-laid state |

**Taken, 19 Nov 2026** (branch `eu-fast`, local): EU1 in both loops (`1dc207b4`,
-5, -8 words), EU2 (`149c8a41`, -4: the reload became `move x0,x1` and fills a
transfer stall), three short-form constants (`27a254f9`), each IDENTICAL (41
renders). The scan: 232.3 → 223.2 cycles a sample; words 362 → 351. The gate
could not build EUCLID before: its audition image lacked EVENTS, which EUCLID
requires (fixed on `ident-wide`, `bd19a163`). `verify_euclid` needs the
`euclid` remix built first (`make bus REMIX=euclid`; then 0 failed checks on the
branch); on a scratch image it
fails five chooser checks, on the base source as on the branch.

#### STUTTR (ilia-murzinov): 268.4, 5.9 % (`dear`)

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| ST1 | T05 | `move #>$ffffff,m4` inside the sample loop, twice (`:157`, `:359`); `proc` already sets m4 linear before the loop (`:64`) and nothing in the loop changes it | Drop both. Also clears a breach of MODULES.md's hardware rule "no M-register write inside the sample loop". | about -10; -4 words | I |
| ST2 | T31 | 58 long immediates in the loop, the most of any insert | Registers, or the short form. | -1 each | I, design |
| ST3 | T17 | the wrap by compare and branch (`:162-168`) | Modulo addressing. | | I or U |
| ST4 | T14 | 92 displaced | Walk. | up to -60 | I, re-laid state |
| ST5 | branches | 49 to 61 cycles a sample of branches | Arms chosen once a block. | | not taken: words |

**Taken, 19 Nov 2026** (branch `stut-fast`, local): ST1 (`92e44f4b`: one m4
write a call, before the loop; -3.9 in FWD at `dear`, estimated about -10: the
AGU waits stay, now on r4's own write before its use; -2 words) and four
short-form constants (`3c044914`) and four zero loads (`69462901`, -2), each
IDENTICAL under the wider gate (58
renders). The scan: 268.4 → 262.5 in FWD at `dear`; words 591 → 581. Before
this, the gate could not see STUTTR at all:
its generic settings never engage the repeater, so every render was the dry
pass; the gate now renders the manifest's `dear` settings (`e4c207a2` on
`ident-wide`).

#### SEND (sambanks): 57.5, 1.3 %

One client; a bus remix runs several beside a server. SE1, T25: five one-cycle
stalls (`proc+234` to `+255`), about -3. Nothing else.

#### REVERB SERVER (sambanks): 1,593.1, 35.2 % of a core, one instance

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| RV1 | T25 | `lfrol`: 8 a sample at each of its sites (an ALU result moved at once), 185 cycles a sample of arithmetic stalls in all | If the eight passes are independent (to read), interleave them in pairs. | up to -100 | I, design: the largest single target in the audit |
| RV2 | T26 | `move y:(r6)+,n5` then `y:(r5+n5)` (`lfrol+372`, 8 a sample) | Load the offset 3 cycles earlier. | -8 to -24 | I |
| RV3 | T17 | five `and #>$7ff` masks | Modulo addressing. | | I or U |
| RV4 | T31, T29, T14 | 44 long immediates; `do #8`, `do #4` twice; 108 displaced | | | design |

#### DELAY SERVER (sambanks): 1,966.2 in GRAIN, 43.4 % of a core

| # | row | site | the change | saving | class |
|---|---|---|---|---|---|
| DL1 | T26 | `move a1,r5` then `y:(r5+n5)` (`proc+1108` to `+1414`: 6 each in CLEAN and GRAIN, 12 each at `+1116` and `+1213` in GRAIN) | Compute the address earlier. | -15 (CLEAN) to -50 (GRAIN) | I, design |
| DL2 | T17 | 7 `and #>$3fff` masks, among them `modtap`'s | Modulo addressing (T17). | | I or U |
| DL3 | T09 | 4 store-and-copy pairs (`:1643`, `:1648`, `:1747`, `:1752`) | X:R moves. | -1, -1 word each | F |
| DL4 | T01 | two `(r0)+n0` (`:1987-1988`) | Not a `lua` (+1 cycle): T19 if the stores allow. | -2 to -4 | I |
| DL5 | T11 | `$31`, `$32` stored, then read back (`:1474`, `:1923`) | A register. | -1 each | I |
| DL6 | T03 | two entry reloads (`:1506`, `:1520`) | First read: they look like deliberate limiting copies. | | check |

#### Not audited in pass 1

- **SIDECHAIN_COMPRESSOR** (Zac Kyoti): Zac's code, pinned in `upstream/`,
  checked against his own build every build, and never edited here; any
  change goes to his repository. It has no sample loop of its own (four hooks
  into the stock COMPRESSOR), so the scan cannot price it. The static checks
  on `patch_sc_dsp3.asm` show 34 long immediates, 8 compare-and-branch tests
  and 5 `lua`-then-read pairs, to price with a trace through the stock
  COMPRESSOR before they are offered to him.
- **TESTGEN**: a test signal generator, not scanned.
- **ANALOG BASSDRUM**: built by `ab_image.py` over SPRING REV's words, no
  `DspSection`; not scanned.
- **The frame hooks** (LOAD METER, USB's `rx_inject`, KEYBUS, REMIX SWITCH's
  park, DLCOPY): they run once a frame, not once a sample, so a cycle saved
  there is worth about a sixteenth of one in a sample loop. Not audited.

### Notes from the pilot (checklist version 1 unchanged)

- **Price a pass in cycles.** An instruction saved is not always a cycle
  saved: #1080's frame-advance `lua` saves an instruction and costs a cycle.
  T19, folding the advance into the stores, beats both.
- **Prefer the order whose forms are stock.** For a tap's reorder (T26), the
  stall-free order needed two forms with no stock site; the order with 2 cycles
  left needs none. The finding gives both.
- **A re-laid state block** (T14, T21) defeats the gate's word-by-word state
  check, which cannot follow a word to its new slot. Name every moved word
  with `--scratch` and say so in the PR; the audio renders still prove the
  output.
- **T11 never across a label.** A reload replaced by a register copy is the
  same value only if no other path enters between the store and the reload
  (VOID's `$26`, `vd_am_apply`).
- **One idiom, three authors.** LOFI2 (Bryan T), VOID (ilia-murzinov) and
  EUCLID (repeat98) end their sample loops with the same three lines,
  `move #>$2,n0` / `move (r0)+n0` / `move #>$1,n0`, the dearest frame advance
  in the repo. A shared origin (a template or a generator) is likely; worth
  telling the authors, so new modules start from the cheap form.
- **One fix, two modules.** M1 and V1 are the same change; so are M3 and V2,
  and M4 and V3.

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
- **One-word constants (T31).** CHARACTER TXTR loads constants whose low 16
  bits are zero with the one-word short form (`move #$5e,y1`, "bits 23-16").
  The other modules spell the same kind of value as a two-word `#>$xx0000`:
  136 times in 23 files. Bit-identical, a word and a cycle each.
- **The frame advance, four ways.** Post-stepping `r0` on the last stores
  (CHARACTER, SPECTRUM and most others) costs nothing. A `lua (r0+$2),r0`
  (MODULATION) costs 3 cycles; two `(r0)+n0` (VIBRATO, DELAY SERVER) 2;
  `#>$2,n0` / step / `#>$1,n0` (LOFI2, VOID, EUCLID) about 8 with its stalls.
  T19 brings them all to the first.
- **Tap offsets, four ways.** Loaded into `n5` just before use (MINIVERB,
  VERBERATION: a 3-cycle stall a tap), streamed from memory into `n5` just
  before use (REVERB SERVER), computed into `r5` just before use (DELAY
  SERVER), and computed early enough (none yet). T24, T26 and T32 are the
  remedies; T32 needs no new form.
- **State addressing.** Walked (MODULATION, CHARACTER, SPECTRUM, mostly BBD)
  against displaced from `r7` (VOID 107, STUTTR 92, LOFI2 93, MINIVERB 58,
  EUCLID 56). MODULATION's 22 Sep pass is the worked example; the cost of
  following it is a re-laid state block.
- **Shared code.** `vb_tap` is `mo_tap` plus one move. A shared tap would come
  in the way `tools/remix/peak_limiter.py` serves SHATTER and RESONATOR: one
  Python source, spliced in through `subst`.

## 6. Side findings

Not optimisations. Reported, and fixed only with Yves's OK.

- `modules/character-txtr/manifest.py:143` names `verify_char_key_txtr.py`;
  the file on disk is `verify_charkey_txtr.py`.
- SEND and DEVILISH declare no gate of their own.
- STUTTR writes `m4` inside its sample loop (`:157`, `:359`), against
  MODULES.md's hardware rule "no M-register write inside the sample loop". The
  value is the one `proc` already set (linear), so it does no harm and costs
  about 10 cycles a sample (ST1 removes it).
- MODULATION's PHSR advances its LFO with a fixed `do #15` a block. The unit's
  block is 16 samples, so PHSR's rate is probably 15/16 of the knob's (#1080's
  deferred note; inferred). The wider identity gate's 16-sample renders see
  the difference.
- `verify_ident.py` used to render every module on the FX1 slot. VOCODER
  renders on slot 5, so on slot 1 it hashed VOCODER's dry pass and passed any
  change to the vocoder (measured 19 Nov 2026: a one-bit coefficient change,
  7/7 identical). Fixed on branch `ident-wide` (`88ca7523`); the same branch adds
  the wider renders (`35fc338c`): of ten deliberate faults the old gate caught
  one, the new gate all ten.
- Two more gate blind spots, found while fixing (both fixed on `ident-wide`):
  MINIVERB has a parameter with no name, and the gate stopped at load on it
  (`ee85d43b`); STUTTR's generic settings never engage it, so every render
  was its dry pass and the gate passed any change (`e4c207a2`: the
  manifest's `dear` settings, and the control accepts them). The control
  caught the second one: that is what it was built for. A third: the
  gate's audition build carried only the module and SEND, so a module that
  requires another (EUCLID: EVENTS) did not build at all (`bd19a163`).

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
