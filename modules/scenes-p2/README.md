# `scenes-p2` — SCENES P2

Scene locks and the crossfader for page 2 of FX1 and FX2. `Kind.CF_PATCH`:
one DRAM unit, seven detours, nothing on the DSP.

## Measured

Under the port, 5 Nov 2026 (`octabam`, a fresh project, `verify_scenes_p2`'s
`panel` scenario and a probe beside it):

- From the panel: T1, FX2 SETUP open, SCENE A held, knob E turned three
  times: scene 0 holds one cell (T1 FX2 slot 4 = LOCK, value 1), the Part
  byte and the lane stay 0. Fader at the A end with the transport on: T1's
  DSP record carries LOCK 1; at the B end, the knob's 0. FX1 SETUP, knob A:
  the same (cell key 8, record 1 / 0).
- Before the fix, the same gesture wrote no cell: a held scene installs
  stock's scene-lock knob handler `0x40053498` over every encoder (the
  dispatch table `0x46c7dede + 20·encoder`), so the page-2 editors and
  their hooks were never called (`--watch-pc`: zero calls of `0x4003a9dc`
  with SCENE A held, three without). The `editor` checks below call the
  editor directly and could not see it (`TRAPS.md` "A held scene replaces
  every encoder's handler"). `scene_knob_hook` at `0x40053498` sends a
  turn to the edit hooks while an FX SETUP window is open; page-1 scene
  locks with no window are unchanged (same scene-block byte as before).

Under the port, 10 Oct 2026, the cells (`tools/verify/verify_scenes_p2.py`
on `remixes/test/scenes-midisc`, MIDI SCENES + KITS + SCENES P2 + PLOCKS
P2, OCTABAM89_setgate):

- Cells `{scene 0: MODE 1, TIME 100; scene 1: TIME 20}` on T1, fader 64:
  MODE 1 and TIME 60 in both pings; fader 0: MODE the knob, TIME 20.
- The FX2 editor with scene A held: one cell written in the working window
  and the SRAM twin, the Part byte and the lane unchanged; a seeded cell
  updated in place; FUNCTION + turn empties it; with all eight cells of the
  scene taken the turn is dropped.
- Stock scene copy `0x400274cc(0, 0)` then paste `0x40027578(0, 3)`: scene
  3's cells equal scene 0's.
- Stock image, every scene block's bytes 30 and 31 set to `0x12 0x34` in
  every Part record against the unmodified project, 300 frames with the
  transport on: no DSP block differs (`blockdump.py diff`); the working
  copy `0x80000ed4` differs in those bytes' pairs only.
- 1,536 bank files on this machine: bytes 30 and 31 are `0xff` in all
  196,608 scene blocks. The census does not show that no stock code reads
  them; the frame builder skips them (`0x4000cef6`), and scene copy, paste,
  undo snapshot and clear move 32 bytes a track (`moveq #32` at
  `0x400274f8`, `0x40025bc8`, `0x4002761c`, `0x40038cbc`).

Under the port, 26 Sep 2026, the 144-byte pool at Part `+0x17a2` this
module used until 10 Oct 2026 (stock's LFO designs of MIDI tracks 2–8,
`docs/firmware/PARTS.md` section 9):

- bamsep26 and rig-kits (Octakit): pool `{scene 0: MODE 1, TIME 100;
  scene 1: TIME 20}` on T1 (BusDelay), fader 64: T1's record carries MODE 1
  and TIME 60 in both pings, the predicted lerp exactly; fader 0: MODE 0
  (the knob), TIME 20. Scene A disabled: the A side is ignored (the fixture
  project has it off).
- The FX2 editor called with scene A held: the pool and its SRAM twin gain
  one entry, the Part byte and the live lane do not move; with a seeded
  entry the same entry is updated, count 1; with FUNC held the entry is
  removed. Under rig-kits the held call returns cleanly and the pool lands
  in the Part DB's current bank.
- Scene copy fills the clip; paste into another scene adds the clip's
  entry under it; clear drops the scene's entries; the undo snapshot fills
  the undo clip and a write from the undo buffer restores it.

## On the unit

- Anything on hardware beyond being carried by image 88 (pre-fix), not
  exercised there.

## Open

- The dial hook (a draw; the port's LCD was not driven to the page).
- Whether SAVE KIT saves after page-2 lock edits alone.
- The undo row's writer is inferred to be `0x40025b40(0x460bf218, ...)`
  from the paste row's shape; the write hook was exercised with that call.

- A knob PRESS with a scene held toggles the page-1 lock of that knob
  (stock, `0x40053a68`); page 2 has FUNC+turn to
  remove a lock instead.
- A scene holds eight page-2 locks across its tracks (128 a Part). The
  pool before 10 Oct 2026 held 47 a Part across all scenes.
- Page-2 scene locks saved by an image before 10 Oct 2026 are in the old
  pool at Part `+0x17a2` and are not read.
- Whether any stock routine other than those named under Measured reads
  or writes scene bytes 30 and 31.

- **Cell store order.** The frame pass (inside the frame ISR) reads the
  cells without a lock, key byte first. A new lock writes the value and
  then the key; a removal writes `0xff` to the key; an update writes the
  value. An ISR between two stores sees no lock or a whole one. The order
  is by reading the code; the port is lock-step and cannot interleave the
  ISR with the task.

## Gates

- `tools/verify/verify_scenes_p2.py`.

## What stock does

The frame builder morphs one scene block a track per frame into the DSP
frame: 32 bytes a track a scene, byte *k* the lock for frame halfword *k*,
bytes 0..29 = page 1 of PLAYBACK, LFO, AMP, FX1, FX2, bytes 30..31 skipped.
Page 2 (slots 6..11) has no byte and the loop stops at halfword 17
(`docs/firmware/MIDI.md` Appendix C). Fader position `0x460d16c8`
(0..127) rebuilds a weight table `0x80003c60` (a long per track, hi word
`-xf*258`, Q15): `xf = 127` is scene A, `xf = 0` scene B.

## Why not stock's scene block

Widening stock's scene block to page 2 means changing all of these
together (`docs/firmware/MIDI.md` Appendix C):

1. Block size: 0x20 bytes/track/scene in the project (`0x8f3e2` stride, 24 code
   sites incl. copy/paste/undo at `0x40025b40`, `0x400274cc`, `0x400275a0`).
2. Working copy `0x80000ed4`: 0x40/track, 32 pairs, all fillers assume 32.
3. Frame-builder extents: `moveq #6` (page block) and `moveq #9` (voice
   record) at `0x4000ccb6/0x4000cd0e`, `0x4000cd96/0x4000cdea`,
   `0x4000ce5e/0x4000cee8`; skip at `0x4000cef6`. Halfwords 24..26 are 7 longs
   past where the record pass stops.
4. The scene editor's slot→byte map (`0x40053a2c` region) and the two
   encoder-hook descriptors at `P+0x12a` that call the STRT/LEN morph.
5. The arithmetic itself, to leave the low byte alone.

Two spare bytes per track could host **one** extra halfword, not three, and
the DSP-side companion packing would still be lost at every intermediate
position. Those two bytes (30 and 31, skipped by the morph) are where this
module keeps its locks instead, as cells the frame pass reads itself.

## What this adds

- **The cells.** Bytes 30 and 31 of each track's 32-byte block in the
  stock scene block (Part `+0x8f3e2 + 0x100·scene + 0x20·track`) are a
  cell: byte 30 = `track<<4 | fx1<<3 | slot2`, bit 7 set = empty; byte 31
  = the value. A scene's eight cells (one per track block) hold up to eight
  locks of any of its tracks. Stock moves these bytes with the rest of the
  block: Part Save, Reload and paste, Project Save, the CS1 copy, KITS's
  Kits, and scene copy, paste, undo and clear. `Claims.part_window` lists
  the 128 cells; MIDI SCENES' bytes are elsewhere.
- **The frame pass** (`frame_hook`, at the join after the stock morph,
  `0x4000cf40`). Per track: the current key `(bank, part, scene A, scene
  B)` (bank/part from `0x8000182a[t]` / `0x80001832[t]`, the selectors from
  the part) is compared with a cache row; on a change the track's locks are
  unpacked from scene A's and scene B's cells (A and B values per slot,
  `0xff` = none). Every
  locked slot is then written into the voice record's page-2 bytes (FX2
  halfwords 24..26 = bytes 48..53, FX1 18..20 = 36..41): `(A*wA + B*wB +
  0x4000) >> 15`, an unlocked side taking the knob byte the copier left in
  the record; a select (descriptor count < 128) snaps, the A side from
  `wA >= 0x4000`. A disabled scene (`0x80000006` / `0x80000007`) counts as
  unlocked; both disabled skips the track, as stock does. Cost with no
  locks: about 15 instructions a track a frame.
- **The editors.** Both page-2 editors (FX2 `0x4003a9dc`, FX1
  `0x4003abe4`) are detoured at entry. With a scene held (`0x460d169c`: 1 =
  A, else B) a turn on slots 6..11 edits the held scene's lock: the slot's
  own encoder hook and clamp (descriptor `+0x12a`, `+0x6a`, `+0x9a`) from
  the lock's value, or the Part's byte when unlocked; the cell in the
  working window and its SRAM twin (`0x100a4ece + part*0x18b2`); the stock
  scene editor's dirty marks; the slot's redraw flag. With FUNC held the
  turn removes the lock. A scene with eight locks drops a turn that would
  add a ninth. No scene held: on to the stock body with the entry
  state untouched.
- **Scene copy / paste / clear / undo.** Stock moves the cells. The scene
  write (`0x40025b40(src, part, scene)`: paste, undo) and the clear writer
  (`0x40038c30(scene)`) are detoured to run as calls and drop the frame
  cache after they return.
- **The dial.** The page-2 knob draw reads the Part byte at `0x40037840`
  (FX2) and `0x40037bdc` (FX1); with a scene held it shows that scene's
  lock instead, as the page-1 dials do. With PLOCKS P2 in the remix and
  no scene held, trigs held show the first held step's page-2 lock
  (`plk_dial`).

## Octakit (until 6 Oct 2026)

Her recipe replaced both page-2 editor entries with wrappers that opened a
kit-write token, called the stock body and validated at a marker inside
it; `modules/scenes-p2-kits` overrode her two writes so this unit's stubs
sat at the entries in front of her wrappers. KITS leaves the editors
stock, so `P2_NEXT2` / `P2_NEXT1` are always the stock bodies.

The entry detours displace eight bytes (`lea` + `movem`), and `fx2_stock`
/ `fx1_stock` continue at entry+8 where the stock `moveal %sp@(32),%a2`
still stands. Until 28 Sep 2026 they displaced twelve and the build
nopped that instruction: under Octakit's trampoline the body ran with a
garbage slot in a2 and her marker check halted the unit on every page-2
knob turn (rig-kits, bottleservice; measured under the port; image 88
carried it and the halt was not reported from the unit).
