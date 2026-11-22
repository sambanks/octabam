# `cc-feedback` — CC FEEDBACK

The OT transmits a CC for every live knob byte that changes, whatever
changed it, so a controller's encoders (a BCR2000's LED rings) follow the
unit. Stock transmits a page-1 knob's CC on a panel turn only; after a
pattern or part change, a project load, MODE DEFAULTS, an incoming CC or a
page-2 knob turn the controller shows stale values.

`Kind.CF_PATCH`: one DRAM unit (`cc_feedback.s`) and one jmp detour. The
sweep compares the PART's knob bytes with the stock emitter's cache (page
1: the machine's PLAYBACK block `+0x8edaa + t·30 + machine·6` and the
LFO·AMP·FX1·FX2 array `+0x8ee9a + t·24`; page 2: `+0x8f07e`/`+0x8f084 +
t·30`), not the live lane: locks, slides and scenes rewrite the lane every
step and never the Part. Paced: one message per UI tick (120 Hz, `PACE`
in `cc_feedback.s`), so a bank or pattern change with a different Kit
reaches the controller over about three seconds instead of one burst —
on image A2 (4 Oct 2026) the unpaced dump of the new Part locked a
BCR2000 up the moment the bank changed.

## Open

- What rewrote T1's lane bytes 8 and 14 at step rate on a fresh project's
  B1 (4 Oct 2026): locks, or a CC-written lane value against the
  sequencer's refresh from the Part (`0x4000c19c`). The lane is the knob
  store the frame builder copies; the lock arrays are
  `0x80001538`/`0x80001658` (`docs/firmware/MIDI.md` section 3).
- LEVEL (CC 46), AMP VOL as CC 25 outside the AMP page, MUTE/SOLO (49/50)
  and the crossfader (48) are not in the map: their state is not in the
  lane.

## The stock emitter (`0x40033e3c`, disassembled)

`EMIT(track, cc, value)`, stack arguments. Gated on AUDIO CC OUT
(`0x8000004a`) bit 1; bit 0 is INT (the panel crossfader path tests it
before applying the move). Track 8 means the current track. For a track
0..7 the channel is `0x8000003f + track` (−1 = off, returns) and a MIDI
track on the same channel (`0x46c76de0 + 68·i`, byte = ch+1) returns. Then:

| write | address | what |
|---|---|---|
| value byte | `0x46c7bf2c + channel·128 + cc` | the last value queued for that CC |
| bit `cc` | `0x46c7d7d8 + channel·16` (four longs) | the channel's dirty CCs |
| bit `channel` | `0x46c7e0de` | channels with dirty CCs |
| bit 2 | INTFRCH `0xfc048010`, when `0x46c7ca34` is 0 | forces source 34, the soft-timer dispatcher `0x400409f4`, which drains the bitmap to UART0 |

The drainer sends every pending CC of every dirty channel into the UART
ring in one batch, then sets `0x46c7ca34` = 1 and re-arms DTIM2 for that
batch's wire time (`bytes × 0x400a763e[rate]`); the flag clears on a drain
that found nothing. The wire is paced to MIDI bandwidth by stock; a burst
of changes goes out in batches and a value that changes twice inside one
batch is sent once (`docs/firmware/MIDI.md` appendix D).

A repeated CC coalesces in the bitmap. Stock callers: 28 `jsr` sites; the
page-1 knob path at `0x400552f0` (current track, CC `10 + 6·page + slot`,
the clamped value) and the panel crossfader as CC 48 are the two traced.

## What this unit does

`cf_tick` is a jmp detour on the keyrepeat task's loop at `0x4005595c`,
which pends on the UI tick event (`0x46c7e0e2`, signalled by DTIM1's
handler at 120 Hz). Each pass calls `cf_sweep` before the pend: one track
(round robin), its live lane `0x80000810 + track·72` compared byte for
byte against the emitter's cache for the track's channel:

| lane bytes | CC | page |
|---|---|---|
| 0..29 | 16..45 | page 1: PLAYBACK 16-21, AMP 22-27, LFO 28-33, FX1 34-39, FX2 40-45 |
| +0x32..0x37 | 108..111, 14, 15 | FX1 page 2 (CC MAP's numbering) |
| +0x38..0x3d | 102..107 | FX2 page 2 (CC MAP's numbering) |

Page 2 went out as CC 68..73 and 62..67 until 1 Nov 2026. On a MKII
sequencing a Tonverk from the MIDI out (issue #981, measured under the
port on the reporter's project): a project load sent 361 bytes, 22 CCs on
each of channels 1–8, CC 64 = 127 among them, and with AUDIO CC OUT on EXT
every Tonverk note hung after its release; on INT none did. That CC 64 is
read as a held sustain pedal is the reporter's inference, not measured.
The numbers moved with CC MAP's; `verify_ccfeedback` takes them from CC
MAP's manifest, so the sweep sends exactly what CC MAP reads.

A byte that differs goes through `EMIT`, which updates the cache itself.
Stock's knob echo goes through the same cache, so a panel turn is sent
once. The sweep skips when AUDIO CC OUT bit 1 is clear or the track's
channel is off; a channel shared with a MIDI track is refused inside
`EMIT` on every call (42 refused calls per sweep of that track). Every
track is covered every 8 ticks (67 ms). PLAYBACK and AMP page 2 have no
CC numbers and are not sent.

The sweep waits while the engine task runs a command. The engine's queue
is `0x460d17ce` (count +4, event flag +8, waiting TCB +0xc): the kernel's
event wait (`0x40000818`) parks the engine's TCB at +0xc while it is
blocked for a command and the post (`0x40000c3c`) clears it, so a
non-zero word there is "the engine is idle". A project load, a bank or
part change transmits nothing until it has settled, as stock does. This
gate was added after the first port run: 272 UART interrupts inside LOAD
PROJECT re-ordered `sys` against the engine and tripped Octakit's
part-byte lifecycle check (`gk_lifecycle_activation_publication_report_fatal`,
the ATA-latency ordering `tools/emu/README.md` records); the same image
loaded at `--ata-latency 32`, and the `rig` test remix (bottleservice without Octakit) loaded at the
default.

## Wiring a BCR2000

OT MIDI OUT to the BCR's MIDI IN, BCR OUT A to OT MIDI IN. The BCR's
encoders in `absolute` mode take an incoming CC on their channel and move
the LED ring (`tools/hw/bcr2000.py`). Whether the BCR's
mode S-4 merges MIDI IN into OUT A is not checked; if it does, every echo
returns to the OT as a redundant CC write of the same value.
