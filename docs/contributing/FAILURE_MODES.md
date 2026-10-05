# Hardware failure modes: the register

Symptom → cause (measured, inferred or open) → fix. Add an entry the moment
a mode is seen on hardware.

`git show 666b6154:docs/remixer/FAILURE_MODES.md` holds the earlier text of
the entries that existed at that commit. These entries are newer than it and
are not in that blob: "PLAY or a sample load halts the unit in Octakit's
pattern-apply check", "Unattended halt in Octakit's Part-refresh wrapper",
"A BCR2000 goes dark or deaf", "Octakit stranded for the session",
"A bank file written by the unit that the firmware then rejects", "A UAC2
host stops audio setup", "A track button pressed within about 250 ms of a pattern
change halts in Octakit's Part-refresh wrapper", and every entry after the line "Entries from here to the end of the file (5 Oct 2026)".

## STOP, a pattern switch while stopped, PLAY halts in Octakit's pattern-event retry bridge, D0 = CORRUPT (image A5, bottleservice) 🔴 open

- **Seen:** Sam's MKII, image A5 (bottleservice at main `f80ecfea`, 5 Oct 2026, USB and the BCR2000 connected): `EXCEPTION SSP:4 VEC:04 FS:0 SR:2008 ADDR:45D27CBC D0:FFFFFFFA SP:460D8D34` = `gk_pattern_event_retry_corrupt_fatal` (`part_event_retry.S`, her bridge on the stock pattern-event refresh, D0 = `GK_ERR_CORRUPT`), after STOP, [PTN] + [TRIG] to A2 while stopped (A1 and A2 on different Kits), PLAY. The same stop/start habit ran on A4.
- **Cause:** open. Her bridge takes that `illegal` when `gk_ui_carried_pattern_lag_event_finish` returns CORRUPT (the current and primary pattern bytes disagree, or `gk_stock_current_context_validate` returns any negative, BUSY during a queue handoff included; STOP starts one) or `gk_ui_transition_context_retry_ensure` returns CORRUPT. Not reached by patch 0002, which touches the Part-refresh writer only. Under the port (A5 bus, `--mkii`, keys only), every variant ran clean on both the gate project and the 4 Oct Bottleservice26 backup: stop/PLAY, double stop/PLAY, fast, six repeats, a timing sweep, the session (A2, knobs, A1, A2, stop/starts), and six stop, switch-while-stopped, PLAY variants including a cold switch and three rounds. With BCR-like CC traffic on the port's MIDI in (24-message bursts around the stop, the switch and PLAY; a message every 40 ms through the sequence; page-1 knob edits before it) the same sequence ran clean on both projects; so did stop, switch, PLAY on the Bottleservice26 backup with the port's USB bench enumerated and streaming the master out (`--usb-host`, 121,718 IN transfers over the run). The BCR itself (its echo and its own CCs) is not modelled. Between A4 and A5 the image also took USB AUDIO OUT changes (#597, #602) and build changes (#603, #609, #612); A4's commit is not recorded.
- **Fix:** open. To find out: whether it recurs with USB and the BCR unplugged, and on A4; the same sequence under the port with CC traffic and the USB model; which of the bridge's two CORRUPT sources fired (a ring under the port, or her diag word `__gk_ui_transition_reserved`).

## A track button pressed within about 250 ms of a pattern change halts in Octakit's Part-refresh wrapper (a chain or a single switch) ✅ measured under the port, open on hardware

- **Seen:** a Discord user's MKII, bottleservice image 88 (Octakit c6d3f39), 5 Oct 2026: `EXCEPTION SSP:4 VEC:04 FS:0 SR:2009 ADDR:45D2DFEC D0:00000001 SP:460D8D3C` = `gk_pattern_queue_request_ipl_fatal` (Octakit's wrapper on the stock pattern-schedule request at `0x400a1030`, `queue_commit_deferral.S`), after two pattern trig keys pressed during a pattern switch, which makes a chain. Em's ems-octakit#5 (a chain playing, any track button, reported on c6d3f39 inside ok-ms, reproduced by her, no fix pushed as of 5 Oct 2026). The unattended BUSY halt below is the same wrapper's sibling fatal (`45D2803C`, workspace).
- **Cause:** measured under the port (`remixes/test/octakit` and bottleservice at main `4bdeaa79`, identical instruction paths), project OCTABAM89_setgate: PLAY, a queued pattern change ([PTN] + [TRIG] 2 or a chain of 2, 3, 4, both halt), then one track-button press at 17.05–17.275 s after the script start, where the playing-pattern byte (`0x800065be`) changes at about 17.1 s, halts at `0x45d28038` = `gk_stock_part_refresh_writer_report_fatal_part_refresh_fatal_context`; presses at 17.00 s and 17.30 s run clean (sweep at 25 ms steps). A press of the current track (T1) halts as well. PC ring: `gk_stock_part_refresh_writer+0xe8` after `gk_stock_current_context_validate` returned `GK_ERR_BUSY` (−3) at `+0x11c`: `__gk_sequencer_latch_queue_handoff` is set while the handoff is pending, `gk_stock_staged_audio_handoff_validate` and `gk_physical_validate` had returned 0, and the writer takes any negative as the context fatal. No octabam module references `0x400a1000`–`0x400a13ff`; the only SR writers outside Octakit are usb-midi's mask and restore pairs. The user's own fatal did not appear in 60 scenarios; its SR shows interrupt level 0 with N and C set, which excludes a caller in DRAM (PR #595's patch) and leaves the IPL, latch and guard-depth checks of the same handoff: a timing the lock-step port did not reach (inferred). Runtime addresses hold for every image since 15 Sep 2026: pins 7ba0ad6 and c6d3f39 have identical runtime sources, resolved with `m68k-elf-nm -n out/runtime/octakit/runtime.elf`.
- **Fix:** `modules/octakit/patches/0002-part-refresh-busy-runs-stock.patch` (5 Oct 2026, measured under the port, unflashed): on BUSY the writer runs stock unwrapped, as her QUIESCED path does (`modules/octakit/README.md` "Patches on her runtime"); every halting scenario and the controls end clean on both images, the unwrapped path seen running at the press. The user's `request_ipl` fatal is a different check in the same handoff and is not covered. Live script that halts without the patch (`ot_emu --mkii --live-script`, key codes from `tools/panel/key_map.json`: PLAY 0x28, PTN 0x2e, TRIG n = n−1, T n = 0x10 + n−1): `1500 key 0x28 down / 1560 up`, `3500 key 0x2e down / 3620 key 0x1 down / 3740 key 0x2 down / 3860 key 0x3 down`, release in reverse at 120 ms, `17250 key 0x12 down / 17310 key 0x12 up`, `22250 quit`. To find out: the window on hardware; whether the user's `request_ipl` fatal is the same press at another phase.

## PLAY or a sample load halts the unit in Octakit's pattern-apply check with a computer on USB (bottleservice, USB AUDIO IN CD) 🟡 inferred

- **Seen:** Sam's MKII, images 95 and 97 (bottleservice with USB AUDIO IN CD + USB CROSSBAR), 3–4 Oct 2026. `EXCEPTION VEC:04 ADDR:45D114DE` = `gk_stock_audio_pattern_primary_begin_report_fatal` in Octakit's runtime, on a sample load and on PLAY in a new project, with the USB cable to a computer. With the cable unplugged PLAY did not halt. Image 96 (without the two modules and without PLOCKS P2) loaded a sample without a halt; PLAY there with USB plugged was not tried.
- **Cause:** inferred from the cable test: something live only with a USB host breaks the state Octakit checks when the sequencer applies a pattern's Part (`gk_selector_begin_physical` fails outside her quiesced state). USB AUDIO IN does its per-frame work in the frame interrupt's state machine beside Octakit's audio patches. Not reproduced under the port (no USB host streams into it).
- **Fix:** USB AUDIO IN CD and USB CROSSBAR removed from bottleservice, 4 Oct 2026. To find out: PLAY with USB plugged on the image without them; whether USB AUDIO OUT MASTER (250 µs since 28 Sep; image 88 polled 1 ms) alone triggers it.

## Unattended halt in Octakit's Part-refresh wrapper, D0 = BUSY (image A0, bottleservice) 🔴 open

- **Seen:** Sam's MKII, image A0, 4 Oct 2026, evening: found halted with `EXCEPTION VEC:04 ADDR:45D2803C D0:FFFFFFFD` = `gk_part_refresh_abort_fatal_report_part_refresh_fatal_workspace`, `GK_ERR_BUSY` (−3), after being left alone with a BCR2000 on MIDI (CC FEEDBACK in the image).
- **Cause:** open. Her wrapper around the Part page writer found her Kit workspace busy when a Part write arrived with nobody at the panel. Under the port, none of these halted: Bottleservice26 playing 1,500,000 frames; playing with a CC on T8's FX1 every other frame for 60,000 frames; playing with one CC per frame round-robin over every track's FX1/FX2 page-1 and page-2 slots for 60,000 frames. The port has no BCR traffic and does not run her background Kit save on a timer.
- **Fix:** open. To find out: whether the BCR echoes a received CC (a loop: a p-locked step → CC FEEDBACK → BCR → the OT's Part writer); whether it recurs with MIDI IN disconnected; what her workspace was busy with (the return addresses on the stack at SP 0x460d8cf4 were not read).

## A BCR2000 goes dark or deaf on some patterns (A02, B1), fine on A01, C1, D1 ✅ measured, closed (4 Oct 2026)

- **Seen:** Sam's MKII, images A0–A3, 4 Oct 2026, BCR2000 on DIN both ways: on A02 no CC reached any track; on B1 every BCR LED went dark and C1/D1 stayed dead until A1; fine with the OT's MIDI OUT unplugged. Reported first as "MIDI stops reaching CHARACTER after a pattern copy and SAVE KIT".
- **Cause:** the OT's Program Change on a pattern change (PROJECT > MIDI > SYNC > PROG CH SEND; seen on the AMT8 capture as `C0 xx` beside a song-position pointer). The BCR2000 selects its preset from PC 0–31: A01 → PC 0 → preset 1 (the layout), A02 → PC 1 → preset 2 (empty), B1 → PC 16 → preset 17 (empty, dark); C1 (PC 32) and D1 (PC 48) are out of range and ignored, so the BCR keeps whatever preset it had. Not reproduced under the port, whose captures of the OT's output carry the PC but have no BCR on the other end.
- **Fix:** PROG CH SEND off on the OT (Sam, 4 Oct 2026). Alternatives: the layout written to all 32 BCR presets (`tools/hw/bcr2000.py`), or a PC filter on the path to the BCR. Found on the way: CC FEEDBACK reported the live lane's lock rewrites at step rate and had AMP/LFO swapped (#583), and dumped a Kit change in one burst (#584) — both fixed, neither was this.

## Octakit stranded for the session after a bank file fails to load: pattern paste halts, every Part apply is skipped (silence) ✅ measured under the port

- **Seen:** Sam's MKII, images 95–99, 3–4 Oct 2026: songs played silent (meters still), and a pattern paste in a fresh project halted with `EXCEPTION VEC:04 ADDR:45D1364E` = `gk_current_pattern_part_set_fatal`. Booting with the remembered project missing from the card halted at `45D173EE` = `gk_stock_empty_project_runtime_initialize_report_fatal`, D0 = −3 (BUSY).
- **Cause:** measured under the port (Octakit alone). Octakit's lifecycle word (`__gk_lifecycle_state`, `0x45f85c84`) is set QUIESCED by boot init, empty-project init and every bank load, and cleared only by `gk_lifecycle_activate_current` after the load's post step. When the stock bank load returns an error (a bank file the firmware cannot parse, −51; a missing project, −12) `gk_stock_banks_load_work` returns at its error exit without activating; stock carries on with the bank it initialised, Octakit stays QUIESCED: `gk_stock_pattern_payload_store` halts on the next paste and the sequencer's Part apply takes her quiesced path. On Sam's card the remembered project (`PROJECT 261004p`) had a `bank01.work` the firmware rejects (below), so every boot into it stranded the session. A project load or CREATE EMPTY PROJECT that succeeds re-activates (measured; on the unit the paste worked after a project change).
- **Fix:** `modules/octakit/patches/0001-banks-load-error-applies-current-bank.patch` (5 Oct 2026, measured under the port; on the unit in image A4, commit 494bdd87's title "Octakit patch on the unit"): after a stock load error the current bank is applied the way stock's loop applies a parsed one, then her post step and activation run on the stock result (`modules/octakit/README.md` "Patches on her runtime"). Running the post step alone activated and then halted at her engine-bank compare (the stock loop skips the engine apply for a bank whose file failed). Measured on the MKII with the patch and the rejected file staged as `PROJECT STRAND` (image A4, 5 Oct): the load reports PARSE ERROR, then PLAY halts at `gk_stock_audio_pattern_primary_begin_report_fatal` (VEC:04, D0 = −1: `gk_physical_validate` finds no lease for the rejected bank's part; reproduced under the port). With the rejected `bankNN.work` DELETED from the card (stock −12, bank initialised empty) the same project loads, plays 400 frames and pastes clean under the port. So: a missing bank file is handled; a rejected one halts on PLAY instead of on paste — delete the file. Reported to Em with the patch (fork `sambanks/ems-octakit`, branch `banks-load-error-activates`). A project name with no directory on the card (the port's `--project NEWPROJ`; stock −12 on every bank file) still strands: her `gk_v3_first_install_migrate_impl` migrates the resident banks (OK) and then `create_pair_from_canonical(WORK)` returns −10, the open error normalised (`normalize_open_error`: −10/−12 → NOT_FOUND) -- there is no directory to create her work pair in. The unit's LOAD PROJECT lists directories only, so this needs a hand-made card to reach (inferred). Without the patch: never load the bad project; change project after any load that stock reports in its LOG (`Couldn't read bank file ... PARSE ERROR / WRONG CHECKSUM`). To find out: whether Em takes the change upstream.

## A bank file written by the unit that the firmware then rejects: one 64-byte burst dropped from a 16 KiB card write, the card's MBR in its place 🟡 measured file, cause inferred

- **Seen:** Sam's MKII, image 99 (bottleservice with USB AUDIO IN CD + USB CROSSBAR, a computer on USB), 4 Oct 2026 12:42:14: `PROJECT 261004p/bank01.work` written with `project.work`, `markers.work` and `p2lk01.work` in the same second (a project change or SYNC, not SAVE: no `.strd`). Checksum 0x7188 stored, 0x4e8c computed; with the checksum repaired the firmware still rejects it (−51). Content: from 0x2c000 to 0x30000 every byte is 64 earlier than in a good bank, and the last 64 bytes of that span are the card's MBR code (`33 c0 8e d0 bc 00 7c fb 50 07 50 1f …`). Three other saves that day (09:40, 12:45, 14:13) are intact.
- **Cause:** inferred: a 16 KiB ATA write lost one 64-byte burst at its head and took a 64-byte block from another buffer (sector 0, read at mount) at its tail — a DMA/bus-arbitration fault, not a serialiser error. USB CROSSBAR raises the USB host's crossbar priority on SDRAM; it is the one module in the image that changes bus arbitration under card DMA. Not reproduced under the port (a project SAVE with PLOCKS P2 writes every bank intact; the port has no bus timing).
- **Fix:** USB CROSSBAR and USB AUDIO IN CD removed from bottleservice (image 100). To find out: whether a bank written on image 100 ever fails again; the bad file is at `~/octa/backups/card_20261004_strand/`.

## Pops and clicks from T1 with BusDelay when T1 plays its own trigs 🔴 open

- **Seen:** Discord, Arcdmd_, 29 Sep 2026. Image, unit model, T1's machine and trig pattern not stated.
- **Cause:** open. The bus (BusDelay on T1, BusVerb on T5) is tested with T1 and T5 as THRU tracks without trigs. The one earlier test with a trig on every T1 step (21 Sep 2026) gave clicks and no wash. A trig splits the host's block into two dispatcher calls; the delay's glides run on the first call only since 21 Sep 2026 (`modules/busdelay/README.md`).
- **Fix:** open. To find out: the reporter's image, machine and trig pattern; whether the clicks land on T1's trigs; whether they follow the delay (FX2 = SEND on T1, same trigs) or the machine (a THRU host with a trig every step clicks from the THRU's re-open); the same test on T5 with BusVerb.

## Every FX1/FX2 page-2 knob turn halts under Octakit with SCENES P2 (bottleservice) ✅ measured under the port

- **Seen:** under the port, 28 Sep 2026. Image 88 carried the twelve-byte build; the halt was not reported from the unit.
- **Cause (measured):** SCENES P2's entry detours at `0x4003a9dc` / `0x4003abe4` displaced twelve bytes and nopped the third stock instruction (`moveal %sp@(32),%a2`, the slot argument). Octakit's trampoline replays eight bytes and continues at entry+8, so a2 held a stale code address, the body took its slot>5 exit, and `validate_result` reported corrupt: `illegal` at `gk_track_setup_byte_fatal` (`0x45d28e98` in bottleservice's runtime). kits (Octakit alone) takes the same turn.
- **Fix:** the detours displace eight bytes (`pad_to=8`), the stubs continue at entry+8 (`modules/scenes-p2`), 28 Sep 2026.
- **Check:** `verify_modedefaults` and `verify_scenesp2` run their editor calls under bottleservice (Octakit SKIPs removed).

## Junk on main R for one frame, from T1 with BusDelay, about twice a minute ✅ measured, fixed (image 43)

- **Seen:** images 32-38, 25 Sep 2026. BusDelay on T1 (STATIC, hard left): 16-24 samples of random full-scale words on main R about 0.5/min, at one phase of the 4-second pattern cycle.
- **Cause (measured):** core 1's frame start reads core 0's bank word (`P:0x57-0x7a`, payload B), picks the read-back buffer (`X:$2600` or `X:$4600`, `X:$206`) and patches the host handlers' masks (`P:$371`/`P:$380`): one read-back buffer per frame, and the ColdFire's pull (DMA channel 1, armed at `P:0x37c`) must finish before the first FX2 copy overwrites it. The ISR pulls core 0, the ESAI, then core 1; on the unit core 1's pull reaches T1's 64 words ~4.5 samples after T1's proc entry (the port models +0.26), jittering with pattern position. BusDelay on core 1 copied inside the pull. A NOP burn after the loop: +0 cycles 1266 runs/min, +256 16/min, +512 1.4/min over 10 min.
- **Fix:** image 43 (branch `padfix`): 8,192 NOPs (two samples, 11 % of the frame) after the loop, before the rts. 10-minute take: 0 junk (baseline 5). Costs two samples of core 1's budget every frame. Polling DSR1 / DCR1.DE (images 37, 38) and a frame-end detour (images 39-42, PR #405: core 1 wedged at project load; the idle at `P:0x57` is the last instruction of `do #16`, a word-by-word handshake with core 0) did not work.
- **Check:** `tools/harness/burst_census.py` on a `tools/rec` take (built from `tools/hw/rec.swift`); only 10-minute takes count (a 90 s take shows nothing 47 % of the time at 0.5/min).

## A white-noise wash from a sample host with trigs on it ✅ measured, fixed (image 43)

- **Seen:** Sam's MKII, 21 Sep 2026, images 39-42. BusDelay on T3 STATIC with a trig every step washes from the second pass; T2 THRU with a trig every step at once. LEVEL 0 silences it; FDBK, WET and STOP do not remove it; PLAY or a reload clears it until the next full loop. T1 as host: clicks, no wash. The port shows nothing (lock-step cores).
- **Cause (🟡 inferred):** each bus participant rebuilt the second call's frame offset from a flag and split stashed by the first call in its block (`$65/$66`). If the stash does not survive a trig between the two calls, the second call runs as a first: at position 0 the rotation tracker advances twice and keeps a lead of one. The stash was never measured on the unit.
- **Fix:** image 43: the offset comes from `r0` (0 on a first call, 2 × split on the second; the port: `r0 = $e` for a trig at frame 7), in SEND, BusDelay and BusVerb. Measured: T3 STATIC with a trig every step clean through eight loops and a reload. PR #344's init stores (removed in 42), the `$84..$88` relocation (#346) and once-per-block glides (#345) were not the cause.

## Sequencer stuck on step 1 at the first play: images 44 and 45 🟡 two causes inferred, fix built (image 46)

- **Seen:** images 44 and 45, 21 Sep 2026: flash, load, play, stuck on step 1; power-cycle and reload recover.
- **Cause (🟡 inferred):** (1) image 44's housekeeper stamp clear used one-word displaced Y stores (`move a,y:(r3+$1)`), a form with no stock site; image 45 used `move a,y:(r3)+` and wedged the same way, so the form was not (or not only) it. (2) The tracker's check read the client's last write offset from its slot as an address; an FX1 NONE slot runs SEND at an r7 below `$6200`, which ROTINIT never seeds, so on the unit the read went to a wild Y address (peripheral registers live in Y). The port zeroes RAM.
- **Fix:** image 46 masks the value (`and #>$30`) before it becomes an address.
- **Check:** the gate chain runs the port with `--dsp-dirty` on the trig-host fixtures.
- **Lesson:** no address from a word init did not seed, unmasked. A DSP form with no stock precedent in `tools/build/dsp_disasm_all.py` output does not ship without a hardware probe.

## A white-noise wash from a THRU host past position 0 with a trig every step; bleed into the bus with every SEND at 0 🟡 lead measured (image 47), cause inferred, fix built (images 48, 49)

- **Seen:** BusDelay on T2 THRU with a trig every step, images 40-43 and 46; on 46 audio also reached the bus with every SEND at 0. T1 as host: clicks, no wash. The port (`verify_set`, `out/OCTABAM89_t2thru`) shows nothing.
- **Cause:** ✅ image 47 (a marker-tone probe): the core-1 tracker sits one step ahead permanently on plain play. 🟡 Inferred (`modules/send/README.md` "An FX1 slot is not a client"): FX1 NONE is id 0 = SEND, which ran on every empty FX1 slot at r7 0x6100/0x6400/0x6700/0x6a00 (measured, PC watch). The 0x6100 call sent from an unseen page byte (the bleed) and, on core 1, ran the tracker compare before position 0's advance; a flip landing before it leaves `T == R + 1` for good. Under the port the flip lands late in core 1's frame every frame.
- **Fix:** image 48: SEND returns at proc entry on an FX1 r7; the self-check removed. Image 49 (structural): eight accumulator and chain buffers, a server reads three back, the housekeeper clears two on, a core-1 client counts its own blocks from a seed read at init, checked against the rotation with a tolerance of one (`modules/send/README.md`). Costs one more block (48 samples) of latency.
- **Check:** the port's two-core gate is bit-identical to the one-core control under every skew. Falsified by any wash or static on 49 that a host position, trig pattern or load changes.

## Audio engine wedged, sequencer alive: the master loop ✅ measured

- **Seen:** 5-6 Sep 2026 (tag 93, the bus image of that date). Sequencer runs, no audio, sample preview silent, record meters B/C/D lit. Distinct from the DSP hang (sequencer frozen).
- **Cause (measured 6 Sep 2026):** T8's station (Character, return role) sent into the reverb bus it returns: T8 FX1 -VRB at 71 in bank02's parts; turning it to 0 brought audio back. Why the loop reads as silence is not established.
- **Fix:** stations have no sends; SEND is refused at track 8's dispatch position on payload A whatever its knob. The refusal outlived the T8 return (20 Sep 2026): with MASTER TRACK on, T8's input includes the hosts' wet.
- **Check:** `tools/verify/verify_onebus.py`.

## The audio engine wedges with only BusVerb + the return 🔴 open (the return removed 20 Sep 2026)

- **Seen:** image 94, 13 Sep 2026, `tools/hw/ot_soak.py`: T5 FX2 = BusVerb, T8 FX1 = Character as return. Output drops to the noise floor while the transport runs; a transport restart recovers.
- **Cause:** open. 3-minute soaks: return alone clean; BusVerb with return at 0 clean twice; BusVerb + return at 127 silent at 131.5 s once, clean on a repeat and on a 9-minute run. Rate ~one freeze in 15 minutes. Not the cycle wall.
- **Fix:** open. Next: soak `BusVerb + return` against `BusDelay + return` for tens of minutes each.

## BusDelay silent with its knobs locked: the MODE formatter wrote over the minimum table ✅ measured

- **Seen:** OCTABAM86. No delay; TONE, PING and MIX pinned and immovable; cleared by a reboot, back when page 2 was drawn.
- **Cause (measured, emulator write watch, 13 Sep 2026):** `tools/build/mode_names.py` wrote renames at `P + 0x4e + 6·slot` where the names live at `E + 0x4e` and `P = E + 0x38`, landing in the minimum-value table (`P + 0x6a + 4·slot`): GRAIN's names set `min[3..5]` to 0x4d444550 / 0x4d524154. Character's SAT view and Modulation's COMB view had the same fault.
- **Fix:** `NAMES_AT = 0x16` (P-relative); the project re-stamped from the manifests (OCTABAM87) measured clean on the ladder.
- **Check:** `verify_modenames` reads the names from the corrected offset (it had read back from the same wrong one).
- **Lesson:** an autocorrelation of the mix that "measured TIME inert" was reading the material's own eighth and quarter (248 / 496 ms at 121 BPM) and is retracted; measure a delay time from the repeats' spacing after the source stops.

## CC MAP (CC PAGE 2 until 25 Sep 2026) did not write on hardware ✅ fixed (image 96)

- **Seen:** CC 62-67 changed nothing on the panel, stopped or running.
- **Cause (measured):** the cave used the PLAYBACK page-2 editor's stores (`0x4003a474`), corrupting the track's PLAYBACK page-2 byte. The FX2 editor's stores are Part `+0x8f084`, shadow `0x100a51d2`, lane +0x38.
- **Fix:** the cave uses the FX2 stores; image 96: CC 63 on channel 5 moved SHMR and raised the tail's 2-8 kHz bands 5-8 dB. Every page-2 sweep taken over the old cave is void.
- **Check:** `verify_ccmap` proves the write against the FX2 editor.

## BusDelay's SEND knob drew TIME's division labels ✅ measured

- **Seen:** on the unit, 15 Sep 2026: the first knob printed `1/8`-style labels.
- **Cause (measured):** `modules/tempo-sync` registered the TIME formatter on slot 0; TIME has been slot 1 since the one-aux re-slot (7 Sep 2026). The published value was the knob's.
- **Fix:** registered on slot 1. The same day the knob became `SEND` on every track (was `AUX`), and the engines' `MIX` became an add-only `WET` (the crossfade had faded the delay out; measured on an impulse, 15 Sep 2026).

## A generated project shows as modified and RELOAD refuses ✅ measured

- **Seen:** a project written by `tools/hw` loads marked modified; RELOAD PROJECT does nothing.
- **Cause (measured):** the saved state is the `.strd` twin of every `.work` file; the tools wrote `.work` only.
- **Fix:** `ot_project.py stored <project>` writes the twins; `rigproj` and `delaytest` write them. A SAVE PROJECT on the unit does the same.

## Re-selecting an effect zeroes the bus ⚠️

- **Seen:** the bus measures dead (no wet on T1 or T5) after panel work.
- **Cause (measured):** a re-select loads manifest defaults, and BusVerb's SEND defaults to 0 (a non-zero default registers every idle host as a client); Character's RET also defaulted to 0.
- **Fix:** assert SEND `CC 40` per track over MIDI immediately before every measurement (and, until 20 Sep 2026, RET `CC 38` on the master's channel).

## A station "at its defaults" was running its default mode's view ✅ measured

- **Seen:** a station documented as bit-exact passthrough at defaults changed T5's level by −2.5 dB on the ladder.
- **Cause (measured):** `ot_project.module_defaults` applied the ModeView of the defaults' MODE (Modulation's CHOR: MIX 64, RATE 30), so `rigproj` and `stamp-defaults` wrote a half-mix chorus into every T5.
- **Fix:** a view applies only when MODE is given explicitly. Re-stamp.

## PARSE ERROR loading a generated project ✅ measured

- **Seen:** LOAD PROJECT on a project from our tooling stops with "PARSE ERROR".
- **Cause (measured):** every PART record carries its own index in byte 8 (parts 1-4 hold 0-3, mirrors 5-8 repeat 0-3); a whole-record copy keeps the donor's. Also: `project.work` edited in text mode loses its CRLF.
- **Fix:** write `p % 4` into byte 8 after any whole-record copy (`ot_ladder.PART_INDEX_OFF`); the generator's read-back checks every record.
- **Check:** under the port the firmware logs `Couldn't read bank file '...bank01.work' ('PARSE ERROR')` to the card's `LOG 000000.txt` (`verify_set`, `ot_emu --card-out`).

## The set went silent after a test flash: the firmware reset the project 🟡

- **Seen:** after flashing a test image whose remix omitted Character; silent back on the bottleservice image.
- **Cause:** ✅ the card's bank records had every part reset (FX1 id 4 with FILTER's page-2 bytes, FX2 = stock delay, T1/T2 no longer THRU, T8 = FX1 NONE / FX2 COMPRESSOR 0x18). 🟡 Inferred: the firmware sanitises part records whose FX ids are not in the running image and writes the .work files back. Not reproduced by LOAD PROJECT under the port (15 Sep 2026, OCTABAM88 bank B under `bus`), so the rewrite happens on another action.
- **Fix:** never load the set under a test image. Recovery: save a copy of the card's project; regenerate (`ot_project.py rigproj … + lfo-clear … all`), copy the banks over in place, keep the project's own `project.work` (a foreign `OS_VERSION` tag gave PARSE ERROR, inferred from the diff).

## The master compressor collapses one channel above COMP ~40 ✅ measured

- **Seen:** 13-14 Sep 2026. Character on T8 with COMP above ~40: R drops 40+ dB, L holds; scales with WDTH; only with the stations loaded.
- **Cause (measured 14 Sep 2026):** T4's Spectrum generated near-full-scale DC from state: init cleared `$00..$17` only; filter B's two HP poles at cHP = 0 were frozen and `hp2 = yB − h2` subtracted a stale h2 every sample (−0.5 FS on silence from a block pre-filled with 0x400000, under `dsp_host`). The makeup clipped DC + audio on the channel with the larger offset. Track LEVEL 0 on T4 cleared it; AMP VOL 0 did not.
- **Fix:** every persistent slot zeroed at init (Spectrum `$00..$3f`, Modulation's LFO values, Character's counters, phase and grace). Image 8: bank G's master at COMP 40 / 80 / 127 reads R−L −0.4 / −0.1 / −0.6 dB (was −44 at COMP 80).
- **Check:** `tools/verify/verify_dirtystate.py` (in `make verify`) renders every module from a garbage block on silence and refuses output above −100 dBFS.
- **Lesson:** a channel-asymmetric failure in channel-symmetric code is a data asymmetry; an AC-coupled capture cannot see DC.

## A diagnostic image silenced every bank with stations; the port played them 🔴 open

- **Seen:** OCTABAM5 (Character 189 words shorter) played banks A, B, E and was silent on F and G (the station layouts), DSP not hung. Image 4 and the shipping image play G.
- **Cause:** open. Under the port image 5 plays F and G and runs no instruction image 4 did not. Left: placement (Modulation moved down, A 0x1c1b, B 0x193c; stock COMB code and dispatch kept on payload B). Image 6 = image 5's Character plus 189 nop words plays F and G. Not bisected.
- **Fix:** workaround: pad a diagnostic module to a placement known to play.

## Sequencer stuck on step 1 at project load: an init that moved r1 ✅ measured

- **Seen:** image 99, 13 Sep 2026, every project loading a Spectrum on FX1.
- **Cause (measured, the port's last-PC ring):** the FX1 dispatcher keeps the effect id in r1 across `jsr init` and indexes the proc table with it (`P:0x4c8..0x4d7`). Spectrum's init returned r1 = r7+24; `jsr (r2)` landed on P:0. `dsp_host` calls init and proc itself and cannot see it.
- **Fix:** init zeroes through r5. Recovery: power-cycle and a project without the module.
- **Check:** `tools/verify/verify_initregs.py` (in `make check`) refuses an init that writes r1/n1/m1.

## Sequencer stuck on step 1: cycle overrun or a wild value

- **Seen:** step 1 solid, no audio.
- **Cause (measured):** a core cannot finish a block: a cycle overrun (three heavy stations beside an engine at a static 3,106 of 3,120; the counter is a floor, the wall a cliff), or a wild stored value feeding an engine on frame one (an old part's crossed-slot byte after a layout change).
- **Fix:** fit the layout (≤ two heavy stations per core); stamp the project for the current remix before playing.

## The bus return is "less rich / bit-crushed" on the unit, clean under the port ✅ gone with the return (images 35 → 38)

- **Seen:** image 35, up to 20 Sep 2026. One sender, WET 0 on both engines, RET 127 on T8: the return duller and grainier than the dry; worse after knob presses; STOP then PLAY resets it. Present on either core, at any send level, with the sender muted post-FX. Under the port the same path is the aux itself at −109 dB residual, lag 60 samples (`verify_set`).
- **Cause:** in the return path; which part (shared-window per-sample reads, the rotation, the station's add) was not bisected and the code is gone.
- **Fix:** 20 Sep 2026: the return removed (Character has no RET, engines publish no stage output, SEND allowed on T8); each engine's wet leaves through its host (T1 repeats, T5 tail). Image 38 on the unit: the reverb on T5 clean (Sam, 20 Sep 2026).

## A TIME turn on BusDelay crackles for about a second, in both directions ✅ measured, fixed (unflashed)

- **Seen:** Sam, image 38, 20 Sep 2026: TIME or FDBK moves crackle; putting knobs back does not clear it; re-selecting does.
- **Cause (measured, `dsp_host` and the port):** the glide (image 33) stepped its Q8 state once per block, up to ~17 samples a step; the loop's tap, REVERSE's lag floor and GRAIN's read base jumped by the step at every block edge (~1 s of clicks after a big move, then a ~3 s sub-sample tail). The FDBK crackle was TIME's tail.
- **Fix:** the Q8 TIME ramps within the block, a sixteenth of the step per sample; REVERSE and GRAIN re-derive their per-sample lag from it. Spikes per mode 5,228 / 2,676 / 4,483 → 0 / 73 / 896 (the remainder is REVERSE's uninterpolated heads).
- **Check:** `tools/harness/glide_census.py`, `port_click_census.py`.

## The RET/CRSH trap ✅ removed by design

- **Seen:** T8's Character in the old BUS mode with knob 3 at 127: switching SAT to TAPE made the whole mix a full-scale 4-bit crush (the same knob was RET in BUS, CRSH elsewhere).
- **Fix:** no BUS mode. 13-20 Sep 2026 slot 4 was RET on every track; since 20 Sep 2026 slot 4 is empty (`---`) and the return is gone. DRV 0 skips the saturator (bit-exact).

## An FX1 station's page 2 does not reach the DSP on a bus host ✅ fixed (image 24)

- **Seen:** 15 Sep 2026. Character on T1 (THRU, FX1) ran TAPE whatever the panel said (−47 dBFS hash at knob 3 = 127). T3 (STATIC) and T8 (FLEX) took page-2 edits; T1 did not. T2 (THRU, FX2 = SEND) kept its page 2; T1 (FX2 = BusDelay) lost it.
- **Cause (measured, `ot_emu --watch-mem` on T1's DSP record):** the tempo cave (`modules/tempo-sync`, in the voice-record writer for FX2 ids 6/7) stored tempo24, clock period, fader+1 and note into record halfwords 18-21 (`+0x24..+0x2a`) every frame after the copier put FX1 page-2 bytes in 18-20 (`0x400d7550`, `0x400d755e`, `0x400d7522`). Halfwords 18-20 are also `r6_FX1+$c..$e`. Every FX1 effect on a delay or reverb host had run page 2 on tempo bytes since 24 Aug 2026.
- **Fix:** the cave publishes only the note, into the low byte of BusDelay's TIME halfword (`+0x1b`, `r6+$1` bits 8-15); BusDelay reads tempo24 from stock's record word (halfword 31, `r6+$13`, `0x40004d6a`) and derives the period on the DSP. Under the port a live SAT edit on T1 lands (`0x7f01`); 120 BPM snaps TIME to 11,025 samples (1/8). Image 24 (15 Sep 2026): sends into the delay work on the unit.

## Static that stays after knob moves with both engines live 🔴 open

- **Seen:** image 26, OCTABAM89 C02, 15 Sep 2026. Knob moves on BusDelay or BusVerb (times, sizes) sometimes bring static that stays, most reliably with the reverb host's SEND and both WETs up; a transport restart clears it. Not reproducible on demand after. One 10 s capture (`out/hw/voicing25/noise_now.wav`): HF above 8 kHz −77 dB against −85..−91 dB after CC toggles, no clean A/B.
- **Cause:** open. Under the port (ONEAUX fixture and OCTABAM89 C02 for 2,400 frames, `out/crackle/c02_recipe.midi`) a knob turn costs no extra cycles (delay 3,754 → 3,754, REVRS 3,914, reverb 16,710 ± 14) and no output rails or jumps above 0.25 FS. The port models no stall; C02 prices ~2,950 (core 1) and ~2,994 (core 0) against 3,120 usable, with the counter ~270 low on the reverb, so an overrun that desynchronises the frame handshake fits (🟡 inferred).
- **Fix:** open. To find out: with the static going, take one station off the core (T2's FX1 to NONE); or `make burn` on C02, stepping the burn until it appears.

## A DC thump every 10.59 s at idle, from track 6 ✅ source measured

- **Seen:** every ladder rung, including the one with no module of ours; transport stopped. DC step +0.23 FS L / +0.46 R, two-sample rise, ~35 ms decay through the output DC blocker. LEVEL 0 on T6 removes it; AMP VOL 0 does not.
- **Cause (measured):** T6 LFO 2: destination 16 (AMP BAL), triangle, speed 18, depth 21, FREE; period 64 steps at 121 BPM with a 3/4X scale; the pulse rate follows LFO speed. A plain BAL move over CC 8 never pulses.
- **Fix:** every LFO depth cleared in OCTABAM87 and the ladder (`lfo-clear all`). Open: whether a balance LFO pulses on stock 1.40C (the port with a fast LFO fixture decides it); a 593.5 Hz tone at −75 dBFS after STOP on OCTABAM87 only.

## Spectrum VOWL went silent with RES up 🟡 seen once

- **Seen:** image 96, T3 soloed, FREQ/RES over CC, MODE set at the panel: VOWL at RES 100 with FREQ ≤ 96, and RES 127 at FREQ 64, output −102 dBFS; other modes bounded.
- **Cause:** 🟡 not reproduced (`dsp_host`; image 97 with MODE over CC 69, both knob orders). The one difference: T3's FX1 page 2 was on screen during the page-1 CCs (the editor's refresher `0x40027e00` runs there). CC 35 with page 2 on screen landed on RES, which falsifies routing by displayed page.
- **Fix:** the two-peak VOWL is gone (image 98: a three-formant resonator bank, bounded at RES 127). If it recurs, capture before touching anything.

## A one-sample tick on an exact 2048-sample grid at idle 🔴 open

- **Seen:** image 93, sequencer stopped: a common-mode one-sample downward spike, −45 dBFS, every few hundred ms; present with the reverb's track muted.
- **Cause:** open. Measured: 23 / 24 ticks per 30 s on a 2048.050 / 2048.049-sample grid (residual 0.29 / 0.25 samples over 631 periods); +24 ppm says the unit generates it; 4 % of wraps spike. Ruled out: the capture setup, Character, the stored project (a reload gave zero ticks), the input path, BusVerb page 1. Page 2 untested (the CC MAP fault). Candidates for 2048: BusVerb's 2048-word modulo buffers (`m5 = $7ff`), Modulation's `buffer_words=2048`, the PCM-pool block (`0x800` in the recorder's table at `0x80003c20`).
- **Fix:** open. When bisecting by hand, take slots to a stock effect, not NONE (id 0 is SEND). `tools/rec` (built from `tools/hw/rec.swift`) must be the HAL recorder.

## Sequencer stuck on step 1 with every effect turned off: id 0 is SEND

- **Seen:** image 85B (the first RIG BURN probe image): every FX1 NONE and every FX2 SEND. Second instance, image 32B, 16 Sep 2026: two projects with every stored page byte zero.
- **Cause:** ✅ id 0 is aliased to SEND and FX1 NONE is id 0, so SEND's proc runs on every FX1 NONE slot with r6 on a page whose bytes the last effect left; the burn read a stale slot-1 byte on four extra slots per core. The emulator never instantiates an FX1-NONE slot. Second instance: 🔴 7,111 burn loop iterations at "0" and the frame never finished; the loop count's cause is open. ❌ Retracted (22 Sep 2026): "the firmware computes page-1 slot 1's word" (`0x378f00` was the previous instruction's `a`; a port page dump shows every slot raw, knob << 16).
- **Fix:** anything in SEND that reads a knob and can cost cycles or write the bus gates on the slot being FX2. Since image 48 SEND keys the refusal on r7 (0x6100/0x6400/0x6700/0x6a00, measured under the port; X:$213 is stale at proc time) and returns before touching state. The burn reads page-2 slot 6 (`$c`, CC 62), unflashed. The stamper writes SEND's defaults into every id-0 slot, FX1 and FX2.
- **Check:** `verify_burn.py` check 5 (`dsp/burn_send.inc`).

## Line-F exception on [PROJ]: a cave pinned in OS .bss

- **Seen:** tag 91: PROJECT throws an exception and wedges.
- **Cause (measured):** a cave at `0x40108800`, in the OS image's last ~30 KB: a zero run at rest that is the PROJECT subsystem's RAM.
- **Fix:** `build_bus.SAFE_CAVE_CEIL` (0x400d8000) refuses any cave above the decoded free region.

## Garbled audio straight after an OS upgrade: the warm-up tag

- **Seen:** right after OS UPGRADE, audio garbled (worse for the delay); not after a reboot.
- **Cause (🟡 inferred):** an upgrade rewrites program memory without clearing DSP state RAM; an engine skips warm-up when its tagged counter holds a valid tag at full count (BusVerb `$2c0000` at `r7+$82`, BusDelay `$2e0000`).
- **Fix:** power-cycle after every upgrade before judging anything.

## A module mistuned on tracks 1-4 only: an absolute stock-table address ✅ measured

- **Seen:** Bryan T's LOFI2 low-pass three times too bright on tracks 1-4.
- **Cause (measured):** the payloads are linked separately: the 6,305-word curve bank is `X:0x438` in A and `X:0x42b` in B; Y tables shift by 16. A bare literal is right on A (tracks 5-8) and 13 words off on B. The single-payload audition render dumps payload A.
- **Fix:** declare stock X/Y table addresses so the build rewrites them per payload, or read through a build-supplied base.
- **Check:** audit any stock-table read on both payloads with `rig_render.py`.

## Self-oscillating squeal: a page-2 value out of range, or deep overrun

- **Cause:** (1) a wild page-2 value: BusVerb DIFF stamped to 127 self-oscillates the tank (the +0x325/+0x331 stamp-offset bug, also flash 4's "the stock DELAY wedges the unit on part load": T4's DELAY row landed on T5's BusVerb). (2) Deep cycle overrun (the high-pitch squeal, `docs/firmware/CHIP.md`).
- **Fix:** re-stamp the project (1); fit the layout (2).

## "Z" screen / won't boot: corrupt OS

- **Fix:** Startup Menu recovery: power off; hold [FUNC], power on; [TRIG 3] MIDI UPGRADE; send a good `.syx` (`make midi-flash PORT=A SYX=…`, or a SysEx app). [`docs/guide/BUILDING.md`](../guide/BUILDING.md) section 7.

## Cross-core bus glitch: the accumulators' race ✅ mechanism measured, fixed

- **Seen:** a tear, stutter or hash on wet audio crossing cores, often smeared into a reverb tail.
- **Cause (measured under the port, `git show 3ceba41:docs/history/COLDFIRE_PORT.md` O12; [`modules/send/README.md`](../../modules/send/README.md)):** core 0's housekeeping flips the rotation word mid-way through core 1's frame; clients read the word directly, so a frame's sends split across two buffers.
- **Fix:** four ACC buffers and one rotation tracker per core (`build_bus.py` ROTLATCH, payload B); eight buffers since image 49 (above). No local test is evidence: `dsp_host` runs the cores lock-step or under a guessed interleave.

## CONTROL menu shows its stock six rows though the image carries eight 🔴

- **Seen:** tag 16: the bus screen's appended rows absent; the image held row count 8 at 0x400cbd54 and the repointed row pointer.
- **Cause:** unknown; the rows are read from somewhere the patch does not reach.
- **Fix:** the module is out of the tree. Navigate to CONTROL in the ColdFire emulator's own menu before any flash that appends rows again.

## The one-aux return never reached T8 ✅ measured under the port

- **Seen:** flash 6: wet out of T1 and T5 (the engines' hosts), nothing at T8.
- **Cause (measured):** the station pinned the return to track 8 by `r7 & 0xff00` against `$6700/$6800` (the harness's two-per-track model). The stock dispatcher bumps r7 three times per track (the third unconditional at P:0x51e), so T8's FX1 runs at `$6a00`.
- **Fix:** pin `$6a00/$6b00`; the harness's r7 model corrected. Confirmed on flash 7.
- **Lesson:** `verify_onebus` was green on exactly this property; dispatcher facts are measured under the port.

## The port reports a wrong bank/pattern for an image that detours `0x40087d44`: the instrument

- **Seen:** under `ot_emu --sequencer`, an image hooking the BANK= store at `0x40087d44` plays bank 0 pattern 0 after LOAD PROJECT (`saved_bank: -1`). A 38-site bisect and a PR to midisc's author (withdrawn) were built on it.
- **Cause (measured):** `rtos.cpp` learned the saved bank from a write watch on `BANK_PTR` (`0x46c82456`) accepting only the stock store's PC; a detour stores from a cave.
- **Fix:** the watch follows a `jsr (abs).l` at the site and accepts the detour's store; `--bank N` overrides.
- **Lesson:** a port watch keyed on a stock PC is blind to any module that detours that PC.

## A send that ignores its knob, a track loud into the bus at SEND 0, different per track 🟡 two causes, both project data

- **Seen:** image 32, OCTABAM89 and its no-effects copy, 16 Sep 2026: T5 and T7 loud through BusDelay at SEND 0; T3 quiet; T2 leaking with a dead knob. CLEAR PATTERN fixed it.
- **Cause 1 (measured):** stale parameter locks: one lock byte per slot per trig (`tools/hw/ot_bank.py`: 64 steps × 32 slots; FX1 = 18-23, FX2 = 24-29; `0xff` = none). Every slot move since 7 Sep left locks on whatever knob sits there now. OCTABAM89 carried 962 FX1 and 6 FX2 lock bytes, one on T5's FX2 knob A.
- **Cause 2 (🟡 inferred):** an FX2 stored as id 0 aliases to SEND; the firmware delivers no page for it, so SEND reads whatever the DSP page word holds. Not measured under the port; the falsifier is a stamped project that still leaks.
- **Fix:** `ot_bank.py strip` clears a page's locks in every pattern; `stamp-defaults` and `clean` store SEND (id 9) with a zero page in every empty FX2 slot.

## Freeze without an exception screen as ColdFire delay-routine work grows 🟡 open

- **Seen:** Jannik Aßfalg (repeat98)'s unit, Tape Echo (PR #357, runs in the stock delay's frame routine, [`docs/firmware/COLDFIRE_DELAY.md`](../firmware/COLDFIRE_DELAY.md)): OCTACLID3 froze on a TIME edit with three instances, OCTACLID4 editing the sixth, the PR's candidate at seven; always during control edits.
- **Cause (🟡 inferred):** the routine's per-frame deadline. Port instruction meter per eight-track frame: stock DELAY 7,628; eight instances ~23,000 settled, up to 32,355 moving (after the 23 Sep 2026 EMAC rewrite: 15,283 / 16,459 / 21,547, `modules/tapeecho/README.md` "Measured", unflashed). Frame period 363 µs, ~95,800 CPU cycles at 264 MHz, shared. The meter prices an uncached SDRAM access at one cycle. State is a fixed 1,600 B; nothing is allocated. Stock spins at `0x40003780` on DMA status `0xfc0450be` before the commit: a silent hang on overrun. Falsified by a freeze at the same count with the work halved, or with settled controls.
- **Fix:** open; the ColdFire's per-frame budget for the routine is not measured. Any reverb or granular on the ColdFire prices above the seven-instance point (BusVerb ~18,000 DSP cycles per frame, four-grain GRAIN ~28,400).

## Bursts of garbage on the reverb host's frame while the delay runs on core 1 🔴 open

- **Seen:** Sam, image 58 on, 23-24 Sep 2026 (heard as intermittent clicks since image 26). BusDelay on T1 with a sample playing, BusVerb on T5, nothing sent: 23-53 samples of near-full-scale garbage on T5's side about 3.5 times per six minutes. Stock 1.40C does not burst (Sam).
- **Cause:** open. Measured:
  - The bursts need the delay's DSP code running on T1 past its preamble: image 95 (proc returns at its first instruction) and 96 (stops after the preamble) read 0 in 12 minutes; every other delay image burst. T1 AMP VOL 0 read 0.
  - Ruled out on the unit: the ColdFire side of id 6, CPU load on core 1, the reverb, the frame write-back, the role lock alone, absolute-address stores into the shared window, words written by both cores, which half of the shared window holds the bus scratch (images 91-99), and the delay's per-sample shared accesses (image 91 take 5: none, same rate).
  - 9 of 12 bursts start 14-18 ms after the loud transient in T1's sample, and follow T1's trigs when those move against the beat.
  - The aligned-copy census: T1's own print deviates in the same 16-sample block in 29 of 32 bursts (0.03-0.35 FS); the same T1 audio instant gives the same burst waveform (12 copies of one cluster across images 91-99), so the content is a function of T1's audio. The junk is in T1's stereo block, full scale on the side T1 is panned away from, before the main mix (CUE shows it), and not T5's block (T5 LEVEL 0 changes nothing).
  - The dispatcher re-sets r0, r1, n1, r3, x1 and y1 before the read-back packer (`P:0x303-0x35e` on B); m0-m6 were saved on image 83 and it still burst.
  - Rates: a six-minute 0 occurs by chance 5-9 % of the time, a twelve-minute 0 about 0.1 %; the earlier two-minute table read 0 by chance ~37 % and separates nothing.
- **Fix:** open: where between T1's audio block after proc and the read-back words at `X:0x2600` the junk appears, and which part of the delay's per-block decodes or sample loop it needs. Branches `diag91`..`diag98`, `core1scratch99`, `nolock94`, `fix97`; captures `out/hw/v9*.wav` (machine-local). The "dead words at 0x360d3-5" (send_client.asm) are unexplained.
- **Check:** `tools/harness/burst_census.py` with the aligned-copy check on a `tools/rec` take (T1 BAL hard left, T5 hard right). `tools/rec` needs the device name as its third argument (without it, it looks for EVO4 and exits).

## A UAC2 host stops audio setup after reading the clock: SET CUR of the read-only rate unanswered ✅ measured, fixed

- **Seen:** an Octatrack MKII with USB AUDIO on an Elektron Outbox 8 (allmyfriendsaresynths (@clickysteve)): the Outbox stays GREEN, "no device connected". macOS enumerates and streams the same image.
- **Cause (measured with a USB request log on the unit):** the Outbox enumerates the unit, sets the configuration, reads GET RANGE and GET CUR of the clock (44100), then sends SET CUR of CS_SAM_FREQ_CONTROL with a 4-byte data stage, and its audio setup stops there. The clock declares the control read-only and the stock EP0 stack has no control OUT data stage: the request fell to the stock STALL tail, which stalls only EP0 IN. Under the port the data stage is never accepted and the host times out. The read-only clock is octemu's design (`custom/usb-audio.py`), carried here.
- **Fix:** `usbaudio.s` `audio_ctrl_shim` takes the SET (44100 acknowledged, any other rate a status-stage STALL). On the unit, with the SET acknowledged (a build before the rate check), the Outbox completes audio setup and streams.
- **Check:** `verify_usb`'s SET CUR checks (44100 ACK, 48000 status STALL, EP0 answering after each).

## USB audio: a burst of reordered samples in the first 1.5 s of every host stream, clean after 🔴 open

- **Seen:** image 64, 25 Sep 2026, macOS recording all sixteen USB channels: four of five takes have one cluster of sample-step events 0.75-1.5 s after stream open, on several channels, none after 2 s (60 s, 60 s, 300 s, and 120 s under a 7,170-message/s USB-MIDI flood with panel work). Device counters (vendor request 0xc0/0x55): 0 underruns, 0 overruns, no bank-duplicate movement. Image 69 (24-bit, four packets queued at a 250 µs poll): still present, 0.51-0.76 s after open, only on the right channel of each pair, in runs 124-380 frames off phase.
- **Cause:** open. Measured: short runs out of order (−11.6, +10.3, −41 frames off the tone's phase), long-window phase agrees to 0.1 frame, so nothing is lost or repeated. Candidates: the device's packet queue on the first primes after alt 1 (the controller's add-dTD tripwire, not modelled by the port's bench), or the host's stream start. 🟡 Right-only on image 69 points at the host's stream assembly: each USB frame carries a track's L and R in one packet. Likely octemu's "some crackles" (sox opens a fresh stream per run).
- **Fix:** none. Workaround: discard the first two seconds of every take, or hold the stream open in a DAW. A stream held open across two recordings, or a sequence counter in the packets, decides the cause.

Entries from here to the end of the file (5 Oct 2026) were recorded in other documents first; each cites its source, which holds the full text.

## Line-F exception (VEC:0B) when a parameter is LFO-modulated: a 5-character `abbr` ✅ measured

- **Seen:** 2 Sep 2026, Bryan T's `modules/hello/` (removed 27 Sep): the descriptor drew correctly and behaved under manual knob use; the moment a parameter was LFO-modulated it threw a line-F exception (VEC:0B) at PC `0x48454C4C` = `"HELL"`. Presented as "custom effects can't be modulated". Source: `AGENTS.md`.
- **Cause:** `abbr` is a 5-byte field holding four characters plus a terminator; `fullname` is 13 bytes holding twelve, and the build tag is appended after the string. A name that fills its field leaves no NUL. A faulting PC made of the field's own ASCII is a smashed return address, so the copy destination is fixed-size (inferred, the copy is not located; the length rule is measured: all 30 stock page descriptors are ≤4 characters with byte 5 zero).
- **Fix:** `schema.MenuEntry` refuses both over-lengths and `build_bus.py` re-checks the string it writes, tag included (this caught two diagnostic delay names, `BusDlyRPLY` and `BusDlyNOCF`, that had filled all 13 bytes since 24 Aug 2026).

## A cloned descriptor draws as the donor's control: three of six page-2 slots wrong ✅ measured, fixed (17 Aug 2026)

- **Seen:** 17 Aug 2026 flash: BusDelay clones SPRING REV, and the formatter fix-up in `build_bus.py` was gated to the reverb. WOW inherited SPRING TYPE's word-label renderer (a three-entry table), was asked to draw 0..127, and drew no knob at all; MODE inherited SPRING BAL's bipolar pair and drew as a balance dial reading −64…−60 instead of a 5-way select. Source: `AGENTS.md`.
- **Cause:** a descriptor's display formatter overrides its value count, and a cloned descriptor inherits every field not explicitly written from the donor. Every field the checks examined was right.
- **Fix:** `verify_menu` checks the renderer against the count (`count < 128` → the enumerated pair with `0x12a` zero; `128` → both formatters zero). `Formatter.PLAIN` zeroes a clone's formatter words (`CHANGELOG.md`, 5 Oct 2026).

## The unit hangs when a module keeps state at r7 `$84` or above ✅ measured

- **Seen:** BusDelay's chain write address, WET glide state, write offset, REVERSE cap and last-seen rotation sat at `$84..$88`; on a host track with a sample playing, the unit hung (images 39–42 per `CHANGELOG.md` image 41; header map in `modules/busdelay/delay_server.asm`). Source: `AGENTS.md`, `docs/firmware/CHIP.md` section 5.
- **Cause:** `r7 $84..$8a` holds the unit's own per-track state between our calls (a host track with a sample playing); per-call scratch there is fine, state across calls is not.
- **Fix:** nothing at `$84` or above ("NEVER WRITTEN", 21 Sep 2026); new per-track state goes in a free slot of the module's own block (`$00..$83`) or the Y state table.

## OKMS1: EXCEPTION VEC:04 at the first Part Reload ✅ measured, fixed (KITS RELOAD)

- **Seen:** `ok-ms` OKMS1, 14 Sep 2026, midisc's author's unit: scenes following kits until the first Part Reload, then `EXCEPTION SSP:4 VEC:04 FS:0 SR:2000 ADDR:45D167E0 D0:40A96F54 SP:460D8D24` = `gk_stock_part_saved_to_working_reload_report_fatal` (an `illegal` Octakit plants); D0 = midisc's `rel_after`. Part Save and Part Clear worked in the same image. Source: `modules/kits-reload/README.md` "The collision is not a byte".
- **Cause:** midisc's `reload` stub replaces the return address on the stack with `rel_after`; Octakit's replacement of `0x4004aab4` accepts only the two stock return addresses (`0x4002dd5c`, `0x4005e060`) and traps on any other. Every byte the two mods write is disjoint, so the ledger saw nothing.
- **Fix:** KITS RELOAD keeps the stock `jsr` at both sites and moves midisc's post-work to the return sites (OKMS2, same unit, 14 Sep 2026). The ledger now checks `Runtime.pinned_returns`.

## Tape Echo `Vec:03` (address error) on the first optimised image ✅ measured, fixed

- **Seen:** the first hardware load of an optimised image (before 21 Sep 2026): `Vec:03` at `te_read_linear`'s scaled-index ring read `move.l (a1,d0.l*8),d5`. The emulator accepted it. Source: `modules/tapeecho/README.md` "On the unit".
- **Cause:** ColdFire raises an address error on scale factor eight.
- **Fix:** the reader forms the byte offset explicitly; generation rejects any `*8` memory address form. The same README lists a separate hardware freeze as open.

## Image 99: an FX2 change on T5 took the reverb off the track ✅ fixed (FX2 LOCK, 4 Oct 2026)

- **Seen:** image 99, 4 Oct 2026, bottleservice: an FX2 change on T5 took the reverb off the track; with the engines hidden from the chooser there was no row to put it back. Source: `modules/fx2-lock/README.md`.
- **Cause:** the FX2 chooser's select handler writes the Part's FX2 id for any track.
- **Fix:** FX2 LOCK: YES's entry in the chooser window's key table points at NO's handler, so the select handler never runs. Measured under the port by `verify_fx2lock`; no hardware result recorded in `modules/fx2-lock/README.md` ("On the unit: Not yet").

## Sound-on-sound plays a zero at each pass (sos-capture BUILD=94 and 95) ✅ measured on the unit (Bryan T), BUILD=95 fixes the cases run

- **Seen:** Bryan T's MKII, 3 Oct 2026, SOSCAP (T1 FLEX on R1, PLAY + REC1 + REC3 with SRC3 = T1 on step 1, 128 BPM, RLEN 16, 24-bit recorders): after a recorder reallocation every long-pass wrap is one sample of zero for the whole take (BUILD=94, three hold caves); in steady state every wrap is an exact repeat. Source: `CHANGELOG.md` "sos-capture BUILD=94 and BUILD=95", `modules/recorder-loop-fix/README.md` section 4.
- **Cause:** the fetch of index END (`+0x64`) finds no block and returns the empty pool base; after a second transport start the recording stays 82,687 samples on every pass and the recorder is past END when the voice reaches it, where the copy loops cap the voice at END − index = 0, stop it and zero-fill the frame. SRC3 records the zero back into the loop.
- **Fix:** BUILD=95 (#564, five hold caves: three fetch caves and two guard caves): the last sample is repeated. No zero in any take (16 → 24-bit reallocation, 24-bit off/on + reload, STOP/PLAY three times, steady state, RLEN 4 trigs); not run: STOP/PLAY on BUILD=94. Every 128 / RLEN 16 wrap is a repeat (lag 82,687 → 82,688) or a skip (82,688 → 82,687).

## BCR2000 locks up when the bank changes (image A2, unpaced CC FEEDBACK dump) ✅ fixed (image A3)

- **Seen:** Sam's MKII, image A2, 4 Oct 2026: the BCR2000 died the moment the bank changed; the dump of the new Part was up to 336 messages in about a second (DIN: 344 messages ≈ 1 s at 31.25 kbaud without running status). Source: `modules/cc-feedback/README.md` "On the unit", `modules/cc-feedback/cc_feedback.s`.
- **Cause:** the sweep put the whole dump on the wire at once. (The dark/deaf BCR on A02 and B1 is a separate cause: the entry "A BCR2000 goes dark or deaf on some patterns".)
- **Fix:** commit `41765855` (#584): one message per UI tick (120 Hz, `PACE`), about three seconds per full dump; image A3.

## A module calling the page-1 writer `0x40054cd8` bare halts the unit under Octakit ✅ measured under the port, fixed

- **Seen:** under the port, 26 Sep 2026: `bottleservice` halted (`illegal`, `0x45d2128e` in that build) at frame 40 of `verify_set`'s run on CC 68 (a MODE change re-defaulting page-1 knobs); TEMPO BUS and MODE DEFAULTS called the writer bare. Not flashed. Source: `modules/octakit/README.md` "Calling the page-1 writer beside her", `modules/tempo-bus/README.md`.
- **Cause:** Octakit rewrites the writer's dirty store (`0x40054fec`) to check a token long 12 bytes above the arguments (top half `GK_TRACK_PARAMETER_TOKEN_ARMED`, `0x54500000`) and halts on any other; her wrapper sets it and accepts only the three stock return addresses.
- **Fix:** both modules push the token (`P1TOKEN`, `modules/tempo-bus/helpers.s`, `modules/mode-defaults/modedef.s`).
