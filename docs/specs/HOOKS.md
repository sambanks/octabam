# HOOKS: bridges between modules that share a stock site

The contract for the bridges HOOKS owns and for adding one. Nobody selects HOOKS; the registry appends it when a remix carries two participants of one bridge.
What was measured is in the [HOOKS module](../../modules/hooks/README.md). Which of STORE, EVENTS and HOOKS fits a site:
[SHARED_SITES.md](SHARED_SITES.md).

## Bridges

| bridge | site | participants | what HOOKS does |
|---|---|---|---|
| track_key | the [TRACK]-held key layer's keys field `0x400d164e` (stock `0x400d1594`, six 26-byte records) | MORPH (adds UP/DOWN); REC_TRIG_MUTE until its pin 553d8d2 (replaced YES/NO) | points the field at one table: stock's records with each participant's replacements, then each participant's added keys |
| status_icon | the track status icon renderer's state-cache load `0x4004bee2` | REC THRESHOLD (`blink_gate`), FREE LOOP (`fl_glyph`); REC_TRIG_MUTE until its pin 553d8d2 (`rtm_glyph`: its mute dots are now beside the tab's machine letter, its own site `0x40040146`) | one `jsr` calls `blink_gate`, then `fl_glyph`: FREE LOOP's ring or dot last, on the tracks it manages |
| rec_gate | the step handler's recorder-trig test `0x4009d9a4` | FREE LOOP (`fl_gate_stub`), REC_TRIG_MUTE (`rtm_gate`) | no code of its own: FREE LOOP's detour stays and, assembled with `HK_REC_GATE`, hands on to `rtm_gate` (pinned, last) where it replayed stock: a trig fires only when both let it |
| ui_tick | the UI task's 1/60 s tick `0x40056c28` (the toast countdown's read) | FREE LOOP (`fl_ui_stub`), RELOAD_FROM_PROJECT (`rl_uitick`) | no code of its own: FREE LOOP's detour stays and, assembled with `HK_UI_TICK`, jumps to `rl_uitick` (pinned, last) where it replayed stock; RELOAD_FROM_PROJECT's detour is overridden. A tick on which FREE LOOP shows a toast returns before stock's countdown, as alone, and RELOAD's UI half runs on the next tick |
| frame_tail | the frame interrupt's epilogue `0x4000d9a6` | LOAD METER (`lm_out`), CF METER (`m_tail`), BOOT TRACE (`tr_frame_end`) | calls each, built to return (`HK_FRAME_TAIL`), then replays the epilogue once |
| frame_entry | the frame interrupt's entry `0x4000aad0` | BOOT TRACE (`tr_frame`), LOAD METER (`lm_in`) | replays the prologue once, then calls each, built to enter after it (`HK_FRAME_ENTRY`): LOAD METER's stamp last, so its duration excludes the note |
| chrom_pitch | the CHROMATIC key handler's key → pitch `0x4004fc58` | OCTA303 (`o3_chrom`), SCALE QUANTIZER (`qz_chrom`) | no code of its own: OCTA303's detour stays and, built with `HK_CHROM_PITCH`, hands every non-303 track to `qz_chrom`; SCALE QUANTIZER's detour is overridden |
| chromatic | the CHROMATIC octave keys `0x40045918`, key index `0x40050254`, keyboard picture `0x40044968` | BLACKPYRAMIDS_303, SCALE QUANTIZER | asks `ot_track_is(the UI track)`: a BLACKPYRAMIDS track its own handler or full-keyboard branch; any other track `ot_chrom_sanitize`, then SCALE QUANTIZER's handler |
| boot | the boot's `jsr 0x4000f938` at `0x40000512` | BOOT TRACE (`tr_dsp_done`), STORE (`store_part_resident_activate`) | calls BOOT TRACE's note 3 (`HK_BOOT`: it returns), then jumps to STORE's routine, which tail-jumps to the stock call |
| machine_rows | the track's machine list and SRC SETUP: the name formatter `0x400334d8`, the name tables, the row highlights, the list's opens, its commits, the SETUP editor and drawer, the Part validator `0x40002318`, the tick that publishes a machine's record, the FLEX kind entry `0x400d6438`, the LFO SETUP PMTR name site `0x4003bff0` (OCTA303 → CX OSC); the lists' row counts and bounds | ANALOG BD, OCTA303, CX OSC: each present one the next row from 5, in that order | the first present (the head) keeps every shared site; each machine, built with `HK_MACHINE_ROWS` and its place in the chain (`MC_ROW`, `MC_NEXT_*`: `machine_inc`), hands a row not its own to the next machine's routine for the same hook, entered as at the site, and the last replays stock. The head's SRC SETUP name table ends with the others' names and its tick publishes their records. LFO_NAME: OCTA303 names a signed 303 track then hands on to CX OSC's `po_lfdname` (PLAYBACK names via the page resolver). The renderer (the FLEX kind entry) chains CX OSC → OCTA303 → ANALOG BD: CX OSC first, as its page code finds its records in the words before the entry's renderer; ANALOG BD's C renderer calls stock itself; the PLAYBACK page resolver `0x40031ece` and the START rewrite `0x4000c634` chain OCTA303 → CX OSC. HOOKS pokes the lists to 5 + N rows (the counts, SRC SETUP's name bound, the commit's persist bound, and the cursor clamp in the list's five key handlers) and takes the drawer's two row tests, so the list scrolls. Three machines at most: PB_TABLE has one spare word past slot 6 |

A bridge takes each participant's claim at the site by `schema.Override`
(`ledger.py` and `build_bus.py` skip the overridden detour or symbol ref).
A participant whose own detour replays stock instructions and never returns
(the frame interrupt and boot bridges) reads a flag from its `remix.inc`
(`tools/remix/hooks_flags.py`): 1 only when its bridge is on, and then it
returns instead; alone, the flag is 0 and its bytes are the ones proven.
STORE's routine already ends in the stock call, so it is called
last and needs no flag: its submodule source is not edited.
A participant's own refs into stock's [TRACK] table are still written when
track_key is bridged; nothing reads that table once the field is repointed.

A selection with a bridged pair and no HOOKS is refused by the ledger, by
name: the participants' claims do not overlap, so without the rule the
pair would build and one of them would silently stop.

## Adding a bridge

A bridge is a participant list in `manifest.py`, a branch of `select()` and
its code in `bridge.s`. Each participant's routine is called as its own
detour would be; the order is the bridge's, and `verify_hooks` should show
why it is that order.
