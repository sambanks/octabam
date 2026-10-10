# MIDI scenes: what stock does for MIDI tracks, and what MIDISC2.1 changes

OS 1.40C, ColdFire side. Phase 0 of the MIDI SCENES rewrite. Base
`0x40000400`. ✅ measured under the port (`ot_emu`, OCTABAM89_setgate,
bank 3, Part 1, T1 a MIDI track on channel 11); 📖 read from disassembly
of the stock image or of bkkbrls-del's MIDISC2.1 image (stock +
`release21.json`). The oracle runs are `tools/verify/verify_scenes.py`.

Images: stock `out/raw/section_3_MAIN_OS.bin`; "his" = MIDISC2.1 as built
from upstream `52eaab0`. Behaviour numbers B1..B33 are the inventory's.

## 1. Oracle runs

Fixture (`verify_scenes.fixture`): every Part of every bank has MIDI track
1 on channel 11 (Part `+0x4e2` = 11, ch+1), CC enables `+0x3e2+30/31` =
`0x3c/0x3f`, scene A = 0, scene B = 8 (Part `+0x10/+0x11`). Script: NO,
MIDI (`0x35`), T1 (`0x10`), FX1/CTRL1 page (`0x25`), then the chords.
`--live-script` runs the sequencer's frame engine with the transport
stopped unless the script presses PLAY (`0x28`). Frames are 16 samples at
44.1 kHz since the script start; `ot_emu --live-script ... --midi-out F`
writes `F.frames` (`<frame> <hex bytes>` per drain) since this commit.

Knob D on CTRL1 = flat 21 = MSC index `0x015` (scene 0) / `0x815`
(scene 8). T1's setup CC slot 2 is CC 1 (setup `+0x14..` = `07 01 02 0a 47..`),
so the wire message is `ba 01 vv`.

