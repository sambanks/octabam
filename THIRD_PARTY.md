# Third-party sources

What this repository carries from elsewhere, under which licence, and where.
`LICENSE` covers this repository's own code and documentation (MIT). Nothing
below is an Elektron byte: the firmware is the user's own copy, read at build
time (`.incbin`, `make os`).

## Transcribed into DSP modules

| source | licence | copyright | used in |
|---|---|---|---|
| jpcima `rc-effect-playground` — Hera `HeraChorus.dsp`, `bbd_line.h` (Juno-60 chorus) | ISC | Jean Pierre Cimalando | `modules/modulation` JUNO |
| pendragon-andyh Juno-60 chorus measurements | data | Andy Harman | `modules/modulation` JUNO (rates, delay ranges) |
| Roland SDD-320 Dimension D service notes + published measurements | laws only | — | `modules/modulation` DIM (the mix amounts were voiced here, not taken from the notes) |
| J. Dattorro, *Effect Design Part 2*, JAES 45(10), 1997 | paper (laws) | AES | `modules/modulation` FLNG (Table 6) |
| Mutable Instruments Rings `string.h` / `string.cc` | MIT | Emilie Gillet | `modules/modulation` COMB |
| Mutable Instruments Clouds `clouds/dsp/fx/reverb.h`, `fx_engine.h` (Griesinger plate) | MIT | Emilie Gillet | `modules/gateverb` |
| Mutable Instruments Clouds (the published design; no code) | MIT | Emilie Gillet | `modules/busdelay` GRAIN (the grain readers, by way of the removed `modules/nimbus`) |
| ChowDSP ChowPhaser (Schulte Compact Phasing A model) | BSD-3-Clause | Jatin Chowdhury | `modules/modulation` PHSR |
| Airwindows Pockey | MIT | Chris Johnson | `modules/character` TXTR, 13 to 22 Sep 2026 (removed; `git show OCTABAM43:modules/character/pockey_ref.py`) |
| Airwindows Pockey2 | MIT | Chris Johnson | `modules/character-txtr` TXTR (`pockey2_ref.py`; in `modules/character` on 5 Oct 2026, moved out the same day) |
| JClones TapeHead, DaTube, OInflator, AC1 (JSFX) | MIT | JClones | `modules/character` SAT (TAPE / TUBE / INFL), COMP / GLUE |
| audiojs/filter `moogLadder`, `oberheim` (Zavalishin's zero-delay forms) | MIT | audiojs contributors | `modules/spectrum` LADR, LP / BP |
| markandrus/octemu `custom/coldfire/usb-midi.s`, `custom/usb-midi.py` (descriptors) | MIT | markandrus | `modules/usb` (his text; one ISA-B substitution, README) |
| markandrus/octemu `custom/coldfire/usb-audio.s`, `custom/usb-audio.py` (descriptors) | MIT | markandrus | `modules/usb` (his shims, producer, packet builder and servo; the loader replaces his card payload machinery); the LAYOUT values TRACKS, MASTER, MAIN and MAIN CUE assemble the same source with fewer channels or other layouts (the README cites `usbaudio.s`, markandrus/octemu, MIT) |
| markandrus/octemu `src/board/ot-board.c` USB packet bench (line protocol) | MIT | markandrus | `tools/emu/ot_emu/usb.h` speaks the same protocol so his `tests/usb-host.py` drives the port; the model is written here |
| Airwindows Capacitor2 | MIT | Chris Johnson | `modules/spectrum` ISO (`capacitor2_ref.py`) |
| [CHOMPI-Club/CHOMPI](https://github.com/CHOMPI-Club/CHOMPI) WAVE firmware at `a73d732` | MIT (`modules/wave/LICENSE-CHOMPI`, `modules/waveload/LICENSE-CHOMPI`); CHOMPI is CHOMPI Club's trademark (their `TRADEMARKS.md`): used to say where the code comes from; not affiliated with or endorsed by CHOMPI Club or Chase Bliss | CHOMPI Club | `modules/wave`, `modules/waveload` |
| [RobinSchmidt/Open303](https://github.com/RobinSchmidt/Open303) (the TB-303 voice: oscillator, filter, envelopes, accent) | MIT | Robin Schmidt, 2009 (www.rs-met.com) | `modules/blackpyramids-303`: the DSP voice in both payloads (`bp_dsp_data.py` in the submodule) |
| DJ-Mixer `fx-dsp/core/src/blocks/TapeEchoBlock.cpp` | licence not stated in the tree | not stated in the tree | `modules/tapeecho`: the behavioural reference for voicing and the 44.1 kHz native comparison (`modules/tapeecho/README.md`); multi-head geometry and the physical-cell write model are not copied |
| BOSS SD-1 Super OverDrive service notes, ET5212-510A (3 Mar 1981) | part values only, no text | © Roland (BOSS) | `modules/distorx` SD-1 (the circuit modelled from its part values) |
| ElectroSmash, *Pro Co Rat Analysis*, https://www.electrosmash.com/proco-rat | part values, schematic, the clipping amplifier's response curve, the LM308's slew rate; laws only, no text | © ElectroSmash | `modules/distorx` RAT, TURB |
| LTspice `LedRed` diode model, as quoted on the All About Circuits forum | two numbers (IS, N) | © Analog Devices (LTspice library); values only | `modules/distorx` TURB |

Retired transcriptions (in history only): jpcima `string-machine` (BSL-1.0,
the Solina ensemble, removed 16 Sep 2026).

Surveyed for the modulation and station ports and not transcribed (GPL
code was read for laws only, never transcribed); each module's README has
the laws (`modules/modulation/README.md` "Sources"):

| source | licence | use |
|---|---|---|
| Airwindows Chorus, ChorusEnsemble, StereoChorus, Vibrato, GalacticVibe, Flutter2, Ensemble | MIT | surveyed |
| jpcima `bbd-delay-experimental`, `ensemble-chorus` | BSL-1.0 | surveyed |
| Mutable Instruments Rings `chorus.h`, `ensemble.h` | MIT | surveyed |
| Faust `phaflangers.lib` `phaser2`, `flanger_mono` (J.O. Smith) | STK-4.3 (MIT-style) | laws (`flanger_mono` beside Dattorro for FLNG) |
| TAL-NoiseMaker chorus, Surge XT chorus/Ensemble, JunoX, chowdsp BBD | GPL | laws only |
| Rakarrack/guitarix Vibe, BYOD Solo-Vibe, Zyn APhaser | GPL | laws only |

## Measurements, circuit values and laws behind ColdFire modules (no code transcribed)

What a module's model is fitted to or built from, when nothing of the source's own text or audio is
in the tree. The recordings are not redistributed: the fits are numbers in the module's tables.

| source | what is used | licence / status | used in |
|---|---|---|---|
| Din Sync, *TB-303 reference recordings for x0xb0x* (25 files, 400 notes at C2 with known knob positions), http://www.dinsync.info/2010/02/tb-303-reference-recordings-for-x0xb0x.html | the calibration target: band levels, peaks, the resonance's ring decay, brightness over time, accent peaks; fitted constants in `tools/octa303/o3tables.py` (and `ladder_cache.json`, coefficients solved from them) | recordings published for x0xb0x builders; licence not stated; not redistributed (measured locally, numbers only) | `modules/octa303` |
| tinyloops, *Programming the Roland TB-303*, https://tinyloops.com/tb303/index.html | two example recordings (the resonant "drops", "saw with only accents") for the ring decay and the accent | licence not stated; not redistributed (numbers only) | `modules/octa303` |
| Robin Whittle, *Devil Fish* manual (2019) and "TB-303 unique" notes, Real World Interfaces, https://www.firstpr.com.au/rwi/dfish/ | circuit values and behaviour: the gate length (3.5 of 6 clocks), the accent RC (47k x 0.033 µF; 47k + 100k with 1 µF), the slide RC, the square's duty by pitch | © Robin Whittle; laws and component values only, no text | `modules/octa303` (and the Devil Fish laws `DF_*` in `tools/octa303/o3tables.py`, read by the `devilish` knobs) |
| Tim Stinchcombe, analysis of the TB-303 diode ladder ("diode2"), https://www.timstinchcombe.co.uk/index.php?pge=diode2 | the transfer function the ladder's low-frequency behaviour was checked against | © Tim Stinchcombe; laws only | `modules/octa303` |
| Roland, TB-303 service notes | the DECAY range, the ENV MOD taper, the slide capacitor | © Roland; values only | `modules/octa303` |
| Tim Hastie, SYNTH MACHINE 2.9, https://github.com/timhastie/octatrick-modules (`v2.9` = `525f4b1`) | the FLEX integration re-done for one voice (the renderer call `sy_render(track, ping, start, end)`, START resolution, PTCH/RATE neutral, pinned positions, the clean retrig byte, the PLAYBACK page clone) and the semitone tuning system; `octa303.s` is written here | MIT, Tim Hastie 2026 | `modules/octa303` |
| repeat98, `analog-bassdrum` (this repository) | the measured machine-list seams the OCTA-303 row uses | this repository's MIT | `modules/octa303` |
| devilfish707, Play Modes investigation, [devilfish707/Octaplay](https://github.com/devilfish707/Octaplay) `playmodes/INVESTIGATION.md` at `acd6b0c` | the sequencer addresses and findings: the per-track step counters, the tick's and the rebuild's step-handler calls, the per-track advance, the UI step query, MIDI mode, the trig-key dispatcher; TRACK PATTERNS writes its own code at those sites | MIT (the repository's LICENSE); addresses and findings only, no code | `modules/trackpatterns` |

## Firmware modifications built from their authors' repositories (git submodules)

| module | upstream | licence |
|---|---|---|
| `modules/midi-scenes` (MIDI SCENES) | https://github.com/bkkbrls-del/midisc | MIT (the repository's LICENSE file, added by its author 9 Sep 2026, carries octabam's copyright line verbatim) |
| `modules/octakit` (Octakit; a submodule built here until 6 Oct 2026) | https://github.com/emuyia/ems-octakit | MIT, Copyright (c) 2026 June Kiff |
| `tools/remix/loader.S` (the DRAM loader) | derived from Octakit's `runtime/loader.S` | MIT, Copyright (c) 2026 June Kiff |
| `tools/remix/pack.py` (the payload packer) | ported from Octakit's encoder (`patcher/src/lib.rs`) | MIT, Copyright (c) 2026 June Kiff |
| `modules/synth`, `modules/quantizer`, `modules/direct-jump`, `modules/tuner` (SYNTH MACHINE, SCALE QUANTIZER, DIRECT JUMP, TUNER) | https://github.com/timhastie/octatrick-modules (one submodule, four wrappers; pinned to `v2.9` = `525f4b1`) | MIT, Tim Hastie 2026 |
| `modules/cxosc` (CX OSC) | local fork of https://github.com/timhastie/octatrick-modules: `poly.s` from `v2.9` = `525f4b1`; `page.s` and `machine.s` from `v2.15` = `17ba281` (machine.s adapted by Tim from Modwerk's FM Synth, https://github.com/repeat98/modwerk `1c1d938`) | MIT, Tim Hastie 2026; Modwerk contributors 2026 (through Tim's `machine.s`); CX OSC voice/page changes by ilia-murzinov — `modules/cxosc/NOTICE`, `LICENSE-TIM` |
| `modules/midi-scales` (MIDI SCALES) | https://github.com/radiohagen/octatrack-modules (submodule at `modules/midi-scales/upstream`; pinned to `5d3deea149fe2a17b6f2fae10e53f0dea21bf1c2`) | MIT; module author: Mattias Wolff (`radiohagen`); inherited Octabam notices retained |
| `modules/midi-loopback` (MIDI LOOPBACK) | https://github.com/radiohagen/octatrack-modules (submodule at `modules/midi-loopback/upstream`; pinned to `5d3deea149fe2a17b6f2fae10e53f0dea21bf1c2`) | MIT; module author: Mattias Wolff (`radiohagen`); inherited Octabam notices retained |
| `modules/midi-follow` (MIDI FOLLOW) | https://github.com/radiohagen/octatrack-modules (submodule at `modules/midi-follow/upstream`; pinned to `5d3deea149fe2a17b6f2fae10e53f0dea21bf1c2`) | MIT; module author: Mattias Wolff (`radiohagen`); inherited Octabam notices retained |
| `modules/store/part*.s` (native Part access) | derived from MIDI PART STATE in https://github.com/radiohagen/octatrack-modules at `3b1fda3410e698718230d984901a34a02e9346ab`; generalized in this repository | MIT; original native Part source by Mattias Wolff (`radiohagen`); inherited Octabam notices retained |
| `modules/direct-jump-kyoti`, `modules/reload-from-project`, `modules/sidechain-compressor`, `modules/blackpyramids-303`, `modules/varispeed` (DIRECT_JUMP_KYOTI, RELOAD_FROM_PROJECT, SIDECHAIN_COMPRESSOR, BLACKPYRAMIDS_303, VARISPEED) | https://github.com/Zac-Kyoti/octatrack-kyoti-fw (one repository, ten submodule mounts; DIRECT_JUMP_KYOTI pinned to `329b801`, RELOAD_FROM_PROJECT to `6a2da8d`; SIDECHAIN_COMPRESSOR to `b0d49bf`; BLACKPYRAMIDS_303 to `9b2e35a`; VARISPEED to `9b2e35a`) | MIT, Zac-Kyoti and the OT Kyoti FW contributors 2026 |
| `modules/batch-bugfixes`, `modules/quantize-live-rec-toggle`, `modules/erase-empty-trigless-locks` (BATCH_BUGFIXES, QUANTIZE_LIVE_REC_TOGGLE, ERASE_EMPTY_TRIGLESS_LOCKS) | https://github.com/Zac-Kyoti/octatrack-kyoti-fw (three mounts; BATCH_BUGFIXES and ERASE_EMPTY_TRIGLESS_LOCKS pinned to `77f132f`, QUANTIZE_LIVE_REC_TOGGLE to `9c890bb`) | MIT, Zac-Kyoti and the OT Kyoti FW contributors 2026 |
| `modules/mute-modes` (MUTE_MODES) | https://github.com/Zac-Kyoti/octatrack-kyoti-fw (one mount, pinned to `a1e0288`) | MIT, Zac-Kyoti and the OT Kyoti FW contributors 2026 |
| `modules/rec-trig-mute` (REC_TRIG_MUTE) | https://github.com/Zac-Kyoti/octatrack-kyoti-fw (one mount, pinned to `0bc14c7`) | MIT, Zac-Kyoti and the OT Kyoti FW contributors 2026 |

The MIDI source repository's [attribution record](https://github.com/radiohagen/octatrack-modules/blob/5d3deea149fe2a17b6f2fae10e53f0dea21bf1c2/THIRD_PARTY.md)
credits Mattias Wolff's module work. Its root `LICENSE` reproduces the inherited
Octabam MIT notice naming Sam Banks for repository tooling; that notice is
preserved and is separate from the module authorship recorded above.

`modules/kits-reload`, `modules/scenes-kits`, `modules/cc-map`,
`modules/tempo-sync`, `modules/mode-defaults` and `modules/recorder-loop-fix`
have `sambanks` as author in their manifests; none of these module
directories holds a `LICENSE` file, and the repository `LICENSE` (MIT) covers
them. `modules/lofi-amf-fix` has `bryantysinger/octa-bt-pt` as author in its
manifest and its README says it is ported from that repository; its licence
is not stated in the tree.

## Emulator and panel from a fork of this repository

| source | licence | copyright | used in |
|---|---|---|---|
| Tim Hastie, [timhastie/octa-panel](https://github.com/timhastie/octa-panel) at `be68244` (a fork of octabam, 10-25 Sep 2026) | MIT (the fork's `LICENSE` is octabam's, copyright line unchanged) | Tim Hastie (his changes) | `tools/panel/` (the virtual front panel, the macOS app, the key/LED map and its evidence); `tools/emu/ot_emu` (`--interactive`, pacing, the DSPI RTC, DMA timers DTIM0-3, event-horizon bursts, the page-table memory path, lazy DSP batching, `--dsp-rt`, bounded records, card write-back, memory-to-memory eDMA copies, per-track taps; `oracle/`, `pgo.sh`); the `--dsp-rt` hunks of `tools/patches/dsp56300.patch`; `git show 666b6154:docs/firmware/COLDFIRE_PORT.md` (his milestones O14i-O24) |
| Mark Roberts, [markandrus/octemu](https://github.com/markandrus/octemu) `assets/panel/gen_svg.py` | MIT (Copyright (c) 2026 Mark Roberts) | Mark Roberts | `tools/panel/skin/gen_svg.py`: the MKII front panel drawn as SVG (geometry measured from photographs of a unit, keys, knobs, fader, LEDs, the lighting classes); octabam added the `dark` palette and an output directory |

## Contributions received

Reverse-engineering results and notes contributed by others, by date, with
where each now lives. The facts are in the topical docs with their status
markers (✅ re-verified here · 🟡 adopted on the author's evidence · ❌
retracts something written here) and the author's name beside them. The
ingest record with the notes exchanged verbatim is
`git show 3ceba41:docs/history/EXTERNAL_INGEST.md`. All were derived from
the officially distributed OS 1.40C (`section_3_MAIN_OS.bin` SHA-256
`164f3122…`, base `0x40000400`). Modules that arrived as code: midisc and Octakit are in the
firmware-modification table above; REPITCH (repeat98, `modules/repitch`)
was removed 14 Oct 2026 at its author's request; no `modules/octalab`
exists in the tree, and nordseele's
octalab appears here as the `octalab-notes` rows below.

| received | from | what | where it lives |
|---|---|---|---|
| 30 Aug 2026 | Bryan T | the Echo Freeze DELAY is a ColdFire routine over SDRAM rings | `docs/firmware/COLDFIRE_DELAY.md` section 1 🟡 |
| 30 Aug 2026 | Bryan T | the ESAI carries audio ("does not" retracted) | `docs/firmware/DSP.md` section 6c ✅ |
| 30 Aug 2026 | Bryan T | timestretch is a ColdFire feature; `P:0x3a1` / `P:0x2bf` / `func_00055a` relabelled | `docs/firmware/DSP.md` section 3 🟡 |
| 30 Aug 2026 | Bryan T | the data-table atlas (Q23 decode of every X/Y module) | `docs/firmware/TABLES.md` 🟡, evaluated 31 Aug |
| 30 Aug 2026 | Bryan T | `objdump -m m68k:cfv4e` for EMAC regions; radare2 cannot decode this CPU | `docs/contributing/TOOLING.md` section 3 ✅ |
| 2–6 Sep 2026 | Bryan T | the track recorders, five sessions: descriptor, storage tiers, length arithmetic, pool, write path, loop point | `docs/firmware/RECORDER.md` sections 1–2 ✅ bytes, 🟡 reading |
| 4 Sep 2026 | Bryan T | `bryantysinger/octa-bt-pt` (stock-effect defaults patcher; its parameter registry) | `docs/firmware/PARAM_PAGES.md` section 5g |
| 4 Sep 2026 | June Kiff | `emuyia/ems-octakit` (256 kits) | `modules/octakit`, a submodule (above); replaced by `modules/kits` 6 Oct 2026, which follows its key map and reads its `kits3a/b.work` |
| 6 Sep 2026 | Bryan T | *Sound-on-Sound Looping with the Octatrack* (PDF) and `octatrack_clickless_loops.xlsx`; not in this repo | `docs/firmware/RECORDER.md` section 3 |
| 13 Sep 2026 | nordseele | [`octalab-notes`](https://github.com/nordseele/octalab-notes) at `40ffa53` (MIT, findings only), from an Octatrack MKI running our loader: FS layer, slot loading, Parts, the card's files, step records and lock stores, the input layer, menus, the platform reserve on hardware | `docs/firmware/STORAGE.md`; `docs/firmware/PARAM_PAGES.md` section 5g; `docs/firmware/PANEL.md` section 4b; `docs/firmware/MAINMENU.md` section 2, section 5; `docs/contributing/PLACEMENT.md`; `docs/firmware/MIDI.md` (PLAYBACK `machine*6`); `tools/hw/ot_project.py` (trig masks `0x40`/`0x48`) |
| 14 Sep 2026 | Bryan T | absolute X addresses are payload-relative (his LOFI2 mistuned on tracks 1–4) | `docs/firmware/TABLES.md` "Payload-relative addresses" ✅; `docs/contributing/FAILURE_MODES.md` |
| 16 Sep 2026 | Bryan T | the parameter enable bitmaps | `docs/firmware/PARAM_PAGES.md` section 3b ✅, with retractions |
| 21 Sep 2026 | Bryan T | the track LFO engine | `docs/firmware/LFO.md` (section 8 what was checked) ✅, with retractions both ways |
| 21 Sep 2026 | Bryan T (hardware) | MAIN/CUE are `(L/128)²` | `docs/firmware/LEVEL_LAW.md` (section 7 what was checked) ✅ |
| 22 Sep 2026 | Jannik Aßfalg (repeat98) | beside Tape Echo (PR #357): the delay routine's frame, seam and per-frame protocol; benchmarking practice for a ColdFire module | `docs/firmware/COLDFIRE_DELAY.md` sections 2–4 ✅, with a retraction; `docs/contributing/MODULES.md` "Pricing a ColdFire module"; `docs/contributing/FAILURE_MODES.md` |
| 23 Sep 2026 | nordseele | [`octalab-notes`](https://github.com/nordseele/octalab-notes) `40ffa53` → `e0dc56d` (nine commits, 13–22 Sep): a FAT directory record's first cluster is the long at `+0x11e`; the storage-job entry `0x40024168` takes its kind/object from `0x460be9e8`/`ec` and a stock save path ran on a MKI; a recorder-reserve figure from the emulator; a held trig under a page of one's own; the SETUP windows' draw calls and the eight font records; their own `+0x10` trig-mask label and current-pattern/part mapping lowered to 🟡 | `docs/firmware/STORAGE.md` section 1 ✅; `docs/firmware/SAMPLE_SAVE.md` section 7 ✅; `docs/firmware/RECORDER.md` section 2 🟡; `docs/firmware/MAINMENU.md` section 6b; `docs/firmware/PANEL.md` sections 2–3; `docs/firmware/PARAM_PAGES.md` section 5g |
| 22 Sep 2026 | markandrus (public repo, not sent to us) | [`octemu`](https://github.com/markandrus/octemu) at `8ccdd84`'s dsp56300 pin (QEMU 11.1 + dsp56300 + SDL2 Octatrack emulator, credits this project as inspiration): three MAC-with-load decode defects in Unicorn's vendored QEMU, confirmed against Unicorn's own source; that `vendor/dsp56300` was 144 commits behind upstream, absorbing several of our own fixes independently; the DMA "de-renewal" semantics for a same-value DCR rewrite mid-window. His three ColdFire firmware customisations (RECEIVE machine, USB-MIDI, USB-Audio) and `re/*.syms` (768 ColdFire + 150 DSP symbols) were reviewed 22 Sep and not adopted then; on 25 Sep 2026 USB-MIDI and USB-Audio were ported onto the DRAM platform (`modules/usb-midi`, `modules/usb-audio-out`) with the port's own USB device-controller model (`tools/emu/ot_emu/usb.h`, his bench protocol) as the off-device gate; his QEMU and dsp56300 patches beyond the three above did not apply to our Unicorn/dsp56300 or were JIT-only, N/A to `execInterpreter()` | `tools/patches/unicorn_emac_fractional.patch` ✅ (PR #360); `docs/contributing/TOOLING.md` section 1 (the re-pin, PR #365; the DE-renewal, PR #367); `tools/emu/README.md` (the "no MAC-with-parallel-load form" retraction) |
| 23 Sep 2026 | Jannik Aßfalg (repeat98) | `STOCK_PROFILE.md`: a stock-firmware ColdFire instruction profile under his port build (frame ISR, delay, sample analysis, voice renderer extents); the port's ACCext write knew only the fractional layout, which the frame ISR's integer-mode save/restore reaches every frame; `FUN_4000c8a4` is not a function boundary. His `stock-analysis-fast` module and `--work-profile` counter were not sent | `tools/emu/ot_emu/v4e.cpp` + `test_emac.cpp` ✅ (eight assertions); `tools/emu/README.md` (the fix; the profile 🟡, the extents ✅); `docs/firmware/MIDI.md` ❌ the label; `docs/firmware/COLDFIRE_DELAY.md` the routine's end ✅ |
| 25 Sep 2026 | Tim Hastie | [`octa-panel`](https://github.com/timhastie/octa-panel) at `be68244` (a fork of this repository, 10-25 Sep 2026, MIT): the virtual front panel over the firmware's own panel-UART stream (LCD blocks 0x10-0x17, LED rows, the key matrix, encoders, crossfader); the port's real-time mode with sound (the DSP cores as JIT worker threads, O17-O17c) and two vendored-JIT defects (MPYI's immediate unsigned -- upstream fixed it independently; a bit op on an M register left its modulo words stale); the DMA timers on the 132 MHz bus (DTRR2 = 132,000,000 for one second); the Echo Freeze Delay's memory-to-memory eDMA copies and the TCD's ATTR/SOFF order; the EMAC -1 x -1 product; the firmware mounting the last set at boot once the sys tick runs. His modules (direct-jump, quantizer, synth) were not ported | `tools/panel/` ✅ (PR); `tools/emu/ot_emu` ✅ (the lockstep block dump equals main's with his three model changes reverted); `git show 666b6154:docs/firmware/COLDFIRE_PORT.md` O14i-O24 🟡 (his records); `docs/firmware/DSP.md` "Core 0's frame", `docs/firmware/STORAGE.md` section 4 |

## Analysis tooling

Portions of the firmware analysis tooling originate from
https://github.com/mxldyn/octamax, Copyright (c) 2025-2026 Maxolydian. The
repository `LICENSE` says "also under the MIT License".
`modules/batch-bugfixes/upstream/CREDITS.md` says octamax ships no `LICENSE`
file, that the setup scripts carried over (`fetch-os.sh`, `analyze.sh`,
`setup.sh`, `tools/entropy.py`, `tools/bin_decode.py`) stay its author's, and
that octamax's stance is educational use only with no binaries
redistributed. The two statements are not reconciled in the tree.

`tools/ghidra/processors/DSP56300/` (the DSP56300 processor module) and
`tools/ghidra/patches/coldfire-emac.patch` (ColdFire ISA_C/EMAC in Ghidra's
68000 module) were written for this repository by Robert Gay and are offered
to Ghidra upstream as `roblg/ghidra` #3 and #2. They carry Ghidra's
licence, Apache-2.0, in each file's header so they can go upstream as they
are; the patch is a diff against Ghidra 12.1.4's
`Ghidra/Processors/68000` (Apache-2.0, National Security Agency).
`make ghidra-install` adds both to a copy of your own Ghidra release; no
Ghidra file is committed.

## Fetched by `make setup`, never committed (`vendor/`, gitignored)

| what | licence | note |
|---|---|---|
| dsp56300 (DSP56300 emulator; `dsp_asm` / `dsp_host` are additions written here, under `tools/harness/dsp_host/`) | GPL-3.0 | patches in `tools/patches/`; built binaries are never distributed |
| joelanders/mc68k-md-mm (Musashi-derived ColdFire core) | GPL-3.0 | pinned commit in `scripts/setup.sh` |
| mischa85/elektron-firmware-tool | MIT, Copyright (c) 2026 Marcel Bierling | `tools/patches/elektron-firmware-tool.patch` |
| Unicorn (via `.venv`, `make emu-setup`) | GPL-2.0 | `tools/patches/unicorn_emac_fractional.patch` |
