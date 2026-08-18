# Elektron Octatrack firmware architecture (MKII, OS 1.40C)

Architecture document consolidated from the educational reverse engineering of the
firmware. It brings together everything that has been verified: hardware, OS format, kernel,
storage, audio engine, sequencer, and the memory map. It complements `NOTES.md` (chronological
log) and the scripts in `tools/`.

> **Scope and honesty**: everything marked ✓ is verified (checksum from the firmware itself,
> byte-exact decompilation, or direct disassembly). Anything marked ~ is a strong inference but
> not confirmed byte by byte. No Elektron firmware is redistributed; only analysis.

---

## 1. Executive summary

The Octatrack is an 8-track sampler/sequencer. Its firmware runs on a
**Freescale ColdFire** CPU (68k family, big-endian, ~266 MHz) assisted by a **Freescale
DSP56xxx** DSP for real-time audio. On top of the hardware runs a proprietary preemptive
**Elektron microkernel** (not a commercial RTOS). The OS is loaded from **CompactFlash** via the
ColdFire's on-chip **ATA** controller.

The architecture is uniformly **producer/consumer decoupled by buffers in RAM**:
the same kernel message-queue pattern appears in storage I/O and in the
audio pipeline.

---

## 2. Hardware

| Component | Detail | Confidence |
|---|---|---|
| CPU | Freescale **ColdFire MCF5445AVR266** (32-bit, big-endian, 266 MHz) | ✓ (board photo, 7 Aug 2026; the earlier "prob. MCF5445x, ~266 MHz" guess was exact) |
| Audio DSP | Freescale Symphony **DSP56721** (`DSPB56721AG`) — **two** DSP5636x cores, **200 MHz / 200 MIPS each**, no external memory controller | ✓ (board photo, 7 Aug 2026) |
| Storage | **CompactFlash** (FAT16/32), OS and data; boots to DEMO without CF | ✓ (official) |
| Expansion bus | FlexBus (chip-selects for ATA, DSP, RAM) | ✓ (from the firmware) |

The firmware **corroborates the ColdFire CPU**: it uses the on-chip ATA controller (registers in
the MBAR space `0xFC04_51xx`) that characterizes the MCF5445x family.

---

## 3. OS format and update chain ✓

Elektron distributes a ZIP with **two transports of the same OS**: a `.bin` and a `.syx`.
Both wrap the same compressed container, which decompresses to the **MAIN OS** (1,112,560 B,
SHA256 `164f3122…`, ColdFire code).

```
.bin  = [ELUP hdr][seed] + XOR-feedback( [len] + ELEK( aPLib( MAIN OS ) ) ) + checksum
.syx  = SysEx 7-bit(              ELEK( aPLib( MAIN OS ) )              )
```

- **ELUP layer** (`.bin`): XOR obfuscation with feedback (fixed embedded constants
  `0x9E3B16A2`/`0x764E28CA`, mixes `C3=0x360FA955`/`C7=0xEF4A9AB6`) + additive checksum.
  Reimplemented in `tools/bin_decode.py`; **the firmware checksum validates** → correct.
- **ELEK layer**: proprietary container with a section compressed in **aPLib**.
- **No cryptographic signature** in any layer → firmware is analyzable and modifiable
  (which is why `elektron-firmware-tool` can rebuild `.syx` with recalculated checksums).

**OS validation on update** (`FUN_4007f748`), with its error codes:
`-1` IO · `-2` not a valid OS · `-3` length · `-4` checksum · `-5` MK1 not allowed (`<"0156"`)
· `-6` cannot downgrade version (`<"0178"`).

**UI → write flow** (all decompiled):
```
OS UPGRADE menu → confirm → os_upgrade (stops audio, "WORKING PLEASE WAIT", enqueues task)
 → scans the CF, validates → os_apply_flash (critical section) → writes the CF via ATA → reboot
```

---

## 4. Kernel: proprietary preemptive microkernel ✓

It is not MQX/ThreadX/VxWorks (zero third-party signatures; only banner `ElektronOctatrack DPS-1`).
It is a custom microkernel with all the classic components:

- **Task Control Block (TCB)**: state @`0x13` (0=blocked, 1=ready), priority @`2`, list pointers
  @`0`/`1`. Current task = `_DAT_800068fc`; top priority = `_DAT_800068d8`.
- **Per-priority ready queues** (doubly-linked circular lists per level).
- **Context switch via `TRAP #0`** (`FUN_40000818`, wait/yield).
- **Message queues with blocking receive** (`FUN_40000c3c`, post): wakes the task
  that is waiting and forces a reschedule with `0xFC04_C010 |= 0x800` (ColdFire interrupt controller).

**Scheduler / context switch core** ✓ (`FUN_4000056e`, reached by `TRAP #0` and by the timer):
1. Saves ALL of the current task's registers (D0–D7, A0–A6, SR) into its TCB `_DAT_800068fc`
   at offsets `0x0c`–`0x48` (hence the TCB layout: saved context at `0x0c`+, SP at `0x38`).
2. Takes the highest-priority ready task (head of the queue at `_DAT_800068d8`).
3. Clears the reschedule bit (`0xFC04_C010 &= ~0x800`) and **re-arms the ColdFire PIT timer
   `0xFC08_0000` (reload `0xb3f`)** = the time-slice quantum → **time-preemptive** scheduler.
4. Switches `_DAT_800068fc` to the new task and restores its context.

This kernel **unifies the whole firmware**: the ATA "async queues" and the audio "voice mailboxes"
ARE its message queues. Scheduler double trigger: `TRAP #0` (voluntary yield)
+ PIT `0xFC080000` (temporal preemption).

---

## 5. Storage: ATA/CompactFlash stack ✓