| scenario | script | stock MIDI out | his MIDI out |
|---|---|---|---|
| b1 ✅ | A held + enc D +40; B held + enc D +100 | none | `ba 01 64` at frame 10143 (B held, XF at the B end: the B lock) |
| b7 ✅ | b1, pot 255 / 128 / 1 / 255 | `b0 30 00`, `b0 30 3f`, `b0 30 7f`, `b0 30 00` (CC 48 echo only) | the same CC 48 bytes in the same frames, each followed by `ba 01 28` (40), `ba 01 45` (69), `ba 01 64` (100), `ba 01 28` |
| b7play ✅ | b7 with PLAY first | CC 48 only | same CC 1 values, frames 14387 / 15765 / 17143 / 18522; no trigs in the pattern |
| b3 ✅ | b7, A held + push of encoder D (key `0x3b`), pot 1 / 255 | CC 48 only | after the push `ba 01 00` (A end now unlocked, Part value 0), then `ba 01 64` at XF 0 and `ba 01 00` at XF 127 |
| b29copy ✅ | b1, A held + REC (copy), B held + STOP (paste), pot 1 / 255 | CC 48 only | `ba 01 28` at XF 0 (B = copy of A's 40); nothing at XF 127 (unchanged) |
| b29clear ✅ | b1, A held + PLAY (clear), pot 1 / 255 | CC 48 only | `ba 01 00` at XF 127 (A has no lock), nothing at XF 0 |

CC 48 bytes and frames are identical between the images in every run.
B1/B3/B7/B29 behave as the inventory describes. Values: 69 at XF 64 =
`(40*64 + 100*63) / 127` truncated. A CC 1 value is sent only when it
differs from the last one sent on that channel (cache `0x46c76100`,
section 4).

State after b1 on his image ✅: `msc21_ram` (`0x40a955e0`) holds
`MSC[0x015] = 40`, `MSC[0x815] = 100`, all else `0xff`. Part 1's
`+0x3e2..+0x401` (the MIDI param bytes) equals stock's; stock's MIDI track
record at `0x46c76dc0 + 21` stays 0 and his is 100 (b1), 40 (b7 end), 0
(b3 end). The only Part-window difference to stock is the sparse blob at
`+0x17a2`: `4d 53 02 00 | 00 15 28 | 08 15 64` (magic `MS`, count 2, pad,
entries `u16 index, u8 value`) ✅ (B1, section 3.3 of the inventory).
Active-lock mask `0x8000664e..` is all zero in every run ✅ (no trig
carries a lock).

Not run: B2/B4/B5 (LCD/LED draw: the LCD is not decoded in `verify_scenes`),
B8..B9, B10 (panel write of an unlocked MIDI param), B12..B18 with trigs
playing, B19..B27, B31. To find out for each: a fixture with MIDI trigs
(`ot_project.py set_pattern_trig` does not write MIDI-track trigs), and
`--card-out` after Project Save.

## 2. The MIDI mode flag

`0x80000012` is a long, `MIDI_MODE` (`MIDI.md` section 1). Pressing MIDI
(`0x35`) gives `0x80000012 = 00 00 00 01` ✅ (`b1_mode.bin`).
`KEYMAP.md` names `0x80000015`: that is the long's low byte (big-endian).
Stock tests the long in the scene-hold dispatch `0x400534ce`,
`0x40052ece`, the encoder presses `0x40053a9e`, `0x40054392` (each
`tstl 0x80000012 / bne` jumping to the audio-only path) and the per-track
and per-page scene-base paths `0x400343bc` ... 📖 (disassembled).

## 3. Stock: MIDI tracks have no scene locks

📖 Stock's scene block is `Part + 0x8f3e2 + scene·0x100 + track·0x20`, 16
scenes × 8 tracks × 32 B, audio tracks only (`MIDI.md` Appendix C).
His R21 replaces four `addi.l #0x8f3e2` scene-base sites (`0x400343e8`,
`0x4003448e`, `0x40034764`, `0x40034950`).
Each hold/press site above bails on MIDI mode, so in MIDI mode stock
neither writes nor reads a scene lock. ✅ Stock's b1 run: the Part and the
track record are unchanged and no CC 1 is sent.

The morph is the frame builder `0x4000cc6c..0x4000cf3e` on the DSP-bound
copy; MIDI tracks do not pass through it. MIDI tracks get their values
from the track records (section 4).

## 4. MIDI track records and the CC send

### Track record `0x46c76dc0 + 0x44·t` (t = 0..7) ✅ layout from the dump

| offset | size | content |
|---|---|---|
| `+0x00..+0x1f` | 32 | the track's param block: flat 0..29, `+0x1e/+0x1f` the CC enable bytes (fixture `3c 3f`). A copy of Part `+0x3e2 + 32·t` made by the apply `0x40009094` (loop `0x400094fe`, 32 B) |
| `+0x20..+0x43` | 36 | the track setup, a copy of Part `+0x4e2 + 36·t` (loop `0x40009534`): `+0x20` channel+1 (0 = off), `+0x21` bank MSB, `+0x22` program, `+0x24` bank LSB (`0x80` = off in MSB/program/LSB), `+0x34..+0x3d` the ten CC numbers (T1: `07 01 02 0a 47 48 49 4a 4b 4c`) |

The record, not the Part, is what the sequencer plays and what his mix
writes (b1: record `+21` = 100, Part `+0x3e2+21` = 0).

`0x46c78960` ✅ (stock): written by `0x4009c110`, inside `0x4009b964`, as a
32-byte copy per track of the lane `0x46c7a6f0 + 32·t` (`lea 0x46c7a6f0`,
`0x4009c100`; track stride 32). 📖 It is the per-track param lane the LFO /
sequencer step code reads ("post-trig LFO input" in the inventory).

### CC send `0x4009eec8(track, flat, value, quiet)` 📖

Callers (stock): `0x40054f6e` (the page-1 knob path), `0x40055426` (panel
write), a table entry at `0x40043a9e`. His adds `0x400d2ad6` (its mix).
`quiet` ≠ 0 skips the transmit and only leaves the state. By flat:

| flat | message | cache |
|---|---|---|
| 18 | pitch bend `0xe0|ch`, 14-bit `value<<7` | `0x46c76990 + 2·index` |
| 19 | channel pressure `0xd0|ch` | `0x46c7a16c + index` |
| 20..29 | CC `0xb0|ch`, number = record `+0x34 + (flat-20)`, only when the enable bit is set (byte 30: bits flat-18 for flat 20..23; byte 31: bits flat-24) | `0x46c76100 + ch·128 + cc` |
| 0..17 | no transmit | |

A value equal to the cache is not sent. Messages go to `0x40010bc8(len,
buf)` (UART0 queue); `ch` = record `+0x20` − 1; a track whose channel is
0 is skipped. A `ba 01 vv` in section 1 is this path ✅.

### MIDI Part push `0x4009ec70(bank, part)` 📖 + ✅ call order

Per track with channel ≠ 0 sends bank select MSB (CC 0) / LSB (CC 32) and
program change from setup `+1`, `+4`, `+2` when they differ from the
cached `0x46c76100`/`+20` and `0x46c7a9b6 + ch` values; marks channels
done in `0x46c7aa22` / `0x46c76900`. Callers: `0x4000961e` (apply),
`0x40009dfa` (pattern-change apply tail), `0x4000a182`, `0x4004af0e`,
`0x4004b03a`, `0x4009eebc`, and `0x400a1752` (the sequencer, below).

## 5. The MIDI sequencer and the switch path

📖 `0x400a1e0c` is the sequencer tick (vector `0x60`, `KERNEL.md`);
`0x400a1608` is its per-step MIDI routine (called from `0x400a1ed6` and
`0x400a1f10`; argument = restart flag) and `0x4009f794` the MIDI note /
CC-loop routine called at its end (`0x400a1dfe`). Identities of his sites:

| site | what it is in stock |
|---|---|
| `0x400a169a` | `0x400a1608`, after a step-time word `d1 = step·2100 + 0x46107564`; the 36-entry compare loop of `0x46c76a26` stamps into flags `0x46c77b66` (hit 5,817 times per 1,600 frames ✅ in `--watch-pc`) |
| `0x400a19da` | inside the per-track loop: `moveml` of 32 B from `0x46c78960 + 32·(slot)` to the destination `sp@(136)` |
| `0x400a1d32` | after the 30-param loop of the track (`d5` = track): `0x400a1d06` loop compares each of 30 params with the trig's lock byte, copies, sets bit `d4<<d1` in the mask long at `sp@(120)` (`orl d0,a3@` at `0x400a1d24`), and `moveb #-1` clears the lock |
| `0x400a1742` | `mvsb 0x46c7a934,d2` / `0x46c7a850,d3`, then `jsr 0x4009ec70(bank=0x46c7a850, part=0x46c7a934)`: the MIDI Part push, guarded by `0x46c76a22 != 0` and flag `0x46c77b87` |
| `0x400a3c2a`, `0x400a44f4`, `0x400a47f0`, `0x400a4ba0` | inside `0x400a1e10` (the tick, one routine to `0x400a4070`+): timing store `0x46c76aae`; the queued-pattern switch (`PARTS.md` section 3); `0x400a47f0` writes `0x46c7a934` (the Part the MIDI push uses); `0x400a4ba0` the per-tick playback step (hit 1,183 times in 1,600 frames ✅) |
| `0x4009faaa` / `0x4009fe4e` | in `0x4009f794`: the note-on build (`0x90|ch` at `0x4009fac2`) and the start of the per-track CC loop over `0x46c76dc0` |

Which path sets the Part step 1 plays, ✅ on both images, PTN + TRIG while
playing (`t2` runs, same instruction counts to within a few hundred):

| order | what | instruction count (stock) |
|---|---|---|
| 1 | switch tick `0x400a44f4`: queued pattern becomes current, Part byte latched | 2,250.9 M |
| 2 | `0x400a1742`: MIDI Part push with `0x46c7a934` / `0x46c7a850` | 2,267.9 M |
| 3 | frame ISR `0x4000b1d8` → `0x40009e00(bank, Part)`: the audio apply | 2,269.3 M |

So the MIDI side takes the new Part at the tick and before the audio apply
(~17 M instructions earlier); `0x40009e00` and `0x40009094` both end by
calling `0x4009ec70`. His `0x400a44f4` cave moves PLAY_PART/PLAY_BANK at
the switch; ZIP's `kits_mswitch` (`0x400a1742`) and `kits_switch`
(`0x4000b1c4`) hook the two sides. Neither images' MIDI output changed at
that switch in this run (no trigs, no scene movement).

Active-lock mask `0x8000664e + 4·t` (u32 per track, bit i = param i of the
track is locked by the playing step): writers ✅ by `--watch-mem` on stock:
`0x400095d2` (zeroed per track in the apply `0x40009094`), `0x40055348`
(a sys-task clear), `0x400a1cac` (the tick clears it before the 30-param
loop); 📖 the only setter is `0x400a1d24`. Readers: `0x40009c92`
(`0x40009848`, the Reload apply) and the tick. His `0x400d6b14` reads it
(B13). Value 0 throughout section 1 ✅.

## 6. The MIDI page map and knob ranges ✅ (descriptors read from the image)

`FUN_40031da4(track, page_kind)` returns the descriptor by kind: NOTE
`0x400d3e3e`, LFO `0x400d4162`, ARP `0x400d3fd0`, CTRL1 `0x400d42f4`,
CTRL2 `0x400d4486` (kinds 0..4). `flat = page·6 + knob`.

| page | knobs (name:init:count) |
|---|---|
| NOTE (0) | NOTE:48:128, VEL:100:128, LEN:6:128, NOT2:64:128, NOT3:64:128, NOT4:64:128 |
| LFO (1) | SPD1..3:32:128, DEP1..3:0:128 |
| ARP (2) | TRAN:64:128, LEG:0:2, MODE:0:7, SPD:5:96, RNGE:0:8, NLEN:6:128 |
| CTRL1 (3) | PB:64:128, AT:0:128, CC1:127:128, CC2:0:128, CC3:0:128, CC4:64:128 |
| CTRL2 (4) | CC5..CC10:0:128 |

Minimum 0 everywhere. These counts match his
clamps: LEG 0-1, MODE 0-6, SPD 0-95, RNGE 0-7 (B1). Enable bitmaps
(`descriptor + 0x18e`): ARP `00111111`, CTRL1 `00111111`, rest
`11111111`.

## 7. Event handlers behind his B26..B28 sites

📖 The main task's event jump table `0x40061cfa` (type−1): `0x40062216` is
in the type `0x14` case (`0x400621a6`): store the Part byte to
`0x80000003` and `0x100b14cf`, call `0x400972fc(part, track, old)` per
track, then `0x400326a0`. `0x400622aa` is in type `0x15` (bank switch) and
`0x400622c6` in type `0x12` (after-load). The producers of these types were
not located. `0x40087eac` is in the project-file parser
(`0x400873d0..0x40087e6e`, `MIDI.md` section 1); the `[STATES] PART=` key is
the only Part key in the fixture's project.work (inferred, not traced).

## 8. Scene rows (B29)

✅ In the scene-held key map the tables at `0x400bae1c` and `0x400bb18a`
(two entries each, one per scene key) map: REC (`0x29`) → copy
`0x40062f60`, STOP (`0x27`) → paste `0x40062da0`, PLAY (`0x28`) → clear
`0x40062e84`. Each checks `arg == 1`, picks the held scene's index from
Part `+0x8ed90` (A) or `+0x8ed91` (B), and calls stock `0x400274cc`
(copy), `0x40027578` (paste, after an undo snapshot `0x400275a0`) or
`0x40038c30` (clear); his R21 hooks the three `jsr`s. Measured: b29copy
and b29clear above.

## 9. Which hook sites need a ROM-resident target

The boot detour `0x40000518` is reached at instruction 4.38 M
(`--watch-pc`, ✅). First arrivals of the sites that run in a plain load,
stock image: `0x40009094` 19.1 M, `0x40025aa2` 18.8 M, `0x4001fbd0` 42.1 M,
`0x400622c6` 45.8 M; `0x400622aa`, `0x40087d44`, `0x40087eac`,
`0x40062216` were not reached in a load (reached by UI/bank/project
actions, 📖). The RTOS handoff is at 10.17 M. Every one of his 52 hook
sites sits in the main/sys/engine tasks, the sequencer tick or the frame
ISR, all of which run after the boot detour; the sequencer tick and
frame ISR are armed by the transport start. No site was found that
executes before the DRAM loader has run. A site executed in interrupt
context needs its DRAM target mapped at that time: DRAM is mapped from
the boot detour onward. Result: no hook site needs a ROM-resident
target by execution order; the boot redirect itself stays in ROM.
To find out: that no other module's boot code needs the scene units
earlier (the cave order of the DRAM loader).

## 10. Gaps (inventory section 6)

Closed here:

| gap | status |
|---|---|
| track record layout `0x46c76dc0` / `0x46c78960` | section 4 (record ✅ dump; `0x46c78960` ✅ writer, reader 📖) |
| sequencer sites `0x400a169a`, `0x400a19da`, `0x400a1d32`, `0x400a3c2a` | section 5 📖 |
| MIDI Part push `0x4009ec70` | section 4 📖; call order ✅ |
| CC send `0x4009eec8` vs emitter `0x40033e3c` | section 4: `0x4009eec8` is the MIDI-track emitter (cache `0x46c76100`, queue `0x40010bc8`); `0x40033e3c` is the audio-track CC-out (`MIDI.md` Appendix D), a separate path ✅ (CC 48 echoes through the second, CC 1 through the first) |
| active-lock mask `0x8000664e` | section 5 ✅ writers, 📖 setter |
| page map, knob ranges | section 6 ✅ |
| which switch path sets the Part step 1 plays | section 5 ✅ |
| stock scene storage for MIDI tracks | section 3 ✅ none |
| flag `0x80000012` vs `0x80000015` | section 2 ✅ |
| his image under the port | boots, loads and runs the scripts above ✅ |

Remaining:

| gap | to find out |
|---|---|
| B2, B4, B5 draw paths; B8..B10, B12..B27, B31 | scripts with MIDI-track trigs (`set_pattern_trig` writes audio trigs only), LCD decode, `--card-out` after SAVE PROJECT |
| Part Save index range (`arg & 0xf`) and the CKPT tail writes `+0x1180..+0x1330` | watch `msc21_ram+0x1100` through a Part menu session |
| event producers for types `0x12`, `0x14`, `0x15`; the `0x40087eac` key | `--watch-pc` on each `jsr` from a PART change, a bank change and a project load |
| `0x4000b1c4` (frame ISR switch) vs `0x400a44f4` order | add `0x4000b1c4` to the watch list of the `t2` run |
| KITS reload order, staged slots | `verify_kits` with his image |
| whether a pattern switch with scene locks and playing trigs changes the MIDI stream between stock and his | needs MIDI trigs |

## 11. Phase 1: the rewrite against MIDISC2.1 (10 Oct 2026)

`modules/midi-scenes/scenes.s` (B1..B8, B11, B29, B30, RAM only) built as
`midi-scenes` and `ok-ms`, run through `verify_scenes.py` beside the
oracle image and stock under the port; every scenario of section 1 plus
`b2` (SCENE A held and left held). ✅ measured on `midi-scenes`, all
comparisons against the oracle pass:

| scenario | MIDI out (bytes, frames) | MSC | track records `0x46c76dc0` | lock mask `0x8000664e` | Part windows vs stock |
|---|---|---|---|---|---|
| b1, b2, b7, b7play, b3, b29copy, b29clear | identical, 0 frames apart | identical | identical | identical (zero) | identical |

- The clipboard (`msc21_ram+0x1000`) is untouched in every scenario but
  b29copy: the oracle's reads zeros, this module's `0xff`; b29copy's is
  identical after the copy.
- b2's end-of-scenario LCD plane (the panel link's UART stream) is
  identical to the oracle's, and differs from stock's (the readout shows
  the held scene's value 40 in both). With KITS in the image the status
  line reads `009 ONE` where the oracle's reads `Pt:1 ONE`; that is the
  only difference on `ok-ms`.
- LED rows and levels on the panel link are identical between stock, the
  oracle and the rewrite in all seven scenarios: the compare cannot see
  B4's LED half or B5.

📖 From the 2.1 image (disassembly), what the rewrite reproduces:

- B9: the release hook's replacement (`0x400d7b14`) executes stock's own
  sequence at `0x40054cb6..0x40054cd2` (`clr.l 0x460d1694`, `clr.l
  0x460d169c`, `pea -1`, `jsr 0x4004d948`, `jsr 0x400418e0`, `addq #8,sp`,
  `jmp 0x4007cf28`); no site is needed.
- The mix wrapper: `0x400d28c8` -> context check, setup refresh
  (`0x400d6600`), then the loop body `0x400d28ce`. Per track and flat: a
  side with no lock reads the trig snapshot (`msc21_ram+0x1a80`, `0xff`
  until a trig) and then the Part's `+0x3e2` value; both sides without a
  lock write the Part's value to the record and send nothing; otherwise
  `A + ((B-A)*w >> 7)`, `w = 127 - (xf & 127)`, weight 0 = A, 127 = B; the
  record byte is written first and `0x4009eec8(track, flat, value, 0)` is
  called when it changed.
- The mix clears bit `flat` of `0x800064d0 + 4t + 0x17e` for flats 18..29
  on every pass: that long is the lock mask of section 5 (`0x8000664e +
  4t`).
- `0x4009eec8` saves d2-d7/a2-a5 in its prologue.
- Its LFO-row write (`0x400d2b24`) is jumped over in 2.1 (`0x400d2b1e: jmp
  0x400d2b2e`); the mix writes only the track record.
- The mix follows PLAY_BANK/PLAY_PART (`0x400d6d60/64`): while the
  sequencer is not scheduling (`0x800065b8 != 1`) they are the current
  bank pointer and the displayed Part (`0x100b14cf`) at each call.
- The scene-held readout, hold and unlock use the displayed Part's scene
  assignment (bank `+0x8ed90 + part*0x18b2`, bytes A, B) and the displayed
  track (`0x100b14cc & 7`).
- The pad hook scans MSC[scene] in every mode, MIDI or not.
