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
