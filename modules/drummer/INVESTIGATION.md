# DRUMMER — investigation

A machine that plays one FLEX track's sliced drum sample as a drummer: the
slices are sorted into zones (KICK, SNARE, HAT…) and roles (ACCENT, NORMAL,
SOFT); at each step the engine picks the slice, the level and the ornaments
from a style, DENSITY, COMPLEXITY and HUMAN; the track's own trigs are forced
accents and fills; BRK, locked on a scene, brings breaks in on the crossfader.

Markers: ✅ measured (on the unit, or under the port where it says so),
✅code read in the stock image this session and not run, 🟡 port or Unicorn
only, ❓ inferred. Image: the user's 1.40C, `out/raw/section_3_MAIN_OS.bin`
at VMA `0x40000400`.

## Phase 1 (5 Nov 2026): design and the addresses it rests on

### Design decisions (the user, 5 Nov 2026)

- DRUMMER is a **machine row** (as ANALOG BD, OCTA-303, CX OSC): a FLEX track
  signed in the Part, joined to HOOKS `machine_rows`. Not the brief's
  "option 1" that writes trigs into the grid.
- Its PLAYBACK page holds its parameters (STYLE, DENS, CPLX, HUMAN, BRK,
  SEED, …): lockable, under LFOs and scenes. BRK on a scene = breaks on the
  crossfader, deterministic for a SEED.
- v1 is mono and renders nothing: the engine chooses, the stock FLEX voice
  plays the slice. A track trig = a forced hit (accent / fill).
- PICKUP stays. The three-added-machines limit is handled in HOOKS if it
  ever blocks.
- A polyphonic renderer is a later v2, only on the user's go.

### Confirmed