```
filesystem → async command queue (FUN_4001568c, +event) → dispatcher (FUN_40015098)
 → dispatch by ATA opcode → handler → ATA task-file registers @ 0x90000000 (PIO)
```

- **ATA commands** dispatched: `0x20` READ SECT · `0x30` WRITE SECT · `0xC8` READ DMA ·
  `0xCA` WRITE DMA · `0xE0` STANDBY.
- **Driver with vtable** (`FUN_40015e28` sets it up) and **hardware variant detection**
  by reading an IDENTIFY-type descriptor.
- **ATA task-file registers** @ `0x9000_00xx`: data `a0`, seccount `a8`, LBA `ac/b0/b4`,
  device `b8` (`|0xE0` = LBA mode), command `bc`, status `d8` (BSY/DRDY/DRQ).
- ATA host (control) in the ColdFire MBAR `0xFC04_51xx`.

---

## 6. Audio engine and sequencer ✓

Engine data structures (all in the `0x80000000` RAM window):

| Structure | Address / layout |
|---|---|
| Per-track voice state (audio) | base `0x800049d8`, stride `0xA8`, ×8; byte[0]=active |
| MIDI track state | `0x80006500[t]`, global `0x800065b8` |
| Voice command mailboxes | `0x46c7e9fa` / `0x800018be` / `0x800018de` `[t*4]` |
| Per-track pattern data | `_DAT_46c82456 + pattern*0x18b2 + track*0xc` |
| Globals | current track `0x100b14cc`, current pattern `0x80000003` |

**Audio pipeline (control path)**:
```
sequencer trig
 → FUN_40005178 writes voice mailbox (RAM)
   → FUN_4000c8a4 (frame builder, control-rate): consumes mailboxes, updates 8 voices,
      assembles a parameter FRAME in a DOUBLE BUFFER in shared RAM 0x80000000 (ping-pong 0x800000e0)
     → handshake with the DSP via registers @ 0x20000000
       → DSP56xxx reads the frame and synthesizes (playback, time-stretch, filters, FX)
```

**DSP interface: MMIO at `0x20000000`** (revealed by radare2):
- `0x2000_0000` control command (`0x81` = start DSP, `0x8C` = swap frame)
- `0x2000_0004` command/status (write, poll bit7 busy)
- `0x2000_0008` status/ready (bit `6`: DSP ready — polled at boot and on every transfer)
- `0x2000_0014`/`0x18`/`0x1c` data port (the 3 bytes of each 24-bit word)

**DSP boot** ✓ (`FUN_40001d4c` = DSP program loader): uploads the program to the DSP
**3 bytes at a time = 24-bit words** through the `0x20000014/18/1c` port, with a handshake on the
ready bit of `0x20000008`, and starts the DSP by writing `0x81` to `0x20000000`. The **24-bit**
word size confirms that the DSP is a Freescale DSP56xxx (hardware fact deduced from the firmware
itself). Args: `param_1`=program, `param_2`=length, `param_3`=load address in the DSP.

**Trig → voice** ✓ (`FUN_400977cc`, dispatched by machine type): given a trig on a track, it reads its
machine state (`FUN_40097168` → 0–4) and, depending on the event type, emits the voice command via
`FUN_40005178` with flags (`0x80` start, `0x10`/`0x8010`/`0xf010` = one-shot/hold/stop/retrig).
It is the bridge "there is a trig on the step" → "the voice sounds".

**Work split**: ColdFire = control (RTOS, sequencer, assembles parameters).
DSP56xxx = signal (real-time audio). Synchronized by double buffer + handshake.

---

## 7. Consolidated memory map

| Window | Use |
|---|---|
| `0x40000000` | SDRAM: code (OS image @ `0x40000400`) |
| `0x46000000` | SDRAM: data/BSS and app objects |
| `0x20000000` | **Audio DSP coprocessor** (cmd `04`, status `08`, frame idx `1c`) |
| `0x80000000` | Fast/shared RAM: voice state, kernel TCBs, **double-buffer DSP frames** |
| `0x90000000` | ATA task-file (CompactFlash) via FlexBus |
| `0x100b0000` | Small globals (current track/pattern) |
| `0xFC000000` | ColdFire on-chip peripherals (MBAR): ATA host `FC0451xx`, IRQ ctrl `FC04C010` |

**Image load base**: `0x40000400` (determined empirically: 1441 string pointers
resolve with that base). Image data/BSS ~`0x400bxxxx`.

---

## 8. Project tools (all reproducible)

Some of the archaeology tools were pruned in the octabam refactor and live in
git history (`git log --all -- tools/<name>`), per the repo's history policy.

| Script | Where | What it does |
|---|---|---|
| `fetch-os.sh` / `analyze.sh` | `scripts/` | downloads the official OS, entropy + binwalk + decompression |
| `bin_decode.py` | `tools/` | decodes the ELUP `.bin` (deobfuscates + validates checksum) |
| `decode_elek.c` | history | decompresses the ELEK container (aPLib) → MAIN OS |
| `find_base.py` | `tools/` | determines the load base by pointer→string correlation |
| `string_func_map.py` | history | function→UI-strings map (619 functions) |
| `disasm.sh` | `scripts/` | radare2 with correct arch/base (m68k BE @ 0x40000400) |
| `Ghidra*.java` | history | headless decompilation scripts (Ghidra 12, Coldfire language) |

---

## 9. Open fronts

- **Sequencer clock**: the periodic source that dispatches the trig-processor `FUN_400977cc`
  (by pointer, according to machine type) — internal tempo clock or MIDI clock (0xF8).
- DSP program load: where the blob that `FUN_40001d4c` uploads comes from (an OS section?).
- Remaining ATA handlers; large functions the ColdFire decompiler does not lift (read in ASM).
- Extract the vector table (`0x400` preamble, not in this section) for the ISR map.
