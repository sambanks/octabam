# Parameter-page descriptor table (OS 1.40C, MKII)

Reverse-engineered from `out/raw/section_3_MAIN_OS.bin` (SHA256 `164f3122…`), base
`0x40000400`, so `file_offset = vaddr − 0x40000400`. Everything below is read
directly out of the image; nothing is inferred from a running unit.

`COVERAGE.md` marks the 17 effects as ⬜ untouched. That is true of the **algorithms**
(they live on the DSP56xxx). It is not true of the **control surface**: every effect's
parameter names, defaults, value ranges and per-page handlers sit in one table in
ColdFire data, fully decodable.

The table is not FX-specific. It describes **every parameter page on the machine** —
sample playback (one entry per machine type), AMP, LFOs, the track recorder, MIDI
NOTE/ARP/CTRL pages, and the effects.

---

## 1. Table bounds

```
0x400d2e52 .. 0x400d5f00     31 entries × 402 (0x192) bytes = 12,462 B
```

> Corrected after the Ghidra pass: the table starts one entry earlier than first
> measured. Entry −1 at `0x400d2e52` has a blank name, which is why a
> printable-name walk skipped it; `FUN_40031da4` returns it (`0x400d2e8a` =
> `0x400d2e52 + 0x38`) for track 7 when `DAT_80000034` is set — the **master
> track** page.

402 is not a multiple of 4, so **this is a packed serialised blob, not a
compiler-laid-out C struct** — absolute alignment shifts 2 bytes per entry, and the
embedded 32-bit pointers are frequently misaligned. Any code walking it must do
unaligned longword reads (fine on ColdFire V4, with a penalty).

There is no `lea`/immediate reference to the table base `0x400d2fe4` anywhere in the
image, which is why a conventional xref sweep never finds this table. Entries are
reached individually, not through a base pointer.

## 2. Entry layout (offsets relative to entry start `E`)

| offset | size | field |
|---|---|---|
| `E+0x00` | 6 × u32 | per-encoder handler pointers (usually `0x40038d94` ×6) |
| `E+0x18` | 29 B | zero |
| `E+0x35` | 6 B | flags — **not decoded** (e.g. `11 11 11 00 00 00` for CHORUS) |
| `E+0x3b` | u8 | effect id (0 for non-FX pages) |
| `E+0x3c` | 5 B | display abbreviation, NUL-terminated (`CHOR`) |
| `E+0x41` | 13 B | full name, NUL-terminated (`CHORUS`) |
| `E+0x4e` | 12 × 6 B | parameter names, NUL-padded — 6 per page, 2 pages |
| `E+0x96` | 12 × u8 | **default value** per parameter |
| `E+0xa2` | 12 × u32 | **minimum value** per parameter |
| `E+0xd2` | 12 × u32 | **number of selectable values** per parameter |
| `E+0x102` | 24 B | zero |
| `E+0x11a` | u32 | formatter / custom-display callback (0 = none) |
| `E+0x14a` | u32 | secondary callback (0 = none) |
| `E+0x176` | u32 | page class handler |
| `E+0x186` | u32 | fourth pointer (almost always 0) |
| | | **total 0x192** |

A parameter slot named `---` is a deliberately empty encoder position. `E+0xd2` is a
*count*, not a maximum: `128` means a 0–127 continuous parameter, `2` an on/off, `17`
the MIDI channel selector (16 channels + off).

### Cross-validation

`NOTES.md` located two arp addresses independently, by tracing the F-knob encoder
handler `FUN_4007a2ec`. The struct decode lands on exactly the same two addresses via
a completely different route — which confirms the layout:

| NOTES (via encoder handler) | this decode (via struct) |
|---|---|
| arp key-scale min `0x400d4066` = 0 | ARPEGGIATOR `E+0xa2 + 11×4` = `0x400d4066` = 0 |
| arp key-scale count `0x400d4096` = 25 | ARPEGGIATOR `E+0xd2 + 11×4` = `0x400d4096` = 25 |

So `build.py`'s `ARP_COUNT_AT = 0x400d4096` (25 → 145) is simply *"parameter 11's value
count in the ARPEGGIATOR descriptor"*. The shipped arp key-scale feature is the first —
apparently accidental — use of this table.

## 3. The 30 entries

`cls` = page class handler (`E+0x176`), `fmt` = formatter (`E+0x11a`).

| # | address | id | abbr | name | cls | fmt |
|---|---|---|---|---|---|---|
| 0 | `0x400d2fe4` | — | PB | PLAYBACK | `40032f28` | `4003b64c` |
| 1 | `0x400d3176` | — | PB | PLAYBACK | `40032f28` | `4003b64c` |
| 2 | `0x400d3308` | — | PB | PLAYBACK | — | — |
| 3 | `0x400d349a` | — | PB | PLAYBACK | — | — |
| 4 | `0x400d362c` | — | PB | PLAYBACK | — | — |
| 5 | `0x400d37be` | — | LFO | LFO (audio) | `400328e4` | `4003bf64` |
| 6 | `0x400d3950` | — | AMP | AMP | `40032ba4` | `4003b6fc` |
| 7 | `0x400d3ae2` | — | — | *(unnamed — routing)* | `400328e4` | — |
| 8 | `0x400d3c74` | — | — | *(unnamed — recorder)* | — | `4003b18c` |
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