| what | where | marker |
|---|---|---|
| A machine signs a FLEX track with 3 bytes in the unused NEIGHBOR PLAYBACK column, Part `+0x8edbc + 30t`, and in the battery copy | `cxosc/machine.s:1424`, `analog-bassdrum/control.c:17`, `octa303.s:1467` | 🟡 port gates of each |
| What a machine must give HOOKS `machine_rows`: TYPE NAME MAIN_COMMIT SRC_COMMIT SRC_COMMIT2 VALIDATE (+ RENDER/PAGE/RETRIG optional, `publish`/`title` as a non-head) | `hooks/manifest.py:193-316` | ✅ code; 🟡 `verify_hooks machines()` |
| PLAYBACK page bytes: Part `+0x8edaa + 30t + 6·machine` (FLEX `+0x8edb0`), SETUP `+0x1b0` from there | `cxosc/machine.s:83,336` | 🟡 |
| The page record the voice and the renderers read, **scenes and LFOs applied**: `0x80000510 + ping·0x180 + 48t` (ping `[0x800000e0]`, pointer `0x800062a8`), halfwords value<<8, rebuilt every frame | LFO.md:42-46, MIDI.md:587; CX reads it in `poly.s:580-640` | ✅ doc |
| The lane `0x80000810 + 72t` carries locks only (no scene, no LFO), applied at `0x4000c5ac` before the morph | STEP_LOCKS.md:47-52 | ✅ doc |
| **STRT in slice mode**: voice start `0x4000f450` reads STRT from the page record (`a3+2`, high byte) and SLIC (`a3+0x19`); with SLIC on and a count > 0, slice = `min(STRT >> 1, count − 1)`; STRT 0..127 → slices 0..63 | `0x4000f63e..f65a` | ✅code |
| Slice table: FLEX slot record `0x100b14f0 + 0x448·slot`, trim +300/+304, **64 slices × 12 B from +312** (start, end, loop), count long at +1092 | `0x4000f696..f6a8` (`(n+1)·12 + 300`); SAMPLE_SAVE.md:340-357 | ✅code |
| End slice = `min(slice + LEN, count − 1)` when voice +22 is 0 | `0x4000f6b2..f6da` | ✅code; meaning of voice +22 ❓ |
| Voice record `0x800049d8 + 0xa8·t`: +32 slice, +33 STRT, +40 start, +44 end | `0x4000f678..f684`, `f790..f7a4` | ✅code |
| Slot a track plays: Part `+0x2ca + 5t + machine`; at play time the lane byte 31 `0x8000082f + 72t` | kits/README.md:40, free-loop/README.md:349 | ✅code, 🟡 port |
| The sequencer decides a trig **one step ahead** in `0x4009d1e8` (called at `0x400a2d68..7e`): condition `0x400a5164`, micro-timing `0x46c7a830[t]` = sext6(word bits 12..7)·110250·scale + swing, kind `0x46c7a810[t]`, count `0x46c7a14c[t]`, locks staged at `0x46c7aa24 + 32t` | STEP_LOCKS.md section 3; one-step lead 5514 samples at 120 BPM (FREE LOOP) | ✅code, 🟡 port |
| Stock SLICES trig mode plays slice n now: lock byte 1 = 2n at `0x46c7dfda + 32t`, then fire `0x40005030(t, 0x1d, 1, −1)` (`0x4004f8dc`) | jump table `0x4005020a` mode 3 → `0x40050278` | ✅code; the same mechanism as chromatic note-on is ✅doc (MIDI.md:452-477) |
| STORE ids taken upstream 0..6; next free 7 (CHORDS PR #1043 asks 7) | `store/manifest.py:51` | ✅ |
| FLEX audio in RAM (for v2): pages of 6144 B from `0x40A955E0`, format bit 0 stereo / bit 1 16-bit in `0x46c922c4 + 44·slot` | memory/README.md:58-90, SAMPLE_SAVE.md:70-80 | ✅ port / doc |

### Corrections to the docs and the brief

- **STORAGE.md:90** gives the slice trim at `a4 + 300 + 20·(slice+1)`. The
  code multiplies by **12** (`lsl #4` − `lsl #2`); with 20, 65 entries would
  overflow the 0x448 record. To fix in STORAGE.md in this branch's PR.
- The brief's STRT→slice "scale 0..127 to 0..n−1" is wrong: it is
  `STRT >> 1`, slice index direct, clamped to the last slice.
- The brief's MORPH gesture: MORPH holds TRACK + UP **and** TRACK + DOWN.
  Moot now that the parameters live on the machine's page.

### What the design learns from this

1. **DRUMMER's page and the slice choice share bytes.** The voice reads STRT,
   LEN and SLIC from the very page record that will carry STYLE, DENS… So
   the slice cannot be chosen by a STRT lock (it would overwrite a DRUMMER
   parameter in the lane, and the lane is what the page shows). The machine
   must **wrap the FLEX start** (entry `0x400d6458` → `0x4000f450`) and give
   the stock start its own STRT = 2·slice, SLIC on, LEN 0, then restore.
   CX OSC replaces that entry (`cxosc/manifest.py:84`) and it is not in the
   HOOKS chain: a new HOOKS chain "start" is needed for DRUMMER and CX OSC
   to share an image.
2. **Live micro-timing is in reach.** The trig instant is computed one step
   ahead into `0x46c7a830[t]`. A detour right after the builder returns
   (`0x400a2d82`, 6 B, `mvzb 0x8000668d,%d0`; claimed by no module) can set
   the micro-timing, the trig kind and the staged VOL/RTRG/RTIM of the
   coming step, and **inject a trig on a step that has none**. That is
   where the engine runs, once per step per DRUMMER track.
3. **Scenes come for free on the page** (the page record is crossfaded). The
   engine reads its parameters there, never from the Part.
4. Prelisten from a KIT screen: the SLICES-mode recipe (lock byte 1 then
   `0x40005030`) through the start wrapper.

### Unknowns for phase 2

1. Run the slice start under the port: a sample with known slices, SLIC on,
   STRT = 2n → voice +40/+44 equal slice n's bounds.
2. The site `0x400a2d82`: inject a trig on an empty step, set
   `0x46c7a830[t]`, the kind and the staged VOL; hear it under the port
   (track output, or the recorder mix `0x800062cc`).
3. Wrapping `0x400d6458`: does the start read only the page record `a3`
   (so a private copy suffices), and what else reads STRT/LEN/SLIC after
   the start (the retrig path, `0x4000c634` START rewrite)?
4. RTRG / RTIM on FLEX: what they do to a voice (page-record words +8/+10).
5. The 4th machine row: HOOKS' limit (PB_TABLE slot 7 spare, FX1 table
   right after at `0x400d5f58`). Not needed for the user's rig (no row
   machine in live-djib); needed upstream with ANALOG BD + OCTA-303 + CX OSC.
6. Where the kit lives (zones/roles per slice, ~64 B a track): `drummer.work`
   through STORE (next id), or the Part's unused bytes (check TRAPS
   trap-unused-bytes first).

### Toolchain

Worktree `.claude/worktrees/drummer` (branch `drummer`, from origin/main
`54200264`): `make emu-cf` then `make check REMIX=cxosc` — 503 PASS, 0 FAIL,
3 SKIP (no project), 5 Nov 2026.

