# `octakit` — OCTAKIT

Em's Octakit — 256 Kits per Project in place of 64 bank-tied Parts — built
from [emuyia/ems-octakit](https://github.com/emuyia/ems-octakit) (submodule
`upstream/`, pinned at `c6d3f39`, ot-26914-152100). `Kind.CF_PATCH` with a
`Runtime`: 735 guarded sparse writes into the OS image plus a 154,766-byte
runtime in DRAM. No DSP code, no menu row.

Her README (`upstream/README.md`) is the user-facing description: LOAD/SAVE
KIT on PART / FUNC+PART (MKI: FUNC+MIDI / FUNC+BANK), FUNC+CUE reload,
7-character names, copy/paste/clear/undo, LOAD KIT > UNDO KIT (the last
loaded Kit), FUNC+PASTE+PART (MKI: FUNC+PASTE+MIDI) saving a pasted
Pattern's Kit to the next free slot, PTN+FUNC+RIGHT (save the Kit, copy
it and the Pattern to the next free slots, load the pair), PTN+FUNC+TRIG
copy/paste/clear/undo of inactive Patterns (BANK+TRIG, then
BANK+FUNC+TRIG for other Banks), automatic Parts→Kits migration of old
projects. **Back up projects before
flashing; downgrading to stock may lose Kit data** (her words).

## Measured

- Homebrew `m68k-elf-gcc` 16.2.0 rebuilds the runtime, the packed runtime
  and the append byte-identical to her pinned 16.1.0 identities.
- `tools/verify/verify_octakit.py` (in `make verify`): stock + her writes + her
  append reproduces her combined OS image (`output.os`) exactly. An octabam
  image is never identical to hers (its own FX2 chooser, DSP null stubs and
  loader); the build prints that.
- Under the ColdFire port: her wrapper calls our loader, her gate and
  post-load entry run with her hash, the boot reaches the RTOS handoff, and
  her window reads back byte-identical.
- Her stage (`0x47fc7410..0x47fd910f`) is needed on boot only (Em, 12 Sep
  2026); the bounce-buffer fills the port measured there happen at project
  load, after her code has moved to the reserve.

## On the unit

- 14 Sep 2026: `OKMS1` (remix `ok-ms`, with MIDI SCENES), confirmed
  working by midisc's author on his unit.
- The tokened page-1 writer (below) was carried by image 88 on Sam's
  MKII, not exercised there.

## Open

- Whether her unsaved-changes marking (if any) notices a tokened or
  page-2 write.
- Her UNDO KIT and pattern-paste paths after one.

## Gates

- `tools/verify/verify_octakit.py` (in `make verify`).

## How it is built

`upstream/runtime/firmware.json` is her recipe. `tools/remix/runtime_build.py`
compiles and links her sources with her linker script, packs with her encoder
(ported to Python), links again with the packed blob, and re-derives every
identity the recipe pins; a mismatch stops the build with both digests. The
Elektron routines her runtime carries (459 distinct `stock/NNNN.bin`
names in `upstream/runtime/*.S`; an earlier count was 411) are `.incbin`'d from the user's
stock 1.40C at build time.

In an octabam image her packed runtime is a payload of octabam's loader
(`tools/remix/loader.S`, derived from hers), staged at her own stage address
so her post-clear relocation finds it; her sparse writes are kept; her own
append is replaced. Her runtime, Kit store and backup are the top 528 pages
of the audio page arena (`0x45d0dde0..0x46025de0`), declared as an
`ArenaReserve` so the build stacks every reservation and writes the arena
geometry once.

## Collisions

Her recipe rewrites the apply_part entry `0x40009094` and the scene-parameter
writer `0x40052ae8`; the ledger refuses any other module on those sites. CC
MAP shares her MIDI CC dispatch entry through `modules/scenes-kits`.

## Calling the page-1 writer beside her (26 Sep 2026)

