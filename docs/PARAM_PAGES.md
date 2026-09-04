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

> The table starts one entry earlier than a printable-name walk finds: entry
> −1 at `0x400d2e52` has a blank name, which is why such a
> walk skips it; `FUN_40031da4` returns it (`0x400d2e8a` =
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

**Decoded end to end by Bryan T, 2 Sep 2026 (`EXTERNAL.md` §6)** — the first
non-FX page followed from this descriptor to shared RAM. Display values, all
hardware-confirmed: INAB/INCD `-, A B, A, B, A+B`; RLEN `1…64, MAX` (raw+1,
raw 64 = MAX); TRIG `ONE, ONE2, HOLD`; SRC3 `-, T1…T8, MAIN, CUE`; FIN/FOUT
`0, 0.063, 0.125 … 64` steps (the 113-entry ladder at `0x400ab63a`, `L/16`);
QREC/QPL `OFF, PLEN, 1,2,3,4,6,8,12,16,24,32,48,64,96,128,192,256` (min `−1`,
the only two parameters with a negative minimum; the numeric ladder is a u32
table at `0x400d80e0`). Storage is three-tiered: the bank blob at
`+0x8f382 + part×6322 + track×12` (the "Part" of §5b/§5c, spelled out —
`[0x46c82456]` is the current bank blob, and the part index is `0x100b14cf`),
an SRAM mirror at `0x100a54d0 + …`, and a per-frame **published copy** at
`0x80000cf4 + track×12 + [0x800000e0]×96` that the recorder's own code reads.
RLEN reaches the engine as `(raw+1)` sequencer steps converted to samples at
`0x4006e3b2`. ⚠️ Two defaults here are NOT what a fresh part shows: TRIG draws
`ONE` (descriptor raw 1 = ONE2) and SRC3 draws `MAIN` (descriptor 0 = `-`); a
fixup somewhere overrides the descriptor and has not been found.

## 3b. Free parameter slots — surveyed across every page

Read straight from the per-parameter enable bitmaps (`P+0x18e` = slots 0-7,
`P+0x18a` = slots 8-11, one nibble each, **0 = disabled, no knob drawn**). Done
while looking for somewhere to put a per-track SEND level for the bus, since the
delay's own twelve are all in use (`BUS.md`).

| page | enable `p0..p7` / `p8..p11` | slots with NO knob |
|---|---|---|
| PLAYBACK 0 | `15311311` / `00001751` | none |
| PLAYBACK 1 | `55311311` / `00001751` | none |
| PLAYBACK 2 | `00031031` / `00000000` | p0 p1 p2 p5 p8 p9 p10 p11 |
| PLAYBACK 3 | `00000000` / `00000000` | all twelve |
| PLAYBACK 4 | `00110111` / `00001100` | p0 p1 p4 p10 p11 |
| LFO (audio) | `11111111` / `00001111` | none |
| **AMP** | `11811111` / `00000111` | **p8** |
| routing | `00111111` / `00001000` | p0 p1 p9 p10 p11 |
| recorder | `11111111` / `00001111` | none |
| NOTE | `11111111` / `00000101` | p8 p10 |
| ARP | `00111111` / `00001001` | p0 p1 p9 p10 |
| LFO (MIDI) | `11111111` / `00001111` | none |
| CONTROL 1 | `00111111` / `00001111` | p0 p1 |
| CONTROL 2 | `11111111` / `00001111` | none |

> ### CAVEAT that invalidates part of this table (photographed on the unit)
>
> **The enable bitmap only governs the GENERIC parameter-page renderer. A page
> drawn by bespoke code ignores it entirely.**
>
> Descriptor 7 is the **MIXER** screen. Its bitmap marks `p0 MAIN` and `p1 DIR`
> as not drawn — and a photograph of the unit shows **`MAIN` right there on
> screen**, alongside `MIX`, `CUE` and both `DIR`/`GAIN` pairs. Every one of
> descriptor 7's parameters is visible and editable. The MIXER simply does not
> use the generic renderer, so its bitmap says nothing about what the user sees.
>
> Consequences:
> * **Descriptor 7 has no free slots.** Dead as a control-surface candidate.
> * **"Not drawn" in this table means only "the generic renderer skips it."** It
>   is not evidence the parameter is unused, and for any page with a custom
>   screen it does not even predict visibility.
> * The table below is still a correct reading of the *bitmaps*. It is not a
>   reliable list of free knobs, and was wrongly presented as one.
>
> **Cheap check before trusting any candidate: look at the page on the unit.**
> If AMP page 2 shows a gap where `ATCK` would sit, the bitmap governs there and
> AMP is a generic page. If `ATCK` is visible, the same trap has struck twice.

**AMP is the interesting page** — always present regardless of machine type, and
per-track, which is the granularity a send level needs. Its full table:

| slot | label | default | count | enabled | formatter `P+0x0ca` |
|---|---|---|---|---|---|
| p0 | `ATK` | 0 | 128 | 1 | 0 |
| p1 | `HOLD` | 127 | 128 | 1 | `0x4003b3d0` |
| p2 | `REL` | 127 | 128 | 8 | `0x4003b408` |
| p3 | `VOL` | 64 | 128 | 1 | `0x4003c7a0` |
| p4 | `BAL` | 64 | 128 | 1 | `0x4003c7a0` |
| p5 | `XVOL` | 127 | 128 | 1 | `0x4003b484` |
| p6 | `AMP` | 1 | 4 | 1 | `0x4003b6fc` |
| p7 | `SYNC` | 1 | 2 | 1 | `0x4003c14c` |
| **p8** | **`ATCK`** | 0 | **2** | **0** | `0x4003b754` |
| p9 | `FX1` | 0 | 4 | 1 | `0x4003b6fc` |
| p10 | `FX2` | 0 | 4 | 1 | `0x4003b6fc` |
| p11 | `TRIG` | 0 | 5 | 1 | `0x4003bdd8` |

* **`p8 ATCK` is the only genuinely un-drawn slot, and it is a boolean** (count
  2). Using it as a level means widening the count to 128 and zeroing its
  formatter as well as enabling it — three edits to a stock page, not one.
* **`XVOL` (p5) is marked ENABLED but it does not appear in the
  GUI.** It is a full 128-range page-1 slot with a custom formatter
  (`0x4003b484`), and a formatter is exactly what decides whether and how a
  parameter draws — the same mechanism that made our `→DEL` render as
  "MIX / SEND" regardless of value count (§5e, `REVERB.md`).
  **Do not assume it is free.** `XVOL` is almost certainly *crossfader volume*;
  a parameter can be consumed by the engine while not being directly editable.
  Repurposing it would likely break crossfader behaviour, which is a flagship
  feature. **Test first: does the crossfader change that track's level?** If it
  does, `XVOL` is live and off-limits. If it does nothing, it is a far better
  candidate than `ATCK`.

### What a probe build would have to establish

Enabling a slot draws a knob. It does **not** follow that the value goes
anywhere. A control has to travel UI → Part storage → publication → the DSP's
per-track record, and a slot disabled since the factory may have no storage and
no publication path behind it. Two questions, in order:

1. **Does an AMP-page parameter reach the DSP at all, and at which offset?**
   AMP values drive the voice, not an effect, so it is not known whether they
   land anywhere an FX effect's `r6` can see. Note the FX record's `r6+6..$a` is
   measured as touched by nothing (`DSP.md` §9) — worth checking whether AMP
   values land there.
2. **Does enabling `p8` give it storage and publication, or is it inert?**

Method is `dsp/page2_probe.asm`'s, which settled the FX page-2 mapping and is
the precedent to copy: give each candidate offset a **distinct audible
signature**, expose the slot with a full 0..127 range, flash once, sweep.

Two recorded traps, both of which apply here:

* **A probe comparing whole words against `64<<16` cannot see a companion
  field.** Earlier probes did exactly that and drew the wrong conclusion.
* **Defaults must be in range.** A default outside its own value count is used
  as an index and stalled the sequencer on hardware — so widening `ATCK`'s count
  means checking its default too.

Settling page 2 took seven probe builds; budget similarly, and note this one edits a
**stock, always-present page shared by every track**, where page 2 only ever
edited our own clones.

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

### `P+0x18a` / `P+0x18e` — the per-parameter ENABLE BITMAP (decoded)

Those "two further fields" are **a nibble per parameter, bit 0 = this parameter
exists**. `FUN_400326d4` (staging a value) and `FUN_40037590` (drawing the knob)
both call `FUN_400a6994(*(u32*)(P+0x18a), *(u32*)(P+0x18e), paramIndex)` and gate
on the returned bit 0 — so a zero nibble means the knob is neither staged nor
drawn.

| word | parameters | nibble order |
|---|---|---|
| `P+0x18e` | 0–7 | low nibble = parameter 0 |
| `P+0x18a` | 8–11 | low nibble = parameter 8 |

Verified against stock: every `---` slot has nibble 0 and every named knob has
bit 0 set, on all four effects checked. SPRING REV
(`TIME --- --- HP LP MIX | TYPE BAL --- --- --- ---`) is the clearest case —
`P+0x18e = 0x11111001`, `P+0x18a = 0x00000000`. `NONE` is all zeros, as expected.
Some slots carry `3` rather than `1` (DARK's `SHVF`, FILTER's `WDTH`); the extra
bits are not decoded, and `FUN_40037590` separately tests bit 2 to pick a display
flag. Plain `1` is what the large majority of stock parameters use.

**This is the field that makes a cloned descriptor work or silently do nothing**,
and it is the reason the `P` vs `E` distinction above is not academic: a clone
copied as `E .. E+0x192` (rather than `P .. P+0x192`) loses exactly the tail
these two words live in, and the effect appears in the menu with a correct name
and **not a single knob**. That mistake cost two hardware flashes to find.

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

## 5d. HARDWARE RESULT — reverbs work on FX1, delay does not

Flashed `OCTATRACK_FX1TEST.bin` to a real MKII running OS 1.40C via the CF-card
OS UPGRADE path. Loaded cleanly.

| effect added to FX1 | result |
|---|---|
| PLATE REV | **works** |
| SPRING REV | **works** |
| DARK REV | **works** |
| DELAY | selectable, but **no audible effect** |

**What the reverbs prove.** The id→algorithm mapping is *not* slot-restricted. The
DSP will run a reverb algorithm requested from the FX1 slot, with no change beyond
two lookup tables. So the stock 10-vs-14 split is not a hard architectural
boundary, and — importantly for the wider question — an effect id is a loosely
coupled selector, not something the DSP validates against the slot. That is the
condition under which an unused id could host a custom descriptor.

**What the delay result means.** The failure is specific to one effect, not to the
slot, so the cause is a per-effect resource rather than a per-slot permission.
Leading hypothesis: the delay needs a delay-line buffer that is allocated only for
the FX2 slot, so an FX1 delay runs with no buffer and produces nothing. Untested.

`FUN_40005638` references the FILTER and DELAY descriptors directly, but it
is not a lead: it is the
**part defaults initialiser** — it copies `E+0x3b` out of each of those two
descriptors into a fresh part's structure, because a new part defaults to
**FX1 = FILTER, FX2 = DELAY**. It has no connection to delay-line buffers. The
real question — where the delay runs, given id `0x08` is a passthrough — is open
and the DSP is ruled out; see `DSP.md` §5.

### Follow-up hardware tests

| test | result |
|---|---|
| FX1 **and** FX2 both = DELAY | FX1 still silent |
| DELAY UI on FX1 | fully present, parameters move and display; audio unaffected |
| two reverbs at once (FX1 + FX2) | **audio glitches**, severity varies by reverb |
| FX1 = reverb, save + power cycle | **survives**, reloads correctly |

**The buffer hypothesis was narrowed, not confirmed or killed.** Co-selecting
DELAY on both slots rules out *one shared delay buffer allocated on demand*. It
does **not** rule out a **per-slot buffer pointer whose FX1 entry is never
initialised** — that version fits every observation.

The UI behaving perfectly while audio is untouched confirms the ColdFire side is
complete: the id is stored, resolved, displayed and published to shared RAM
correctly. Whatever refuses the delay is on the far side of the chip boundary.

**The glitching is the more important practical finding.** Two simultaneous
reverbs exceed something the DSP was provisioned for — unsurprising, since stock
firmware makes that combination impossible, so nothing in the DSP budget had to
allow for it. Severity varying by reverb type is consistent with a cycle budget
rather than a memory limit. It is audio-only misbehaviour, harmless to the
hardware, but it means **this build is not a free upgrade**: FX1 reverb is usable,
FX1 + FX2 reverb is not reliably usable.

### Where this leaves the two questions

- *Can an unused id host a custom descriptor?* The reverbs say the mechanism
  allows it. Any such effect is still limited to algorithms the DSP already
  implements, and is subject to the same unbudgeted-cycles risk.
- *Why is delay silent?* Now purely a DSP-side question. Settling it means
  disassembling the DSP program (`COVERAGE.md`); nothing further is extractable
  from the ColdFire image.

## 5e. Adding an effect needs FIVE tables, not two

Discovered the hard way while making a custom effect selectable — each missing
piece fails differently, and none of them error:

| # | table | keyed by | consequence if missing |
|---|---|---|---|
| 1 | id lookup `0x400d5f58` (FX1) / `0x400d5fdc` (FX2) | effect id | descriptor unresolvable |
| 2 | chooser list `0x400d6060` (FX1) / `0x400d6090` (FX2) | position | not offered in the menu |
| 3 | **its own descriptor record** (402 B, **from `P`, not `E`**) | — | see below |
| 4 | descriptor's **id byte** at `P+0x03` | — | see below |
| 5 | **id -> cursor position `0x400d6150`** | effect id | selecting it jumps to NONE |

> **(3) is measured from `P = E + 0x38`** (§5b), so a clone must copy
> `P .. P+0x192`. Copying `E .. E+0x192` looks right, lands the name and id in
> the correct places, and still produces an effect with **no knobs at all**,
> because the enable bitmap at `P+0x18a`/`P+0x18e` falls off the end. See §5b.

**(3) and (4)**: the stored effect id comes from the *descriptor*, not the list
position — `FUN_40052474` does `*(Part+0x8ed88) = (char)*(int*)list[cursor]`,
i.e. the low byte of the word at `P+0`, which is the id at `P+0x03`. So two list
entries sharing one descriptor **are the same effect**: selecting the second
stores the first's id and the cursor snaps back to it. A new effect needs its own
402-byte record with its own id byte.

Note the same line indexes the id table by the **whole** 32-bit word at `P+0`, so
the three bytes above the id must be zero.

**(5)** is the one with no obvious reason to exist. `FUN_4005996c` counts the
list by scanning to its terminator (so a longer list is handled correctly), but
then seeds the cursor from `0x400d6150[id]`. It is a reverse map of the chooser
order — `FLTR`→1, `EQ`→2, … `DARK`→14 — and an id missing from it selects
position 0, which is `NONE`. Every other table can be perfectly correct and the
effect will still appear unselectable.

## 6. Not yet decoded

- `E+0x35` flags (6 bytes).
- The six `E+0x00` per-encoder pointers — purpose inferred, not confirmed.
- Why the effects split across two page classes.
- What `0x800000a0` (PERSONALIZE word) actually switches.
- Which of entries 0/1 is FLEX and which STATIC; the machine-type ordering against
  `FUN_40097168`.
- Whether the sparse effect-id gaps are usable for a new effect slot.


---

## ⚠️ THE PAGE-2 SLOT MAP

**Each page-2 word carries TWO controls: the KNOB field at bits 16–23 and a
COMPANION field at BITS 8–15.** Not the low byte. The low byte is never
published.

**The rule is slot -> word -> bit field, whatever a module calls its knobs.**
The examples below are named `<BusVerb> / <BusDelay>` because those were the
only two effects when this was measured; a module names its own twelve slots
in its manifest and the mapping is unchanged.

❌ **RETRACTED 4 Sep 2026: "a stepped control can only live on 7, 9 or 11".**
That was our convention, not the panel's. The stock descriptors put CHORUS
TAPS (a 5-way select) on slot 6, FILTER's HP/ENV/Q2 on 6/8/10, and plain
128-value knobs on 9 and 11 (CHORUS FBLP, FILTER DIST); COMB FILTER's PTCH
(108 values) is on page 1. The field a slot is DELIVERED in is fixed by the
slot; its count and renderer are free. **Both bus engines' MODE moved to
slot 6 the same day**, because the panel's page-2 knob editor
(`docs/MAINMENU.md` §9c-ii) writes even slots only — a MODE there can be set
from a main-menu screen through the firmware's own routine, one on 7/9/11
cannot. Proven locally: every mode of both engines renders bit-identically
through the new fields (`send_probe --rmode/--dmode`, which drives the
parameter word; `render_reverb --mode` forces the decoded value and cannot
see this). ✅ **Confirmed on hardware the same day (tag 84):** MODE draws
and steps as a select on slot 6, and SHMR / MDEP sweep smoothly from slot 7 —
a count-128 knob in a companion field works, so the 10 Aug "near-boolean
companion" reading is retired (it was the inherited formatter). ⚠️ The
first play stalled the sequencer until the project was refreshed: parts
saved under the old layout hand the count-3 slot a 0–127 byte
(`docs/FLASHPLAN.md`, the MODE re-slot).

| slot | word | field | example (since 4 Sep 2026) |
|---|---|---|---|
| 6 | `$c` | knob, bits 16–23 | **MODE** / **MODE** |
| 7 | `$c` | **bits 8–15** | SHMR / MDEP |
| 8 | `$d` | knob, bits 16–23 | DIFF / MRAT |
| 9 | `$d` | **bits 8–15** | SHFT / SIZE |
| 10 | `$e` | knob, bits 16–23 | GATE / DRV |
| 11 | `$e` | **bits 8–15** | RATE / FRZE |

⚠️ **Slot 6 is on `$c`, not `$b`.** `$b` is not a page-2 parameter word at all.

**The evidence**, because the map was inferred from behaviour rather than
documented anywhere:
- **MODE (then slot 7) read bits 8–15 and worked** — swept on hardware across
  five positions, repeatedly. (Slot 6 / bits 16–23 since 4 Sep 2026; the
  field map itself is what this measured, and it stands.)
- **SHMR independently needed `$c`'s knob field, not `$b`'s** — the
  same off-by-one word.
- **Slot 11 confirmed dead for both effects TESTED** (BusVerb's →DEL and BusDelay's
  FRZE), which rules out a per-effect descriptor fault and leaves the
  slot itself.

Everything that read bits 0–7 had never worked on hardware: slot 9 and slot 11,
in both effects then existing, until this map was applied (fixed in `7a4f96b`).

⚠️ **The trap this map explains**: dsp_host used to write only KNOB fields
(`(pv[i] & 0x7f) << 16`) and mapped slots 6–11 onto `$b,$c,$d,$e` cyclically —
so slot 6 landed on `$b`, which is exactly why the delay's WOW always worked
locally and never on hardware. `DMODE=`/`DINT=`/`DFRZ=` exist as build-time
overrides for that reason. **A green local render says nothing about whether
a page-2 companion control publishes** unless the harness implements this
map.

✅ dsp_host now implements this exact map (`cd8964a`), and a
param-driven companion renders **bit-identical** to the
build-time overrides (`MODE=`/`DMODE=`) it duplicates — with negative
controls. `send_probe` has `--dmode/--dptch/--dfrz/--width/--gate/--rdel`.
The end-to-end path is proven locally: BusVerb's `-DEL` select at 3 feeds
BusDelay at 0.375 FS peak; at 0, digital silence.
⚠️ What is STILL impossible locally: changing a parameter **mid-run** —
dsp_host writes params once before the first block — so FREEZE still engages
at sample 0 and holds silence. Testing freeze-on-a-filled-line remains
hardware-only; that limitation is the harness dispatcher's, not the map's.

## 7. Display formatters, decoded (24 Aug 2026 — static, r2)

Asked for by the tempo-sync work: can a knob show "1/8" instead of 64? Yes,
and cheaply. Every per-slot formatter (`P+0x0ca`, the "A" array) has ONE
signature, and it is trivial:

```c
void fmt(char *buf, int value);      // 4(a7) = buf, 8(a7) = value
```

and every stock one is a thin wrapper over `sprintf` (`0x40013a08`):

| formatter | what it prints | used by |
|---|---|---|
| `0x4003c718` | `sprintf(buf, "%d", value + 1)` | every stepped select (TAPS, TYPE, our MODE/PTCH/FRZE), DELAY TIME |
| `0x4003c14c` | `sprintf(buf, value ? "ON" : "OFF")` — **the label IS the format string** | DELAY X/TAPE/SYNC/LOCK/PASS |
| `0x4003c770` | `value ? "%d" : "OFF"` | NOTE CHAN |
| `0x4003c7a0` | `value − 64` with `"+%d"` / `"%d"` | SPRING BAL, our bipolar donors |

Strings: `"%d"` `0x400b465d`, `"OFF"` `0x400b4e78`, `"ON"` `0x400b7702`,
`"+%d"` `0x400b449f`.

**So a labelled select is a ~20-byte code cave:** index a pointer table by
`value`, put the pointer where the format string goes, `jmp sprintf`. The
table and the strings are data in the same cave region the tempo cave lives
in (`0x400d7000..0x400d7c3c`, 3 KB free). We already ship a ColdFire cave
and the build pins/verifies its bytes, so the mechanism is proven.

**The "B" array (`P+0x0fa`) is the WIDGET drawer**, and each one has its
position count hard-coded (the same prologue, then `cmp #N`):

| B callback | widget |
|---|---|
| `0x40047254` | 5-position ticks (CHORUS TAPS — and what we borrowed for MODE/PTCH/FRZE, which is why PTCH's 4 values sit on a 5-tick widget) |
| `0x40047424` | 3-position (SPRING TYPE) |
| `0x400477d4` | boolean (DELAY's five switches) |
| `0x400467a4` / `0x4004661c` | numeric bar (NOTE) |
| `0` | **the plain dial with the A text** — stock DELAY TIME is `A=0x4003c718, B=0` |

There is no 12-position widget, and none is needed: `B = 0` draws the dial
and prints whatever A wrote.

**A formatter may read globals.** It gets only `(buf, value)`, but the
tempo is at `0x80001814` (BPM×24, `DSP.md` §6c). So a FREE TIME dial can
print "1/8" when its ms value lands within a tolerance of a division at the
current tempo, and "%d" otherwise — the "newer devices" behaviour. That is
option 3's display half, and it is small; the DSP half (snap TIME to the
nearest division inside the same tolerance) is ~100 words. Costed but NOT
built (Sam: investigate only).

**Reading the labels back (2 Sep 2026):** because the words are printed
rather than stored, `tools/stock_labels.py` simply *calls* every stock
select's A formatter on the emulated ColdFire (`emu_bringup._call`) for
each legal value and records `buf` — FILTER HP/LP print "12dB|24dB", ENV
"BASE|WDTH", EQ TYP "LOW|PEQ|HIGH", PHASER NUM "2..10", COMB PTCH note
names "A#0".."A 9". Static decoding of eleven formatters was never needed.

**Two things still unmeasured:** the buffer length behind `buf` (stock's
longest label is "OFF"/"%d" of 3–4 chars; our labels would be ≤ 5,
"1/16T"), and whether the A formatter is also consulted anywhere the B
widget's count matters (a count-12 dial with `B=0` is stock DELAY TIME's
own configuration, so this is low-risk). Both are one flash to settle.

