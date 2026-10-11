# The track LFOs

ColdFire side of OS 1.40C. Three LFOs per track, eight tracks, evaluated
once per audio frame inside the frame builder. Read out of the binary by
Bryan T (21 Sep 2026) and re-read here in objdump
the same day (section 8); nothing below has been run under the port yet.

Status key as `CHIP.md`: ✅ read from our image · 🟡 inferred from
what was read · ⬜ open.

## 1. Where it is ✅

Inline in the frame builder at `0x4000cf40`–`0x4000d09e` (`MACSR = 0x20`
set at `0x4000cf60`), and a second copy as a standalone function at
`0x40003b90` that computes the ping offsets itself from `[0x800000e0]`
(`a2 += ping·0x180`, `a5 += ping·0x200`); no direct `jsr` to it in the
image (⬜ reached through a pointer). The DSP has no LFO code: the wavetable
bank at `X:0x6c00`/`X:0x7000`/`X:0x7400` is LO-FI's (selector `P:0x1b85`,
`base = 0x6c00 + (param − 1)·0x400` from `x:(r6+$d)`).

Loop shape: outer over `a4` from `0x80004890` down by 8 until below
`0x80004858` (eight tracks); inner `d2 = 2, 1, 0` (three LFOs); a counter
at `sp@(4)` starts at 23 and decrements per LFO. Pointers per iteration:

| reg | start (inline) | step | what it is |
|---|---|---|---|
| `a2` | `sp@(128) + 0x80000660` | −48 per track | `0x80000510 + ping·0x180 + 48·t`, the ColdFire page record (`PARAM_PAGES.md` section 5c); start = track 7 🟡 |
| `a3` | `0x8000136c` | −28 per LFO | LFO state record `i = 3·t + lfo`, array `0x800010e8 + 28·i`, 24 records, ending at `0x80001388` |
| `a4` | `0x80004890` | −8 per track | per-track trig flags byte (⬜ record not decoded) |
| `a5` | `sp@(94) + 0x800002b8` | −64 per track | `a5 + 24 = 0x80000110 + ping·0x200 + 64·t`, the DSP voice record |
| `acc1`/`acc2` | `0x80000000` / `0x7fff80ff` | — | saturation floor / ceiling |
| `acc3` | `[0x8000181c] << 2` | — | tempo24 × 4 |

🟡 The track order (7 → 0) follows from the two immediates against the
record bases `PARAM_PAGES.md` and `MIDI.md` already hold; the `sp` slots
are the ping offsets the standalone copy computes. A `--pcwatch` run under
the port would make it ✅. The state-array base is also the end address of
an apply-part loop (`cmpal #0x800010e8` at `0x400094a8`).

## 2. The records ✅

### The page record `a2` (`0x80000510 + 48·t`)

| offset | contents |
|---|---|
| `+0x00`–`+0x17` | 12 words: the scene-crossfaded page-1 values, PLAYBACK 0–5, LFO 6–11 (SPD1–3 at words 6–8, DEP1–3 at 9–11) |
| `+0x18`–`+0x1d` | lane `+0x20..+0x25` (the copier, `PARAM_PAGES.md` section 5c): PLAYBACK page 2; `+0x1c` is the TSTR byte `REPITCH.md` reads |
| `+0x1e + i` | PMTR *i* (byte, `mvsb`); lane `+0x26..` |
| `+0x21 + i` | WAVE *i* (`mvsb`); lane `+0x29..` |
| `+0x24 + i` | MULT *i* (`mvzb`); lane `+0x3e..` |
| `+0x27 + i` | TRIG *i* (`mvzb`); lane `+0x41..` |
| `+0x2a`–`+0x2f` | ⬜ (the copier does not write them) |

The four byte groups are the displacements `1e 21 24 27` in the extension
words at `0x4000d032`, `0x4000cfbe`, `0x4000cfd6`, `0x4000cf88` (hex;
Bryan's note reads the last two as decimal, giving MULT `+0x18` and TRIG
`+0x1b`, which is where PLAYBACK page 2 and TSTR sit). SPD *i* at word 6+i
is itself destination 6+i, so an LFO can modulate another LFO's speed. Word 12+ of the scene numbering (AMP 12–17, FX1 18–23,
FX2 24–29) is not in this record: see the destination rule below. This
settles `MIDI.md` Appendix C section 1's two 🟡 rows: scene bytes 6–11 are LFO page 1 and
12–17 are AMP page 1.

### The LFO state record `a3` (28 bytes, `0x800010e8 + 28·(3·t + lfo)`)

