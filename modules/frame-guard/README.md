# FRAME GUARD

A frame interrupt that enters 110 to 190 µs late waits until it is 190 µs
late. ColdFire only; no DSP code or state, nothing on the panel.
Author: Sam Banks. On hardware (Sam's MKII, 12 Nov 2026).

## The observed failure

The DSP raises the frame interrupt once a frame (362.8 µs) and the
ColdFire answers by sending it the next frame. At START and at a program
change one frame interrupt runs 475 to 585 µs (every image measured, with
and without USB), so the next one enters late.

Measured on Sam's MKII, 12 Nov 2026, `octabam`, first START after boot,
with a log of the last frame interrupts read over USB (33 logged STARTs
without the guard, on images without added delay or within 10 s of START):

| the next frame interrupt enters | what follows | STARTs | stalls |
|---|---|---|---|
| 128 to 149 µs late | one back-to-back frame interrupt, then the 362.8 µs grid | 8 | 0 |
| 149 and 155 µs late | two back-to-back frame interrupts, the second before its grid time, then none | 2 | 2 |
| 155 to 223 µs late | one frame skipped, then the grid | 23 | 0 |

After a stall the sequencer holds step 1, LOAD METER's DSP count is
constant, and the panel and USB answer; a power-cycle clears it. Rates
without the guard on that unit: 5 of 8 first STARTs (`octabam` without
SHATTER, 4-channel USB capture), 1 of 8 (20-channel capture, stock
crossbar priorities), 1 of 16 (4-channel capture, with the frame log), 0
of 8 with no capture (START frame 473 to 481 µs) and 0 of 8 with 60 µs
added to every frame interrupt and no capture (the next entry 163 to 180
µs late). A USB capture adds 25 to 30 µs to the START frame, which is what
moved it onto the boundary.

Outside the window, and not covered by this module: on a test image with
60 µs added to every frame interrupt and a 20-channel capture (the frame
interrupt at 91 % of the ColdFire), 1 of 16 first STARTs stalled with the
next entry 209 µs late and one skipped frame, and 7 of 16 froze the whole
unit (panel and USB) 8.2 s after START, at the pattern's wrap. Neither has
been seen on an image without the added delay.

Inferred, not measured: at that lateness the ColdFire's transfer chain is
still sending when the DSP starts its next frame, and the exchange loses
step. A core A log (the 513-word block reported from a STALL PROBE build,
Nov 2026) fits it. What would falsify the window as the whole cause on a
shipping image: a stall there with an entry lateness outside 110 to 190 µs
in the frame log.

## The change

One detour at the frame interrupt's entry `0x4000aad0`. `fg_in` keeps each
entry's lateness against the DSP's frame grid (the previous lateness plus
the interval between entries less a frame, floored at 0, modulo a frame;
DMA timer 3 at 132 MHz). An entry more than 110 and less than 190 µs late
spins until it is 190 µs late, then the stock handler runs. The DSP then
skips one frame, as it does without the guard for an entry that late.
`fg_waits` counts the waits. After the skipped frame the next entry is on
time: a lateness within 20 µs of a whole frame counts as that frame.

Until 13 Nov 2026 (PR #1093 as merged) that reduction was at exactly one
grid frame, the lateness after a skip stayed at 362.7 µs, decayed 0.5 µs a
frame into the window about 0.12 s later, and about 150 on-time entries in
a row waited up to 80 µs each. A never-freezing frame log caught a stall
inside such a run of waits (`octabam`, program-change bursts, 20-channel
capture, 353 s into `kits-identity`); `kits-identity` stalled in 3 of 4
runs on images with that arithmetic. The unit results in this file were
taken with it.

Beside LOAD METER or BOOT TRACE, HOOKS owns the site and calls `fg_in`
before LOAD METER's entry, so LOAD METER's frame time leaves the wait out
and the demand loader's pump runs after it.

With the guard, same unit and day, 20-channel USB capture: 32 first STARTs
and 192 program changes without a stall (16 and 96 as test code inside
LOAD METER's entry, 16 and 96 as this module); every guarded entry was
followed by one skipped frame.

Not measured: what the skipped frame does to audio that is sounding at
that moment; an MKI; a remix other than `octabam`.

## Gate

`tools/verify/verify_frame_guard.py` assembles `guard.s` alone and bridged
and enters it under Unicorn at lists of entry times against a model of the
timer: which entries wait, the lateness at which each leaves, the
prologue's frame and the exit. It does not model the DSP.

On a unit: `tools/hw/ot_stall.py` runs the first-START assay, one trial a
power-cycle; `tools/hw/framelog.patch` is the frame log it reads with
`--framelog` (a test edit to LOAD METER and USB, not for an image that
ships).
