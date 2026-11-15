#!/usr/bin/env python3
"""Load the Octatrack OS into Ghidra: the ColdFire MAIN OS and both DSP payloads.

    python3 tools/ghidra/ot_ghidra.py layout             # -> out/ghidra/load/: memory images + layouts
    python3 tools/ghidra/ot_ghidra.py import [--ghidra DIR] [--project DIR] [--only MAIN_OS,DSP_A] [--image [PATH]]
    make ghidra [GHIDRA=<install dir>] [IMAGE=out/mainos_bus.bin]   # both steps
    make ghidra-install GHIDRA=<stock 12.1.4>            # the Ghidra to point GHIDRA at (install.sh)

Three programs in one Ghidra project (default out/ghidra/octatrack.gpr):

  MAIN_OS  the ColdFire image at 0x40000400, with the board's memory map
           (docs/firmware/ARCHITECTURE.md section 7), the on-chip peripherals
           the docs name, the interrupt handlers (KERNEL.md) and every
           stock address a module names with `.set`/`.equ`.
  DSP_A    core 0 (tracks 5-8), payload A, and
  DSP_B    core 1 (tracks 1-4), payload B: P/X/Y exactly as the ColdFire
           uploads them (tools/build/dsp_modmap.py), the 64 K-word shared
           window with both bootstraps and payload A's shared records in it,
           X and Y mapped onto P there (they alias on the chip, CHIP.md
           section 3), the I/O registers under the names dsp56kDisassemble
           prints, the vectors, and both effect dispatch tables with every
           entry named (DSP.md section 5).
  REMIX    with --image: a built image (default out/mainos_bus.bin) under
           MAIN_OS's layout, the build's appended payloads unpacked to the
           DRAM addresses the loader copies them to, so module code and its
           calls into stock are in one listing.

Everything is derived from YOUR out/raw/section_3_MAIN_OS.bin at run time;
nothing from the image is stored in the repo. The layout files are plain
text (one directive per line, tools/ghidra/OtLayout.java is the reader), so
a finding can be added to the tables below and the project re-imported.

The DSP programs need Ghidra's DSP56300 processor module and the MAIN OS is
best read with the 68000 module's ColdFire EMAC fractional variant
(tools/ghidra/README.md says where both come from). Without them the MAIN OS
falls back to stock Ghidra's `68000:BE:32:Coldfire` and the DSP programs are
skipped.

DEBUG=1 prints every step and streams Ghidra's own output.
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import dsp_modmap as dm  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
IMG = ROOT / "out/raw/section_3_MAIN_OS.bin"
OUT = ROOT / "out/ghidra"
DEBUG = bool(os.environ.get("DEBUG"))


def log(msg):
    if DEBUG:
        print(f"[ghidra] {msg}", file=sys.stderr)


# ------------------------------------------------------------------ ColdFire --

BASE = dm.BASE

# ARCHITECTURE.md section 7. (name, start, length, flags); flags r/w/x/v(olatile).
CF_BLOCKS = [
    ("FLASH_CS0", 0x00000000, 0x00800000, "r"),
    ("CS1", 0x10000000, 0x00100000, "rw"),
    ("HI08", 0x20000000, 0x00001000, "rwv"),
    ("SDRAM_LOW", 0x40000000, 0x00000400, "rwx"),      # below the image: the vector preamble, not in this section
    ("SDRAM", None, None, "rwx"),                       # image end .. 0x47ffffff, filled in below
    ("SRAM", 0x80000000, 0x00008000, "rw"),            # 32 KB on-chip SRAM: voice state, TCBs, DSP frames
    ("ATA", 0x90000000, 0x00001000, "rwv"),
    ("MBAR", 0xfc000000, 0x00100000, "rwv"),
]
SDRAM_END = 0x48000000                                  # 128 MB
UNCACHED = 0x48000000                                   # the same SDRAM, uncached
UNCACHED_ALIAS = UNCACHED - 0x40000000                  # the loader writes DRAM through the uncached view

# On-chip peripherals: bases and the registers the docs read. (address, name, comment)
CF_IO = [
    (0xfc008000, "FLEXBUS", "FlexBus chip selects (DSP.md 1: 0xfc00801c written at boot)"),
    (0xfc044000, "EDMA", "eDMA controller"),
    (0xfc045000, "EDMA_TCD0", "eDMA TCDs, 32 bytes per channel (tools/emu/ot_emu/periph.h)"),
    (0xfc048000, "INTC0", "vectors 64 + source (KERNEL.md)"),
    (0xfc048010, "INTC0_INTFRCH", "force: bit 0 the sequencer tick, bit 4 MIDI (source 36)"),
    (0xfc04801d, "INTC0_CIMR", ""),
    (0xfc048040, "INTC0_ICR00", "ICRn at +0x40+n"),
    (0xfc04c000, "INTC1", "vectors 128 + source (KERNEL.md)"),
    (0xfc04c010, "INTC1_INTFRCH", "bit 11 = source 43, the reschedule"),
    (0xfc04c01d, "INTC1_CIMR", ""),
    (0xfc04c040, "INTC1_ICR00", "ICRn at +0x40+n"),
    (0xfc058000, "I2C", ""),
    (0xfc05c000, "DSPI", "the clock is on SPI (SAMPLE_SAVE.md)"),
    (0xfc060000, "UART0", "MIDI IN (MIDI.md)"),
    (0xfc060004, "UART0_USR", ""),
    (0xfc06000c, "UART0_RB", ""),
    (0xfc064000, "UART1", "the panel link, 312,500 baud (PANEL.md)"),
    (0xfc064004, "UART1_USR", ""),
    (0xfc06400c, "UART1_RB", ""),
    (0xfc068000, "UART2", "serial block, RX only (KERNEL.md)"),
    (0xfc068004, "UART2_USR", ""),
    (0xfc06800c, "UART2_RB", ""),
    (0xfc070000, "DTIM0", ""),
    (0xfc07000c, "DTIM0_DTCN", "latched per MIDI clock 0xF8 (MIDI.md)"),
    (0xfc074000, "DTIM1", ""),
    (0xfc078000, "DTIM2", ""),
    (0xfc07c000, "DTIM3", ""),
    (0xfc080000, "PIT0", "the 5 ms time-slice (KERNEL.md)"),
    (0xfc080002, "PIT0_PMR", ""),
    (0xfc084000, "PIT1", "the storage layer's delay timer"),
    (0xfc084002, "PIT1_PMR", ""),
    (0xfc0a4000, "GPIO", ""),
    (0xfc0a400c, "GPIO_DSP_CORE_SELECT", "0 = core 0 (payload A), 1 = core 1 (payload B): picks the HI08 the host window drives"),
    (0xfc0b0000, "USB_OTG", "USB device controller"),
    (0xfc0c4000, "PLL_PCR", "(reg >> 24) * 12 MHz must be 264 MHz or the boot halts (CHIP.md)"),
    (0x20000000, "HI08_ICR", "DSP host port, one register per 4 bytes (0x81 = INIT|RREQ at boot)"),
    (0x20000004, "HI08_CVR", ""),
    (0x20000008, "HI08_ISR", ""),
    (0x2000000c, "HI08_IVR", ""),
    (0x20000014, "HI08_TXH", "data bits 23-16"),
    (0x20000018, "HI08_TXM", "data bits 15-8"),
    (0x2000001c, "HI08_TXL", "data bits 7-0"),
    (0x90000000, "ATA_TASKFILE", "CompactFlash task file via FlexBus"),
]

# Routines the docs name. (address, name, comment)
CF_FUNCS = [
    (0x40000400, "start", "image entry: sets SP 0x48000000, checks the PLL"),
    (0x40000550, "isr_pit0_timeslice", "vector 0xab, INTC1 43 (KERNEL.md)"),
    (0x40001b18, "dsp_upload_payload", "walks a self-describing payload (DSP.md 2)"),
    (0x40001d4c, "dsp_upload_bootstrap", "(blob, bytes, P address) through the boot ROM"),
    (0x40001e50, "dsp_boot", "boots both cores (DSP.md 1)"),
    (0x400031a0, "stock_delay_frame", "the stock DELAY's frame routine (COLDFIRE_DELAY.md)"),
    (0x40005178, "voice_command", "emits a voice command (ARCHITECTURE.md 6)"),
    (0x40005540, "task_midi_mailbox", "task entry, prio 6: MIDI / voice mailbox (KERNEL.md Tasks)"),
    (0x4000aad0, "isr_dsp_frame", "vector 0x41, INTC0 1, level 5"),
    (0x400106ec, "isr_uart0_midi_rx", "vector 0x5a, INTC0 26 (MIDI.md)"),
    (0x400109bc, "isr_uart1_panel", "vector 0x5b, INTC0 27"),
    (0x40010b88, "isr_uart2_rx", "vector 0x5c, INTC0 28"),
    (0x40010efc, "uart1_init", "312,500 baud"),
    (0x40015304, "isr_ata", "vector 0xb6, INTC1 54: one sector per interrupt"),
    (0x400160f8, "ata_init", ""),
    (0x4001c244, "isr_intc1_49", "vector 0xb1: counter + ack of 0xfc0bc008"),
    (0x4001e594, "isr_intc1_47", "vector 0xaf"),
    (0x4001ee30, "task_storage", "task entry, prio 5: FAT/ATA (KERNEL.md Tasks)"),
    (0x4001f834, "task_main", "task entry, prio 0: runs the init list, then spins at main_idle (KERNEL.md Tasks)"),
    (0x4001fc9c, "main_idle", "main's `bras .` after the init list (KERNEL.md Tasks)"),
    (0x4001fca0, "isr_halt", "vector 0x47: SR 0x2700, bras ."),
    (0x40020c7c, "storage_delay", "waits on PIT1"),
    (0x40020d38, "isr_pit1_storage", "vector 0xac, INTC1 44"),
    (0x400409f4, "isr_intc0_34", "vector 0x62"),
    (0x4005593c, "task_key_repeat", "task entry, prio 4: key-repeat timer (KERNEL.md Tasks)"),
    (0x40055cb8, "isr_intc0_33", "vector 0x61"),
    (0x40056c40, "task_ui", "task entry, prio 3: queue_receive(UI_QUEUE) (KERNEL.md Tasks)"),
    (0x40061a94, "task_sys_init", "task entry, prio 1: serial + SPI start-up, then creates storage, UI, p3 (KERNEL.md Tasks)"),
    (0x4008445c, "task_engine", "task entry, prio 1: the 46-opcode dispatcher (KERNEL.md Tasks)"),
    (0x4009203c, "task_machine_params", "task entry, prio 2: machine parameters (KERNEL.md Tasks)"),
    (0x4009228c, "isr_intc0_37", "vector 0x65"),
    (0x40092bf4, "isr_midi_framer", "vector 0x64, INTC0 36 (MIDI.md)"),
    (0x40097168, "machine_state", "the track's machine state, 0-4"),
    (0x400977cc, "trig_to_voice", "dispatched by machine type"),
    (0x400a1e0c, "isr_seq_tick", "vector 0x60, INTC0 32: the forced sequencer tick"),
]

# Data the docs name. (address, name, bytes or 0, comment)
CF_DATA = [
    (0x400d5f58, "fx1_descriptors", 0, "FX1 descriptor pointers by effect id"),
    (0x400d5fdc, "fx2_descriptors", 0, "FX2 descriptor pointers by effect id"),
    (0x400d6060, "fx1_chooser_list", 0, "CHIP.md 0"),
    (0x400d6090, "fx2_chooser_list", 0, ""),
    (0x80004000, "ts_hann_table", 0, "timestretch crossfade, 512 entries (DSP.md 3)"),
]


def module_names():
    """{address: [(name, source file, comment)]} for every `.set`/`.equ` a
    ColdFire module gives a stock address. Values that land in flash are
    offsets, not addresses, and are skipped."""
    rx = re.compile(r"^\s*\.(?:set|equ)\s+([A-Za-z_]\w*)\s*,\s*(0x[0-9a-fA-F]+)\s*(?:\|\s*(.*))?$")
    out = {}
    files = sorted(ROOT.glob("modules/*/*.s")) + sorted(ROOT.glob("modules/*/*.S")) + [ROOT / "tools/remix/loader.S"]
    for f in files:
        if not f.exists():
            continue
        for line in f.read_text(errors="replace").splitlines():
            m = rx.match(line)
            if not m:
                continue
            a = int(m.group(2), 16)
            if a < 0x10000000:
                continue
            out.setdefault(a, [])
            if m.group(1) not in [n for n, _, _ in out[a]]:
                out[a].append((m.group(1), str(f.relative_to(ROOT)), (m.group(3) or "").strip()))
    return out


def dram_runtimes(built, stock_len):
    """[(run address, bytes, blob address, blob length)]: every GKA3 payload
    the build appends after the OS, unpacked.

    The loader's table (tools/remix/platform_build.py) holds, per payload,
    (blob, len, phash, stage, dst, rawlen, rhash, backup); a blob is found
    by its GKA3 stream and its entry by the pointer to it."""
    import depack
    app, out = built[stock_len:], []
    for m in re.finditer(b"GKA3", app):
        g, at = m.start(), BASE + stock_len + m.start()
        # The table entry pointing at this blob (signature + stream, or the
        # stream itself); the loader's own `cmpi.l #'GKA3'` has none.
        entries = []
        for start in (g - 4, g):
            ptr = (BASE + stock_len + start).to_bytes(4, "big")
            i = app.find(ptr)
            while 0 <= i <= len(app) - 32:
                entries.append([int.from_bytes(app[i + 4 * k:i + 4 * k + 4], "big") for k in range(8)])
                i = app.find(ptr, i + 1)
        if not entries:
            log(f"GKA3 at 0x{at:08x}: nothing points at it; not a payload")
            continue
        try:
            raw = depack.depack(app[g:])
        except (ValueError, IndexError) as e:
            print(f"[ghidra] warning: the payload at 0x{at:08x} does not unpack ({e})")
            continue
        entry = next((e for e in entries if e[5] == len(raw)), None)
        if entry is None:
            print(f"[ghidra] warning: no loader table entry for the payload at 0x{at:08x} ({len(raw)} bytes unpacked)")
            continue
        run = entry[4] - UNCACHED_ALIAS if entry[4] >= BASE + UNCACHED_ALIAS else entry[4]
        log(f"DRAM runtime: {len(raw)} bytes to 0x{run:08x}")
        out.append((run, raw, entry[0], entry[1]))
    return out


def cf_layout(img, prog="MAIN_OS", stock_len=None, dram=()):
    """MAIN_OS's layout; for a built image, `stock_len` is where the build's
    appended bytes start and `dram` is [(run address, length, file, blob
    address, blob length)]."""
    end = BASE + len(img)
    what = "image" if stock_len is None else "built image"
    lines = [f"# {prog}: ColdFire MCF54454, {what} {len(img):,} bytes at 0x{BASE:08x}",
             f"rename ram:0x{BASE:08x} OS_IMAGE rwx"]
    for name, start, ln, fl in CF_BLOCKS:
        if name != "SDRAM":
            lines.append(f"block {name} ram:0x{start:08x} 0x{ln:x} {fl}")
            continue
        # Image end .. SDRAM end, less the runtimes the loader unpacks there.
        at = end
        for i, (run, n, f, _blob, _bn) in enumerate(sorted(dram)):
            if run < at or run + n > SDRAM_END:
                sys.exit(f"{prog}: runtime {i} at 0x{run:08x} (+0x{n:x}) is not in free SDRAM above the image")
            if run > at:
                lines.append(f"block SDRAM_{i} ram:0x{at:08x} 0x{run - at:x} {fl}")
            lines += [f"file DRAM_RUNTIME_{i} ram:0x{run:08x} {f} rwx",
                      f"label ram:0x{run:08x} dram_runtime_{i}",
                      f"comment ram:0x{run:08x} plate DRAM runtime {i}: {n:,} bytes the loader unpacks here at boot"]
            at = run + n
        lines.append(f"block SDRAM ram:0x{at:08x} 0x{SDRAM_END - at:x} {fl}")
    if stock_len is not None and stock_len < len(img):
        # The loader is code (the boot detour lands in it); the packed blobs
        # are data to it.
        a = BASE + stock_len
        lines += [f"label ram:0x{a:08x} build_appended",
                  f"comment ram:0x{a:08x} plate appended by the build: {len(img) - stock_len:,} bytes "
                  f"(the loader, its table and the packed runtimes, tools/remix/platform_build.py)"]
        for i, (run, n, f, blob, bn) in enumerate(sorted(dram)):
            lines += [f"label ram:0x{blob:08x} dram_runtime_{i}_packed", f"data ram:0x{blob:08x} byte {bn}",
                      f"comment ram:0x{blob:08x} plate DRAM runtime {i}, packed: unpacked to 0x{run:08x} (DRAM_RUNTIME_{i})"]
    # Not byte-mapped onto SDRAM: analysis follows flow into a mapped copy and
    # disassembles the image twice (measured: 168K of 359K instructions).
    lines += [f"block SDRAM_UNCACHED ram:0x{UNCACHED:08x} 0x8000000 rw",
              f"comment ram:0x{UNCACHED:08x} plate SDRAM_UNCACHED: the same 128 MB as 0x40000000, uncached"]
    lines.append(f"entry ram:0x{BASE:08x}")
    for a, n, c in CF_IO:
        lines.append(f"label ram:0x{a:08x} {n}")
        if c:
            lines.append(f"comment ram:0x{a:08x} eol {c}")
    for a, n, c in CF_FUNCS:
        lines.append(f"func ram:0x{a:08x} {n}")
        if c:
            lines.append(f"comment ram:0x{a:08x} plate {n}: {c}")
    for a, n, sz, c in CF_DATA:
        lines.append(f"label ram:0x{a:08x} {n}")
        if c:
            lines.append(f"comment ram:0x{a:08x} plate {n}: {c}")
    # The DSP blobs are data to the ColdFire: keep the disassembler out of them.
    for tag, va, ln, dsp in dm.BOOTSTRAPS:
        lines += [f"label ram:0x{va:08x} dsp_bootstrap_{tag}", f"data ram:0x{va:08x} byte {ln}",
                  f"comment ram:0x{va:08x} plate DSP bootstrap {tag}: {ln // 3} words to P:0x{dsp:05x} (program DSP_{tag})"]
    for tag, va, ln in dm.PAYLOADS:
        lines += [f"label ram:0x{va:08x} dsp_payload_{tag}", f"data ram:0x{va:08x} byte {ln}",
                  f"comment ram:0x{va:08x} plate DSP payload {tag}: {ln:,} bytes of load records (program DSP_{tag}, DSP.md 2)"]
    named = {a for a, *_ in CF_IO + CF_FUNCS + CF_DATA}
    n = 0
    for a, names in sorted(module_names().items()):
        for name, src, c in names:
            lines.append(f"label ram:0x{a:08x} {name}")
            n += 1
        if a not in named:
            srcs = ", ".join(sorted({f"{nm} ({s})" for nm, s, _ in names}))
            lines.append(f"comment ram:0x{a:08x} repeatable named by {srcs}")
    log(f"{prog}: {n} module names")
    return lines


# ----------------------------------------------------------------------- DSP --

# The default memory map, which stock runs (CHIP.md section 3, Fig 3-2): internal
# P/X/Y words per core, and the shared window.
INTERNAL = {"P": 0x2000, "X": 0x9000, "Y": 0xc000}
SHARED, SHARED_LEN = 0x30000, 0x10000
IO = 0xffff80

# Both dispatch tables are one X record per payload (DSP.md 5; tools/build/dsp_reach.py).
XTAB = {"A": 0x400e2345, "B": 0x400f5a10}

# Effect ids (DSP.md 5). Every other id is the null stub.
EFFECTS = {0x04: "FILTER", 0x05: "SPATIALIZER", 0x0c: "EQUALIZER", 0x0d: "DJ_EQ", 0x10: "PHASER",
           0x11: "FLANGER", 0x12: "CHORUS", 0x13: "COMB", 0x14: "PLATE_REV", 0x15: "SPRING_REV",
           0x16: "DARK_REV", 0x18: "COMPRESSOR", 0x1c: "LO_FI"}

# Payload A's routines the docs name (DSP.md 3). Payload B's addresses differ.
DSP_A_NAMES = [
    ("func", 0x002bf, "mix_summing", "summing mixdown (module 0x2bf)"),
    ("func", 0x003a1, "voice_playback", "2-tap linear interpolator over a 128-word ring, pitch only"),
    ("label", 0x0041e, "fx_dispatch_module", "the only effect dispatch: six jsr (r2) sites (DSP.md 5)"),
    ("func", 0x0055a, "host_pack", "24-bit <-> dual-16-bit host packer"),
    ("label", 0x0058c, "selfmod_58c", "rewritten at run time: frame setup writes move x0,p:>$58c"),
    ("label", 0x0059b, "selfmod_59b", "rewritten at run time: frame setup writes p:>$59b"),
    ("label", 0x006e5, "scratch_one_word_records", "15 one-word P records, all zero: scratch, not a table"),
]

# X/Y I/O registers, as vendor/dsp56300's dsp56kDisassemble names them (so the
# listing reads like the docs). Those are the DSP56362's; the DSP56720 is not
# modelled there, and the docs' reading of the ESAI and host-port setup
# (DSP.md 6c) is what vouches for them on this chip.
DSP_IO = {
    "X": {
        0xffffff: "M_IPRC", 0xfffffe: "M_IPRP", 0xfffffd: "M_PCTL", 0xfffffc: "M_OGDB",
        0xfffffb: "M_BCR", 0xfffffa: "M_DCR", 0xfffff9: "M_AAR0", 0xfffff8: "M_AAR1",
        0xfffff7: "M_AAR2", 0xfffff6: "M_AAR3", 0xfffff5: "M_IDR", 0xfffff4: "M_DSTR",
        0xfffff3: "M_DOR0", 0xfffff2: "M_DOR1", 0xfffff1: "M_DOR2", 0xfffff0: "M_DOR3",
        0xffffef: "M_DSR0", 0xffffee: "M_DDR0", 0xffffed: "M_DCO0", 0xffffec: "M_DCR0",
        0xffffeb: "M_DSR1", 0xffffea: "M_DDR1", 0xffffe9: "M_DCO1", 0xffffe8: "M_DCR1",
        0xffffe7: "M_DSR2", 0xffffe6: "M_DDR2", 0xffffe5: "M_DCO2", 0xffffe4: "M_DCR2",
        0xffffe3: "M_DSR3", 0xffffe2: "M_DDR3", 0xffffe1: "M_DCO3", 0xffffe0: "M_DCR3",
        0xffffdf: "M_DSR4", 0xffffde: "M_DDR4", 0xffffdd: "M_DCO4", 0xffffdc: "M_DCR4",
        0xffffdb: "M_DSR5", 0xffffda: "M_DDR5", 0xffffd9: "M_DCO5", 0xffffd8: "M_DCR5",
        0xffffd7: "M_PCRD", 0xffffd6: "M_PRRD", 0xffffd5: "M_PDRD", 0xffffd4: "M_XSTR",
        0xffffd3: "M_XADRB", 0xffffd2: "M_XADRA", 0xffffd1: "M_XNADR",
        0xffffd0: "M_XCTR", 0xffffc9: "M_HDR", 0xffffc8: "M_HDDR", 0xffffc7: "M_HOTX",
        0xffffc6: "M_HORX", 0xffffc5: "M_HBAR", 0xffffc4: "M_HPCR", 0xffffc3: "M_HSR",
        0xffffc2: "M_HCR", 0xffffbf: "M_PCRC", 0xffffbe: "M_PRRC", 0xffffbd: "M_PDRC",
        0xffffbc: "M_RSMB", 0xffffbb: "M_RSMA", 0xffffba: "M_TSMB", 0xffffb9: "M_TSMA",
        0xffffb8: "M_RCCR", 0xffffb7: "M_RCR", 0xffffb6: "M_TCCR", 0xffffb5: "M_TCR",
        0xffffb4: "M_SAICR", 0xffffb3: "M_SAISR", 0xffffab: "M_RX3", 0xffffaa: "M_RX2",
        0xffffa9: "M_RX1", 0xffffa8: "M_RX0", 0xffffa6: "M_TSR", 0xffffa5: "M_TX5",
        0xffffa4: "M_TX4", 0xffffa3: "M_TX3", 0xffffa2: "M_TX2", 0xffffa1: "M_TX1",
        0xffffa0: "M_TX0", 0xffff94: "M_HRX", 0xffff93: "M_HTX", 0xffff92: "M_HSAR",
        0xffff91: "M_HCSR", 0xffff90: "M_HCKR", 0xffff8f: "M_TCSR0", 0xffff8e: "M_TLR0",
        0xffff8d: "M_TCPR0", 0xffff8c: "M_TCR0", 0xffff8b: "M_TCSR1",
        0xffff8a: "M_TLR1", 0xffff89: "M_TCPR1", 0xffff88: "M_TCR1",
        0xffff87: "M_TCSR2", 0xffff86: "M_TLR2", 0xffff85: "M_TCPR2",
        0xffff84: "M_TCR2", 0xffff83: "M_TPLR", 0xffff82: "M_TPCR",
    },
    "Y": {
        0xffff9c: "M_RSMB_1", 0xffff9b: "M_RSMA_1", 0xffff9a: "M_TSMB_1",
        0xffff99: "M_TSMA_1", 0xffff98: "M_RCCR_1", 0xffff97: "M_RCR_1",
        0xffff96: "M_TCCR_1", 0xffff95: "M_TCR_1", 0xffff94: "M_SAICR_1",
        0xffff93: "M_SAISR_1", 0xffff8b: "M_RX3_1", 0xffff8a: "M_RX2_1",
        0xffff89: "M_RX1_1", 0xffff88: "M_RX0_1", 0xffff86: "M_TSR_1",
        0xffff85: "M_TX5_1", 0xffff84: "M_TX4_1", 0xffff83: "M_TX3_1",
        0xffff82: "M_TX2_1", 0xffff81: "M_TX1_1", 0xffff80: "M_TX0_1",
    },
}


def payload(img, tag):
    """(records, entry): records are (space, addr, [words], image address)."""
    va, ln = [(va, ln) for t, va, ln in dm.PAYLOADS if t == tag][0]
    mods, b = dm.modules(img, va, ln)
    if not mods:
        sys.exit(f"payload {tag}: no load records parse; is {IMG} OS 1.40C?")
    recs = []
    for sp, addr, cnt, data in mods:
        if sp not in (0, 1, 2):
            sys.exit(f"payload {tag}: record in space {sp} at +0x{data:x}")
        recs.append(("PXY"[sp], addr, [dm.w24(b, data + 3 * i) for i in range(cnt)], va + data))
    end = mods[-1][3] + mods[-1][2] * 3
    term, entry = dm.w24(b, end), dm.w24(b, end + 3)
    if term <= 2:                         # 3 ends the stream; the next word is the entry
        sys.exit(f"payload {tag}: no terminator after the last record (0x{term:06x})")
    return recs, entry


def dsp_images(img):
    """Per-core P/X/Y word arrays and the shared window, as uploaded."""
    shared = [0] * SHARED_LEN
    owner = {}
    for tag, va, ln, dsp in dm.BOOTSTRAPS:
        for i in range(ln // 3):
            shared[dsp - SHARED + i] = dm.w24(img, va - BASE + 3 * i)
            owner[dsp + i] = f"bootstrap {tag}"
    cores = {}
    for tag in ("A", "B"):
        recs, entry = payload(img, tag)
        mem = {sp: [0] * n for sp, n in INTERNAL.items()}
        for sp, addr, words, _ in recs:
            for i, w in enumerate(words):
                a = addr + i
                if SHARED <= a < SHARED + SHARED_LEN:
                    if a in owner and shared[a - SHARED] != w:
                        print(f"[ghidra] warning: payload {tag} {sp}:0x{a:05x} overwrites {owner[a]}", file=sys.stderr)
                    shared[a - SHARED] = w
                    owner[a] = f"payload {tag}"
                elif a < INTERNAL[sp]:
                    mem[sp][a] = w
                else:
                    sys.exit(f"payload {tag}: {sp}:0x{a:05x} is outside the default memory map")
        cores[tag] = (mem, recs, entry)
        log(f"payload {tag}: {len(recs)} records, entry P:0x{entry:05x}")
    return cores, shared


def words_bytes(words):
    return b"".join(bytes((w & 0xff, (w >> 8) & 0xff, (w >> 16) & 0xff)) for w in words)


def dsp_layout(tag, mem, recs, entry, other_entry):
    lines = [f"# DSP_{tag}: payload {tag}, {len(recs)} load records",
             "rename P:0x0 P_INTERNAL rwx",
             f"file X_INTERNAL X:0x0 DSP_{tag}.X.bin rw",
             f"file Y_INTERNAL Y:0x0 DSP_{tag}.Y.bin rw",
             f"file P_SHARED P:0x{SHARED:x} SHARED.bin rwx",
             f"alias X_SHARED X:0x{SHARED:x} P:0x{SHARED:x} 0x{SHARED_LEN:x} rw",
             f"alias Y_SHARED Y:0x{SHARED:x} P:0x{SHARED:x} 0x{SHARED_LEN:x} rw",
             f"block X_IO X:0x{IO:x} 0x80 rwv",
             f"block Y_IO Y:0x{IO:x} 0x80 rwv"]
    for sp, regs in DSP_IO.items():
        for a, n in sorted(regs.items()):
            lines.append(f"label {sp}:0x{a:x} {n}")
    # Where each load record landed, for reading the listing against dsp_modmap.
    for sp, addr, words, va in recs:
        lines.append(f"comment {sp}:0x{addr:x} pre load record: {len(words)} words from 0x{va:08x}")
    # Vectors: two words per slot, P:0x00-0x3f is the vector module.
    for v in range(0, 0x40, 2):
        if mem["P"][v] or mem["P"][v + 1]:
            lines += [f"code P:0x{v:x} vec_{v:02x}", f"entry P:0x{v:x}"]
    for t, va, ln, dsp in dm.BOOTSTRAPS:
        lines += [f"func P:0x{dsp:x} bootstrap_{t}",
                  f"comment P:0x{dsp:x} plate bootstrap {t}: uploaded by the ColdFire through the boot ROM"]
    lines += [f"func P:0x{entry:x} payload_{tag}_entry", f"entry P:0x{entry:x}",
              f"comment P:0x{entry:x} plate payload {tag}'s entry word (after the terminator record)"]
    if other_entry is not None:
        lines += [f"func P:0x{other_entry:x} payload_B_entry",
                  f"comment P:0x{other_entry:x} plate payload B's entry, written by payload A: the window is one memory"]
    # The dispatch tables.
    xt = [(addr + (XTAB[tag] - va) // 3) for sp, addr, words, va in recs
          if sp == "X" and va <= XTAB[tag] < va + 3 * len(words) and (XTAB[tag] - va) % 3 == 0]
    if len(xt) != 1:
        sys.exit(f"payload {tag}: dispatch tables not found at 0x{XTAB[tag]:08x}")
    init, proc = xt[0], xt[0] + 32
    lines += [f"label X:0x{init:x} fx_init_table", f"data X:0x{init:x} uint3 32",
              f"comment X:0x{init:x} plate INIT_TABLE[effect id]: called when a slot's id changes (DSP.md 5)",
              f"label X:0x{proc:x} fx_process_table", f"data X:0x{proc:x} uint3 32",
              f"comment X:0x{proc:x} plate PROCESS_TABLE[effect id]: called every frame"]
    ids = {}
    for i in range(32):
        for base, kind in ((init, "init"), (proc, "process")):
            tgt = mem["X"][base + i]
            ids.setdefault((tgt, kind), []).append(i)
            lines.append(f"ref X:0x{base + i:x} P:0x{tgt:x}")
    for (tgt, kind), idl in sorted(ids.items()):
        named = [EFFECTS[i].lower() for i in idl if i in EFFECTS]
        if named:
            name = f"fx_{'_'.join(named)}_{kind}"
        elif len(idl) > 1:
            name = f"fx_null_{kind}"          # the passthrough every unused id points at
        else:
            name = f"fx_id{idl[0]:02x}_{kind}"
        lines += [f"func P:0x{tgt:x} {name}",
                  f"comment P:0x{tgt:x} plate {name}: effect id {', '.join(f'0x{i:02x}' for i in idl)}"]
    if tag == "A":
        for kind, a, n, c in DSP_A_NAMES:
            lines += [f"{kind} P:0x{a:x} {n}", f"comment P:0x{a:x} {'plate' if kind == 'func' else 'eol'} {c}"]
    return lines


# ------------------------------------------------------------------ commands --

def cmd_layout(args):
    if not IMG.exists():
        sys.exit(f"missing {IMG}: run `make os && make recon` first")
    img = IMG.read_bytes()
    load = OUT / "load"
    load.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(IMG, load / "MAIN_OS")
    (load / "MAIN_OS.layout").write_text("\n".join(cf_layout(img)) + "\n")
    progs = ["MAIN_OS", "DSP_A", "DSP_B"]
    if getattr(args, "image", None):
        image = pathlib.Path(args.image).expanduser()
        if not image.exists():
            sys.exit(f"no built image at {image}: run `make bus REMIX=<name>` first")
        built = image.read_bytes()
        if len(built) < len(img):
            sys.exit(f"{image} is shorter than the stock image: not a build of this OS")
        dram = []
        for i, (run, raw, blob, bn) in enumerate(dram_runtimes(built, len(img))):
            (load / f"REMIX.dram{i}").write_bytes(raw)
            dram.append((run, len(raw), f"REMIX.dram{i}", blob, bn))
        shutil.copyfile(image, load / "REMIX")
        (load / "REMIX.layout").write_text("\n".join(cf_layout(built, "REMIX", len(img), dram)) + "\n")
        progs.append(f"REMIX ({image.name}, {len(dram)} DRAM runtimes)")
    cores, shared = dsp_images(img)
    (load / "SHARED.bin").write_bytes(words_bytes(shared))
    for tag, (mem, recs, entry) in cores.items():
        (load / f"DSP_{tag}").write_bytes(words_bytes(mem["P"]))
        (load / f"DSP_{tag}.X.bin").write_bytes(words_bytes(mem["X"]))
        (load / f"DSP_{tag}.Y.bin").write_bytes(words_bytes(mem["Y"]))
        other = cores["B"][2] if tag == "A" else None
        (load / f"DSP_{tag}.layout").write_text("\n".join(dsp_layout(tag, mem, recs, entry, other)) + "\n")
    print(f"layout: {', '.join(progs)} -> {load.relative_to(ROOT) if load.is_relative_to(ROOT) else load}")


def find_ghidra(arg):
    g = arg or os.environ.get("GHIDRA_INSTALL_DIR")
    if not g:
        sys.exit("no Ghidra: pass --ghidra <install dir> (or GHIDRA=... to make, or set GHIDRA_INSTALL_DIR)")
    g = pathlib.Path(g).expanduser().resolve()
    head = g / "support/analyzeHeadless"
    if not head.exists():
        sys.exit(f"{head} not found: --ghidra is the directory holding ghidraRun")
    return g, head


def languages(g):
    """(ColdFire language id, DSP language id or None) this install offers."""
    ldefs = g / "Ghidra/Processors/68000/data/languages/68000.ldefs"
    cf = "68000:BE:32:Coldfire"
    if ldefs.exists() and "Coldfire_EMAC_frac" in ldefs.read_text():
        cf = "68000:BE:32:Coldfire_EMAC_frac"
    dsp = "DSP56300:LE:24:default" if (g / "Ghidra/Processors/DSP56300").is_dir() else None
    return cf, dsp


def cmd_import(args):
    g, head = find_ghidra(args.ghidra)
    cf, dsp = languages(g)
    cmd_layout(args)
    proj = pathlib.Path(args.project).expanduser().resolve() if args.project else OUT
    # Ghidra refuses a project path with an element starting with '.'
    # ("Path element starting with '.' is not permitted"): a worktree under
    # .claude/, say. The default moves to the temp directory; --project must
    # name a legal one.
    if any(p.startswith(".") for p in proj.parts):
        if args.project:
            sys.exit(f"Ghidra will not open a project under a directory starting with '.': {proj}")
        proj = pathlib.Path(os.environ.get("TMPDIR", "/tmp")).resolve() / f"octabam-ghidra-{os.getuid()}"
        print(f"[ghidra] {OUT} is under a hidden directory; the project goes to {proj} (--project to choose)")
    proj.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else {"MAIN_OS", "DSP_A", "DSP_B", "REMIX"}
    load = OUT / "load"
    plan = [("MAIN_OS", cf, "0x40000400")]
    if args.image:
        plan.append(("REMIX", cf, "0x40000400"))
    if dsp:
        plan += [("DSP_A", dsp, "0x0"), ("DSP_B", dsp, "0x0")]
    else:
        print("[ghidra] this Ghidra has no DSP56300 processor: DSP_A and DSP_B skipped (tools/ghidra/README.md)")
    if cf.endswith(":Coldfire"):
        print("[ghidra] no ColdFire EMAC fractional variant here: MAIN_OS uses 68000:BE:32:Coldfire (tools/ghidra/README.md)")
    failed = []
    for name, lang, base in plan:
        if name not in only:
            continue
        logf = OUT / f"{name}.log"
        cmd = [str(head), str(proj), args.name, "-import", str(load / name), "-overwrite",
               "-processor", lang, "-loader", "BinaryLoader", "-loader-baseAddr", base,
               "-scriptPath", str(HERE), "-preScript", "OtLayout.java", str(load / f"{name}.layout")]
        if args.no_analysis:
            cmd.append("-noanalysis")
        else:
            cmd += ["-postScript", "OtReport.java"]
        print(f"[ghidra] {name} ({lang}) ...", flush=True)
        log(" ".join(cmd))
        with open(logf, "w") as fh:
            if DEBUG:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in p.stdout:
                    sys.stderr.write(line)
                    fh.write(line)
                rc = p.wait()
            else:
                rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT).returncode
        text = logf.read_text(errors="replace")
        rx = re.compile(r"(Ot(?:Layout|Report): .*?)(?:\s+\(GhidraScript\))?\s*$")
        summary = [m.group(1) for m in map(rx.search, text.splitlines()) if m]
        for s in summary:
            print(f"    {s}")
        if rc != 0 or "REPORT: Import succeeded" not in text or not any("OtLayout:" in s for s in summary):
            failed.append(name)
            print(f"    FAILED (exit {rc}); the log is {logf}")
            for ln in [ln for ln in text.splitlines() if "ERROR" in ln or "Exception" in ln][:10]:
                print(f"    {ln.strip()}")
    print(f"[ghidra] project {proj / args.name}.gpr")
    if failed:
        sys.exit(f"failed: {', '.join(failed)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    img_help = f"also a built image as program REMIX (default {ROOT / 'out/mainos_bus.bin'})"
    lo = sub.add_parser("layout", help="write out/ghidra/load/ (memory images + layouts); no Ghidra needed")
    lo.add_argument("--image", nargs="?", const=str(ROOT / "out/mainos_bus.bin"), help=img_help)
    im = sub.add_parser("import", help="layout, then import and analyse every program headless")
    im.add_argument("--ghidra", help="Ghidra install directory (default $GHIDRA_INSTALL_DIR)")
    im.add_argument("--project", help="project directory (default out/ghidra)")
    im.add_argument("--name", default="octatrack", help="project name (default octatrack)")
    im.add_argument("--only", help="comma-separated subset of MAIN_OS,DSP_A,DSP_B,REMIX")
    im.add_argument("--image", nargs="?", const=str(ROOT / "out/mainos_bus.bin"), help=img_help)
    im.add_argument("--no-analysis", action="store_true", help="import and lay out only; analyse later in the GUI")
    args = ap.parse_args()
    {"layout": cmd_layout, "import": cmd_import}[args.cmd](args)


if __name__ == "__main__":
    main()
