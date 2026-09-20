# External findings

Reverse-engineering results from outside this project, with what we
re-verified, adopted, and retracted kept distinct. §1–§6, §8 and §10–§12
are Bryan T's (Discord); §7 scans two parallel projects; §9 is nordseele's
octalab. All were derived from the officially distributed OS 1.40C
(`section_3_MAIN_OS.bin` SHA-256 `164f3122…`, base `0x40000400`). The full
ingest record, including the frame-phase model, the notes exchanged and
Bryan's xtables note verbatim, is `EXTERNAL_INGEST.md` in git history
(`git show 3ceba41:docs/history/EXTERNAL_INGEST.md`).

Status key: ✅ re-verified here · 🟡 adopted on their evidence · ❌ retracts
something we had written.

## 1. The Echo Freeze Delay is on the ColdFire 🟡

Per-frame DMA descriptor arithmetic over per-track rings in SDRAM, EMAC
loops for gain and mix (`octatrack-delay-architecture.md`, 30 Aug 2026):

| | |
|---|---|
| frame routine | `0x400031a0` (body to ~`0x40003900`) |
| ring base | SDRAM `0x4F502C10` (cached alias `0x477...`, `CLAUDE.md`) |
| ring size | 1,411,200 bytes per track = 176,400 × 8 = 4 s × stereo × 4 bytes |
| 4-second cap | `if (samples > 176400) samples = 176400` |
| read head | `read_pos = write_pos − delay_samples × 8`, wrapping at the ring size |
| DMA | `0xfc045040/50/60/70`, count/control `0xfc04505e/7e` |
| tap processing | EMAC loop `0x40003664`; two cascaded first-order sections, coefficients per track via `0x80006180` |
| mix and feedback | EMAC loop `0x40003734`; four gains, each linearly ramped across the frame |

No fractional-delay interpolation: whole 8-byte frames, time changes as a
two-tap crossfade between this frame's and last frame's positions (TAPE off
snaps, TAPE on glides). No recursive feedback code: the ring's write stream
contains a scaled copy of its filtered read stream. Eight tracks sustain
4-second delays because each has its own ring in CPU SDRAM.

❌ Ours: "the ColdFire does no per-sample audio arithmetic" (verified only
for the audio ISR `0x4000aad0`). The staged delay-time word `0x80005fa0` is
written by the delay routine itself at `0x40003284..88` from the per-track
record `0x80001a00 + 96·track` (✅ 31 Aug 2026; units open). Open: the
gain-to-knob mapping in the EMAC block; whether tracks 5–8 share the
function.

## 2. The ESAI carries audio ✅ (❌ ours)

`DSP.md` had concluded from the self-looping ESAI vectors `0x30`–`0x3e`
that audio does not arrive over the ESAI. A DMA-serviced peripheral needs
no vectors. Both ESAIs are configured at boot from `P:0x30026`:

```
030026: movep #>$40,x:<<M_SAICR
03002c: movep #>$37d01,x:<<M_TCR    ; M_TE0, M_TMOD=1 (network), M_TSWS=$1f
030036: movep #>$ff,x:<<M_TSMA      ; 8 transmit slots
030045: movep a,x:<<M_TX0
```

and a second port (`M_*_1`) identically; `M_TDC=$7` = 8 slots. `CHIP.md`
had labelled that module "host-port loader + ESAI setup" throughout.

## 3. Timestretch is a ColdFire feature 🟡

The CPU renders the grains and crossfades and ships finished audio to the
DSP every frame; the DSP's playback engine (`P:0x3a1`) is a 2-tap linear
interpolator over a 128-word ring applying pitch only. Crossfade: a
512-entry Hann table at `0x80004000`, `T[i] = round(2³¹·sin²(π/2·(i+1)/513))`
(zero error, `T[i] + T[511−i] = 2³¹`), fixed 512-source-sample fade,
minimum grain body 2,048 samples. No pre-analysis: the `.ot` serializer
persists 64 slice records, trim points and a checksum; BEAT mode's
transients are slice markers. Segments are butt-spliced on the DSP.

Module labels adopted into `DSP.md`: `P:0x3a1` voice playback engine (was
"parameter unpacking"), `P:0x2bf` summing mixdown (was "resampler"),
`func_00055a` the 24-bit ↔ dual-16-bit host packer (was "gain routine").

## 4. Data-table atlas 🟡 → `TABLES.md`

