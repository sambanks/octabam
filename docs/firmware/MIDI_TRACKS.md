# The MIDI tracks: setup record, live copy, writers, outgoing MIDI, CTRL labels

Where a MIDI track's setup lives in the Part, what the UI writers store when
a setup value changes, how the unit sends it out, and where the CTRL pages
draw their knob labels. Written for BRAIN (`docs/proposals/BRAIN.md`) and
for any module that applies a template to the eight MIDI tracks.

Markers: 📖 read from `out/raw/section_3_MAIN_OS.bin` in
`m68k-elf-objdump -m m68k:cfv4e` output (7 Oct 2026), 🟡 inferred from that
reading. Nothing in this document was run under the port or on a unit.
Addresses are SDRAM addresses, `address = 0x40000400 + file offset`.
Spot-checked a second time against the image on 10 Oct 2026: the setup-record
writers `0x4003fd34` and `0x4003f80c`, the program/bank send `0x4009ec70`,
the cache invalidation `0x4009a3e0`, the label draw call `0x4004e474`, the
project-settings writer `0x40088288` and the LFO resolver immediates.

Notation: `B` = bank RAM = `*0x46c82456` = `0x400e21e0 + bank*0x9b340`;
`p` = Part 0..3; `t` = MIDI track 0..7; `T` = `0x100b14cc`, the UI's current
track 🟡; `P#` = `0x100b14cf`, the current Part 🟡. `0x80000002` is the
current bank and `0x80000003` the current Part as `0x4009eec8` reads them 📖.

## 1. The setup record 📖

Per Part and MIDI track, 0x24 bytes: `B + 0x8f262 + p*0x18b2 + t*0x24 + off`.
It holds the five MIDI pages' page-2 slots. The page-1 record (values) is
`B + 0x8f162 + p*0x18b2 + t*0x20` (`MIDI.md` Appendix A section 3).

| off | content |
|---|---|
| `+0x00` | CHAN: 0 = off, else channel + 1 (count 17); NOTE setup slot 0 |
| `+0x01` | BANK, 128 = off |
| `+0x02` | PROG, 128 = off |
| `+0x03` | unused |
| `+0x04` | SBNK, 128 = off |
| `+0x05` | unused |
| `+0x06..0x08` | LFO PMTR x3 |
| `+0x09..0x0b` | LFO WAVE x3 (resolver `0x40057598`, `LFO.md` section 7) |
| `+0x0c..0x11` | ARP setup; LEN at `+0x0e`, KEY at `+0x11` by slot order 🟡 |
| `+0x12..0x13` | CTRL1 setup slots 0 and 1, unused |
| `+0x14..0x17` | CC1..CC4 numbers (defaults 7, 1, 2, 10) |
| `+0x18..0x1d` | CC5..CC10 numbers (defaults 71..76) |
| `+0x1e..0x20` | LFO MULT x3 |
| `+0x21..0x23` | LFO TRIG x3 (resolver `0x400575c8`) |

Page-1 flat indices of `0x40054cd8` for a MIDI track: 0-5 NOTE, 6-11 LFO
SPD/DEP, 12-17 ARP, 18 PB, 19 AT (channel pressure), 20-29 the values of
CC1..CC10. Page-1 `+0x1e` and `+0x1f` of the record are the per-slot enable
bitmaps of CTRL1 and CTRL2: a clear bit draws OFF and a bar, a set bit draws
the value and a knob. The bits are XOR-toggled in the knob-press code around
`0x4004ed74..0x4004ef24` (entry not located), which writes the Part, the CS1
mirror and the live byte 📖.

## 2. The live copy 📖

`0x46c76dc0 + t*0x44`: `+0x00..0x1f` is page 1 and `+0x20..0x43` the setup
record. The Part apply at `0x40009094` fills it (loop `0x400094fe..0x4000953c`)
and then calls `0x4009ec70(bank, p)`. The live setup byte for record offset
`off` is `0x46c76de0 + t*0x44 + off`.

