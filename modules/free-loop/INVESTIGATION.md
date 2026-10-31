# FREE LOOP — firmware investigation (phase 2)

> A record of the firmware investigation, kept as written. LIVE PEDAL and
> `live-djib` are the owner's earlier pedal module and rig remix (not
> published; `verify_live_pedal` was its gate): FREE LOOP grew out of them
> and took over their sites. The OCTABAM numbers are the owner's images.

FREE LOOP replaces LIVE PEDAL in `live-djib`: one pedal per instrument
(pedal 3 guitar T1/T2, pedal 4 synth T3/T4); the first loop, played with
the sequencer stopped, sets the tempo and starts the sequencer; the same
pedal then arms and cuts the overdub on the grid. It keeps LIVE PEDAL's
pattern / bank steps and buffer clear.

Markers: ✅ measured on a unit, 🟡 measured under the ColdFire port only,
❓ read from the code or inferred, not measured.

Image: `live-djib` built in this worktree (base `ae69a3be`), the owner's
1.40C. Port: `out/emu/ot_emu --mkii`, 26 Oct 2026. Probes:
[`probes/probe_stop.py`](probes/probe_stop.py),
[`probes/probe_play.py`](probes/probe_play.py) (run with the worktree root and
an output folder); the tempo and pattern-length runs are the `ot_emu`
command lines quoted below.

## Summary

| # | unknown | answer | marker |
|---|---|---|---|
| 1 | start / stop a MAX take from code, sequencer stopped | start `0x40005178(t, (keys + 0x8000) \| 0x10, 1)` (`0x9010` for INAB AB); stop `0x40005178(t, 0x80, 1)`; D = LIMIT `0x46c7fe24[t]`, written at the stop | 🟡 |
| 2 | clean tempo write | `0x4009c708(tempo24)`: clamp 720..7200, pattern or project tempo, `0x80001814/18`, engine message | 🟡 project tempo; ❓ pattern tempo, MIDI clock out |
| 3 | END per track | the playback end is copied at every trig from the recorder slot's trim end, `0x100b14f0 + 0x448 × (128 + r) + 0x130`, into the voice (`0x800049d8 + 0xa8 t`, +0x2c end, +0x64 END) | 🟡 T1 / R1 |
| 4 | pattern length / scale, RLEN | length byte = record − 1, scale = record + 0; the sequencer follows a written length at once; RLEN need not be written (RLEN PLEN) | 🟡 length; ❓ scale |
| 5 | clear R1 | stock CLEAR SLOT `0x4002557c(128 + r)` from the UI task | ✅ (LIVE PEDAL, OCTABAM4) |
| 6 | a pattern change that has landed | the playing bank / pattern `0x800065bd/be`, polled from the UI task's tick | ✅ bank (LIVE PEDAL, OCTABAM7); 🟡 pattern (`verify_live_pedal` "land") |

## 1. Starting and stopping a free take 🟡

The REC keys' running-recorder branch (`0x40083544`, read here) decodes the
recorder's TRIG (Part rec setup byte +1, `mvsb %a0@(1)` at `0x40083598`):

| TRIG | a press on a running recorder |
|---|---|
| 0 ONE | posts start word \| 0x10 (`0x1010`): a new pass, LIMIT := last pass length |
| 1 ONE2 | `0x40005178(t, 0x80, 1)` (`0x400835f8..0x40083602`): stop |
| 2 HOLD | key release stops |

Measured (`probe_stop.py`: fresh project, T1 FLEX on R1, rec setup INAB AB,
RLEN MAX, TRIG ONE2, sequencer stopped, `--audio-in tones`):

- TRACK 1 + REC AB at 2000 ms: mailbox `0x46c7e9fa[0]` ← `0x9010` at
  `0x400051f4`, consumed one frame later (`0x4000c8c2`); LIMIT ← 0 at
  `0x400069d6` (the MAX arm).
- The write position `0x46c802c8` (T1; ❓ `+ 4 t` per track) rises by 16
  each frame (`0x400078c0`): 64,288 at 1.46 s.
