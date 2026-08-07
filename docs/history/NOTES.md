# RE Log — Octatrack

Record of findings. Each run of `analyze.sh` leaves evidence in `out/`.

## Phase 0 — Static recon of the public OS  [COMPLETED ✓ 2026-07-26]

Goal: decide whether the payload is **compressed** (feasible) or **strongly encrypted** (blocking),
and identify where the real ColdFire code lives. **Result: compressed. Firmware obtained.**

Checklist:
- [x] Download official OS 1.40C + record sha256
- [x] Entropy of `.bin` and `.syx`
- [x] elektron-firmware-tool on `.syx` → extracts the raw section, checksums OK
- [x] Confirm container: Octatrack uses **ELEK** (within the supported family)
- [x] Save the decompressed raw as a candidate for disassembly
- [ ] binwalk on the `ELUP` `.bin` (optional; the `.syx` already yielded the raw)

### Results

- **Artifacts** (`OCTATRACK_OS1.40C_dist.zip`, sha256 `370c55a3…73ff0`):
  - `.bin` (459 KB): magic `ELUP`, entropy **uniform ~8.0** (compressed end to end).
  - `.syx` (641 KB): `F0 00 20 3C` (SysEx + Elektron ID) wrapping the **`ELEK`** container.
- **elektron-firmware-tool `-i`**: `device: Octatrack (0x05)`, `version 1.40C`,
  container `ELEK` 469834 B, **section id 3 "MAIN OS" → 1,112,560 B decompressed**, checksums OK.
- **Decompressed raw** `out/raw/section_3_MAIN_OS.bin` (1,112,560 B):
  - Mean entropy **5.5** (real code+data, NOT encrypted); only 3.8% of windows are high.
  - **2908 readable strings**: UI menus, error codes, `/octatrack_factory_os.bin`.
  - m68k big-endian disassembly OK: prologue `lea -0x1c(a7),a7` + `movem.l d2-d7/a2,(a7)`.

### Memory-map clues (from absolute refs in the code)

- **Data/BSS in SDRAM base `0x40000000`** (refs to `0x400b9650`, `0x400b9654`, `0x400dea48`).
- Initial stack loaded from ~`0x48000000`.
- **Code load** base: still to be determined (the raw starts in code, not in a vector table).
  Strategy: locate where the code references its own strings to fix the base address.

## Phase 1 — Static disassembly  [IN PROGRESS]

- Target: **ColdFire / m68k, big-endian**.
  - radare2: `scripts/disasm.sh` (already configured with base and arch).
  - Ghidra: processor `68000`, big-endian, base `0x40000400`; then run
    `tools/ghidra_import.py` to define strings/pointers and populate xrefs.

### BASE ADDRESS DETERMINED ✓  =  `0x40000400`

Empirical method (`tools/find_base.py`, not an assumption): correlate the offsets of
the 2607 strings in the file against the absolute 32-bit pointers (high byte 0x40).
The sweep of candidate bases gave an unambiguous peak:

| candidate base | strings with a direct pointer |
|---|---|
| **0x40000400** | **1441** |
| 0x400003dc | 291 |
| 0x40000424 | 290 |

- Peak 5× over the second → solid base. Image in SDRAM `0x40000000` + `0x400` of
  header/vectors; the decompressed MAIN OS section maps at `0x40000400`.
- Data/BSS at `~0x400bxxxx` (consistent: `0x400b9650 - 0x40000400 = 0xb9250`, inside the image).
- Verified in r2: at `0x40000400` the prologue `lea -0x1c(a7),a7` + `movem.l` appears,
  and there is code `move.l #0x400b3349,d0` loading pointers to strings as immediates.
- Artifacts: `out/base.txt`, `out/pointers_to_strings.csv` (**1993 sites** ptr→string).

### Function → UI-strings map ✓  (`tools/string_func_map.py` → `out/string_function_map.txt`)

Detects string-pointer loads in the code (`pea`/`lea`/`move.l #imm`) and walks back
to the function prologue (`LINK`/`lea -n(a7),a7`). **619 functions** anchored to strings,
1060 refs in code. Key functions already identified by name:

| Function | What it is (by its strings) |
|---|---|
| `0x40086d7a` | **Serializes project settings** — 58 keys (`MIDI_CLOCK_SEND`, `MASTER_TRACK`, `MAIN_LEVEL`…) |
| `0x4001fc1e` | **Error handler** — 49 strings (`WAV/AIFF PARSE ERROR`, `SAMPLE NOT UNLOADED`…) |
| `0x400867e0` | Writes the `[SAMPLE]` section of the project file (OctaLib format) |
| `0x40069424` | `FORMAT CARD` handler |
| `0x400645ce` | `SAVE PROJECT` handler |
| `0x40022fdc` | `COLLECT SAMPLES` handler |

This **connects the firmware to the already-documented file format**: the settings
function emits exactly the project-file keys in plain text.

### Decompilation in Ghidra ✓  (12.1.2, language `68000:BE:32:Coldfire`, base 0x40000400)

Project in `out/ghidra_proj`. Scripts: `tools/GhidraDecompile*.java` (Ghidra 12 doesn't ship
Jython → use Java). Logs: `out/ghidra_decompile*.log`.

**Finding: shared dialog constructor `FUN_4006d57c`**
Reconstructed signature: `(title, num_options, char **options, default, confirm_callback)`.
Creates a popup (measures text with the font at `DAT_400ba876`, window via `FUN_4005829c`) and
stores the confirmation callback. Every action menu calls it with its label.

**OS UPGRADE flow traced end to end** (`FUN_400636bc`):
```c
if (FUN_400448dc() == 0)   FUN_40063660(0);          // no playback -> direct upgrade
else {                                                // with playback:
    opts = {"PLAYBACK WILL BE", "STOPPED. CONTINUE?"};
    FUN_4006d57c("OS UPGRADE", 2, opts, 3, FUN_40063660);  // dialog; on confirm -> FUN_40063660
}
```
→ **`FUN_40063660` = the actual OS update routine** (next target to decompile).

**ColdFire hardware registers identified** (in the init/main function `~0x4001fc1e`):
- `0x20000008` — status register polled at boot (`while ((*0x20000008 & 6)==0)`).
- `0xfc04xxxx` — on-chip peripheral space (MBAR) of the ColdFire (init writes).
- App data/BSS at `0x460exxxx` and `0x46c8xxxx` (in addition to the `0x400bxxxx` of the image).

**Known limitation**: the ColdFire decompiler fails ("Cannot properly adjust input
varnodes") on large functions with complex frames (e.g. `project_settings_serialize`
5388 B, `project_sample_section` 1434 B). The disassembly does work; analyze them at the ASM level.

### Complete OS UPGRADE chain (decompiled) ✓  — logs `out/ghidra_{osupgrade,flashwriter,apply,program}.log`

```
OS UPGRADE menu
  └─ FUN_400636bc   confirms "PLAYBACK WILL BE / STOPPED. CONTINUE?" (via FUN_4006d57c)
      └─ FUN_40063660 (os_upgrade)  stops audio, "WORKING PLEASE WAIT", QUEUES a deferred task:
          └─ FUN_4006370c  scans the CF, picks the OS file, validates existence
              └─ FUN_40080434 (os_apply_flash)  critical section + calls the loader and maps errors
                  └─ FUN_4007f748 (os_file_program)  << THE CORE: parses/deobfuscates/verifies >>
```

**`FUN_4007f748(path, mode)` — OS file format (`.bin`, magic ELUP):**
- `fopen`; if it fails → `-1 IO_ERROR`. Reads size; `payload = filesize - 0xC` (12 B header).
- `payload > 0x100000` (1 MiB) → `-3 LENGTH_ERROR`.
- Header (words): `[0]`=magic (`== DAT_400a966c`), `[1]`=feedback seed,
  `[3]`=flags (bit `0x800000` selects variant) + checksum, `[4]`=version material. Payload from `[2]`.