Her recipe repoints the three stock calls to the page-1 writer
`0x40054cd8(track, flat, value)` at her wrapper
(`gk_stock_track_parameter_absolute`), and rewrites the writer's own dirty
store (`0x40054fec`) to run her marker: it reads the long 12 bytes above
the writer's arguments and halts (`illegal`, `0x45d2128e` in the
`bottleservice` build) unless its top half is
`GK_TRACK_PARAMETER_TOKEN_ARMED` (`0x54500000`, her `abi.inc`). Her wrapper
is what puts it there, and it accepts only the three stock return
addresses, so a module can neither call the writer bare nor call her
wrapper. TEMPO BUS and MODE DEFAULTS did call it bare: under the port
`bottleservice` halted at frame 40 of `verify_set`'s run on CC 68 (a MODE
change re-defaulting page-1 knobs).

What they do now: push the token themselves (`P1TOKEN` in
`modules/tempo-bus/helpers.s`, `modules/mode-defaults/modedef.s`), then
call the stock writer. `manifest.py` reads the constant from her `abi.inc`
and stops the build if it moves. Stock ignores the extra word. Her
`gk_track_parameter_prepare` / `finish` (workspace mark-dirty and commit)
do not run on that path, as they do not for CC MAP's page-2 stores.

Measured under the port (`bottleservice`, the `make accept` stress project,
`make panel` on `localhost:8572`, 26 Sep 2026):

- `--watch-pc`: five MODE DEFAULTS calls per CC 68 (the PHSR view's
  page-1 defaults 28 121 127 64 64), each reaching `0x40054fec`, none
  reaching her fatal; `verify_set` 900/900 frames, 0 failures.
- Kit save / reload: CC 68 = 0 (JUNO) wrote T1 FX1 page 1 `1a 15 12 40 .. 46`
  through the tokened writer; FUNC+PART+YES saved Kit 001; CC 68 = 77
  (PHSR) changed it to `1c 79 7f 40 .. 40`; FUNC+CUE brought the JUNO
  bytes back.
- Cross-Kit: Kit 002 set to PHSR and saved; LOAD KIT 001 read JUNO, 002
  read PHSR.
