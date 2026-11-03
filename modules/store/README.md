# STORE

Platform module. Holds the stock sites where a project's side files are
written, read, copied and cleared, and where a Part is saved or cleared. The
ledger allows one detour on a site; KITS and PLOCKS P2 each hooked some of
these sites, so the sites are held once here and each module is a client that
STORE calls at the event.

Spec: [docs/specs/STORE.md](../../docs/specs/STORE.md) — the events and their stock sites, the client list, the file calls, refused files, native Part access, the MIDI SETUP byte table and the register ABI.

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
| newproj_post | after the native new-project routine returns | none; optional |
| bankw_guard | before bankw_pre | d1 = bank mask; negative d0 refuses the write |
| bankcopy_guard | before native file copy | d0 = destination, d1 = source, d2 = 0; negative d0 refuses |
| bankcopy_done | after native copy and bankcopy notifications succeed | d0 = destination, d1 = source, d2 = native result; negative d0 propagates companion failure |
| bankcopy | `0x4008ee42`, `0x4008f14e`, and the four `d5` loads at `0x4008ef9a`, `0x4008f02e`, `0x4008f2a6`, `0x4008f33a` (stock `.work` / `.strd` file copy) | d0 = destination path, d1 = source path; after stock's copy |
| tocs1 | `0x4000faf0` (current bank into CS1) | d0 = bank; before stock's copy |
| fromcs1 | `0x40025808` (power-up bank from CS1) | d0 = bank; after stock's call |
| partsaved | `0x4004a9c4` (Part Save tail) | d0 = part |
| partclear | `0x4004a9d0` (Part Clear entry) | d0 = part |
| ctl (not an event) | `0x40061e00` (the encoder dispatch call) | opens the refusal prompt, scrolls it; else KITS' list scroll or stock's dispatch |

A handler may clobber every register. Handlers of one event run in the order
of `CLIENTS` in `manifest.py`. Wrappers keep one return slot per event and do
not re-enter. Checked callbacks return negative d0 to stop the phase;
nonnegative results allow the next client. Arguments are restored before each
client even if the previous callback clobbered all registers. Native file-copy
failure skips all companion notifications. With no subscribers, checked phases
and the post-new-project return slot are omitted.

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
| FREE LOOP (`fl`) | loadall_post, loadmask_post, newproj, bankw_post, pstore_pre/post, preload_post |

| MIDI HARMONY (`ch`) | loadall_post, loadmask_post, newproj, newproj_post, bankw_guard, bankcopy_guard, bankcopy_done, tocs1, fromcs1 |

## Caller census

Every caller of `0x40090504` (1), `0x400905d4` (3), `0x400909d8` (5, one
pc-relative), `0x400917c8` (5, one pc-relative), `0x4008ee74` (3) and
`0x4008f180` (1) in the stock image is a direct call; a byte search of the image
for each address finds only those call operands (10 Oct 2026). PLOCKS P2's
call-site hooks covered every caller of the load and new-project routines, so
an entry hook sees the same calls.

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


## Provenance and verification

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

## Harmony retained storage

Selecting MIDI HARMONY also selects STORE's retained MIDI storage support.
There is no separate MIDI SRAM module to enable, and other STORE clients do
not install this code or its copy/clear changes.

The unchanged radiohagen implementation is read from Harmony's pinned source
(`modules/midi-harmony/upstream/modules/midi-sram`). STORE owns the two linked
units, eight MIDI-only copy/clear loop guards and 8,192 separate two-byte SRAM
claims. Its native copy wrapper preserves these bytes in CS1 and strips them
from native bank files and clipboards. Audio-step fields keep stock behavior.
The full 16,384-byte pool belongs to Harmony's step state and track metadata;
PLOCKS and MIDI Scenes retain their separate allocations. This does not alter
the retained layout or the `hdegNN.work` / `.strd` companion format.

Harmony owns checkpoint validation and publication. Clearing SRAM invalidates
those checkpoints; recovery uses validated project companions. The optional
`verify_midi_sram.py` gate checks bounds and native copy/clear protection;
Harmony's gates check the installed lifecycle. Fresh author-source assembly
is compared with the packaged storage units by `verify_harmony_reference.py`.
Physical battery retention, power-cycle behavior and hardware timing remain
unverified for this integration.