Shape-only catalogue of every X/Y data module (Q23 decode), merged into
`TABLES.md`. Every substantive data module is byte-identical between
payloads at shifted addresses (§10). Correction: the curve at `X:0x01bd9`
is GN1/GN2, not FRQ1; FRQ reads `X:0x015c7` with a ×4 index. ✅ Evaluated
against our modules 31 Aug 2026 (`TABLES.md`, "Use to our modules"): the
32 × 128 bank is one-pole coefficient pairs; no stock curve fits `k²` or
`(1−k)³` better than 0.040 RMS; BodeShift's sine-table variant was built,
measured and reverted; BusDelay's smoothstep must not be tabled
(`s(g) + s(1−g) = 1` is load-bearing; best stock complementarity error
0.24).

## 5. Disassembler tooling ✅

`objdump -m m68k:5407` mangles EMAC regions; `m68k:547x` / `m68k:cfv4e`
(the same decoder) is required. radare2's m68k backend cannot decode
`mvs`/`mvz`/`mov3q`/EMAC and, assuming 2-byte opcodes, reads each
extension word as an instruction: 6,757 undecodable instructions below
`0x40098000`, 4,543 of them longer than two bytes (`mvz` 4,539, `mvs`
1,834, EMAC 791; EMAC clusters: `0x40001000` 48, `0x40003000` 62,
`0x40004000` 50, `0x40007000` 98, `0x4000c000–d000` 47). At `0x40003664`:

| | first four instructions |
|---|---|
| `m68k:547x` | `msacl %d0,%a1,%acc2` · `msacl %d0,%a2,%acc3` · `macl %d2,%a1,%a5@+,%a1,%acc0` · `msacl %d5,%a1,%a0@+,%a1,%acc0` |
| `m68k:5407` | `msacl %d0,%a1` · `.short 0xa4c0` · `btst %d4,%a0@` · `macl %d2,%a1,%a5@+,%a1` |
| radare2 | `invalid` · `btst.l d4,(a0)` · `invalid` · `btst.l d4,(a0)` |

`scripts/disasm.sh emac <addr> [bytes]` uses `m68k-elf-objdump -m
m68k:cfv4e`. All 90 ColdFire addresses our docs cite in
`0x40000400`–`0x4000dfff` were re-read with `cfv4e`; no conclusion changed
(the four r2-unreadable sites: `0x4000b786` `mov3ql #-1,%a1@+`, `0x4000c24a`
`mvsb %a3@(0,%d1:l),%d0`, `0x40003664`/`0x40003900` EMAC). The menu and
descriptor work was Ghidra; the MIDI work was objdump `cfv4e`.

## 6. Track recorders (received 2–6 Sep 2026)

### Control path ✅

| claim | read here |
|---|---|
| descriptor entry 8 `E = 0x400d3c74`, `INAB INCD RLEN TRIG SRC3 LOOP / FIN FOUT AB QREC QPL CD` | byte-identical |
| defaults `E+0x96` | `1 1 64 1 0 1 0 0 0 255 255 0` |
| min `E+0xa2` | `−1` for QREC/QPL only |
| count `E+0xd2` | `5 5 65 3 11 2 113 113 128 18 18 128` |
| formatter `E+0x11a` | `0x4003b18c` |
| QREC/QPL ladder `0x400d80e0` (`0xFFFFFFFF` sentinel before) | `1 2 3 4 6 8 12 16 24 32 48 64 96 128 192 256` |
| one-hot class table `0x400d8120` | `1 2 4 1024 8 2048 16 4096 32 8192 64 16384 128 32768 256 65536 512` |
| tempo chain `0x4000ca94..cabc`, publisher call `0x4000cac2` | `1814→181c`, `1818→1824`, `d1 = 0x80000000 ÷ [181c] → 1820`; `pea 0x60 / pea 0x80000c94 / dest 0x80000cf4 + page×96` |
| RLEN conversion `0x4006e3b2` | `mvsb 0x80000cf4(2,track)`, gate `≤ 63`, `(raw+1) × 63504000`, `remul` by `[0x80001814] << 2`, floor 64 |
| arm caller `0x40005ff0` | `[0x100b14cf] × 6322 + [0x46c82456] + track + 0x8eda2 == 4` gate; `a3 = 0x80000cf4 + 12·track + 96·page`; `L = table[a3@(7)]`; `addl d1,d1`; `macl d1, −[0x80001820]`; `(x+1)>>1` |
| step ladder `0x400ab63a` | `992250 × L`, 113 entries: `0, 1..32, 34..64 by 2, 68..128 by 4, 136..256 by 8, 272..512 by 16, 544..1024 by 32` |

