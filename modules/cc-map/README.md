# `cc-map` — CC MAP

Maps MIDI CC numbers that stock ignores onto parameters stock CC cannot
reach. Each **block** is a range of CC numbers written to one page's slots.
Stock incoming CC reaches page 1 only (CC 16–45): the handler admits
`cc−16 < 30` and derives `slot = flat % 6` (`docs/firmware/MIDI.md` section 2).

| block | target |
|---|---|
| CC 102–107 | FX2 page 2, slots 6–11 |
| CC 108–111, 14, 15 | FX1 page 2, slots 6–11 |

The blocks were CC 62–67 and 68–73 until 1 Nov 2026 (issue #981). That
range holds the pedal CCs, 64 sustain to 69 hold 2. A keyboard's sustain
pedal on a track's channel wrote an FX2 page-2 knob, and CC FEEDBACK's
sweep at every project load sent CC 64 = 127 to each synth on channels
1–8, which held its notes. Every number now is undefined in the MIDI
standard. `FX2_CCS` / `FX1_CCS` in the manifest are the numbers;
`tools/remix/midi_cc.py` refuses a stateful CC (pedals, bank select, data
entry, RPN/NRPN, channel mode) at import.

`Kind.CF_PATCH`: one cave (`cc_map.s`, linked where the ColdFire free region
places it) and one poke. Named CC PAGE 2 (`modules/ccpage2`) until
25 Sep 2026. Flash notes and commits before that date use the old name.

## Open

- The new numbers on a unit: CC 102 and CC 108 moving their knobs, and a
  sustain pedal (CC 64) on a track's channel moving nothing.

- FX2 page 2 of any FX2 effect other than BusDelay/BusVerb: the cave skips
  those tracks.
- MIDI CC through the SCENES KITS chain on hardware (under the port CC 68,
  the old FX1 number, reached page 2 through the chain, above).
- An FX1 page-2 edit reaching the DSP on a THRU track, on hardware
  (measured under the port: `docs/contributing/FAILURE_MODES.md`, image 24).

## Hook

The MIDI dispatch table's CC entry `0x400d64a0` (`0x400d6474[0xB]`) is
repointed from the stock handler `0x4000e79c` to the cave. A CC outside
every block tail-calls `CC_NEXT` with the message pointer intact. The build
defines `CC_NEXT`: the stock handler. (Until 6 Oct 2026 the SCENES KITS
bridge chained Octakit's handler in between.)

## What a CC in a block does

The cave rebuilds the channel→track map (`0x40001854`, as stock does on
every CC), returns if AUDIO CC IN (`0x80000049`) is zero, and writes to
every audio track whose trig channel matches the message's channel. The
part is byte `0x80000003`, the one the page-2 editors use.

Each block makes the stores of that page's firmware editor. DB is the long at
`0x46c82456`. Store addresses are `+ part*6322 + track*30 + slot2`, and lane
addresses are `0x80000810 + track*72 + lane + slot2`.

| block | editor | written when | clamp | Part | shadow | lane |
|---|---|---|---|---|---|---|
| 102–107 | FX2 page 2, `0x4003aab2` | the Part's FX2 id is BusDelay (6) or BusVerb (7); other ids skip the track | count tables in the cave (`VCOUNT`/`DCOUNT`) | DB `+0x8f084` | `0x100a51d2` | `+0x38` |
| 108–111, 14, 15 | FX1 page 2, `0x4003abe4` | the Part's FX1 id is not 0 (NONE) | the FX1 descriptor's min/count (`0x400d5f58[id]`, `+0x6a`/`+0x9a`) | DB `+0x8f07e` | `0x100a51cc` | `+0x32` |

Both blocks then set the editor's four dirty flags: `DB+0x95048 |= 1<<part`,
`0x100b145e |= 1<<part`, `DB+0x9b332 = 1`, `0x100f8598 = 1`. The cave leaves
out the editors' redraw marker and refresher call. Without the dirty flags
the Part store is inert. The page-2 path posts nothing to the DSP. The
per-frame copier `0x4000cae8` ships the live lane every frame.

Selects are clamped to their count. A stored value past a select's count
is used as an index and stalls the sequencer (docs/contributing/TRAPS.md, "A part saved
under an older slot layout").

After each write the cave calls `CC_MODEDEF2` (FX2) or `CC_MODEDEF1` (FX1)
with a2 = slot2, d2 = the clamped value, d4 = track, d5 = part. When MODE
DEFAULTS is in the image these resolve to its entries, so a MODE sent over
CC re-defaults the knobs around it. Otherwise they resolve to a stock `rts`
(`0x40027e1a`).

## CC numbers

Stock audio-track CC map (handler `0x4000e79c`, `docs/firmware/MIDI.md`
section 1): 7, 8, 16–61 and 112–127 are used. 0–6, 9–15 and 62–111 fall through
to the handler's `rts`.

| CC | holder |
|---|---|
| 102–107 | this module, FX2 page 2 |
| 108–111, 14, 15 | this module, FX1 page 2 |
| 80 | REC TRIG MUTE |
| 83–89 (PROG CH channel), 90–93 | FREE LOOP |
| 0, 6, 32, 38, 64–69, 96–101, 120–127 | never: they hold state on the receiving synth (`tools/remix/midi_cc.py`) |
| 3, 9 | free, undefined in the MIDI standard |
| 70–79, 81, 82 | free, but sound controllers and general-purpose CCs that synths map |
| 1, 2, 4, 5, 10, 11, 84 | free, but keyboards send them unasked (mod wheel, breath, foot, portamento time, pan, expression, portamento control) |

A synth may map any CC to a parameter of its own, undefined ones too.
CC FEEDBACK sends these numbers on every audio track's channel, so an
external synth on one of those channels hears them; keeping it on a
channel of its own is the user's part.

## Adding a block

1. Take CC numbers from the table above, outside `midi_cc.STATEFUL`, and
   declare them in the manifest beside `FX2_CCS` / `FX1_CCS` through
   `refuse_stateful`.
2. Trace the target page's editor: its Part, shadow and lane stores, its
   clamp, and its dirty flags. `docs/firmware/MIDI.md` section 6 has the table for
   the three page-2 editors traced so far (PLAYBACK `0x4003a474`, FX2, FX1).
3. Extend the decode at `CAVE` (today `cc−102 ≤ 9`, then `cc−14 ≤ 1`) to
   give the new block its slot index, and add a write path for it.
4. Regenerate the oracle (`manifest.CODE`), and extend
   `tools/verify/verify_cc_map.py` to prove the new stores on all eight
   tracks against the editor.

## Oracle

`manifest.CODE` is the hand-assembled form of the cave. `legacy_bytes`
patches in the count-table addresses. It is the `CavePatch.reference` that
the linked source is compared against, wherever the source is linked. The
comparison is skipped when `CC_MODEDEF*` resolve to MODE DEFAULTS, since
that changes the bytes.

`VERB_COUNTS` / `DLY_COUNTS` in the manifest and `VCOUNT` / `DCOUNT` in the
cave must match the busverb and busdelay page-2 counts.
