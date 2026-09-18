# Parameter-page descriptor table (OS 1.40C)

Read from `out/raw/section_3_MAIN_OS.bin` (SHA256 `164f3122…`), base
`0x40000400`, `file_offset = vaddr − 0x40000400`. Markers as in `CHIP.md`:
✅ measured or decompiled, 🟡 inferred. One table describes every parameter
page on the machine: sample playback (one entry per machine type), AMP,
LFOs, the track recorder, MIDI NOTE/ARP/CTRL pages and the effects.

## 1. Table bounds

```
0x400d2e52 .. 0x400d5f00     31 entries × 402 (0x192) bytes = 12,462 B
```

Entry −1 at `0x400d2e52` has a blank name (a printable-name walk skips
it); `FUN_40031da4` returns `0x400d2e8a` (= `0x400d2e52 + 0x38`) for track
7 when `DAT_80000034` is set: the master-track page.

402 is not a multiple of 4: packed serialised data, embedded 32-bit
pointers misaligned; walk it with unaligned longword reads. No `lea` or
immediate references the table base; entries are reached individually.

## 2. Entry layout

Two bases are in use. `E` = entry start (the layout below). `P = E + 0x38`
= the pointer the lookup tables hold and every firmware routine receives
(✅ `FUN_40031da4`'s fixed returns are all `entry + 0x38`). A routine handed
`P` uses P-relative offsets: `min = P+0x6a`, `count = P+0x9a`, formatter
array A `P+0x0ca`, widget array B `P+0x0fa`, enable bitmap
`P+0x18a`/`P+0x18e`; the record is 0x192 bytes from `P`. The fields listed
before `E+0x38` below belong to the previous record when read from `P`.
The mode-rename cave used `E`'s `+0x4e` on `P` from 3 to 13 Sep 2026 and
wrote names over the minimum table (`FAILURE_MODES.md`, "BusDelay went
silent").

| offset | size | field |
|---|---|---|
| `E+0x00` | 6 × u32 | per-encoder handler pointers (usually `0x40038d94` ×6; FILTER all zero, MULTIBCOMP fifth zero) 🟡 one per encoder |
| `E+0x18` | 29 B | zero |
| `E+0x35` | 6 B | not decoded (`11 11 11 00 00 00` for CHORUS) |
| `E+0x3b` | u8 | effect id (0 for non-FX pages); read as the whole u32 at `P+0`, so the three bytes above it must be zero |
| `E+0x3c` | 5 B | abbreviation, 4 chars + NUL |
| `E+0x41` | 13 B | full name, 12 chars + NUL |
| `E+0x4e` | 12 × 6 B | parameter names, NUL-padded, 6 per page × 2 pages |
| `E+0x96` | 12 × u8 | default per parameter |
| `E+0xa2` | 12 × u32 | minimum per parameter (= `P+0x6a`) |
| `E+0xd2` | 12 × u32 | number of selectable values (= `P+0x9a`): 128 = 0–127, 2 = on/off, 17 = MIDI channel |
| `E+0x102` | 12 × u32 | formatter array A (= `P+0x0ca`), §7; `E+0x11a` = A[6] |
| `E+0x132` | 12 × u32 | widget array B (= `P+0x0fa`), §7; `E+0x14a` = B[6] |
| `E+0x176` | u32 | page class handler |
| `E+0x186` | u32 | fourth pointer (almost always 0) |
| `P+0x18a`/`P+0x18e` | u32 | enable bitmap, §3b (past `E+0x192`: the next entry's leading bytes as `E` sees them; `E+0x35` 🟡 is the previous record's) |

A slot named `---` is an empty encoder position. `E+0xd2` is a count, not
a maximum.

Cross-check: `NOTES.md` found the arp key-scale min `0x400d4066` = 0 and
count `0x400d4096` = 25 by tracing the F-knob handler `FUN_4007a2ec`;
`ARPEGGIATOR E+0xa2 + 11×4` and `E+0xd2 + 11×4` are those addresses.
`build.py`'s `ARP_COUNT_AT = 0x400d4096` (25 → 145) is parameter 11's
count in this descriptor.

## 3. The entries

`cls` = `E+0x176`, `fmt` = `E+0x11a` (A[6], slot 6's formatter).

| # | address | id | abbr | name | cls | fmt |
|---|---|---|---|---|---|---|
| 0 | `0x400d2fe4` | — | PB | PLAYBACK (STATIC) | `40032f28` | `4003b64c` |
| 1 | `0x400d3176` | — | PB | PLAYBACK (FLEX) | `40032f28` | `4003b64c` |
| 2 | `0x400d3308` | — | PB | PLAYBACK (THRU) | — | — |
| 3 | `0x400d349a` | — | PB | PLAYBACK (NEIGHBOR) | — | — |
| 4 | `0x400d362c` | — | PB | PLAYBACK (PICKUP) | — | — |
| 5 | `0x400d37be` | — | LFO | LFO (audio) | `400328e4` | `4003bf64` |
| 6 | `0x400d3950` | — | AMP | AMP | `40032ba4` | `4003b6fc` |
| 7 | `0x400d3ae2` | — | — | MIXER (main/cue routing) | `400328e4` | — |
| 8 | `0x400d3c74` | — | — | track recorder | — | `4003b18c` |
| 9 | `0x400d3e06` | — | NOTE | NOTE | — | `4003c770` |
| 10 | `0x400d3f98` | — | ARP | ARPEGGIATOR | — | — |
| 11 | `0x400d412a` | — | LFO | LFO (MIDI) | — | `4003be70` |
| 12 | `0x400d42bc` | — | CTL1 | CONTROL 1 | `40033250` | — |
| 13 | `0x400d444e` | — | CTL2 | CONTROL 2 | `4003347c` | `4003c178` |
| 14 | `0x400d45e0` | — | NONE | NONE | — | — |
| 15 | `0x400d4772` | `0x04` | FLTR | FILTER | `40032814` | `4003bd00` |
| 16 | `0x400d4904` | `0x05` | SPAT | SPATIALIZER | `40032814` | — |
| 17 | `0x400d4a96` | `0x08` | DEL | DELAY | `40032814` | `4003c14c` |
| 18 | `0x400d4c28` | `0x0c` | EQ | EQUALIZER | `40032814` | `4003bb70` |
| 19 | `0x400d4dba` | `0x0d` | DJEQ | DJ EQUALIZER | `400328e4` | — |
| 20 | `0x400d4f4c` | `0x10` | PHSR | PHASER | `40032814` | — |
| 21 | `0x400d50de` | `0x11` | FLNG | FLANGER | `40032814` | — |
| 22 | `0x400d5270` | `0x12` | CHOR | CHORUS | `40032814` | `4003c718` |
| 23 | `0x400d5402` | `0x13` | COMB | COMB FILTER | `40032814` | — |
| 24 | `0x400d5594` | `0x14` | PLTE | PLATE REV | `400328e4` | — |
| 25 | `0x400d5726` | `0x15` | SPRG | SPRING REV | `400328e4` | `4003c718` |
| 26 | `0x400d58b8` | `0x16` | DARK | DARK REV | `400328e4` | — |
| 27 | `0x400d5a4a` | `0x18` | COMP | COMPRESSOR | `400328e4` | — |
| 28 | `0x400d5bdc` | `0x19` | MBC | MULTIBCOMP | `400328e4` | — |
| 29 | `0x400d5d6e` | `0x1c` | LOFI | LO-FI | `400328e4` | — |

15 effects; ids `04 05 08 0c 0d 10 11 12 13 14 15 16 18 19 1c`. The gaps
are where a module's id goes (`MODULES.md`); a stock id is also an FX1 id
(`CLAUDE.md`).

### PLAYBACK entries = machine types

Index = machine type (`FUN_40097168 → 0..4`; ✅ 7 Sep 2026: type 0 reads
the STATIC arena, type 1 the FLEX arena, `docs/history/RTOS_FORK.md` §10.13;
2–4 🟡 from the parameter sets).

| # | page 1 | page 2 | type |
|---|---|---|---|
| 0 | PTCH STRT LEN RATE RTRG RTIM | LOOP SLIC LEN RATE TSTR TSNS | STATIC |
| 1 | same as 0 | | FLEX |
| 2 | INAB VOL --- INCD VOL --- | all `---` | THRU |
| 3 | all `---` | all `---` | NEIGHBOR |
| 4 | PTCH DIR LEN RATE GAIN OP | --- --- --- --- TSTR TSNS | PICKUP |

`TSTR` has 4 values on entries 0/1, 3 on entry 4; `TSNS` 0–127.

### Entry 8 = the track recorder

```
page1  INAB(1/5)  INCD(1/5)  RLEN(64/65)  TRIG(1/3)  SRC3(0/11)  LOOP(1/2)
page2  FIN(0/113) FOUT(0/113) AB(0/128)  QREC(255/18) QPL(255/18) CD(0/128)
```

(default/count.) Decoded to shared RAM by Bryan T, 2 Sep 2026
(`EXTERNAL.md` §6), display values hardware-confirmed: INAB/INCD
`-, A B, A, B, A+B`; RLEN `1…64, MAX` (raw+1, raw 64 = MAX); TRIG `ONE,
ONE2, HOLD`; SRC3 `-, T1…T8, MAIN, CUE`; FIN/FOUT `0, 0.063, 0.125 … 64`
(113-entry ladder at `0x400ab63a`, `L/16`); QREC/QPL `OFF, PLEN,
1,2,3,4,6,8,12,16,24,32,48,64,96,128,192,256` (min −1, the only negative
minimums; ladder u32 table `0x400d80e0`). Storage: bank blob
`+0x8f382 + part×6322 + track×12` (current bank blob `[0x46c82456]`, part
index `0x100b14cf`), SRAM mirror `0x100a54d0 + …`, per-frame published
copy `0x80000cf4 + track×12 + [0x800000e0]×96`. RLEN reaches the engine
as `(raw+1)` steps converted to samples at `0x4006e3b2`. Open: a fresh
part draws TRIG `ONE` and SRC3 `MAIN` where the descriptor defaults are
raw 1 (= ONE2) and 0 (= `-`); the fixup is not located.

### Other decoded pages

```
 5 LFO    SPD1/2/3 DEP1/2/3 | PMTR(30) WAVE(19) MULT(7) TRIG(8) SPD DEP
 6 AMP    ATK HOLD REL VOL BAL XVOL | AMP(4) SYNC(2) ATCK(2) FX1(4) FX2(4) TRIG(5)
 7 MIXER  MAIN DIR GAIN CUE DIR GAIN | MIX ...
 9 NOTE   NOTE(48) VEL(100) LEN(6) NOT2 NOT3 NOT4 | CHAN(17) BANK(129) PROG(129) …
10 ARP    TRAN LEG(2) MODE(7) SPD(96) RNGE(8) NLEN | … LEN(16) … KEY(25)
```

## 3b. Enable bitmaps

`P+0x18e` = parameters 0–7, `P+0x18a` = 8–11, one nibble each, low nibble
first. `FUN_400326d4` (staging a value) and `FUN_40037590` (drawing the
knob) both call `FUN_400a6994(*(u32*)(P+0x18a), *(u32*)(P+0x18e),
4·paramIndex)` and gate on bit 0. The accessor (✅ objdump, 16 Sep 2026) is
a 64-bit arithmetic right shift of the pair by its third argument, low half
returned in D1, high in D0, with a second path for shifts ≥ 32 (params
8–11); it masks nothing, so every bit decision is made at the call site (26
direct calls, 3 through a register, 2 sites read the words inline;
`EXTERNAL.md` §11). Every nibble in the table is one of `0 1 3 5 7 8`; all
31 rows and Bryan T's bit reading were re-read from our image 16 Sep 2026.

| bit | value | meaning | status |
|---|---|---|---|
| 0 | 1 | drawn by the generic renderer and staged by `FUN_400326d4`; a zero nibble is neither | ✅ (31 rows; PICKUP page 2 `0,0,0,0,1,1` draws TSTR and TSNS only, THRU/NEIGHBOR page 2 blank, on the unit) |
| 1 | 2 | a link element tying this knob to the one on its left: STRT/LEN, RTRG/RTIM, RATE/TSTR (STATIC and FLEX), INAB/VOL and INCD/VOL (THRU), BASE/WDTH (FILTER), SHVG/SHVF (DARK REV). Ours since 16 Sep 2026: `Param(link=True)` sets it (`build_bus.penable`, checked by `verify_menu`) on BusVerb SIZE and SHFT, BusDelay FDBK/DENS/PTCH, Spectrum RES/LSP, Modulation DPTH | ✅ on the unit for stock (Bryan T, MKII) and for our clones (image 29, 16 Sep 2026: every linked pair draws its bracket); the drawer is not located |
| 2 | 4 | PLAYBACK page 2 only: LOOP, RATE, TSTR on STATIC and FLEX, SLIC on FLEX alone. At `0x4003780e` the drawer passes `8` (else `0`) as the flags word of the knob renderer `0x400479b4`, which loads it into CCR and takes the `bpl`-not-taken layout at `0x40047ab0` instead of the one at `0x40047b4a` that offsets the dial by `max(0, (0x46c7d244 + 20·index)+4)` (0..3); a record field > 3 or flags bit 0 takes the `0x40047ab0` layout regardless | 🟡 read in objdump 16 Sep 2026, not run; on the unit the six page-2 knobs look identical to each other and SLIC looks the same on STATIC and FLEX (Bryan T) |
| 3 | 8 | AMP p5 XVOL only, bit 0 clear: absent from the AMP page, drawn while a scene button is held; six call sites test mask `0x9` | 🟡 one slot, one mask pattern; the `0x9` sites are not traced to the scene UI |

| page | `p0..p7` / `p8..p11` | nibble 0 |
|---|---|---|
| PLAYBACK 0 (STATIC) | `15311311` / `00001751` | none |
| PLAYBACK 1 (FLEX) | `55311311` / `00001751` | none |
| PLAYBACK 2 (THRU) | `00031031` / `00000000` | p2, p5–p11 (all `---`) |
| PLAYBACK 3 (NEIGHBOR) | `00000000` / `00000000` | all |
| PLAYBACK 4 (PICKUP) | `00110111` / `00001100` | p3 RATE, p6–p9 (`---`) |
| LFO (audio) | `11111111` / `00001111` | none |
| AMP | `11811111` / `00000111` | p11 TRIG (p5 XVOL is `8`) |
| MIXER | `00111111` / `00001000` | p6 MIX, p7–p10 (`----`); p11 is blank-named and `1` |
| recorder | `11111111` / `00001111` | none |
| NOTE | `11111111` / `00000101` | p9, p11 (`----`) |
| ARP | `00111111` / `00001001` | p6, p7, p9, p10 (`-----`) |
| LFO (MIDI) | `11111111` / `00001111` | none |
| CONTROL 1 | `00111111` / `00001111` | p6, p7 (`----`) |
| CONTROL 2 | `11111111` / `00001111` | none |

Named slots with nibble 0: PICKUP p3 RATE, AMP p11 TRIG, MIXER p6 MIX,
LO-FI p1 NOIS. Effect rows are in `EXTERNAL.md` §11's table; each `---`
is 0 and each named knob is 1 except FILTER WDTH and DARK REV SHVF (`3`).
Until 16 Sep 2026 this section's derived lists read `P+0x18e` high nibble
first (ARP "p0 p1 p9 p10", NOTE "p8 p10", MIXER "p0 p1 …", AMP REL `8`);
the hex words were right. The MIXER "drawn anyway" counterexample rested
on that reversed read — MAIN and DIR are `1` — so whether a bespoke page
handler consults the bitmap is unmeasured.

AMP (per track, present for every machine type):

| slot | label | default | count | enable | formatter A |
|---|---|---|---|---|---|
| p0 | ATK | 0 | 128 | 1 | 0 |
| p1 | HOLD | 127 | 128 | 1 | `0x4003b3d0` |
| p2 | REL | 127 | 128 | 1 | `0x4003b408` |
| p3 | VOL | 64 | 128 | 1 | `0x4003c7a0` |
| p4 | BAL | 64 | 128 | 1 | `0x4003c7a0` |
| p5 | XVOL | 127 | 128 | 8 | `0x4003b484` |
| p6 | AMP | 1 | 4 | 1 | `0x4003b6fc` |
| p7 | SYNC | 1 | 2 | 1 | `0x4003c14c` |
| p8 | ATCK | 0 | 2 | 1 | `0x4003b754` |
| p9 | FX1 | 0 | 4 | 1 | `0x4003b6fc` |
| p10 | FX2 | 0 | 4 | 1 | `0x4003b6fc` |
| p11 | TRIG | 0 | 5 | 0 | `0x4003bdd8` |

`p11 TRIG` is the un-drawn AMP slot. Whether an AMP-page value reaches the
DSP record, and whether enabling p11 gives it storage and publication, are
unmeasured; a default outside its count stalls the sequencer (`CLAUDE.md`).

## 4. Page class handlers

Both gate on `0x800000a0` (PERSONALIZE block, `0x80000090`–`0x800000d0`)
and check `0x46c7dd26`:

- `0x40032814`: FILTER, SPATIALIZER, DELAY, EQ, PHASER, FLANGER, CHORUS,
  COMB. Indexes a 20-byte-stride array at `0x46c7d244`.
- `0x400328e4`: DJ EQ, PLATE, SPRING, DARK, COMPRESSOR, MULTIBCOMP, LO-FI,
  the audio LFO, the MIXER. Args at `0x18/0x1c/0x20`, computes `+0x38`.

The split does not follow FX1/FX2 assignment; FX1 already hosts both
classes. Why there are two classes is not decoded.

The resolver `FUN_40031da4(track, page_kind)` ✅:

```c
if (track < 8) switch (page_kind) {                    // audio tracks
  case 0: id = Part[track] @ +0x8eda2; tbl = 0x400d5f38; break;  // machine type
  case 1: return 0x400d37f6;                                     // LFO
  case 2: return (track==7 && DAT_80000034) ? 0x400d2e8a          // master track
                                            : 0x400d3988;         // AMP
  case 3: id = Part[track] @ +0x8ed80; tbl = 0x400d5f58; break;   // FX1
  case 4: id = Part[track] @ +0x8ed88; tbl = 0x400d5fdc; break;   // FX2
  return tbl[id];
}
switch (page_kind) {                                   // MIDI tracks (>= 8)
  case 0: return 0x400d3e3e;  // NOTE      case 3: return 0x400d42f4;  // CTRL 1
  case 1: return 0x400d4162;  // LFO       case 4: return 0x400d4486;  // CTRL 2
  case 2: return 0x400d3fd0;  // ARP
}
```

`FUN_400326d4(descriptor, page, out)` stages a page into a 0x16-stride
working array, `min` from `P+0x6a`, `count` from `P+0x9a`, `page ? 6 : 0`
bias.

## 5. Storage and delivery

### 5a′. The live lane is the lock record ✅ (port, 18 Sep 2026)

A track's live lane (`0x80000810 + 72·t`) begins with the same 32 slots a
pattern's step lock record holds (`tools/hw/ot_bank.py`): PLAYBACK page 1
0–5, LFO page 1 6–11 (SPD1–3 DEP1–3, lane defaults 32 32 32 0 0 0), AMP
12–17 (ATK HOLD REL VOL BAL XVOL, defaults 0 127 126 64 64 127), FX1 page 1
18–23, FX2 page 1 24–29 (a locked value on slot *k* lands in lane byte
*k*; a distinct lock in every slot 0–11, 30, 31 of one trig confirmed each).
The page-2 lanes follow (§5a: AMP p2 +0x2c, FX1 p2 +0x32, FX2 p2 +0x38).
`tools/hw/ot_spec.py` names locks by these slots.

### 5a. The Part's page arrays ✅ (port, 12 Sep 2026)

DB = the part pointer (`0x46c82456`; `0x400e21e0` under `ot_emu`), t =
track:

| array | per track | order (6 bytes each) |
|---|---|---|
| page 1 | `DB + 0x8ee9a + t·24` | LFO · AMP · FX1 · FX2 (FX1 p1 `+0x8eea6`, FX2 p1 `+0x8eeac`; = the page-1 writer's `flat − 6`) |
| page 2, read by the dial | `DB + 0x8f06c + t·30` | machine · LFO · AMP · FX1 (`+0x8f07e`) · FX2 (`+0x8f084`) |
| page 2, PLAYBACK editor storage | `DB + 0x8ef5a + t·30 + 6·machine + slot` | indexed by `0x460d5c30` |

The bank file's page-2 block (`ot_project.P2_OFF 0x307 + t·30`, FX1 p2 at
+0, FX2 p2 at +6) has the DB display array's order from the FX1 column on.

### 5b. Page-2 editors ✅ (port, 13 Sep 2026)

Each page has its own page-2 editor. Retracted the same day: "`0x4003a474`
is the FX page-2 editor". It is PLAYBACK's: `0x460d5c30` indexes
`0x400d5f38[machine]`, Part store `+0x8ef5a + t·30 + machine·6 + slot`, live
write `0x80000830 + t·72 + slot`.

| editor | entry | Part store | shadow | live lane (`0x80000810 + t·72 +`) |
|---|---|---|---|---|
| FX1 page 2 | `0x4003abe4(slot2, delta)` | `DB + part·6322 + 0x8f07e + t·30 + slot` (pc `0x4003acb2`) | `0x100a51cc + …` | +0x32 |
| FX2 page 2 | `0x4003a9dc(slot2, delta)` | `… + 0x8f084 + t·30 + slot` (pc `0x4003aaaa`) | `0x100a51d2 + …` | +0x38 |
| AMP page 2 | `~0x4003ae..` | — | — | +0x2c |

Each reads the slot's id from the Part (`+0x8ed80 + t` / `+0x8ed88 + t`),
takes the descriptor from `0x400d5f58[id]` / `0x400d5fdc[id]`, clamps by
`P+0x6a`/`P+0x9a`, and has no page or index term (FX1 editor called for
T1, T3, T8 under the emulator, THRU included). The page-1 writer
`0x40054cd8(track, flat, value)`: FX1 slot k at `+0x12 + k`, FX2 slot k at
`+0x18 + k`. The lane store has no page term: page index 0..3 moves only
the Part/shadow bytes.

### 5c. The copier ✅ (port, 13 Sep 2026)

`0x4000cae8` (loop `0x4000cb2a..cb98`, eight tracks) takes three six-byte
page-2 blocks per track from the live lane `0x80000810 + t·72` into the
DSP record `0x80000110 + 64·t`:

| lane bytes (`t·72 +`) | lands in | page |
|---|---|---|
| `+0x20..+0x2b` | ColdFire record `0x80000510 + 48·t` only | PLAYBACK p2, LFO p2 (never the DSP) |
| `+0x2c..+0x31` | DSP record hw 21–23 | AMP p2 |
| `+0x32..+0x37` | DSP record hw 18–20 | FX1 p2 |
| `+0x38..+0x3d` | DSP record hw 24–26 | FX2 p2 |

Measured with marker bytes (scratchpad `copier_markers.py`).

### 5d. Effect ids into shared RAM ✅

`apply_part` publishes both ids as two adjacent 8-byte arrays, one byte per
track, immediately before the live scene buffer `0x80000ed4 + t·0x40`:

```asm
40009370  movea.l D4,A1              ; D4 = track
40009372  adda.l #-0x7ffffef0,A1     ; A1 = 0x80000110 + track
4000937e  adda.l #0x8ed80,A0         ; FX1 id in the Part
40009384  move.b (A0),(0xdb4,A1)     ; -> 0x80000ec4[track]
4000938c  addq.l #0x8,A2             ; +8 = the FX2 id field (0x8ed88)
4000938e  move.b (A2),(0xdbc,A1)     ; -> 0x80000ecc[track]
```

Nine ColdFire sites touch these arrays; each FX1 site has an FX2
counterpart 12–20 bytes away (`0x40004c22` reaches FX2 through `+8` off
`lea 0x80000ec4,A6`). Ghidra's `ReferenceManager` reports zero references
(all displacement-based). On the ColdFire side the two slots differ only
by an 8-byte offset; the descriptor path forwards nothing to the DSP.

### 5e. FX1 on hardware (MKII, `OCTATRACK_FX1TEST.bin`)

| FX1 = | result |
|---|---|
| PLATE / SPRING / DARK REV | works; save + power cycle survives |
| DELAY | selectable, UI complete, no audible effect; FX1 and FX2 both DELAY: FX1 still silent |
| reverb on FX1 and FX2 | audio glitches, severity varies by reverb type |

The id→algorithm mapping is not slot-restricted. The delay's silence is
per-effect, DSP-side; 🟡 a per-slot buffer pointer whose FX1 entry is never
initialised fits every observation (one shared on-demand buffer does not).
`FUN_40005638` references the FILTER and DELAY descriptors because it is
the part-defaults initialiser (a new part is FX1 = FILTER, FX2 = DELAY),
not a buffer lead. Two reverbs exceed the DSP's budget (🟡 cycles, from
the per-type variation). `DSP.md` §5 for the delay.

### 5f. Adding an effect: five tables

| # | table | keyed by | if missing |
|---|---|---|---|
| 1 | id lookup `0x400d5f58` (FX1) / `0x400d5fdc` (FX2) | id | descriptor unresolvable |
| 2 | chooser list `0x400d6060` (FX1) / `0x400d6090` (FX2) | position | not offered |
| 3 | its own 402 B descriptor, copied from `P` | — | copied from `E`: correct name and id, no knobs (the enable bitmap falls off the end) |
| 4 | the id byte at `P+0x03` | — | two list entries sharing a descriptor are one effect |
| 5 | id → cursor position `0x400d6150` | id | selecting it jumps to NONE |

(3)/(4): `FUN_40052474` does `*(Part+0x8ed88) = (char)*(int*)list[cursor]`,
the low byte of the word at `P+0`. (5): `FUN_4005996c` counts the list to
its terminator, then seeds the cursor from `0x400d6150[id]` (`FLTR`→1,
`EQ`→2, … `DARK`→14); an id absent from it selects position 0 = NONE.

## 6. The page-2 slot map ✅

Each page-2 word carries two controls: the knob field at bits 16–23 and a
companion field at bits 8–15. The low byte is never published. The field a
slot is delivered in is fixed by the slot; its count and renderer are free.
Slot 6 is on `$c`; `$b` is not a page-2 parameter word.

| slot | word | field | example (BusVerb / BusDelay) |
|---|---|---|---|
| 6 | `$c` | knob, bits 16–23 | MODE / MODE |
| 7 | `$c` | bits 8–15 | SHMR / MDEP |
| 8 | `$d` | knob, bits 16–23 | DIFF / MRAT |
| 9 | `$d` | bits 8–15 | SHFT / SIZE |
| 10 | `$e` | knob, bits 16–23 | GATE / PTCH |
| 11 | `$e` | bits 8–15 | RATE / FRZE |

Evidence: MODE on slot 7 read bits 8–15 across five positions on hardware;
SHMR needed `$c`'s knob field, not `$b`'s; slot 11 was dead for both
effects while it read bits 0–7 (fixed `7a4f96b`). Retracted 4 Sep 2026: "a
stepped control can only live on 7, 9 or 11" (stock puts CHORUS TAPS on 6,
FILTER HP/ENV/Q2 on 6/8/10, 128-value knobs on 9 and 11). Both bus
engines' MODE moved to slot 6 (4 Sep 2026) because the main-menu page-2 knob
editor (`MAINMENU.md` §9c-ii) writes even slots only; ✅ tag 84: MODE steps
as a select on slot 6, SHMR/MDEP sweep 0–127 from slot 7 (a count-128 knob
in a companion field works; the 10 Aug "near-boolean companion" reading was
the inherited formatter). The first play after the move stalled on stored
parts (`CLAUDE.md`, stamp-defaults).

`dsp_host` implements this map (`cd8964a`); a param-driven companion
renders bit-identical to the `MODE=`/`DMODE=` build-time overrides, which
exist because the harness previously mapped slots 6–11 onto `$b..$e`
cyclically (slot 6 on `$b`: the delay's WOW worked locally and never on
hardware). `send_probe` has `--dmode/--dptch/--dfrz/--width/--gate/--rdel`.
`dsp_host` writes params once before the first block; a mid-run change
(FREEZE on a filled line) is hardware-only.

## 7. Display formatters ✅ (r2, 24 Aug 2026)

Array A (`P+0x0ca`), one signature: `void fmt(char *buf, int value)`
(`4(a7)` = buf, `8(a7)` = value); every stock one wraps `sprintf`
(`0x40013a08`).

| formatter | prints | used by |
|---|---|---|
| `0x4003c718` | `"%d", value + 1` | stepped selects (TAPS, TYPE, MODE/PTCH/FRZE), DELAY TIME |
| `0x4003c14c` | `value ? "ON" : "OFF"` (the label is the format string) | DELAY X/TAPE/SYNC/LOCK/PASS |
| `0x4003c770` | `value ? "%d" : "OFF"` | NOTE CHAN |
| `0x4003c7a0` | `value − 64`, `"+%d"` / `"%d"` | SPRING BAL, bipolar donors |

Strings: `"%d"` `0x400b465d`, `"OFF"` `0x400b4e78`, `"ON"` `0x400b7702`,
`"+%d"` `0x400b449f`. A labelled select is a ~20-byte cave: index a pointer
table by value, `jmp sprintf` (`modules/tempo-sync/time_fmt.s`). A
formatter may read globals (tempo `0x80001814`, BPM×24).

Array B (`P+0x0fa`) draws the widget; each has its position count
hard-coded (`cmp #N` after a common prologue):

| B | widget |
|---|---|
| `0x40047254` | 5-position ticks (CHORUS TAPS; borrowed for MODE/PTCH/FRZE, so PTCH's 4 values sit on a 5-tick widget) |
| `0x40047424` | 3-position (SPRING TYPE) |
| `0x400477d4` | boolean (DELAY's switches) |
| `0x400467a4` / `0x4004661c` | numeric bar (NOTE) |
| `0x40046f10` / `0x40046d9c` / `0x40046c28` / `0x40046ab4` | the PLAYBACK-page select: 2 / 3 / 4 / 5 positions, one body, a `cmp #N-1` bound and a 17x7 icon table each (`0x400be2f2`, `0x400be2fa`, `0x400be306`, `0x400be316`); a value past the bound draws nothing. The 5-position one is unreferenced in stock; REPITCH's TSTR uses it (✅ 16 Sep 2026, `docs/firmware/REPITCH.md`) |
| `0x400479b4` | the knob (PTCH, RATE); a negative value draws its frame alone (`0x40047a0e`) |
| `0` | plain dial printing A's text (stock DELAY TIME: `A=0x4003c718, B=0`; used for labelled selects wider than five because the tick widget stops at value 4) |

A formatter overrides the count: a cloned slot inherits the donor's A/B,
and a count-128 slot on a 3-entry word-label renderer draws nothing
(`CLAUDE.md`; `verify_menu` checks renderer against count).
`tools/build/stock_labels.py` reads the stock labels by calling each A
formatter under the emulator (`emu_bringup._call`): FILTER HP/LP
"12dB|24dB", ENV "BASE|WDTH", EQ TYP "LOW|PEQ|HIGH", PHASER NUM "2..10",
COMB PTCH "A#0".."A 9".

Unmeasured: the buffer length behind `buf` (stock's longest label is 4
chars; ours ≤ 5, "1/16T"); whether A is consulted where B's count matters.

## 8. Not decoded

- `E+0x35` flags.
- The six `E+0x00` pointers (🟡 one per encoder).
- Why the effects split across two page classes.
- What `0x800000a0` (PERSONALIZE) switches.
- Enable-nibble bit 2 (what the `0x40047ab0` layout changes on screen) and
  bit 3 (whether the six mask-`0x9` sites are the scene-edit path); the
  link-element drawer for bit 1; the four undecoded `0x4004exxx` call
  sites (§3b, `EXTERNAL.md` §11).
- Which staged index and live-lane bytes an FX1 page-2 edit uses when
  opened from the page key (`0x4005a5b0`, the 4→3 remap; no emulator
  drives it): a hardware read (turn a station's MODE, SAVE, read the part
  file). Gates per-mode defaults on the unit (`PLAN.md`).