Closed from our side: `Dr == Dq` in `4c40/1801` is `DIVS.L` (gas encodes
`divs.l %d2,%d1` as `4c42 1801`; objdump prints `remsl`), so
`[0x80001820] = −2³¹/tempo24`. `[0x80001814]` = BPM × 24 (clamp 720..7200),
so recorder lengths are 44.1 kHz samples, RLEN raw+1 is sequencer steps
(`661500 / BPM` samples per 16th), the 64 floor is four frames, and
`992250 = 22.5 × 44100` gives `table[L] / tempo24 = L/16` steps. The
`0x400ab63a` ladder is the FIN/FOUT display series (`0, 0.063, 0.125 … 64`);
`0x40005ff0` nets to `round(table[FOUT] / tempo24)`. `MACSR = 0x20`
(`0x4000cf60` `moveq #32 / movel %d0,%macsr`; `0x4000d3ae` `movel
#32,%macsr`): fractional, signed, no saturation, truncating. Why the pickup
arm reads the FOUT slot is open.

❌ Ours: `0x80000003` / `0x100b14cf` are the current PART, not pattern
(`0x40062120..48`: `mvzb 0x80000004` × `0x8ed8` + bank blob, byte
`+0x8e57`); `[0x80000004]` is the pattern. Pattern records are `0x8ed8`
bytes (16 fill `blob + 0 .. 0x8ed80`), parts `0x18b2` from `blob + 0x8ed80`.
`NOTES.md`'s `+0x8f385` "sequenced data" is the recorder TRIG byte. `DSP.md`
§6c's `0x400060c4` is the PICKUP arm length (FOUT ÷ tempo24), not a
tempo→frame site; `0x80001820` is negative.

🟡 Adopted: three storage tiers (bank `+0x8f382 + part×6322 + track×12`
via `[0x46c82456]`, SRAM `0x100a54d0 + …`, published `0x80000cf4 + track×12
+ page×96` refreshed per frame from `0x80000c94`); `FUN_40005178` is the
QREC scheduler (`0x800018be/de` staged, `0x46c7e9fa` immediate, comparator
`0x4000b308`, class mask `[0x46c7fe94]`); the engine queue `0x460d17ce` /
task loop `0x4008484e` / 46-entry jump table is `FUN_4008445c` (also RELOAD
BANK, types `0x14`, `6`); recorder buffers are object ids 128–135 in the
136-entry arena `0x100b14f0 + id×1096` (control records `0x46c922c4 +
id×44`), armed by opcode `0x25`, length floored at 64, LOOP at state
`+292`; the TRIG=ONE / SRC3=MAIN default fixup is not in the image.

### Pool, write path, loop point (Sessions 2–5) ✅ bytes, 🟡 reading

| claim | read here |
|---|---|
| pool cold init `0x40096f7a`: cursor `0x8000691c := 0`, count 14602 → `0x80006920`, block array `0x46c2e9c0`, index table `0x46c2e580` | byte-identical |
| block address `= blk×6144 + 0x40A955E0` (`lsll #13` − `lsll #11` at `0x400963b4`) | exact |
| recorder row `(track+2) × 14602` at `0x40095aa4` and `0x40006fc4` | exact |
| segment emission `0x40007298` | exact |
| lazy allocation `0x40007196–e2` (`tstb 0x80000052` = `DYNAMIC_RECORDERS`) | exact |
| pack loop `0x40007854`: 6 B per 24-bit stereo frame | exact |
| position advance `0x400072ba–be`; loop point `clrl %fp@(24)` at `0x4000703c`; ping-pong flip `0x40007032–36`; wrap test `0x40007004` | exact |
| 16-sample limit extension `0x40006e2a–4c` | exact; runs at arm time (inside the arm-calling converter, before `jsr arm` at `0x40006edc`), not per wrap |
| converter that feeds `arm()`, `0x40006dfc–10`: `#31752000 / mulsl / macl / movclrl / addql #1 / asrl #1` | exact |
| one `andil #-16` in the image, `0x40003646` | exact |
| settings keys `RECORD_24BIT`, `DYNAMIC_RECORDERS`, `RESERVED_RECORDER_COUNT/LENGTH`; metadata `BPMx24`, `LOOP_BARSx100`, `TSMODE`, `LOOPMODE` | `0x400b7d49–0x400b7d80`, `0x400b79fc–0x400b7a26` |
| `0x40A955E0` literal | 23 sites |
| per-frame dispatcher `0x4000d2a0–86`: 8 × { `0x400068e4(track, page e4, 0, nibble)`; if `word & 0xd0`: `0x40005ff0(track, word)`; `0x400068e4(track, page e0, nibble, 16)` } | exact |