## 3. The UI writers 📖

Every UI writer uses `T` and `P#`. Each stores:

- the Part byte;
- the CS1 mirror `0x100a53b0 + p*0x18b2 + t*0x24 + off`;
- the unsaved bit `B + 0x95048 |= 1<<p` and the byte `0x100b145e |= 1<<p`;
- `B + 0x9b332 = 1` and `0x100f8598 = 1` (unidentified, as in `MAINMENU.md`
  section 7);
- a call to `0x40027e00`;
- the live byte.

| writer | arguments | writes |
|---|---|---|
| `0x4004ae08` | `0x38 + slot`, phase | NOTE SETUP, one slot; commits on phase 0; stage `0x460d5cb4` (6 longs); redraw `0x40036548`; slot 0 calls `0x4009a3e0`; tail-jumps to `0x4009ec70(*0x80000002, P#)` |
| `0x4004af20` | none | NOTE SETUP commit-all; calls `0x4009a3e0` only when CHAN changed |
| `0x4003fd34` | slot 0..3, cc 0..127 | CC1..CC4 number to `+0x14 + slot`; stage `0x460d5ce0`; redraw `0x4003f9ac` |
| `0x4003fe14` | none | CTRL1 commit-all |
| `0x4003f80c` | slot 4..9, cc 0..127 | CC5..CC10 number to `+0x18 + (slot - 4)`; stage `0x460d5d0c`; redraw `0x4003f490` |
| `0x4003f71c` | `0x38 + slot`, phase | CTRL2, one slot |
| `0x4003f8e8` | none | CTRL2 commit-all |

The two single-number writers range-check their arguments (slot 0..3 or
4..9, cc <= 127) and return without a store otherwise. The stores of
`0x4003fd34` were checked offset by offset: Part byte `+0x14 + slot`, CS1
byte `+0x14 + slot`, live byte `0x46c76df4 + t*0x44 + slot`.

MIDI LEARN (`0x40060f84`) calls `0x4003fd34` and `0x4003f80c`; its index is
`0x46c7d23c` (0-3 CTRL1, 4-9 CTRL2). The per-slot callbacks are in the
windows' record tables (CTRL2: `0x400bcb64..`). Which panel event fires
phase 0 is not traced 🟡.

Setup windows (open / close / draw; close does not commit):

| window | open | close | draw |
|---|---|---|---|
| NOTE | `0x400597b4` | `0x40056808` | `0x40036548` |
| CTRL1 | `0x40059620` | `0x400567e0` | `0x4003f9ac` |
| CTRL2 | `0x4005948c` | `0x400567b8` | `0x4003f490` |
| ARP | `0x40079c28` | `0x40079abc` | `0x40079d48` |

## 4. Outgoing MIDI 📖

`0x4009ec70(bank, p)` walks the eight MIDI tracks of that bank and Part; the
arguments are read at `sp+48` (bank) and `sp+52` (Part). For each track with
CHAN != 0:

- Bank select: status `0xb0 | ((CHAN + 15) & 15)`. CC0 carries `+0x01` and
  CC32 carries `+0x04`. Each counts when its value is < 128 and differs
  from its cache; the routine sends CC0 alone, CC32 alone, or both as one
  6-byte message. The caches are `0x46c76100 + ch*128` (bank) and the byte
  at displacement `0x20` in the same row (SBNK; the displacement is decoded
  from the extension word, objdump prints it as `20`).
- Program change: status `0xc0 | ch`, data `+0x02`, sent when `+0x02` < 128
  and (the value differs from `0x46c7a9b6[ch]` or a bank message was just
  sent for this track). The routine also keeps two 16-bit "done" masks
  (`0x46c7aa22`, `0x46c76900`) so that two tracks on one channel send once.
- The send primitive is `0x40010bc8(len, buffer)`, with buffers at
  `0x400d8097..0x400d809e`.

