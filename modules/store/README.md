# STORE

Platform module. Holds the stock sites where a project's side files are
written, read, copied and cleared, and where a Part is saved or cleared. The
ledger allows one detour on a site; KITS and PLOCKS P2 each hooked some of
these sites, so the sites are held once here and each module is a client that
STORE calls at the event.

## Events

| event | stock site | arguments to a handler |
|---|---|---|
| loadall_pre / post | `0x40090504` (load of every bank) | none |
| loadmask_pre / post | `0x400905d4` (masked bank load) | d1 = mask, d2 = return address |
| newproj | `0x400909d8` (new, empty project) | none |
| bankw_pre | `0x400918aa` (inside the bank writer, after the project directory exists) | d1 = mask of banks written |
| bankw_post | `0x400917c8` (bank writer, after it returns) | none |
| pstore_pre / post | `0x4008ee74` (project store) | none |
| preload_post | `0x4008f180` (project reload) | none |
| bankcopy | `0x4008ee42`, `0x4008f14e`, and the four `d5` loads at `0x4008ef9a`, `0x4008f02e`, `0x4008f2a6`, `0x4008f33a` (stock `.work` / `.strd` file copy) | d0 = destination path, d1 = source path; after stock's copy |
| tocs1 | `0x4000faf0` (current bank into CS1) | d0 = bank; before stock's copy |
| fromcs1 | `0x40025808` (power-up bank from CS1) | d0 = bank; after stock's call |
| partsaved | `0x4004a9c4` (Part Save tail) | d0 = part |
| partclear | `0x4004a9d0` (Part Clear entry) | d0 = part |
| ctl (not an event) | `0x40061e00` (the encoder dispatch call) | opens the refusal prompt, scrolls it; else KITS' list scroll or stock's dispatch |

A handler may clobber every register. Handlers of one event run in the order
of `CLIENTS` in `manifest.py`. Wrappers keep one return slot per event and do
not re-enter.

## Clients

`CLIENTS` in `manifest.py` lists, per module key, the symbol prefix and the
events it handles; the handler for event `e` is `<prefix>_st_<e>`. A client not
in the remix is left out of the tables, and a handler named there that the
link cannot find stops the build. A client declares `requires=("STORE",)`.

| client | events |
|---|---|
| PLOCKS P2 (`plk`) | loadall_pre, loadmask_pre, newproj, bankw_pre, bankcopy, tocs1, fromcs1 |
| KITS (`kits`) | loadall_pre/post, loadmask_pre/post, newproj, bankw_post, pstore_pre/post, preload_post, partsaved, partclear |
| MIDI SCENES (`scn`) | loadall_pre/post, loadmask_pre/post, newproj, bankw_post, pstore_pre/post, preload_post, tocs1, fromcs1, partclear |
| PERSISTENT BUFFERS (`pbf`) | loadall_post, loadmask_post, pstore_pre, preload_post |
| MORPH (`mrp`) | loadall_post, loadmask_post, newproj, bankw_post, pstore_pre/post, preload_post |

## Caller census

Every caller of `0x40090504` (1), `0x400905d4` (3), `0x400909d8` (5, one
pc-relative), `0x400917c8` (5, one pc-relative), `0x4008ee74` (3) and
`0x4008f180` (1) in the stock image is a direct call; a byte search of the image
for each address finds only those call operands (10 Oct 2026). PLOCKS P2's
call-site hooks covered every caller of the load and new-project routines, so
an entry hook sees the same calls.

## File calls

`store_path`, `store_fopen`, `store_fread`, `store_fwrite`, `store_fclose`
and `store_crc32` (running value in d1, 0 to start). A client owns a 4,120-byte
context (stock file object and its 4 KB buffer), so one client's open file is
never another's. `scenes.work` uses them; KITS and PLOCKS P2 keep their own
copies.

## Refused files

A client that cannot use a file (unknown version, bad length or CRC) calls
`store_refuse(client id, argument)` and leaves the file alone: it is never
written over. STORE lists up to 16 refusals (`store_pend`, `store_npend`,
cleared at a load of every bank). At the first encoder turn after the load
(the only UI-task site STORE holds; a list cannot be opened from the engine
task) a dialog names the file and explains which saved data could not be
loaded: FX page 2 locks, saved Kits or MIDI scenes. It says UNREADABLE OR
INCOMPATIBLE and offers NO: KEEP FILE / YES: OPTIONS.
YES opens the three recovery choices. NO keeps the
file protected and dismisses the prompt until the next project load:

| row | answer | what the client does |
|---|---|---|
| KEEP FILE / SKIP SAVED DATA | `ANS_IGNORE` | keeps the file protected and does not load its saved data |
| START FRESH / REPLACE FILE | `ANS_OVERWRITE` | starts empty (KITS: as a missing file, the stock Parts become Kits); the next save replaces the original file |
| BACKUP FILE THEN START FRESH | `ANS_BACKUP` | starts fresh, and the next save first copies the original file to `.bak` |

This is recovery, not a format upgrade: the old saved data is not converted.
The prompt can also appear for damaged or incomplete files, not just files
from development builds. The exact cause needs the refused file to be examined.

LEVEL scrolls the list; YES answers; NO closes it without an answer, leaving the
entries listed and asking no more until the next load. No answer touches the
card: the callbacks run in the UI task and the save in the engine task (a file
copy called through the port's `--call` never returned). Client ids: 0 PLOCKS P2
(argument = the bank), 1 KITS, 2 MIDI SCENES, 3 PERSISTENT BUFFERS, 4 MORPH. PLOCKS P2 used
to read a refused `p2lkNN.work` as empty and overwrite it at the next bank write.

## Measured

Under the port (10 Oct 2026): `verify_kits` (the refused `kits.work`: listed; OVERWRITE
and BACKUP read it as a missing file; the list opens at an encoder turn, LEVEL + YES
answers OVERWRITE, YES on row 0 answers IGNORE), `verify_plocks_p2` (a bad `p2lk` header is
listed and survives SAVE PROJECT), `verify_scenes --persist` (a bad `scenes.work` stays byte
for byte under IGNORE; OVERWRITE and BACKUP give a good file, BACKUP also `scenes.bak`).
15 Oct 2026 (#742): `verify_kits` also checks the initial information
dialog, YES opening the choices, and NO keeping the file protected without
reopening on another encoder turn. `verify_plocks_p2` exercises the same
information, choices and cancellation with a refused lock file, capturing
the LCD for review. Not covered: a list opened over another window, the
new prompt on a unit.

With COPY PROJECT in the remix, LEVEL (control 6) scrolls that module's
project LISTPOP only (`M_CBS == name_fp`, the same gate `kits_level` uses
for KITS' own lists). Other stock LISTPOPs are left to stock / `kits_level`.

## Native Part access

STORE also owns the native copy/reset boundaries used by modules that keep
settings in working Parts. The native Part service is selected only when a
registered Part client is in the remix; other STORE
compositions retain their existing code and hooks.

Use this service when a module needs to edit native Part bytes, read a track's
playing Part independently of the editor, or discard temporary history after
Part replacement. Continue using the side-file events above for companion
files. A module that only reacts to transport or editor gestures uses EVENTS.

### Adding a client

1. Declare `requires=('STORE',)` in the module manifest.
2. Add one entry to `PART_CLIENTS` in `modules/store/parts.py`: the native
   Part-relative read windows and writable byte offsets. Read windows are
   merged and snapshotted once. Write offsets must belong to a read window;
   out-of-Part ranges and invalid registrations fail before linking.
3. Declare ownership of custom bytes in the module's `Claims.part_window`.
   STORE's access registration does not allocate storage or grant two modules
   independent ownership of the same field. The shared MIDI SETUP flags byte
   remains owned once by STORE; clients preserve the other bits.
4. Use the explicit context API below. Validate the field's meaning and range
   in the client. Keep note ownership, routing and other musical state there.
5. Test the client alone and alongside existing clients, including native
   save/reload/clear, interrupted replacement and disabled behavior. Declare
   the client gate in its own manifest.

Current clients read the native MIDI SETUP window; the general byte API also
supports declared non-MIDI Part windows. A synthetic regression exercises two
separate non-MIDI windows, odd packed-snapshot stride and the last Part byte.
No untested audio-field layout or audio parameter semantics are claimed.

### Register ABI

All entries preserve registers other than d0 and condition codes. A context
is `bank * 4 + Part` (0–63), with no dependence on the current UI selection
after it is captured. Offsets are relative to a native working Part, not a
bank file's serialized header. No raw writable pointer is returned.

| entry | input | result in d0 |
| --- | --- | --- |
| `store_part_ui_context` | none | edited bank/Part, or −1 |
| `store_part_audio_context` | d0 = audio track 0–7 | audio-engine bank/Part; applied-context fallback while unlatched, or −1 |
| `store_part_midi_context` | d0 = MIDI track 0–7 | MIDI-engine bank/Part; applied-context fallback while unlatched, or −1 |
| `store_part_read` | d0 = Part byte offset, d1 = context | coherent byte, or −1 outside a registered read window/context |
| `store_part_write` | d0 = Part byte offset, d1 = context, d3 = byte | 1 accepted; 0 for invalid/unregistered input or a Part currently being replaced |
| `store_part_epoch` | d0 = context | wrapping 32-bit replacement counter; invalid context returns −1 |
| `store_part_midi_read` | d0 = MIDI track, d1 = context, d2 = SETUP byte 0–35 | layout adapter for the general read API |
| `store_part_midi_write` | same, d3 = value 0–127 | layout adapter for the general write API |
| `store_part_midi_key` | d0 = MIDI track, d1 = context | read-only KEY byte; no writable permission is added |

The MIDI readers share the general reader's register frame. Valid track/field
pairs already prove the Part bounds; context, registered-window and snapshot
checks still use the shared service. The ordinary MIDI read and KEY paths take
44 and 42 executed instructions respectively with the current MIDI window,
down from 48 and 53 before this optimization (`verify_store_part` checks the
ceilings). These are instruction counts under the CPU harness, not hardware
cycle or utilization measurements.

Native replacement and setting writes use the native single UI-writer path;
playback/interrupt readers may interrupt it. This API does not serialize
competing writers: a client must not write from a playback interrupt or another
concurrent writer.

Writes update the working byte, its current-bank battery-backed CS1 mirror
and native Part/bank dirty markers in one short interrupt-masked section.
Saved Parts and card files remain owned by the native save operations.
Unchanged writes do not mark clean state dirty. A busy write returns zero;
the client must not report success or spin waiting for the replacement; retry
from the UI after the native operation returns.

Native copy and initialization run with their original interrupt state.
Readers of affected contexts see the outgoing snapshot until publication;
unaffected Parts continue to read their native data. Publication increments
the counters for exactly the affected Parts and exposes the incoming bytes
in one short critical section. Compare counter inequality, not ordering;
ordinary single-setting edits do not increment it. Snapshot state and counters
are runtime-only and initialized by the existing loader. Existing saved
settings and stock-firmware fallback behavior do not change.

Replacement notifications are polling through `store_part_epoch`; there is no
runtime subscriber list. Optional build-time companion callbacks in
`PART_CALLBACKS` can prepare side data before replacement. They run outside
the publication critical section, must not re-enter replacement or yield, and
cannot veto the native operation. Read-only `store_part_snapshot_bank` and
`store_part_snapshot_parts` expose the currently replacing bank and Part mask
for companion snapshots; only STORE may write them. Bulk copies spanning
multiple native banks are outside this contract.

When a composition selects no companion callback, the build omits its setup
and replacement walk. STORE's shared APIs and publication rules stay available.

The cold resident gates use stock copy/init before the runtime is loaded.
The original post-loader activation point publishes the DRAM targets. The
new names and generic windows do not remove this cold-start protection.
When BOOT TRACE is also selected, HOOKS calls its boot notification and then
STORE's activation. Without a registered native Part client, STORE adds no
boot hook and needs no bridge.

### Provenance and verification

The initial copy/reset implementation comes from radiohagen's MIDI PART STATE
at `3b1fda3410e698718230d984901a34a02e9346ab` (MIT). Native layout and lifecycle
provenance is in [Parts](../../docs/firmware/PARTS.md); MIDI SETUP layout is in
[MIDI tracks](../../docs/firmware/MIDI_TRACKS.md). The source checks the stock
instructions at copy `0x40020898`, init `0x40005638`, activation `0x40000512`
and, only for a client with live NOTE SETUP fields, confirmation `0x4004af20`.

The `verify_store_part*` gates cover context bounds, write permissions, CS1 and
dirty state, cold-entry ABI, real copy/clear publication, replacement counters,
boot integrity and non-MIDI windows. Removing epoch publication and corrupting
the cold-entry register save are rejected by negative controls. Functional
checks are emulator evidence. On an Octatrack MKII (29 October 2026,
MFOL29U / BUILD FA), Follow's native OCT setting passed Part save/reload and
project save/power-cycle persistence; post-reboot USB MIDI pitches matched the
saved OCT 4 value. This is limited native Part hardware coverage, not validation
of every client or replacement operation. Earlier hardware reports for STORE's
side-file service and MIDI Loopback remain scoped to their recorded images.

Audio latches are `0x8000182a` / `0x80001832`; MIDI latches are
`0x8000666e` / `0x80006676` (published by the MIDI step routine at
`0x400a1ace` / `0x400a1ad4`). Both use applied `0x80001828` / `0x80001829`
only while their own track is unlatched. The context gate deliberately keeps
audio and MIDI on different Parts.
