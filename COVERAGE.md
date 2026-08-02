# RE coverage vs. firmware features (OS 1.40 manual)

Cross-reference between what we have mapped/decompiled and the complete set of features
per the official manual (146 pp.). Legend: ✅ done · 🟡 partial (structure found, not fully
decompiled) · ⬜ untouched.

## Key discovery that reframes the remaining work

**The Octatrack's audio algorithms are NOT in the binary we have analyzed.** The MAIN OS
(ColdFire code) is the *control*: UI, sequencer, files, and the assembly of voice parameters.
The *signal processing* — sample playback, **timestretch**, and the **17 effects**
(filters, reverbs, delays, phaser…) — runs on the **DSP56xxx**, whose program is a **separate
binary** that the ColdFire uploads at startup (`FUN_40001d4c`, 24-bit words).

→ Reversing the actual audio (FX, timestretch) is a **separate project**: you have to **extract and
disassemble the DSP56xxx program** (24-bit DSP56300 architecture, a different disassembler).
That blob is not in `section_3_MAIN_OS.bin`; it has to be located (another section of the ELEK
container? data inside the MAIN OS that `FUN_40001d4c` receives as `param_1`?).

## Coverage matrix by subsystem

| Subsystem (manual ch.) | Status | What we have / what's missing |
|---|---|---|
| Hardware & boot | ✅ | ColdFire CPU, DSP boot, memory map. Missing: codec/DAC-ADC init, panel (encoders/buttons/LEDs), display driver |
| OS format & update (8.5.2, ch.18) | ✅ | ELUP/ELEK/aPLib, checksum, validation, ATA write, MIDI upgrade. Complete |
| Kernel / RTOS / scheduler | ✅ | Context switch, priority queues, PIT, TRAP #0. Missing: task list, allocator |
| ATA/CF storage | ✅ | ATA stack (PIO/DMA), driver+vtable, registers. Missing: FAT layer (vtable `_DAT_46c82xxx`) |
| File hierarchy: Sets/Projects/Audio Pool (ch.4,7,8) | 🟡 | Project settings serialization found; the rest missing (banks/parts/samples on disk) |
| Audio engine (voices) | 🟡 | Data model (voice `0x800049d8`, mailboxes), frame builder, handoff to the DSP. Missing: voice parameter computation, envelopes, amp modulator |
| Sample playback: FLEX vs STATIC | ⬜ | FLEX=RAM, STATIC=stream from CF. Not decompiled |
| **Timestretch** (NORMAL/BEAT) | ⬜ | On the DSP (separate binary) |
| **Effects — Appendix B (17 FX)** | 🟡 | All on the DSP. The **dispatcher ABI, per-instance memory allocator and parameter path are fully reversed**, and a custom reverb replaces DARK REV and runs on all 8 tracks (`dsp/reverb71.asm`, see `DSP.md` + `HANDOFF.md`). The stock algorithms themselves are still undecompiled |
| Machines — Appendix A (FLEX/STATIC/THRU/NEIGHBOR/PICKUP) | 🟡 | Dispatch by type found (`FUN_40097168`→0-4); logic not decompiled |
| Track recorders / Pickup / sampling (ch.9) | ⬜ | Recording of input to buffers. Only a passing glimpse ("ROTATING AUDIO") |
| Sequencer: clock/tick | ✅ | **Sample-accurate**: clocked by the audio frame ISR (`0x4000aad0`), `2³¹/tempo` phase accumulator; wakes the seq task via a kernel queue |
| Sequencer: trig → voice | 🟡 | `FUN_400977cc` maps trig→voice command. Found |
| Trig types / p-locks / sample locks (12.4-12.6) | ⬜ | Per-step automation. Not decompiled |
| Conditional locks / micro timing / fill / scales (12.12-12.15) | ⬜ | Trig conditions, probability, per-track lengths. Untouched |
| **Scenes & crossfader** (10.3) | ⬜ | Morphing of locked parameters. The OT's flagship feature. Untouched |
| **LFO designer** / LFOs (11.4) | ⬜ | 3 LFOs per track, custom shapes. Untouched |
| Arranger / song mode (ch.14) | ⬜ | Pattern chaining. Format in OctaLib; code not decompiled |
| MIDI sequencer (ch.15) | ⬜ | 8 MIDI tracks, notes/CC, MIDI LFOs. MIDI state found; engine not |
| MIDI I/O & sync (8.7) | ⬜ | MIDI parser, clock sync, transport, Turbo MIDI, CC control. Config found; UART/parser not |
| Audio editor (ch.13) | ⬜ | Trim/slice/loop points/timestretch setup. Untouched |
| Mixer / routing / audio crossfader (8.8, 11.6) | ⬜ | Main/Cue, levels, thru. Untouched |
| UI framework (menus, display, LEDs, encoders) | 🟡 | Dialog builder `FUN_4006d57c` found; missing the framework, display driver, input |
| USB disk mode (8.5.1) | ⬜ | Untouched |
| System/service: Test mode, Card tools, Personalize, Empty reset (18.1-18.5) | ⬜ | Untouched |
| Metronome (8.6.6) | ⬜ | Click track. Untouched |

## Summary

- **Done thoroughly (✅)**: ~5 subsystems — the system "plumbing" (boot, kernel, storage, update, HW map). It's the scaffolding: we understand *how the machine works*.
- **Partial (🟡)**: ~6 — the audio data model, the sequencer bridge, the project format, UI, machines.
- **Untouched (⬜)**: ~12 — nearly everything that makes the Octatrack *an instrument*: effects, timestretch, playback, the deep sequencer (p-locks, scenes, conditional trigs), LFOs, arranger, MIDI, audio editor.

## Suggested priorities (highest value first)

1. ~~Close out the sequencer clock~~ ✅ DONE — sample-accurate, frame ISR + phase accumulator.
2. **DSP56xxx program** — ✅ LOCATED AND EXTRACTED (`out/dsp_region.bin`, DSP56300, ~188 KB).
   Missing: **disassemble it with a DSP56300 target** → unlocks FX + timestretch.
3. **Sample playback engine** (ColdFire side): FLEX vs STATIC, how voices are fed to the DSP.
4. **Sequencer depth**: p-locks, conditional locks, scenes/crossfader — the "soul" of the OT.
5. **MIDI subsystem** (parser, sync, MIDI seq) and **UI/display framework**.