**15 effects.** Effect ids are sparse (`04 05 08 0c 0d 10 11 12 13 14 15 16 18 19 1c`) —
the gaps are unassigned or reserved slots, and are the obvious place to look when
asking whether an effect can be *added* rather than modified.

### The five PLAYBACK entries = the five machine types

Entries 0–4 are one page per machine type, matching the dispatch
`FUN_40097168 → 0..4` already found in `NOTES.md`. The mapping below is **inferred
from the parameter sets**, not yet confirmed against the dispatch order:

| # | page 1 | page 2 | reading |
|---|---|---|---|
| 0 | PTCH STRT LEN RATE RTRG RTIM | LOOP SLIC LEN RATE TSTR TSNS | FLEX / STATIC |
| 1 | *(identical to 0)* | | STATIC / FLEX |
| 2 | INAB VOL --- INCD VOL --- | all `---` | **THRU** (input AB/CD volume) |
| 3 | all `---` | all `---` | **NEIGHBOR** (no parameters) |
| 4 | PTCH DIR LEN RATE GAIN OP | --- --- --- --- TSTR TSNS | **PICKUP** |

`TSTR` (timestretch) has 4 selectable values on entries 0/1 and 3 on entry 4;
`TSNS` (sensitivity) is a full 0–127. So the timestretch *mode selector* is here in
ColdFire data even though the algorithm is on the DSP.

### Entry 8 = the track recorder

```
page1  INAB(1/5)  INCD(1/5)  RLEN(64/65)  TRIG(1/3)  SRC3(0/11)  LOOP(1/2)
page2  FIN(0/113) FOUT(0/113) AB(0/128)  QREC(255/18) QPL(255/18) CD(0/128)
```

Record source AB/CD (5 values each), record length (65), trig mode (3), a third source
with 11 options, fade in/out (113), and quantised record/play (18 values, default
`255` = off). This is the whole sampling front-end's parameter model.

### Other decoded pages

```
 5 LFO    SPD1/2/3 DEP1/2/3 | PMTR(30) WAVE(19) MULT(7) TRIG(8) SPD DEP
 6 AMP    ATK HOLD REL VOL BAL XVOL | AMP(4) SYNC(2) ATCK(2) FX1(4) FX2(4) TRIG(5)
 7 —      MAIN DIR GAIN CUE DIR GAIN | MIX ...          (main/cue routing)
 9 NOTE   NOTE(48) VEL(100) LEN(6) NOT2 NOT3 NOT4 | CHAN(17) BANK(129) PROG(129) …
10 ARP    TRAN LEG(2) MODE(7) SPD(96) RNGE(8) NLEN | … LEN(16) … KEY(25)
```

19 LFO waveforms and 30 modulation destinations are both single `u32` counts —
the same shape of field the arp patch already proved is safely widenable.

## 4. Handlers

Two page classes cover the effects, and both gate on `0x800000a0` — a word in the
**PERSONALIZE settings block** (`NOTES.md` maps that block at `0x80000090`–`0x800000d0`),
alongside a check of `0x46c7dd26`:

- **`0x40032814`** — FILTER, SPATIALIZER, DELAY, EQ, PHASER, FLANGER, CHORUS, COMB.
  Indexes a 20-byte-stride array at `0x46c7d244` (`a2 = 0x46c7d244 + idx*20`).
- **`0x400328e4`** — DJ EQ, PLATE, SPRING, DARK, COMPRESSOR, MULTIBCOMP, LO-FI, plus
  the audio LFO and the routing page. Different signature (args at `0x18/0x1c/0x20`,
  computes `+0x38`).

The split does not follow FX1/FX2 slot assignment and is not yet explained.

