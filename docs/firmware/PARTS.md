# Parts: storage, the routines that move them, pattern changes

OS 1.40C, ColdFire side. Where a Part lives, which stock routines copy,
save, reload and apply it, and what the sequencer does with a pattern's
Part when the pattern changes. Measured under the ColdFire port on the
stock image with OCTABAM89_setgate (bank 3 saved) on 5–6 Oct 2026 unless
marked; ✅ measured or read from the code. Base `0x40000400`. The page
arrays inside a Part are `PARAM_PAGES.md` section 5, the step locks
`STEP_LOCKS.md`, the files `STORAGE.md` and `STEP_LOCKS.md` section 5.

## 1. Where a Part lives

`B` = a bank's RAM, `0x400e21e0 + bank·0x9b340`; `p` = the Part, 0..3;
`0x18b2` (6,322) bytes a Part.

| what | address | |
|---|---|---|
| working Part | `B + 0x8ed80 + p·0x18b2` | ✅ |
| saved Part | `B + 0x9504a + p·0x18b2` | ✅ |
| unsaved bits (bit p = working differs from saved, as stock tracks it) | byte `B + 0x95048` | ✅ |
| has a saved copy | bytes `B + 0x9b312 + p` | ✅ |
| name, six characters and a NUL | `B + 0x9b316 + 7·p` | ✅ |
| bank written by the next bank write | long `B + 0x9b332` | ✅ |
| a pattern's Part | byte `B + n·0x8ed8 + 0x8e57` | ✅ |
| the current bank's copies in CS1: patterns, working Parts, saved Parts, unsaved bits, has-saved bytes, names, edited flag | `0x1001614e`, `0x100a4ece`, `0x100ab196`, `0x100b145e`, `0x100b145f`, `0x100b1463`, `0x100f8598` | ✅ (`0x4000faf0` copies each from `B`) |

✅ The unsaved bit is not "working ≠ saved": OCTABAM89_setgate's bank 3
loads with `0x95048 = 0x0f` while Part 3's working copy equals its saved
copy byte for byte, and Parts 1, 2 and 4 differ from theirs by 1, 11 and
3 bytes.

### 1a. The sample slots a Part names ✅ (13 Oct 2026)

A Part names the sample slots its machines play: five bytes a track at
`Part + 0x2ca + 5t`, between the SRC page-2 array (`+0x1da..+0x2ca`) and
the page-2 arrays (`+0x2f2`). Index 0 is the Static slot, 1 the Flex slot,
4 the Pickup slot (2 and 3 unused); the byte is the slot number less one, and
`0x80..0x87` is recorder buffer 1-8. Read on the running port on
OCTABAM89_setgate (T3 STATIC `0x15` = slot 22, T7 FLEX `0x86` = recorder
buffer 7, its Pickup byte `0x86` too). In a bank file the same bytes are at
`0x2d3` in the Part record (`tools/hw/ot_project.py` `SLOT_OFF`): the file's
Part record starts 9 bytes before the RAM Part's first byte (the machine
bytes: file `0x2b`, RAM `0x22`). The slot's file, trim and attributes are the
project's (`project.work` `[SAMPLE]` blocks, manual 4.3 and 13.2.4), so these
bytes mean the same sample only within one project's slot lists.

## 2. The routines

