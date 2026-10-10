# `plocks-p2` — PLOCKS P2

Parameter locks on page 2 of FX1 and FX2. `Kind.CF_PATCH`: one DRAM
unit, 52 detours, nothing on the DSP. Requires SCENES P2.

## Use

Open the FX1 or FX2 SETUP page, hold one or more trigs and turn a knob:
each held step gets that slot's page-2 lock. FUNC held while turning
removes it. The trig plays the lock and the next trig puts the Part's
value back, as page 1 does.

## Measured

Under the port, 2 Oct 2026, `tools/verify/verify_plocksp2.py` on
`plocks-p2` and on bottleservice with PLOCKS P2 added (Octakit, the bus, the FX1
stations, SCENES P2 KITS), project OCTABAM89_setgate:

- A held trig and knob A on the FX2 SETUP page lock step 1's page-2
  slot 0; stock's page-1 locks of step 1 stay 0xff.
- Trig copy and paste, clear a trig's locks, pattern copy and paste,
  clear pattern and its undo each carry or clear the page-2 locks with
  the stock data.
- T1 step 1 locked to 99 with trigs on steps 1 and 2: the live lane reads
  99 after step 1 and the Part's value after step 2; no other track's
  page-2 lane byte moves. The DSP record follows the lane (both pings,
  measured by hand the same day).
- SAVE PROJECT writes `p2lk03.work` and `p2lk03.strd` with the lock; a
  second boot of that card has it in the table after the load.
- Power cycles (`ot_emu --cs1-in` with the first run's CS1, `--no-post`
  for the firmware's own power-up load): a saved lock, a lock never saved,
  and a saved lock with the CS1 copy cleared (read from `p2lk03.work`)
  are each in the table after the power-up.

## On the unit

Not flashed.

## Open

- The CS1 copy holds 4,768 locks (`NV_MAX`; 10,234 until 10 Oct 2026, when 16,400 B of its top went to MIDI SCENES' copy); a current bank with more has no copy
  and a power cut loses its page-2 locks back to the last save.
- That CS1 keeps its contents over a power-off on the unit is read from
  stock's use of it (the power-up check and restore), not measured here.
- Bank reload and project reload (the `.strd` → `.work` copies) are
  hooked and not exercised by the gate.
- The dial draw with trigs held (SCENES P2's dial hooks call `plk_dial`;
  the port's LCD was not decoded).
- Page 2 has no slide: a slide trig moves page 1 only.
- A held step with no trig takes a page-2 lock that never plays (stock
  makes a lock trig from a page-1 lock; not mirrored).
- On the unit.

## CS1 writer ordering

`nv_save` is called from the UI task (priority 3) and the engine task
(priority 1, `plk_loadall`, `plk_loadmask`, `plk_tocs1`); the UI task
preempts the engine task at any instruction. Each call takes a ticket
(`NVGEN` incremented and `NVBANK` stored under SR `0x2700`). The entry loop
compares its ticket with `NVGEN` every four bytes, and the commit (count,
sum, magic) runs under `0x2700` after the same compare. A call that finds a
newer ticket starts over from `NVBANK`. The mask covers a few instructions;
the scan of up to 98,304 bytes runs unmasked, because a mask held for the
scan would delay the frame ISR (about 24,600 long compares on an empty bank:
inferred from the instruction count, not measured). A spin on a flag was
not used: the engine task spinning on the UI task's flag cannot make
progress if the UI task is the one preempting it. The ordering is by reading
the code; the port is lock-step and cannot interleave tasks, so it is not
measured on the port or the unit.

`read_bank` rejects a `p2lkNN` header whose version is not 1 as no locks.

## Gates

- `tools/verify/verify_plocksp2.py`.

## What stock does

`docs/firmware/STEP_LOCKS.md`. A step record is 32 lock bytes, page 1 of
the five pages. A trig's record goes from the step through a per-track
staging record and a pending slot to the frame ISR, which writes each
lock into the track's live lane and restores the Part's value at the next
trig. Nothing carries page 2, and every byte of the pattern data is used.

## What this adds

- **The table** (`.bss`, 1,572,864 B): 12 bytes a step for every bank,
  pattern, track and step; byte j = FX1 page-2 slot j, 6 + j = FX2's;
  0xff = no lock. `plk_init` fills it at the first use. The platform build
  refuses a `.bss` that ends past the arena reserve's ceiling.
- **Recording.** With a SETUP window open (`0x460d175c`) on the FX1 or
  FX2 page (`0x460d1684` = 3 / 4) and trigs held (`0x460d174a`), stock
  sends a knob turn to the page-1 lock editor `0x400508e4`, which locks
  the page-1 slot behind the window. `plk_edit` takes the turn instead:
  the slot's encoder hook and clamp from its descriptor, stock's edited
  marks (`DB + 0x9b332`, `0x100f8598`, `0x40027e00`), the slot's redraw.
- **Playback**, beside stock's stages: the record builder `0x4009d1e8`'s
  two fill paths (staging or pending slot n), the two staging → pending
  copies, the pending reset, the frame ISR's pending → trig record copy
  and a MIDI note's own record, and the join of the restore and apply
  paths (`0x4000c59e`), which writes the page-2 locks into the lane
  (`0x80000810 + 72t + 50 + j`) and restores the Part's bytes the last
  trig locked. SCENES P2's morph reads the lane as the knob.
- **Operations**: placing a trig, clearing locks, clearing a track or a
  pattern, trig copy and paste, and every memcpy site that moves a
  pattern (`0x8ed8`) or a track (`0x91a`) between the bank RAM, the
  clipboard (`0x460c8122`) and the undo buffer (`0x460bf218`): page 2
  follows in the same shape (two 6,144 B mirrors for the buffers). memcpy
  itself runs before the loader has placed the runtime, so its call sites
  are hooked, not its entry.
- **The current bank over a power-off.** Stock keeps the current bank in
  CS1 (`0x10000000`): `0x4000faf0` copies a bank there, edits write
  through, and at power-up `0x40025770` checks it, `0x4000fbb4` restores
  the bank and the firmware's load reads only the other banks from the
  card. The page-2 locks of that bank follow, sparse, in CS1's unused top
  (`0x100f8600..0x100fbdf0`): 16 bytes of header (`P2NV` written last,
  bank, count, sum) and 3 bytes a lock (step index << 7 | value). The copy
  is rewritten when stock copies a bank into CS1 and after every change
  to that bank; at power-up it is applied after stock's restore, or, with
  no valid copy, that bank's `p2lkNN.work` is read at the first bank load.
  Before 2 Oct 2026 nothing read the current bank at power-up, so its
  page-2 locks came back empty even when saved (measured under the port).
- **Files**: `p2lkNN.work` / `p2lkNN.strd` beside `bankNN.*` in the
  project directory, 16 bytes of header (`P2LK`, version 1, bank, length)
  and the bank's 98,304 B. Written where stock writes `bankNN.work`
  (`0x400918aa`), copied where stock copies `.work` ↔ `.strd` (bank store
  and reload, the project store and reload loops), read at the project
  load and the masked bank loads, and emptied for a new project. A missing
  source copies as an empty file.

## KITS

KITS (in bottleservice beside this module since 6 Oct 2026) hooks the
file routines' own entries (`0x40090504`, `0x400905d4`, `0x400909d8`,
`0x400917c8`, `0x4008ee74`, `0x4008f180`) where this module hooks their
call sites, so the two share no site. Its CS1 ranges (`0x100f85a0..e8`,
`0x100ffe00..ff00`) and MIDI SCENES' (`0x100fbdf0..0x100ffe00`) sit on either side of this module's.
