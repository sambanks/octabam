# EVENTS

System owner of shared native event boundaries. Select **EVENTS** once; clients
declare `requires=('EVENTS',)` and register only the events they consume.
EUCLID uses transport notifications. MIDI Follow uses transport and accepted-note
notifications. PLOCKS P2 uses held-edit ownership and
copy notifications. PAGES' locks use held-edit and held-scene ownership, and
copy and step notifications. The module adds no controls, persistent data or FX slots.

Spec: [docs/specs/EVENTS.md](../../docs/specs/EVENTS.md) — the stock boundaries, the registration form and each family's contract and timing.

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
