# hooks-boot (test remix)

BOOT TRACE beside STORE, with MIDI LOOPBACK (which requires it) and the stock
effects. Both take the boot's call after the platform loader (`0x40000512`), so the registry
appends [HOOKS](../../../modules/hooks/README.md), which sends BOOT TRACE's note 3 and then
runs STORE's native Part activation, which makes the stock call. Without a registered
native Part client, STORE has no boot hook and BOOT TRACE keeps its own call.

`tools/verify/verify_hooks.py hooks-boot` checks the chain in this image after
`make bus REMIX=hooks-boot`.

## Where it has run

Not flashed. Built, and its chain checked (verify_hooks).
