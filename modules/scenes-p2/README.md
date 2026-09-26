# SCENES P2

Scene locks and the crossfader for page 2 of FX1 and FX2. `Kind.CF_PATCH`:
one DRAM unit, nine detours, nothing on the DSP.

## What stock does

The frame builder morphs one scene block a track per frame into the DSP
frame: 32 bytes a track a scene, byte *k* the lock for frame halfword *k*,
bytes 0..29 = page 1 of PLAYBACK, LFO, AMP, FX1, FX2, bytes 30..31 skipped.
Page 2 (slots 6..11) has no byte and the loop stops at halfword 17
(`docs/firmware/MIDI.md` Appendix C). Fader position `0x460d16c8`
(0..127) rebuilds a weight table `0x80003c60` (a long per track, hi word
`-xf*258`, Q15): `xf = 127` is scene A, `xf = 0` scene B.

## What this adds

- **The pool.** Each Part window carries 144 bytes at `+0x90522`: `u16`
  magic `P2`, `u8` count, then 3-byte entries `scene<<3 | track`,
  `fx1<<3 | slot2`, `value`; 47 at most. The window is copied whole by
  Part Save, Part Reload and Project Save (`docs/firmware/STORAGE.md` §3)
  and by Octakit's Kit operations (`gk_copy_payload_interruptible`,
  `GK_PART_PAYLOAD_SIZE / 4` longs; no digest over it), so the pool travels
  with the part. midisc's MIDI-track lock blob lives at the same offset:
  `Claims.part_window` makes the ledger refuse the pair.
- **The frame pass** (`frame_hook`, at the join after the stock morph,
  `0x4000cf40`). Per track: the current key `(bank, part, scene A, scene
  B)` (bank/part from `0x8000182a[t]` / `0x80001832[t]`, the selectors from
  the part) is compared with a cache row; on a change the track's locks are
  unpacked from the pool (A and B values per slot, `0xff` = none). Every
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
  the lock's value, or the Part's byte when unlocked; the pool in the
  working window and its SRAM twin (`0x100a4ece + part*0x18b2`); the stock
  scene editor's dirty marks; the slot's redraw flag. With FUNC held the
  turn removes the lock. No scene held: on to the stock body (or Octakit's
  wrapper, see below) with the entry state untouched.
- **Scene copy / paste / clear / undo.** A copy (`0x400274cc`) snapshots
  the scene's entries beside the stock clipboard; the undo snapshot
  (`0x400275a0`) does the same for its buffer; a scene write
  (`0x40025b40(src, part, scene)`: paste, undo) drops the target scene's
  entries and adds the clip's when `src` is the stock clipboard
  (`0x460c8122`) or the undo buffer (`0x460bf218`); the clear writer
  (`0x40038c30(scene)`) drops them.
- **The dial.** The page-2 knob draw reads the Part byte at `0x40037840`
  (FX2) and `0x40037bdc` (FX1); with a scene held it shows that scene's
  lock instead, as the page-1 dials do.

## Octakit

Her recipe replaces both page-2 editor entries with jumps to wrappers that
open a kit-write token, call the stock body, validate at a marker inside
it that the body stored what she expected, and commit; a body that is
skipped is fatal. `modules/scenes-p2-kits` overrides her two writes and
the build defines `P2_NEXT2` / `P2_NEXT1` as her wrappers, so this unit's
stubs sit at the entries: a held-scene turn writes the pool and never
enters her wrapper; every other turn reaches her wrapper with the entry
state untouched. A held-scene edit alone does not mark the Kit dirty in
her bookkeeping (the stock Part dirty bits are set). Her writes touch none
of the other seven sites.

## Measured (the port, 26 Sep 2026; `tools/verify/verify_scenesp2.py`)

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

## Not measured

- Anything on hardware.
- The dial hook (a draw; the port's LCD was not driven to the page).
- Octakit's unheld editor path through the bridge: her wrapper refuses a
  `--call` (no UI context; plain rig-kits faults identically), so it needs
  a panel-driven edit.
- Whether SAVE KIT saves after page-2 lock edits alone.
- The undo row's writer is inferred to be `0x40025b40(0x460bf218, ...)`
  from the paste row's shape; the write hook was exercised with that call.

## Open

- A knob PRESS with a scene held toggles the page-1 lock of that knob
  (stock, `0x40053a68`, a function Octakit wraps); page 2 has FUNC+turn to
  remove a lock instead.
- The pool holds 47 locks a part.
