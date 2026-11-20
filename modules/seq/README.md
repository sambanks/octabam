# `seq` - SEQ

Author: [ilia-murzinov](https://github.com/ilia-murzinov). Rhythm math matches
filter [EUCLID](../euclid/README.md) ([repeat98](https://github.com/repeat98)).

SEQ takes its name from the SEQ submenu on Digitakt II and Digitone II.

SEQ opens a dedicated track window. Hold **`[TRACK]`** and press
**`[PAGE]`**. The window shows the title SEQ, **LEN** at bottom right, the
stock 3×2 grid, and a 4×16 step grid for up to 64 steps. **`[LEFT]`** returns
from **Harmony** to **Rhythm**. On Rhythm, selecting audio **PTCH** or MIDI
**NOTE** shows **` 1>`** and enables **`[RIGHT]`**. Other destinations keep
SEQ on Rhythm. Harmony shows **`<2 `**. The step grid stays visible.

Rhythm has A=**PULS**, B=**ROT**, C=**LANE**, D=page and parameter, E=**DPTH**,
and empty F. Harmony has A=**SCAL**, B=**ROOT**, D=**PHRS**, E=**JUMP** on
audio and MIDI. MIDI C=**VOIC** 1 to 4 and F=**CHRD**; audio C and F are empty.
Fresh audio settings select **SRC** / **PTCH**; MIDI settings select
**NOTE**. The page hint sits at the top-right of the SEQ logo panel.
Audio pitch availability follows the resolved parameter name: FLEX PTCH
opens Harmony, while THRU INAB stays on Rhythm without the RIGHT hint.
`verify_seq_tonal_port.py` checks both machines through the panel.
**LANE** selects whether A/B and the grid edit the **TRIG** rhythm or the
**PLOCK** rhythm for the current destination. **`[YES]`** writes the TRIG
rhythm and selected destination's locks. On audio tracks, TRIG writes sample
trigs; on MIDI tracks, it writes note trigs. PLCK writes locks on that
destination's rhythm. Audio PLCK hits without sample trigs create trigless
trigs. **`[NO]`** closes SEQ. Bare **`[PAGE]`** keeps its stock function and
does not close SEQ.

**Hardware confirmation, 16 Nov 2026:** the author confirmed the `OCTA S3.RMX`
handoff checklist on his MKII: the image loads in BRAIN, PTCH opens Harmony,
and THRU INAB has no RIGHT hint. Built as `REMIX=octabam BUILD=S3` from
`854ea9c055d9dea89a91763ed43f065e3a24de10`. Artifact SHA-256:
`c5efe642cab1de0d71d5ba8f5abb619147c8ea13877cc506bf21ad6bf14e086b`.
This report covers those checks; no audio or timing measurements were reported.

**Earlier hardware report:** author's MKII, `CX CJ.RMX`, 14 Nov 2026. Six reported
device checks passed: PLCK **PULS** 0 clears only that destination; all three
**[FUNC]** + **[BANK]** clear rows act immediately and return to SEQ, and
**[NO]** cancels; **"ARE YOU SURE?"** stays above SEQ with knobs locked until
answered; stock TRACK shortcuts work; **[CUE]** + **[TRACK]** cues without
randomizing while bare **[CUE]** randomizes the focused lane; and with SCALE
off, pitch locks match the Part's PLAYBACK PTCH. This report covers those
interactions on MKII; it does not claim audio testing or MKI behavior. The
port gates also pass: `verify_seq`, `verify_seq_func_bank` and
`verify_seq_scenarios`.

Historical hardware report: author's MKII, CX EUCL93, 11 Nov 2026, dual LANE,
write-only YES, LOCK_COLL + floor, PLCK overwrite and TRIG reshape preserving
other destinations.

SEQ generates track rhythms and pitch. The DSP
[EUCLID](../euclid/README.md) effect modulates filter and amp. SEQ's scale
and root remain separate from the PROJECT SCALE QUANTIZER.

Rhythm names, ranges, and the TRIG PULS default match filter EUCLID; **LEN**
shows the active length (it is not a knob).

## Controls

| control | does |
|---|---|
| **`[TRACK]`** + **`[PAGE]`** | open SEQ on that track |
| **`[TRACK]`** (while open) | switch SEQ to that track |
| A | PULS of the focused lane |
| B | ROT of the focused lane |
| C | LANE — TRIG ↔ PLCK |
| D | Page and parameter for the lock destination; names match LFO SETUP PMTR |
| E | DPTH — 0..127, lock span around Part |
| F | empty |
| **`[LEFT]`** / **`[RIGHT]`** | switch knob pages; indicator is **1/2** or **2/2** at top-right |
| **`[CUE]`** | hold = stock cue; bare release = random PULS hits on the focused lane; **`[CUE]`** + **`[TRACK]`** cues that track |
| **`[TRACK]`** (stock) | double-tap QUICK ASSIGN; **`[FUNC]`** + **`[TRACK]`** mutes; **`[TRACK]`** + **`[PLAY]`** / **`[STOP]`** / **`[BANK]`** keeps stock behavior |
| **`[FUNC]`** + **`[BANK]`** | clear menu: CLEAR DEST / CLEAR ALL DEST / CLEAR ALL+TRIGS |
| **`[YES]`** | write the focused lane and selected destination locks |
| **`[NO]`** | close |

**`[PAGE]`** / **`[UP]`** / **`[DOWN]`** / **`[PROJ]`** / **`[PART]`** /
**`[AED]`** / **`[ARR]`** are **omitted** from `EF_KEYS`
(not listed — a `0` swallows; a `-1` row still clears the sub-map). LEFT /
RIGHT select knob pages. Soft dialog keeps the layer so knobs stay locked (`ef_ask`);
user/orphan close pops it (`ef_layer_on`). LEVEL does nothing.

Hold **`[TRACK]`** + **`[PAGE]`** opens SEQ on that track. Selecting another track while
open retargets **`[YES]`** and loads that track's per-track params. DPTH and
PLOCK PULS/ROT are remembered **per DEST** on that track. D/E stay live
even when LANE is TRIG (no auto-focus switch). Slots + DEST tables live in
DRAM and in `euclid.work` (audio recipes, per-DEST depth/plock + LANE,
separate MIDI-track recipes and per-flat depths, and per-track tonal
settings; STORE client, `EF_VER` 11) on SAVE PROJECT / bank write. Older files
migrate their saved tonal settings; files predating tonal settings use the
defaults. **Pattern length:** shown as `LEN n` at
the bottom right. Defaults: TRIG PULS 5,
DEST = SRC PTCH on audio and NOTE on MIDI, ROT/DPTH/PLOCK PULS 0,
LANE = TRIG.

Write-only: open / track switch load bank SEQ params only — the grid never
mirrors live sample trigs. YES overwrites from PULS/ROT (or a CUE mask).
When a step's last lock is cleared, orphan trigless bits drop and stock's
plock LED bitmap is rebuilt (`0x400339d8`).

**CUE** keeps **PULS** as density on the focused lane and only randomizes
*which* steps are on. Changing **PULS** leaves free mode and returns to
Euclidean. PULS / ROT / CUE with sample trigs already present open stock
**ARE YOU SURE?** only when LANE is TRIG. Dialog YES unlocks knobs/CUE
only; writing the pattern is a separate YES.

**DEST** matches LFO SETUP PMTR targets. **0..29** page-1 lock flats
(**AMP XVOL** skipped). On **CX OSC**, **30..34** SETUP knobs stack in DRAM.

**DPTH** (0..127): at 0, YES clears that DEST's locks for the path in
use (TRIG: reshape to trig set; PLOCK: clear on hits/misses). Non-zero:

- **DEST = PTCH:** DPTH sets pitch variation around the Part PLAYBACK PTCH.
  SEQ chooses pitches from SCAL and ROOT. Silent / PLCK misses fall back to Part.
- **DEST = AMP VOL:** unipolar below Part AMP VOL.
- **Any other DEST:** uniform `[Part−DPTH .. Part+DPTH]` clamped 0..127.

**LANE = TRIG:** **`[YES]`** writes DEST/DPTH locks on the TRIG steps and
syncs that DEST's PLCK rhythm. Only **this DEST** is reshaped; other DEST
locks stay. On audio tracks, a step that loses its sample trig but keeps
another DEST lock becomes trigless. On MIDI tracks, the note-trig mask is
rewritten while other MIDI locks stay on their steps; they do not add note
trigs. **LANE = PLCK:** independent lock rhythm; audio PLCK hits without a
sample trig become trigless (`+0x10`). A miss or PULS 0 clears this DEST on
every step in range —
including note trigs — so a PLCK YES **overwrites** locks previously placed
from TRIG for that DEST (other DEST locks stay). PULS 0 uses the same
clear helper as DPTH 0 (stale free/CUE masks ignored) and drops orphan
trigless bits when no other DEST remains on the step.

YES writes **only** the selected DEST's lock bytes (plus the TRIG mask).
A later YES with another DEST leaves earlier locks alone.

**FUNC + BANK** while SEQ is open opens a three-row LISTPOP for wiping
pattern data without a new Euclidean fill:

1. **CLEAR DEST** - this DEST's locks only; sample trigs stay; that DEST's
   DPTH / PLOCK PULS / ROT / free mask → 0.
2. **CLEAR ALL DEST** - every SEQ DEST on the track; sample trigs stay;
   all per-DEST params → 0.
3. **CLEAR ALL+TRIGS** - row 2, then wipe sample trigs; TRIG PULS 5 /
   ROT 0.

Class-5 SEQ soft-closes while the list is up (stacking SEQ on top hid the
menu on hardware). A NO-only layer sits above LISTPOP so one NO closes and
restores SEQ. List YES runs the clear immediately (no second SEQ YES) and
restores SEQ. BANK again does the same. Outside SEQ the chord is stock
**TRACK TRIG EDIT** on MKII (`0x4007c0d0`) / PATTERN SETTINGS on MKI
(`0x40058a64`).

### FUNC+BANK hook (MKII / BRAIN)

MKII FUNC-held keys live in a table pointed from FUNC's sub-map
(`PARTS.md` MKI site `0x40058a64` is not the MKII path). On CX, **BRAIN**
SymbolRefs the MKII FUNC keys pointer (`0x400bfa36`) to a DRAM clone
`brain_func_keys`, so a ROM press patch at the stock table never runs.
SEQ Detours TRACK TRIG EDIT entry `0x4007c0d0` instead: SEQ open → clear
LISTPOP; else stock. MKI still SymbolRefs the ROM FUNC+BANK press field.
Port (`--mkii`, remix `cx`): CLEAR DEST labels; one NO / list YES / FUNC+BANK
again restores SEQ. FUNC+BANK is Detour/SymbolRef only (no EF_KEYS BANK) so
the list does not toggle open/closed on a single chord.
`verify_seq_func_bank.py` and `verify_seq_scenarios.py` cover the cases.

Manual site: [`docs/site/usage/seq.md`](../../docs/site/usage/seq.md).

## MIDI tracks

The tonal page applies to audio and MIDI tracks. **SCAL** selects MAJ, MIN,
PENT, DOR, PHR, MIX, WHOL or CHRO; **ROOT** selects C through B. **JUMP** is
available on both audio and MIDI. It sets the spacing between successive
phrase notes: 0 advances one scale position, and higher values skip farther
(range 0..127). It changes pitch spacing, while **DPTH** sets the outer pitch
span. UP starts at the Part pitch and ascends; DOWN starts there and descends.
Both wrap at the **DPTH** boundary. ALT moves up and down in alternation; TRI
repeats a short up-and-down contour. RAND chooses a random direction for each
step, with JUMP controlling the scale-degree distance; the walk wraps within
the **DPTH** candidate set. RAND is the first PHRS option
and the default for new settings. Older saved phrase values migrate without
changing their selected mode. Filling again rerolls RAND without changing
the controls. Audio C and F are empty and inactive.
On MIDI, **VOIC** selects one to four notes and
**CHRD** selects one of the FM SYNTH chord types and its inversion. **DPTH**
controls the pitch span around the Part value, up to four octaves in either
direction. **PHRS** selects RAND, UP, DOWN, ALT or TRI. MIDI **VOIC** 1 writes
one note. Higher values add
notes from **CHRD**. Filling with **VOIC** 1 clears NOT2, NOT3 and NOT4 on
hit trigs. The Octatrack MIDI arp can play the generated notes when enabled
on that track.

Hardware report, 15 Nov 2026: the author tested SEQ 83 on the MKII and
confirmed it works, including the fix that leaves unused NOTE3/4 slots empty
at VOIC 2. SEQ 82 had displayed -64 in those slots. The report does not
provide separate measurements of audio pitch or MIDI timing.

MIDI mode has separate TRIG/PLOCK rhythms, per-destination depth and
settings stored in `euclid.work` version 11. The reader migrates earlier
versions. The Part page-1 read window is registered with STORE;
`store_part_midi_context` selects the playing MIDI Part independently of
the audio engine and UI selection. All MIDI writes update the bank and
its CS1 mirror.

**D** selects NOTE, VEL, LEN, LFO, ARP, pitch bend, channel
pressure or CC1-10. **E** varies that parameter around its Part value.
TRIG rewrites the note mask and selected destination only. PLOCK keeps
the note mask and uses that destination's own rhythm. Other destinations
retain their stored locks, including when the note rhythm changes.
NOTE is an absolute MIDI pitch. VOIC and CHRD generate NOT2-4 as intervals
from NOTE; these secondary notes are omitted from the destination chooser.

With existing trigs, confirmation **`[YES]`** unlocks the pending MIDI
encoder or CUE edit in the preview. A second explicit **`[YES]`** writes
the fill. **`[NO]`** cancels. Merely choosing a destination or setting its
depth does not write locks.

**`[FUNC]`** + **`[BANK]`** opens CLEAR DEST, CLEAR ALL DEST and
CLEAR ALL+TRIGS. Each action clears steps within LEN on the focused MIDI
track. CLEAR DEST resets only that destination's depth and PLOCK settings;
CLEAR ALL DEST resets all its MIDI lock settings. CLEAR ALL+TRIGS also
clears its note mask and restores TRIG PULS 5 / ROT 0. Audio data, other
MIDI tracks, steps beyond LEN and neighboring patterns are preserved.
MIDI TRACK double-tap keeps stock behavior; NOTE SETUP uses double-tap
**`[SRC]`** or **`[FUNC]`** + **`[SRC]`**.

### MIDI proof

The author confirmed the MIDI behavior on his MKII with **CX M8**, built
and flashed on 14 Nov 2026. Artifact SHA-256:
`b6722704137567abf1ac82a6d71e3d6faaf7de915c8b3357d837675ef330f3c3`.
The image remains outside git in the shared remix folder.

Receive-only USB captures showed channel-2 note-ons, velocity 100 and
matching note-offs, with changing additional chord voices. A subsequent
fixed C3 was traced to empty NOTE locks in the saved project despite
SEQ depth 73. An explicit fill wrote the NOTE locks; the author then
confirmed that the MIDI randomization was working. Confirmation and the
explicit fill are separate actions.

The port gates check nonzero NOTE, VEL, NOT2-4 and CC locks, separate
TRIG/PLOCK behavior, CUE at depths 0 and 4, and distinct UI/MIDI playing
Parts. `verify_seq_midi_edit.py` drives real panel gestures on T2 with all
30 destinations populated. It checks confirmation YES/NO, pending edits,
selected-destination isolation, zero-depth clearing, all MIDI clear rows,
recipe resets, RAM/CS1 agreement and preservation outside the edited scope.
This automated coverage is separate from the author's device report.