| offset | contents |
|---|---|
| `+0` | phase value handed to the waveform handler |
| `+4` | handler's raw output |
| `+8` | live / held modulation value; read once, at `0x4000d054` |
| `+12`, `+16`, `+20` | ⬜ |
| `+24` | phase accumulator, modulus `0x791fd` (496,125) |

### The designer table (`0x80001388`, 16 bytes per LFO index)

The designer handler `0x40003a90` (audio) takes `sp@(20)` = the loop
counter (= `3·t + lfo`), reads step bytes at `0x80001388 + 16·i + step`
and a per-LFO word at `0x80000110 + 2·(0x9fc + i)` = `0x80001508 + 2·i`
whose bit *step* selects linear interpolation to the next step (else a
held step). Apply-part copies 16 bytes per entry from the Part's designer
data (`part + 0x1702 + …`, `0x40009320`) into it. 🟡 That copy is where
the T1–T8 choice is resolved (all eight T slots share the handler, which
never sees the WAVE value). The MIDI handler `0x40003b10` reads its steps
from `0x46c76dc0` instead.

## 3. Phase, rate, MULT, TRIG ✅

```
4000cfa8  mvsw  %a2@(0xc,%d2:l:2),%d6      ; SPD (word 6+lfo)
4000cfb0  mulsl %d3,%d6                    ; × tempo24·4
4000cfba  macl  #8657,%d6,%a3@,%d1,%acc0
4000cfc8  addl  %a3@(24),%d6               ; phase accumulator
4000cfd6  mvzb  %a2@(0x24,%d2:l),%d4       ; MULT
4000cfda  cmpl  %d3,%d6 / subl %d3,%d6     ; wrap at 496125
4000cfe2  asll  %d4,%d0                    ; MULT is a left shift, 2^0..2^6
4000cfe4  movel %d6,%a3@(24)
```

MULT has seven values because it is a shift count; its formatter
`0x4003bda4` prints `1 << value` (clamped to 7). TRIG (`a2@(0x27+lfo)`)
selects a 16-byte control record at `0x80006184 + 16·n`, with one bit of
`a4@` masked through the word at `0x80006284 + 4·n` adding 8 to *n*; bytes
12–15 of the record steer the store offset (below) and the masks. ⬜ The
eight modes' records are not decoded individually.

## 4. Waveform dispatch ✅

```
4000d004  lea   0x400d6210,%a1
4000d012  movel %d1,%a3@                   ; phase value → record +0
4000d014  moveal %a1@(0,%d7:l:4),%a1       ; d7 = WAVE byte, mvsb, no bound
4000d01e  moveal %a3,%a0
4000d022  jsr   %a1@
```

Handler ABI: `a0` = the state record, input at `a0@(0)`, result written
to `a0@(4)`; the designer handler also reads `sp@(20)`. Everything after
the call is shape-agnostic.

`0x400d6210`, 32 longwords (audio LFOs); `0x400d6290`, 32 longwords (MIDI
LFOs, consumer `0x40003f56`, which masks the index to 31):

| index | audio | MIDI |
|---|---|---|
| 0–10 | `0x4000385c 3888 38bc 38cc 38dc 3910 3944 3990 39dc 3a04 3a30` = TRI ITRI SAW ISAW SQR ISQR EXP IEXP RMP IRMP RND | same |
| 11–18 | `0x40003a90` ×8 (designer, T1–T8) | `0x40003b10` ×8 |
| 19–31 | `0x400038bc` ×13 (SAW; padding) | same |

The audio table is referenced from the inline engine (`0x4000d006`) and
the standalone copy (`0x40003c6c`) only.

## 5. Output ✅

```
4000d024  mvzb  %fp@(12),%d0               ; TRIG record byte 12: 4 or 8
4000d028  movel %a3@(4),%d1
4000d02e  movel %d1,%a3@(0,%d0:l)          ; → +4 (held) or +8 (live)
4000d032  mvsb  %a2@(0x1e,%d2:l),%d4       ; PMTR
4000d038  cmpl  #12,%d4 / blt              ; < 12: a0 = a2, else a0 = a5
4000d03e  mvsw  %a2@(0x12,%d2:l:2),%d0     ; DEP (word 9+lfo)
4000d042  lea   %a0@(0,%d4:l:2),%a1        ; destination word
4000d046  cmpiw #0x7f00,%d0 / seq / and #256   ; full DEP → +256
4000d054  movel %a3@(8),%d1                ; THE LFO VALUE
4000d05a  mvsw  %a1@,%d3                   ; unmodulated destination
4000d05c  asll  #8,%d0
4000d05e  movel %d3,%acc0
4000d060  macl  %d0,%d1,%acc0              ; dest + DEP·LFO
4000d06c  movclrl / satsl against acc1, acc2
4000d07a  movew %d0,%a1@
```

