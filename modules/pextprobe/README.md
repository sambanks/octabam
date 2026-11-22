# `pextprobe` -- PEXT PROBE

A measurement instrument: where can a DSP core keep code besides its stock P
memory? Hot reload (the proof of concept on the hot-reload branch) needs a
pool for swapped effects. `DSP.md` section 3 records `P:0x2000` as executable
(a relocated CHORUS ran on the unit, `P:0x2000..0x2148`) and the upper bound
as unmeasured; the stock boot code also runs from the shared window
(`P:0x30000`, `P:0x38000`). It ships in no remix but `remixes/test/pext-probe`.

It is an insert on EQUALIZER's id (every id 4..31 is taken). Its output replaces
its track's audio with a status word, 32 bits a frame, one per sample slot, and
a capture of the track's audio reads it with `decode.py`. `pextprobe.asm` is
written by `gen_pextprobe.py` (the rungs are the same code at different
addresses).

## The two ladders

GO is a select: OFF, LOW, WIN. Seven rungs, one every 64 frames (23 ms) after
64 idle frames. Turning GO to OFF starts the ladder over.

| GO | rungs | what a rung does | codes |
|---|---|---|---|
| LOW | `P:0x1fe0` (a control: spare words on both payloads, known real), `0x2000`, `0x2100`, `0x2400`, `0x2800`, `0x3000`, `0x3800` | reads the address and the address `0x2000` below it: equal and non-zero is a wrap onto live code and nothing is written; otherwise writes a pattern, reads it back, puts the old word back | 1 REAL, 2 ALIAS, 3 ABSENT |
| WIN | `P:0x30100, 0x35900, 0x36300, 0x36800, 0x37000, 0x37800, 0x37e00` | writes the pattern and reads it back; then writes a three-word routine (`move #>$a5a5a5,x0` / `rts`), calls it and reads x0; then zeroes the three words | 1 read/write only, 2 read/write and EXECUTE, 3 read/write failed |

If LOW's rung 0 is not REAL, the store does not work and nothing else in LOW
means anything. A call that freezes the core leaves its rung in the last frame.

The WIN addresses are the words the bus remix leaves free in payload A's half of the shared
window, from `Claims.dsp_ranges` (`tools/remix/dsp_ranges.py`): BusVerb takes
`0x30800..0x35800`, the bus scratch `0x36000..0x36200`, stock's staging
`0x30000..0x30048`, the mailbox `0x37f00`, the LOAD METER's figures
`0x37f10..0x37f50`; free: `0x30048..0x30800` (1,976 words), `0x35800..0x36000`
(2,048), `0x36200..0x37f00` (7,424). Payload B's half is BusDelay's LineL
(`0x38000..0x40000`). The window is one memory for both cores, so both
instances use the same words: run one core at a time.

Under `dsp_host` every rung passes (the emulator maps P at all of them), so
`tools/verify/verify_pextprobe.py` proves the instrument, the decoder and the
routine a WIN rung writes and calls, not the hardware's answer;
`tools/verify/tests/test_pextprobe.py` covers the outcomes the emulator cannot
produce (ALIAS, ABSENT, a frozen core, a silent capture). Forms the chip has
not run: a P store through `(r1)` and `jsr (r5)` (the stock listing has
absolute P stores and `jsr` to an address).

## Files

`pextprobe.asm` (written by `gen_pextprobe.py`), `manifest.py`, `decode.py`,
and [`remixes/test/pext-probe`](../../remixes/test/pext-probe/README.md).
