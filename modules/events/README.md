# EVENTS

System owner of shared native event boundaries. Select **EVENTS** once; clients
declare `requires=('EVENTS',)` and register only the events they consume.
EUCLID uses transport notifications. MIDI Follow uses transport and accepted-note
notifications. PLOCKS P2 uses held-edit ownership and
copy notifications. The module adds no controls, persistent data or FX slots.

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
| Copy | The 22 call/address-load sites listed in `manifest.py` target native memcpy `0x40020898`; callbacks finish before entering it with the original frame |

These addresses and instructions are observed; the event names describe their
roles, not firmware symbols. Native-code tests check transport writes, MIDI
acceptance and copy behavior. The individual copy sites retain PLOCKS' existing
bank/track, clipboard and undo scope; they are not a claim to intercept every
firmware copy. Memcpy's entry is not patched because stock also calls it before
the runtime is loaded. Client-owned RAM and storage provenance remains in the
[PLOCKS reference](../plocks-p2/README.md#what-stock-does) and
[development notes](../plocks-p2/DEVELOPMENT.md#stock-address-provenance).

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
    'edit': (('PLOCKS P2', 'plk_ed', ('held', 'copy_pre')),),
}
```

Each entry is `(module key, callback prefix, handled events)`. A client may
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

## Selection and performance

`Module.select` is applied in `registry.bound()` before claims, linking and
installation. EVENTS chooses each event's detours independently and links only
the source units needed by selected subscribers. Assembly omits every unused
entry point. Consequently:

- No clients: no event code, tables or hooks; zero runtime overhead.
- PLOCKS only: 23 editor/copy hooks, no transport or MIDI hooks.
- EUCLID only: two transport hooks, no MIDI or editor hooks.
- EUCLID + PLOCKS: 25 hooks, no MIDI hooks.
- MIDI Follow: four hooks (two transport, two accepted-MIDI). Adding EUCLID
  keeps those same four hooks and adds its transport callbacks.

Active dispatch uses generated direct calls. There are no null checks, pointer
tables, indirect callback calls or registration loops on a live event. One
client pays one direct callback call; each additional notification client adds
argument reloads and one call. Code size grows linearly with subscriber count;
stack depth stays constant. This favors small, fixed firmware compositions.

The assembled event fixtures measure the following instruction counts,
excluding the entry instruction and client/native bodies. Held fallthrough
includes the two displaced native prologue instructions:

| Clients | Copy dispatcher | Held fallthrough | Transport dispatcher | Accepted-MIDI dispatcher |
| --- | ---: | ---: | ---: | ---: |
| 0 | 0 | 2 (stock prologue) | 1 (stock instruction) | 1 (stock instruction) |
| 1 | 13 | 16 | 12 | 30 |
| 3 | 21 | 26 | 16 | 34 |

Zero-client EVENTS has no dispatcher: tests execute stock code. Both MIDI
acceptance sites have the same count. These are emulator instruction counts,
**not** ColdFire cycles, elapsed time, hardware CPU headroom or MIDI latency.

The real PLOCKS mirror path was also assembled against its pre-dispatch source
(`ff9c5f84`). Across 14 track/pattern transfers and uninitialized cases, native
copy results, side data and `nv_touch` call counts match. Shared dispatch
adds **19 instructions**. For example, a track bank-to-clipboard copy is
680 → 699, and a pattern copy is 4718 → 4737. These counts include the
six-instruction PLOCKS adapter, but exclude the unchanged caller, native memcpy and `nv_touch`
bodies, which the probe substitutes at their entry points.

## Verification boundary

`verify_system_events.py` executes production assembly with zero/one/three
synthetic clients, independent transport subscriptions, and native MIDI packet
construction/arbitration. `verify_edit_events.py` checks first-owner precedence,
native fallback, register/stack/condition-code preservation, callback ordering,
copy results and counts. A second pass executes native memcpy for 12 lengths
and four alignments, comparing zero/one/three clients' copy bytes, entry frame,
return registers, stack and condition codes. Synthetic callbacks deliberately
clobber registers.
`verify_events_selection.py` checks all 32 event subsets, absent code/hooks,
invalid registrations and the registry's bound real-client selections. A
16-subscriber MIDI case also checks branch reach and constant stack depth.
`verify_event_clients.py` checks executable callbacks, exclusive installed hook
ownership and stock bytes at every unused boundary in each built image.

The [events-clients fixture](../../remixes/test/events-clients/README.md) selects
both clients with USB MAIN/CUE and LOAD METER for focused integration checks.
EUCLID and PLOCKS retain their own behavior gates. The fixture's
[hardware results](../../remixes/test/events-clients/README.md#hardware-results)
identify the tested image and scope.
Add further events only with an audited native boundary, a precise contract,
and both dispatcher and installed-image tests.
