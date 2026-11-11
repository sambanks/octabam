# EVENTS: native event boundaries

The contract for modules that react to transport, accepted MIDI, the held-step editor or native copies. A client declares
`requires=('EVENTS',)` and registers per family in EVENTS's `CLIENTS`; EVENTS installs only the boundaries a client uses. Selection rules, instruction counts and
the verification boundary are in the [EVENTS module](../../modules/events/README.md). Which of STORE, EVENTS and HOOKS fits a site:
[SHARED_SITES.md](SHARED_SITES.md).

## Native boundaries and saved data

The installer checks each hook site's expected stock 1.40C instructions,
detour kind and overwritten width against the user's image before patching.
Selection determines which sites are installed. The address-load sites
`0x40029550` and `0x4002a426` cover track-lock snapshot/restore for trig undo.

| Contract | Stock boundary and continuation |
| --- | --- |
| Transport | `0x4009c3d4` / `0x4009c4d4` write PLAYING at `0x800065b8`; continue at `0x4009c3da` / `0x4009c4da` |
| Accepted MIDI | `0x4009fbb2` / `0x4009fcfa`, after native sender `0x40010bc8` returns; continue at `0x4009fbb8` / `0x4009fd00` |
| Held editor | Entry `0x400508e4`; unclaimed edits replay its prologue and continue at `0x400508ec` |
| Held scene | Stock's scene knob handlers, installed over every encoder while a scene key is held (`0x46c7dede + 20 * encoder`): SCENE A's entry `0x40053498`, SCENE B's `0x40052e98`; unclaimed turns replay the prologue and continue at `0x400534a0` / `0x40052ea0` |
| Steps | Stock's routines that move or clear a step's page-1 locks (`docs/firmware/STEP_LOCKS.md` section 4): a trig taken off `0x4006036e` (after its `d3 = a5 + d6·16`), clear the held steps' locks `0x40040e14`, clear a track `0x40039df4`, trig copy `0x4002bf38`, trig paste `0x4002cb52` (before the step's lock copy); each replays what it displaced and goes on (`0x40060374`, `0x40040e1c`, `0x40039dfc`, `0x4002bf40`, `0x4002cb58`) |
| Copy | The 22 call/address-load sites listed in `manifest.py` target native memcpy `0x40020898`; callbacks finish before entering it with the original frame |

These addresses and instructions are observed; the event names describe their
roles, not firmware symbols. Native-code tests check transport writes, MIDI
acceptance and copy behavior. The individual copy sites retain PLOCKS' existing
bank/track, clipboard and undo scope; they are not a claim to intercept every
firmware copy. Memcpy's entry is not patched because stock also calls it before
the runtime is loaded. Client-owned RAM and storage provenance remains in the
[PLOCKS reference](../../modules/plocks-p2/README.md#what-stock-does) and
[development notes](../../modules/plocks-p2/DEVELOPMENT.md#stock-address-provenance).

EVENTS owns no project fields, sidecars, battery-RAM records or saved values,
so it introduces no saved-data migration or new stock value range. PLOCKS keeps
its existing `P2LK` version-1 sidecars and `P2NV` record; STORE still owns its
save/load integration. Switching to firmware without a client removes that
client's behavior. The unchanged formats do not establish a stock-firmware
save/return guarantee for client data; no such round trip is claimed here.

## Register by contract

`manifest.py` groups registrations in `CLIENTS`, with one list per family:

```python
CLIENTS = {
    'transport': (('EUCLID', 'eu_seq', ('start', 'resume')),
                  ('MIDI FOLLOW', 'bf_seq', ('start', 'resume'))),
    'midi': (('MIDI FOLLOW', 'bf_seq', ('note_accepted',)),),
    'edit': (('PLOCKS P2', 'plk_ed', ('held', 'copy_pre')),
             (('PAGES', 'DRUMMER'), 'pg', ('held', 'scene_held', 'copy_pre', 'steps'))),
}
```

Each entry is `(module key, callback prefix, handled events)`; a module key may be a
tuple of keys, present when all of them are (PAGES' locks: PAGES with a LOCKS client). A client may
register in several families. Prefixes must yield unique callback symbols;
invalid events, duplicate clients within a family, duplicate callbacks and
invalid assembler names fail at build time, even for absent clients.
Missing callback implementations fail linking.

| Family / event | Contract and timing |
| --- | --- |
| `transport.start` | Notify all: d0 = native PLAYING value, after its fresh-start write |
| `transport.resume` | Notify all: d0 = native PLAYING value, after its resume write |
| `midi.note_accepted` | Notify all: d0 = MIDI track 0–7, d1 = native pool kind, d2 = packet velocity, d3 = packet note; after the sender returns, before ownership bookkeeping |
| `edit.held` | First owner: `<prefix>_claim(d0=encoder, d1=delta)` returns zero to pass or nonzero to select `<prefix>_handle` with the original native entry frame |
| `edit.scene_held` | First owner: `<prefix>_scene_claim(d0=encoder, d1=delta)` returns zero to pass or nonzero to select `<prefix>_scene_handle` with the original native entry frame; SCENES P2 detours SCENE A's entry privately, so the two cannot share a remix until it registers here |
| `edit.steps` | Notify all: d0 = op, d1-d5 its arguments; 0 TRIG_CLEAR (step, the UI's bank, pattern and track), 1 LOCKS_CLEAR (pattern, track, page, mask), 2 TRACK_CLEAR (pattern, track, flags), 3 TRIG_COPY (clip, pattern, track, page, mask), 4 TRIG_PASTE (clip, pattern, track, source record, destination step); before the stock routine goes on. PLOCKS P2 detours the same five sites privately, so the two cannot share a remix until it registers here |
| `edit.copy_pre` | Notify all: d0 = destination, d1 = source, d2 = length; before exactly one native copy with its original arguments |

Notification symbols are `<prefix>_<event>` (for example `eu_seq_start` or
`observer_note_accepted`). Family names describe contracts; there is no runtime
event-number switch or universal callback ABI. `sequencer.s` implements timing
notifications, `edit.s` implements editor ownership and copies, and `frame.inc`
holds only their common register-save contract.

Callbacks run synchronously in registration order, may clobber d0–d7/a0–a6,
and must preserve SP and the interrupt mask. Arguments are reloaded before
every callback, independently of earlier clients. Native registers and condition
codes are restored before continuation. All saved frames are stack-local;
dispatch stack depth does not grow with the number of clients.

Transport/MIDI callbacks must not emit MIDI, re-enter the sequencer, or modify
the native MIDI packet or ownership records. Acceptance describes the firmware
boundary, not UART delivery or reception by an external device. It is per
accepted voice, including chords and ownership replacement, not a chord-root
event. Pool kind is passed through unchanged (1 is the live arp pool). Rejected
and zero-velocity native notes bypass these boundaries; note-offs, CCs, MIDI
input, pause and STOP are not events.

Held predicates must be read-only. The first matching predicate wins; its
handler receives the untouched native function frame. No match falls through
to the native editor exactly once. New editors must define their context and
test overlap with existing owners. Neither predicates nor handlers may re-enter
held dispatch. Copy observers own their side data and filter addresses/lengths
themselves; native memcpy runs once after all observers. Trig clear/paste hooks
remain feature-owned. Persistence remains STORE's responsibility.