Destination *d* = PMTR: `d < 12` → word *d* of the page record (PLAYBACK
0–5, LFO 6–11); `d ≥ 12` → word `d` off `a5`, i.e. `0x80000110 + 64·t +
2·(d − 12)`: the DSP voice record's halfwords 0–17 (AMP 0–5, FX1 6–11, FX2
12–17), the same halfwords the scene morph writes (`MIDI.md` Appendix C section 1). HOLD
works through the store offset at `0x4000d02e`: a mode whose byte 12 is
not 8 leaves `+8` untouched, so the held value persists.

**Low byte of the store (measured, port, 5 Oct 2026).** `ot_emu --watch-pc
0x4000d07a` on bottleservice with `tools/harness/stress_project.py` (24 LFOs
per part, depth 18-28 on FX1/FX2 knobs), 900 frames: 21,088 output stores,
each modulating its destination; 21,011 wrote a halfword with a non-zero low
byte (e.g. `d0 = 0x22fe` for knob 34). 147 stores had knob byte 0 (the clamp
at the bottom of the range) and all 147 had a non-zero low byte; the largest
knob byte seen at the clamp was 0x7d. Each halfword is one DSP word `<< 8`,
so an LFO-modulated knob word has non-zero bits 8-15. On the gate project at
LFO depth 0, all 19,843 stores had a zero low byte. DSP code reads of
page words take `and #>$7f0000` first (`AGENTS.md`).

## 6. Extending it

Measured against the image; none built.

**A slew (one-pole on the LFO value).** One insertion site: between the
load at `0x4000d054` and the `macl`, smoothing every waveform identically
with no change to TRIG, depth or saturation. Needs one long of state per
LFO (`+12`/`+16`/`+20` ⬜ until mapped, else widen the 28-byte stride:
base `0x8000136c`, step at `0x4000d068`, the apply-part loop at
`0x400094a8`, and the designer table that starts at the array's end).
Both LFO pages are full (counts `128 ×6 | 30 19 7 8 128 128`), so a SLEW
knob displaces a slot or is not a knob; as extra waveforms it needs no
slot.

**Waveforms past 19.** Four places, all read from our image:

1. Dispatch: slots 19–31 of `0x400d6210` (and `0x400d6290` for MIDI) are
   pre-filled padding; write the handler's address into one.
2. Count: WAVE is slot 7, counts are `u32` at `E + 0xd2 + 4·slot`, so
   **`0x400d38ac`** (audio, `E = 0x400d37be`) and **`0x400d4218`** (MIDI,
   `E = 0x400d412a`), both 19. (Bryan's note has `0x400d386c` /
   `0x400d41d0`, which hold 0.) The knob writer clamps to the descriptor
   count (`PARAM_PAGES.md` section 5b); ⬜ whether anything else bounds it.
3. Storage: WAVE is a byte at `part + 0x2f2 + 30·t + 3 + n`, masked to
   seven bits by the UI accessor; the engine's `mvsb` reads it signed with
   no bound. Values ≤ 127 store and reload unchanged.
4. Labels: the WAVE formatter `0x4003be4c` does `value &= (19 > value) ?
   −1 : 0` — an index ≥ 19 draws label 0 — then indexes the pointer array
   `0x400be38e` (19 longwords, packed against TRIG's `FREE` at
   `0x400be3da`) and jumps to `0x40013a08`. The array has exactly one
   reference, the `lea` immediate at `0x4003be5c`. So: a relocated array,
   the immediate at `0x4003be5c`, and the `moveq #19` at `0x4003be50`.

**A fourth LFO per track** changes the Part layout (every LFO field is
packed three-wide, section 7) and is not planned.

## 7. Part storage ✅ (`0x40057538`–`0x40057690`)

`part = bank + 0x8ed80 + part·0x18b2`; the resolver takes the page-2 slot
in `d3`, the current LFO *n* (`0x460d1a32`), and branches on
`[0x80000012]` for MIDI:

| slots | audio | MIDI |
|---|---|---|
| 0–1 PMTR / WAVE | `part + 0x2f2 + 30·t` | `part + 0x4e8 + 36·t` (❌ was `0x2e8`) |
| 2–3 MULT / TRIG | `part + 0x30a + 30·t` | `part + 0x500 + 36·t` (❌ was `0x300`) |
| 4–5 SPD / DEP | `part + 0x11a + 24·t` | `part + 0x3e8 + 32·t` (❌ was `0x268 + 36·t`) |

then `+ 3·(slot & 1) + n`. 📖 Re-read 10 Oct 2026: the MIDI offsets are
the `addal` immediates `0x8f268` (`0x40057598`), `0x8f280` (`0x400575c8`) and
`0x8f168` (`0x400575f4`) from the bank base, i.e. `0x4e8`, `0x500` and `0x3e8`
from `part`; the SPD / DEP path (`0x400575da`) shifts the track by 5 (stride
32), the other two by 5 plus 2 (stride 36). ❌ Retracted: the MIDI column
`0x2e8` / `0x300` / `0x268`. `0x2f2 + 8·30 = 0x3e2` and `0x30a + 7·30 + 6 =
0x3e2` are the base of the MIDI tracks' page-1 array (`part + 0x3e2` = bank
`+ 0x8f162`); the MIDI page-2 (setup) array is at `part + 0x4e2` (bank
`+ 0x8f262`, `MIDI_TRACKS.md` section 1). ❌ Retracted: "`0x3e2` is the MIDI
page-2 array". The audio
page-2 array is `part + 0x2f2 + 30·t`, per track PMTR×3 WAVE×3 · AMP p2 ·
FX1 p2 · FX2 p2 · MULT×3 TRIG×3. Designer data: `part + 0x1702 + 16·t`
(audio), `+ 0x1792` (MIDI).

