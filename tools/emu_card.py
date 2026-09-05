#!/usr/bin/env python3
"""CompactFlash card emulation for the ColdFire emulator (docs/EMU.md, M4).

Three pieces:

  1. A pure-Python FAT16 image builder (`build_image`) that turns a directory
     tree — a SET folder holding a PROJECT folder — into an MBR + FAT16 card
     image the firmware's own mount code accepts (`0x400168e8`: MBR signature,
     partition type 4/6/0x0e, 512-byte sectors; `0x40017ad4`: BPB, FAT size
     <= 16384 sectors). Long names are written as VFAT LFN entries.
  2. An ATA task-file model (`AtaCard`) mapped at the FlexBus window
     0x90000000 (data 0xa0, features/error 0xa4, count 0xa8, LBA 0xac/b0/b4,
     device 0xb8, command/status 0xbc, alt status 0xd8 — docs/ARCHITECTURE.md
     §5). IDENTIFY advertises PIO only, so the driver's variant detection
     (`0x40015e28`) never programs the on-chip DMA channel.
  3. The detour past the RTOS. The PIO handlers (`0x40014b94` READ, `0x40014c48`
     WRITE, `0x400159bc` IDENTIFY) only program the registers; the DATA PHASE is
     the ATA interrupt handler at `0x40015304`, which streams 256 words per
     sector and then signals an RTOS event the queue primitive `0x4001568c`
     is blocked on (`0x40000818`). We never take the interrupt: `attach()`
     hooks `0x40000818`, and when a command is in flight (`0x46c8c58a`) it
     performs the transfer the handler would have — same bookkeeping words
     (`0x46c8c592` count, `0x46c8c594` buffer, `0x46c8c593` command,
     `0x460bac18` IDENTIFY buffer, `0x460bae18` lock) — and returns as if the
     event had fired. Everything else in the storage stack then runs
     unmodified, cold, exactly like the FX-page detours.

Run:  .venv/bin/python3 tools/emu_card.py --project <dir> [--set NAME]
      (builds out/emu_card.img, boots the raw image, attaches, runs card init)
"""
import argparse
import os
import pathlib
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emu_bringup as eb  # noqa: E402

SECTOR = 512

# ---------------------------------------------------------------------------
# FAT16 image builder
# ---------------------------------------------------------------------------

_SKIP = {".DS_Store"}


def _short_name(name, used):
    """8.3 name for `name` (upper-cased, invalid chars -> '_'); returns
    (basis11, needs_lfn)."""
    stem, _, ext = name.rpartition(".") if "." in name else (name, "", "")
    if not stem:                      # ".foo"
        stem, ext = ext, ""
    def clean(s):
        out = ""
        for c in s.upper():
            out += c if (c.isalnum() or c in "$%'-_@~`!(){}^#&") else "_"
        return out
    cs, ce = clean(stem).replace(" ", ""), clean(ext).replace(" ", "")[:3]
    lossy = (cs != stem or ce != ext or len(cs) > 8 or " " in name
             or name != name.upper() and name != name.lower() or
             name != (stem + ("." + ext if ext else "")))
    if len(cs) <= 8 and not lossy and stem == stem.upper() and ext == ext.upper():
        basis = cs.ljust(8) + ce.ljust(3)
        if basis not in used:
            used.add(basis)
            return basis, False
    # generate a ~N tail
    for n in range(1, 10000):
        tail = f"~{n}"
        b = (cs[:8 - len(tail)] + tail).ljust(8) + ce.ljust(3)
        if b not in used:
            used.add(b)
            return b, True
    raise RuntimeError("too many name collisions")


def _lfn_checksum(basis11):
    s = 0
    for c in basis11.encode("ascii"):
        s = (((s & 1) << 7) | (s >> 1)) + c
        s &= 0xFF
    return s


def _lfn_entries(name, basis11):
    """VFAT long-name directory entries (reverse order, as stored)."""
    u = name.encode("utf-16-le")
    u += b"\x00\x00"
    while len(u) % 26:
        u += b"\xff\xff"
    chunks = [u[i:i + 26] for i in range(0, len(u), 26)]
    cs = _lfn_checksum(basis11)
    out = []
    for i, ch in enumerate(chunks):
        seq = i + 1 | (0x40 if i == len(chunks) - 1 else 0)
        e = bytes([seq]) + ch[0:10] + bytes([0x0F, 0, cs]) + ch[10:22] + b"\x00\x00" + ch[22:26]
        assert len(e) == 32
        out.append(e)
    return list(reversed(out))


def _dir_entry(basis11, attr, first_cluster, size):
    # constant timestamp: 2026-09-05 12:00:00
    t = (12 << 11) | (0 << 5) | 0
    d = ((2026 - 1980) << 9) | (9 << 5) | 5
    return (basis11.encode("ascii") + bytes([attr, 0, 0]) +
            struct.pack("<HHHHHHHI", t, d, d, (first_cluster >> 16) & 0xFFFF, t, d,
                        first_cluster & 0xFFFF, size))


