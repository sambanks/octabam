# LAZY CHOP

Slice a sample by tapping the trig keys while it plays, from the audio editor's slice menu.

Author: [8thmyth](https://github.com/8thmyth). ColdFire only, one linked DRAM unit (`lazychop.s`). Settings in BRAIN: ZERO SNAP and LIVE CHOP.

Companion modules, each its own module and each optional: **LOCK EDIT** ([TRIG]+[BANK] opens the editor on a step's sample and slice), **ZOOM KEEP** (the editor keeps its zoom on audition) and **SRC3 KEY** ([MIDI] in the editor records SRC3 on an MKI). LAZY CHOP works without them and uses them when they are in the remix.

## Using it

1. Open the audio editor on the sample: [TRACK] + [BANK] for the track's sample, [REC AB/CD] + [BANK] for a recorder buffer (MKI), or [AED] (MKII). The track must be the one that plays it. (With LOCK EDIT: in grid recording, hold a trig and press [BANK] to open a step's locked sample.)
2. [AMP]: the SLICE page. [FUNC] + [BANK] (or [YES]): the slice menu. **LAZY CHOP** is its first row. A popup names the mode, e.g. `LAZY CHOP: STUDIO`.
3. **TRIG 1** plays the track from the trim start; slice 1 starts there.
4. **TRIG 2** ends slice 1 and starts slice 2 at the playhead, **TRIG 3** the next, and so on. After **TRIG 16** the page turns (a popup says `SLICES 17-32`) and **TRIG 1** starts slice 17. Four pages, 64 slices. Only the next key in order places a marker.
5. **[YES]** writes the slices (the last ends at the trim end) and ends the mode; the 64th slice does the same by itself. **[NO]** puts back the slices that were there and ends the mode. Leaving the SLICE page while chopping puts them back too.
6. Edit the slices as any others: LEVEL moves the marker between them, A/B/C edit the one under it. They are stock slices and are kept as any others: SYNC TO CARD writes `markers.work`, SAVE `markers.strd` (RELOAD brings them back), and a sample saved from the editor's FILE menu, or a recorder take saved by BUFFER SAVER, carries them in its `.ot`.

### Keys while LAZY CHOP is open

| key | does |
|---|---|
| TRIG 1..16 | TRIG 1 starts; the next key in order cuts at the playhead |
| a red trig (a slice made), short press | auditions that slice (as a slice: no timestretch for the moment) |
| the last red trig, held 0.7 s | undoes that slice; holding the green TRIG 1 at a page start goes back across the page |
| the green trig after an audition | resumes from the last marker; the next press cuts |
| [YES] | writes the slices and ends the mode (in a LIVE take: stops the recording first) |
| [NO] | puts the old slices back and ends the mode |
| [SCALE] (MKI) / [PAGE] (MKII) | ZERO SNAP on / off |
| [CUE] | LIVE CHOP / STUDIO CHOP |
| [MIDI] | held, so it cannot close the editor; with SRC3 KEY (MKI) it starts / stops a SRC3 recording |
| [PTN] + trig | selects a pattern as usual and places no marker |

None of these keys are taken outside LAZY CHOP: its key layer exists only while the mode is open.

### The trig LEDs

While LAZY CHOP is open the trig LEDs show the current page: red for the slices placed on it, green for the next key to press. Stock's running light and p-lock flashes are held off them until the mode ends.

### LIVE CHOP and STUDIO CHOP ([CUE])

[CUE] while LAZY CHOP is open switches the two; the choice is the BRAIN setting LIVE CHOP (kept across power-off) and the start popup names it (`SNAP` is added with ZERO SNAP on).

- **STUDIO CHOP** (default): as above; TRIG 1 plays the take.
- **LIVE CHOP**, on a recorder buffer: TRIG 1 starts the recorder with every source its RECORDING SETUP has (QREC applies), or joins a take a recorder trig already started; slice 1 starts at the record head and each cut lands at the head, with nothing played. During the take red trigs do not audition, a hold on the last red trig undoes silently, and ZERO SNAP searches behind the head only. [YES] stops the take at once (whatever RLEN and QREC) and writes the slices. After the take LAZY CHOP goes on as STUDIO. With every input off, or on a sample slot, LIVE is silent chop: the take plays muted and the cuts land at the playhead.

### ZERO SNAP

[SCALE] (MKI; [PAGE] on an MKII) turns ZERO SNAP on or off (the BRAIN setting ZERO SNAP, kept across power-off). On, every cut lands on the nearest zero crossing of the take (left + right): it searches 8 ms either side of the tap, then 23 ms if there is none (bass-heavy material), and only with none in 23 ms (near silence) takes the quietest frame. In a LIVE take it searches behind the record head only.

### Timestretch and slice 1

The Octatrack's timestretch (TSTR AUTO, NORM, BEAT) needs about 300 samples before the point it starts from: a voice restarted again and again within the first ~300 samples of a sample stalls silent (measured on 8thmyth's MKI: 200 and 250 samples failed, 308 held; stock CREATE SLICE GRID slices do it too). So when the track's TSTR is AUTO, NORM or BEAT as LAZY CHOP starts, slice 1 and the take TRIG 1 plays start no earlier than sample 384 (~9 ms); with OFF or VARI they start at the trim start. A trim start past 384 is left alone.