## Phase 2 (5 Nov 2026): the measurements under the port

Sample: the user's 2-bar loop at 93 BPM (stereo 16-bit, 227 613 frames), 16 slices
from its `.ot` (the unit's FILE > SAVE SAMPLE SETTINGS). It stays on the user's disk
and on scratch cards under `out/`; nothing of it is committed. The `.ot` holds the
same 12-byte slice entries as the settings record (0x3a + 12n), count at 0x33a.

Scripts (port, image = `out/mainos_bus.bin` of `cxosc`, or of `test/drummer-probe`):
`probe_slices.py` (an empty project by `ot_fresh`, the sample on FLEX slot 1, T1
FLEX SLIC on, 16 STRT locks), `probe_steps.py` (the step builder's words, voice
starts and VOL per step; `DR_SPARSE=1` = trigs on steps 1, 5, 9, 13 with micro-timing
0, +12, −12, +23), and the probe module `modules/drummer-probe` (never shipped).

### Results

| what | result | marker |
|---|---|---|
| STRT lock → slice | 16/16 steps start `min(STRT >> 1, count − 1)` with that slice's exact bounds at voice +40/+44: odd values, 40 and 127 clamped, a step without lock (Part STRT 0 → slice 0) | 🟡 port |
| Trig word in the bank FILE | `TRAC + 0x899 + 2·step` (0-based; the RAM word is `+0x89a`): a word written there reads back in RAM at `+0x89a + 2·step` | 🟡 port (the doc's ✅ stands) |
| Step builder per step | runs ~912 samples after the step counter `0x800064d0[t]` changes, for the step index the counter now holds. Sample trig: `0x46c7a810[t]` = 29, `0x46c7a14c[t]` = 1, `0x46c77bfa[t]` = 15 876 000 at 120 BPM, `0x46c7a830[t]` = µt·110 250·6. Trigless trig (mask +0x10): `a810` = 1. Empty step: nothing written. `a810` is cleared by its consumers (`0x400a3374`, `0x400a3bce`) | 🟡 port |
| Micro-timing | one unit = 1/24 of a step: +12 → +2 756 samples, −12 → −2 756, +23 → +5 283 at 120 BPM (5 512 per step), on top of a constant ~+900 from the counter change (the grid instant). Two trigs landing on the same instant start one voice | 🟡 port |
| **Adding a trig** to an empty step from the detour after the builder (`0x400a2d82`): `a810` = 29, `a14c` = 1, `a830`, `7bfa` = stock's last value | the voice starts, on the grid, or +2 756 with `a830` = +12's value | 🟡 port (probe) |
| **Moving a trig**: `a830` rewritten after the builder | +12 → 0 plays on the grid | 🟡 port (probe) |
| A STRT lock staged at `0x46c7aa24 + 32t` for an added trig | **ignored** (slice 0 played) | 🟡 port |
| A VOL byte written into the pending block `0x80001558 + 32t` | **never applied** (the apply at `0x4000c5ac` is skipped for these trigs: the `bmi` on the trig's flags at `0x4000c5a2`) | 🟡 port |
| **Forcing the slice** in a wrapper of the FLEX start (`0x400d6458` → `0x4000f450(track, slot)`): page record STRT byte = 2·slice, SLIC = 1, call stock, restore | slice 9 played on steps 9 and 13, their micro-timing kept | 🟡 port (probe) |
| **VOL per hit** in that wrapper, as stock applies a lock: lane `0x80000810 + 72t + 15`, DSP halfword `0x80000a50 + 64t + 30` = v<<8, bit 15 of `0x80001538 + 4t` | DSP VOL 80<<8 for the hit; at the next trig stock restores the Part's 64 (`0x4000c54c`) before the start, and the wrapper applies again | 🟡 port; heard: not yet |
| The page record `0x80000510 + ping·0x180 + 48t` | rewritten every frame (16 samples), alternating ping, by `0x4000ced4` | 🟡 port |
| The stock FLEX renderer `0x40004008` reads the page record every frame: PTCH `+0`, RTIM `+10`, byte `+27` (page 2) | | ✅code |

### What the design takes from it

1. **The engine** runs in the detour after the step builder (`0x400a2d82`, free):
   once per step per DRUMMER track it decides whether the step plays (adds or
   drops the trig through `0x46c7a810`), its micro-timing (`0x46c7a830`, in
   1/24 of a step, live: the humanisation's TIME aspect is not frozen), and
   queues the hit (slice, VOL, ornament) for the start.
2. **The hit** is applied in the FLEX start wrapper (`0x400d6458`): slice
   through the page record, VOL as a stock lock with its restore bit. No grid
   writes, nothing saved in the pattern: HUMAN varies at every pass.
3. **The parameters page**: DRUMMER's knobs share the page record with what the
   stock voice and renderer read (PTCH, STRT, LEN, RATE, RTRG, RTIM, SLIC...).
   Since the record is rebuilt every frame, DRUMMER copies its knob values (scenes
   and LFOs applied) out of it each frame, then writes the playback values it
   wants (PTCH 64, RATE forward, SLIC on, LEN 0, its STRT) for its tracks,
   between the build (`0x4000ced4`) and the packer `0x4000d3fc`. Site to choose in
   phase 4; the HOOKS RENDER chain (`0x400d6438`) is the other candidate.
4. **Not usable**: locks staged or pending for an added trig. Apply them in the
   start wrapper instead.

### Still open

- RTRG / RTIM on FLEX (flams, rolls): what the renderer does with page-record
  `+8`/`+10`, and whether setting them at the start is enough. Phase 4, by ear
  (`--dsp --audio-out`).
- The VOL halfword heard in the output (DSP side): `--dsp` run in phase 4.
- `0x400d6458`: CX OSC replaces the same entry (`cxosc/manifest.py:84`): a HOOKS
  "start" chain, or a declared conflict, before an image carries both.
- Everything above is port-only; nothing has run on the unit.

## Phase 3 (5 Nov 2026): the engine on the host

`drummer.h` / `drummer.c`: the engine, freestanding C (integers, no library
call, no allocation, no .bss), compiled for `-mcpu=5475` with the flags of
TRACK PATTERNS and FREE LOOP. One call per step per DRUMMER track,
`dr_step(kit, params, state, bar, step, forced, &hit)`; the hit is what phase 2
showed the firmware can do: play or not, slice, level, micro-timing in 1/24
step (−23..12), retrigs.

- Kit: zone + role per slice (64), combo masks, a priority order (default
  KICK SNARE CRASH HATO HATC RIDE TOM PERC GHOST).
- Styles BREAKBEAT, HIP-HOP, FUNK: original tables (core, CPLX layer, fill),
  a snare lay-back and a hat swing each.
- DENS scales the core (the backbone kick on 1, snare on 2 and 4 kept down to
  DENS 16), CPLX adds the second layer.
- HUMAN × the six aspects (VEL metric + chance, ROUND another slice of the
  role, TIME lay-back + swing + looseness, GHOST soft snares near the
  backbeat, ORN flams and fill rolls, VAR a fill at a phrase's end and a crash
  at its start); HUMAN 0 is the table untouched.
- BRK (one knob, scene-lockable): 1-31 more of the CPLX layer, 32-63 a fill of
  2 to 5 steps at every bar's end, 64-95 slices drawn from the whole kit
  (80-95 half-time), 96-127 cuts per beat (repeat with retrigs, or a hole).
  Deterministic from SEED and the bar: BRK 0 is the groove again.
- The track's trig always plays (an accent, 118; on an empty step a kick on
  the beat or a snare).

`verify.py`: 25 checks (HUMAN 0, SEED, trigs, BRK back, collisions, SHIFT,
bounds, the ColdFire compile), all pass. `render.py`: WAVs with the user's
sample through a one-voice model of the track (each hit cuts the last, 2 ms
fade); the VOL law is a placeholder until the unit's AMP VOL curve is measured.

## Phase 4a (5 Nov 2026): the engine in the firmware (port)

Module `drummer` (manifest.py, `generate.py` → `drummer_unit.s` from
drummer.c + adapter.c + hooks.s, 12.8 KB, 0 B .bss), test remix
`remixes/test/drummer`. T1 is the DRUMMER track (`dr_on`), the kit is the
user's 16-slice proposal built in; the knobs are the PLAYBACK page's values
(PTCH STYLE, STRT DENS, LEN CPLX, RATE HUMAN, RTRG BRK, RTIM SEED) until 4b.

Sites: `0x400a2d82` (tick, after the builder), `0x4009dca2` (rebuild, after
the builder, 8 bytes), `0x4000d3ae` (packer, page records set), SymbolRef
`0x400d6458` (FLEX start).

Learnt on the way (port):
- An added trig applies the lock block of its slot: the staging
  `0x46c7aa24 + 32t` when the builder's n is −1, else pending slot
  `0x46c7ab30 + 32 (n·8 + t)`. Stock fills it only for the trigs it builds; at
  boot it holds zeros, and an added trig set all 32 lane values of T1 to 0.
  DRUMMER now writes 0xff there (n = the builder's 5th argument, still on the
  stack at the tick's site). 🟡
- The transport start: the rebuild (`0x4009dc9e`, n −1) builds the first
  step twice, with the transport still at 0 (`0x800065b8` becomes 1 ~100
  samples later, `0x4009c3d4`); the tick's first call is step 2. So step 1 is
  decided in the stopped rebuilds, each from a fresh state, and the run goes
  on from there. Decisions made during the load (knobs not yet copied) were
  silence: while no frame has been packed the knobs come from the lane. 🟡
- A second build of the same step (the start's two rebuilds, an edit's
  rebuild while playing) replays the step's decision: the engine moves once
  per step. 🟡
- The tick's restart path (`0x8000668d` bit t) was never set in these runs.

`verify_port.py` (port, the user's sample, 240 BPM, 2 bars): each T1 voice
start is matched to its step and compared with engine.py for the same kit and
knobs — groove (BREAKBEAT, HUMAN 0) 32/32, human (HIP-HOP, HUMAN 100: ROUND,
ghosts, micro-timing) 32/32, forced (FUNK, DENS 0, track trigs on 3 and 11)
32/32.

Open: the hit's VOL heard (DSP, `--dsp` render), RTRG/RTIM rolls (not sent
yet: rtrg is dropped by the adapter), ALIGN, the scale learnt from a stock
trig (6 = 1X until one is seen), CX OSC on `0x400d6458`.

## Phase 4b (5 Nov 2026): the machine and its two pages (port)

`machine.s` (derived from ANALOG BD's registration, repeat98): DRUMMER is
row 5 of the machine list; a DRUMMER track is FLEX signed "DR",1 at Part
`+0x2a + 18 + 30t` (and the battery copy); a first signing seeds the twelve
knob bytes. adapter.c: `dr_type`, the page descriptor (FLEX's, cloned from
`0x400d3176`, twelve names, STYL 3 values with BRKB/HHOP/FUNK, all twelve
drawn: nibble words `P+0x18a` = 0x1111, `P+0x18e` = 0x11111111 — ANALOG BD's
words hid p6 and p11, measured on the screen), the Part validator (FLEX
defaults during stock's check, then DRUMMER's bytes back), PB_TABLE[5] each
UI tick. The DRUMMER tracks are now the signed ones (checked at each build
and each frame; the start's rebuilds come before any frame decision).

Pages: LIVE (SRC) STYL DENS CPLX HUMN BRK GHST — page record words, scenes
and LFOs applied; CONFIG (FUNC + SRC) SEED VEL ALT SWNG ORN VAR — page 2
bytes. SHIFT, the phrase and the priority go to the KIT window (4c).

Measured under the port (`shots_ui.py`): the list shows DRUMMER, YES signs T1
(machine byte 1, `DR\x01`, defaults 0/64/32/64/0/48 and 1/64/64/64/32/64), the
LIVE and CONFIG pages draw their six knobs each. `verify_port.py` with T1
signed in the project: groove, human, forced and config (every CONFIG knob
off its default: SEED 9 would be clamped to LOOP's 2 without the validator)
32/32 each. Not yet: the STYL formatter seen while turning, a scene moving
BRK (the page record path is the same as CX OSC's), the unit.

## Phase 4c (5 Nov 2026): the KIT window (port)

`kit.c`. TRIG + UP on a DRUMMER track opens it: a layer of ours (UP only)
is pushed while any trig key is held (key matrix rows 0-1, `0x46100b18`: any
mode, not GRID RECORDING's `0x460d174a` CHORDS reads) on a signed current
track in audio mode; the window is CHORDS' chooser (MAIN MENU's 118 x 64,
five rows, scroll arrows, SCALES' recipe). Rows: slice, ZONE (9 zones, 7 two-
zone combos, OUT), ROLE, ALIGN. UP / DOWN move and play, a trig key jumps to
that slice of the cursor's sixteen and plays it, A ZONE, B ROLE, C ALIGN (2 ms
a detent, 0-250), D SHIFT, E PHRASE 4/8, YES or NO close.

A slice is heard through the track's own trig (`0x40005030(t, 0x1d, 1, -1)`,
the SLICES mode's call) with the slice handed to the start wrapper
(`dr_preview`), not a STRT lock (STRT is DENS here).

ALIGN: the micro-timing word counts samples x tempo24 (`0x80001814`, BPM x
24); a slice's hit starts `ms x 44.1 x tempo24` earlier, never past stock's
−23 units.

Measured under the port: the window opens on the held trig's slice, UP/DOWN
and trig keys play the slices (voice +32 written 3, 4, 4, 5), A and C edit
(HAT C -> HAT O, 10 MS), the list scrolls, YES closes (`shots_kit.py`).
`verify_port.py` align: ALIGN 20 ms on slice 6, its starts 880 samples early
(882 wanted), the pattern 32/32. The kit is RAM only until drummer.work
(4d); a new DRUMMER track starts with the built-in 16-slice kit.

## Phase 4d (5 Nov 2026): drummer.work (port)

`store.c`, STORE client 8 (`modules/store`: CLIENTS, CLIENT_IDS, name_tab
`DRUMMER.WORK`, store_info "DRUMMER KITS NOT LOADED"). The file:
{`DRMK`, 1, 2656, CRC-32} + 8 × 332 B (zones, roles, combo masks, ALIGN,
priority, SHIFT, PHRASE, has-a-kit), FREE LOOP's handlers (written at the
bank writer and the project store when it changed, `.strd` at the store,
back at the reload, a bad file refused and never written over). The id is 7
on this branch (origin/main has 0-6); the user's rig has TURING 7 and CHORDS
8, CHORDS' PR asks 7 upstream: renumber when merging.

`verify_store.py` (port, `--mkii`: without it PROJECT > SAVE PROJECT did not
run and no .strd was written): KIT window edits on the panel (slice 1 SNARE,
ALIGN 20, SHIFT), SAVE PROJECT; drummer.work and drummer.strd on the card,
the header and CRC (zlib's CRC-32), T1's record as edited and T2-T8 without
a kit; a boot on that card puts T1's zones, roles, ALIGN, SHIFT and kit flag
back in RAM. 11/11.

## Phase 4e (5 Nov 2026): AUTO kit (host, then port)

`autokit.c` (freestanding, shared by the unit and the host). The audio of a
FLEX slot in RAM is big-endian: a stereo 16-bit slot reads as the WAV
byte-swapped (port, the user's loop, at 0x40aa45e0 in that image: the pool's
base moves with the platform's DRAM reserve, so the unit reads through
stock's pool walk `0x4009499c(slot, frame, 1)` -> d0 the frame, d1 the
contiguous run, hooks.s `dr_sample_at`). Slot flags `0x46c922c4 + 44 slot`:
bit 0 stereo, bit 1 16-bit (3 = stereo 16-bit, 227 613 frames, measured).

Calibration on the loop (`verify_autokit.py`): measuring from the slice's
start missed hits 160 ms in (slices 2 and 10: kicks), so the features are
taken from the main hit; the peak clips on most slices, so roles rank by
the level after the hit. Result: kicks 1 4 6 8 9 12 14 16 (2 and 10 with
ALIGN 160 / 158), snares 3 7 11 15, hats 5 13 — the phase 3 hand analysis.

The question: a DRUMMER track shown with no kit (ready 2: every slice OUT,
only its own trigs play) gets stock's YES/NO box (`0x4006d57c`, STORE's) —
only once a project is loaded: asked at boot, before the load, it answered
later with no slots and emptied a kit the load had restored (measured; the
fix also drops an answer for a track that got a kit meanwhile). FUNC + YES
in the KIT window asks AUTO again.

Port: the firmware's AUTO (T1 pressed, YES) = the host's, zone, role and
ALIGN for all 16 slices; the play gate now gets its kit from a drummer.work
in the project (load path), all cases 32/32; the save gate 11/11.

## After the first unit tests (5-6 Nov 2026)

On the owner's MKII (images 44-46): the machine row, the KIT question, AUTO
and the KIT window worked; PLAY played DRUMMER once DIAG mode 0 and grid
trigs were removed (accents and BRK breaks on the fly worked). Found and
fixed since, under the port:

- **The voice start takes three arguments**, `0x4000f450(track, slot,
  flags)` (the packer pushes `flags | 0xc0` at `0x4000d490`; stock reads it at
  `0x4000f54c`, `sp@(72)`). The wrapper forwarded two: stock read a word of
  the wrapper's stack. With the three, stock's retrigs run.
- **Retrigs**: RTRG = the restarts after the hit; RTIM is exponential, half a
  step at 79, twice as long every 12 (47 / 63 / 79 / 95: 434 / 1094 / 2756 /
  6946 samples at 120 BPM). Stock restarts the voice by another path than
  the start entry, reading the page record (RTRG `+8` is read after the start,
  `0x4000d4ea`), so DRUMMER sets RTRG / RTIM for the hit and dr_frame holds
  them; a retrig takes no queue entry. Gate `rolls`: 27 hits in the engine's
  order, 22 of 23 retrigs (one cut by the next hit: one voice).
- **The queue**: an entry older than the step before is dropped (it was two:
  a lost first hit — negative micro-timing on the transport's first step,
  dropped by stock — made every later start play the hit before it). The
  first step's micro-timing is never negative.
- **VOL**: the hit's level scaled a base read only when the restore bit of
  `0x80001538` was clear; on the unit that bit can be set at power-up and the
  base stayed 0 (silent hits until the machine was chosen again, or the AED
  touched the track — reported). The base is now the lane's VOL unless it is
  the last hit's own.
- **The KIT question** waited for no load to finish: asked between the banks
  and drummer.work (boot), it stayed open. Now held from `loadall_pre` /
  `loadmask_pre` to the `_post`.
- FUNC + YES / NO are stock's arm keys: AUTO again is RIGHT, the counters LEFT.
- Every track: `verify_port.py --track 2..8` groove 32/32 (T8 included).
- A power cycle with CS1 (`--cs1-in` + `--boot-load`): the slot, the kit and
  the starts come back. The unit's empty slot after a reload is to be
  checked against PROJECT > RELOAD (the last SAVE PROJECT).

## Image 55 (7 Nov 2026): the sample from DRUMMER, KIT on two pages, SCENE per slice (port)

**The sample.** PLAYBACK SETUP's machine list is the list record `0x460d5c28`
(cursor `0x460d5c30`), its slot lists `0x460d5c3c` (STATIC) and `0x460d5c50`
(FLEX, cursor `+8`); `0x460d1a48` is the focus (0 the machines, 1 a slot
list). Its key handler `0x4003d1c0(key)`: RIGHT (`0x21`) with focus 0 opens
the slot list of the cursor's machine, cursor 0 STATIC, 1 FLEX, anything else
nothing (DRUMMER's row 5 did nothing, measured); LEFT (`0x34`) with focus 1
goes back. YES with focus 1 commits through `0x4005a850` (dr_src_commit2,
measured with `--watch-pc`). `dr_setup_key` (detour at `0x4003d1c0`) sets the
cursor to FLEX on RIGHT from row 5 and marks the pick (`dr_ml_pick`): stock's
list, preview and commit run as FLEX's, the commit signs DRUMMER, LEFT puts
row 5 back, PLAYBACK SETUP's opening ends a pick. PB_TABLE[1] is DRUMMER's
page during the pick so the six SETUP knobs beside the list stay CONFIG's
(without it they drew as LOOP/SLIC... and knob A wrote SEED through LOOP's
range). Measured: T1 DRUMMER, RIGHT, UP, YES puts slot 135 in Part `+0x2ca +
5t + 1`, machine 1, `DR\x01` kept; a plain FLEX track unchanged (slot 135, no
signature). The title stays `<<FLEX` (stock's, drawn from elsewhere).

An objdump of `out/raw/section_3_MAIN_OS.bin` with `--adjust-vma=0x40000000`
is 0x400 off: the section starts at `0x40000400` (the build's expected bytes
for `0x4003d1c0` sit at file offset `0x3cdc0`).

**A new sample asks.** When a SETUP window closes on a DRUMMER track whose
FLEX slot changed while it was open, DRUMMER asks AUTO again (NO keeps the
kit); a Part or bank change never asks. KIT's AUTO AGAIN with NO emptied the
kit before (the first question's NO); it keeps it now.

**KIT pages.** LEFT / RIGHT pick page 1 (ZONE ROLE SHIFT PHRASE) or 2 (ALIGN
GAIN SCENE DOSE). FUNC held puts stock's layer over ours (RIGHT never reached
dr_kw_right, `--watch-pc`): FUNC + RIGHT is read from the key rows
(`0x46100b18 + 4` bit 1) each UI tick.

**SCENE per slice.** Scene locks are at Part `+0x662 + (scene * 8 + track)
* 32`, byte k = parameter k, 0xff none (PARAM_PAGES.md 5g; a fresh Part all
0xff, measured). A hit whose slice has a scene gets the scene's cells 6..29
in its trig's lock block (staging or pending slot n, as the added trigs'
0xff fill), DOSE of the way from the Part's value; a byte the trig locks
itself is kept. `verify_port.py --case scene`: FX1's first knob in the lane
at every start, 100 on slice 5's hits (DOSE 100), 50 on slice 3's (DOSE 50,
Part 0), 0 on the others (stock's restore at the next trig): 22/22.
drummer.work version 3 (4192 bytes: + SCENE and DOSE, 8 x 64 each),
`verify_store.py` saves them from the panel and reads them back.

## Image 56 (7 Nov 2026): the KIT title overflow, LIVE 2

**Reported on the unit (image 55):** the KIT window stayed on 2/2 (LEFT drew
1/2, then 2/2 again) and the column titles were gone. The title buffer
`dr_kw_band[24]` held "KIT T1 BRKB SHIFT PHR4 2/2" (27 bytes with SHIFT on):
the map has `dr_kw_info` at band + 24, `dr_kw_page` + 25, `dr_kw_rprev` + 26,
so every redraw wrote the page ('/' or '2') and the info countdown (the header
line showed SHIFT / PHRASE instead of the titles). The port's runs had SHIFT
off. Now 40 bytes, and the title is "KIT T1 BRKB SHFT P4 2/2" (it fits the
window). Seen under `--mkii` with SHIFT on: 1/2 kept after RIGHT, LEFT.

**LIVE 2.** `0x460d1684` = 0 on the SRC page, 2 on AMP (port, MKII). FUNC
held 8 UI ticks on a DRUMMER track's SRC page, nothing else open, no trig
held: a window and a layer whose encoders A-F (`dr_l2_enc`) turn six Part
bytes, the track's STATIC PLAYBACK column (`Part + 0x2a + 30t`), marked 'M'
after "DR",1 (`+0x3f + 30t`) once seeded at 64; written with the battery copy
and stock's edited marks (`bank + 0x9b332`, `0x100f8598`, `0x40027e00`, as
the SETUP commit). The Part validator wrapper keeps them (stock's FLEX
defaults during the check). FUNC + SRC opens CONFIG with no LIVE 2 window
(port). The engine reads them each step (`params_of`, 64 when unmarked).

## Image 57 (7 Nov 2026): LIVE 2 on PAGES, the KIT on TRIG + BANK

LIVE 2 moved from FUNC held (image 56, the owner's choice) to PAGES: audio
mode's SRC declared in PAGES with DRUMMER as client (`dr_page_shown / open /
close / tick`); `dr_page_open` does nothing off a DRUMMER track. Stock's
audio SRC again measured first (modules/pages/README.md). `verify_live2.py`.

The KIT opens on TRIG + BANK (was TRIG + UP). Stock's TRIG + BANK (a trig
held, BANK) is BANK's own SELECT BANK popup (port, MKII, FLEX track): BANK
alone, then a trig, still selects a bank; dr_up_layer only exists while a
trig is held on a DRUMMER track.

`verify_store.py` failed once with thirteen port runs in parallel (no
drummer.strd: SAVE PROJECT not done within the script's fixed wait) and
passed alone: run it on its own.

## Image 58 (7 Nov 2026): the whole kit in every style, KIT BALANCE

LIVE 2 is named KIT BALANCE (the owner's), drawn as six cells with dotted
borders, names and values centred. The rule routine `0x40011910(surface, x1,
y, x2, rows)` takes the end x, not a width (a 1-wide call drew whole rows
from x 1, seen on the screen).

Styles: 14 styles had PERC at COMPLEX only, 6 none; 11 had no tom, 8 more
only in fills. Worse, PERC and TOM ranked under HAT C and RIDE: on a level
with 16th hats every written perc lost its step (never played), and most
written fill toms sat on a snare step (lost too). Now: `styles.py` LAYER
writes PERC and TOM from STANDARD up for 19 styles (the 10 perc-built ones
keep theirs, BOSS gains a tom, SAMB and ELEC a COMPLEX perc), emit() drops
the cells on a kick or snare 'X' of their level, a fill's tom takes its
step from the snare and a fill with no tom ends on three; the default
priority is KICK SNARE CRASH HATO TOM PERC HATC RIDE GHOST (store.c turns the
old default of a saved kit into the new one). A zone the kit lacks plays its
first available substitute (SUBST); a fill's tom with no TOM, the snare. A
RIDE in the kit takes the closed hats every other phrase on a style without
ride (HUMN, VAR > 32). verify.py: a three-zone kit plays every style, a full
kit plays its nine zones.
