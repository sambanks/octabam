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

## Side-file clients

Refusal / `name_tab` ids: 0 PLOCKS P2, 1 KITS, 2 MIDI SCENES, 3 PERSISTENT BUFFERS, 4 MORPH, 5 FREE LOOP, 6 SCALES, 7 CHORDS FACTORY, 8 DRUMMER (`DRUMMER.WORK`), 9 SEQ (`EUCLID.WORK`), 10 PAGES' locks (`PGLOCKS.WORK`), 11 PATTERN MUTE (`PMUTE.WORK`). Each id has its line in `store_info_text`; until 17 Nov 2026 the table stopped at 9, so a refused `PGLOCKS.WORK` read past it.

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

## Saved Part byte reads

`store_part_saved_read` takes the same registered Part-relative offset and
0..63 bank/Part context as `store_part_read`, and returns a saved byte or -1.
It preserves every register except d0 and condition codes. Working-copy
snapshots do not replace the saved array. Any registered client can use it;
STORE assigns no musical interpretation to the byte.