Recorder buffers are chains of 6144-byte blocks from one pool of 14,602
at `0x40A955E0` (85.56 MiB, the Flex RAM figure), rows at `0x46c2e9c0`
(0–1 the free/sample map, 2–9 recorder tracks). The write path is a
read-modify-write in `0x400068e4` (unpack `0x400072f2`, EMAC mix of four
sources `0x40007680` → `0x800062cc`, pack `0x40007826`); the loop point is a
hard cut inside the frame (up to four segments per 16-sample call). Length
arithmetic, final form:

```
tempo24 = 24·bpm + (23·tenths + 4)/9                       0x4009c7c4 (tenths 0..9 → 0 3 5 8 10 13 15 18 20 23)
Q       = trunc(2³¹ / tempo24)                              0x4000cab8
L       = ( ((steps × 31,752,000) × Q >> 31) + 1 ) >> 1     0x40006dfc..e10
```

An exact x.5 quotient rounds down (128/16 → 82,687). The truncating
`0x4006e3b2`'s consumer is open. The click itself: `RECORDER_CLICK.md`
(three stacked faults, fixed on hardware 12 Sep 2026); the frame-phase
model and its simulation are in `docs/history/EXTERNAL_INGEST.md`.

❌ Ours: buffers are not DMA siblings of the delay rings; the recorder
write path is traced (still project-dependent for the emulator).
❌ His: `0x40004860–0x40004bd0` on DMA channel 0 is the ColdFire→DSP frame
transfer (`DSP.md` §6c), not control-surface polling; his 198/16 row was a
transcription slip (53,454, rounded down).

## 7. Two parallel projects (4 Sep 2026)

`bryantysinger/octa-bt-pt` (Streamlit patcher of stock effect defaults;
`patch_tool/registry.json`, 61 parameters across 14 effects): ✅ 12 of 14
parameter counts agree with ours (FILTER 12, SPAT 10, DELAY 12, EQ 8, DJEQ
5, PHSR 7, FLNG 6, CHOR 8, COMB 5, SPRG 6, COMP 7, LOFI 6); PLATE and DARK
differ (we read 10 active slots, they list 9; open, likely the trailing
`MIXF`). Its `fx1_disallowed_effects` = DELAY, PLATE, SPRING, DARK,
"confirmed on real hardware". `emuyia/ems-octakit`: 256 kits replacing 64
parts; since ingested as the `octakit` submodule (`docs/remixes/`).

## 8. Bryan T's primer and spreadsheet (6 Sep 2026)

