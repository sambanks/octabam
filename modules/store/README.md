# STORE

Platform module. Holds the stock sites where a project's side files are
written, read, copied and cleared, and where a Part is saved or cleared. The
ledger allows one detour on a site; KITS and PLOCKS P2 each hooked some of
these sites, so the sites are held once here and each module is a client that
STORE calls at the event.

Spec: [docs/specs/STORE.md](../../docs/specs/STORE.md) — the events and their stock sites, the client list, the file calls, refused files, native Part access, the MIDI SETUP byte table and the register ABI.

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

## Retained storage provenance and verification

The [retained byte storage contract](../../docs/specs/STORE.md#retained-byte-storage)
covers registration, bounds and client-owned publication.

The implementation lives in `modules/store/retained*`, derived from
radiohagen's MIT-licensed protected pool at `3e5ac07`. STORE does not load
code or a module manifest from Harmony's submodule. The physical backing is
still two padding bytes in each MIDI step of the current-bank CS1 mirror:
16 patterns × 8 tracks × 64 steps × 2 bytes. That location does not restrict
a client's purpose to MIDI. Audio-step fields keep stock behavior.

STORE owns the three linked units, eight MIDI-only direct-loop guards and
8,192 separate two-byte SRAM claims. The protection covers the whole backing
pool, including unallocated bytes. Native copies preserve pool destinations
and return unlocked bytes for pool sources, keeping retained data out of
native DRAM, clipboards and bank files. No intervening stock bytes are claimed.
This is one protected backing region, not an allocator for all device SRAM.

`verify_store_retained.py` checks installed client bounds, native copy/clear
protection and two synthetic non-Harmony clients with disjoint reservations.
It also checks a retained-only client with no Part windows. Registration tests
cover zero/one/multiple clients, absent clients, overlap, duplicate IDs and
capacity errors. Harmony's retention gates cover its specialized word layout,
publication, interrupted saves and recovery. `generate-retained.py --check`
checks generated assembly against the maintained C source; Harmony's separate
author-reference gate no longer claims these locally maintained STORE units.
Physical battery retention, power-cycle behavior and hardware timing remain
unverified for this integration.
