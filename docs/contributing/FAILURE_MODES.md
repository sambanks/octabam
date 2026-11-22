# Hardware failure modes: the register

Faults seen on a unit. Each entry is the symptom, the cause (marked
unconfirmed when it is not established), the fix, and the gate that now
catches it. Add an entry the moment a fault is seen on hardware; an entry
whose code has been removed is deleted.

## FREE LOOP: the first PLAY after a reboot, in MIDI mode, records T1 with T1 idle

- **Symptom:** The first
  PLAY after a power-on, in MIDI mode, started T1's recorder although
  FREE LOOP had started nothing (T1 idle, its popup said FINISHING, R1
  filled). A double STOP before that PLAY prevented it. Gone on images
  42-43 with the guard below.
- **Cause (inferred, not measured):** a quantized recording start left
  staged in `0x800018be` / `0x800018de` (the QREC branch of REC_POST,
  `0x40005178`) and fired by the first PLAY. The port does not reproduce
  the boot state that leaves it there, so neither the writer of the staged
  start nor why a double STOP clears it has been traced.
- **Guard, not a fix at the source:** FREE LOOP's `stray_guard`
  (`modules/free-loop/adapter.c`) stops any recording it did not start on a
  FREE or GRID track within one UI tick (`REC_POST(t, 0x80, 0)`), clears the
  buffer on a track with no loop yet, and says REC: FREE LOOP ONLY. Under
  the port, `REC_POST(T1, 0x9010)` after the load records for the whole run
  without the guard and is stopped within a tick, R1 empty, with it.
  `verify_free_loop stray` covers a stock T1 + REC AB on a looping T1.
- **Open:** the source of the staged start. It would also hit a track
  FREE LOOP does not run (ROLE OFF), which the guard leaves alone; a probe
  of `0x800018be` / `0x800018de` at boot on the unit is the next step.

## FX PAGE 2 LOCKS NOT LOADED at every load: SAVE PROJECT wrote empty page-2 lock files with no header

- **Symptom:** STORE's prompt (FX PAGE 2 LOCKS NOT LOADED /
  UNREADABLE OR INCOMPATIBLE) at loads of one project. Of its sixteen
  `p2lkNN.work`, bank 1's held a header; the other fifteen were 98,320 bytes
  of 0xff, header included. The project had been played under several remixes
  first; which save made those files is inferred, not traced.
- **Cause:** a bank copy with no `p2lkNN` source
  (`plk_st_bankcopy`) writes an empty file: the header, then a body filled
  in `IOB`. `IOB` is the buffer the file was opened with, and the 16 header
  bytes were still in it, unwritten; the fill wrote 0xff over them. PLOCKS
  P2 refuses a file without `P2LK` and version 1, and STORE lists it.
  `verify_plocks_p2` on origin/main `828314dc`: `p2lk02.strd` made by SAVE
  PROJECT from no source reads `ffffffff…`; with the fix, `P2LK`, version 1,
  length `0x18000`, an all-0xff body.
- **Fix:** the body is written from `FFROW`, a row of 0xff in `.data`, and
  `IOB` is left to the file layer. On a card that already holds such files,
  START FRESH / REPLACE FILE loses nothing: they hold no locks.
- **Not established:** whether the refusals have anything to do with the
  freezes seen on the same unit and project; the freezes stayed open when
  this was found (`tools/hw/freeze_watch.py` caught four).

## PLOCKS trig-paste undo keeps copied page-two locks

- **Symptom:** A continuous-hold paste/undo retained MIX 40 on the destination.
- **Measured under the port:** stock restores previous page-one locks but
  retains the trig. The private-hook baseline `ff9c5f84` also fails for page
  two: PLOCKS did not mirror the native track-lock snapshot/restore copies.
- **Fix:** EVENTS intercepts those two boundaries; PLOCKS mirrors 64 page-two
  records using its existing buffers. Stock/page-two regressions cover empty
  and existing destinations, repeated paste/undo, multiple held steps and
  clear/undo.
- **Hardware:** early E2 (`9a752f97`) observations retained MIX 40 after undo,
  both stopped and playing. Later controlled stopped checks on the same E2
  implementation restored an explicitly prepared MIX 64 and no-lock state.
  Those early observations were not reproduced with explicitly prepared
  destinations; current-source native snapshot/restore gates also pass. The
  [fixture results](../../remixes/test/events-clients/README.md)
  identify the image and confirmed scope.

## EVENTS-CLIENTS transport stress reaches silence with healthy frames

- **Symptom:** A ten-minute
  transport/tempo/program-change sequence stopped on silence at 431.5 seconds.
  USB fault deltas and DSP bad-record deltas were zero; frames remained healthy.
  Short suffix replays passed. The original cause was not established.
- **Later E2 evidence:** 600 seconds of uninterrupted C03 playback and a
  separate CONTINUE check passed their audio/USB checks. These do not reproduce
  the mixed-transport sequence. Longest observed ColdFire frame interrupt:
  424 us; four of 301 retained load samples exceeded 363 us. Downsampled maxima
  do not count individual overrunning frames or establish total CPU headroom.

- **Current-image verification:** E3 (`d476ab24`) completed the original
  223-operation sequence over 604 seconds. USB fault and DSP bad-record deltas
  were zero, no audio samples clipped, and audio remained present around the
  earlier failure point (MAIN RMS -37.1 dBFS over capture seconds 428–433).
  The original failure is not reproduced on the current image. The monitor
  allows a full 64-step pattern at the sequence's minimum 60 BPM before
  treating silence as a failure.

### E2 CONTINUE monitor stops before the fixture's next trigger

A three-second silence timeout stopped a fixed-C03 test 18 seconds after
START/STOP/CONTINUE. C03 has only a step-1 sample trig in a 64-step pattern;
its next trigger was 4.1 seconds after CONTINUE. A corrected capture observed
that trigger and resumed audio, with zero USB faults or bad DSP records.
The short timeout was a fixture error, not evidence of a resume failure.
Transport silence checks must allow for the next programmed trigger.

### Post-restart workload comparison does not isolate an EVENTS regression

Ninety-second BASE / EUCLID FX2 / edited both-slot captures measured longest
frame interrupts of 363.2 / 398.5 / 417.3 us after a two-second startup
exclusion. USB faults and DSP bad-record deltas were zero. Edited C03 was
3.9 dB above BASE and had 14 detector threshold hits, all clustered into one
stereo transient near 87.26 seconds; no samples clipped. BASE still carried
both EVENTS subscribers, and the post-restart image was not independently
identified. This comparison does not attribute the timing or transient to
EVENTS. Local records: `shared-events-hardware-E2/hardware/`.

### Matched upstream control

On the same MKII, E3 and upstream `ae69a3be` used identical generated
pattern, Part and sample data. Ninety-second BASE/both-slot captures measured
mean frame-interrupt shares of 61.00%/71.03% with EVENTS and 61.57%/71.39%
upstream; longest sampled interrupts were 364.7/417.5 us and 371.9/411.4 us.
The both-slot level rise was 4.66 dB with EVENTS and 4.56 dB upstream. The
transient detector counted 3 threshold hits with EVENTS and 134 upstream;
these are not audible-click counts. Both images had healthy frame rates,
zero USB faults, zero DSP bad records and no clipping. The level rise and
detector hits are present without EVENTS, and these captures show no increase
in mean frame-interrupt load. The
[fixture results](../../remixes/test/events-clients/README.md)
identify the builds and test settings.

## Warm restarts and emulator boots can miss cold-start failures

- **Symptom:** An early-startup code change passed emulator
  boots and quick power cycles but stalled at the logo after several minutes
  powered off. Moving the activation helper into the main OS image resolved
  the observed failures in repeated cold starts on that unit; the main module
  still runs from RAM.
- **Design consideration:** keep small startup gates and activation helpers
  resident where practical, so entering them does not require executing newly
  loaded runtime code. Publish callbacks only once their runtime is ready.
- **Contributor check:** validate the exact final image after a sustained
  power-off as well as a quick restart. Emulator success cannot validate
  physical startup behavior that the emulator does not model.
- **Limit:** the underlying failure mechanism was not established. The
  successful placement change does not establish a general defect in RAM
  execution, the shared loader or caching.

## MIDI TRACK → CHROMATIC halts at the LCD surface descriptor

- **Symptom:** `ssp: 4 VEC: 04 FS:0 SR:2000 ADDR: 400BF10A R0178`. KITS seemed good
  in the same session; the image build identifier was not supplied.
- **Cause:** the quantizer's octave-number hook
  nopped a shared stack push at `0x400449be`. MIDI branches directly into
  it and bypasses the replacement runtime, so the CHROMATIC drawer returns
  four bytes off its stack into `0x400bf10a` (the LCD descriptor).
- **Fix:** shorten the installed audio detour to six bytes and `Keep` the
  shared push. The original report's path runs clean with CHROMATIC selected
  under the port; `verify_quantizer_ui` covers both modes and models.
  Hardware retest remains open. A halt on the fixed image would falsify
  the claim that this accounts for the reporter's entire failure.

## A selected remix is lost after another reboot

- **Symptom:** The automatic switch boots the selected remix, then a later
  reboot returns to core. The maintainer confirmed that the selection must
  persist; target remix and image build identifiers were not supplied.
- **Cause (read from the source):** the loader consumes the DRAM mailbox
  once and the switcher stores no persistent selection. The previous
  documented power-cycle behaviour fails the intended workflow.
- **Fix (measured under the port):** keep the selected filename in BRAIN's
  card store and restore it at boot before the project loads. Missing targets
  release the project load in FLASHED; STARTUP MENU > EXIT bypasses the choice;
  the selected image does not recursively switch. Both DSP cores restart.
  `verify_remix_switch` covers these paths. Hardware retest is open, including
  the real boot duration and startup-menu bypass on the reporter's MKII.

`git show 666b6154:docs/remixer/FAILURE_MODES.md` holds the earlier text of
the entries that existed at that commit. These entries are newer than it and
are not in that blob: "PLAY or a sample load halts the unit in Octakit's
pattern-apply check", "Unattended halt in Octakit's Part-refresh wrapper",
"A BCR2000 goes dark or deaf", "Octakit stranded for the session",
"A bank file written by the unit that the firmware then rejects", "A UAC2
host stops audio setup", "A track button pressed within about 250 ms of a pattern
change halts in Octakit's Part-refresh wrapper", "USB MIDI clock moves the
sequencer and not the tempo", "A ten-character page-2 label faults the unit", "Eight LOFI2 in SHIFT: the audio cuts out with bursts of digital noise", "

## Crackle on core B, then tracks 1-4 silent: a `rep` in an effect's proc