*Sound-on-Sound Looping with the Octatrack* (PDF) and
`octatrack_clickless_loops.xlsx`; not in this repo. The workbook's arithmetic
is the firmware's: `tempo24` as above; length = RLEN × 15,876,000 / tempo24
(= `0x4006e3b2`'s `(raw+1) × 63,504,000 / (tempo24 << 2)`); clean ⇔
`MOD(8·RLEN·15,876,000, 8·M·tempo24) = 0`; 5,279 clean pairs, 60 golden
tempos, 86 bar-length tempos all reproduce here. Primer claims checked: the
converter runs on the arm path (✅, `0x40006dfc` per frame; never at RLEN
MAX); displayed BPM ≠ actual (`.6` = 65 + 15/24) ✅; RLEN is measured
against the master clock, no per-track scale term ✅; at MAX the recording
ends at the next trig ✅; "the filter introduces clicks at the loop point"
open. Emulator (7 Sep 2026, `docs/history/RTOS_FORK.md` §10.16): 128/RLEN 4
writes 20,672 every pass with arm spacings 20,672 ×7 then 20,671; 128/16
writes 82,687 with trigs at ⌊event⌋ (offsets 15, 15, 14, 14).

## 9. nordseele's octalab (read 13 Sep 2026, commit `40ffa53`)

[`nordseele/octalab-notes`](https://github.com/nordseele/octalab-notes)
(MIT, findings only). octalab is a ColdFire DRAM module of this remixer,
running on an Octatrack MKI through our loader since 11 Sep 2026.

### 9.1 Hardware data on our pipeline

- ✅ (theirs) an image built at origin `9a49f21` (loader at `0x4010fdf0`,
  boot site `0x4000050c`, 10 MiB reserve at `0x40a955e0`, FX2 chooser
  rebuilt with 15 rows at `0x400d7bbc`) runs on a MKI: the first hardware
  run of the DRAM platform, on the model we cannot test.
- ❌ (ours) `FLASHPLAN.md` claim 2 ("MEMORY reports ~75 MB"): the MEMORY
  page still shows 85.5 MB total while the Flex list reads FREE MEM 71.4
  MB. The page count `0x390a` appears at 18 sites; which the page reads is
  unpinned (a fifth geometry site, open).
- Their standalone cave `0x400d64e0..0x400d7bf5` straddles the FX2
  chooser's NONE row at `0x400d6b00`; as a module they claim `LAB_MENU`,
  402 B at `0x400d64e0..0x400d6671`.

### 9.2 Corrections to ours

| ours | theirs | verdict |
|---|---|---|
| trig masks `0x40`/`0x48` "not masks, a run of `0xaa`" | `0x40` = swing trigs (default `0xaa…`), `0x48` = slide trigs; diffed bank files on the unit | ✅ adopted (`RTOS_FORK.md`, `tools/hw/ot_project.py`) |
| `MIDI.md` appendix A (was `midi_re_cc.md`): PLAYBACK page-1 `Part + 0x8edaa + track*30 + machine*7 + slot` | `machine*6` | ✅ re-verified from the writer `0x40054d7e..88` (`d1 = (m<<3) − m*2`) |
| `ot_project.py`: a STATIC PATH must be bare, `../AUDIO/…` loads empty | the unit writes nested STATIC paths itself; the "empty" slot is one with no `markers.work` record (§9.4) | 🟡 adopted; `tools/hw/` never writes `markers.work` |
| `MAINMENU.md`: list-descriptor `+0x08..+0x14` uninterpreted | cursor / absolute selection / visible-row count / count; boot init `0x4007ec60` from `0x40064c70..` | ✅ re-verified |
| `MAINMENU.md`: root window descriptors uninterpreted | the category icon, 19 × 9 | 🟡 adopted |
| `MAINMENU.md`: 16 × 0x14 menu-state table | "eleven pages, stride 0x1c" | ❌ theirs: dumped under both strides here, 0x14 holds (id 12's draw = `0x40068e00`) |

### 9.3 Ground they closed

FAT layer (`FS_LAYER.md`): 23-slot FS vtable `0x46c823fa..0x46c82452`,
three implementations installed by `0x40014524` / `0x40014636` /
`0x40014750`, variant B runs (load path's open `0x4001b724` in slot 0);
`0x46c8242a` `open(path, mode) → fd`, `0x46c823fa` existence probe,
`0x46c8241e` file size; `0x46c82456` is the bank pointer, not a slot.
`0x40090a14` = recursive directory walker `walk(path, *dirs, *files, mode,
progress)`, stacks `0x46070e44`/`0x46038e40`; 🟡 `mode == 0` calls
`0x46c8241a` per file and `0x46c8243a` per directory (unlink/rmdir; never
call mode 0 on a card you care about); it enumerates a whole directory
before the callback. Buffered primitives `0x40016864` open, `0x400166b8`
write, `0x4001677c` close.

Slot loading (`SLOT_LOADING.md`, MKI ✅): `0x40093980(slot, keep_trim)` has
one caller (case 1 of `0x4008445c`), followed by post-load (`0x40099148(0,
slot)` / `0x40099680`), `0x40093468(-1)` (re-arm eight tracks' voices) and
`0x4009da20(-1)` (refresh); loader alone gives a slot that shows name and
size, no BPM, no preview, no trig. Status record `0x46c90a78 + slot*0x2c`
(`+0x08` state 0/2/3, `+0x0c` code, `+0x24` handle; `-0x10` INVALID
FILENAME, `-0x1e` INVALID FILETYPE). CLEAR SLOT `0x40025288(kind, slot)`
= `0x40093814(slot)` then zero the 0x448 record (skipping the first leaks
the handle: MAX OPEN FILES). STATIC settings `0x100d5b30`, FLEX
`0x100b14f0`, stride `0x448`.

Step records (`TRIGS.md`) ✅: 64 × 32-byte records from `TRAC + 0x59`
(byte k = p-lock of scene parameter k: PLAYBACK 0..5, LFO 6..11, AMP
12..17, FX1 18..23, FX2 24..29; byte 31 sample lock; `0xff` none); full
address `bank + p*0x8ed8 + t*0x91a + 0x78 + (s−1)*0x20`. Trig word `TRAC +
0x89a + (s−1)*2` (bits 15-13 trig count − 1, 12-7 micro-timing ±23, 6-0
condition; labels `0x400b2588`); in the bank FILE one byte earlier
(`+0x899`). Sample-lock store `0x40040ee0(slot)` (steps from `0x460d174a`,
page base `0x460d174c`; writes bank byte + `0x1001614e` copy, dirty flags,
bitmaps `0x400339d8` → `0x46c7d48c[step]`). P-lock store
`0x4004f5f8(track, param, value)` returns unless a trig key is down
(`FUN_4003171c`); they replicate its body (dirty flags `bank+0x9b332` /
`0x100f8598` / `0x40027e00`, refresh `0x4009da20`).

A part lives three times (`FINDINGS.md`, MKI ✅): working `bank + 0x8ed80 +
part*0x18b2`, saved `bank + 0x9504a + …`, SRAM `0x100a4ece + part*0x18b2`
(the copy that survives a power cycle; patterns' at `0x1001614e`). A bank
write alone is lost at boot. `0x40029a4c(src, part)` writes both, sets
`bank + 0x95048` / `0x100b145e`, and re-applies with `0x40009094(bank,
part)` (also copies scenes A/B at `part + 0x10/0x11` into `0x80000ed4`).

Input layer (`INPUT.md`) ✅: keymaps `0x400bfbf6` (59 records, no `0x1c`;
🟡 MKI) and `0x400c01f4` (62, `0x1c` = MAIN MENU; 🟡 MKII); record `+0
code, +2 press, +6 release, +0xa, +0xe sub-map, +0x12, +0x16`. Maps are
layers: `0x40031494(map)` / `0x4003146c(map)` register / remove a 20-byte
map `{next, keys, encoders, 0, marker}`; rebuild (`FUN_4003125c`) into keys
`0x46c7d8de + code*0x18` and encoders `0x46c7dede + enc*0x14`; last
registered wins; −1 lets the layer below through; a null encoder handler
swallows the turn. Codes: UP `0x33`, DOWN `0x20`, LEFT `0x34`, RIGHT
`0x21`, ENTER `0x31`, EXIT `0x32`, encoder presses `0x38..0x3e`, encoders
A..F = 0..5, LEVEL = 6, trig keys `0x00..0x0f` → `0x40060ce0`, track keys
`0x10..0x17` → `0x40040250`, BANK `0x2f`, PATTERN `0x2e`, FUNCTION `0x2d`.
Double press: `0x400c0aac` last keycode, `0x460d5de0` ticks (display loop
`0x40052204`, reset `0x40033e20`), window 14 ticks. LEVEL press `0x3e`
special-cased at `0x4004ecfc`. Popups: yes/no `0x4006d57c(title, n,
lines[], 3, handler)`; scrolling list `0x4006d94c(count, sel, arg3,
labels[], handlers[])` / close `0x4006d754` / refresh `0x4006d784`; labels
pointer `0x460e5e2c`. Grid recording `0x460d1736 != 0`; audio editor
`0x4006de34(type, slot)` + `0x4006e160()`.

Fifth MAIN MENU category (`MENU.md`, MKI ✅ 7 Sep 2026): the `MAINMENU.md`
§5 move; a null-action row is a heading the cursor skips; a row inside a
pane cannot descend (`+0x10` read on the root only); the descriptor must
ship initialised.

Smaller: 🟡 pattern `+0x8e55` scale mode, `+0x8e53` length, `+0x8e54`
scale, `+0x8e50` master length (short, −1 INF); per track `TRAC + 0x50`
length, `+0x51` scale. ✅ descriptor defaults page-1 `desc + 0x5e`, page-2
`+0x64` (`FUN_400526e4`); part offsets from `part = bank + 0x8ed80 +
part*0x18b2`: `+0x22 + track` machine type, `+0x2a + track*30 + machine*6`
PLAYBACK p1, `+0x11a + track*24 + page*6` LFO/AMP/FX1/FX2 p1, `+0x2f2 +
track*30` LFO PMTR ×3 then WAVE ×3, `+0x662 + (scene*8 + track)*0x20` scene
locks; LFO destinations 0..29 use the scene-byte numbering. ✅ the zero runs
`0x401087e4..0x4010c315` and `0x4010cdd1..0x4010fdf0` are live at runtime
(code there raised `VEC:03`). ✅ `RANDOMIZE PAGE` = `0x4005b9c0`, via
`0x400bab22`.

### 9.4 The card from the host (`PROJECT_FILE.md`, MKI ✅)

`PATH=` bare, no quotes; `TRIM_BARSx100 = 100 × 2^round(log2(seconds ×
tempo24 / 24 / 240))`, capped 3200 (🟡 cap from one point), never cloned;
`markers.work`: 16-byte header `FORM 00000000 DPS1SAMP`, 264 records × 784 B
(136 flex incl. 8 recorders, then 128 static), 8-byte trailer ending in
`sum(body) & 0xffff`; STATIC slot n at `16 + (136 + n − 1) × 784`, frame
count at `+10` (4 bytes BE). A slot with no record falls back to 64 frames,
writes `TRIM_BARSx100=0` on the next save, shows the minimum tempo, and
neither trigs nor previews. The unit auto-saves the loaded project
continuously and its RTC runs behind wall clock (compare content, not
mtimes). `project.work` has no checksum; bank files do. Their `[META]`
signs `OS_VERSION=R0178     OLAB<n>`.

## 10. Absolute X addresses are payload-relative (Bryan T, 14 Sep 2026) ✅

The payloads are linked separately:

| block | payload A | payload B | words | content |
|---|---|---|---|---|
| curve bank | `X:0x438` | `X:0x42b` | 6,305 | identical |
| block below it | `X:0x421` | `X:0x421` | 23 on A, 10 on B | the 13-word cause |
| `X:0x4840` | same | same | 4,096 | identical |
| `X:0x6c00` | same | same | 3,730 | identical |
| Y table | `Y:0x290` | `Y:0x2a0` | 1,024 | identical |
| Y tables | `Y:0x690` / `0x710` / `0x715` | `Y:0x6a0` / `0x720` / `0x725` | 128 / 5 / 128 | not compared |

Stock code carries a different extension word per payload (EQUALIZER
`payload_A.asm` `0x000c07` = `0a73ce 0013c7`, `payload_B.asm` `0x0009c7` =
`0a73ce 0013ba`). A module is one source assembled into both, so a bare
literal into the curve bank is right on tracks 5–8 and 13 words off on
1–4; past the end of the relocated table it reads unuploaded memory (his
LOFI2: knobs 125/126 identically dull, 127 fine). `send_probe`'s
single-payload render dumps payload A. Our modules' `#>` immediates in
`0x438..0x1cd8` (156 sites) were read 14 Sep 2026: modulo masks, bus
scratch (`$901`…`$9da`, placed identically on both cores), a tap length
(1407), a decay coefficient (`$755`); none reads a stock table.
`FAILURE_MODES.md` carries the failure mode. His fix (an `xtables` field on
`DspSection`, immediates rewritten per payload with the delta read from
the image being built) is in his fork, not landed here. Also argued for:
a build flag on undeclared absolute X literals in the relocated range; a
four-character limit on `Formatter.STEPPED` labels (a ten-character label
threw `VEC:04` at `ADDR 4E007890`); a range check on `lua` displacements
(seven-bit signed, `dsp_asm` wraps `lua (r7+$40),r1` to `r7-$40`;
unverified here).

## 11. The parameter enable nibbles (Bryan T, 16 Sep 2026) ✅ (❌ ours)

`~/Downloads/enable-nibbles.md`; the note verbatim is
`docs/history/EXTERNAL_INGEST.md` §11. What it establishes is now
`PARAM_PAGES.md` §3b; this section is what was checked.

Re-read from our image 16 Sep 2026: all 31 descriptors' `P+0x18e`/`P+0x18a`
words and nibbles match his table (script in the ingest record); PICKUP
TSTR count 3 against 4 on STATIC/FLEX. The accessor `FUN_400a6994`, which
he hand-decoded, in objdump: `asrl` where he read `lsr.l`, and the branch
he elided (`bles 0x400a69ce`) is the path for shifts ≥ 32 — params 8–11 —
returning `hi >> (index−32)` in D1 and the sign of `hi` in D0. Both return
the same nibble for every word in the table. Call-site masks checked:
`0x40053810` (`moveq #9; andl`), `0x40052b82` (`#15` then `#9`),
`0x4003780e` (`#4`).

Effect rows (nibbles p0..p11, `-` = a `---` slot at 0):

| id | page | nibbles |
|---|---|---|
| `0x04` | FILTER | `131111111111` (WDTH `3`) |
| `0x05` | SPATIALIZER | `111111010111` |
| `0x08` | DELAY | `111111111111` |
| `0x0c` | EQUALIZER | `111111100100` |
| `0x0d` | DJ EQUALIZER | `101111000000` |
| `0x10` | PHASER | `111111010000` |
| `0x11` | FLANGER | `111111000000` |
| `0x12` | CHORUS | `111111100100` |
| `0x13` | COMB FILTER | `111101000000` |
| `0x14` | PLATE REV | `111111111001` |
| `0x15` | SPRING REV | `100111110000` |
| `0x16` | DARK REV | `113111111001` (SHVF `3`) |
| `0x18` | COMPRESSOR | `111111100000` |
| `0x19` | MULTIBCOMP | `101111000000` |
| `0x1c` | LO-FI | `101111001000` (NOIS `0`) |

❌ Retracted from `PARAM_PAGES.md` §3b: the derived "no knob" lists for
p0..p7 (read high nibble first), the MIXER "drawn anyway" counterexample
(MAIN and DIR are `1`; p6 MIX is the 0), AMP REL `8` (REL is `1`, XVOL is
`8`, ATCK is `1`, TRIG is `0`). `build_bus.py`, `verify_menu.py`,
`verify_hidden.py`, `rig.py` and `stock.py` shift `4·index` from the low
nibble; every built image's bitmaps were right.

Bit 2 taken one step past his note (🟡 objdump, not run): the drawer's site
at `0x4003780e` passes `8` for it as the flags word of the knob renderer
`0x400479b4(x, y, index, value, flags, formatter, window)`; the renderer
does `move.w flags,%ccr`, and `bpl` at `0x40047aac` picks the layout at
`0x40047b4a` (dial offset by the live record's `(0x46c7d244 + 20·index)+4`,
0..3) only when bit 3 is clear, flags bit 0 is clear and that field is
≤ 3. What differs on screen between the two layouts is open, as is bit 3's
path and bit 1's drawer. 🟡 A module would get a link element by setting
bit 1 on the right-hand slot (stock data + his panel reading; no module has
tried it); `build_bus.py`'s `penable` writes bit 0 only.

## 12. The track LFO engine (Bryan T, 21 Sep 2026) ✅ (❌ ours, ❌ his)

`~/Downloads/LFO.md`, a handoff read out of the binary in one session,
answering two questions of ours (a slew control; more than 19 waveforms).
What it establishes is `LFO.md`; this section is what was checked, all in
objdump against our image the same day, none of it run.

Re-read and matching: the engine at `0x4000cf84`–`0x4000d096` (inline in
the frame builder, `MACSR = 0x20`), 24 iterations, the 28-byte state
record with the phase accumulator at `+24` (modulus `0x791fd`), the value
read once at `0x4000d054`, MULT as `asll`, the destination rule (`PMTR <
12` → the page record, else the `a5` record), both 32-entry dispatch
tables with slots 19–31 as `0x400038bc` padding, the handler ABI (`a0`,
`+0`/`+4`), the 19-entry label array at `0x400be38e` packed against
`FREE`, the Part resolver's six bases, and that `0x400074a0`/`0x40007502`
are the recorder's FIN/FOUT fades over a `1/n` table (`a4@(6)`/`(7)`, the
recorder page's slots 6 and 7).

❌ Ours, retracted: `DSP.md`'s "LFO speed `0x400074a0`/`0x40007502`, MULT
table `0x400ab83a`" (they are the fade generator; the LFO rate is `SPD ×
tempo24 × 4` and MULT is a shift). `PARAM_PAGES.md` §5a's page-2 display
array at `+0x8f06c` with a machine column: his `part + 0x2f2` / `+ 0x30a`
(re-read at `0x4005762c`/`0x4005765a`) put PMTR/WAVE and MULT/TRIG at
`+0x8f072 + 30·t` and `+0x8f08a + 30·t`, which is his "open discrepancy"
resolved in his favour — the array starts six bytes later than we had it
and ends on the MIDI array. `MIDI.md` Appendix C's two 🟡 rows (scene bytes
6–11 and 12–17) are LFO p1 and AMP p1.

❌ His, corrected in `LFO.md`:
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