class _Fat16:
    def __init__(self, total_sectors, sectors_per_cluster, part_start):
        self.spc = sectors_per_cluster
        self.cluster_bytes = SECTOR * self.spc
        self.reserved = 1
        self.nfats = 2
        self.root_entries = 512
        self.root_sectors = self.root_entries * 32 // SECTOR
        self.total = total_sectors
        # solve sectors per FAT
        data_est = self.total - self.reserved - self.root_sectors
        clusters = data_est // self.spc
        self.spf = (clusters + 2) * 2 + SECTOR - 1
        self.spf //= SECTOR
        self.data_start = self.reserved + self.nfats * self.spf + self.root_sectors
        self.nclusters = (self.total - self.data_start) // self.spc
        if not 4085 <= self.nclusters <= 65524:
            raise ValueError(f"{self.nclusters} clusters is not FAT16 (4085..65524); "
                             "change the image size or cluster size")
        if self.spf > 16384:
            raise ValueError("firmware refuses FAT larger than 16384 sectors")
        self.fat = [0] * (self.nclusters + 2)
        self.fat[0] = 0xFFF8
        self.fat[1] = 0xFFFF
        self.next_free = 2
        self.data = bytearray(self.nclusters * self.cluster_bytes)
        self.root = bytearray(self.root_sectors * SECTOR)
        self.part_start = part_start

    def alloc_chain(self, payload):
        n = max(1, (len(payload) + self.cluster_bytes - 1) // self.cluster_bytes)
        if self.next_free + n > self.nclusters + 2:
            raise ValueError("image full")
        first = self.next_free
        for i in range(n):
            c = first + i
            self.fat[c] = c + 1 if i < n - 1 else 0xFFFF
            off = (c - 2) * self.cluster_bytes
            self.data[off:off + self.cluster_bytes] = payload[i * self.cluster_bytes:(i + 1) * self.cluster_bytes].ljust(self.cluster_bytes, b"\x00")
        self.next_free += n
        return first

    def build_dir(self, path, parent_cluster, is_root, log):
        """Return (entries_bytes, first_cluster) for directory `path`."""
        entries = bytearray()
        used = set()
        names = sorted(p for p in os.listdir(path)
                       if p not in _SKIP and not p.startswith("._"))
        subdirs = []
        # a subdirectory's own cluster must exist before we can write '..'
        my_cluster = 0 if is_root else self.next_free
        if not is_root:
            entries += _dir_entry(".".ljust(11), 0x10, my_cluster, 0)
            entries += _dir_entry("..".ljust(11), 0x10, parent_cluster, 0)
        # reserve our cluster(s) later: size unknown until entries are counted
        placeholder = []
        for name in names:
            full = os.path.join(path, name)
            basis, lfn = _short_name(name, used)
            if os.path.isdir(full):
                placeholder.append((name, basis, lfn, None))
            else:
                data = pathlib.Path(full).read_bytes()
                first = self.alloc_chain(data) if data else 0
                if lfn:
                    for e in _lfn_entries(name, basis):
                        entries += e
                entries += _dir_entry(basis, 0x20, first, len(data))
                log.append((name, basis, first, len(data)))
        if not is_root:
            # allocate this directory now, so children see a valid parent cluster;
            # size the chain for the entries we will have (dirs add <= 20 each).
            est = len(entries) + sum(32 * 21 for _ in placeholder) + 32
            my_cluster = self.alloc_chain(b"\x00" * est)
            # fix '.' entry cluster (we guessed next_free; alloc_chain confirms it)
            entries[26:28] = struct.pack("<H", my_cluster & 0xFFFF)
        for name, basis, lfn, _ in placeholder:
            sub_entries, sub_first = self.build_dir(os.path.join(path, name), my_cluster, False, log)
            if lfn:
                for e in _lfn_entries(name, basis):
                    entries += e
            entries += _dir_entry(basis, 0x10, sub_first, 0)
            log.append((name + "/", basis, sub_first, 0))
        if is_root:
            if len(entries) > len(self.root):
                raise ValueError("too many root entries")
            self.root[:len(entries)] = entries
            return bytes(entries), 0
        off = (my_cluster - 2) * self.cluster_bytes
        cap = self.cluster_bytes * self._chain_len(my_cluster)
        if len(entries) > cap:
            raise ValueError(f"directory {path} overflowed its cluster reservation")
        self.data[off:off + len(entries)] = entries
        return bytes(entries), my_cluster

    def _chain_len(self, c):
        n = 0
        while c != 0xFFFF and c != 0 and n < 100000:
            n += 1
            c = self.fat[c]
        return n

    def volume(self, label):
        bpb = bytearray(SECTOR)
        bpb[0:3] = b"\xEB\x3C\x90"
        bpb[3:11] = b"MSWIN4.1"
        struct.pack_into("<HBHBHHBHHHII", bpb, 11, SECTOR, self.spc, self.reserved,
                         self.nfats, self.root_entries,
                         self.total if self.total < 0x10000 else 0, 0xF8, self.spf,
                         63, 255, self.part_start, self.total if self.total >= 0x10000 else 0)
        bpb[36] = 0x80
        bpb[38] = 0x29
        struct.pack_into("<I", bpb, 39, 0x0C7A0BA8)          # volume serial
        bpb[43:54] = label.upper().ljust(11)[:11].encode("ascii")
        bpb[54:62] = b"FAT16   "
        bpb[510:512] = b"\x55\xAA"
        fat = bytearray(self.spf * SECTOR)
        struct.pack_into(f"<{len(self.fat)}H", fat, 0, *self.fat)
        return bytes(bpb) + bytes(fat) * self.nfats + bytes(self.root) + bytes(self.data)


def build_image(tree_dir, size_mb=64, label="OCTABAM", part_start=2048, log=None):
    """MBR + one FAT16 partition holding the directory tree at `tree_dir`."""
    total = size_mb * 1024 * 1024 // SECTOR
    part_sectors = total - part_start
    spc = 4 if size_mb <= 128 else (8 if size_mb <= 256 else 16)
    fs = _Fat16(part_sectors, spc, part_start)
    log = log if log is not None else []
    fs.build_dir(tree_dir, 0, True, log)
    vol = fs.volume(label)
    mbr = bytearray(SECTOR)
    struct.pack_into("<BBBBBBBBII", mbr, 446, 0x00, 0xFE, 0xFF, 0xFF, 0x06, 0xFE, 0xFF, 0xFF,
                     part_start, part_sectors)
    mbr[510:512] = b"\x55\xAA"
    img = bytearray(total * SECTOR)
    img[0:SECTOR] = mbr
    img[part_start * SECTOR:part_start * SECTOR + len(vol)] = vol
    return bytes(img)


# ---------------------------------------------------------------------------
# ATA task-file model
# ---------------------------------------------------------------------------

ATA_BASE = 0x90000000
R_DATA, R_FEAT, R_COUNT, R_LBA0, R_LBA1, R_LBA2, R_DEV, R_CMD, R_ALT = (
    0xa0, 0xa4, 0xa8, 0xac, 0xb0, 0xb4, 0xb8, 0xbc, 0xd8)
ST_DRDY, ST_DSC, ST_DRQ = 0x40, 0x10, 0x08

# firmware bookkeeping (docs/EXTERNAL.md §6 / this file's header)
FW_INFLIGHT, FW_COUNT, FW_CMD, FW_BUF, FW_EVENT = (
    0x46c8c58a, 0x46c8c592, 0x46c8c593, 0x46c8c594, 0x46c8c598)
FW_IDENT_BUF, FW_LOCK, FW_ERR = 0x460bac18, 0x460bae18, 0x46c85fe6
FW_WAIT_EVENT = 0x40000818        # RTOS event wait the queue primitive blocks in
FW_QUEUE_NOWAIT_RET = 0x40015786  # 0x4001568c's return when called with the no-wait
                                  # flag: the command is in flight and nobody waits
FW_ATA_HOST_STATUS = 0xfc0a4039   # bit 3 must be CLEAR (movew ->ccr; bpl)
FW_SHOW_MESSAGE = 0x4005a2b8      # (str, kind): storage layer's error popup
FW_ATA_INIT = 0x400160f8          # ATA subsystem init: ISR on vector 0xb6, the two
                                  # command queues (64/32 entries), 16 event objects
# The main init task (0x4001fc00..0x4001fc9c) runs these after the ATA init and
# before parking in `bra *`; the RTOS tasks they create never run in a detour,
# but the queues, tables and objects they set up are what every later detour
# needs (the engine queue 0x460d17ce among them).
FW_SYSTEM_INITS = (0x400209c0, 0x40092178, 0x40040b94, 0x400054c4, 0x4009ae48,
                   0x400a1050, 0x40091ce8, 0x40098a2c)
FW_QUEUES_INIT = 0x40040b14       # creates the three engine-side queues 0x460d17ce/ee/ae
                                  # (1024-entry rings at 0x460d8de4/0x460dde38/0x460d5de4)
FW_CARD_INIT = 0x40061648         # (mode): 1 = detect/init/mount
FW_CARD_READY = 0x460d1cb8        # := 1 after a successful init+mount
FW_SPRINTF = 0x40013a08           # (dst, fmt, ...): every path is built here
FW_SET_NAME = 0x100f8480          # current SET folder name (0x104 bytes)
FW_PROJECT_NAME = 0x100f8378      # current PROJECT folder name (0x104 bytes)
FW_SET_PROJECT_EXISTS = 0x400255ec  # () -> nonzero if SET/PROJECT exists on the card
FW_POST_LOAD_PROJECT = 0x40023c7c   # (name*) -> posts engine command 4 (load project)
FW_POST_RELOAD_BANK = 0x40022778  # (bank) -> posts engine command 20 (RELOADING BANK)
FW_CUR_BANK = 0x80000002          # current bank byte (ARCHITECTURE.md / EXTERNAL.md §6)
FW_ENGINE_QUEUE = 0x460d17ce      # the engine task's command queue (Bryan T, EXTERNAL.md §6)
FW_QUEUE_RECV = 0x40000d00        # (queue) -> message pointer (blocks when empty)
FW_ENGINE_LOOP = 0x4008484e       # engine task loop head; every handler jumps back here
FW_ENGINE_TABLE = 0x40084870      # 46 x s16 offsets from the table base
PART_PTR = 0x46c82456             # project database pointer (null until a project loads)


def identify_words(total_sectors):
    w = [0] * 256
    w[0] = 0x848A                          # CF signature
    cyl, heads, spt = 1024, 16, 63
    w[1], w[3], w[6] = cyl, heads, spt
    w[7], w[8] = (total_sectors >> 16) & 0xFFFF, total_sectors & 0xFFFF
    def s(idx, n, text):
        b = text.ljust(n * 2)[:n * 2].encode("ascii")
        for i in range(n):
            w[idx + i] = (b[2 * i] << 8) | b[2 * i + 1]
    s(10, 10, "OCTABAM0001")
    s(23, 4, "1.0")
    s(27, 20, "OCTABAM EMULATED CF")
    w[47] = 0x8001
    w[49] = 0x0200                          # LBA supported, NO DMA (bit 8 clear)
    w[51] = 0x0200                          # PIO mode 2
    w[53] = 0x0000                          # words 54-58 / 64-70 not valid -> PIO path
    w[54], w[55], w[56] = cyl, heads, spt
    w[57], w[58] = total_sectors & 0xFFFF, (total_sectors >> 16) & 0xFFFF
    w[60], w[61] = total_sectors & 0xFFFF, (total_sectors >> 16) & 0xFFFF
    return w


class AtaCard:
    """ATA/CF device behind the FlexBus task-file window, backed by an image."""

    def __init__(self, image, log=None):
        self.img = bytearray(image)
        self.nsect = len(self.img) // SECTOR
        self.regs = {R_FEAT: 0, R_COUNT: 0, R_LBA0: 0, R_LBA1: 0, R_LBA2: 0, R_DEV: 0xE0}
        self.status = ST_DRDY | ST_DSC
        self.error = 0
        self.data = b""
        self.dpos = 0
        self.wbuf = bytearray()
        self.wlba, self.wremaining = 0, 0
        self.cmd = 0
        self.log = log if log is not None else []
        self.reads = self.writes = 0

    # -- register access -----------------------------------------------------
    def lba(self):
        return (self.regs[R_LBA0] | (self.regs[R_LBA1] << 8) | (self.regs[R_LBA2] << 16)
                | ((self.regs[R_DEV] & 0x0F) << 24))

    def count(self):
        return self.regs[R_COUNT] or 256

    def read(self, off, size):
        if off == R_DATA:
            if self.dpos + 1 < len(self.data):
                v = (self.data[self.dpos] << 8) | self.data[self.dpos + 1]
                self.dpos += 2
                if self.dpos >= len(self.data):
                    self.status &= ~ST_DRQ
                return v
            return 0
        if off in (R_CMD, R_ALT):
            return self.status
        if off == R_FEAT:
            return self.error
        return self.regs.get(off, 0)

    def write(self, off, size, val):
        if off == R_DATA:
            if self.wremaining:
                self.wbuf += bytes([(val >> 8) & 0xFF, val & 0xFF])
                if len(self.wbuf) >= SECTOR:
                    self._commit_sector(bytes(self.wbuf[:SECTOR]))
                    self.wbuf = self.wbuf[SECTOR:]
            return
        if off == R_CMD:
            self.command(val & 0xFF)
            return
        if off in self.regs:
            self.regs[off] = val & 0xFF

    # -- commands ------------------------------------------------------------
    def command(self, c):
        self.cmd = c
        self.error = 0
        self.status = ST_DRDY | ST_DSC
        if c == 0xEC:                                   # IDENTIFY DEVICE
            self.data = struct.pack("<256H", *identify_words(self.nsect))
            self.dpos = 0
            self.status |= ST_DRQ
            self.log.append(("IDENTIFY",))
        elif c == 0x20:                                 # READ SECTORS
            l, n = self.lba(), self.count()
            self.data = bytes(self.img[l * SECTOR:(l + n) * SECTOR])
            self.dpos = 0
            self.status |= ST_DRQ
            self.reads += n
            self.log.append(("READ", l, n))
        elif c == 0x30:                                 # WRITE SECTORS
            l, n = self.lba(), self.count()
            self.wbuf = bytearray()
            self.wlba, self.wremaining = l, n
            self.status |= ST_DRQ
            self.log.append(("WRITE", l, n))
        elif c == 0x87:                                 # CFA TRANSLATE SECTOR
            self.data = bytes(SECTOR)
            self.dpos = 0
            self.status |= ST_DRQ
            self.log.append(("CFA-TRANSLATE", self.lba()))
        elif c in (0xE0, 0xE1, 0xE2, 0xE3, 0xE6, 0xEF, 0xC0, 0x03, 0x91, 0xC6):
            if c == 0xE5:
                self.regs[R_COUNT] = 0xFF
            self.log.append((f"CMD-{c:02x}",))
        elif c == 0xE5:                                 # CHECK POWER MODE
            self.regs[R_COUNT] = 0xFF
            self.log.append(("CHECK-POWER",))
        else:
            self.error = 0x04                           # ABRT
            self.status |= 0x01
            self.log.append((f"UNSUPPORTED-{c:02x}",))

    def _commit_sector(self, data):
        """One sector of a WRITE, in order: the handler streams the first
        sector through the data register itself (0x40014c48 after the
        command), the interrupt handler would stream the rest."""
        l = self.wlba
        if l < self.nsect:
            self.img[l * SECTOR:(l + 1) * SECTOR] = data
        self.writes += 1
        self.wlba += 1
        self.wremaining -= 1
        if self.wremaining <= 0:
            self.wremaining = 0
            self.status &= ~ST_DRQ

    # -- the data phase the interrupt handler would do -------------------------
    def complete(self, uc):
        """Perform the transfer for the command the firmware has in flight, with
        the bookkeeping `0x40015304` does, minus the RTOS signal."""
        cmd = uc.mem_read(FW_CMD, 1)[0]
        count = uc.mem_read(FW_COUNT, 1)[0] or (256 if cmd == 0x20 else 0)
        buf = int.from_bytes(uc.mem_read(FW_BUF, 4), "big")
        if cmd == 0xEC:
            words = identify_words(self.nsect)
            uc.mem_write(FW_IDENT_BUF, struct.pack(">256H", *words))
            self.data, self.dpos = b"", 0
        elif cmd == 0x20:
            n = count
            uc.mem_write(buf, bytes(self.data[:n * SECTOR]).ljust(n * SECTOR, b"\x00"))
            uc.mem_write(FW_BUF, (buf + n * SECTOR).to_bytes(4, "big"))
            uc.mem_write(FW_COUNT, b"\x00")
            self.data, self.dpos = b"", 0
        elif cmd == 0x30:
            # the count byte is SECTORS REMAINING: the handler already streamed
            # the first sector and decremented it (a 1-sector write reads 0
            # here — treating that as 256 wiped a whole card, 5 Sep 2026)
            rem = uc.mem_read(FW_COUNT, 1)[0]
            if rem and self.wremaining:
                rem = min(rem, self.wremaining)
                data = bytes(uc.mem_read(buf, rem * SECTOR))
                for i in range(rem):
                    self._commit_sector(data[i * SECTOR:(i + 1) * SECTOR])
                uc.mem_write(FW_BUF, (buf + rem * SECTOR).to_bytes(4, "big"))
            uc.mem_write(FW_COUNT, b"\x00")
        elif cmd == 0x87:
            uc.mem_write(buf, bytes(SECTOR))
        elif cmd == 0xE5:
            uc.mem_write(FW_ERR, bytes([self.regs[R_COUNT]]))
        self.status &= ~ST_DRQ
        uc.mem_write(FW_INFLIGHT, (0).to_bytes(4, "big"))
        uc.mem_write(FW_CMD, b"\x00")
        uc.mem_write(FW_EVENT, (0).to_bytes(4, "big"))
        uc.mem_write(FW_LOCK, (0).to_bytes(4, "big"))


# ---------------------------------------------------------------------------
# attaching to a warm machine
# ---------------------------------------------------------------------------

class CardSession:
    def __init__(self, r, card):
        self.r, self.uc, self.card = r, r.uc, card
        self.messages = []        # storage-layer popups (error strings)
        self.paths = []           # every path the firmware formats
        self.waits = 0            # event waits we satisfied
        self.wait_log = []        # (caller, event, kind) per satisfied wait
        self.engine_ops = []      # engine opcodes run by engine_run_once
        self.async_completions = 0

    def _emulate_rts(self, uc, d0=0):
        sp = uc.reg_read(eb.UC_M68K_REG_A7)
        ret = int.from_bytes(uc.mem_read(sp, 4), "big")
        uc.reg_write(eb.UC_M68K_REG_A7, sp + 4)
        uc.reg_write(eb.UC_M68K_REG_D0, d0)
        uc.reg_write(eb.UC_M68K_REG_PC, ret)


def attach(r, image, log=None):
    """Map the card into a warm machine (after `emu_bringup.boot`)."""
    uc = r.uc
    card = AtaCard(image, log)
    s = CardSession(r, card)
    # SDRAM the storage stack uses that the boot never touched: sector buffers
    # at 0x4ece3000 / 0x4eceb200 and the file-system state around them.
    # The boot maps 32 MB of SDRAM; the storage stack and the project loader
    # use the rest of the 256 MB: the PCM pool 0x40A955E0..0x45F..., sector
    # buffers 0x4ece3000/0x4eceb200, the delay rings 0x4F502C10. Map it all,
    # plus the on-chip SRAM around the boot's 0x100b0000 window (names at
    # 0x100f8480, object tables 0x100b14f0..0x100f7f30).
    # (the boot already maps 0x40000000 +32 MB, 0x46000000 +32 MB, 0x48000000
    # +1 MB and 0x100b0000 +64 KB; mem_map refuses overlaps, so fill the gaps)
    for base, size in ((0x42000000, 0x04000000),
                       (0x48100000, 0x07f00000),
                       (0x10000000, 0x000b0000),
                       (0x100c0000, 0x00040000)):
        try:
            uc.mem_map(base, size)
        except eb.UcError:
            pass
    # replace the generic peripheral stub on the task-file window
    uc.mem_unmap(ATA_BASE, 0x1000)
    uc.mmio_map(ATA_BASE, 0x1000,
                lambda u, off, size, d: card.read(off, size), None,
                lambda u, off, size, val, d: card.write(off, size, val), None)

    def on_wait(u, addr, size, user):
        # Every RTOS event wait in a cold detour returns at once. The ATA wait
        # first gets its data phase; a timer wait (the storage layer's delay
        # helper 0x40020c7c programs 0xfc084000 then blocks here) just passes
        # instantly; anything else is logged so a silently-satisfied wait for
        # something that never happened can be recognised in the record.
        sp = u.reg_read(eb.UC_M68K_REG_A7)
        ret = int.from_bytes(u.mem_read(sp, 4), "big")
        ev = int.from_bytes(u.mem_read(sp + 4, 4), "big")
        # READ/WRITE set both the in-flight flag and the command byte; the
        # IDENTIFY getter (0x400159bc) sets only the command byte and the lock.
        pending = u.mem_read(FW_CMD, 1)[0]
        kind = f"ata-{pending:02x}" if pending else "other"
        if pending:
            card.complete(u)
        s.waits += 1
        s.wait_log.append((ret, ev, kind))
        s._emulate_rts(u, 0)
    uc.hook_add(eb.UC_HOOK_CODE, on_wait, begin=FW_WAIT_EVENT, end=FW_WAIT_EVENT)

    def on_nowait(u, addr, size, user):
        # An asynchronous command (queue primitive called with flag bit 1)
        # would complete on the interrupt while the caller works on. With no
        # interrupt it would hold the lock forever, every later command would
        # queue behind it, and the caller would spin on a full queue (seen 5
        # Sep 2026 in the bank loader). Complete it here, before the caller
        # continues; its later event wait then finds nothing pending.
        if u.mem_read(FW_CMD, 1)[0]:
            card.complete(u)
            s.async_completions += 1
    uc.hook_add(eb.UC_HOOK_CODE, on_nowait, begin=FW_QUEUE_NOWAIT_RET, end=FW_QUEUE_NOWAIT_RET)

    def on_message(u, addr, size, user):
        sp = u.reg_read(eb.UC_M68K_REG_A7)
        p = int.from_bytes(u.mem_read(sp + 4, 4), "big")
        s.messages.append(eb._cstr(u, p, 64))
    uc.hook_add(eb.UC_HOOK_CODE, on_message, begin=FW_SHOW_MESSAGE, end=FW_SHOW_MESSAGE)

    def on_sprintf(u, addr, size, user):
        sp = u.reg_read(eb.UC_M68K_REG_A7)
        fmt = int.from_bytes(u.mem_read(sp + 8, 4), "big")
        f = eb._cstr(u, fmt, 64)
        if "/" in f or "." in f:
            args = []
            for i in range(f.count("%")):
                a = int.from_bytes(u.mem_read(sp + 12 + 4 * i, 4), "big")
                try:
                    raw = bytes(u.mem_read(a, 64)) if "%s" in f else b""
                    args.append(raw.split(b"\x00")[0].decode("ascii", "replace") if raw else hex(a))
                except eb.UcError:
                    args.append(hex(a))
            s.paths.append((f, args))
    uc.hook_add(eb.UC_HOOK_CODE, on_sprintf, begin=FW_SPRINTF, end=FW_SPRINTF)
    uc.ctl_flush_tb()
    r.card = s
    return s


def card_init(s):
    """Run the firmware's storage bring-up cold: the ATA subsystem init the
    storage task would have done (`0x400160f8`, once), then card
    detect/init/mount (`0x40061648(1)`)."""
    uc = s.uc
    if not getattr(s, "_ata_inited", False):
        eb._call(uc, FW_ATA_INIT, [])
        s.init_log = []
        for fn in (FW_QUEUES_INIT,) + FW_SYSTEM_INITS:
            try:
                eb._call(uc, fn, [], count=50_000_000)
                s.init_log.append((fn, "ok" if not s.r.trap else f"trap {s.r.trap}"))
            except (eb.UcError, eb.DetourTrap, eb.DetourStall) as e:
                s.init_log.append((fn, f"fault {e} pc={uc.reg_read(eb.UC_M68K_REG_PC):#x}"))
        s._ata_inited = True
    eb._call(uc, FW_CARD_INIT, [1])
    d0 = uc.reg_read(eb.UC_M68K_REG_D0) & 0xFFFFFFFF
    ready = int.from_bytes(uc.mem_read(FW_CARD_READY, 4), "big")
    return d0, ready


FW_ENGINE_TASK = 0x4008445c       # engine task entry (NOTES.md FUN_4008445c)
FW_ENGINE_RECV_SITE = 0x40084854  # the loop's `jsr 0x40000d00` — our step boundary
ENGINE_SP = 0x47f80000            # a stack for the cold-run engine task
_REGS = None


def _regs():
    global _REGS
    if _REGS is None:
        _REGS = [getattr(eb, f"UC_M68K_REG_D{i}") for i in range(8)] + \
                [getattr(eb, f"UC_M68K_REG_A{i}") for i in range(8)] + \
                [eb.UC_M68K_REG_SR]
    return _REGS


def engine_start(s):
    """Run the engine task from its entry to its first receive: the prologue
    creates its own queue (`0x460d17ce`) and state, so this must happen before
    anything is posted to it."""
    uc = s.uc
    if hasattr(s, "_engine_regs"):
        return
    uc.reg_write(eb.UC_M68K_REG_A7, ENGINE_SP)
    uc.reg_write(eb.UC_M68K_REG_SR, 0x2700)
    trap = eb._run_until(uc, FW_ENGINE_TASK, FW_ENGINE_RECV_SITE)
    s._engine_regs = [uc.reg_read(r) for r in _regs()]
    if trap is not None:
        raise eb.DetourTrap(trap[0], trap[1], "engine task prologue")


def engine_run_once(s):
    """Run the engine task cold, one message at a time.

    The handlers address locals through the task's frame pointer, so they can
    only run inside the task: the first call runs the task from its entry to
    the loop's receive call (prologue done, queue empty is fine — we stop
    BEFORE the receive would block); each later call resumes at that call
    with a message queued and runs until the loop comes back round to it.
    The task's registers are kept across calls. Returns the opcode handled,
    or None if the queue was empty."""
    uc = s.uc
    engine_start(s)
    # queue layout (0x40000c3c post / 0x40000d00 receive): +4 pending count,
    # +12 waiting task, +16 index mask, +20 ring of message pointers,
    # +24 write index, +28 read index
    q = FW_ENGINE_QUEUE
    count = int.from_bytes(uc.mem_read(q + 4, 4), "big")
    if count == 0:
        return None
    ring = int.from_bytes(uc.mem_read(q + 20, 4), "big")
    rd = int.from_bytes(uc.mem_read(q + 28, 4), "big")
    msg = int.from_bytes(uc.mem_read(ring + 4 * rd, 4), "big")
    op = uc.mem_read(msg, 1)[0] if msg else None
    for reg, v in zip(_regs(), s._engine_regs):
        uc.reg_write(reg, v)
    # emu_start(begin == until) runs nothing, so step in two legs: through the
    # receive call to the instruction after it, then round the loop back to it.
    trap = eb._run_until(uc, FW_ENGINE_RECV_SITE, FW_ENGINE_RECV_SITE + 6)
    if trap is None:
        trap = eb._run_until(uc, FW_ENGINE_RECV_SITE + 6, FW_ENGINE_RECV_SITE)
    s._engine_regs = [uc.reg_read(r) for r in _regs()]
    if trap is not None:
        raise eb.DetourTrap(trap[0], trap[1], f"engine op {op}")
    s.engine_ops.append(op)
    return op


def set_names(s, set_name, project_name):
    """The set name is an ABSOLUTE path on the card: the firmware's own
    default is "/PRESETS" (0x400b46ef) and its log names bank files
    "/PRESETS/<project>/bank01.work". Without the slash the project loads
    (relative to the root) and then every bank is "missing" (measured 5 Sep
    2026: the loader had changed into the project directory)."""
    uc = s.uc
    if not set_name.startswith("/"):
        set_name = "/" + set_name
    uc.mem_write(FW_SET_NAME, set_name.encode("ascii")[:0x100] + b"\x00")
    uc.mem_write(FW_PROJECT_NAME, project_name.encode("ascii")[:0x100] + b"\x00")


def reload_bank(s, bank):
    """Post RELOAD BANK for `bank` (0-based) and run the engine command: this
    is what pulls bank%02d.work into the bank blob. LOAD PROJECT alone reads
    project.work, markers.work and the arrangements (measured 5 Sep 2026).
    The command's word argument is a BITMASK of banks (the loader
    `0x4008f0b0` loops over set bits and formats bank%02d for each, 1-based),
    so bank 0 is mask 1."""
    uc = s.uc
    engine_start(s)
    eb._call(uc, FW_POST_RELOAD_BANK, [1 << bank])
    ops = []
    for _ in range(4):
        op = engine_run_once(s)
        if op is None:
            break
        ops.append(op)
    return ops


def load_project(s, set_name, project_name, banks=()):
    """Name the set and project the way the storage task would have, confirm
    the firmware can see them on the card, post LOAD PROJECT and run the
    engine command. LOAD PROJECT reads project.work, markers.work, the
    arrangements and ALL SIXTEEN bank files itself (given the absolute set
    path); `banks` posts extra RELOAD BANK commands. Returns
    (exists, posted, ops_run, part_ptr)."""
    uc = s.uc
    engine_start(s)
    set_names(s, set_name, project_name)
    eb._call(uc, FW_SET_PROJECT_EXISTS, [])
    exists = uc.reg_read(eb.UC_M68K_REG_D0) & 0xFFFFFFFF
    eb._call(uc, FW_POST_LOAD_PROJECT, [FW_PROJECT_NAME])
    posted = uc.reg_read(eb.UC_M68K_REG_D0) & 0xFFFFFFFF
    ops = []
    for _ in range(8):
        op = engine_run_once(s)
        if op is None:
            break
        ops.append(op)
    for b in banks:
        ops += reload_bank(s, b)
    part = int.from_bytes(uc.mem_read(PART_PTR, 4), "big")
    return exists, posted, ops, part


def boot_with_card(image_path=None, card_image=None, log=None):
    """Boot (with the ATA host status override) and attach the card."""
    eb.EXTRA_OVERRIDES[FW_ATA_HOST_STATUS] = 0x00
    # 0x40040b94 (system init) polls 0xfc05c02c until bits 4-7 read 2; the
    # all-ones default spins forever.
    eb.EXTRA_OVERRIDES[0xfc05c02c] = 0x00000020
    r = eb.boot(image_path)
    if not r.reached_handoff:
        return r, None
    s = attach(r, card_image, log)
    return r, s


def _cli():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", help="project directory (bank*.work, project.work, ...)")
    ap.add_argument("--set", default="OCTABAM", help="SET folder name on the card")
    ap.add_argument("--name", default=None, help="PROJECT folder name (default: dir name)")
    ap.add_argument("--audio", action="store_true", help="include .wav/.ot files")
    ap.add_argument("--size", type=int, default=64, help="image size, MB")
    ap.add_argument("--image", default="out/emu_card.img", help="card image path to write")
    ap.add_argument("--firmware", default=None, help="MAIN OS image (default: emu_bringup's)")
    ap.add_argument("--image-only", action="store_true", help="build the card image and stop")
    ap.add_argument("--load", nargs=2, metavar=("SET", "PROJECT"), default=None,
                    help="after card init, load SET/PROJECT through the engine command")
    a = ap.parse_args()

    tree = pathlib.Path("out/_emu_card_tree")
    if a.project:
        import shutil
        src = pathlib.Path(a.project)
        name = a.name or src.name
        if tree.exists():
            shutil.rmtree(tree)
        dst = tree / a.set / name
        dst.mkdir(parents=True)
        (tree / a.set / "AUDIO").mkdir()
        for p in sorted(src.iterdir()):
            if p.name.startswith("._") or p.name in _SKIP:
                continue
            if not a.audio and p.suffix.lower() in (".wav", ".ot"):
                continue
            if p.is_file():
                shutil.copy2(p, dst / p.name)
        files = []
        img = build_image(str(tree), a.size, log=files)
        pathlib.Path(a.image).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.image).write_bytes(img)
        print(f"card image : {a.image}  ({len(img) // 1048576} MB, {len(files)} entries, "
              f"/{a.set}/{name}/)")
    else:
        img = pathlib.Path(a.image).read_bytes()
        print(f"card image : {a.image} (existing)")
    if a.image_only:
        return

    t0 = time.time()
    ata_log = []
    r, s = boot_with_card(a.firmware, img, ata_log)
    print(f"boot       : {r.stopped}  ({time.time() - t0:.1f}s)")
    if s is None:
        sys.exit(1)
    try:
        d0, ready = card_init(s)
        for fn, res in s.init_log:
            print(f"  init     : {fn:#x} {res}")
        print(f"card init  : d0=0x{d0:08x} ready={ready}  event-waits satisfied={s.waits}")
    except (eb.UcError, eb.DetourTrap, eb.DetourStall) as e:
        print(f"card init  : FAULT {e} at pc=0x{s.uc.reg_read(eb.UC_M68K_REG_PC):08x}")
    for m in s.messages:
        print(f"  message  : {m!r}")
    load = a.load or ((a.set, a.name or pathlib.Path(a.project).name) if a.project else None)
    if load:
        try:
            exists, posted, ops, part = load_project(s, *load)
            print(f"load       : /{load[0].lstrip('/')}/{load[1]}  exists={exists} posted={posted} "
                  f"engine ops={ops}  PART=0x{part:08x}")
            if part:
                uc = s.uc
                fx1 = [uc.mem_read(part + 0x8ed80 + t, 1)[0] for t in range(8)]
                fx2 = [uc.mem_read(part + 0x8ed88 + t, 1)[0] for t in range(8)]
                print(f"  part 1   : FX1 ids {fx1}  FX2 ids {fx2}  (bank A, from bank01.work)")
        except (eb.UcError, eb.DetourTrap, eb.DetourStall) as e:
            print(f"load       : FAULT {e} at pc=0x{s.uc.reg_read(eb.UC_M68K_REG_PC):08x}")
        for m in s.messages:
            print(f"  message  : {m!r}")
    print(f"ATA        : {len(ata_log)} commands, {s.card.reads} sectors read, "
          f"{s.card.writes} written")
    for e in ata_log[:40]:
        print("  ", e)
    for f, args in s.paths[:40]:
        print(f"  path     : {f!r} {args}")
    import collections
    waits = collections.Counter((hex(c), k) for c, _, k in s.wait_log)
    for (c, k), n in waits.most_common(12):
        print(f"  wait     : caller {c} {k} x{n}")


if __name__ == "__main__":
    _cli()