- **Symptom:** Continuous crackle on core B with FILTER or PHASER on T1's FX1, at MIX 0, FDBK 0, with T1 muted and at level 0; STGS changes clicked and after a few all four tracks on core B went silent until a power cycle. The same effect on T5 was clean, and three instances on T2-T4 were clean. A second report, from Zac's MKI (Zac-Kyoti): a per-sample `rep #21` in a DSP voice tore the read-back (each sample's halves from different moments, L/R one word apart) and at worst wrote ColdFire RAM out of place (a garbage project name, "never saved", "set not mounted"; a power cycle restored them), on both cores.
- **Cause:** a DIAG selector ran parts of the proc: the per-call control code with its `rep #$18` / `div x0,a` divides crackled; a `nop` burn of the sample loop's cycle count and the sample loop without the divides did not. Cycle count and memory traffic are not the cause. **Mechanism (unconfirmed):** `rep` is not interruptible (56300 FM section 2.3.2); payload B's host-command vectors (`P:0x10`, `P:0x12`) arm DMA channels 0 and 1 for the ColdFire's transfers and must answer at once, and T1 is the first track core B runs after its frame handshake. Interrupt timing was not observed; the port has no host-port timing and reproduces neither report.
- **Fix:** each `rep` became `do #n,>label / div x0,a / label:`, bit-identical (BBD03 on the unit: FILTER and PHASER on T1's FX1 clean, STGS clean on T1 and T5, tracks 1-4 keep playing; the MKI voice clean). Neither stock payload contains a `rep` or a `div`.
- **octabam:** the 20 `rep` sites (BusDelay 1, Character 5, Character TXTR 6, Spectrum 4, Modulation 1, TESTGEN 2, Vocoder 1 at init; the first count of 21 was one too many; VOCODER 0.2 later brought a second Vocoder site, its per-call `rep #24` / `div` for GEND, converted the same way) are `do #n,>norep_<module>_<nn> / <insn> / label:` loops, one program word longer each. `tools/build/norep.py` refuses a `rep` in any DSP source at assembly (`tests/test_norep.py`). Audio is bit-identical (`verify_bus --base`, 34/34, and each module's own gates); `cycle_count.py` per-sample figures are unchanged (the sites are per-call code). Whether BusDelay's `rep` is the cause of "Junk on main R for one frame, from T1 with BusDelay" below, whose fix is an 8,192-NOP pad, is not measured.
- **Check (open on hardware):** on the unit, each module on T1's FX2 behind FILTER on FX1 with samples playing, then a STGS change on T1; BusDelay with and without its 8,192-NOP pad, checking "Junk on main R" with `tools/harness/burst_census.py` on 10-minute takes.

## A track output stuck left-only, right-only or silent, or a muted track leaking into MAIN: dense core work in a DMA's memory block

- **Symptom:** A DSP voice doing dense X work in core 0's `$8000` block, later in its `$2000` block: the ColdFire-core 0 handoff slipped into persistent wrong states until the next disturbance: a track's output left-only, right-only, silent or stereo; a muted track leaking into MAIN on ~29% of frames, mostly every other frame (a recorder take with SRC3 = MAIN); at worst the sequencer stuck on step 1-2 until a power cycle. T5 and T8 were clean until disturbed, T6 and T7 dirty from the start; core 1 never showed it.
- **Cause (inferred from the manual, bounded on the unit):** when the core and a DMA channel contend for the same internal memory partition the core wins and the DMA waits (56300 FM section 10.3.2). The partitions measured on that unit are 8K words (`$0000`, `$2000`, `$4000`, `$6000`, `$8000`): dense work at `X:$3224` failed, at `X:$6400` and `X:$7b24` was clean. Core 0's DMA: ESAI TX `X:$8000-$80ff` and RX `X:$8100-$833f` (DMA2/3, armed at `P:$3001d`, payload A only); the host ping-pong `X:$2400-$28ff` / `$4400-$48ff`; the records at `X:$000-$1cf`. Y has no DMA on either core.
- **Fix (theirs):** the 216-word working set moved to `X:$7b24`, inside stock's unreferenced `X:$7a92-$7fff`: clean on every track, both cores, two instances, a 10-minute soak.
- **Possibly affected in octabam (not measured):** ANALOG BD's DSP voice, tables at `X:$2840-$30ff` and voice blocks at `$3100-$31ff`, in the `$2000` block. Check: the voice on T5-T8 with the track muted, listening to the master or recording MAIN with SRC3 = MAIN; sweep a knob through a heavy mode and back.

## Eight LOFI2 in SHIFT: the audio cuts out with bursts of digital noise

- **Symptom:** LOFI2 in SHIFT UP on T1-T7 played cleanly; switching T8's to SHIFT as well cut the audio out, with occasional bursts of digital noise. No exception screen. Seven in RING (T1-T7) were clean too.
- **Cause (unconfirmed):** core 0 out of cycles. T1-T7 put four SHIFT instances on core 1 and three on core 0; T8 makes four on core 0, which also does the mixing. `cycle_count.py` prices SHIFT at 654 cycles/sample, which brackets the chip's figure near 900-1,000 if this is the limit (Modwerk measured its own effects at 1.4-1.7x their emulator counts); not measured on the chip.
- **Fix:** none in the code; the limit is in `modules/lofi2/README.md` ("Cost, and how many fit"): SHIFT up to four on T1-T4 and three on T5-T8.

## A ten-character page-2 label faults the unit when its knob turns: EXCEPTION VEC:04 ADDR 4E007890

- **Symptom:** LOFI2 with its MODE select labelled `RING` / `SHIFT UP` / `SHIFT DOWN` (`Formatter.STEPPED`): turning MODE threw `EXCEPTION VEC:04 ADDR:4E007890`, an illegal instruction at an address outside the OS's `0x400xxxxx` range.
- **Cause (unconfirmed):** the label overran the buffer the firmware passes to the display formatter (`void fmt(char *buf, int value)`, `docs/firmware/PARAM_PAGES.md` section 7), whose length is not measured; the copy is not located. Same family as the `abbr` overrun (`TRAPS.md`).
- **Fix:** labels `RING` / `DOWN` / `UP`; ran on the unit through images 96-99 (October 2026). Five-character labels run on hardware (BusDelay `CLEAN` / `GRAIN` / `REVRS`, BusVerb `PLATE`, TEMPO SYNC `1/16T`); six to nine are unmeasured. The schema does not bound label length.

## USB MIDI clock moves the sequencer and not the tempo: time stretch, LFOs and FX ignore it

- **Symptom:** USB clock reaches the sequencer, not time stretch, LFOs or FX; DIN clock drives all of them.
- **Cause:** the tempo (`0x80001818`) is built by the clock handler `0x40005a48` from the DTCN0 interval the UART0 ISR stores for each `0xF8` (`0x4001070a`); the USB decoder enqueued the byte without it, so the tempo stayed at the project's (no DIN clock since power-on) or at the last DIN clock's. Measured under the port (`modules/usb/README.md` "Clock"); that time stretch, LFOs and FX read `0x80001818` is inferred.
- **Fix:** `usbmidi_rx_decode` timestamps each `0xF8` as the ISR does; `verify_usb_midi_clock`.

## A halt on every power-on: EXCEPTION VEC:04 ADDR:400D7790

- **Symptom:** `EXCEPTION SSP:4 VEC:04 FS:0 SR:2504 ADDR:400D7790` on every power-on, with nothing pressed, over project Bottleservice26 (its track page drawn behind the dialog). No LOG line was written; no project file on the card changed.
- **Not reproduced under the port**: LOAD PROJECT, DSPs, 600 frames; and a power-up from captured CS1 with no LOAD PROJECT post, 600 frames. BRAIN's writes do not reach the cave: MODE DEFAULTS' view table (`0x400d765e`) ends at `0x400d76f7`; descriptor writes land on the clone descriptors.
- **Cause:** BRAIN's `snapped` flag, which gates its first snapshot, was in `.bss`. The platform leaves a unit's `.bss` as the boot left it (`tools/remix/platform_build.py`: "the unit initialises it"; the depack stage sits inside it), so on the unit it starts nonzero: the snapshot is skipped, and the restore writes through uninitialised `desc[][]` pointers and an uninitialised `table_len` starting at MODE DEFAULTS' table (`0x400d765e`), which reaches RIG HOSTS' cave and the tempo cave (`0x400d7790` is `0x132` bytes on). The port and `dsp_host` boot zeroed RAM, which is why neither showed it.
- **Fix:** image B0 (`modules/brain`: `snapped`, `table_len` and the counters in `.data`; `verify_brain` checks the four symbols are `.data`), sha256 `ca9c50c373c3c6f7…`: boots and loads Bottleservice26 on the same unit and card, (with A8 booting and A7 halting, the change between A7 and B0 is the measured cause).
- **A8 boots (measured):** image A8, bottleservice from the same tree with no BRAIN, flashed over MIDI, boots and loads on the same unit and card. So the halt comes from BRAIN.
- **To find out:** image A8 (bottleservice from the same tree, no BRAIN, sha256 `40aa4ca3fb40c9fd…`) and A9 (`brain` built with `BRAIN_DIAG=noload`: BRAIN's two load-path hooks out, sha256 `8fd683abd9a36dde…`), both on the card: A8 halting rules BRAIN out; A8 clean and A9 halting points at BRAIN's presence (its runtime or the engine job switch at `0x4008485e`); both clean points at its work at load.

## A BCR2000 goes dark or deaf on some patterns (A02, B1), fine on A01, C1, D1

- **Symptom:** On A02 no CC reached any track; on B1 every BCR LED went dark and C1/D1 stayed dead until A1; fine with the OT's MIDI OUT unplugged. Reported first as "MIDI stops reaching CHARACTER after a pattern copy and SAVE KIT".
- **Cause:** the OT's Program Change on a pattern change (PROJECT > MIDI > SYNC > PROG CH SEND; seen on the AMT8 capture as `C0 xx` beside a song-position pointer). The BCR2000 selects its preset from PC 0–31: A01 → PC 0 → preset 1 (the layout), A02 → PC 1 → preset 2 (empty), B1 → PC 16 → preset 17 (empty, dark); C1 (PC 32) and D1 (PC 48) are out of range and ignored, so the BCR keeps whatever preset it had. Not reproduced under the port, whose captures of the OT's output carry the PC but have no BCR on the other end.
- **Fix:** PROG CH SEND off on the OT (Sam). Alternatives: the layout written to all 32 BCR presets (`tools/hw/bcr2000.py`), or a PC filter on the path to the BCR. Found on the way: CC FEEDBACK reported the live lane's lock rewrites at step rate and had AMP/LFO swapped, and dumped a Kit change in one burst — both fixed, neither was this.

## A bank file written by the unit that the firmware then rejects: one 64-byte burst dropped from a 16 KiB card write, the card's MBR in its place

- **Symptom:** `PROJECT 261004p/bank01.work` written with `project.work`, `markers.work` and `p2lk01.work` in the same second (a project change or SYNC, not SAVE: no `.strd`). Checksum 0x7188 stored, 0x4e8c computed; with the checksum repaired the firmware still rejects it (−51). Content: from 0x2c000 to 0x30000 every byte is 64 earlier than in a good bank, and the last 64 bytes of that span are the card's MBR code (`33 c0 8e d0 bc 00 7c fb 50 07 50 1f …`). Three other saves that day (09:40, 12:45, 14:13) are intact.
- **Cause:** inferred: a 16 KiB ATA write lost one 64-byte burst at its head and took a 64-byte block from another buffer (sector 0, read at mount) at its tail — a DMA/bus-arbitration fault, not a serialiser error. USB CROSSBAR raises the USB host's crossbar priority on SDRAM; it is the one module in the image that changes bus arbitration under card DMA. Not reproduced under the port (a project SAVE with PLOCKS P2 writes every bank intact; the port has no bus timing).
- **Fix:** USB CROSSBAR and USB AUDIO IN CD removed from bottleservice (image 100). To find out: whether a bank written on image 100 ever fails again; the bad file is at `~/octa/backups/card_20261004_strand/`.

## REMIX SWITCH (OS SWITCH at the time): VEC:04 at PC 0x2007E788 on a file load after a switch

- **Symptom:** A switch to itself, a power-cycle, a file load -> `VEC:04 ADDR:2007E788`.
- **Cause :** MAIN MENU's rescan listed the card through the stock dir scan (`0x4007f598`), whose one global name pool (`0x460e76ac`) and cache the project, set and sample browsers keep pointing into.
- **Fix:** the rescan saves the pool and cache, lists into its own table and restores both. BSRET3OS2 ran the sequence clean. **Check:** `verify_remix_switch` (the cache as found after the menu).

## REMIX SWITCH (OS SWITCH at the time): the unit hangs on the logo after a switch, keys dimmer than at power-on

- **Symptom:** After the switch's reset the logo stays; builds 11-12 got to the UI and hung on play.
- **Cause:** the soft reset restarts the ColdFire, not the DSP. (1) The next OS's upload assumes the cores in their boot ROM; they ran the old payload on. (2) Two stale words sat in core 0's host-side receive register. (3) The payload's start sets HPCR bit 7, in which the ColdFire read every record echo as `0x010101`; the record sender abandons the upload silently.
- **Fix:** before the reset each core is sent a host command into a park (`modules/remix-switch/dsp_park.asm`, in stock's dead vectors): DMA and ESAI stopped, HPCR bit 7 cleared, a boot-ROM-style loader; the ColdFire drains each receive register. Build 14 on the unit: uploads complete, audio and play work.

## STEM REC: RING FULL ends a 24-bit take on a busy project

- **Symptom:** T1 to T8, MAIN, AB, and CD at 24 bits (eleven stereo files, 2.91 MB/s), with every track playing audio and scenes set on several parameters; T2 to T8 were Static machines with all 16 trigs on, so seven tracks restarted a sample from the card on every step. PEAK reached 100%, the status read SAVING, then RING FULL. The files saved and play, cut where the ring filled. The same sources on a light project (audio on AB, T1 as THRU, and MAIN) peaked at 13 to 16%, and at 10% at 16 bits. Again on STEMS4 (flash D): T1 to T8 at 24 bits on a project of eight Static tracks, RING FULL after 6.75 s; on STEMS5 (flash E) after 18 s.
- **Cause:** measured with `STATS.TXT`. On Yves's MKII the card was not the limit (27 MB/s at best, 4.1 MB/s on average). BuMa measured a MKI's card writes at 1.4–2.1 MB/s with Static tracks streaming, below the STEMS3 take's 2.91 MB/s, and names the writer's FS_MUTEX holds as a priority-inversion candidate (`docs/firmware/STEM_REC.md` section 19.1); not measured on the MKII. The writer task, at priority 1, ran only when every higher task was idle and in turn with three stock tasks: its copy of the ring into the card's uncached buffers averaged 15 to 18 times its own uninterrupted cost, and that copy was about half its work.
- **Fix:** for eight tracks: zero copy (STEMS7, STEM_REC.md 20.7). The frame hook, which never waits for a turn, writes each file's bytes into that file's own ring through the uncached alias, and the writer hands the card whole sectors straight from the rings. Flash G: T1 to T8 at 24 bits on the same project ran 61 s with the ring at most 21% full, every file whole. Twelve files at 24 bits (3.17 MB/s) still stop after 4.3 s on that project: documented as a limit (`modules/stems/README.md`, Limits). The next lever, built and not flashed: the writer at priority 2 (branch `stems-prio2`, STEM_REC.md 20.6).

## No audio on the first boot after an OS upgrade, with no DSP module (open)

- **Symptom:** With STEM REC alone and no DSP module, the first boot after the upgrade played nothing, in the loaded project and in a new one; the stock recorder's buffers still drew the inputs' waveforms. A power cycle brought the sound back.
- **Cause:** open. The garbled-audio entry's warm-up tag can't apply: the image places no DSP words. Not known: whether a stock 1.40C upgrade on the same unit does the same.
- **Not seen again:** STEMS2 on the same MKII, a new project made straight after the first boot played audio. Flash A had loaded the saved project first.
- **Fix:** power-cycle after every upgrade before judging anything (`docs/guide/BUILDING.md` section 5 step 5). To find out: whether a first boot that loads the saved project is silent again, and whether a stock 1.40C upgrade's is.

## Pops and clicks from T1 with BusDelay when T1 plays its own trigs (open)

- **Symptom:** Pops and clicks from the delay when track 1 plays its own trigs.
- **Cause:** open. The bus (BusDelay on T1, BusVerb on T5) is tested with T1 and T5 as THRU tracks without trigs. The one earlier test with a trig on every T1 step gave clicks and no wash. A trig splits the host's block into two dispatcher calls; the delay's glides run on the first call only (`modules/busdelay/README.md`).
- **Fix:** open. To find out: the reporter's image, machine and trig pattern; whether the clicks land on T1's trigs; whether they follow the delay (FX2 = SEND on T1, same trigs) or the machine (a THRU host with a trig every step clicks from the THRU's re-open); the same test on T5 with BusVerb.

## Junk on main R for one frame, from T1 with BusDelay, about twice a minute

- **Symptom:** 16-24 samples of random full-scale words on main R about 0.5/min, at one phase of the 4-second pattern cycle.
- **Cause:** core 1's frame start reads core 0's bank word (`P:0x57-0x7a`, payload B), picks the read-back buffer (`X:$2600` or `X:$4600`, `X:$206`) and patches the host handlers' masks (`P:$371`/`P:$380`): one read-back buffer per frame, and the ColdFire's pull (DMA channel 1, armed at `P:0x37c`) must finish before the first FX2 copy overwrites it. The ISR pulls core 0, the ESAI, then core 1; on the unit core 1's pull reaches T1's 64 words ~4.5 samples after T1's proc entry (the port models +0.26), jittering with pattern position. BusDelay on core 1 copied inside the pull. A NOP burn after the loop: +0 cycles 1266 runs/min, +256 16/min, +512 1.4/min over 10 min.
- **Fix:** image 43 (branch `padfix`): 8,192 NOPs (two samples, 11 % of the frame) after the loop, before the rts. 10-minute take: 0 junk (baseline 5). Costs two samples of core 1's budget every frame. Polling DSR1 / DCR1.DE (images 37, 38) and a frame-end detour (images 39-42: core 1 wedged at project load; the idle at `P:0x57` is the last instruction of `do #16`, a word-by-word handshake with core 0) did not work.

## A white-noise wash from a sample host with trigs on it

- **Symptom:** BusDelay on T3 STATIC with a trig every step washes from the second pass; T2 THRU with a trig every step at once. LEVEL 0 silences it; FDBK, WET and STOP do not remove it; PLAY or a reload clears it until the next full loop. T1 as host: clicks, no wash. The port shows nothing (lock-step cores).
- **Cause (unconfirmed):** each bus participant rebuilt the second call's frame offset from a flag and split stashed by the first call in its block (`$65/$66`). If the stash does not survive a trig between the two calls, the second call runs as a first: at position 0 the rotation tracker advances twice and keeps a lead of one. The stash was never measured on the unit.
- **Fix:** image 43: the offset comes from `r0` (0 on a first call, 2 × split on the second; the port: `r0 = $e` for a trig at frame 7), in SEND, BusDelay and BusVerb. The earlier init stores (removed in 42), the `$84..$88` relocation and once-per-block glides were not the cause.

## Sequencer stuck on step 1 at the first play: images 44 and 45

- **Symptom:** Stuck on step 1; power-cycle and reload recover.
- **Cause (unconfirmed):** (1) image 44's housekeeper stamp clear used one-word displaced Y stores (`move a,y:(r3+$1)`), a form with no stock site; image 45 used `move a,y:(r3)+` and wedged the same way, so the form was not (or not only) it. (2) The tracker's check read the client's last write offset from its slot as an address; an FX1 NONE slot runs SEND at an r7 below `$6200`, which ROTINIT never seeds, so on the unit the read went to a wild Y address (peripheral registers live in Y). The port zeroes RAM.
- **Fix:** image 46 masks the value (`and #>$30`) before it becomes an address.
- **Lesson:** no address from a word init did not seed, unmasked. A DSP form with no stock precedent in `tools/build/dsp_disasm_all.py` output does not ship without a hardware probe.

## A white-noise wash from a THRU host past position 0 with a trig every step; bleed into the bus with every SEND at 0

- **Symptom:** No wash. The port (`verify_set`, `out/OCTABAM89_t2thru`) shows nothing.
- **Cause:** image 47 (a marker-tone probe): the core-1 tracker sits one step ahead permanently on plain play. Inferred (`modules/send/README.md` "An FX1 slot is not a client"): FX1 NONE is id 0 = SEND, which ran on every empty FX1 slot at r7 0x6100/0x6400/0x6700/0x6a00 (measured, PC watch). The 0x6100 call sent from an unseen page byte (the bleed) and, on core 1, ran the tracker compare before position 0's advance; a flip landing before it leaves `T == R + 1` for good. Under the port the flip lands late in core 1's frame every frame.
- **Fix:** image 48: SEND returns at proc entry on an FX1 r7; the self-check removed. Image 49 (structural): eight accumulator and chain buffers, a server reads three back, the housekeeper clears two on, a core-1 client counts its own blocks from a seed read at init, checked against the rotation with a tolerance of one (`modules/send/README.md`). Costs one more block (48 samples) of latency.

## BusDelay silent with its knobs locked: the MODE formatter wrote over the minimum table

- **Symptom:** No delay; TONE, PING and MIX pinned and immovable; cleared by a reboot, back when page 2 was drawn.
- **Cause:** `tools/build/mode_names.py` wrote renames at `P + 0x4e + 6·slot` where the names live at `E + 0x4e` and `P = E + 0x38`, landing in the minimum-value table (`P + 0x6a + 4·slot`): GRAIN's names set `min[3..5]` to 0x4d444550 / 0x4d524154. Character's SAT view and Modulation's COMB view had the same fault.
- **Fix:** `NAMES_AT = 0x16` (P-relative); the project re-stamped from the manifests (OCTABAM87) measured clean on the ladder.
- **Lesson:** an autocorrelation of the mix that "measured TIME inert" was reading the material's own eighth and quarter (248 / 496 ms at 121 BPM) and is retracted; measure a delay time from the repeats' spacing after the source stops.

## CC MAP (CC PAGE 2) did not write on hardware

- **Symptom:** CC 62-67 changed nothing on the panel, stopped or running.
- **Cause:** the cave used the PLAYBACK page-2 editor's stores (`0x4003a474`), corrupting the track's PLAYBACK page-2 byte. The FX2 editor's stores are Part `+0x8f084`, shadow `0x100a51d2`, lane +0x38.
- **Fix:** the cave uses the FX2 stores; image 96: CC 63 on channel 5 moved SHMR and raised the tail's 2-8 kHz bands 5-8 dB. Every page-2 sweep taken over the old cave is void.

## BusDelay's SEND knob drew TIME's division labels

- **Symptom:** On the unit, the first knob printed `1/8`-style labels.
- **Cause:** `modules/tempo-sync` registered the TIME formatter on slot 0; TIME has been slot 1 since the one-aux re-slot. The published value was the knob's.
- **Fix:** registered on slot 1. The same day the knob became `SEND` on every track (was `AUX`), and the engines' `MIX` became an add-only `WET` (the crossfade had faded the delay out; measured on an impulse).

## A generated project shows as modified and RELOAD refuses

- **Symptom:** A project written by `tools/hw` loads marked modified; RELOAD PROJECT does nothing.
- **Cause:** the saved state is the `.strd` twin of every `.work` file; the tools wrote `.work` only.
- **Fix:** `ot_project.py stored <project>` writes the twins; `rigproj` and `delaytest` write them. A SAVE PROJECT on the unit does the same.

## Re-selecting an effect zeroes the bus

- **Symptom:** The bus measures dead (no wet on T1 or T5) after panel work.
- **Cause:** a re-select loads manifest defaults, and BusVerb's SEND defaults to 0 (a non-zero default registers every idle host as a client); Character's RET also defaulted to 0.
- **Fix:** assert SEND `CC 40` per track over MIDI immediately before every measurement (and, RET `CC 38` on the master's channel).

## A station "at its defaults" was running its default mode's view

- **Symptom:** A station documented as bit-exact passthrough at defaults changed T5's level by −2.5 dB on the ladder.
- **Cause:** `ot_project.module_defaults` applied the ModeView of the defaults' MODE (Modulation's CHOR: MIX 64, RATE 30), so `rigproj` and `stamp-defaults` wrote a half-mix chorus into every T5.
- **Fix:** a view applies only when MODE is given explicitly. Re-stamp.

## PARSE ERROR loading a generated project

- **Symptom:** LOAD PROJECT on a project from our tooling stops with "PARSE ERROR".
- **Cause:** every PART record carries its own index in byte 8 (parts 1-4 hold 0-3, mirrors 5-8 repeat 0-3); a whole-record copy keeps the donor's. Also: `project.work` edited in text mode loses its CRLF.
- **Fix:** write `p % 4` into byte 8 after any whole-record copy (`ot_ladder.PART_INDEX_OFF`); the generator's read-back checks every record.

## The set went silent after a test flash: the firmware reset the project

- **Symptom:** After flashing a test image whose remix omitted Character; silent back on the bottleservice image.
- **Cause:** the card's bank records had every part reset (FX1 id 4 with FILTER's page-2 bytes, FX2 = stock delay, T1/T2 no longer THRU, T8 = FX1 NONE / FX2 COMPRESSOR 0x18). Unconfirmed: the firmware sanitises part records whose FX ids are not in the running image and writes the .work files back. Not reproduced by LOAD PROJECT under the port (OCTABAM88 bank B under `bus`), so the rewrite happens on another action.
- **Fix:** never load the set under a test image. Recovery: save a copy of the card's project; regenerate (`ot_project.py rigproj … + lfo-clear … all`), copy the banks over in place, keep the project's own `project.work` (a foreign `OS_VERSION` tag gave PARSE ERROR, inferred from the diff).

## The master compressor collapses one channel above COMP ~40

- **Seen:**. Character on T8 with COMP above ~40: R drops 40+ dB, L holds; scales with WDTH; only with the stations loaded.
- **Cause:** T4's Spectrum generated near-full-scale DC from state: init cleared `$00..$17` only; filter B's two HP poles at cHP = 0 were frozen and `hp2 = yB − h2` subtracted a stale h2 every sample (−0.5 FS on silence from a block pre-filled with 0x400000, under `dsp_host`). The makeup clipped DC + audio on the channel with the larger offset. Track LEVEL 0 on T4 cleared it; AMP VOL 0 did not.
- **Fix:** every persistent slot zeroed at init (Spectrum `$00..$3f`, Modulation's LFO values, Character's counters, phase and grace). Image 8: bank G's master at COMP 40 / 80 / 127 reads R−L −0.4 / −0.1 / −0.6 dB (was −44 at COMP 80).
- **Lesson:** a channel-asymmetric failure in channel-symmetric code is a data asymmetry; an AC-coupled capture cannot see DC.

## A diagnostic image silenced every bank with stations; the port played them (open)

- **Symptom:** An image with CHARACTER 189 words shorter played banks A, B and E and was silent on F and G, with the DSP not hung.
- **Cause:** open. Under the port image 5 plays F and G and runs no instruction image 4 did not. Left: placement (Modulation moved down, A 0x1c1b, B 0x193c; stock COMB code and dispatch kept on payload B). Image 6 = image 5's Character plus 189 nop words plays F and G. Not bisected.
- **Fix:** workaround: pad a diagnostic module to a placement known to play.

## Sequencer stuck on step 1 at project load: an init that moved r1

- **Symptom:** Every project loading a Spectrum on FX1.
- **Cause:** the FX1 dispatcher keeps the effect id in r1 across `jsr init` and indexes the proc table with it (`P:0x4c8..0x4d7`). Spectrum's init returned r1 = r7+24; `jsr (r2)` landed on P:0. `dsp_host` calls init and proc itself and cannot see it.
- **Fix:** init zeroes through r5. Recovery: power-cycle and a project without the module.

## Sequencer stuck on step 1: cycle overrun or a wild value

- **Symptom:** Step 1 solid, no audio.
- **Cause:** a core cannot finish a block: a cycle overrun (three heavy stations beside an engine at a static 3,106 of 3,120; the counter is a floor, the wall a cliff), or a wild stored value feeding an engine on frame one (an old part's crossed-slot byte after a layout change).
- **Fix:** fit the layout (≤ two heavy stations per core); stamp the project for the current remix before playing.

## A TIME turn on BusDelay crackles for about a second, in both directions

- **Symptom:** TIME or FDBK moves crackle; putting knobs back does not clear it; re-selecting does.
- **Cause:** the glide (image 33) stepped its Q8 state once per block, up to ~17 samples a step; the loop's tap, REVERSE's lag floor and GRAIN's read base jumped by the step at every block edge (~1 s of clicks after a big move, then a ~3 s sub-sample tail). The FDBK crackle was TIME's tail.
- **Fix:** the Q8 TIME ramps within the block, a sixteenth of the step per sample; REVERSE and GRAIN re-derive their per-sample lag from it. Spikes per mode 5,228 / 2,676 / 4,483 → 0 / 73 / 896 (the remainder is REVERSE's uninterpolated heads).

## An FX1 station's page 2 does not reach the DSP on a bus host

- **Seen:**. Character on T1 (THRU, FX1) ran TAPE whatever the panel said (−47 dBFS hash at knob 3 = 127). T3 (STATIC) and T8 (FLEX) took page-2 edits; T1 did not. T2 (THRU, FX2 = SEND) kept its page 2; T1 (FX2 = BusDelay) lost it.
- **Cause:** the tempo cave (`modules/tempo-sync`, in the voice-record writer for FX2 ids 6/7) stored tempo24, clock period, fader+1 and note into record halfwords 18-21 (`+0x24..+0x2a`) every frame after the copier put FX1 page-2 bytes in 18-20 (`0x400d7550`, `0x400d755e`, `0x400d7522`). Halfwords 18-20 are also `r6_FX1+$c..$e`. Every FX1 effect on a delay or reverb host had run page 2 on tempo bytes.
- **Fix:** the cave publishes only the note, into the low byte of BusDelay's TIME halfword (`+0x1b`, `r6+$1` bits 8-15); BusDelay reads tempo24 from stock's record word (halfword 31, `r6+$13`, `0x40004d6a`) and derives the period on the DSP. Under the port a live SAT edit on T1 lands (`0x7f01`); 120 BPM snaps TIME to 11,025 samples (1/8). Image 24: sends into the delay work on the unit.

## Static that stays after knob moves with both engines live (open)

- **Symptom:** Knob moves on BusDelay or BusVerb (times, sizes) sometimes bring static that stays, most reliably with the reverb host's SEND and both WETs up; a transport restart clears it. Not reproducible on demand after. One 10 s capture (`out/hw/voicing25/noise_now.wav`): HF above 8 kHz −77 dB against −85..−91 dB after CC toggles, no clean A/B.
- **Cause:** open. Under the port (ONEAUX fixture and OCTABAM89 C02 for 2,400 frames, `out/crackle/c02_recipe.midi`) a knob turn costs no extra cycles (delay 3,754 → 3,754, REVRS 3,914, reverb 16,710 ± 14) and no output rails or jumps above 0.25 FS. The port models no stall; C02 prices ~2,950 (core 1) and ~2,994 (core 0) against 3,120 usable, with the counter ~270 low on the reverb, so an overrun that desynchronises the frame handshake fits (unconfirmed).
- **Fix:** open. To find out: with the static going, take one station off the core (T2's FX1 to NONE); or the burn knob on C02, stepping it until the static appears (`make burn` was retired; `tools/harness/README.md` "The burn knob" says how to recover it).

## A DC thump every 10.59 s at idle, from track 6

- **Symptom:** Every ladder rung, including the one with no module of ours; transport stopped. DC step +0.23 FS L / +0.46 R, two-sample rise, ~35 ms decay through the output DC blocker. LEVEL 0 on T6 removes it; AMP VOL 0 does not.
- **Cause:** T6 LFO 2: destination 16 (AMP BAL), triangle, speed 18, depth 21, FREE; period 64 steps at 121 BPM with a 3/4X scale; the pulse rate follows LFO speed. A plain BAL move over CC 8 never pulses.
- **Fix:** every LFO depth cleared in OCTABAM87 and the ladder (`lfo-clear all`). Open: whether a balance LFO pulses on stock 1.40C (the port with a fast LFO fixture decides it); a 593.5 Hz tone at −75 dBFS after STOP on OCTABAM87 only.

## Spectrum VOWL went silent with RES up

- **Symptom:** VOWL at RES 100 with FREQ ≤ 96, and RES 127 at FREQ 64, output −102 dBFS; other modes bounded.
- **Cause:** not reproduced (`dsp_host`; image 97 with MODE over CC 69, both knob orders). The one difference: T3's FX1 page 2 was on screen during the page-1 CCs (the editor's refresher `0x40027e00` runs there). CC 35 with page 2 on screen landed on RES, which falsifies routing by displayed page.
- **Fix:** the two-peak VOWL is gone (image 98: a three-formant resonator bank, bounded at RES 127). If it recurs, capture before touching anything.

## A one-sample tick on an exact 2048-sample grid at idle (open)

- **Symptom:** A common-mode one-sample downward spike, −45 dBFS, every few hundred ms; present with the reverb's track muted.
- **Cause:** open. Ruled out: the capture setup, Character, the stored project (a reload gave zero ticks), the input path, BusVerb page 1. Page 2 untested (the CC MAP fault). Candidates for 2048: BusVerb's 2048-word modulo buffers (`m5 = $7ff`), Modulation's `buffer_words=2048`, the PCM-pool block (`0x800` in the recorder's table at `0x80003c20`).
- **Fix:** open. When bisecting by hand, take slots to a stock effect, not NONE (id 0 is SEND). `tools/rec` (built from `tools/hw/rec.swift`) must be the HAL recorder.

## Sequencer stuck on step 1 with every effect turned off: id 0 is SEND

- **Symptom:** Every FX1 NONE and every FX2 SEND.
- **Cause:** id 0 is aliased to SEND and FX1 NONE is id 0, so SEND's proc runs on every FX1 NONE slot with r6 on a page whose bytes the last effect left; the burn read a stale slot-1 byte on four extra slots per core. The emulator never instantiates an FX1-NONE slot. Second instance: 🔴 7,111 burn loop iterations at "0" and the frame never finished; the loop count's cause is open. a port page dump shows every slot raw, knob << 16).
- **Fix:** anything in SEND that reads a knob and can cost cycles or write the bus gates on the slot being FX2. Since image 48 SEND keys the refusal on r7 (0x6100/0x6400/0x6700/0x6a00, measured under the port; X:$213 is stale at proc time) and returns before touching state. The burn reads page-2 slot 6 (`$c`, CC 62), unflashed. The stamper writes SEND's defaults into every id-0 slot, FX1 and FX2.

## Line-F exception on [PROJ]: a cave pinned in OS .bss

- **Symptom:** PROJECT throws an exception and wedges.
- **Cause:** a cave at `0x40108800`, in the OS image's last ~30 KB: a zero run at rest that is the PROJECT subsystem's RAM.
- **Fix:** `build_bus.SAFE_CAVE_CEIL` (0x400d8000) refuses any cave above the decoded free region.

## Garbled audio straight after an OS upgrade: the warm-up tag

- **Symptom:** Right after OS UPGRADE, audio garbled (worse for the delay); not after a reboot.
- **Cause (unconfirmed):** an upgrade rewrites program memory without clearing DSP state RAM; an engine skips warm-up when its tagged counter holds a valid tag at full count (BusVerb `$2c0000` at `r7+$82`, BusDelay `$2e0000`).
- **Fix:** power-cycle after every upgrade before judging anything.

## A module mistuned on tracks 1-4 only: an absolute stock-table address

- **Symptom:** Bryan T's LOFI2 low-pass three times too bright on tracks 1-4.
- **Cause:** the payloads are linked separately: the 6,305-word curve bank is `X:0x438` in A and `X:0x42b` in B; Y tables shift by 16. A bare literal is right on A (tracks 5-8) and 13 words off on B. The single-payload audition render dumps payload A.
- **Fix:** declare stock X/Y table addresses so the build rewrites them per payload, or read through a build-supplied base.

## Self-oscillating squeal: a page-2 value out of range, or deep overrun

- **Cause:** (1) a wild page-2 value: BusVerb DIFF stamped to 127 self-oscillates the tank (the +0x325/+0x331 stamp-offset bug, also flash 4's "the stock DELAY wedges the unit on part load": T4's DELAY row landed on T5's BusVerb). (2) Deep cycle overrun (the high-pitch squeal, `docs/firmware/CHIP.md`).
- **Fix:** re-stamp the project (1); fit the layout (2).

## "Z" screen / won't boot: corrupt OS

- **Fix:** Startup Menu recovery: power off; hold [FUNC], power on; [TRIG 3] MIDI UPGRADE; send a good `.syx` (`make midi-flash PORT=A SYX=…`, or a SysEx app). [`docs/guide/BUILDING.md`](../guide/BUILDING.md) section 7.

## Cross-core bus glitch: the accumulators' race

- **Symptom:** A tear, stutter or hash on wet audio crossing cores, often smeared into a reverb tail.
- **Cause (measured under the port, `git show 3ceba41:docs/history/COLDFIRE_PORT.md` O12; [`modules/send/README.md`](../../modules/send/README.md)):** core 0's housekeeping flips the rotation word mid-way through core 1's frame; clients read the word directly, so a frame's sends split across two buffers.
- **Fix:** four ACC buffers and one rotation tracker per core (`build_bus.py` ROTLATCH, payload B); eight buffers since image 49 (above). No local test is evidence: `dsp_host` runs the cores lock-step or under a guessed interleave.

## CONTROL menu shows its stock six rows though the image carries eight (open)

- **Symptom:** The bus screen's appended rows absent; the image held row count 8 at 0x400cbd54 and the repointed row pointer.
- **Cause:** unknown; the rows are read from somewhere the patch does not reach.
- **Fix:** the module is out of the tree. Navigate to CONTROL in the ColdFire emulator's own menu before any flash that appends rows again.

## The port reports a wrong bank/pattern for an image that detours `0x40087d44`: the instrument

- **Symptom:** Under `ot_emu --sequencer`, an image hooking the BANK= store at `0x40087d44` plays bank 0 pattern 0 after LOAD PROJECT (`saved_bank: -1`). A 38-site bisect and a PR to midisc's author (withdrawn) were built on it.
- **Cause:** `rtos.cpp` learned the saved bank from a write watch on `BANK_PTR` (`0x46c82456`) accepting only the stock store's PC; a detour stores from a cave.
- **Fix:** the watch follows a `jsr (abs).l` at the site and accepts the detour's store; `--bank N` overrides.
- **Lesson:** a port watch keyed on a stock PC is blind to any module that detours that PC.

## A send that ignores its knob, a track loud into the bus at SEND 0, different per track

- **Symptom:** T5 and T7 loud through BusDelay at SEND 0; T3 quiet; T2 leaking with a dead knob. CLEAR PATTERN fixed it.
- **Cause 1:** stale parameter locks: one lock byte per slot per trig (`tools/hw/ot_bank.py`: 64 steps × 32 slots; FX1 = 18-23, FX2 = 24-29; `0xff` = none). Every slot move since 7 Sep left locks on whatever knob sits there now. OCTABAM89 carried 962 FX1 and 6 FX2 lock bytes, one on T5's FX2 knob A.
- **Cause 2 (unconfirmed):** an FX2 stored as id 0 aliases to SEND; the firmware delivers no page for it, so SEND reads whatever the DSP page word holds. Not measured under the port; the falsifier is a stamped project that still leaks.
- **Fix:** `ot_bank.py strip` clears a page's locks in every pattern; `stamp-defaults` and `clean` store SEND (id 9) with a zero page in every empty FX2 slot.

## Freeze without an exception screen as ColdFire delay-routine work grows

- **Symptom:** TAPE ECHO (which runs in the stock delay's frame routine, [`docs/firmware/COLDFIRE_DELAY.md`](../firmware/COLDFIRE_DELAY.md)) freezes the unit on a control edit with several instances.
- **Cause (unconfirmed):** the routine's per-frame deadline. Port instruction meter per eight-track frame: stock DELAY 7,628; eight instances ~23,000 settled, up to 32,355 moving (after the EMAC rewrite: 15,283 / 16,459 / 21,547, `modules/tapeecho/README.md` "Measured", unflashed). Frame period 363 µs, ~95,800 CPU cycles at 264 MHz, shared. The meter prices an uncached SDRAM access at one cycle. State is a fixed 1,600 B; nothing is allocated. Stock spins at `0x40003780` on DMA status `0xfc0450be` before the commit: a silent hang on overrun. Falsified by a freeze at the same count with the work halved, or with settled controls.
- **Fix:** open; the ColdFire's per-frame budget for the routine is not measured. Any reverb or granular on the ColdFire prices above the seven-instance point (BusVerb ~18,000 DSP cycles per frame, four-grain GRAIN ~28,400).

## Bursts of garbage on the reverb host's frame while the delay runs on core 1 (open)

- **Symptom:** 23-53 samples of near-full-scale garbage on T5's side about 3.5 times per six minutes. Stock 1.40C does not burst (Sam).
- **Cause:** open. Measured:
  - The bursts need the delay's DSP code running on T1 past its preamble: image 95 (proc returns at its first instruction) and 96 (stops after the preamble) read 0 in 12 minutes; every other delay image burst. T1 AMP VOL 0 read 0.
  - Ruled out on the unit: the ColdFire side of id 6, CPU load on core 1, the reverb, the frame write-back, the role lock alone, absolute-address stores into the shared window, words written by both cores, which half of the shared window holds the bus scratch (images 91-99), and the delay's per-sample shared accesses (image 91 take 5: none, same rate).
  - 9 of 12 bursts start 14-18 ms after the loud transient in T1's sample, and follow T1's trigs when those move against the beat.
  - The aligned-copy census: T1's own print deviates in the same 16-sample block in 29 of 32 bursts (0.03-0.35 FS); the same T1 audio instant gives the same burst waveform (12 copies of one cluster across images 91-99), so the content is a function of T1's audio. The junk is in T1's stereo block, full scale on the side T1 is panned away from, before the main mix (CUE shows it), and not T5's block (T5 LEVEL 0 changes nothing).
  - The dispatcher re-sets r0, r1, n1, r3, x1 and y1 before the read-back packer (`P:0x303-0x35e` on B); m0-m6 were saved on image 83 and it still burst.
  - Rates: a six-minute 0 occurs by chance 5-9 % of the time, a twelve-minute 0 about 0.1 %; the earlier two-minute table read 0 by chance ~37 % and separates nothing.
- **Fix:** open: where between T1's audio block after proc and the read-back words at `X:0x2600` the junk appears, and which part of the delay's per-block decodes or sample loop it needs. Branches `diag91`..`diag98`, `core1scratch99`, `nolock94`, `fix97`; captures `out/hw/v9*.wav` (machine-local). The "dead words at 0x360d3-5" (send_client.asm) are unexplained.

## A UAC2 host stops audio setup after reading the clock: SET CUR of the read-only rate unanswered

- **Symptom:** The Outbox stays GREEN, "no device connected". macOS enumerates and streams the same image.
- **Cause:** the Outbox enumerates the unit, sets the configuration, reads GET RANGE and GET CUR of the clock (44100), then sends SET CUR of CS_SAM_FREQ_CONTROL with a 4-byte data stage, and its audio setup stops there. The clock declares the control read-only and the stock EP0 stack has no control OUT data stage: the request fell to the stock STALL tail, which stalls only EP0 IN. Under the port the data stage is never accepted and the host times out. The read-only clock is octemu's design (`custom/usb-audio.py`), carried here.
- **Fix:** `usbaudio.s` `audio_ctrl_shim` takes the SET (44100 acknowledged, any other rate a status-stage STALL). On the unit, with the SET acknowledged (a build before the rate check), the Outbox completes audio setup and streams.

## USB audio: a burst of reordered samples in the first 1.5 s of every host stream, clean after (open)

- **Symptom:** Four of five takes have one cluster of sample-step events 0.75-1.5 s after stream open, on several channels, none after 2 s (60 s, 60 s, 300 s, and 120 s under a 7,170-message/s USB-MIDI flood with panel work). Device counters (vendor request 0xc0/0x55): 0 underruns, 0 overruns, no bank-duplicate movement. Image 69 (24-bit, four packets queued at a 250 µs poll): still present, 0.51-0.76 s after open, only on the right channel of each pair, in runs 124-380 frames off phase.
- **Cause:** open. Candidates: the device's packet queue on the first primes after alt 1 (the controller's add-dTD tripwire, not modelled by the port's bench), or the host's stream start. Right-only on image 69 points at the host's stream assembly: each USB frame carries a track's L and R in one packet. Likely octemu's "some crackles" (sox opens a fresh stream per run).
- **Fix:** none. Workaround: discard the first two seconds of every take, or hold the stream open in a DAW. A stream held open across two recordings, or a sequence counter in the packets, decides the cause.

Entries from here to the end of the file were recorded in other documents first; each cites its source, which holds the full text.

## Line-F exception (VEC:0B) when a parameter is LFO-modulated: a 5-character `abbr`

- **Symptom:** A module's descriptor drew correctly and behaved under manual knob use; the moment a parameter was LFO-modulated it threw a line-F exception (VEC:0B) at PC `0x48454C4C` = `"HELL"`. Presented as "custom effects can't be modulated".
- **Cause:** `abbr` is a 5-byte field holding four characters plus a terminator; `fullname` is 13 bytes holding twelve, and the build tag is appended after the string. A name that fills its field leaves no NUL. A faulting PC made of the field's own ASCII is a smashed return address, so the copy destination is fixed-size (inferred, the copy is not located; the length rule is measured: all 30 stock page descriptors are ≤4 characters with byte 5 zero).
- **Fix:** `schema.MenuEntry` refuses both over-lengths and `build_bus.py` re-checks the string it writes, tag included (this caught two diagnostic delay names, `BusDlyRPLY` and `BusDlyNOCF`, that had filled all 13 bytes).

## A cloned descriptor draws as the donor's control: three of six page-2 slots wrong

- **Symptom:** BusDelay clones SPRING REV, and the formatter fix-up in `build_bus.py` was gated to the reverb. WOW inherited SPRING TYPE's word-label renderer (a three-entry table), was asked to draw 0..127, and drew no knob at all; MODE inherited SPRING BAL's bipolar pair and drew as a balance dial reading −64…−60 instead of a 5-way select.
- **Cause:** a descriptor's display formatter overrides its value count, and a cloned descriptor inherits every field not explicitly written from the donor. Every field the checks examined was right.
- **Fix:** `verify_menu` checks the renderer against the count (`count < 128` → the enumerated pair with `0x12a` zero; `128` → both formatters zero). `Formatter.PLAIN` zeroes a clone's formatter words (`CHANGELOG.md`,).

## The unit hangs when a module keeps state at r7 `$84` or above

- **Symptom:** BusDelay's chain write address, WET glide state, write offset, REVERSE cap and last-seen rotation sat at `$84..$88`; on a host track with a sample playing, the unit hung (images 39–42 per `CHANGELOG.md` image 41; header map in `modules/busdelay/delay_server.asm`). Source: `TRAPS.md`, `docs/firmware/CHIP.md` section 5.
- **Cause:** `r7 $84..$8a` holds the unit's own per-track state between our calls (a host track with a sample playing); per-call scratch there is fine, state across calls is not.
- **Fix:** nothing at `$84` or above ("NEVER WRITTEN"); new per-track state goes in a free slot of the module's own block (`$00..$83`) or the Y state table.

## Tape Echo `Vec:03` (address error) on the first optimised image

- **Symptom:** `Vec:03` at `te_read_linear`'s scaled-index ring read `move.l (a1,d0.l*8),d5`. The emulator accepted it. Source: `modules/tapeecho/README.md` "On the unit".
- **Cause:** ColdFire raises an address error on scale factor eight.
- **Fix:** the reader forms the byte offset explicitly; generation rejects any `*8` memory address form. The same README lists a separate hardware freeze as open.

## Image 99: an FX2 change on T5 took the reverb off the track

- **Symptom:** An FX2 change on T5 took the reverb off the track; with the engines hidden from the chooser there was no row to put it back. Source: `modules/fx2-lock/README.md`.
- **Cause:** the FX2 chooser's select handler writes the Part's FX2 id for any track.
- **Fix:** FX2 LOCK: YES's entry in the chooser window's key table points at NO's handler, so the select handler never runs. Measured under the port by `verify_fx2_lock`; no hardware result recorded in `modules/fx2-lock/README.md` ("On the unit: Not yet").

## Sound-on-sound plays a zero at each pass (sos-capture BUILD=94 and 95)

- **Symptom:** After a recorder reallocation every long-pass wrap is one sample of zero for the whole take (BUILD=94, three hold caves); in steady state every wrap is an exact repeat. Source: `CHANGELOG.md` "sos-capture BUILD=94 and BUILD=95", `modules/recorder-loop-fix/README.md` section 4.
- **Cause:** the fetch of index END (`+0x64`) finds no block and returns the empty pool base; after a second transport start the recording stays 82,687 samples on every pass and the recorder is past END when the voice reaches it, where the copy loops cap the voice at END − index = 0, stop it and zero-fill the frame. SRC3 records the zero back into the loop.
- **Fix:** five hold caves (three fetch caves and two guard caves): the last sample is repeated. No zero in any take (16 → 24-bit reallocation, 24-bit off/on + reload, STOP/PLAY three times, steady state, RLEN 4 trigs); not run: STOP/PLAY on BUILD=94. Every 128 / RLEN 16 wrap is a repeat (lag 82,687 → 82,688) or a skip (82,688 → 82,687).

## BCR2000 locks up when the bank changes (image A2, unpaced CC FEEDBACK dump)

- **Symptom:** 344 messages ≈ 1 s at 31.25 kbaud without running status). Source: `modules/cc-feedback/README.md` "On the unit", `modules/cc-feedback/cc_feedback.s`.
- **Cause:** the sweep put the whole dump on the wire at once. (The dark/deaf BCR on A02 and B1 is a separate cause: the entry "A BCR2000 goes dark or deaf on some patterns".)
- **Fix:** commit `41765855`: one message per UI tick (120 Hz, `PACE`), about three seconds per full dump; image A3.

## MKI: FUNC+BANK opens SAVE KIT, PATTERN SETTINGS unreachable (KITS)

- **Symptom:** A user on an MKI with KITS, Discord (kazeko), "cant find pattern edit now ... before FUNC + BANK". Not reproduced on an MKI unit.
- **Cause:** `kits_mkisave` detoured the MKI FUNC+BANK dispatch `0x40058a64` and opened SAVE KIT whenever KITS was ready. Stock opens the Part edit menu there only while the PART window is open, and otherwise PATTERN SETTINGS (`0x40083440`) or one of two targets chosen by flags at `0x460d1aec` / `0x460d1736`. Octakit kept the stock condition (SAVE KIT from LOAD KIT only).
- **Fix:** SAVE KIT only while KITS' LOAD KIT list is open (the stock list's callbacks pointer `0x460e5e28` is KITS' table), close SAVE KIT, cancel the Kit name editor; anything else runs the stock dispatch. `verify_kits` `mki*` scenarios on the MKI panel.

## KITS: an empty project shows Kit 256, and SAVE KIT opens on it

- **Symptom:** "empty project, first kit is 256 instead of 1".
- **Cause:** ASSIGN and RESID store "no Kit" as `0xff`, which is also Kit 256's index; `cur_kit`'s callers bounded it by 256 Kits, so a slot with no Kit read as Kit 256 (the status line, the LOAD KIT and SAVE KIT cursors, PTN+FUNC+RIGHT), and a save there could never be assigned to a pattern.
- **Fix:** 255 Kits (`NUSE`); record 256 is never a Kit. A Part found in it at a load (an earlier save, or Em's Kit 256 on import, with the patterns her manifest names) moves to the next empty Kit (`rescue_k256`). `verify_kits` `k256save`, `k256load`, `k256rescue`.

## KITS: LOAD KIT shows the loaded values late, or only after a key press when stopped

- **Symptom:** "after loading new KIT values appear after a moment; when OT sequencer does not run, after loading kit i need to press FUNC to display loaded values".
- **Cause:** LOAD KIT ran the stock Part Reload (`0x4004aab4`) without the screen refresh stock FUNC+CUE runs after it (`0x4005e0a8..0x4005e0d8`). Under the port, stopped: the screen after LOAD KIT differed from the screen after a further FUNC tap by 11 bytes.
- **Fix:** `kits_load_current` runs the same refresh; the two screens are equal (`verify_kits` `drawn`).

## Left-only click bursts from VOCODER on T1, at one phase of the pattern

- **Symptom:** Click bursts on the left main out only, at one phase of the 2-second pattern, worst at trigs. Captured at the main outs through a Scarlett 18i8. Absent with T1's FX2 on NONE; absent with VOCODER on T2 or T3 (OCTABAM20, clean alone and two per core).
- **Cause (unconfirmed):** a core's position 0 is the case of "Junk on main R ... T1 with BusDelay": an effect there can finish before the ColdFire's pull of the previous frame's read-back has passed T1's words. That entry is main R with 16-24 samples of random full-scale words; these were left-only bursts, so the match is not measured. T5 (core 0's position 0) was never tried.
- **Fix (avoidance):** VOCODER runs at FX2 positions 1 and 3 only (r7 0x6500 and 0x6b00: T2, T4, T6, T8; positions 1 and 2) and is a dry pass at position 0. Position 3 is checked in the emulator only, not heard on the unit. The padding fix of the BusDelay entry costs two samples a frame, which two VOCODERs on a core cannot afford.

## KITS: with PATTERN held, a second single TRIG starts a chain

- **Symptom:** "i have to release PATTERN every time i want to just switch to another one, otherwise if i hold PATTERN then CHAIN starts"; "normally holding PATTERN switches to PATTERN until i press two or more step buttons at once"; after PATTERN is released the SELECT PATTERN window still chains.
- **Cause:** the stock PATTERN+TRIG press handler (`0x40056b2c`) keeps the key in `d2` across its call to the scheduler and then sets that key's bit in the held-TRIG mask `0x460d1ab6`; a press with the mask non-zero appends to the chain (`0x40056b50`). KITS' `stage_req`, called from its scheduler and chain-append detours, returned with `d2` = 0, so the press set TRIG 1's bit, the release cleared its own key's, and TRIG 1's stayed set until PATTERN was pressed again (`0x4005a076`). Under the port, TRIG 2 then TRIG 3: stock schedules both; KITS appended the second to the chain from `0x40056ba0`, and the mask read `0x0001`.
- **Fix:** `stage_req` keeps `d2`. `verify_kits` `ptnmask` (mask 0; `0x0001` on the code before).

## Two SET_INTERFACE requests 40 ms apart freeze the unit (USB AUDIO OUT, a DAW changing its buffer size) (open)

- **Symptom:** Erreye's MK1, `felipe` remix (USB AUDIO OUT TRACKS POST, `AUD_TARGET` 256 locally), macOS and Ableton Live with the unit as the open input. A buffer-size change in Live: CoreAudio stops IO (20:11:18.653), SET_INTERFACE(4, alt 1) (.747), `Initialize failed` and SET_INTERFACE(4, alt 0) (.786); 6 s later `Unable to select alternate setting`, `0xe00002d6` (timeout): the alt 0 status stage never completed. Then every EP0 request timed out (5 s each), EP 0x82 (USB MIDI) took transaction errors and the device dropped. Frozen until a power cycle; the screen was not recorded. Also while building an aggregate device: 12 failed starts in about a second, and a freeze at 20:08:06 right after a reopen.
- **Cause:** open. Not reproduced under the port (`usb_host` bench, `--frame`): 24 rounds of alt 1, then 0–160 polls on EP3, alt 0 and GET_INTERFACE; the same 18 rounds with GET CUR + SET CUR 44100 before alt 1, and with SET CUR 48000 (STALL) mid-stream. All clean, alt reads 0. erreye's candidate: alt 0 in `audio_setiface_shim` runs `audio_ep3_flush` inside the USB interrupt, and the port's flush completes at once (`modules/usb/README.md`, "Bus reset and session end"), so that path is unmeasured on a unit.
- **Fix:** none. Workaround: don't change the DAW's buffer size or sample rate while the unit is its open input. To find out: the same on stock upstream test images (`AUD_TARGET` 64, without POST); a diagnostic build on erreye's unit (offered) around the alt 0 flush; whether the port's bench can hold the flush pending.

## A marginal USB cable freezes the unit in DISK MODE

- **Symptom:** Entering DISK MODE, the first MSC bulk IN (EP 0x81) fails with a transaction error, then babble errors and 0 bytes; macOS resets the device about every 0.4 s; then every EP0 request times out and the unit is frozen. The same on OCTABAM3 (no USB CROSSBAR), OCTABAM4 and a BCR-only build.
- **Cause:** the cable. A generic 2 m cable mounts DISK MODE (32 GB FAT32) with 0 errors on OCTABAM3 and OCTABAM4. The MK1 (or this unit) is at the edge of the signal budget.
- **Fix:** a shorter or better cable, straight into the computer. Try one before treating a USB freeze as a firmware hang.

## An LFO design on tracks 2–8 changes after a MIDI scene lock or a page-2 scene lock (MIDI SCENES, SCENES P2) (open)

- **Symptom:** Found while checking whether PLOCKS P2 and MIDI SCENES can share a remix (radiohagen, Discord).
- **Cause:** both modules store their data at Part `+0x1712..+0x1832`, which stock uses for the LFO designer records of audio tracks 2–8 and MIDI tracks 2–8 (`docs/firmware/PARTS.md` section 9, measured under the port). MIDI SCENES writes its sparse blob (`+0x17a2`) once a Part holds MIDI scene locks and its freeze twin (`+0x1712`) on Part Save; SCENES P2 wrote its pool (`+0x17a2`) from the first page-2 scene lock. A track whose LFO WAVE is a designed shape (12–18 for T2–T8) then plays the module's bytes as its shape; the module reads a design the editor wrote as its own data.
- **Fix:** SCENES P2 keeps its locks in bytes 30 and 31 of the stock scene block (`verify_scenes_p2`); the old pool's bytes stay as the last image wrote them. MIDI SCENES: open; its storage is its author's. To find out: on a unit, a designed LFO on T2 before and after a MIDI scene lock and a Part Save.

## A cave at 0x400d24d0 changes the stock DELAY

- **Symptom:** `make check REMIX=octabam-experimental` with TAPE ECHO added: `verify_tapeecho_cpu` failed its stock-DELAY comparison with `stock delay changed track 1 frame 172 sample 10: 1079fe41/10b85bf1`. The failure reproduces with TAPE ECHO + SYNTH MACHINE alone and not with TAPE ECHO alone or with SIDECHAIN_COMPRESSOR.
- **Cause:** the stock DELAY routine reads `0x400d1ce0 + 4 * (x >> 6)` (`0x40003526`, `0x40003540`; stored into the track's delay state at `+20` and `+24`). The table has 508 entries and ends at `0x400d24d0`; at a slow tempo with a long TIME the index reaches 508 (51 BPM in the gate). In the stock image the words after the table are zero. SYNTH MACHINE's page cave is pinned at `0x400d24d0`, so the DELAY read `0x20300c00` there. Single-stepped: the write at `0x4000354e`, `a3 = 0x400d24d0`, `d0 = 0x1fc`. The LP pole's index is `(BASE + WDTH) >> 6` (`mvs.w 8(a0),d0 / add.l d1,d0 / asr.l #6` at `0x4000353c`), up to 1016 with both knobs at 127, and the boot init at `0x40002f44` reads entry 1023; the whole run `0x400d24d0..0x400d2ce0` is table data (entries 508..1023, zero in stock). Measured by Zac under route-A on OT DEMO: entries 508 and 764 read; read here from the stock bytes. `octabam-core`, `-bus` and `-inserts` leave them zero.
- **Fix:** `SYNTH MACHINE`'s `PLACE` setting (`timhastie.synth`, `DRAM` by default; `CAVE` is the author's bytes): `DRAM` links `page.s` into the platform runtime and the resolver at `0x40031ece` is a detour; the zero run is left alone. With `PLACE = DRAM` the TAPE ECHO + SYNTH MACHINE remix passes `verify_tapeecho_cpu`, and the synth PLAYBACK and LFO pages render pixel for pixel as the cave form's (port, `remixes/test/octatrick`). The DRAM form has no author reference bytes and is not on a unit.
- **Gate:** the stock DELAY carries a `Keep` on `0x400d24d0..0x400d2ca8` (`tools/remix/stock.py`; the first 16 bytes only). The run's tail `0x400d2ca8..0x400d2cdd` is SCALE QUANTIZER's pinned `qzs` and `qzk` (Tim Hastie's fixed addresses) and stays exposed until they move: inferred, DELAY reads `qz_pkey` at BASE + WDTH = 253 and `qz_pmask[1]` at 127/127 while CHROMATIC keys are held on a synth track (`stock.DELAY_KEEP_END`): the ledger refuses any module's write there, and the build asserts the finished image, in a remix that lists DELAY. `selftest` has the case; `tools/verify/tests/test_synth_place.py` has SYNTH MACHINE's. CX OSC pins a cave at `0x400d24d0` and will be refused beside DELAY until it moves.

## The unit freezes when it takes the card back from a Mac that holds it mounted read/write (open)

- **Symptom:** `octabam-bus` builds (the image running at each freeze was not recorded), one USB cable to a Mac, the card mounted by DISK MODE. Twice the whole machine stopped answering (no buttons, screen frozen) after DISK MODE was left on the unit with the Mac volume still mounted: 07:46:31 on the MIDI sync menu, and 08:14 on loading a project. Left once the same way with the volume idle (unmounted by `diskutil` two minutes later) it did not freeze.
- **Measured (macOS unified log, `log show`):** at 07:37:58 the Mac's pending WRITE(10) got `NOT READY / MEDIUM NOT PRESENT` (sense `02/3A/00`) and both bulk endpoints stalled; the Mac retried the same write for nine minutes (1 s growing to 1 min apart); at 07:46:31 the volume disappeared (`media is not present`). The second time, a write issued 14 s after a `diskutil mount` (08:12:16) failed the same way, retries ran 08:12:30 to 08:14:03, EP0 control requests then timed out (`0xe00002d6`) and the Mac reset the device at 08:14:10.
- **Cause:** open. The pending Mac write is the common factor; a truncated project (17 of 96 files short on the card after the first event) was ruled out as the only cause by the second. Whether the unit's USB stack hangs on the retries, or the freeze is the unit's card access colliding with the USB mass storage, is not known.
- **Workaround:** unmount the volume on the Mac and leave it unmounted before leaving DISK MODE; verify a copy with a fresh read (`sync`, unmount, mount, `cmp`), not the Mac's cache.
- **To find out:** the PC-sampler vendor request (a ring of the frame interrupt's interrupted PCs, read over EP0) while the Mac retries a write; the same with the module's USB MSC off.

|  |

## A layout past the DSP's frame budget leaves the audio engine degraded, the panel responsive (open)

- **Symptom:** `octabam-inserts` image I1, project MXPRED_01 under `tools/hw/ot_matrix.py run`. Layouts 1-3 (pairs at 85.7, 85.4 and 81.8 % busy on core 0) ran and matched their predictions (sum of the single-effect slot costs) to 0.1 point. Layout 4, SPECTRUM FX1 + LOFI2 FX2 at `dear` on all eight tracks (predicted 105.3 % core 0, 97.7 % core 1), was followed by 18 layouts in which the USB audio capture delivered nothing and LOAD METER read the same 81.9 / 74.3 % busy under every program change and STOP.
- **Measured afterwards (LOAD METER over USB, 09:58):** the frame interrupt ran 690 times per 0.5 s window (nominal 1,379); the DSP's frame count advanced 696 per 0.5 s (nominal about 1,400); ColdFire share 14.2 %; USB audio-out counters `underruns` 379,795, `reprimes` 44,518, `overruns` 3. The USB device, MIDI and EP0 still answered. Sam: the unit was not frozen (panel responsive) and its frame-overload log showed overloads. START then produced no sound on the USB audio capture: channels 1-2 stayed at about -85 dBFS in idle, play and tail (10:03).
- **Boundary (same day):** TRANSIENT FX1 + LOFI2 FX2 at `dear` ran clean at 98.2 / 90.6 % busy (frame interrupt 2,756 a second, no gap). EUCLID FX1 + LOFI2 FX2 at `dear`, 95.8 / 88.2 % busy, did not: the frame interrupt median was 2,560, 2,596 and 2,560 a second in three runs (6 to 7 % under nominal) and the capture had a silence of over a second at 9.75 to 10.5 s in each, recovering by itself. EUCLID adds about 7 points of ColdFire share. So the limit is not DSP busy alone; whether the ColdFire side of EUCLID, or the sum, is what costs the frames is not known.
- **Indicator:** LOAD METER's `bad` count (DSP records that failed their checks) is 0 in every layout but this one: 2,952, 2,939, 2,936 and 2,959 in the four runs of EUCLID FX1 + LOFI2 FX2 `dear` (25 runs of other layouts: 0; the frame-interrupt median shows only 7 % low in the same window). Seven EUCLID FX1 pairs at 42 to 81 % busy ( `euc01`) ran with 2,756 interrupts a second and no gap, predicted to within 0.7 point.
- **Cause:** inferred. The load was past what the DSP does in a frame, it missed the frame and waited for the next (CF METER's late-frame signature, `modules/cfmeter/README.md`), and the loop then stayed at the doubled period. Nothing tried since (program change, STOP) changed it. No single-slot layout had gone past 98.8 % busy; none of those overloaded.
- **Fix:** none. `ot_matrix.py` flags OVERLOAD (the frame interrupt under 80 % of 2,756 a second) and stops the run; `predict` leaves layouts predicted at 100 % or more out unless `--include-overload` is given.
- **To find out:** whether a power-cycle clears it (expected); what BRAIN > LOG > EVENTS recorded; whether the unit recovers when the load drops below the budget without a power-cycle; where between 98.8 and 105 % it starts.

## The DSP's frame count stops while the ColdFire and USB keep running

- **Symptom:** `octabam-inserts` image I1, three times through LOAD METER over USB: 10:40 after the fourth run of EUCLID FX1 + LOFI2 FX2 `dear` (the frame count `lm_dsp[0]` constant at 4,189,348; the frame interrupt still ran 2,756 a second but with a mean of 0.6 µs; `bad` 14,701); 11:03 after `ot_matrix.py switch` had sent program changes during play between layouts of MXEUC_01 (frame count constant at 7,090,409; the ColdFire share 69 %); and after the 10:0x overloads. Each time the panel and USB answered.
- **In the 11:03 run:** BASE to TRANSIENT FX1 + LOFI2 FX2 (98.2 %) and back took effect at the pattern boundary (load 22.5 to 98.2 % to 22.5 %). The next two program changes (to EUCLID FX1 + CHARACTER FX2 and back) did not: the load stayed at the starting layout's. The two after that started on the wrong layout (69.7 % constant), the DSP already stopped. Whether the mid-play changes caused the stop, or the unit stopped between them, is not known; the raw series was not kept until after this run.
- **Idle recurrence, 17:23:** after a power-cycle at about 16:32:25 and a 25-minute `mix` stress run that ended 17:19 (0 bad records), the unit was left idle under `ot_watch.py`. `lm_dsp[0]` stopped at 8,388,607 (2^23 - 1) and `lm_stats` at 6,083, 3,044 s after boot (8,388,607 / 2,756.25 per second = 3,043.6 s; the log shows the last advance at 17:23:15). Both counters stayed frozen through 17:27:45 (the last log line). The three 10:40 to 11:03 stops were at 4,189,348 and 7,090,409 frames, not at 2^23 - 1. Whether the earlier stops and the idle one share a cause is not established.
- **Cause of the idle stops:** LOAD METER's own DSP frame count (`x:(r1+6)`, core 0). At 8,388,608 frames the load sign-extends A2, `and #>$f` leaves it and `move a,n1` limits the OTOP slot index; the cost read goes to a wild address (docs/contributing/TRAPS.md#trap-frame-count). The 07:41 stop on 25 Oct was at `lm_dsp` seq 8,388,607 again (`lm_stats` 6,082). Image P1 (ColdFire seq preset to 8,388,000) stopped at seq 16,776,607 = 8,388,000 + 8,388,607, so the stop follows the DSP count and not the ColdFire seq. Image Q1 (DSP count preset to 8,388,600) stopped at `lm_dsp` seq 7 within seconds of boot, with `bad` 2 and `lm_stats` seq 0. Image Q2 (same preset, count wrapped at 2^23) ran on: seq 75,868 to 131,060 over 25 s. Unconfirmed: that the wild read stalls the DSP core; the port reads zero there and keeps running.
- **Fix:** dsp_meter.asm wraps the count at 2^23. **Gate:** `verify_load_meter` `wrap` builds with `LM_FRAME0` = 2^23 - 1000 and checks every OTOP slot is sampled and the costs read (0 without the fix).
- **Fix verified on the unit:** image I4 (the wrap) ran a 56-minute `ot_fuzz.py` `mix` sequence (seed 21, 4,546 operations) with no failure and was healthy at 67.5 minutes after boot (`lm_dsp` seq 11,162,914; the unfixed image stopped at 8,388,607).
- **Not explained by this:** the 10:40 and 11:03 stops, at 4,189,348 and 7,090,409 frames, after overload and mid-play program changes.
- **Stop on image J1 after the wrap, no overload:** Sam's MKII, `octabam-inserts` J1 (the wrap included), project SCJ4 loaded, the DSP's frame count constant at 25,011,824 (2 h 31 min of frames at 2,756.25 a second after boot; `bad` 2 since reset; `lm_stats` seq advancing, the frame interrupt at 2,756 a second with a share of 0.2 % where it had been 28.9 %); MIDI in and out kept working. Last healthy reading: the end of a 604 s `pc` run at 17:55:55 (`load_meter.healthy()`, 0 bad records, DSP busy 48.6 / 41.0 %). First failed reading: 18:55:37, at the start of an `ot_fuzz.py run`. The stop therefore fell between 18:37 (J1 was flashed about 16:06, 9,074 s of frames earlier) and 18:55:37. Between 17:55 and 18:55 the unit received only MIDI (crossfader sweeps at 200, 50 and 20 ms per step with the transport stopped and playing, a replay of the first 25 s of a `xf` sequence, a stop and a program change) and LOAD METER polls (0.5 s, in some sweeps); no layout change, no audio-track effect change. LOAD METER was last read healthy before the stop, so the stop was not observed. Cleared by a power-cycle (about 18:58). Not reproduced afterwards on the same image and project: the unit ran about 12 hours (DSP count 118.8 million at 06:56 on 26 Oct, past 25,011,824 at about 21:30 and past 2^23) with `ot_watch.py` sampling, 480 samples idle (19:21 to 23:21), then four repeats of the 18:46 to 18:55 MIDI activity (sweeps stopped and playing, with LOAD METER polling, audio capture and both, a stop, a program change, scene and crossfader CCs, a replay of the first 25 s of an `xf` sequence; 23:21 to 23:50, `healthy()` true after every step, 600 samples at 10 s to 01:01), then 710 samples idle (01:02 to 06:56): no `STOPPED` and no "no answer" line. The cause is not established.
- **Cause:** open. **Check:** `load_meter.healthy()` (the frame count advancing at about 2,800 a second) before every layout and transition; `ot_matrix.py` stops when it fails.

## A generated test project plays a sample wrongly: collapsed trim view, jumpy playhead, a probe's output corrupted by one effect

- **Symptom:** `test/ext-probe` image X1, projects built from the `EMPTY` template with a sample on T8: the SRC TRIM view showed the start and end markers together at the left edge and the playhead jumped. After a note trig, with FLANGER on T8's FX2, the probe track's output (EXTPROBE on T1's FX1) stopped decoding (all samples positive, 0 frames; one capture read 8,522,308 differing words in a 15,779-word region). SPATIALIZER, CHORUS and COMB FILTER did not do this with the same trig.
- **Cause:** the T8 slot was a STATIC slot (14) copied from a song project, with no trim record in `markers.work` and `TSMODE=2`. Stamping the projects for the remix and setting `TSMODE=0` did not clear it (`MXSG2_*`). A FLEX slot with `TSMODE=0`, `LOOPMODE=1`, a `BPMx24` and a markers record of (0, frames, 0) did (`MXSG4_*`: trim view looked right, FLANGER ran with signal, the probe decoded 27,501 frames). Why only FLANGER corrupted the probe on the bad setup is open.
- **Also found:** the template's `MIDI_TRANSPORT_RECEIVE` is 0, so MIDI Start does nothing until it is set to 1 in `project.work` and `project.strd`. `ot_matrix._stim_text` removes every following `[SAMPLE]` block when the project's blocks have no blank line between them, as in a cloned project.
- **Fix:** write the sample as a FLEX slot with its trim record (a `[SAMPLE]` block with `TSMODE=0`, `LOOPMODE=1`, `BPMx24`, and a `markers.work` record of `>III` (0, frames, 0) at `0x16 + (slot - 1) * 784`, checksum refreshed), set transport receive, and write the `.strd` twins. `tools/hw/ot_sampleslot.py` writes all of this.

## A flashed image boots into an old image: the card remembers the last REMIX SWITCH choice

- **Symptom:** Sam's MKII. A card used for several test images booted through MAIN MENU > BRAIN > REMIXES; then `OCTABAM H1` was flashed and loaded. The unit did a double boot and ran `COST-H CH`: LOAD METER answered, the DLPUMP block (the pump diagnostics) was refused, and a MODULATION track read a dry slot. The pane showed `FLASHED` as `OCTABAM H1` and the running image as `COST-H CH`. Two rounds of unit tests were run on the wrong image before this was noticed.
- **Cause (the module's README, read, and the symptom):** REMIX SWITCH saves the last image picked in a card blob (`octabam.remix-switch` in `BRAIN/card.work`); the flashed image reads it at power-on and switches before the project loads. It follows the card, not the project, and not the name length (`COST-H CH` is 9 of 15 characters).
- **Fix:** select the name under `FLASHED` in BRAIN > REMIXES (clears the choice), or hold FUNC at power-on and choose EXIT in the STARTUP MENU for one boot. After flashing, check the running name against the flashed one before trusting a measurement; `tools/hw/dl_state.py` and the logo's name both show it.

|  |

## DARK REV picked on T4's FX2 while a demand effect's code is in T4's block stops the DSP frame loop

- **Symptom:** Images `octabam` H1 to H3. Project `MXHOME_A`: MODULATION on T1's FX1, T3 and T4's FX2 on the stock DELAY, a noise loop on T1. Sequence: T3's FX2 to DARK REV (the pump moves MODULATION from T3's block to T4's), T3's FX2 to DELAY, T4's FX2 to DARK REV from the chooser. Within about 4 ms of the pick the DSP frame loop stops (the ColdFire frame-interrupt count, the DSP meter sequence and the pump's call counter stay constant; USB and the panel answer). 3 of 3 runs. The unit needs a power cycle.
- **Cause:** payload B's frame routine writes `x:$3f7f..$3fbf` every frame; the guard kept its per-instance buffer bases at `x:$3f90 + idx` (T3 idx 40, T4 idx 43). The late resume of a dry reverb ran DARK REV's init and proc on a scratch value as the base. Payload A does not write there: T7 and T8 were unaffected. [The trap](TRAPS.md#trap-stock-x-scratch) has the evidence.
- **Diagnostic builds, one run each on the same sequence (the tags are image names):**

| build | after the code leaves T4's block | result |
|---|---|---|
| H1 to H3 | late stock init, then the stock proc in the same call | stop |
| H4: guard always reports an overlap | the stock reverb never runs | no stop |
| H5: a dry instance stays dry | the stock reverb never resumes | no stop |
| H6: late init, then dry for good | init only | no stop |
| H7: late init, stock proc on the next frame | proc runs | stop |
| H8: stock proc for one frame, then dry | proc runs once | stop |
| H9: stock proc 100 frames after the late init | proc runs | stop |
| HA: buffer words from base + `$3800` to the extent zeroed before the late init | proc runs | stop |
| P1, P2: probe images, guard as in H1 | proc runs | stop |
| P4: guard cells at `x:$3dc0 + idx` and `x:$3e00 + idx` | proc runs | no stop, 3 sequences |

- **Probe readings (DLPROBE on T2's FX1, recorded over USB, [`modules/dlprobe`](../../modules/dlprobe/README.md)):** on P2 no guard instance other than T3's held a state of 1 to 3 in the last 0.33 s before the stop. On P3 (T3's pick only) the base cell `x:$3fb8` read `$ffb754` after a reboot and again after the guard's init; the allocator entry `$25a` held `$38000`. On P4 T3's base read `$038000` and T4's (entry `$25c`) `$03c000`; T4's state read 2, then 1 after the pump's move.
- **Not established:** what `func_00034f` computes, and whether another writer touches `x:$3dc0..$3e3f`. The stub's flags at `x:$3f00..$3f3f` are that routine's input.

## Sequencer stuck at play with a stock fallback: id 0 ran FILTER on every empty FX1 slot

- **Symptom:** The owner's unit, a 50-module selection with
  `fallback="FILTER"` built with an unmerged build change that pointed id 0's
  DSP init and proc at the stock effect's entries: PLAY lit one step and held
  it (sometimes 2, then 1), no audio. The same selection with
  `fallback="NONE"` (id 0 left on the null stub) played, with the same project
  and no `stamp-defaults` between the two: the image was the only change
  (owner report).
- **Cause (unconfirmed):** FX1 NONE is id 0 (see "Sequencer stuck on step 1
  with every effect turned off: id 0 is SEND"), so the image ran FILTER on
  every empty FX1 slot as well as every unassigned FX2 slot. Which part wedged
  the frame (an init that never ran on those slots, a page byte the last effect
  left, the cycles of up to eight extra instances per core) was not measured.
- **Fix:** `registry.remix` refuses a stock effect as the fallback: `NONE`,
  `SEND` or a module the remix carries. Before this the build also crashed on
  a stock fallback (`fb_init` unbound) as soon as a registry module was left
  out, so no image with one had reached a unit.

## CX OSC in the image: the DSP frame loop stops when a host reads the USB audio, with a continuous clock and a program change before START

- **Symptom:** `ot_matrix.py run` on `OCTABAMS1` (octabam at `5f8e779f` with MODULATION, SPECTRUM,
  CHARACTER, TRANSIENT, DISTORX and SIDECHAIN_COMPRESSOR demand-loaded, and the 14 extra ColdFire modules), `SFX_01`
  from `ot_suite.py build`. `fx01` stopped at layout 3: `rms -43.7`, CoreAudio `err=-10863` on the host, then
  `USBError [Errno 19] No such device`. The unit was frozen and needed a power-cycle. Three further `--only` runs: `0,3` clean, `0-3` and
  `0,1` (BASE, then FILTER FX2 def) stopped it; the level fell to about -45 dB first.
- **After a stop:** `load_meter.healthy()` gives "the DSP's frame count advances 0 a second" while the frame interrupt
  runs at 2,756 a second; every LOAD METER figure is then stale. The input LEDs A, B and D were solid yellow or
  orange (Sam), the display worked, the sequencer froze on step 1 at PLAY. The LED reading is inferred to be the
  input levels frozen with the DSP; not checked.

| clock | host USB audio capture | program change | cycles | stalls |
|---|---|---|---|---|
| continuous (one thread) | open (20 ch, TRACKS PRE) | alternating 0 and 1 | 5, 2 and 1 (three runs) | 3, at 0.035 s, 1.2 s and 0.048 s after START (the last with TRACKS OFF, 4 ch) |
| continuous | none | alternating | 20 | 0 |
| continuous | open | 1, every cycle | 20 | 0 |
| continuous | open | none (STOP and START only) | 12 | 0 |
| restarted per cycle | open | alternating | 11 (a stall in cycle 0, then 10 clean) | 1 (8.04 s after START) |
| restarted per cycle | none, or open with 6 s of play | alternating | 10 and 10 | 0 |

  A stall is either the record count stopping or a LOAD METER read timing out (`Errno 60`).
- **Bisect** (recipe, 20 cycles, TRACKS PRE; `remixes/test/` names in parentheses). Stalled: `OCTABAMS1`, `N1` (without
  SIDECHAIN_COMPRESSOR), `T3` (stations only), `P1` (without PATTERN MUTE), `Q1` (`L1` plus OCTA303, MORPH, FX2 LOCK,
  CX OSC: the DSP stopped about 3 s after it started, before any probe), `Q2` (`L1` plus OCTA303 and CX OSC: at the first
  program change). Clean (2,756 records a second): `F1` (27 Oct), `L1` (`F1`'s module list on today's code), `H1`, `Q3`
  (OCTA303 alone), `X1` (all 14 extra ColdFire modules but CX OSC), `Y1` (`OCTABAMS1` without CX OSC), `R3`. The
  stalling images read 2,745 to 2,748 records a second at rest.
- **Established:** CX OSC is in every stalling image and in none of the clean ones; `OCTABAMS1` without it (`Y1`) is
  clean. TRANSIENT, DISTORX and SIDECHAIN_COMPRESSOR are not implicated.
- **Not established:** the mechanism (CX OSC chains its machine row with OCTA303 on DRAM, `HOOKS machine_rows`); whether
  CX OSC alone stalls (`Q2` had both); why the host's audio capture, the continuous clock and a changed program are
  all needed.
- **Fix:** CX OSC is out of `octabam` ([the 0.1 scope](../../remixes/octabam/README.md)).

## Interface locked while the audio keeps playing; four or more OCTA-303 machines

- **Symptom:** `OCTABAMP1`: with four to eight OCTA-303 machines the panel stopped answering while the audio played; with trigs on step 1 of all eight tracks the unit stalled (seven starts did not). The USB meter kept answering in the first case.
- **Measured (LOAD METER, one MKII, meter only, fresh start, `v0.2`):** frame-interrupt share 25.3 % with nothing playing; 2 machines 65.5 %; 4 machines 83.2 %; the live log of a locked panel read 97.7 % with a mean interrupt run of 354 us against a 362.8 us frame, interrupts 2,756 a second and the DSP counter advancing. Machines that had not been started cost nothing (0 to 6 read 25.3 %). Trig density did not matter (every step, every fourth step, all but step 1: 80 to 82 % at four). Eight simultaneous step-1 starts: boundary run 513 to 516 us.
- **Cause (unconfirmed):** the frame interrupt leaves the UI task about 2 % of the CPU near 98 %. A model of about 21 points once any machine plays plus 9.3 per machine gives about 102 % for six. Not shown: what the 21 points are. The position write-back removed in two test images (`P1`, `P2`) saved 14.8k instructions a frame in the port and nothing on the unit's share for signed machines.
- **Fix:** OCTA303 allows two machines in a Part (`O3_MAX`): a third pick is refused with a toast, and the Part validator unsigns a third signed track of a loaded Part (it becomes FLEX). Port: `verify_octa303_ui`. Image `OCTABAMP3` (the render limit only), one MKII: four stamped machines read 72.1 % against 83.2 % on `v0.2`.

## FX2 chooser: picking an effect does nothing in `octabam`

- **Symptom:** Selecting an effect on FX2 changes nothing.
- **Cause (from the code):** FX2 LOCK was in `octabam`'s `COLDFIRE` set. It points YES's key-table entry at NO's handler, so YES closes the chooser and the select handler never runs. `modules/fx2-lock/README.md`: made for bottleservice; "On the unit: Not yet"; `verify_fx2_lock` ran on bottleservice only.
- **Fix:** FX2 LOCK is out of `octabam`; `octabam-bus` keeps it. Sam's MKII, image `OCTABAMV5` (`octabam` with VARISPEED, no FX2 LOCK), FX2 picks take effect. The failing image was not re-flashed to reproduce the symptom, so the cause is the code reading plus this result.

## Program changes left unapplied in a loader soak (open)

- **Symptom:** in a soak of program changes between MODULATION, PLATE REV and
  BASE (the change sent during play, landing at the pattern end), a few of 32
  changes do not apply: the DSP keeps the previous layout. Most are BASE to
  MODULATION.
- **What moves it:** the count rises with the number of extra ColdFire modules
  in the image. STEM REC, VARISPEED, SCOPE, MIDI SCALES and RND NAME each raised
  it; CX OSC with all the extra ColdFire modules made the unit stop answering
  USB. With STEM REC, a BASE to MODULATION switch during play also stopped the
  DSP's frame count.
- **Common to every image:** about 340 ms of silence and a ColdFire spike to
  440-500 µs (136 % of the 362.8 µs frame) at every applied switch.
- **Fix so far:** STEM REC, MIDI SCALES and RND NAME are out of the released
  remixes, and SCOPE is only in Octabam; the demand loader's copy loop, repeat
  and pump were reworked.
- **Open:** whether the load, the USB MIDI receive path or a hook drops the
  program change; why a change landing during play is needed.

## The DSP's frame exchange stops at START or a program change: the frame interrupt after a long one enters about 150 µs late

- **Symptom:** `octabam` builds A1 and E1 and the `_hw-oct-pre` control C1, a USB audio capture
  open. The sequencer holds step 1 at PLAY, LOAD METER's DSP count is constant, the frame-interrupt count stops 3 to 5
  above it, the panel and USB answer; a power-cycle clears it. First START after boot and load: 5 of 8 (A1 and C1, 20
  channels), 5 of 8 (E1, 4 channels); program changes: 1 in 27 (E1, 20 channels). No capture: 0 in 13 first STARTs
  and 64 program changes.
- **Measured (frame log, `tools/hw/framelog.patch`, read by `tools/hw/ot_stall.py`):** the transfer chain's last
  state comes 224 to 245 µs after the frame interrupt's entry on every frame. The START frame interrupt runs 473 to
  481 µs with no capture, 488 to 527 µs with one. The next entry 128 to 149 µs late: one back-to-back frame
  interrupt, runs on (8 STARTs). 155 to 223 µs late: one frame skipped, runs on (23). The two stalls logged: 149 and
  155 µs late, two back-to-back frame interrupts, the second 16 and 36 µs before its grid time, then none.
- **Inferred:** at that lateness the transfer chain is still sending when the DSP starts its next frame (a core A log
  from a STALL PROBE build reported a 513th word in the 512-word block).
- **Fix:** FRAME GUARD (`modules/frame-guard/README.md`), in `octabam`, `octabam-bus` and `octabam-verbs`: 32 first
  STARTs and 192 program changes at 20 channels without a stall. **Gate:** `verify_frame_guard`.
- **Open:** on the test image with 60 µs added and 20 channels (frame interrupt 91 % of the ColdFire), 1 of 16 first
  STARTs stalled with the next entry 209 µs late, and 7 of 16 froze the whole unit 8.2 s after START at the pattern's
  wrap; not seen without the added delay. `octabam-bus` and `octabam-verbs` not run with the guard. The whole-unit
  freezes, the USB device absent after a REMIX SWITCH double boot and the boot freezes of 12 Nov are not explained by
  this. Audio through the skipped frame is not measured.

## DSP stall after a demand load during play: the copier ran at the frame head, between core B's two handshakes with core A

- **Symptom:** 12 to `octabam` with FRAME GUARD, 20-channel USB capture, sequencer playing. A
  program change at a pattern wrap switches the tracks to a demand effect that is not loaded (SPECTRUM and
  SIDECHAIN_COMPRESSOR logged; none after a switch to MODULATION). The audio stops, the panel and USB answer, a
  power-cycle clears it. `ot_fuzz.py` profile pc, seed 3101 (`ot_suite.py` phase kits-identity, 76 changes and about 21
  loads in 10 min) on `SFX_01`: a stall in roughly 2 runs of 3 on eleven test images; the longest clean streak was 3
  runs.
- **Measured (frame log, and test images that read the stalled DSP; the window read-back is `tools/hw/dlprobe.patch`, read by `tools/hw/dl_probe.py`):**
  - The pump's last chunk, two frames with the doorbell due, the doorbell, two more frame interrupts, then none. Every
    frame on the grid, none bad, none held by FRAME GUARD.
  - Core A takes host commands and sits at `P:$a3`, its wait on the link to core B. Core B takes no host command.
  - The loaded effect's entry is BOUND, published = received, refused 0. Its words in the window equal the staged
    block, and the resident code equals the image.
  - Core B's last frame: its frame-start hook ran, it left the copier, passed the second link wait and reached
    `P:$268` in the first track; it entered no effect slot. The frame before was 18 % busy.
  - A core in the illegal-instruction trap answers host commands with `P:$04`; core B's stack-error vector was not
    taken (a flag set there read clear).
- **Not known:** what core B does between `P:$268` and `P:$2a7` in that frame, and why binding is needed (the copy
  alone at the same place did not stall).
- **Fix:** DLCOPY's hook moved from `P:0x76` (the frame head) to `P:0x342` (the frame's end, before the jump back to
  the frame wait). The same test image with only that change: 12 runs of 12 without a stall, 251 loads.
  **Gates:** `verify_dlstub`, `verify_dlhook`, `verify_dlwrap`, `verify_dlload`; none of them can see this fault (the
  port and `dsp_host` run one core).
- **Open:** one stall with no loader activity, the same end state (core A at `P:$a3`, core B deaf): a program-change
  frame of 564 µs with the next entry 205 µs late, past FRAME GUARD's 190 µs. One whole-unit freeze on an image that
  never binds (panel frozen, USB gone), cause not established. 27 to 35 bad DSP records per 10 min at pattern wraps
  while MODULATION's code runs, with and without this fix.

## Stopped on the boot screen after REMOTE's COMMAND 3 booted an `.RMX`: most often with a stalled DSP

MKII, image N1 (`octabam` with REMOTE, commit 95e52aee). COMMAND 3 for `OCTABAM N1.RMX` was
taken; the unit reset, showed the boot screen and did not return to USB in 150 s. A power-cycle recovered it.

- Before the command, in that boot: the first boot after flashing N1, the project loaded from the menu, PLAY
  from the panel, a MIDI START, two program changes and a STOP, COMMAND 1 and 2, COMMAND 4.
- The host polled for the device from 3 s after the command.
- Nine later COMMAND 3 boots returned: five with 20 to 75 s of host silence, four polled from 3 s; two of
  the four after the same sequence from a menu load and a panel PLAY, one of those the first boot after
  flashing N1 again.
- Not tested: the same file booted from BRAIN > REMIXES in that state; the card's state at the time (it was
  the first selection REMIX SWITCH saved from this image).
- Second sighting, MKII: COMMAND 3 for `OCTABAM 05.RMX` (`octabam` at `5b991c85`) from image N1 (the
  same N1 image as the first). Taken; no USB device at 30 s; the unit showed the boot screen and was power-cycled,
  and it came back on N1. The same file picked from BRAIN > REMIXES on the panel booted `OCTABAM 05` (build tag `05`
  in the effect names). Later COMMAND 3 boots, all from BUILD 05 images: octabam to verbs, verbs to bus, bus to
  octabam, octabam to bus: 4 of 4 returned (`tools/hw/ot_card.py boot`).
- Third sighting, MKII: COMMAND 3 for `OCTABAM 05.RMX` sent from `octabam` BUILD 05 while its DSP frame count was
  stopped (the entry "DSP frame count stops 27 minutes into a mixed program-change sequence" below). No return in 150 s;
  power-cycled. The first sighting from a BUILD 05 image.
- **Pattern, 18 to (from the session's notes and the saved run logs; no complete count exists, because the retry of a failed boot skipped the
  per-run logs; `ot_card.py boot` now writes every attempt to `out/hw/boot_ledger.tsv`: time, image asked for, the unit's state before it, outcome, seconds):**
  - the 39 COMMAND 3 boots in the saved run logs all returned, on units whose DSP was counting;
  - a COMMAND 3 sent while the DSP was stalled did not return or fell back to the flashed image N1 in most of the attempts I noted (not counted:
    boot-screen freezes needing a power-cycle, and fall-backs that the image-name check caught: `OCTABAM N1` running when another image was asked for);
  - from N1 it froze at least 3 times (15 Nov, 18 Nov, 20 Nov) and returned several times;
  - from a counting `octabam` unit it froze once (20 Nov, switching to `OCTABAM D3`), after a power-cycle and a healthy reading;
  The ring fingerprint and the boot screen's version string do not show a fall-back; `ot_card.py image` does.

|  |

## USB DISK MODE entered by COMMAND 1, the card never mounts on the Mac: a stale `diskN` after `diskutil unmount`

MKII, `octabam`, `octabam-verbs` and `octabam-bus` BUILD 05. After one DISK MODE session ended with
`diskutil unmount` and COMMAND 2, the Mac kept the device node (`diskutil list external` still listed `disk4`) and every
later COMMAND 1 left the card unmounted: the ring showed COMMAND and BANKW (the unit entered the mode), the disk-mode
flag (`0x460e76a0`) read 1 for 2 to 4 s and then 0, and the Mac mounted nothing in 60 s. 3 of 3 loads after the first
failed. `diskutil mount disk4s1` and `diskutil list external` hung until the cable was replugged. This was first logged
as `octabam-bus` leaving DISK MODE within 4 s; the same failure followed an `unmount`-based leave on the other two
images, so that reading is withdrawn.

- **Fix:** `ot_card.py` ejects the device (`diskutil eject diskN`) after the unmount and before COMMAND 2. 3 of 3
  consecutive loads then mounted and reloaded the project, each with the DSP's frame count advancing 0.4 s after the
  reload record. A first COMMAND 1 right after an image switch has failed once and mounted on the retry.
- **Not known:** whether `diskutil mount` hanging is the Mac's or the unit's USB stack's.

## DSP frame count stays at 0 after a project reload that follows a demand-loader phase

MKII, `octabam` BUILD 05 (`5b991c85`), 18 and. A project reload (`ot_card.py load`: DISK MODE, copy, COMMAND 2; the
NEWPROJ record arrives) after `ot_matrix.py switch` had run `loader01` (30 transitions, SFX_01) left the DSP's record count
(`dsp.seq`) fixed at 1,510,920 for the 90 s the tool waited and still fixed 20 minutes later, while the ColdFire frame interrupt
ran at 2,756 a second and the USB device answered. A second reload with the DSP in that state gave the same reading.

- **Seen 3 times:** 18 Nov, `octabam` after `loader02` (the next phase's start read 0 a second, three phases in a row); 18 Nov,
  `octabam-verbs` after `loader02` (90 s wait); 19 Nov, `octabam` after `loader01`, in a run built to reproduce it.
- **Not seen:** a reload directly after a boot (every one, on all three images); a reload after `fx01` to `fx04` runs (the loader01 load after `fx03`
  was fine); `pc-soak`, `kits-identity` and the scene phases after a boot and a load.
- **Recovery:** COMMAND 3 for the same image (`ot_card.py boot`): the count advanced 0.4 s after the unit returned. No power-cycle.
- **Not tested:** the same reload from the panel; a reload after `loader01` on `octabam-bus` (it has no loader phases); what state the demand
  effect's block is in when the reload comes (the phase ends on a SHATTER, CHARACTER or MODULATION layout); DLCOPY's counters
  (`dl_state.py`) before the reload.
- **Workaround:** `ot_suite.py run --auto --image "<NAME>.RMX"` boots the image again after each loader phase.

## The DSP stops when DARK REV is picked on the tracks while MODULATION is loaded (open)

- **Symptom:** with MODULATION loaded (in use on a track, or in the 10 s after
  the last track stops using it), a program change that puts DARK REV on all 8
  tracks, then START: the DSP's frame count stops. The sound stops; the panel
  and USB still answer; a power-cycle clears it. A reboot from the stalled unit
  can freeze on the boot screen.
- **What it needs:** MODULATION's code resident in T3's block. With SPECTRUM
  (T7's block) loaded instead, or nothing loaded, it does not stall. PLATE REV
  and SPRING REV in DARK REV's place do not stall. It stalls most often with
  DARK REV on all 8 tracks, less often on four, not seen on one.
- **What the frame log shows:** every START gives a 505 µs frame interrupt and
  a late entry held by FRAME GUARD; at the stalling START one more frame is
  skipped and the count stops five or six frames later.
- **Cause (unconfirmed):** DARK REV's inits (about 800 instructions each, four
  on core B) land in the START frames beside the loaded code's block. The guard's
  cells and its resume path are ruled out.
- **Workaround:** avoid DARK REV on many tracks in a song that uses MODULATION.
  Octabam Verbs has no stock DARK REV; Octabam Bus loads no effects on demand.
- **Open:** whether DARK REV's init or the frame timing is the trigger; whether
  CHARACTER, SHATTER or SIDECHAIN_COMPRESSOR do the same.
- **Guard in the build:** `build_bus.py` refuses a record inside a guarded
  reverb's slot extent, after a diagnostic build pushed the SIDECHAIN_COMPRESSOR
  stubs to `0x34000`, where DARK REV writes.

