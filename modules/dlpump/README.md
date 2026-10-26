# `dlpump` -- DLPUMP

The ColdFire half of the demand loader (design, measurements and open items:
[`docs/proposals/DEMAND_LOAD.md`](../../docs/proposals/DEMAND_LOAD.md)).

`pump.s` is called from LOAD METER's entry code (`lm_in`, a weak symbol) on every frame
interrupt. Idle, on frames whose ping word (`0x800000e0`) is 0, it compares the ids on the 16
live FX slots (`0x80000ec4`) with the effects loaded and arms one message: a load when an effect
is used, not loaded, and one of its homes is free; a withdrawal when it is loaded and unused. Sending, it writes 100 halfwords a ping-0 frame
to core B's `X:0x2901..` by the stock host write, then the doorbell two frames later; a load is
sent three times. It never writes to core A. An effect is loaded into the first of its homes (blocks of the window) that no other
demand effect holds and whose FX2 slot is not a stock reverb that reaches the code; when such a reverb arrives on a loaded
effect's block and another home is free, the effect is moved there.

Detours at the FX1 and FX2 choosers' "same effect" test (`0x4005272a`, `0x400524ba`) refuse the
choice that would collide (an effect with no free home, or a reverb on a loaded effect's block when
the effect has nowhere to move) and show a toast saying why. Collisions made by other routes (song load, pattern,
paste) are toasted at the next page key by a detour at `0x4005578c`.

`remix.inc` (the effect table and the blocks) is generated per remix from
`out/dsp/demand_records.json`; the unit reserves 2,600 code words an effect on every link.

Gate: `verify_dlload` (the port). Not run on a unit.
