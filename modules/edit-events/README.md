# EDIT EVENTS

Platform owner of held-step encoder dispatch and the native pattern/track copy
sites shared by extended editors. It adds no controls or retained storage.

Register `(module key, symbol prefix, events)` in `CLIENTS` in `manifest.py`,
following STORE. Only selected clients enter the generated tables; unresolved
handlers fail linking. Declare `requires=('EDIT EVENTS',)` and select the module.

| Event | Contract |
| --- | --- |
| held | `<prefix>_claim(d0=encoder, d1=delta)` returns zero to pass; nonzero selects `<prefix>_handle` with the original native entry frame |
| copy_pre | d0=destination, d1=source, d2=length; before native data moves |

Held predicates must be read-only. Registration order is explicit precedence:
the first matching predicate wins. A new editor must declare its exact context
and test overlap and fallthrough with existing editors. Handlers return as the
native held editor would; they must not re-enter this dispatch. No owner means
one native fallback. This supports multiple editors on the same track type.

Copy notifications visit every client in registration order. Each client owns
its side data and filters addresses/lengths for its supported objects. Native
memcpy executes once after the notifications, and its result is returned unchanged.
Callbacks may clobber d0–d7/a0–a6; preserve SP and interrupt mask. Dispatcher
frames are stack-local. Client scratch state may impose stronger non-reentrancy.

The copy sites include pattern/track clipboard and undo transfers. This does
not pretend every clear/paste command is memcpy: distinct MIDI/audio trig-clear
and trig-paste hooks remain in their owning modules. Project/Part persistence
belongs to STORE. Add further shared editing boundaries here only after auditing
the native ABI and before/after semantics, with behavior tests at installed hooks.

PLOCKS P2's pre client preserves FX page-two locks and claims held audio FX SETUP edits. The dispatcher has no knowledge of its data format.

## Verification and cost

`verify_edit_events.py` tests the assembled dispatcher with zero, one and
three synthetic clients: precedence, fallthrough, arguments, register/stack
and condition-code preservation, callback order and exactly one native copy.
Client and native bodies are substituted at their boundaries.

For zero/one/three clients, copy dispatch executes 29/37/53 instructions and
held fallthrough 16/28/52. Counts exclude client/native-copy bodies and the
entry jump; held counts include the two displaced native instructions.
These are instruction counts, not physical timing measurements.

The old `plk_memcpy` had one tail jump after the mirror work. With PLOCKS,
that work now returns to a six-instruction adapter plus the 37-instruction
dispatcher: **43 extra instructions per copy-site invocation**. Assembled
old/new paths (baseline `ff9c5f84`) give these counts, including mirror work:

| Transfer | Old track | New track | Old pattern | New pattern |
| --- | ---: | ---: | ---: | ---: |
| Bank → clipboard | 680 | 723 | 4718 | 4761 |
| Clipboard → bank | 681 | 724 | 4719 | 4762 |
| Undo → bank | 683 | 726 | 4721 | 4764 |

Counts exclude the unchanged caller, native memcpy and `nv_touch` bodies;
copy results and `nv_touch` call counts match. The 29/37/53 dispatcher-only
counts above exclude the PLOCKS adapter and mirror work.

Only `held` and `copy_pre` ship, both consumed by PLOCKS. There is no sequencer
note dispatch. `verify_edit_event_clients.py` checks 21 installed hooks and
three executable callbacks; `verify_plocks_p2.py` covers real-client panel,
copy, playback and persistence behavior under the port. The claims ledger
rejects competing hook owners; dispatch selects one handler or native fallback.

Hardware: radiohagen, Octatrack MKII, Core PLK858/build 98, 22 October 2026:
FX1/FX2 held edits, multiple steps, native page-one/MIDI fallback and
trig/track/pattern operations passed. [Observed cases and image identity](../plocks-p2/DEVELOPMENT.md#edit-events-hardware-results-22-october-2026).