- **Obfuscation = XOR cipher with feedback** (not compression, not real crypto):
  each word: `p ^= 0x9E3B16A2` (or `0x764E28CA` if flag) → rotate/byteswap → `k ^= prev_cipher ^ x`.
  Constants **fixed and embedded** → the `.bin` is fully decodable offline. (This explains the
  uniform ~8.0 entropy of Phase 0: it's this XOR stream, not compression.)
- **Integrity = additive checksum** (sum of deobfuscated words) compared with the stored value;
  mismatch → `-4 CHECKSUM_ERROR`. **There is NO cryptographic signature** (confirms Phase 0: modifiable firmware).
- **Model/version gating**: `< "0156"` (0x30313536) → `-5 MK1_OS_NOT_ALLOWED`;
  `< "0178"` (0x30313738) → `-6 CAN_NOT_DOWNGRADE`. Version = packed ASCII.
- `mode=1` → only returns the version (for the pre-scan). `mode=0` → deobfuscate+verify (commit).
- On successful completion: `FUN_4007fe80(0xffffffff,...)` finalizes/reboots into the new OS.

### Offline `.bin` decoder ✓✓✓  (`tools/bin_decode.py` + `tools/decode_elek.c`)

Reimplementation of `FUN_4007f748`. Constants extracted from the OS image:
`magic=0x454C5550 ("ELUP")`, `C3=0x360FA955`, `C7=0xEF4A9AB6`, XOR `0x9E3B16A2`/`0x764E28CA`.

**Double validation:**
1. `bin_decode.py` deobfuscates the `.bin` and **the additive checksum matches** (`0xa85be7ef`) — the
   SAME check the firmware performs → deobfuscation demonstrably correct.
2. The deobfuscated payload is an **`ELEK0178`** container (identical to the one in the `.syx`). `decode_elek.c`
   (reuses the tool's `ap_depack`/aPLib) decompresses it → **1,112,560 B, SHA256 `164f3122…`**,
   **byte-identical to the MAIN OS extracted from the `.syx`**.

**Full chain reconstructed and verified end to end:**
```
.bin  = [ELUP hdr][seed] + XOR-feedback( [len] + ELEK(aPLib(MAIN_OS)) ) + checksum
.syx  = SysEx 7-bit( ELEK(aPLib(MAIN_OS)) )
                                    → both → the SAME MAIN OS (164f3122…)
```
No cryptographic signature at any layer: reversible XOR obfuscation + additive checksum + aPLib.

### Full storage stack (decompiled) ✓ — logs `out/ghidra_{commit,hw,drv,fac,prim,txn,disp,ata}.log`

Traced from the UI down to the ATA registers. **The OS "flash" = writing to the CompactFlash (ATA)**;
the driver is the ColdFire ATA block stack, NOT an internal NOR flash.

```
os_apply_flash (FUN_40080434)
  └─ FUN_400323a0   dispatches via driver vtable: (*(obj+0x10))(0)   [obj=_DAT_460d16cc]
      └─ FUN_400158cc  = method +0x10 → sends ATA command 0xE0 (STANDBY IMMEDIATE: flush/park before reboot)
          └─ FUN_4001568c  QUEUES the command (async ring, 0x16 B entry) + reserves event (_DAT_460babfc) + waits
              └─ FUN_40015098  DISPATCHER: drains the queue and dispatches by ATA opcode:
                    0x20 READ SECT · 0x30 WRITE SECT · 0x87 · 0xC0 · 0xC8 READ DMA · 0xCA WRITE DMA · 0xE0 STANDBY
                    └─ FUN_40014c48 (0x30 WRITE SECTORS)  ← ATA task-file registers @ 0x90000000 (FlexBus)
```

- **Factory driver** `FUN_40015e28`: builds the vtable at `&DAT_46c85c76` (methods 0x400157xx/0x400158xx)
  and **detects the hardware variant** by reading an IDENTIFY-type descriptor (offsets 0x62/0x6a/0x146/0x7e/0xb0).
- **Confirmed hardware map**:
  - ATA host registers (control/config) in ColdFire MBAR: `0xFC04_51xx`, status `0xFC0A_4039`.
  - ATA task-file (data/LBA/cmd/status) in FlexBus window `0x9000_00xx`
    (data=0xa0, seccount=0xa8, lba=0xac/b0/b4, dev=0xb8, cmd=0xbc, status=0xd8).
  - **The MCF5445x has an on-chip ATA controller → corroborates the ColdFire CPU from Phase 0.**
- **RTOS confirmed (not bare-metal)**: async I/O via command queue with event-based completion
  (bit pool at `_DAT_460babfc`), a worker that drains the queue. There are tasks and synchronization.

## Musical layer — audio/sequencer engine (decompiled) — logs `out/ghidra_{play,trk,voice,voice2}.log`

Engine data map (all in the RAM window `0x80000000` = hot state):

| Structure | Address / layout | What it is |
|---|---|---|
| Per-track voice state | base `0x800049d8`, stride `0xA8`, 8 tracks | live audio voice; byte[0] = active |
| "Active voice" query | `FUN_40000ee0(t)` reads `0x800049d8[t*0xA8]` | 0=inactive, 1/2 per `0x8000184a` |
| "Something sounding" query | `FUN_400448dc` walks the 8 tracks | used by OS-upgrade to block |
| MIDI tracks state | `0x80006500[t]`, global `0x800065b8` | MIDI mute/active flags |
| Voice command mailboxes | `0x46c7e9fa`/`0x800018be`/`0x800018de` `[t*4]` | `FUN_40005178` queues per-track commands |
| Per-track pattern data | `_DAT_46c82456 + pat*0x18b2 + trk*0xc` (+0x8f385) | sequenced data (trigs/params) |
| Globals | current track `0x100b14cc`, current pattern `0x80000003` | live selection |

**Confirmed architecture — same pattern as storage**: `FUN_40005178` (command voice)
writes mailboxes in RAM, consumed asynchronously by an ISR/feeder that feeds the DSP56xxx.
Hardware (DSP) behind an async boundary, just as ATA was behind the command queue.
→ reinforces the RTOS model: producer (sequencer) / consumer (audio ISR) decoupled by RAM.

## RTOS identified: Elektron's PROPRIETARY microkernel ✓ — log `out/ghidra_kern.log`

Not MQX/ThreadX/VxWorks/Nucleus. Negative evidence: **zero** copyright/version/API strings
of a commercial RTOS. Only banner: `ElektronOctatrack DPS-1 0002 / FROM WWW.ELEKTRON.SE`
(DPS-1 = internal Elektron platform, shared across their ColdFire machines).

Positive evidence — preemptive priority-based microkernel, decompiled primitives:
- **`FUN_40000818` (wait_event)**: if `*ev < 1`, links the current TCB into a wait list, state
  `TCB[0x13]=0` (blocked), and executes **`TRAP #0`** = context switch via m68k software trap.
- **`FUN_40000c3c` (post/queue)**: writes ring buffer; if a task is waiting, marks it `TCB[0x13]=1`
  (ready), inserts it into the **priority ready queue** (doubly-linked circular lists), and forces
  reschedule with `0xFC04_C010 |= 0x800` (ColdFire interrupt controller).
- **TCB**: state@0x13, priority@2, list pointers@0/1. Current task = `_DAT_800068fc`.
  Top-priority pointer = `_DAT_800068d8`.

**Unifies everything above**: the ATA stack's "async queues" and the audio engine's "voice mailboxes"
ARE this kernel's message/event queues. A single microkernel, used throughout the firmware.

## DSP interface and audio pipeline ✓ — logs `out/ghidra_{dsp,frame}.log`, r2 disasm

**Physical DSP interface: MMIO at `0x20000000`** (revealed by r2; Ghidra's ColdFire module
fails on this hot-path code). Handshake registers:
- `0x2000_0004` command/status (writes `0x8C`, polls busy bit7 until ack)
- `0x2000_0008` status ("DSP ready": boot polled `while ((*0x20000008 & 6)==0)`)
- `0x2000_001c` frame index reported by the HW → selector of the double buffer `0x800000e0`

**Full pipeline (control path):**
```
sequencer trig
 → FUN_40005178 writes voice mailbox (0x46c7e9fa / 0x800018be) in RAM
   → FUN_4000c8a4 (frame builder, control-rate) consumes mailboxes, updates 8 voices,
      assembles a parameter FRAME in a double buffer in shared RAM 0x80000000 (ping-pong 0x800000e0)
     → handshake via 0x20000000 (reads frame idx 0x1c, writes cmd 0x8C to 0x04, polls busy)
       → DSP56xxx reads the frame from 0x80000000 and synthesizes (samples, time-stretch, filters, FX)
```

**ColdFire↔DSP split**: ColdFire = control (RTOS, sequencer, assembles voice parameters).
DSP56xxx = signal (real-time audio). Synchronized by **double buffer + register handshake**.

### Consolidated memory map
| Window | Use |
|---|---|
| `0x40000000` / `0x46000000` | SDRAM: code (img @0x40000400) + app data/BSS |
| `0x20000000` | **Audio DSP coprocessor** (cmd 0x04, status 0x08, frame idx 0x1c) |
| `0x80000000` | Fast/shared RAM: voice state, mailboxes, **double-buffered DSP frames** |
| `0x90000000` | ATA task-file (CompactFlash) via FlexBus |
| `0x100b0000` | Small globals (current track/pattern) |
| `0xFC000000` | ColdFire on-chip peripherals (MBAR: ATA host, interrupt ctrl 0xFC04C010, etc.) |

## Sequencer clock ✓ — logs `out/ghidra_clock.log`, r2 disasm

**The sequencer has NO timer of its own: it is clocked by the DSP's audio FRAME interrupt**
(sample-accurate sequencing). Phase accumulator:
- Tempo → `_DAT_80001814`; per-frame increment `_DAT_80001820 = 2³¹ / tempo`
  (seen in `FUN_4000c8a4`: `_DAT_80001820 = -0x80000000 / _DAT_80001814`).
- `FUN_4009c550` sets the tempo period from the pattern data (`_DAT_46c82456 + pat*0x8ed8`).
- The **frame ISR** (`0x4000aad0`, fires on reading the frame index at `0x2000001c`) accumulates the phase;
  on overflow it advances the step and **posts to a kernel queue** (`FUN_40000c3c`) to wake the
  sequencer task → trigs → `FUN_400977cc` → voice command. Refs to tempo/phase at `0x4000axxx`.

## DSP program: located and extracted ✓ — `out/dsp_region.bin`

**DSP56300 (24-bit), at the TAIL of the MAIN OS image** (`~0x400e2000 .. 0x4010fdf0`, ~188 KB
= ~62,600 24-bit words). Confirmed: `f803 00bb …` = DSP56k opcodes, loaded 3 bytes at a time.
- Loaders: `FUN_40001d4c` → **P** memory (24-bit stream, starts with `0x20000000=0x81`);
  `FUN_40001b18` → **X/Y** data. Uploads in sections to DSP `0x31000`, `0x32000`, …
- Blobs from init: `0x400e21e0`(len 0x96→0x31000), `0x400e2276`(0xae→0x32000), `0x400e2324`, `0x400f59ef`.
- **For the FX/timestretch**: disassemble with target **DSP56300** (Ghidra/r2 don't ship it; a56/dsp56k
  or community SLEIGH modules). Separate project.

## Go/No-Go — patch "preserve volume when switching Part" → FEASIBLE (corrected)

- The behavior lives in the **audio hot path** (`FUN_4000c8a4` + core `0x40009xxx`/`0x4000cxxx`):
  the frame builder reads the **active Part** (`0x80000002`) and **active pattern** (`0x80000003`) every frame
  and from there takes the LEVEL → that's why it jumps when switching Part (continuous read, not "apply on change").
- **CORRECTION of a previous erroneous verdict**: it is NOT blocked by tooling. Ghidra's ColdFire SLEIGH
  **already decodes** this code (defines MAC/MSAC/MACSR/ACC0-3; `71f9`/`73c3` = `mvz.w`/`mvs.w`).
  Verified: the frame builder disassembles **121 clean instr., 0 gaps** in Ghidra's listing.
  The previous error was using **radare2** (blind to ColdFire extensions) for the check and confusing the
  **decompiler** failure (no C) with a **disassembler** failure (which does work).
- **Rule**: for the audio core → use **Ghidra's listing** (not radare2, not the decompiler).
- **EMAC sub-project: UNNECESSARY** (Ghidra already covers the ISA). Off the roadmap.
- Remaining work for wish 1 (hard but defined, NOT blocked): read the frame builder's ASM
  to find the exact LEVEL read, map free RAM in the voice struct (`0x800049d8`/0xA8),
  design the per-voice latch, patch at the byte level, test on hardware.

### A vs B confirmed → **B**, and intermediate "lazy apply on first trig" design
- `FUN_40005030` (trig helper) reads **pattern** data (`_DAT_46c82456 + pattern*0x18b2`, which sample)
  and writes sample-slot + voice command + DSP double-buffer, but **does NOT refresh the Part params**
  (doesn't touch `0x80000a50` nor the Part data `*0x9b340`). → The trig fires the sample but does NOT re-apply
  the Part. Only `FUN_40009094` (by event) does. **Scenario B confirmed.**
- Intermediate design (apply destination Part on the first trig per track): **moderate**. Components:
  "pending" flag per track (or better: **Part-applied per track**, 8 bytes), skip reload of sounding
  tracks in `FUN_40009094`, per-track apply, hook in the trig (`FUN_40005030`/`FUN_400977cc`).
- **Layered params model**: base Part → (FUN_40009094 on change) base buffer → per-frame computation
  (LFO/scene/p-lock, in `FUN_4000c11a` 5066 B, does NOT decompile) → `0x80000a50` → DSP. The voice-in-transition
  uses the buffer, which derives from the ORIGIN Part if we skip the reload → no jump. ✓

### AUDIO PATCH SPEC (intermediate design) — per-track infrastructure ALREADY EXISTS ✓
- **`per_track_part[8]` @ `0x8000182a`, `per_track_pattern[8]` @ `0x80001832`** already exist. Both
  param appliers (frame builder + `FUN_40002df4`) are gated by `per_track == active`.
- The jump originates in the frame builder: when `GLOBAL_applied (0x80001828) == active`, at `0x4000ca32`
  it does `per_track_part[track]=active` (`move.b D1,(A5)`) + `0x4000ca34` pattern + applies params.
- **Patch**: at `0x4000ca30` (update+apply block), gate: if `voice_active[track] && !trig_pending`
  → jump to `0x4000ca76` (keeps old per_track → no jump). Otherwise → apply + clear pending.
  Both appliers respect it for free (they key on per_track). Trig hook (`FUN_40005030`):
  `trig_pending[track]=1`. Active voice = `0x800049d8 + track*0xA8` byte0.
- **Resources**: code cave `0x400d64da` (5986 B of 0x00); free RAM `0x80006a00` (340 slots) for
  `trig_pending`. Minimal new state (the Part array already exists). Difficulty: medium, bounded.
- Improvement over the previous idea of patching `0x4000c8c6`: reuses existing infra, 1 gate + 1 hook.
- Knob→Part editor: cornered to the cluster `0x40041–0x40043` (param pages), writes the Part data
  without calling `FUN_40009094`; still need to pin the exact function (1 pass). Enables the GUI-in-transition
  (route editing through `per_track_part[track]`, which already exists).

### DYNAMIC ANALYSIS OPERATIONAL — ColdFire emulator (Unicorn) ✓✓
- `tools/emu_validate.py`: validates that **Unicorn (m68k) runs the firmware's ColdFire** —
  `FUN_40000e50(5)` → `0x80004d20` exact. Viable approach.
- `tools/emu_trace.py`: memory-write tracer. Ran `FUN_40009094(0,0)` and **dynamically confirmed**
  that it writes `0x80001828/29` (global), `0x8000182a/32` (per-track), `0x80000a50` (voice).
- `tools/emu_find_editor.py`: sets up globals (`_DAT_46c82456`=project, track/pattern/mode) and traces
  candidates watching for writes to the Part data. **Found `FUN_4005a918`**: writes 6 params/page
  to the Part data (`0x8edaa`…) + dirty flag (`0x9b332=1`); operates on `DAT_100b14cc/cf/46c7d8d8`.
  (Probably page recall/scene/commit, not the single-encoder editor — but the dynamic
  methodology works to pin any function.)
- **Proven method**: set globals + trace + watch writes to the `_DAT_46c82456`-region = hunt editors.
  The single-encoder editor is a few more traces away. CPU exception sometimes (~0x40000c42, unsupported
  instr) but the useful trace happens before it.

### "LAZY PART" BEHAVIOR PATCH — IMPLEMENTED AND VALIDATED ✓✓✓ → `out/OCTATRACK_OS1.40C_LAZYPART.syx`
- **Behavior**: on pattern change, SOUNDING tracks keep their params (no volume
  jump); on their first trig they apply the new Part (via the frame builder's D6 gate).
- **Implementation** (save/restore, `tools/patch.s`, assembled with `m68k-elf-as -mcpu=5407`):
  - Cave at `0x400d64e0`: `save_stub` (0x400d64e0) + `restore_stub` (0x400d6538), 184 B.
  - ENTRY detour `0x40009094` → `save_stub`: bulk-saves voice buffers (`0x80000a50`, 0x200 B) +
    per_track (`0x8000182a`, 16 B) + "sounding" flags (`0x80006c20`); runs the displaced lea+movem;
    `jmp 0x4000909c`.
  - EXIT detour (tail-call) `0x40009664` → `restore_stub`: restores voice buffer + per_track of the
    tracks that were sounding; `jmp 0x40000c3c` (original tail-call to post_work). RAM save: `0x80006a00`.
  - Key: `FUN_40009094` does NOT end in rts but in tail-call `jmp 0x40000c3c` @0x40009664 (the rts
    @0x40009844 belongs to ANOTHER function — bug fixed).
- **Validated in the Unicorn emulator** (`tools/emu_clean.py`): sounding track preserved (0xEE intact),
  silent tracks updated. Pre-stub of post_work + 1 EMAC func (instructions Unicorn doesn't
  support; on real HW they run normally).
- **Repackaging**: `-c 3` → `.syx` with `checksums: ok`. Flashable. Final test = flash over MIDI
  (recoverable).

### GUI-IN-TRANSITION PATCH — IMPLEMENTED AND VALIDATED ✓✓✓ → `out/OCTATRACK_OS1.40C_LAZYPART_GUI.syx`
- **What it does**: turning a knob while a track is in transition (per_track_part≠active) edits the ORIGIN
  Part and live-updates (sculpts the sound-in-transition in real time). Combines with the audio.
- **Editor** = `FUN_40052e98(enc,delta)`. Addressing (traced in the emulator): writes the param to
  `_DAT_46c82456 + DAT_100b14cf*0x18b2 + (iVar10*8+track)*0x20 + enc + 0x8f3e2`; live-update gated by
  `0x80000002==per_track_part[track] && 0x80000003==per_track_pattern[track]`. iVar10 = part of
  DAT_100b14cf (from `+0x8ed91`).
- **Discovery**: redirecting ONLY `DAT_100b14cf`→per_track_pattern makes it read/write the source
  (iVar10 still follows); + `0x80000002/03`=source passes the gate → live-update. (emu: TRANS without patch
  writes dest without sounding; with override writes source `0x90df4` + live `0x80000f94/95`.)
- **Implementation** (`tools/patch_gui.s` — SUPERSEDED by `patch_gui2.s`, it was not reentrant;
  see "Hardware crash and fix" below. m68k-elf-as+ld @0x400d6600): wrapper with **return-hook**.
  Entry `0x40052e98`→setup: if in transition, saves+sets globals to source, replaces the return on the stack
  with cleanup. cleanup restores globals + jmp to the real return (covers rts + the editor's tail-call). Save
  area `0x80006c30`, cave `0x400d6600` (no overlap with audio: cave `0x400d64e0`, RAM `0x80006a00`).
- **Validated**: transition→source+live; normal→intact; globals restored; robustness 4 tracks × 4
  encoders (incl. LEVEL=6) all ✓. Combined repackage (audio+GUI) checksums ok.
- **Caveat**: sets `0x80000002/03` temporarily (µs) for the gate; the frame builder skips sounding
  non-triggered tracks (D6 gate) → track in transition unaffected; µs risk window is negligible. Documented.

### FLASHABLE FIRMWARE CHAIN — PROVEN END-TO-END ✓✓✓
- POC patch: `COLLECT SAMPLES` → `COLLECT SAMPLEZ` in the raw MAIN OS.
- Repackaging: `elektron-firmware-tool -i orig.syx -c 3 mainos_patched.bin -o patched.syx`
  (recompresses aPLib + rebuilds ELEK + recomputes checksums).
- `-i patched.syx` → **checksums: ok**. The Octatrack would accept it.
- Byte-perfect round-trip: decompressed differs from the original by **1 byte** (the one we changed).
- → `out/OCTATRACK_OS1.40C_patched.syx` is valid, flashable modified firmware. **Full chain
  decode→patch→recompress→checksum→.syx demonstrated.**

### BEHAVIOR PATCH SITE — CONFIRMED in clean code ✓
- Frame builder D6 gate (`0x4000c9e2 beq 0x4000ca7c`): **the frame builder only applies params
  when there's a trig (D6≠0)**. → The volume jump comes from `FUN_40009094` (per-event applier).
- **Clean patch**: in `FUN_40009094`, skip the apply for SOUNDING tracks (`0x800049d8+track*0xA8` byte0).
  A sounding track keeps its params; on its first trig, the frame builder (D6≠0) applies the new Part.
  No `trig_pending`, no trig hook — the existing D6 gate is enough. Decompilable code.
- Pending implementation: nail the insertion point in the `FUN_40009094` loop (nested loops,
  SP-relative locals), assemble the cave (m68k-elf-as installed), detour, and **validate in the emulator**.

### ENCODER EDITOR PINNED (dynamic + static) ✓✓ — `FUN_40052e98`
- Hunted with `tools/emu_batch.py` (classified functions by number of params written → the 1-param ones).
- **`FUN_40052e98(param_1=encoder_idx 0-6, param_2=delta)`**: the encoder parameter editor.
  - `def = FUN_40031f28()` (param min/max). encoder 6 = LEVEL (special case 0/0x7f).
  - else: reads the current Part value (`…+0x8f3e2`), adds `param_2` (delta), clamps, writes back.
  - Writes the Part data indexed by **`DAT_100b14cf` (DISPLAYED pattern)** + dirty flag `0x9b332=1`.
  - **ALREADY integrates per-track**: only updates the live sound buffer if
    `DAT_80000003==per_track_pattern[track] && DAT_80000002==per_track_part[track]`.
    → If the track is in transition, it writes the Part but does NOT touch the sound — out of the box.
- **GUI-in-transition**: redirect the editor's write destination to `per_track_part[track]` during
  transition (same class of patch as the audio); the live-update check already uses per_track. Sizing closed.

### TWO "current" POINTERS — key to GUI-in-transition ✓
- **`DAT_80000003`/`0x80000002`** = **sounding** pattern/Part → used by the AUDIO engine.
- **`DAT_100b14cf`** = **displayed/edited** pattern → used by GUI and EDITOR (`FUN_40031da4` reads
  `_DAT_46c82456 + DAT_100b14cf*0x18b2 + …`). They are distinct: that's why after the change you see the destination
  but hear the origin.
- Editor/param definitions: `FUN_4004f5f8` (audio branch) → `FUN_40031ee0` → `FUN_40031da4`
  (descriptor selector by machine type; min@0x6a, max@0x9a). It's the definition machinery,
  not the value writer.
- **GUI-in-transition = redirect `DAT_100b14cf` (GUI pointer, SEPARATE from the audio one) toward the
  per-track origin Part during transition.** Same class as the audio patch, they don't interfere.
- Honest limit: the exact audio param value writer was NOT pinned by static analysis (scattered
  through UI). Efficient path to close it: **dynamic analysis** (ColdFire emulator, QEMU m68k style)
  observing what runs when a knob is turned. The emulator we have (`dsp56300`) is for the DSP, no use here.

### PATCH POINT (earlier, superseded) — the Part index is per-track in the hot path
- The knob→Part editor **writes the Part data** (persistent); does NOT call apply. The sound is
  updated because the per-frame compute **re-reads the active Part every frame, per track**.
- The callers of `FUN_40009094` are structural (paste part, assign part), NOT the knob editor.
  → The volume jump originates in the per-frame re-read, NOT in `FUN_40009094` (corrects the previous GO).
- **Surgical point**: `0x4000c8c6` `move.b (0x80000002).l,D0` (bytes `1039 80000002`), INSIDE the
  per-track loop (0x4000c8a2→0x4000ca90, counter D4). The value flows to `A2 → D1*0x9b340` (indexes the
  Part) at `0x4000ca44`. It's code that Ghidra reads cleanly.
- **Patch**: reserve `part_per_track[8]` in RAM; replace the 6 bytes with `jsr code_cave` (6 bytes);
  the cave does `D0=part_per_track[D4]; rts`. Maintain the array: pattern change → old Part for
  sounding tracks; first trig → active Part. Controls ALL params (not just level). **Surgical.**
- Caveat: verify whether there are OTHER re-reads of the active Part for audio (0x80000002 is read 1× in this
  function, but the function is large; confirm this loop is the main param path).

### GUI-in-transition (edit the origin Part's params while the track transitions) — FEASIBLE, the most complex
- The origin params ARE live in the engine (working buffer) during the transition.
- Elegant implementation: use **Part-applied per track** (the same as the intermediate design) also
  for the GUI → edit/display `applied_part[selected_track]` instead of the global active Part.
  This way audio and GUI share a mechanism.
- Extra cost over the intermediate design: route the **parameter editing path** and the **display** path
  through `applied_part[track]`. RE still needed: locate the knob→param editor (the write to the Part data
  is probably decodable code; the per-frame compute `FUN_4000c11a` is the one that doesn't decompile,
  but for editing you don't need to touch it). It's the most ambitious front of the ones discussed.

### Go/No-Go redone with Ghidra → **GO** (cleaner than expected)
- **`FUN_40009094` = "apply Part parameters to the voices"** (decompiles to clean C). Reads Part params
  (`part*0x9b340 + pattern*0x18b2 + track*0x1e + …`) and writes them into the voice working buffer
  `0x80000a50 + track*0x40` (16-bit per param) that the frame builder copies to the DSP double buffer.
- **It's BY EVENT, not per frame**: the frame builder compares active Part (`0x80000002`) vs. applied
  (`DAT_80001828/29`) and only triggers the reload on change. `FUN_40009094` has 9 callers, all
  event handlers (pattern/part change, load). → **That's where the volume jumps.**
- **Clean hook, NO new RAM**: the buffer `0x80000a50` already IS the "current level". To preserve the
  origin level it's enough to **NOT overwrite the LEVEL field for tracks that are sounding** inside
  `FUN_40009094`; the buffer keeps the old value (free latch). On the next trig, the normal path
  applies the new Part's level (desirable).
- "Sounding" = active voice flag in `0x800049d8 + track*0xA8` byte 0 (already read by `FUN_40000ee0`).
- Still needed for the concrete patch: (1) fix the exact offset of the LEVEL field within the params block,
  (2) insert the "skip if sounding" conditional (a code-cave possible for space), (3) test on hardware.
- This also covers the spirit of wish 2 (state preserved until manual re-trigger).

### DSP56300 toolchain ready ✓
- Disassembler built: `vendor/dsp56300` (Access Virus emulator) → `build/.../dsp56kDisassemble`.
  Usage: `dsp56kDisassemble -in blob.bin -pc <addr_hex>` (big-endian by default, 3 bytes/word).
- Validated: boot blobs disassembled (`out/dsp_disasm/mod_31000.asm`, `mod_32000.asm`) → code
  coherent with peripheral registers (`M_TCR0/1`, `M_DCR2`), parallel moves. They are init routines.
- Still needed: enumerate each module's load addresses (from the ColdFire call-sites) to disassemble
  the entirety of `out/dsp_region.bin` with the correct `-pc` per module → effects + timestretch.

### Coverage statistics (measured in Ghidra)
- ColdFire image: **2165 functions** total; **27 named/analyzed** by us (~1.2%).
  187,114 instructions, 593,744 B of code (of 1,112,560 B; the rest is data + DSP program).
- DSP program: ~62,600 24-bit words, 0 functions analyzed (toolchain now ready).

### Pending (Phase 1+)
- Disassemble `out/dsp_region.bin` by modules (with correct `-pc`) → effects + timestretch.
- Sequencer depth: p-locks, conditional locks, scenes/crossfader, LFO designer.
- MIDI subsystem (parser/sync) and UI/display framework.
- Remaining ATA handlers; large functions the ColdFire decompiler doesn't lift.
- Extract the vector table (0x400 preamble, NOT in this section) for the ISR map.

## Phase 2 — Hardware (only if needed)  [PENDING]

- UART on the PCB → boot logs (cheap, low-invasive).
- ColdFire uses **BDM** (Background Debug Mode), not ARM JTAG → live flash dump.
- Desolder flash + external programmer = last resort.

## Open questions

- Exact RAM and DAC/ADC codec (undocumented; require teardown/PCB photos).
- Do MKI (DPS-1) and MKII share the OS container format?
- Is there signature/encryption beyond checksums? (resolved by Phase 0)
- Is there any flash dump or community Ghidra project beyond OctaLib/ot-tools-io/elektron-firmware-tool?

## Sources

- Elektron support: https://www.elektron.se/support-downloads/octatrack-mkii
- elektron-firmware-tool: https://github.com/mischa85/elektron-firmware-tool
- OctaLib (Research.md): https://github.com/snugsound/OctaLib
- Elektronauts CPU thread: https://www.elektronauts.com/t/octatrack-cpu-chip-model/93304
- Modding firmware thread: https://www.elektronauts.com/t/modifying-elektron-firmware/36228
- EFF RE FAQ (legal): https://www.eff.org/issues/coders/reverse-engineering-faq

---

## Boot branding — change the displayed version (splash + SYSTEM STATUS)

**Goal**: the first screen on power-on shows `1.40C`; change it to custom text.

**Finding (RE)**: the displayed version is NOT in the MAIN OS code. It lives as text in the
**ELEK container header**, which ends up in flash starting at `0x4000` after flashing
(`FUN_4007fb84` = flash writer writes the container to flash 0x4000). Header layout:
- `0x00` `"ELEK"` (magic)
- `0x04` `"0178"` (internal version code; used by the downgrade check `< "0178"` — DO NOT touch)
- `0x08` DISPLAY version field: `"     1.40C\0"` (5 spaces + version, right-aligned,
  fixed width **10 chars**, offsets 0x08–0x11). The byte `0x12` = high byte of the aPLib section
  length (always `0x00` for an OS < 16 MB) → serves as the **NUL terminator** of the string.
- `0x12` onward: compressed aPLib section (offset **hardcoded** in the device's decompressor).

The MAIN OS reads the display via `FUN_40069848` (SYSTEM STATUS menu): `DAT_400a95c0` = first entry of
the **flash sector table** = `0x4000`; reads `0x4000 + 8 = 0x4008`, skips spaces, copies ≤10
chars. The **bootloader** (outside our container) draws the splash reading the same `0x4008` — that's
why the splash reflects the installed OS version. Editing `0x08–0x11` changes **both**.

**Hard limit**: the field is 10 chars (0x08–0x11). It can't be enlarged: the aPLib section starts
right after (0x12) at an offset the device's decompressor assumes fixed → moving it = brick. That's
why `"MAXOLYDIAN 1.40C"` (16) doesn't fit; the cap is 10 → `"MAXOLYDIAN"` was used.

**Implementation**: extended `set_version()` of `vendor/elektron-firmware-tool/main.c` so that in
ELEK the editable field starts at `0x08` (previously `ELEK_VERSION_OFF=0x0D`, only 5 chars) → now it writes
the full 10 chars of the display area. Build:
```
elektron-firmware-tool -i downloads/extracted/OCTATRACK_OS1.40C.syx \
    -c 3 out/mainos_combined.bin -V "MAXOLYDIAN" -o out/OCTATRACK_OS1.40C_LAZYPART_GUI_MAXO.syx
```
**Verified**: header `0x08–0x11` = `6d 61 78 6f 6c 79 64 69 61 6e` = "MAXOLYDIAN"; `0178` intact;
`0x12` = `00` (NUL); checksums ok; round-trip of the MAIN OS section byte-identical to `mainos_combined.bin`
(audio+GUI patches intact). 100% cosmetic change; the version code `0178` is not touched.

### Boot splash font = UPPERCASE only (verified on hardware)

When flashing with the field in lowercase (`maxolydian`) the boot splash showed **garbage glyphs**
below the Elektron logo (user's photo) — but the text WAS being drawn (confirms the bootloader
reads the version field from flash `0x4008` and paints it on the splash). The splash font (which lives in the
bootloader, outside our container) **has no glyphs for lowercase**: it's an embedded font of
~6 bits (range `0x20`–`0x5F`: space, symbols, digits `0-9`, `A-Z`), that's why `1.40C` (digits + `.` +
uppercase `C`) always looked fine. The lowercase bytes (`0x61`+) fall outside → garbage.

**Fix**: use UPPERCASE. Rebuild with `-V "MAXOLYDIAN"`. Verified header:
`0x08..0x11` = `4d 41 58 4f 4c 59 44 49 41 4e` = "MAXOLYDIAN"; `0178` intact; `0x12`=`00`; checksums ok;
round-trip MAIN OS byte-identical. **Rule for future splash brandings: only `A-Z 0-9 . space`
(and ASCII symbols 0x20-0x40), NO lowercase, max 10 chars.**

---

## SCENES subsystem (crossfader) — RE for "sticky scenes on Part change"

**User goal**: when switching to a pattern with a different Part, keep the currently selected
A/B scenes instead of loading those of the destination Part.

**Data structure (verified by decompilation):**
- Per-pattern scene selection: byte at `_DAT_46c82456 + pattern*0x18b2 + 0x8ed90` (scene A) and
  `+ 0x8ed91` (scene B). `_DAT_46c82456` = project database base; pattern stride = `0x18b2`.
- Each scene's data (p-locked params): `base + pattern*0x18b2 + scene*0x100 + 0x8f3e2`.
- RAM mirror of the selection: `0x100a4edf + pattern*0x18b2` (written by the writer alongside the project).
- Slot-in-edit flag (A vs B): `_DAT_460d169c` (1 = A).

**Key readers/writers:**
- `FUN_4003f1b4` = **crossfader/scene morph** (live, control-rate): uses the **ACTIVE** pattern
  `DAT_80000003` → reads the A/B selection (`0x8ed90/91`) → reads both scene blocks (`scene*0x100+0x8f3e2`)
  and interpolates them by the crossfader position. **This is where the scenes "change"**: on switching
  pattern, `DAT_80000003` changes and the new pattern's selection is read.
- `FUN_40052944` = scene B selection writer (manual assignment): writes `0x8ed91` in project +
  mirror `0x100a4edf` + display (`FUN_40033e3c(8,0x38,...)`). There's an analog for scene A (0x8ed90/0x37).
- Scene edit menu (COPY/PASTE/CLEAR/UNDO): `FUN_40062da0/e84/f60`, read the selection via `DAT_100b14cf`
  (DISPLAYED pattern) — GUI path.
- The **pattern-change commit** (write of `DAT_80000003`) lives in the giant event loop
  `FUN_40061a94` (store register-indirect, not a direct ref → hard to hook there).

**Part/pattern model**: the selection is stored per-pattern (0x18b2), but in practice reflects the
Part (activating a pattern loads its Part's data into the active block; patterns of the same Part
share the selection). That's why the "jump" is perceived when changing Part.

**Patch feasibility: YES.** Recommended approach (copy-on-change / "sticky"): on Part change,
copy the outgoing A/B selection to the incoming pattern's block (`0x8ed90/91` + mirror `0x100a4edf`),
so that the crossfader reads the previous scenes. Natural hook: the same Part-change path the
lazy-part patch already uses (`FUN_40009094`), carrying a shadow of the last applied pattern to know
origin→destination. **Tradeoff**: it modifies the destination pattern/Part's saved scene selection (working
copy); if the project is saved, it persists. Semantic decision pending with the user.

### Sticky scenes v1 — SUPERSEDED (`tools/patch_scene.s`, buggy; see "Sticky scenes v2" below)

`scene_stub` inserted in the detour chain of `FUN_40009094` (part-apply):
`0x40009094 -> scene_stub(0x400d6700) -> save_stub(0x400d64e0) -> ... -> jmp 0x4000909c`.
Copies the A/B selection of the outgoing pattern (carried in `LAST_PAT`@`0x80006c60`, with `INIT_FLAG`@
`0x80006c61`) to the incoming pattern's block (arg2), at `0x8ed90/91`, before the crossfader reads.
Details: base=`*(0x46c82456)`; `dst = base + arg2*0x18b2 + 0x8ed90/91`. Uses muls.l and movem in
ColdFire style (`lea -0x18,sp; movem.l ...,(sp)` — ColdFire does NOT support `movem -(An)`).
- Validated in emulator (`tools/emu_scene.py`): correct copy, respects init/same-pattern, no
  wild-writes, regs restored, SP balanced, chains to save_stub. The audio+GUI patches intact
  (scene_stub restores all state before the jmp; save_stub byte-unaltered).
- Diff vs mainos_combined: only 2 regions (detour `0x40009098` 2B + stub `0x400d6700` 134B).
- Final firmware: `out/OCTATRACK_OS1.40C_FULL_MAXO.syx` (audio+GUI+scene+MAXOLYDIAN), checksums ok,
  round-trip MAIN OS byte-identical to `out/mainos_scene.bin`.
- **Uncertainty (soft, no brick risk)**: efficacy depends on `FUN_40009094` running on the
  Part change (confirmed: the lazy-part patch that uses it ALREADY works on hw) and on the per-pattern
  selection not being reloaded after the copy (evidence: writer/readers are per-pattern → no reload).
  Worst case if the assumption fails: the scenes jump the same (harms nothing; the stub only writes 2 bytes
  of valid index to an in-range address).

### Correction: there is NO separate RAM mirror — logs `out/ghidra_mirror{,2}.log`, `out/ghidra_partapply.log`

An earlier note claimed the scene LEDs might read a mirror at `0x100a4ede/edf` that the patch
leaves stale. **That was wrong.** `0x100a4ede/edf` and `*(0x46c82456) + 0x8ed90/91` are the
**same two bytes**: the project working copy has a compile-time-constant base `0x1001614e`
(84 code sites use it directly), and part of the firmware reaches the same fields through the
pointer at `0x46c82456` instead. The offsets line up exactly:

| via pointer | absolute | field |
|---|---|---|
| `+0x8ed80` | `0x100a4ece` | (neighbouring field) |
| `+0x8ed88` | `0x100a4ed6` | (neighbouring field) |
| `+0x8ed90/91` | `0x100a4ede/edf` | **scene A / B selection** |
| `+0x8eda2` | `0x100a4ef0` | (neighbouring field) |

So writing "the mirror" would be a no-op — `scene_stub` already writes what every reader reads.
All four functions touching `0x100a4ede/edf` (`FUN_4000e79c`, `FUN_4004a100`, `FUN_40052944`,
`FUN_400a0734`) only **store** to it; none loads from it.

### Two-level scene storage (this is the real model)

- **Live working copy** — `0x1001614e + pattern*0x18b2 + 0x8ed90/91`. What the crossfader
  `FUN_4003f1b4` reads. **This is what `scene_stub` writes.**
- **Per-Part saved copy** — `0x40170f70 + part*0x9b340 + pattern*0x18b2` (+1 for B).
  Part stride `0x9b340`. `FUN_4004a100`/`FUN_400a0734` write both copies, but the live one only
  when the entry's Part/pattern are the active ones (`DAT_80000002`/`DAT_80000003`).

**`FUN_40009094` (our detour host) reads the per-Part copy, not the live one**
(`cVar2 = *(char *)(iVar13 + 0x40170f70)`, then indexes scene data by it). It does **not** write
`0x8ed90/91`, so it does not overwrite `scene_stub` — but anything it drives uses the destination
Part's selection regardless of the patch. Signature confirmed: `FUN_40009094(part, pattern)`,
matching the stub's `arg2 = pattern` read at `0x20(%sp)`.

**Open**: which copy the scene LEDs/display read is still unidentified. If they read the per-Part
copy, full stickiness needs writing `0x40170f70 + part*0x9b340 + pattern*0x18b2` too — more
invasive, since that block is what gets persisted on project save.

**Resolved** (see below): every consumer reads the live copy. Nothing extra is needed.

## Sticky scenes v2 — `tools/patch_scene2.s` (v1 was wrong)

**v1 was broken on hardware**: assigning a scene by hand after a transition got clobbered.

Root cause: v1 hooked `FUN_40009094` and treated every invocation as a pattern change,
copying the outgoing pattern's selection over the incoming one. That premise is false.
`FUN_40009094` is `apply_part(part, pattern)`, called from **10 sites**, and:

- 7 push the active pattern `(0x80000003)` as the argument;
- 3 push an **arbitrary pattern from a register** (`FUN_4002b470` D3, `FUN_4002b654` D7,
  `FUN_4004a8a4` D2), each preceded by `0x9b332 = 1` and `0x100f8598 = 1` — the
  "a parameter was edited, re-apply the Part" idiom;
- `FUN_40052944` (manual scene assign) sets those same two flags, so **assigning a scene
  reaches apply_part too**, and v1 fired as a side effect of the user's own action.

v2 ignores the arguments entirely and polls the real active pattern:

```
enforce():
    p = *(0x80000003)
    if !VALID:          STICKY = live[p]              ; first run
    elif p != LAST_P:   live[p] = STICKY ; HOLD = 4   ; pattern changed -> impose
    elif HOLD != 0:     live[p] = STICKY ; HOLD--     ; anti-loader window
    else:               STICKY = live[p]              ; user assigned -> adopt
    LAST_P = p ; VALID = 0xA5
```

A pattern change and a manual assignment are distinguishable because the index changes in
one and not the other. `HOLD` is a heuristic guarding against the Part loaders
(`FUN_4004a100`/`FUN_400a0734`) writing the destination's saved selection right after the
change; it is the one tunable parameter. RAM `0x80006c60`..`0x64`. `enforce()` is
idempotent and hangs off two hosts: `FUN_40009094` and `FUN_4003f1b4` (crossfader entry,
prologue `lea -0x3c(SP),SP ; movem.l d2-d7/a2-a6,(SP)` displaced into the stub).
Validated 9/9 in `tools/emu_scene2.py`. **Confirmed working on hardware.**

## Display of the scene selection — no GUI patch needed

All three consumers read the SAME live bytes, indexed by the ACTIVE pattern:

| consumer | what it drives |
|---|---|
| `FUN_4003f1b4` | the crossfader morph (audio) |
| `FUN_40061a94` @`0x40062c32` | publishes UI elements `0x37`/`0x38` via `FUN_40033e3c` |
| `FUN_4004d640` | the scene numbers on the LCD (`+1`, so 0-15 shows as 1-16) |

So correcting the data corrects audio and display together. `FUN_4004d5b8` (the scene trig
comparator) is the exception: it uses `DAT_100b14cf`, the DISPLAYED pattern.

`FUN_40002df4(part, pattern, scene, slot)` is NOT an LED setter — it stages 0x20 bytes of
scene parameter data per track from `0x401715c2 + part*0x9b340 + ...` into the live scene
buffer at `0x80000ed4 + track*0x40`, gated on the track's part/pattern matching the active
ones. **That gate is what makes a track in transition keep the source Part's scene params
— the real definition of "dirty".**

## LED subsystem — logs `out/ghidra_led{,map,drv,buf,enc}.log`

- State buffer `0x460ba98c`, **2 bits per LED** — `FUN_400132c4(id, state)` masks with
  `3 << (id & 7)`, and ids advance by 2. Bi-colour: one bit per die, so
  `00` off / `01` red / `10` green / `11` amber.
- Brightness is separate and 4-bit: `FUN_400135b0(id, level)`, one call per die.
- `FUN_400131a0(id)` / `FUN_400131c8(id)` set/clear a single bit (the widely-used pair).
- **Track LEDs**: `FUN_40083eb0` loops 8 tracks over an id table at `0x400a9670`, computes
  a colour state 0-3, and passes a **hardcoded `0xF` brightness** — so brightness is a free
  dimension there. Loop tail registers: `D5` = track index, `D2` = id, `D3` = id+1,
  `A3` = `FUN_400135b0`. It does NOT pop per call; it cleans `0x20` once at `0x40083fc6`,
  so a stub must push exactly the same bytes and clean nothing.
- **Trig LEDs**: `FUN_40034a44` loops 16 trigs building two local arrays, then emits them:
  colour at `SP+0xA0`, brightness at `SP+0x20`, 4 B per entry, 2 entries per trig
  (confirmed by the prologue `lea (-0x120,SP),SP ; lea (0xa0,SP),A6 ; lea (0x20,SP),A2`).
  Stock combinations: `(0,0)` empty, `(0,1)` has content, `(1,0)` selected scene.
  **`(1,1)` is never used** — that is the free slot the dirty indicator takes.

Dirty indicators: `tools/patch_led.s` (track LED dimmed to `0x5`, detour `0x40083fb4`) and
`tools/patch_trig.s` (selected scene trig amber, detour `0x40034b5e` — conveniently a
6-byte `lea`, exactly one instruction). Both use `per_track_part[track] != DAT_80000002`.
Validated 4/4 and 5/5 in `tools/emu_led.py` / `tools/emu_trig.py`.

## Hardware crash and fix — the GUI patch was not reentrant

**Symptom**: `EXCEPTION  VEC:0B  SR:2000  ADDR:000C94CA`. Vector 11 is the unimplemented
F-line trap, and the address contains no defined code — i.e. the CPU jumped to garbage.
Repro: play B1 P1, switch to B2 P1, hold `[SCENE B]` and turn a track's amp volume.

**Cause**: `tools/patch_gui.s` installed a return-hook using ONE global slot (`SAVE_RET`
`0x80006c34`) and ONE flag (`DID_OVERRIDE` `0x80006c33`), and `cleanup` jumped through
`SAVE_RET` unconditionally:

1. outer entry: `SAVE_RET = retOuter`, `(sp) = cleanup`, `DID_OVERRIDE = 1`
2. nested entry: `SAVE_RET = retInner` — **clobbers retOuter**
3. inner returns → cleanup restores, clears the flag, jumps `retInner` (fine)
4. outer returns → cleanup sees the flag already 0, skips the restore, and jumps
   `SAVE_RET` = `retInner`, **an already-consumed address** → wild jump → F-line

A second defect rode along: in step 2 the nested entry saved the *already overridden*
globals as if they were the originals, so the restore left them corrupted.

**Fix** (`tools/patch_gui2.s`): guard at the top of `setup` — if `DID_OVERRIDE` is already
set, a nested entry neither overrides nor hooks the return, and runs like stock. One slot
is then sufficient because only one override can be live. The guard branch must be `bne.w`;
`.b` is out of range (the jump crosses the whole 130-byte override block). Validated 4/4 in
`tools/emu_gui2.py`, including the nested case.

**Lesson for future patches here**: any hook that stores per-call state in a fixed global
must either guard against reentry or keep a stack. The emulator harnesses only exercised
single calls, which is why this survived validation and only surfaced on hardware.

## BANK/PTN selection: removing the 4-second countdown — logs `out/ghidra_{bankptn,timeout,countdown,timerstruct,timerrefs}.log`

Manual (Banks and Patterns): pressing `[BANK]` or `[PTN]` opens a SELECT window that
expires in four seconds; `[NO]` exits. On the unit the countdown is drawn as four boxes
that empty once per second.

**State machine** — `FUN_4005a044(_, event)` is the PTN key handler, `event` 1 = press,
0 = release:

- `_DAT_460d1742`: 0 normal, 1 key held, 2 SELECT window open
- `_DAT_460d1ab2`: set on press to `(mode != 2)` — this is what makes **press-again-to-exit
  already work in stock firmware** on both keys (confirmed on hardware). Only the timeout
  and the key LED were missing from what the user wanted.

**The timed window** — `FUN_40059f8c(text, ticks, enable, on_timeout)`:

```
_DAT_460d1e5c = window handle      _DAT_460d1e60 = on_timeout
_DAT_460d1e50 = ticks >> 2         _DAT_460d1e58 = reload
_DAT_460d1e54 = 4                  _DAT_460d1e4c = enable
```

`0xf0 >> 2 = 60` ticks per box, `_DAT_460d1e54 = 4` boxes → the four seconds.
`FUN_40056ab8` is the tick; it gates on `tst.l (0x460d1e4c)` and on expiry calls
`FUN_40056a70` (close + callback). Callers pass `enable`: PTN `1`, SELECT BANK `0`,
`BANK %c: SELECT PTN` `0` — the BANK path enables it afterwards via `FUN_40031200`
(`moveq #1,D0 ; move.l D0,(0x460d1e4c)`), whose only caller is `FUN_4007b26c`.

**Patch (2 bytes)**: `FUN_40056ab8` → `rts` (`4ab9…` → `4e75`). Safe because the whole
timer is exclusive to bank/pattern selection — `FUN_40059f8c` has exactly three callers,
all of them SELECT windows, and the tick has one caller. Closing on a trig press goes
through `FUN_40056b00` from `FUN_4007b2fc`, independent of the countdown. The four boxes
stay full and act as a mode indicator. **Confirmed on hardware.**

**Methodology note**: a scalar-operand sweep MISSES absolute-long operands — Ghidra models
those as references. That is why an early sweep found neither `tst.l (0x460d1e4c).l` nor the
writers of `_DAT_46c82456`. Use `ReferenceManager.getReferencesTo` for globals; keep the
scalar sweep only for immediates and struct offsets.

## PERSONALIZE menu structure — logs `out/ghidra_{personalize,flags,settingsblock,settertbl}.log`

OS 1.40C has **16 items**, not the 12 in the 1.40A manual (added: `SHORT SAMPLE NAME`,
`RECORD QUICK MODE`, `EXT LEN GRID-REC`, `LED BRIGHTNESS`). Three parallel arrays:

| array | address | entries |
|---|---|---|
| labels | `0x400b2a34` | 16 |
| value getters | `0x400b2a74` | 16 |
| `LED BRIGHTNESS` values (`LOW`/`MID`/`MAX`) | `0x400b2ab4` | 3 |
| setters | `0x400b2ac0` | 16 |

Contiguous, `0x400b2a34`–`0x400b2aff`, immediately followed by unrelated FILE MANAGER data
— so **they cannot be extended in place**.

- `FUN_40068e00(win)` renders: label `[i]`, then calls getter `[i]` for the right-hand
  column. Count `_DAT_460e4678`, cursor `_DAT_460e4670`, scroll `_DAT_460e4668`.
- `FUN_40068fd0(key)` handles input: calls setter `[cursor]`. Setters take `(delta, flag)`
  on the stack, add to the current value and clamp.
- Each setting is its **own 32-bit word**, not a bit in a shared mask:
  `MUTE FOCUSES TRK` `0x80000090`, `QUANTIZE LIVE REC` `0x800000ac`,
  `DIS. PAGE AUTOCOPY` `0x800000c0`, `EXT LEN GRID-REC` `0x800000cc`,
  `LED BRIGHTNESS` `0x800000d0`.
- **Free words inside the block**: `0x800000a8`, `0x800000d4`, `0x800000d8`, `0x800000dc`
  (zero references anywhere).
- No settings word is referenced by the project serializer `FUN_40086d7a`, yet the settings
  survive power cycles → the block lives in **battery-backed RAM** (consistent with the
  Startup Menu's EMPTY RESET, which the manual describes as clearing settings). A new flag
  in a free word should therefore persist with no file-format change. *Inferred, not yet
  verified on hardware.*

To add items: relocate all three arrays to the cave with more entries, repoint the
references, write a getter/setter pair per item, and raise the count.

**Item count** — `FUN_40068fa8` is the list init:

```asm
tstl 0x46c8d18c ; sne d0 ; mvsb d0,d0 ; moveq #15,d1 ; subl d0,d1   -> 15 or 16
movel d1,-(sp) ; pea 5 ; pea 0x460e4668 ; jsr 0x4007ec60            -> list_init(list, rows, count)
```

Raising the immediate to 17 gives 17 or 18 and **preserves the conditionality** of the
16th item (which depends on `0x46c8d18c`). One byte.

**Careful**: the getter and setter arrays are reached by `lea`, but the label array is
loaded as an **immediate into D5** (`move.l #0x400b2a34,%d5` at `0x40068efc`). A sweep
for `lea` alone misses it.

Implemented in `tools/patch_menu.s` + `tools/patch_flags.s`: `NO BANK/PTN TIMER`
(`0x800000d4`) and `LAZY TRANSITIONS` (`0x800000d8`, one switch for lazy part apply +
GUI-in-transition + sticky scenes + both dirty indicators). Both default to unchecked, so
an unconfigured unit behaves exactly like stock — every patch got an early-out gate.
Glyphs: `0x400b5e90` checked, `0x400b5e8e` unchecked. Setters are `(flag + delta) & 1`,
which turns both [YES] and the arrows into a toggle.

## Composition testing — `tools/emu_image.py`

**V6 froze on the logo screen while all 25 per-stub emulator tests were green.** Adding a
gate to `save_stub` shifted `restore_stub` by 10 bytes, and the exit detour at
`0x40009664` kept jumping to the old address, landing inside `save_stub`'s tail.
A second stale detour (`xf_stub`, shifted 8 bytes by the `scene_stub` gate) was found by
the same check before it could cause the next crash.

The per-stub harnesses cannot catch this: each loads a freshly assembled `.bin` at a fixed
address and tests its logic in isolation. Nothing tested whether the detours **in the
assembled image** point where the symbols ended up.

`tools/emu_image.py` runs against the real patched image and checks:

1. every detour targets **exactly a known symbol** — not merely "somewhere in the cave",
   which is what made the bug subtle: `0x400d6538` was inside the cave and inside
   `save_stub`; it just was not an entry point;
2. no target lands in the middle of another stub;
3. real execution from each detour site, flagging any PC that touches a cave byte not
   belonging to a stub (i.e. garbage);
4. no stub overlaps the next.

Verified against a deliberately re-broken image: it fails both statically and dynamically.
**Detour targets are now derived from the symbol tables at build time, never hardcoded.**

Three layers now cover a build: per-stub logic (the `emu_*.py` harnesses), image
composition (this), and reproducibility (`sysex/apply_patch.py`). Both hardware bugs in
this project — the reentrancy crash and this freeze — escaped through gaps between layers,
not through a layer.

## Feature set redefined (R2) — what was dropped and why

After instability on hardware, the spec was rewritten and the build restarted from stock:

- **GUI-in-transition: removed.** It did the *opposite* of the new spec — it wrote encoder
  edits into the SOURCE Part and deliberately kept the track dirty, whereas an encoder move
  must now *end* the transition. It was also the patch that crashed (`VEC:0B`, and a second
  `VEC:04` with `ADDR:00000000` consistent with its `cleanup` jumping through a null
  `SAVE_RET`) and the only one that overrode shared globals.
- **Amber scene-trig indicator: removed.** It scanned all 8 tracks and OR-ed the result,
  forcing a per-track property into one global light — so it latched on permanently and
  conveyed nothing. The scan was the symptom, not the cause: the track LED needs no scan
  because the painter already iterates tracks and each pass checks its own.
- **Track LED: fixed.** It was missing the `&& sounding` half of the condition that the
  original design (recorded in `REVERB_LOG.md`) specified — an idle track with a stale `per_track_part`
  read as dirty forever. Voice-active byte at `0x800049d8 + track*0xa8`.
- **New — encoder ends the transition** (`tools/patch_enc.s`, same hook site the removed GUI
  patch used). The destination Part's parameters no longer exist by then: `apply_part`
  computed them and `restore_stub` overwrote them, which is exactly how the track stays
  protected. So `restore_stub` now snapshots them on the way past — at that instant the
  voice buffer still holds the destination values — into `0x80006e00 + track*0x40`, and
  `enc_stub` copies them back when an encoder moves on a dirty track.

`tools/build.py` replaces the ad-hoc packing: it starts from the stock image, derives every
detour from the linker symbol tables, and aborts if any assumption about the stock bytes
fails.

## CF-card flashing — `tools/make_bin.py`

MIDI SysEx takes minutes at 31250 baud. The manual's §8.5.2 OS UPGRADE path reads a `.bin`
from the root of the CF card instead. Decoding the official `.bin` showed the ELUP payload
is simply:

    [4-byte BE length][ELEK container]

— exactly the container `elektron-firmware-tool` already builds, so no new format work was
needed, only the forward direction of the obfuscation `tools/bin_decode.py` already
reverses. `rot16` and `bswap` are involutions, so inverting is direct:

    encode: x = k ^ mixer ^ p ;  c = rot16(x) ^ XOR_A   (variant 0, k & 0x800000 == 0)
                                 c = bswap(x) ^ XOR_B   (variant 1)

with the feedback `k` being the previous **cipher** word.

Getting the patched container out: the `.syx` is 7460 SysEx messages each with its own
framing, so rather than reverse that transport, `EFT_EMIT_CONTAINER=<path>` was added to the
vendored tool (5 lines) to dump the container it already builds internally.

**Validation**: `make_bin.py` regenerates Elektron's official `.bin` **byte-for-byte** from
that file's own container. Nothing about the format is inferred. Confirmed working on
hardware.

One caveat: a container whose size is not a multiple of 4 needs the payload padded to a word
boundary (ours needed 2 bytes; the official happened to align). The device reads the declared
length and ignores the tail. `FUN_4007f748` validates the checksum and returns an error code
*before* touching flash, so a malformed `.bin` is rejected rather than half-applied.

## Lazy transitions — final shape (R10) and the LED saga

The shipped feature: on a pattern change to a different Part, sounding tracks keep the
previous Part's params (no jump), the track LED dims, and the track adopts the destination
Part on any modification — sequencer trig, manual trig, or an encoder move.

- **Audio**: `patch.s` (save/restore + destination snapshot) + `patch_enc.s`. The encoder
  path was the last piece of point (c). The destination params no longer exist when the
  encoder moves — `apply_part` computed them and `restore_stub` overwrote them — so
  `restore_stub` snapshots them into `DEST_SNAP` (0x80006e00, at the instant the voice
  buffer still holds them) and `enc_apply` copies them back. **There are FIVE encoder
  editors** (`0x40052e98`, `0x40052ae8`, `0x40053498`, `0x40053a68`, `0x4005435c`), same
  shape but different prologues; hooking only one made the feature look dead. All five are
  trampolined in `patch_enc.s`.
- **LED**: `patch_led.s`, eight instructions — `per_track_part[track] != active Part` →
  dim (`0xF`→`0x5`). That is the whole indicator, and it was ALREADY WORKING before this
  round; the user said so explicitly.

### The LED mistake, recorded so it isn't repeated

I "fixed" a working indicator and spent many hardware flashes making it worse. Root causes,
each a thing assumed rather than verified:

1. The "always dirty" bug belonged to the **amber scene-trig** indicator (removed), which
   OR-ed all 8 tracks into one light. `led_stub` never had it — the painter iterates tracks
   and each pass checks its own. I conflated the two and edited the healthy one.
2. Added a `&& sounding` test reading `0x800049d8` — a byte that **pulses** — so the LED
   flickered. The audio patch reads it once per pattern change; in a per-frame painter it is
   not a boolean.
3. Added a patch-owned dirty mask at `0x80006c70` — which the **firmware writes**, proven by
   the flicker returning exactly when the mask was present (R5/R6/R7/R9) and gone when it was
   removed (R8/R10). "Free RAM" was never verified; the earlier `GhidraRamFree` scan misses
   computed/indexed writes. Proven-stable patch RAM ends around `0x80006c64` (scene block);
   `0x80006c70` is past it.

**Rule**: when something worked and now doesn't, the first suspect is what I changed, not the
firmware. And never trust "this address looks free" — the only RAM proven safe is what an
already-working patch reads back correctly.

### Definition (R10): dim == "not yet re-trigged since the Part change"

After the LED saga, the feature was redefined around what the code naturally does rather than
chasing an encoder-clears-the-dim behaviour. The dim means: a **sounding** track that changed
Part and has **not been re-trigged**. A trig settles `per_track_part[track] = active` durably
and clears it; an encoder move does not (it applies the destination sound via `DEST_SNAP`, but
`per_track_part` is firmware-owned and re-asserted to source until a genuine trig). Under this
definition the encoder-not-clearing-the-dim is correct by design: the LED and the encoder are
two orthogonal signals — "re-trigged yet?" vs "apply the destination sound now". No further RAM
hunt or `per_track_part` lifecycle mapping is needed. (Kept for reference: `0x100f8598`, the
"param edited, re-apply" flag, has many writers and no direct reader — polled via a computed
address.)

---

## ARP key-scale (F knob) — RE map for adding scales (Greek modes / blues)

Educational investigation into extending the arpeggiator's "key scale" (ARPEGGIATOR
SETUP, F knob) beyond the stock major/minor. No binary was changed. All addresses
verified against `out/raw/section_3_MAIN_OS.bin` (file_offset = vaddr − 0x40000400);
analysis ran in a fresh fully-analyzed project at `out/ghidra_arp` (scripts:
`tools/GhidraArp*.java`).

### Mechanism (manual §15.4.4)
The F knob forces arpeggiated notes *and* the per-step note offsets onto a key scale;
it "affects the note trigs of the track even if the MODE setting is OFF" → the actual
pitch quantizer sits on the shared MIDI note-trig output path, not inside the arp loop.

### Selector — fully mapped and patchable
- **Per-track storage**: arp struct byte at `_DAT_46c82456 + pattern*0x18b2 + track*0x24
  + 0x8f273` (offset +3; +0 is the arp LEN byte). In the compact load struct
  (`FUN_400260d0`) it is field **+0x16**.
- **Encoder handler**: `FUN_4007a2ec`, branch `param==5`. Reads the byte
  (`mvz.b (1,A0),D0` @0x4007a428), min `0x400d4066`=0, count `0x400d4096`=**0x19 (25)**,
  `subq #1` → max 24, clamp, write back (`0x4007a466`).
- **Enum**: 25 states = `0` OFF, `1..24` = 12 roots × {major,minor}, encoded as one
  value: `root=(v-1)>>1`, `quality=(v-1)&1` (0=MAJ, 1=MIN). No hidden scales.
- **Label render** (`FUN_4003b790`, descriptor @0x400d40c6): draws root-note name +
  suffix from two parallel 25-entry pointer tables — roots @`0x400a7e54`, suffixes
  @`0x400a7eb8` (`MAJ`=0x400b5750, `MIN`=0x400b4419). Guard `moveq #0x18` @0x4003b7ca.
  The scale is TEXT only (root + maj/min); no keyboard is drawn — so new scales are
  cheap visually (just add suffix strings + widen the tables).

### To add qualities (major,minor → +dorian,phrygian,lydian,mixolydian,locrian,blues)
Encoding is root×quality, so 8 qualities ⇒ 1 + 12×8 = **97 states**. Selector/label side:
1. count datum `0x400d4096`: `19`→`61` (25→97).
2. formatter guard `moveq #0x18` @0x4003b7ca (`70 18`→`70 60`).
3. table-copy sizes `pea (0x64).w` @0x4003b7a0 / @0x4003b7b6 (100→388=`0x184`), enlarge
   `FUN_4003b790` stack frame accordingly.
4. rebuild both label tables to 97 entries (root ×8 per pitch class; suffix cycling
   8 abbreviations e.g. DOR/PHR/LYD/MIX/LOC/BLU) — packed literal pool, cannot grow in
   place, relocate + repoint the two `pea` bases (@0x4003b7a4→0x400a7eb8,
   @0x4003b7ba→0x400a7e54).

### Runtime quantizer — LOCATED (`FUN_4009f794`), all bytes verified
The MIDI note-trig emitter for all 8 MIDI tracks (called from `FUN_400a1608`), runs for
every track's note trigs regardless of arp MODE. Reads the scale byte from a **third RAM
mirror** at `0x46c76df1 + track*0x44` (not the project struct +0x8f273; `FUN_400260d0`
writes all three mirrors on load). Algorithm (verified):

```
scale = mirror[track][0x31]                 ; 0x4009fad2  move.b (0x31,A0),D0
if (scale == 0) noQuantize                   ; OFF
root = (scale-1) >> 1                         ; asr.l #1     (root 0..11)
K    = (scale & 1) ? 0x0C : 0x15              ; btst #0 @0x4009fae4; odd=MAJOR(12), even=MINOR(21)
local_44 = K - root
idx  = (note + local_44) % 12                 ; 0x4009fb6a moveq #0xC / divsl.l
note = note + snaptable[idx]                  ; 0x4009fb74 lea 0x400d80a0 ; add.l (A0,idx*4),D0
```

**One snap table only** @`0x400d80a0` (file `0xd7ca0`), 12×int32 =
`[0,-1,0,-1,0,0,-1,0,-1,0,-1,0]` → in-scale PCs `{0,2,4,5,7,9,11}` = **MAJOR**.
Minor has no table of its own: it reuses major rotated by the relative-major offset
(K=21 vs 12; +9 mod 12). Snapping is always DOWN 1 semitone for out-of-scale tones.

Verified byte anchors: scale read `0x4009fad2` (`10280031`); quality bit `0x4009fae4`
(`08000000`); minor K `0x4009faec` (`7415`); major K `0x4009faf8` (`760c`); OFF guard
`0x4009fb58` (`4aaeffc06f22`); table lea `0x4009fb74` (`41f9400d80a0`).

### Adding scales is FEASIBLE — two tiers
- **5 Greek modes = FREE** (all rotations of major, reuse table `0x400d80a0`, new K each):
  Dorian 14, Phrygian 16, Lydian 17, Mixolydian 19, Locrian 23 (Ionian 12 / Aeolian 21
  already present). `local_44 = K - root` stays > 0 for all roots, satisfying the guard.
- **Blues** `{0,3,5,6,7,10}` is non-diatonic → needs one new 12×int32 snap table + a
  conditional table base at the lookup `lea 0x400d80a0` (`0x4009fb74`).
- **Code change (not data-only):** rewrite the decode block `0x4009fad2–0x4009fafc`
  (~46 B). With 8 qualities the split becomes `root=(v-1)%12 / quality=(v-1)/12` feeding a
  small switch that picks K (and, for blues, the alternate table). Relocate to a code cave
  + detour (same pattern as the other patches); pair it with the selector/label widening
  above (enum 25→97 at `0x400d4096`, formatter guard `0x4003b7ca`, label tables
  `0x400a7e54`/`0x400a7eb8`).

### IMPLEMENTED — 12-quality arp key scale (`tools/patch_arp.s`, emulator-validated)

Standalone build `tools/build_arp.py` → `out/mainos_arp.bin` (stock + arp only, for
isolated testing). Cave at `0x400d7000` (inside the proven-free R10 run, clear of R10's
stubs). Adds 10 qualities to the F-knob: MAJ MIN + DOR PHR LYD MIX LOC BLU PHD MEL OCT HIR.

- **Encoding**: value 0 = OFF; 1..144 = root*12 + quality (root = (v-1)/12 slow/outer,
  quality = (v-1)%12 fast/inner). Enum count datum `0x400d4096`: 25 → 145.
- **decode_cave** (detour @0x4009fad2, replaces the 46-byte local_44 block): sets
  `local_44 = 12*quality + (12-root)` (0 for OFF). The 12*quality term vanishes under the
  stock mod-12, so the existing idx computation still yields (note-root) mod 12; and the
  lookup recovers quality as (local_44-1)/12 — so NO extra stack slot / frame change is
  needed (the prologue movem saves regs at the frame bottom, so growing the frame was
  unsafe). Division by 12 done with the magic multiply (v*171)>>11 (exact for 0..143;
  avoids ColdFire divide-form uncertainty).
- **lookup_cave** (detour @0x4009fb74, replaces `lea 0x400d80a0`): idx += quality*12;
  note += UT[quality*12+idx] (signed byte); preserves D2/D3.
- **fmt_cave** (detour @0x4003b790, replaces FUN_4003b790): computes root/quality and
  draws NOTETAB[root] + QUALTAB[quality] instead of the stock 25-entry tables. Same
  callback contract (draw suffix at pos via 0x40013a08, tail-draw root at pos+5).
- **UT** unified snap table (144 signed bytes, quality-major): MAJ/MIN reproduce stock
  `0x400d80a0` exactly; 7-note scales snap down; BLU/OCT/HIR snap to nearest. A snap-up at
  note 127 wraps to a negative byte and the firmware drops it (benign, top of MIDI range).

Validation `tools/emu_arp.py` (Unicorn): decode 145/145, lookup 18432/18432 (scale×note),
MAJ parity 0 mismatches, formatter labels correct. Composes with R10 (no detour/cave
overlap) — mergeable as a new revision. NOT yet hardware-tested.

---

## Bank load from CF is ASYNC and does NOT stop audio (enables live bank paging)

Educational RE of whether a single-bank reload halts playback (for a "page in 16 banks
mid-performance" feature). Verdict: **it does not stop the sequencer/audio, and the load
runs on a dedicated background task** — the same concurrency that streams samples from CF
while playing. Scripts: `tools/GhidraBank*.java`.

### Two-tier bank storage (new structural finding)
- **Resident bank blobs**: `0x400e21e0 + bank*0x9b340` (635,200 B/bank, 16 banks ≈ 10 MB).
  Cold store in RAM, deserialized from `<proj>/bankNN.work` by FUN_4008ded0.
- **Live working copy**: patterns at `0x46c82456 + pat*0x18b2` — filled from the blob only
  when a bank becomes current (FUN_4000faf0), gated on `DAT_80000002` = playing bank.

### RELOAD BANK call chain (verified addresses)
- Menu builder FUN_40063590 → confirm handler FUN_40063bf8.
- FUN_40063bf8: FUN_400a10c8 (reset UI/MIDI scratch — NO transport stop) + FUN_40022778
  posts job `{type=0x14, mask, begin=0x40023230, done=FUN_40023bf4}` via FUN_40000c3c to
  queue @0x460d17ce (sets ColdFire soft-IRQ 0xfc04c010|=0x800 to wake consumer).
- Consumer = dedicated task **FUN_4008445c** (created FUN_40040b94, prio 1, own 0x4000
  stack), blocking-dequeues FUN_40000d00, switch on msg type:
  - type 0x14 → FUN_4008f0b0(mask): loops bits 0..15, copies `bankNN.strd → .work` via
    FUN_40016388 (buffered FS copy, no ATA spin). On done posts type 6.
  - type 6 → FUN_400905d4(mask): loops bits 0..15, opens `bankNN.work`, FUN_4008ded0
    deserializes into `0x400e21e0 + bank*0x9b340`. For NON-playing banks: RAM fill +
    FUN_4000fa98(mask,0) only. Live re-apply gated `if (DAT_80000002==bank)`
    (FUN_4000faf0/FUN_400a1030/FUN_40009094).
- End re-sync FUN_40023998 → FUN_400238a4 (re-derive voice/engine to current position;
  clock never stops). Short-circuit this when the playing bank is not in the mask.
- Blocking "WORKING PLEASE WAIT" (0x400b68b2) is used only by OS-upgrade/other paths
  (FUN_40070db8/FUN_4006e450), NOT the reload path (which uses the non-modal
  "RELOADING BANK" 0x400b3898 overlay FUN_400808bc).

### Feasibility — "page 16 banks from a sibling project, no audio stop"
~90% exists: FUN_4008f0b0/FUN_400905d4 already accept a 16-bit bank mask and loop all 16
into disjoint per-bank regions on the background task, concurrent with audio, no stop.
To build: (1) redirect the filename builder from FUN_40025230(0,0) (current project) to a
sibling project dir; (2) trigger the type-6 job with a mask excluding the playing bank;
(3) short-circuit FUN_400238a4 when the playing bank isn't in the mask.
- "PRELOAD" (0x400be7c5) is a dead string (no xref) — not a usable primitive.
- **Hard usage constraint**: sample slots (Flex/Static pool) are PROJECT-level, not bank-
  level; parts reference samples by slot. Sibling projects must share the same sample
  pool/slot assignments, or paged banks play the wrong/absent samples. Flex RAM is not
  reloaded by a bank load either → siblings should share Flex assignments.

### HARDWARE-VALIDATED: non-playing bank loads from CF without stopping audio

De-risking experiment (throwaway builds, `tools/patch_exp_bankload.s` + `tools/build_exp.py`)
confirmed on a real MKII the assumption behind the live bank-paging feature.

Method: hooked the reload confirm handler FUN_40063bf8 (the sole caller of the poster
FUN_40022778) to (a) skip the synchronous pre-step FUN_400a10c8 and (b) force the reload
mask to a NON-playing bank `(current+1)&15`; plus NOP the end-of-load re-sync call
`jsr FUN_400238a4` at 0x400239a2 (`4ebaff00` → `4e71 4e71`).

Findings, in order (each isolated one variable):
- v1 (mask hook only, pre-step still ran): **audio cut at the instant of confirm** →
  the cut is FUN_400a10c8 (per-track note/voice scratch reset), which runs synchronously
  on confirm, NOT the async load. (Also fixed a self-inflicted VEC:04: a 6-byte detour at
  0x40022778 spilled 2 bytes into the following `lea`; resume must replicate the displaced
  `lea` and land at 0x40022782.)
- v2 (skip pre-step, non-current bank, re-sync kept): immediate cut gone; **audio cut a few
  steps AFTER confirm** → the delayed cut is the end-of-load re-sync FUN_400238a4.
- v3 (skip pre-step + skip re-sync + non-current bank): **audio kept playing through the
  entire load, no cut.** ✓

Conclusion: the async loader task filling a non-playing bank's disjoint RAM region
(0x400e21e0 + bank*0x9b340) does not disturb playback. The only two things that stop audio
are the confirm-menu pre-step and the end-of-load re-sync — both avoidable when the loaded
bank(s) exclude the playing bank. The live bank-paging feature is therefore viable; the
remaining work is plumbing (sibling-project detection, PAGE-key state machine, YES/NO popup,
redirect the load path to the sibling project dir) + the sample-pool-sharing usage constraint.

### S1 HARDWARE-VALIDATED: redirected sibling bank load, no audio stop

Bank paging Stage 1 (tools/patch_bankpage_s1.s, tools/build_bankpage_s1.py) confirmed on the
MKII. Three detours over R11: (1) gate FUN_40025230 @0x40025244 — global g_redirect (char*)
overrides the projname==0 default (0x100f8378) when set; (2) trigger at FUN_40063bf8 @0x40063bfe
— skip pre-step FUN_400a10c8, sprintf("%s_2", 0x100f8378) into a cave buffer, set g_redirect,
mask = 0xffff & ~(1<<curbank) (0x100b14ce), tail-post via FUN_40022778; (3) done at FUN_40023998
@0x400239a2 — clr.l g_redirect + skip re-sync (replicate displaced `pea (0x1).w`, resume 0x400239aa).
The RELOAD gesture loaded the sibling "<name>_2" project's 15 non-playing banks into RAM with the
sequencer running and NO audio stop; a paged bank then played the sibling's patterns. Confirms the
FUN_40025230 redirect gate + the masked multi-bank load are the correct, audio-safe mechanism.
g_redirect/sib_name live in the code cave (writable SDRAM) — worked fine on hardware.

### S3/S3b: PAGE-key bank paging UX (R12) — cycling emulator-validated

Bank paging integrated into build.py as R12 (tools/patch_bankpage.s). Three detours over the
R11 image, cave at 0x400d7400:
- **page_cave** ← FUN_4004ffc4 @entry ([PAGE] key, keycode 0x1b). Gate: edge==1 (press) AND
  in SELECT BANK (`_DAT_460d1e5c!=0 && _DAT_460d1e60==0x4007b408`) AND no popup open
  (`_DAT_460e5cd0==0`). If gated: advance g_page `(page&3)+1` (1→2→3→4→1), build the target
  name into sib_name (page 1 = base `<name>` via `sprintf("%s")`, pages 2–4 = `<name>_N` via
  `sprintf("%s_%d")`), show `FUN_4006d57c("LOAD BANKS?", 1, {&sib_name}, 3, confirm_handler)`,
  swallow the key (rts). Else fall through (replicate displaced `lea -0x10,SP`+`movem`, resume
  0x4004ffcc).
- **confirm_handler**: YES (p==0) → g_redirect=sib_name, mask=`~(1<<playingbank)`, post via
  FUN_40022778, re-enter SELECT BANK via `FUN_4007af80(0x2f,1)`. NO → nothing.
- **gate_cave** ← FUN_40025230 @0x40025244 and **done_cave** ← FUN_40023998 @0x400239a2:
  the S1 redirect + conditional-re-sync mechanism (done_cave now does the stock re-sync when
  g_redirect==0, so a normal RELOAD still re-syncs).

Validation: `tools/emu_bankpage.py` (Unicorn, runs real sprintf) — cycling + name construction
1→2→3→4→1 with correct `<name>`/`<name>_N` = ALL PASS. The core load path is the S1/S3a
mechanism (hardware-proven). **S3b's UX additions (cycling, dynamic name, PAGE hook) are
emulator/static-validated only — pending hardware test.**

Deferred (need hardware + the vtable, see DESIGN_BANKPAGE.md):
- **Existence gate**: only page when `<name>_2` exists, else stock PAGE. Recipe worked out:
  build `<name>_2`, `FUN_40025230(0, name)` → path `0x460bf112`, `FUN_40025650(path)` (nonzero
  = valid project; it checks `<path>` and `<path>/AUDIO` via the FS vtable `_DAT_46c823fa`).
  Not shipped because that vtable is uninitialized in the static image → not emulator-testable,
  and it sits on the PAGE critical path. Currently PAGE always pops the confirm in SELECT BANK
  (NO declines); a load of a missing page falls to the stock error dialog.
- **Skip-missing-page** cycling; the **page LED** (FUN_400135b0(id,0xF)); the **16th-bank
  catch-up** on bank change; the **save guard** while paged.

### Bank paging existence check — via file-open, not a dir predicate (R12, hardware-validated)

The sibling-existence check first tried FUN_40025650 (the firmware's "valid project?"
predicate). Hardware diagnostics (tools/patch_bankpage_diag.s) showed it returns 0 even for
the CURRENTLY-LOADED project (C=0) — its FS vtable `_DAT_46c823fa` does not resolve project
DIRECTORIES from this call site. Switched to a FILE-open check: existence = can we open
`<sibling>/bank01.strd` via the loader's own open helper FUN_40016864(fh, path, "r", buf,
0x10000) (D0>=0 = opened; close with FUN_4001677c). Diagnostics confirmed the sibling's
bank01.work AND bank01.strd both open (wrk=1 std=1).

Critical rule learned: **only ever open SIBLING files, never the playing project's** — a
diagnostic that opened the current project's bank01.strd and closed it made the NEXT open
fail with -2 (closing a handle the firmware holds open for playback corrupts FS state).
chk_sibling only touches `<name>_N` files, so it is safe. Validated end-to-end in
tools/emu_bankpage.py with the open/size/close vtable slots stubbed to simulate a card with
base + _2 + _3 (no _4): the PAGE cycle skips _4 and, with no `_2`, PAGE stays stock.

Open refinement (for the non-modal redesign): skip the CURRENTLY-LOADED page in the cycle
(track g_loaded, updated on YES-load, reset to base on project load) so it never offers a
useless reload of the page you are on.

### Bank paging SHELVED — the audiopool is the real blocker

Bank paging (loading sibling-project banks live) was reverse-engineered and hardware-proven to
load without stopping audio, but cancelled. Reason: it only avoids the audio stop by requiring
siblings to SHARE the sample pool. `PROJECT → CHANGE` stops playback because it reloads the
**audiopool** (samples); paging sidesteps that only by not touching samples. So paging brings in
new patterns/parts but not new sounds — too limiting, and it doesn't solve the root problem
(loading genuinely new material live). The real, unsolved frontier is a **live audiopool swap**
(new Flex/Static samples into RAM without halting the DSP/playback). Shipped firmware reverted to
R11 (arp key scales + lazy transitions). The bank-paging sources/emulators/diagnostics remain in
tools/ and DESIGN_BANKPAGE.md as documented, reusable RE.