## 8. Provenance: what was checked (22 Sep 2026)

Bryan T's handoff answered two open questions (a slew control; more than
19 waveforms). Re-read in objdump against our image and matching: the engine
at `0x4000cf84`–`0x4000d096` (inline in the frame builder, `MACSR =
0x20`), 24 iterations, the 28-byte state record with the phase
accumulator at `+24` (modulus `0x791fd`), the value read once at
`0x4000d054`, MULT as `asll`, the destination rule (`PMTR < 12` → the page
record, else the `a5` record), both 32-entry dispatch tables with slots
19–31 as `0x400038bc` padding, the handler ABI (`a0`, `+0`/`+4`), the
19-entry label array at `0x400be38e` packed against `FREE`, the Part
resolver's six bases, and that `0x400074a0`/`0x40007502` are the
recorder's FIN/FOUT fades over a `1/n` table (`a4@(6)`/`(7)`, the
recorder page's slots 6 and 7).

❌ Retracted on it: `DSP.md`'s "LFO speed `0x400074a0`/`0x40007502`, MULT
table `0x400ab83a`" (they are the fade generator; the LFO rate is `SPD ×
tempo24 × 4` and MULT is a shift). `PARAM_PAGES.md` section 5a's page-2 display
array at `+0x8f06c` with a machine column: his `part + 0x2f2` / `+ 0x30a`
(re-read at `0x4005762c`/`0x4005765a`) put PMTR/WAVE and MULT/TRIG at
`+0x8f072 + 30·t` and `+0x8f08a + 30·t`, which is his "open discrepancy"
resolved in his favour — the array starts six bytes later than we had it
and ends on the MIDI array. `MIDI.md` Appendix C's two 🟡 rows (scene bytes
6–11 and 12–17) are LFO p1 and AMP p1.

❌ Corrected from the handoff, above (found in the re-read):
- WAVE's count: `0x400d386c` / `0x400d41d0` hold 0. The counts are `u32`
  at `E + 0xd2 + 4·slot`; WAVE is slot 7, so `0x400d38ac` (audio) and
  `0x400d4218` (MIDI), both 19.
- The page record's MULT and TRIG bytes are at `+0x24` and `+0x27`, not
  `+0x18` and `+0x1b`: the displacements `24`/`27` in the `mvzb` extension
  words are hex. `+0x18..+0x1d` is PLAYBACK page 2 (`REPITCH.md`'s TSTR at
  byte 28 sits there).
- The label array's reader and its only reference: the WAVE formatter
  `0x4003be4c` (`lea` immediate at `0x4003be5c`), which also clamps the
  index with a `moveq #19`; a count bump needs that word too.
- The MIDI dispatch table is not identically shaped: its designer slots
  hold `0x40003b10`, which reads steps from `0x46c76dc0`.

Taken one step further (🟡 objdump): the iteration order is track 7 → 0
(`a2 = 0x80000510 + 48·7`, `a5 + 24 = 0x80000110 + 64·7` at the first
iteration; the `sp` slots are ping offsets, computed explicitly by the
standalone copy of the engine at `0x40003b90`); the state array is
`0x800010e8 + 28·(3·t + lfo)`, ending at the designer table `0x80001388`
(16 bytes per LFO index, with a per-LFO slope word at `0x80001508 +
2·i`); the copier's lane `+0x3e..+0x43` carries MULT/TRIG into the record.
Open, as he left it: the state record's `+12/+16/+20`, the TRIG modes'
records, whether anything but the descriptor count bounds WAVE, and how
the T1–T8 choice reaches the per-LFO designer copy.