- Again at 4000 ms: mailbox ← `0x80`; LIMIT ← **88,208** at `0x40005e8e`,
  and the position ends at the same value. 2000 ms between presses is
  88,200 samples: D is read off LIMIT to within the key timing (8 samples).
- With TRIG ONE (the image's default here) the second press posts `0x1010`
  and the recorder keeps running (voice byte 1 = `0xff` afterwards): a
  different pass, not a stop. FREE LOOP therefore calls `0x40005178`
  itself with `0x80`, whatever TRIG says.

Not yet measured: the call made from our code (the probes used the keys,
which reach the same `0x40005178` call); per-track addresses beyond T1.

## 2. Writing the tempo 🟡 / ❓

`0x4009c708(tempo24)` (read here):

```
clamp tempo24 to 720..7200
sr := 0x2700
if [0x80000024] (PATTERN TEMPO) and 0x40033968() == 0:      ; getter of 0x460d1aec ❓
    pattern record (bank blob [0x46c82456] + pattern × 0x8ed8 + 0x8e58) := tempo24, its SRAM mirror,
    dirty flags, jsr 0x40027e00
else:
    0x80000020 (project TEMPOx24) := tempo24, CS1 mirror 0x100b1480
0x80001814 := tempo24 ; 0x80001818 := tempo24
sr restored ; post 0x400a74cc to the engine queue 0x460d17ae
```

The project loader calls it with `TEMPOx24` (`STORAGE.md`); the per-frame
latch copies `0x80001814` to `0x8000181c` (`RECORDER.md` section 1). `0x4009c7c4`
is the (BPM, tenths) form.

Measured: `--step -:call:0x4009c708,2900` → `0x80000020`,
`0x80001814`, `0x80001818`, `0x8000181c` all `0xb54` (120.83 BPM) 100
frames later. FREE LOOP writes tempo24 directly, so the tenths rounding
of the brief becomes: the smallest tempo24 whose firmware loop length
`L(tempo24)` is ≤ D (section 4).

Open: the pattern-tempo branch and `0x460d1aec`; the outgoing MIDI clock
at the new tempo (`--midi-out`, phase 4); which task may call it (stock
calls it from the UI and the loader; FREE LOOP will call it from the UI
task).

## 3. The end of the loop 🟡

At the stop (`probe_play.py`, same project plus a trig on step 1 of T1):

- `0x400043ba..be` writes the recorder slot's trim start 0 and end
  `0x15890` (88,208) into its settings record
  (`0x100b14f0 + 0x448 × 128 = 0x100d38f0`, +0x12c / +0x130; the layout
  of `STORAGE.md`'s sanitiser, `a4 + 300 + 20 × (slice + 1)`), then
  `0x40099074..0x4009952c` (the sanitiser) completes the record.
- On PLAY, at every trig of T1: voice start `0x4000f790/94` copies start /
  end into the voice (`0x80004a00/04` = voice +0x28/+0x2c) and
  `0x4000f8ac` writes END `0x80004a3c` (voice +0x64) = 88,208. So
  `RECORDER.md` section 2a's END is the playback voice's copy, refreshed per trig.

Consequence: to cut the loop to L ≤ D, FREE LOOP writes the slot's trim
end (+0x130) after the stop and before the first trig; it is re-read at
every trig. Open: whether the sanitiser rewrites it later (bank load,
PERSISTENT BUFFERS save); the fade at the cut (phase 4, by ear).

## 4. Pattern length and scale 🟡 / ❓

Pattern record (`modules/rlen-plen`): `0x400eb034 + p × 0x8ed8 + b ×
0x9b340`. Read on A1 of a fresh project: `0x400eb033` = 16 (length),
`0x400eb034` = 2 (scale 1X; ticks per step `3 4 6 8 12 24 48` for
2X … 1/8X).

Measured: `--step -:poke:0x400eb033=32` with the transport running: the
per-track step counters `0x800064d0 + t` and `0x800064e0 + t`, and the
master `0x800065b3/b5`, run to 27 then wrap to 0 (snapshots every 2000
frames), where 16 wraps at 15. The sequencer reads the length live.

Not measured: a scale write; whether a length / scale written outside the
editor survives a bank save and reload (the record is the bank's own
data, ❓ saved as is).

**RLEN is not written.** The template sets every recorder's RLEN to PLEN
(RLEN PLEN, raw 65): the overdub length follows the pattern's length ×
scale through the firmware's converter, `L = (((steps × 31,752,000) × Q >>
31) + 1) >> 1`. The Part validator's RLEN clamp (`0x40002c72/78`) is
RLEN PLEN's and is left alone.

## 5. Clearing a buffer ✅

Stock CLEAR SLOT `0x4002557c(128 + r)` from the UI task's toast countdown
tick (`0x40056c28`), with "RECORDING CLEARED!": LIVE PEDAL, flashed on
OCTABAM4. Reused as is.

## 6. A pattern change that has landed ✅ / 🟡

`0x800065bd/be` is the playing bank / pattern, `0x800065bf/c0` the cue.
LIVE PEDAL polls the bank from the UI tick and clears on a change
(OCTABAM7, any source: pedal, Program Change, A16 → B1). The same poll on
the pattern byte applies the per-pattern ARM / OFF / KEEP mode, with no
new hook: KITS already owns the scheduling sites `0x400a0570` /
`0x4009c634`. Measured for the pattern only by `verify_live_pedal`'s
"land" scenario (the playing pattern reads A2 once the cue lands).

## Timing: the free take's end to the first step ❓

The brief wants about one frame (16 samples) between the end of the take
and step 1. Two constraints from what is above:

- The stop is consumed one frame after the post; LIMIT and the slot's end
  are written then.
- The UI task ticks at 1/60 s (about 46 frames). Tempo, slot end and
  pattern length written from there would start the loop up to ~17 ms
  late.

Proposal for phase 3, to be measured in phase 4: on the pedal press (MIDI
thread), take D from the write position `0x46c802c8[t]` directly, post the
stop, and start the transport with the stock MIDI Start handler
`0x4000a274` as LIVE PEDAL's PLAY does (on a unit, OCTABAM4); compute and
write tempo, slot end and pattern length before that start, in the same
call. Whether `0x4009c708` may run on the MIDI thread is open (it masks
interrupts itself and posts to the engine queue).

## Slave

CLOCK RECEIVE is `0x80000028` bit 0 (`MIDI.md`). FREE LOOP refuses a free
take while it is set, with a toast.

## Hooks FREE LOOP needs (all owned by LIVE PEDAL today)

| site | stock bytes | use |
|---|---|---|
| `0x4000e79c` CC handler entry | `4e56ffd4 48d73cfc` | the pedal CCs |
| `0x4009d9a4` recorder-trig test | `4a83 676e 243c0000091a` | overdub on / off per track |
| `0x40006d1a` recorder setup pointer | `d9fc80000cf4` | (LIVE PEDAL's player setup; to decide) |
| `0x40056c28` UI toast countdown | `2039460d1e6c` | clears, toasts, pattern-mode poll |

The status-icon hook `0x4004bee2` (REC THRESHOLD, REC_TRIG_MUTE) is free in
`live-djib` for the blink while armed.

## Phase 4 findings (port, 26 Oct 2026)

**A free take follows the track's RLEN.** On the template (RLEN PLEN) the
take posted with `0xd010` stopped by itself after one pattern length
(LIMIT 88,545 for a 16-step pattern at 120). The recorder routine reads
RLEN through a4 = the published setup (`0x40006d1a`, LIVE PEDAL's site);
FREE LOOP points it at a copy with RLEN MAX (64) while the track's free
take runs. With it: LIMIT 353,080 for 8 s of take plus FOUT. 🟡

**The take's length is the write position at the press**, not LIMIT:
LIMIT adds the fade-out (FOUT 0.063 = 1/16 step, ~345 samples at 120)
appended after the stop. 🟡

**The slot's end is rewritten until the recorder is done.**
`0x400043ba..0x400043ea` (a function; read here) sets the slot's start
(+0x12c), end (+0x130) and loop point (+0x134) from the recorded length,
clears the valid byte (+0x128), and stamps the slot's tempo (+0x114) from
the latched tempo `0x8000181c` and +0x118 = −[0x80001820]. Watched: it runs
every frame through the fade-out, then the sanitiser `0x400994b4` writes the
end once more; a single write of L before that is lost. FREE LOOP writes L
from the UI tick until it has held four ticks. Because the tempo is set
before the fade-out ends, the slot's tempo stamp is the new tempo (no
time-stretch by old / new): ❓ to confirm with a take far from 120 BPM. 🟡

**Stock's tempo / bars arithmetic** (read here), used by the slot
sanitiser `0x40098f50..0x4009908c` (+0x11c = LOOP_BARS × 100):

```
bars100 = (length × tempo24 + 1,270,080) / 2,540,160      0x40020a24 (19845 × 128 = 2,540,160)
tempo24 = (2 × 2,540,160 × bars100 / length + 1) / 2      0x40020a94 (64-bit 0x40021a4c / 0x40021ae8)
```

2,540,160 × 100 = 96 ticks × 2,646,000: one 4/4 bar in RLEN PLEN's units.
The PICKUP resume `0x40005214` sets the project tempo from the slot's +0x114
(`jsr 0x4009c708` at `0x4000527e`) and the loop length `0x8000186a`; the
code at `0x40005bb4` (21,168,000) is the external MIDI clock's tempo
estimate (24 per beat, clamp 600..7320), not a loop's.

## UNDO: the slot a trig plays, a second recorder (port, 27 Oct 2026) 🟡

**The slot a trig plays is the live lane's byte 31.** The trig dispatch
`0x4000d492..0x4000d49c` (an indirect `jsr %a0@` through the per-machine
handler table, MUTE MODES' `dt_trig` site) passes the byte at
`0x8000082f + 72 t` (the live lane `0x80000810 + 72 t`, lock slot 31: the
sample lock) to `0x4000f450(track, slot)`, which takes the slot's settings
`0x100b14f0 + 0x448 slot` into the voice (+8). Measured with T1 FLEX on R1
after a free take: poking the Part's Flex byte (`DB + 0x8ed80 + 0x2cb`, and
its CS1 copy) at 12 s changed nothing at T1's trig at 18 s (voice +8 still
slot 128); poking the engine's DSP halfword copy `0x80000a8e` neither; poking
the lane byte to `0x84` made the 18 s trig take slot 132 (R5). The lane is
written from the Part by the Part apply (`0x400092c2`) and at the
transport's start (`0x4000c05c`, `0x4000c22a`), and by a sample lock
(`0x4000c5ac..`); nothing else wrote it from 12 s to 19.5 s. FREE LOOP
writes both: the Part bytes (four Parts, RAM and CS1) so an apply keeps the
choice, the lane so the next trig takes it.

**A pass into another recorder.** The record builder `0x4009d1e8(track,
...)` runs for T1..T8 in order on each step (the recorder-trig test
`0x4009d9a4` is per track); a trig word given to T5's call on the step T1
decides lands in `0x46c7a6c0[4]` and starts T5's recorder on that step
(measured: T5's recorder running at 21 s, T1's not). The recorder routine's
setup pointer (`0x40006d1a`, `a4 = 0x80000cf4 + 12 t + 96 page`) lent to
T1's makes the RLEN PLEN cave compute T1's length (5,514 cave entries with
`a4 = 0x80000cf4`, none on the MAX branch), but the recording did not end:
LIMIT[4] stayed 0 and the write position ran on to 485,115 (11 s) where
T1's own PLEN pass ended at 353,022 (L + the fade-out) and posted LIMIT.
Stock reads part of the setup from the Part itself (the arm at
`0x40005dde` reads LOOP from `DB + 0x8f382 + part·6322 + 12 t + 5`), and T5's
Part setup said RLEN MAX. FREE LOOP therefore keeps the UNDO buffer's
track's Part setup equal to its loop track's (four Parts, RAM and CS1), and
the template writes T5-T8's setups as T1-T4's.