### Chopping while the recorder records

LIVE CHOP is the way to chop as you record: TRIG 1 starts the recording and the cuts land at the record head, with nothing played back. In STUDIO CHOP, arm LAZY CHOP on the recorder buffer **before** the recording starts, then start it ([TRACK] + [REC AB/CD] or a recorder trig). The cuts land where you tap; each shows as a thin split while the take records and as full markers when it stops. Stock's slice editing refuses a buffer that is already recording, and so does LAZY CHOP.

- The slices stay with the buffer for the next take: recording again keeps the markers, with the last slice's end clamped to the new length (stock's behaviour, `recnew` measures it).
- **Monitoring:** a THRU track on the same input plays it a second time beside the FLEX playback; monitor through the MIXER's DIR instead to chop exactly what you hear.

## How

- A row at the top of both SLICE menus (`TableGrow`; counts 6 -> 7 and 9 -> 10). Only the opener `0x40072c10` reads those tables, and every row has its own handler.
- LAZY CHOP's handler registers a key layer of its own with the firmware's keymap list (`0x40031494`; the last registered wins) holding only the keys in the table above, and only while chopping. No encoder table, so the page's encoders stay stock. A `jsr` detour on the SLICE page's map removal (`0x40071bb2`) takes the layer down with the page.
- TRIG 1 writes `0x1d` to the track's command word `0x46c80354 + 4t`, as a MIDI note-on does. While chopping, entry 0 of the slice table is the whole take and the slices made are entries 1..n, so the editor draws every marker and the voice plays the whole take; [YES] moves them down, writes the count, sorts (`0x40070c28`) and refreshes as ADD SLICE HERE does. Each tap reads the voice's position (`0x800049d8 + 0xa8t + 68`).
- While chopping, the sequencer's play commands for the chopped track are held off (a `jsr` detour on the frame path's read of the command word, `0x4000b54a`), so the take plays straight on; the other tracks play as usual.
- The LEDs: stock's trig-LED pass (slot `0x400c0936`) is skipped while open; the LED task's tick (`0x40055958`) re-checks ids 0-31 at 20 Hz; stock's step-LED painter's five `set_led` operands drop ids 0-31 while open.
- ZERO SNAP reads the sample through the firmware's own frame-address call (`0x4009499c`) for FLEX and recorder buffers, and through the card's stream buffer for STATIC.
- UI task only: nothing new in the frame interrupt beyond the one command-word test, no DSP code. Code and data in DRAM.

## Guards

- Only the expected trig key places a marker; a tap within 64 samples of the previous marker, behind it, or within 64 samples of the trim end does nothing; a tap behind the last marker (the take looped) says `LOOPED` and places nothing.
- At most 64 slices: the 64th ends the mode.
- If the track's voice plays another sample than the editor's, the mode stops, the old slices come back and a popup says `TRACK PLAYS ANOTHER SAMPLE`.
- The mode refuses to start when stock's own slice editing would (`0x4006e2cc`, `0x4006dae4`), e.g. on a buffer already recording.
- Settings writes re-read their value after BRAIN's call: a register clobbered by the call once sent a stray pointer to the popup (an earlier build on 8thmyth's MKI glitched the audio on [CUE]; fixed before this version).

## Measured

- **Under the ColdFire port** (`tools/verify/verify_lazy_chop.py`, the module gate; MKI unless named): chop (live markers, page turns, the order rule, NO and leaving the page restore), cap (64 slices), save (SAVE / RELOAD keep the slices), leds (red made / green next, repainted after a wipe and after a stock flash, no flicker from p-locked steps), mkii (as an MKII, from [AED]), rec (a recorder take saved by BUFFER SAVER carries the slices), seq (sequencer running, LOOPED), recnew (a new take mid-chop), ptn ([PTN]+trig, MIDI program changes), slic (SLIC on with the sequencer running), snap and static (ZERO SNAP on FLEX and STATIC), undo, aud and audslic (audition and resume), live (LIVE CHOP on a recorder buffer, silent chop), tstr (slice 1 at 384 with TSTR on, at the trim start with it off), cost (hooks with LAZY CHOP closed: about 177,000 instructions a second with the sequencer playing; ZERO SNAP 17,000-42,000 instructions a tap). All pass alone (`test/lazy-chop`) and with LOCK EDIT, ZOOM KEEP and SRC3 KEY in `test/octabam-lazy-chop`.
- **On 8thmyth's MKI**, builds from 10 to 14 Nov 2026, the last OCTABAMHC (`test/octabam-lazy-chop` on octabam main 4165efb5): chopping FLEX, STATIC and recorder buffers with the sequencer stopped and running; STUDIO and LIVE CHOP; silent chop; ZERO SNAP; audition, resume and undo; pattern recording; timestretched slice 1; saving with BUFFER SAVER. Every feature tested extensively, no issues found, no key collisions.
- The probes behind the firmware facts are in `probes/` (port scripts; they need the ColdFire port and a 1.40C image).

## Inferred / open

- Tap-to-sample accuracy is one ColdFire frame (128 samples) at best; the port has no audio timing beyond its frame model.
- A track whose RATE is negative (reverse) plays backwards: every tap lands behind the previous marker and is refused.
- The page LEDs (which of the four pages) are not driven; the page-turn popup says it.
