# hooks-core (test remix)

CORE with the modules a [HOOKS](../../../modules/hooks/README.md) bridge joins to it:
CF METER, CF METER IDLE and BOOT TRACE beside CORE's LOAD METER. The registry appends
HOOKS, which owns the shared frame interrupt entry and epilogue. MORPH and REC THRESHOLD,
once bridged with CORE's REC_TRIG_MUTE, are still in the image, now on sites of their own
(REC_TRIG_MUTE's pin after `553d8d2`).
PHASER gives up its words for LOAD METER's DSP half, as in `stock-meter-a`; DARK REV's
hold CF METER's readout insert, as in `cfmeter`.

`tools/verify/verify_hooks.py hooks-core`, after `make bus REMIX=hooks-core`, checks each
bridged site and each chain's calls in this image.

## Where it has run

Not flashed. Built, and its sites and chains checked (verify_hooks).