| routine | does | |
|---|---|---|
| `0x40029a4c(src, p)` | Part paste: `src` → working Part of the current bank and its CS1 copy, sets the unsaved bit (RAM and CS1) and the edited flags; when `p` is the current Part, tail-jumps to `0x40009094(current bank, p)` | ✅ |
| `0x4004a908(p)` | Part Save: working → saved (and CS1), clears the unsaved bit, sets has-saved; re-applies when `p` is current | ✅ |
| `0x4004a9d0(p)` | Part Clear: `0x40005638` initialises working and saved, writes the name `PART<n>` (format `0x400b4200`), clears the bits, ends in Part Save (`bra 0x4004a908`) | ✅ |
| `0x4004aab4(p)` | Part Reload: returns 0 without a saved copy; else copies the eight machine bytes of the working Part (`+0x22`) to the stack, saved → working (and CS1), clears the unsaved bit; for the current Part calls `0x40009848(bank, p)` and then `0x400972fc(p, track, old)` for each of the eight tracks, `old` the machine byte copied before (read from the code 13 Oct 2026; this is the only stock path that runs the machine transition, and KITS' LOAD KIT uses it) | ✅ |
| `0x4004a8a4(p)` | the current pattern's Part = `p` (RAM and CS1), edited flags, `0x40027e00`, `0x40009094(current bank, p)` | ✅ |
| `0x40009094(bank, p)` | apply a Part to the engine: writes `0x80001828/9`, copies the Part's pages into the engine, the LFO designer records (section 9) | ✅ |
| `0x40009e00(bank, p)` | the pattern-change apply: `0x80001828/9`, the scene bytes, the rest as `0x40009094` | ✅ |

Part names: `0x40029a4c` copies the 0x18b2-byte payload only; the name at
`B + 0x9b316` is written by Part Clear and by nothing in this table
(✅). `0x4000faf0` copies the four names (28 bytes) into CS1 with the
bank.

## 3. Pattern changes

Every pattern request goes through the schedule routine `0x400a0570(bank,
pattern, a, b, c)` (✅ callers: the request `0x400a1030`, the arranger's
row publish `0x4004a652`, the arranger playback `0x400a0eaa` and the
repeat `0x400a101e`, the last two from the sequencer tick). It:

- returns at once when `B + 0x9b336` (a per-bank long) is non-zero;
- while the sequencer queues (`0x800065b8 == 1`): stores the queued bank
  and pattern (`0x800065bf`, `0x800065c0`) and posts an event; the
  switch reads the pattern's Part byte later (below);
- otherwise applies now: `0x40009e00(bank, Part byte)`, then the current
  and previous bank/pattern bytes `0x800065bd..0x800065c2`.

The switch (tick, `0x400a4430..0x400a4856`) makes the queued pattern
current, latches the bank into `0x46c7ff40` and **the pattern's Part
byte into `0x46c7ff62` at the switch**; the frame ISR then calls
`0x40009e00(latched bank, latched Part)` at `0x4000b1d8` and resets the
eight track bytes (`0x8000182a + t` bank, `0x80001832 + t` Part) to
`0xff`, which it rewrites per track at `0x4000bf62`/`0x4000bf6a` as each
track plays. A Part byte rewritten between the request and the switch is
the one that plays.

Chains: the chain append `0x4009c634(pattern)` (from the pattern trig
press `0x40056b9a` and the bank key release `0x4007b3ae`) adds to a list
of up to 16 longs at `0x80006552` (count `0x8000654e`, index `0x8000654a`,
flag `0x80006546`), patterns of the queued bank. The switch takes the next
entry into `0x800065c0` itself (`0x400a4500..0x400a4542`) and wraps; the
schedule routine is not called for a chain's later entries.

✅ Measured, stock image (`--watch-pc`, `--watch-mem`):

| form | the request | the switch |
|---|---|---|
| project load | `0x400a1030(bank, pattern)` from `0x400907da` inside the masked bank load; applied at once (`0x40009e00`), then `0x40009094` from `0x400907ea` | — |
| PTN + TRIG, playing | `0x400a1030` from `0x40056b6e` (sys task); queued at `0x400a06d6` | `0x400a4568`, Part byte latched at `0x400a468c`, `0x40009e00` at `0x4000b1d8` in the frame ISR, 13.5 s later on this pattern |
| PTN + TRIG, stopped | the same, applied at once | — |
| PTN + four trigs, 190 ms apart | four requests, each replacing the queued pattern (`0x80006546` cleared each time at `0x4009a404`); no chain was built this way | one switch, to the last |
| STOP with a pattern queued | `0x400a1030` from `0x400a1272`, applied at once | — |
| program change (`c0 21`, channel 1 = the project's) | `0x400a1030` from `0x4001fc9c` | the port's run applied it at once |
| BANK + TRIG, then PTN + TRIG | one request for the second, same bank (the bank key was released first) | — |

✅ Not driven here: the arranger (row publish and playback, tick
context), DIRECT JUMP (`modules/direct-jump`, a hook at `0x400a06d6`
inside the queued path).

## 4. How many Parts the engine names at once

✅ After every switch above the eight track bytes named one (bank, Part)
or `0xff` (a track that had not played yet), e.g. `02 02 02 ff 02 ff ff
ff` / `01 01 01 ff 01 ff ff ff`. ✅ The frame ISR resets all eight at
the switch and writes them as tracks play; no traced form left two Parts
named at once. PER TRACK scale (tracks of different lengths) and
"plays free" tracks were not measured.

## 5. Cost of moving a Part

✅ `0x40029a4c` (two 6,322-byte copies and the bits, before the engine
apply): 4,826 instructions. A KITS stage that copies one Kit into a slot
(saved and working copies, their CS1 copies, the slot tests): 133,563
instructions in its first build, most of them four whole-Part
compares; at the CPI 4.4 measured for voice code on the unit (Bryan T,
4 Oct 2026) about 2.2 ms of task time. The compare now runs only on
slots no track names, by long words.

## 6. The CC handler Octakit wraps

✅ Octakit's handler on the MIDI CC dispatch entry (`0x400d64a0`,
`midi_control_parameter.S`) routes CC 7, 46 and 47 (Part `+0x12`,
`+0x12`, `+0x13`), 55 and 56 (scene A `+0x10`, scene B `+0x11`), 57 (a
flag) and 58 (`+0x60d`, 12 bytes) through her workspace (capture,
mark dirty, commit). Stock writes the same Part bytes itself; KITS adds
nothing there.

## 7. The panel routes to the Part menus

✅ `--live-script`, MKII (`--mkii`) and MKI:

| keys | reaches |
|---|---|
| MKII PART (`0x1d`) | `0x4002e7b8` (the keymap's `0x4002e7c8` is `bra`), the PART window `0x4002e710` |
| MKII FUNC + PART | `0x4002dc9c`, the Part edit menu (`0x4006d94c`, four rows) |
| MKI FUNC + MIDI (`0x35`) | `0x4002e7b8` |
| MKI FUNC + BANK (`0x2f`) | `0x40058a64`, which opens the Part edit menu only while the PART window is open (`0x4002dc3c`); otherwise PATTERN SETTINGS (`0x40083440`) or one of two targets chosen by `0x460d1aec` / `0x460d1736`. RECORDING SETUP has its own key map (`0x400b9e36`) and does not reach it |
| MKII FUNC + BANK (`0x2f`) | FUNC-held keys table (FUNC.sub → map+4 → `0x400bf628`, or BRAIN's `brain_func_keys` clone): press `0x4007c0d0` opens **TRACK TRIG EDIT**. Not the MKI site above. |
| FUNC + CUE, both | `0x4004aab4` from `0x4005e05a` (return `0x4005e060`) |
| FUNC + YES | `0x4005e3d8` (press, then release), not an open list's YES |

The stock list menu `0x4006d94c(count, cursor, &cursor, labels,
callbacks)`: `labels` and `callbacks` are tables of pointers, one per
row; YES (`0x4006d8f4`) stores the cursor, closes the list
(`0x4006d754`) and passes `callbacks[cursor]` to `0x40020c28`, which
calls it with no argument. ✅ 257 rows draw and scroll.

## 8. The file seams

The masked bank load `0x400905d4(?, mask, …)` is how every project load
reads its banks (✅): LOAD PROJECT calls the empty-project init
`0x400909d8` (from `0x4008534c`) and then `0x400905d4` with mask `0xffff`
(from `0x400853d8`); a second engine command loads every bank but the
current one (`0xfffb` from `0x40084d60`, the power-up's path too). The
all-banks load `0x40090504` (from `0x400852c8`) did not run in a LOAD
PROJECT under the port. PLOCKS P2 hooks the call sites of these and the
copies of section 5 of `STEP_LOCKS.md`; KITS hooks the routines' own
entries (`0x40090504`, `0x400905d4`, `0x400909d8`, `0x400917c8`,
`0x4008ee74`, `0x4008f180`), so the two compose with no shared site.

## 9. The Part window bytes MIDI SCENES and SCENES P2 claim

✅ Stock addresses the LFO designer records as `B + 0x90482 + p·0x18b2
+ 16·n` (audio, Part `+0x1702`) and `B + 0x90512 + …` (MIDI, `+0x1792`)
and reads `B + 0x905b2 + …`: the apply-part copy `0x400092e0..0x40009328`
(`n` = WAVE − 11), the designer editor and operations (`0x40038212`,
`0x40038308`, `0x400384de`, `0x40038eea`, …) and the LFO paste/undo
(`0x400278dc`, `0x40027a00`).

✅ The run `0x90492..0x905b2` (Part `+0x1712..+0x1832`) that MIDI SCENES
and SCENES P2 store in is LFO designer data (measured 10 Oct 2026, stock
image under the port, a copy of OCTABAM89_setgate with T2 LFO1 WAVE = 12
and the bytes `11..20` at Part `+0x1712` in every Part record: after the
load the engine's LFO shape table held `11..20` at `0x800013b8`, T2 LFO1's
slot of `0x80001388 + 16·(3t + lfo)`):

| Part offset | stock | written by |
|---|---|---|
| `+0x1712..+0x1782` | audio LFO designs, tracks 2–8 | MIDI SCENES' freeze twin, on Part Save when the sparse blob carries `MS` |
| `+0x1782..+0x1792` | 0 in every census file (below) | MIDI SCENES' freeze twin |
| `+0x1792..+0x17a2` | MIDI LFO design, track 1 | MIDI SCENES' freeze twin |
| `+0x17a2..+0x1812` | MIDI LFO designs, tracks 2–8 | MIDI SCENES' sparse blob (`MS`); SCENES P2's pool (`P2`, from the first page-2 scene lock) until 10 Oct 2026 |
| `+0x1812..+0x1832` | not located | the same |

Census of the Part tail across 1,536 bank files (12,288 Part records) on
this machine: `+0x1662..+0x1702` is `0xff` in all but a few bytes,
`+0x1782..+0x1792` is 0 in every record, `+0x1812..+0x1832` is one of
three patterns, `+0x1832..+0x18b2` is 0 in most records, and stock reads
`+0x1832`. The Part has no 144-byte run known free. A zero in a census is
not a measurement of use.

Not measured: the designer editor's writes landing on the module bytes
(✅ from the addresses above); on the unit.

Since 10 Oct 2026 SCENES P2 keeps its locks in bytes 30 and 31 of the
stock scene block (`modules/scenes-p2/README.md`); MIDI SCENES still
stores at `+0x1712..+0x1832`.

## 10. KITS

`modules/kits` stages each pattern's Kit through these slots: section 3's
schedule routine and chain append, section 1's copies, section 2's
Reload and Save. Its README says what it does and what was measured.
