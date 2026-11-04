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

A **soft** effect, one that keeps a stock effect's dispatch (`MenuEntry.stock_dsp`: SIDECHAIN_COMPRESSOR is
COMPRESSOR, id `0x18`), is never refused: while its code is not loaded the track runs the stock effect. The
choosers let it and any reverb through, a reverb that reaches its loaded code takes the block at once (the
effect is withdrawn and the track runs as stock), and its toasts say so (`SC KEY OFF: T4 FX2` when no home is
free, `SC KEY OFF: T4 REV` when a reverb took it). The flag is the eighth long of the effect's `dl_tab` row
(`table_inc`'s `_soft`). While SIDECHAIN_COMPRESSOR's code is not loaded, page 2's KEY reads `--`: `dl_keyfmt`
wraps sc_cf's `key_fmt` (`FormatterReg(wraps=True)`, written over KEY's formatter word only, so the switch widget
stays) and prints `--` while the effect's `dl_loaded` bit is clear; the stored KEY is not touched (issue #934).
`verify_labels` calls it in both states under the emulator. Not run on a unit.

`remix.inc` (the effect table and the blocks) is generated per remix from
`out/dsp/demand_records.json`; the unit reserves 2,600 code words an effect on every link.

Gate: `verify_dlload` (the port). Not run on a unit.