- Copy: FUNC+REC on 002 in LOAD KIT, FUNC+STOP on 003, loaded 003 ("003
  TWO"): the PHSR bytes; 001 and 002 unchanged.
- The same sequence over CC MAP's page-2 store (`bottleservice`, T1 FX1 slot 6)
  saved, reloaded and stayed per Kit.

## Kit data, for anyone writing to it (from Em, 12 Sep 2026)

- Kits keep the Part layout and offsets.
- Saved Kit data is at `__gk_canonical_payloads + kit * PART_PAYLOAD_SIZE`
  (`0x18b2`), a flat 256-entry array — the read side is a base change.
- The saved Kit and the active working Kit are separate. A write goes
  through her editing functions, in order: `gk_workspace_prepare` →
  `gk_physical_acquire` → `gk_descriptor_store_byte` per changed byte →
  `gk_workspace_mark_dirty_pending` → `gk_workspace_commit_update` →
  `gk_descriptor_release`. All six are `.global` in her runtime.

## Patches on her runtime

`manifest.py` lists `Runtime.patches`: unified diffs the build applies to
a COPY of her sources after her own build has reproduced her pins, with
the patched build's own pins (`Runtime.patched`: raw, packed, append) as
the refuse-on-drift rule. Her recipe writes that carry the runtime's
length, its x33 hashes or a linker-derived address (the backup's start)
carry the patched values; the build substitutes them over each guard's
region because her writes are sparse and a literal can straddle two of
them (4 Oct 2026: `4e00|01 52` across a kept stock byte). A patch must
not move a stock slice: the build checks every `.incbin`'d routine at
its recorded offset, so a site edit is a same-length replacement and new
code is a new unit listed LAST in the recipe's `sources`, in a
`.runtime.*` section, after `persistence.c`.

- `patches/0001-banks-load-error-applies-current-bank.patch` (5 Oct 2026;
  on the unit in image A4, below): a stock bank load that returns an error (a bank file whose
  checksum fails, −51; a missing one, −12) returned from
  `gk_stock_banks_load_work` before the post step, so the lifecycle word
  stayed QUIESCED for the session: every paste halted at
  `gk_current_pattern_part_set_fatal`, every Part apply was skipped. Stock's
  load loop applies the current bank (SRAM working copy `0x4000faf0`,
  pattern request `0x400a1030`, engine part load `0x40009094`,
  `0x400907b8..ea`) only when its file parsed, so after an error the
  engine's bank/part bytes (`0x80001828/9`) are the previous project's and
  her `gk_ui_transition_prepare_entry_release` returns CORRUPT at the
  engine-bank compare. `octabam_banks_load_fixup.S` runs that apply when
  the engine's bytes disagree with the current bank/part (the engine part
  load through her trampoline: her wrapper accepts four stock callers in
  the quiesced state), then the post step and the activation run on the
  stock result, which is still what the caller sees. Measured under the
  port with Sam's rejected `bank01.work` staged as the current bank: stock
  returns −51, the apply runs once (the background load's second −51
  finds the bytes agreeing and skips it), activation clears the word, no
  fatal, a pattern paste completes; a clean project enters the fixup with
  d0 = 1 and skips it. On the unit (image A4, 5 Oct, the rejected file
  as `PROJECT STRAND`): PARSE ERROR on load, then PLAY halts at
  `gk_stock_audio_pattern_primary_begin_report_fatal` (no lease for the
  rejected bank's part; reproduced under the port). With the rejected
  file deleted (stock −12, bank initialised empty) load, play and paste
  are clean under the port. Raw runtime 154,878 B (hers 154,766; her code
  budget ends 770 B above it). A project name with no directory on the
  card (stock −12 on every file) still strands: her work-pair create
  returns −10 with nowhere to write (`docs/contributing/FAILURE_MODES.md`).
- `patches/0002-part-refresh-busy-runs-stock.patch` (5 Oct 2026, measured
  under the port, unflashed): a track button pressed within about 250 ms
  of a queued pattern change (a chain or a single [PTN] + [TRIG] switch)
  halted at `gk_stock_part_refresh_writer_report_fatal_part_refresh_fatal_context`:
  `gk_stock_current_context_validate` returns BUSY while
  `__gk_sequencer_latch_queue_handoff` is set, and her Part-refresh
  writer wrapper took every negative return as the context fatal. Her
  `machine_selection.S` and `midi_bit_toggle.S` test BUSY before their
  fatal and return it; this writer wraps a stock call with nobody to
  return to, so on BUSY it runs the stock writer the way her QUIESCED
  path does, with no Kit lease. The writer's four validator calls and the
  dirty-store marker's compare are same-length `jsr` swaps into
  `octabam_part_refresh_busy.S`; `d7` carries a third token state through
  the stock body (UNWRAPPED, `0x4655` beside her ARMED `0x4652` and
  WRITTEN `0x4657`; stock's writer saves and uses d2–d6/a2–a5 only) and
  the marker replays stock's dirty store for it. A BUSY from the
  post-write validation releases the descriptor and returns. Measured
  under the port (Octakit alone and bottleservice): the press that halted
  at 17.05–17.275 s, the single-switch and current-track controls, 250
  presses at 180 ms over a three-pattern chain, and a run that goes on
  through a knob turn, a second press at the next change and SAVE KIT all
  end clean with the lifecycle word active; the unwrapped path ran at
  both presses (PC watch, d0 = −3). Not exercised: the marker's unwrapped
  replay (stock's writer found every track byte already `0x80`, so it
  never reached its dirty store) and the post-write BUSY. What the Kit
  workspace misses by not seeing an unwrapped run's dirty marks is not
  measured. Raw runtime 155,062 B (586 B below her code budget's end).

## Updating

Bump the submodule and rebuild; the identity checks either pass or name the
digest that drifted. A new `interface_version` in her recipe stops
`runtime_build.py` until it is taught.
