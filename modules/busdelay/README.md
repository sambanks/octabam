# `busdelay` — DELAY SERVER

A multi-mode delay: CLEAN, GRAIN (a pitched granular cloud over the delay
lines: four grain readers per line, one continuous pitch) and
REVERSE, with a tape wow on the loop tap in every mode. Hosted
on payload B (core 1), which serves tracks 1–4. Stage 1 of the one aux bus:
its output goes on to BusVerb; the repeats come out on the host track.

## Knobs

| | CLEAN | GRAIN | REVERSE |
|---|---|---|---|
| page 1: DEL · REV · FDBK · TONE · PING · WET | the same everywhere | | PING reads `---` (the mode pins it to 0) |
| MODE (p6) | CLEAN | GRAIN | REVRS |
| SCTR (p7) | `---` | how far apart the grains read | `---` |
| DENS ⌐(p8) | `---` | density, level-flat | `---` |
| SIZE (p9) | `---` | GLEN: grain length 46 / 93 / 23 ms, XTRM 186 ms | SLEN: segment; XTRM = 371 ms |
| PTCH ⌐(p10) | `---` | ±2 oct, 64 = unison; a held MIDI note overrides | `---` |
| TIME (p11) | delay time, a free dial that sticky-snaps to tempo divisions | the same | the same |

Each mode's `ModeView` re-defaults the knobs and names every knob the mode
never reads `---` (20 Sep 2026, every effect). PING 0 by default: an aux
delay sits still; the bounce is the knob's. DEL (p0) is the host's own dry
send into the delay; REV (p1) its dry send into the reverb's REV
accumulator (26 Sep 2026, SEND's recipe: ramped per sample, counted as a
REV client only while nonzero). On the host page these two are the only
knobs drawn (the remix's `host_slots`); the rest are the TEMPO window's.
TIME moved from p1 to p11 the same day, and the tape wow that sat on p11
(20 Sep 2026, in the freeze's slot) went: at WOW 0 it added exactly 0 to
the lag, so every render at WOW 0 is unchanged (verify-bus). The freeze
hold is gone.
In REVERSE LineL alone is the 32K mono ring (the R line is not read or
written; XTRM = 16,384 samples = 371 ms, the mode's default), PING is forced
off and the output is mono to both channels.

## Open

- REVERSE's segment ceiling is 371 ms (its 32K ring is LineL); a 741 ms
  segment would need both lines as one ring, which they are not (LineR is
  in the private region).
- Pitch accuracy below −1.5 octaves: finder or engine.
- The delay's wet is ~4 dB quieter than the reverb's at equal send.

## Memory: two 32K lines, 741 ms

Since 15 Sep 2026 each line is 32,768 words: LineL is core 1's whole
shared half (`Y:0x38000–0x3FFFF`), LineR the core's private FX2 buffer
region (`Y:0x4000–0xBFFF`) — the region BusVerb's tank owns on core 0 and
nothing writes on core 1 (measured under the port: OCTABAM89 C02, 900
frames, every DSP write per 256-word region on both cores; core 1 wrote
`Y:0x0000–0x07ff`, `0x0900–0x09ff`, `0x36000–0x361ff` and its shared half,
nothing in `0x1000–0xBFFF`). Stock's core 1 → core 0 mailbox was the first
16 words of LineL (`X:0x38000–0x3800F`, rewritten by stock every frame, so
16 samples were wrong once per ring pass); every build moves it to
`X:0x37F00–0x37F0F` (`docs/firmware/DSP.md`, section 5). TIME is 64 + knob·256 samples, 1.5–739 ms;
the sticky snap knows twelve divisions, 1/32T … 1/4. — at 121 BPM 1/4 (496
ms) and 1/2T (661 ms) hold, 1/4. (744 ms) from 122 BPM, 1/2 never below
162. REVERSE's mono ring is LineL's 32K, unchanged. LineR's pointer is
base-relative (`y:(r2+n2)`): the private base is only 16K-aligned, so an
absolute pointer cannot be masked — the first build wrote every other
sample 16K away. The DEV hatch (payload A, beside the reverb's tank) keeps
two 16K lines in the shared half; `tools/remix/geom.py` selects the
`; @B` / `; @DEV` lines, and the two geometries render bit-identically at
any TIME both can hold (`verify_two_core`). The ledger refuses a second
owner of the private region on the same payload (`Claims.owns_fx2_buffers`)
and anything else declared in LineL's half (`Claims.dsp_ranges`,
`Y:0x38000–0x3FFFF`); `verify_set` holds the port's shared-window write
census to it.

Stored TIME bytes from before (64 + knob·128) now mean twice the time:
`ot_project.py stamp-slot <project> busdelay 1 20` puts every part's T1 at
the old default's 118 ms.

## TIME: snap and glide

TIME is a free dial with a sticky snap: near a division it snaps, holds that
division through tempo changes, and lets go when the knob moves. The tempo
is stock's record word (tempo24 at `r6+$13`, halfword 31 of every track's
record); the MIDI-clock period is derived per block on the DSP (24-step
`div`, `y:$090d`). The held MIDI note arrives from the
[`tempo-sync`](../tempo-sync/) note cave at `r6+$1` bits 8-15; the panel
label comes from its formatter cave. BusDelay latches the note in
`y:>$090a` (HOLD: the last note sticks after note-off; a never-received
note leaves the PTCH knob in force). In GRAIN the note drives the
continuous pitch, `2^((note−84)/12)`, ±24 semitones.
`tools/verify/verify_midi.py` checks the note against the PTCH knob path
(bit-identical at unison, spectral elsewhere); `DNOTE=n` is the local
override. On the unit: +12/+6/0/−5/−12 within 1/4 semitone.

TIME glides toward the knob (1/1024 per block), the glided value ramps
across each block a sixteenth of the step per sample (the whole step at the
block edge was a click per block for the ~1 s a big move glides, in every
mode; measured and fixed 20 Sep 2026, `tools/harness/glide_census.py`),
and the loop tap reads between samples at the ramp's fraction (the integer
read since the wow went skipped a sample at every integer crossing -- a
click per crossing, recirculating). REVERSE's lag floor and GRAIN's read
base follow the ramp per sample. The step is never smaller than 1/16
sample per block toward the target and never past it, so the state lands
exactly and the fraction is 0 at rest (a standing fraction is a two-sample
average on every pass, which dulled the repeats after a TIME increase in
image 33; images 34-39 snapped from 4 samples out instead). FDBK, TONE,
PING and WET move an eighth of the way to their knob per block, and the
loop steps FDBK, TONE and PING toward that per sample, 1/16 of the gap
(26 Sep 2026; GRAIN's makeup and read step the same way, and the host's
DEL and REV sends 1/64 per sample, `make verify-knobs`). All of it
runs on the first call of a block only (21 Sep 2026): a trig splits the
block into two dispatcher calls, and a glide that ran on both restarted
the ramp at the trig -- a click at every trig while TIME moved. The glide
state is guarded against boot garbage (negative or past the line: start
at the target).

## T1's key level

29 Sep 2026: every call publishes the peak |mono in| of
the block so far to `y:$990` (zeroed on the block's first call, held in raw
`$79`) and increments a counter at `y:$991`. Character reads them when its
KEY is T1. The host's own output is bit-identical with the publish
(`verify_char_key`, and a CLEAN / GRAIN / REVERSE render against the build
before it); cost 24 words, 6 cycles per sample by the pricer (1,001 ->
1,007).

## Local rendering

`dsp_host` renders payload B only under `rig_render.py` (both cores); the
DEV hatch (`make render-delay`) places the delay out of region in payload A.
