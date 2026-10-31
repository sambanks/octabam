# HOOKS

Platform module: the one owner of a stock site that two selected modules both
claim. Nobody selects it; the registry appends it to a remix whenever one of
its bridges has two participants in it, as it appends MEMORY. A remix with one
participant, or none, gets nothing from HOOKS: that module's own claim stands
and its bytes do not move, so a module proven alone on a unit stays exactly what
was proven. A submodule participant's source is not edited; an in-tree
participant builds a bridged form under a flag and is byte-identical alone.

The design, and the conflicts it is meant to remove next:
[docs/proposals/SHARED_HOOKS.md](../../docs/proposals/SHARED_HOOKS.md).

## Bridges

| bridge | site | participants | what HOOKS does |
|---|---|---|---|
| track_key | the [TRACK]-held key layer's keys field `0x400d164e` (stock `0x400d1594`, six 26-byte records) | REC_TRIG_MUTE (replaces YES/NO), MORPH (adds UP/DOWN) | points the field at one table: stock's records with each participant's replacements, then each participant's added keys |
| status_icon | the track status icon renderer's state-cache load `0x4004bee2` | REC_TRIG_MUTE (`rtm_glyph`), REC THRESHOLD (`blink_gate`) | one `jsr` calls `rtm_glyph`, then `blink_gate`: the mute fold first, so the blink bit survives it |
| frame_tail | the frame interrupt's epilogue `0x4000d9a6` | LOAD METER (`lm_out`), CF METER (`m_tail`), BOOT TRACE (`tr_frame_end`) | calls each, built to return (`HK_FRAME_TAIL`), then replays the epilogue once |
| frame_entry | the frame interrupt's entry `0x4000aad0` | BOOT TRACE (`tr_frame`), LOAD METER (`lm_in`) | replays the prologue once, then calls each, built to enter after it (`HK_FRAME_ENTRY`): LOAD METER's stamp last, so its duration excludes the note |
| chrom_pitch | the CHROMATIC key handler's key → pitch `0x4004fc58` | OCTA303 (`o3_chrom`), SCALE QUANTIZER (`qz_chrom`) | no code of its own: OCTA303's detour stays and, built with `HK_CHROM_PITCH`, hands every non-303 track to `qz_chrom`; SCALE QUANTIZER's detour is overridden |
| chromatic | the CHROMATIC octave keys `0x40045918`, key index `0x40050254`, keyboard picture `0x40044968` | BLACKPYRAMIDS_303, SCALE QUANTIZER | asks `ot_track_is(the UI track)`: a BLACKPYRAMIDS track its own handler or full-keyboard branch; any other track `ot_chrom_sanitize`, then SCALE QUANTIZER's handler |
| boot | the boot's `jsr 0x4000f938` at `0x40000512` | BOOT TRACE (`tr_dsp_done`), STORE (`store_part_resident_activate`) | calls BOOT TRACE's note 3 (`HK_BOOT`: it returns), then jumps to STORE's routine, which tail-jumps to the stock call |
| machine_rows | the track's machine list and SRC SETUP: the name formatter `0x400334d8`, the name tables, the row highlights, the list's opens, its commits, the SETUP editor and drawer, the Part validator `0x40002318`, the tick that publishes a machine's record, the FLEX kind entry `0x400d6438`; the lists' row counts and bounds | ANALOG BD (row 5), OCTA303 (row 6) | ANALOG BD's hooks take every shared site; built with `HK_MACHINE_ROWS`, each hands a row not its own to OCTA303's routine for the same hook, and OCTA303 is built with its row as 6. HOOKS pokes the lists to seven rows (the counts, SRC SETUP's name bound, the commit's persist bound, and the cursor clamp in the list's five key handlers) and takes the drawer's two row tests, so the list scrolls |

A bridge takes each participant's claim at the site by `schema.Override`
(`ledger.py` and `build_bus.py` skip the overridden detour or symbol ref).
A participant whose own detour replays stock instructions and never returns
(the frame interrupt and boot bridges) reads a flag from its `remix.inc`
(`tools/remix/hooks_flags.py`): 1 only when its bridge is on, and then it
returns instead; alone, the flag is 0 and its bytes are the ones proven.
STORE's routine already ends in the stock call, so it is called
last and needs no flag: its submodule source is not edited.
REC_TRIG_MUTE's own refs into stock's [TRACK] table are still written when
track_key is bridged; nothing reads that table once the field is repointed.

A selection with a bridged pair and no HOOKS is refused by the ledger, by
name: MORPH's and REC_TRIG_MUTE's claims do not overlap, so without the
rule the pair would build and REC_TRIG_MUTE's keys would silently stop.

## Measured

- `tools/verify/verify_hooks.py`: the selection rules; under Unicorn, the
  three participants' own sources linked with `bridge.s`, `hk_status_icon`
  over 128 states (track, state, mute, arm, TRIG, blink phase) against the
  model and against the two routines called in turn, the opposite order
  losing the blink; the [TRACK]-layer table decoded; the frame interrupt's
  entry and epilogue chains (one prologue, one epilogue, each participant's
  work done, registers and stack as found) and the boot chain (the stock
  call made once, STORE's targets set). With a built image of
  [`test/hooks`](../../remixes/test/hooks/README.md) or
  [`test/hooks-core`](../../remixes/test/hooks-core/README.md): stock's six
  records are the ones HOOKS copies, every bridged site holds HOOKS's write,
  and each chain calls its participants at their linked addresses.
- Each participant alone, and `octabam`, `stock-meter-a`, `cfmeter`,
  `remix-switch-trace`, `morph`, `rec-threshold`, `octa303`, `blackpyramids-303`:
  image byte-identical to the branch's base (28 Oct 2026).
- CHROMATIC: under Unicorn, 40 key → pitch cases (a 303 track as OCTA303 alone,
  every other track, scale off and on, as `qz_chrom`) and 48 octave/index/picture
  cases (a BLACKPYRAMIDS track as its own handlers, every other as sanitize then
  SCALE QUANTIZER's); in [`test/hooks-chrom-303`](../../remixes/test/hooks-chrom-303/README.md)
  and [`test/hooks-chrom-bp`](../../remixes/test/hooks-chrom-bp/README.md). One
  difference from BLACKPYRAMIDS alone, by design: FUNC + LEFT/RIGHT on another track
  with an octave of 2 or 3 left by a BLACKPYRAMIDS track lands on 1, not 0.
  BLACKPYRAMIDS's manifest's conflict with SCALE QUANTIZER named `0x4000e746`, which
  SCALE QUANTIZER no longer claims; its wrapper drops that one conflict.
- The boot bridge: under Unicorn, and in [`test/hooks-boot`](../../remixes/test/hooks-boot/README.md)
  (BOOT TRACE beside STORE and MIDI LOOPBACK).
- Machine rows: under Unicorn, each track's row type (static, FLEX, ANALOG BD,
  OCTA-303), the drawer's two stubs over both top rows and every screen row
  (60 cases), ANALOG BD's name and main-commit hooks reaching OCTA303's (row 6
  signs `TB 1`, row 5 `AB 1`, any other row neither, in the Part and its shadow).
  Under the ColdFire port, in [`test/hooks-machines`](../../remixes/test/hooks-machines/README.md)
  with a fresh project: both machines' own UI gates pass on the one image
  (`verify_analog_bassdrum_ui`, `verify_octa303_ui`: OCTA-303's record as UI type 6);
  the list scrolls to OCTA-303 and back, YES on either row commits that machine,
  and reopening on an OCTA-303 track opens scrolled with its row boxed. ANALOG BD
  and OCTA303 alone are byte-identical to the base (28 Oct 2026).
- Not flashed. Apart from the machine rows, not run under the ColdFire port with a project.

## Adding a bridge

A bridge is a participant list in `manifest.py`, a branch of `select()` and
its code in `bridge.s`. Each participant's routine is called as its own
detour would be; the order is the bridge's, and `verify_hooks` should show
why it is that order.