The `E+0x11a` formatter is present only where a parameter needs non-numeric display
(DELAY's `X`/`TAPE`/`SYNC`, CHORUS's `TAPS`, NOTE's note names). CHORUS and SPRING REV
share `0x4003c718`.

The six `E+0x00` pointers are one per encoder on the page (inference from the count);
`0x40038d94` is the shared default. FILTER has all six zeroed, MULTIBCOMP has the
fifth zeroed.

## 5. What this makes possible without touching the DSP

Every one of these is a data edit or a small detour, in the same style as the shipped
patches, and needs no DSP work:

- **Change any parameter's range or resolution** — the `E+0xd2` count field. Proven
  safe: this is exactly what the shipped arp key-scale patch does (25 → 145).
- **Change defaults** — the `E+0x96` byte array.
- **Rename parameters / repurpose `---` slots** — an effect like FLANGER has six empty
  page-2 slots whose names and ranges are pure data.
- **Retarget an effect id** to a different descriptor.
- **Recorder and playback behaviour** — quantise options, fade curves, record lengths,
  timestretch mode counts are all here.

The hard boundary stays where it was: none of this changes what the DSP *does* with a
parameter. Widening `TSTR` to a fifth value gets you a fifth selectable mode that the
DSP has no code for. Data edits reach the control surface; new behaviour behind a
parameter still needs the DSP56300 work described in `COVERAGE.md`.

## 5b. Confirmed by decompilation (Ghidra 12.1.2 pass)

`FUN_40031da4(track, page_kind)` is the resolver, and it settles the layout:

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

Every fixed return is an entry start + 0x38, which confirms that **the canonical
struct base is the pointer stored in the tables, `P = E + 0x38`** — not the entry
start used for the field table in §2. Re-based, the two arrays the decompiler
reads directly are `min = P+0x6a` and `count = P+0x9a`, exactly the offsets
`NOTES.md` already recorded for this function. Add `0x38` to every §2 offset to
get the P-relative form; the fields listed *before* `E+0x38` belong to the
**previous** record.

`FUN_400326d4(descriptor, page, out)` stages a page into a 0x16-stride working
array, reading `min` from `P+0x6a` and `count` from `P+0x9a` with a `page ? 6 : 0`
bias — i.e. six parameters per page, two pages, as the layout implies. It also
reads two further fields at `P+0x18a`/`P+0x18e`, so the record really is 0x192
bytes long measured from `P`.

**Bearing on the FX1 experiment**: the effect id is used for *one* thing here —
indexing the descriptor table, `return tbl[id]`, with no side effects and no
bounds check beyond the table's own extent. Nothing in this path forwards the id
to the DSP, which is consistent with (but does not yet prove) the algorithm being
selected elsewhere. Where the DSP is actually told which effect to run is still
open, and is the one thing the hardware test will settle empirically.

Supporting evidence that the slots are symmetric: FX1 already hosts effects of
**both** page classes (class A `0x40032814`: FILTER SPAT EQ PHSR FLNG CHOR COMB;
class B `0x400328e4`: DJEQ COMP LOFI), and the four effects being added span both.
So the page-class handler is not what excludes delay and reverb from FX1.

## 5c. Where the effect id crosses to the DSP

`apply_part` publishes both ids into the `0x80000000` window — the RAM shared with
the DSP56300 — as two **adjacent 8-byte arrays**, one byte per track:

```asm
40009370  movea.l D4,A1              ; D4 = track
40009372  adda.l #-0x7ffffef0,A1     ; A1 = 0x80000110 + track
4000937e  adda.l #0x8ed80,A0         ; FX1 id in the Part data
40009384  move.b (A0),(0xdb4,A1)     ; -> FX1 id array 0x80000ec4[track]
4000938c  addq.l #0x8,A2             ; +8 = the FX2 id field (0x8ed88)
4000938e  move.b (A2),(0xdbc,A1)     ; -> FX2 id array 0x80000ecc[track]
```

`0x80000ec4[8]` / `0x80000ecc[8]` sit immediately before the live scene buffer at
`0x80000ed4 + track*0x40`, so the whole per-track audio state is one contiguous
block in shared RAM.

**Every ColdFire site touching these arrays treats the two slots identically.**
Eight of the nine FX1 sites have an FX2 counterpart 12–20 bytes away, in adjacent
code. The ninth (`0x40004c22`) only looks unpaired: it does `lea 0x80000ec4,A6`
and reaches the FX2 array through a `+8` displacement off the same base, because
the arrays are contiguous — the same one-base-serves-both idiom as the `0x8ed80` /
`0x8ed88` Part fields.

Ghidra's `ReferenceManager` reports **zero** references to these addresses, because
every access is displacement-based off a base register. That is the mirror image of
the trap `NOTES.md` records for the scalar sweep: a reference sweep finds absolute
operands and misses computed ones. Both sweeps are needed.

**Conclusion for the FX1 experiment.** On the ColdFire side the two FX slots are
structurally identical: same descriptor mechanism, same table shape, same page
classes, same publication path into DSP-shared RAM, differing only by an 8-byte
offset. Nothing in the control processor treats FX1 as the lesser slot — the
restriction is purely the contents of two lists.

The residual risk is therefore **entirely on the DSP side** and is not answerable
from this binary at all: whether the DSP provisions delay-line memory or cycles
per slot. That is across the chip boundary, and settling it statically means
disassembling the DSP program (`COVERAGE.md`). The hardware test answers it in
about two minutes instead.

## 6. Not yet decoded

- `E+0x35` flags (6 bytes).
- The six `E+0x00` per-encoder pointers — purpose inferred, not confirmed.
- Why the effects split across two page classes.
- What `0x800000a0` (PERSONALIZE word) actually switches.
- Which of entries 0/1 is FLEX and which STATIC; the machine-type ordering against
  `FUN_40097168`.
- Whether the sparse effect-id gaps are usable for a new effect slot.