`0x4009a3e0` writes `0xff` to byte 0 of each 128-byte row at `0x46c76100`
(16 channels) and to all 16 bytes of `0x46c7a9b6`, so the next
`0x4009ec70` resends. It leaves the displacement-`0x20` bytes untouched 🟡
(read as the SBNK cache; not checked against a run).

A CC-number change (`0x4003fd34`, `0x4003f80c`) sends no MIDI.

`0x4009eec8(t, flat, value, force)` sends one page-1 value: 18 PB, 19 channel
pressure, 20-29 CC, with the CC number from the live setup byte
`0x46c76df4 + t*0x44 + (flat - 20)`. It reads bank and Part from
`0x80000002` and `0x80000003`.

The page-1 writer `0x40054cd8` takes a MIDI track as `track >= 8` (arm at
`0x40054ea6`). It writes the Part page-1 array (`B + 0x8f162`) and the CS1
mirror; it writes the live byte only when the track's playing bank and Part
(`0x8000666e[t]`, `0x80006676[t]`) are the current ones; then it calls
`0x4009eec8`.

Incoming CC routing reads CHAN from the Part on every CC (`0x40001882`).

## 5. Applying a template to a track (recipe) 🟡

For a module that writes a template without UI globals, built from the
writers' stores above (not run):

1. Per setup byte: write the Part byte, the CS1 mirror and the live byte
   `+0x20 + off` of `0x46c76dc0 + t*0x44`.
2. Set the dirty bits (`B + 0x95048`, `0x100b145e`, `B + 0x9b332`,
   `0x100f8598`).
3. When CHAN changed, call `0x4009a3e0`.
4. Call `0x4009ec70(*0x80000002, p)` to send bank and program.
5. Write CC values through `0x40054cd8(8 + t, 18..29, v)`.

Calling `0x4003fd34` or `0x4003f80c` directly needs `T` and `P#` set to the
target track and Part, because they read both globals.

## 6. CTRL page knob labels 📖

Page 1 draws the descriptor's fixed 6-byte names (CTL1, entry `0x400d42bc`:
PB, AT, CC1..CC4; CTL2, entry `0x400d444e`: CC5..CC10). The drawer
`FUN_4004d948(-1)` takes its MIDI arm when `0x80000012 != 0`
(`0x4004e1da..0x4004e4c2`). There `P = 0x40031ee0(-1, -1)` and the label
pointer at `fp@(-56)` is `P + 0x16`, advancing 6 per slot.

The draw call (`0x4004e474..0x4004e49c`) is
`0x40013904(0x400ba876, 0x400bf10a, x, y, 1, 0, "XXXX", label)`. The label is
passed as the format string, so a `%` in a name would be expanded.

Injection point: `0x4004e474`, the 4-byte `movel %fp@(-56),%sp@-`. A detour
there can push a per-(Part, t, slot) string when `P` is `0x400d42f4` or
`0x400d4486` 🟡. Labels longer than 4 characters on page 1 are not measured.

The value text comes from formatter array A (CTL1 `0x4003c6a0..0x4003c45c`,
CTL2 `0x4003c3e4..0x4003c194`): `%d` or OFF according to the enable bits. The
audio-track arm draws its labels at `0x4004e85a`.

SETUP pages: the label column is the descriptor's page-2 name (CC1..CC10).
The value column is the CC name from the 128-pointer table `0x400be882[cc]`,
printed `%.8s` (MODWHEEL, "CC #3", ...); lookup sites `0x4003f60c` (CTRL2
draw `0x4003f490`) and `0x4003fb32` (CTRL1 draw).

## 7. To find out

- Which panel event fires phase 0 of the setup callbacks.
- The ARP setup byte map beyond the slot-order reading.
- How page 1 draws a label longer than 4 characters.
- The entry of the knob-press code that toggles the enable bitmaps.
- A port run with `--midi-out` that shows `0x4009ec70` sending program and
  bank during a template apply.
- Whether `0x4009a3e0` leaves the SBNK cache stale (section 4).
