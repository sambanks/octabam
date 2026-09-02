#!/usr/bin/env python3
"""A ColdFire display formatter that prints a select's WORDS, not its number.

PLAN §6. Every stepped select on the unit reads as a bare number today --
WarpFold's MODE draws `1 2 3` where the manifest has said `FOLD RING BOTH`
all along -- because `Param.labels` was authored, schema-checked against
`count`, and then never read by the build. This is what makes it load-bearing.

THE MECHANISM, from docs/PARAM_PAGES.md section 7. Every per-slot formatter
(`P+0x0ca`, the "A" array) has one signature:

    void fmt(char *buf, int value);      4(sp) = buf, 8(sp) = value

and every stock one is a thin wrapper over `sprintf` (0x40013a08). The
0x4003c14c formatter (ON/OFF) proves the shape that matters here: **the label
IS the format string**. So a labelled select is a small cave -- index a
pointer table by value, overwrite the value slot with the pointer, and tail
`jmp` into sprintf, which then sees sprintf(buf, label).

WHY THE BYTES ARE EMITTED HERE rather than assembled. The build deliberately
needs no m68k toolchain: a CavePatch carries PINNED bytes and the source is
re-assembled and compared only when `m68k-elf-as` is on PATH. Twelve caves
whose contents vary with the labels cannot be hand-pinned, so they are
emitted -- and `verify()` below re-derives them through the real assembler
whenever it is available, which is the same discipline one level up.

The code is a FIXED 40 bytes; only the bounds immediate varies. Verified
against m68k-elf-as -mcpu=5407 (2 Sep 2026).
"""
from __future__ import annotations

SPRINTF = 0x40013a08
CODE_LEN = 40                      # the table starts here; see _CODE below


def emit(labels: tuple[str, ...]) -> bytes:
    """The cave for one labelled select: code, offset table, strings."""
    n = len(labels)
    if not 1 <= n <= 128:
        raise ValueError(f"a select needs 1..128 labels, got {n}")
    for s in labels:
        # THE LABEL IS THE FORMAT STRING, so a '%' in one would be read as a
        # conversion and sprintf would consume a garbage argument off the
        # stack. None of the twelve authored selects contains one; refuse
        # rather than leave it to the next person.
        if "%" in s:
            raise ValueError(f"label {s!r} contains '%': the label IS the "
                             f"format string, so it would be a conversion")
        if not s.isascii():
            raise ValueError(f"label {s!r} is not ASCII")
    code = bytes([
        0x20, 0x2f, 0x00, 0x08,                          # move.l 8(sp),d0
        0x0c, 0x80, *n.to_bytes(4, "big"),               # cmp.l  #n,d0
        0x65, 0x02,                                      # blo.s  ok
        0x70, 0x00,                                      # moveq  #0,d0
        0x41, 0xfa, 0x00, 0x18,                          # lea    tab(pc),a0
        0x32, 0x30, 0x0a, 0x00,                          # move.w (a0,d0.l*2),d1
        0x02, 0x81, 0x00, 0x00, 0xff, 0xff,              # and.l  #0xffff,d1
        0xd1, 0xc1,                                      # adda.l d1,a0
        0x2f, 0x48, 0x00, 0x08,                          # move.l a0,8(sp)
        0x4e, 0xf9, *SPRINTF.to_bytes(4, "big"),         # jmp    sprintf
    ])
    assert len(code) == CODE_LEN, len(code)
    # Offsets are from the TABLE's own address, so the cave is position
    # independent -- it is placed wherever the allocator has room.
    tab, blob, off = b"", b"", 2 * n
    for s in labels:
        tab += off.to_bytes(2, "big")
        enc = s.encode("ascii") + b"\0"
        blob += enc
        off += len(enc)
    out = code + tab + blob
    return out + b"\0" * (len(out) % 2)          # keep the next cave aligned


def source(labels: tuple[str, ...]) -> str:
    """The same thing as assembler, for verify() and for a human reading it."""
    tab = ",".join(f"s{i}-tab" for i in range(len(labels)))
    strs = "\n".join(f's{i}:     .asciz  "{s}"' for i, s in enumerate(labels))
    return (f'        .text\n'
            f'fmt:    move.l  8(%sp),%d0\n'
            f'        cmp.l   #{len(labels)},%d0\n'
            f'        blo.s   ok\n'
            f'        moveq   #0,%d0\n'
            f'ok:     lea     tab(%pc),%a0\n'
            f'        move.w  (%a0,%d0.l*2),%d1\n'
            f'        and.l   #0xffff,%d1\n'
            f'        adda.l  %d1,%a0\n'
            f'        move.l  %a0,8(%sp)\n'
            f'        jmp     0x{SPRINTF:08x}\n'
            f'tab:    .word   {tab}\n'
            f'{strs}\n'
            f'        .balign 2\n')


def verify(labels: tuple[str, ...]) -> None:
    """Re-derive emit() through the real assembler. No-op without one."""
    import os, pathlib, shutil, subprocess, tempfile
    if not (shutil.which("m68k-elf-as") and shutil.which("m68k-elf-objcopy")):
        return
    with tempfile.TemporaryDirectory() as td:
        s = os.path.join(td, "l.s")
        pathlib.Path(s).write_text(source(labels))
        o, b = os.path.join(td, "l.o"), os.path.join(td, "l.bin")
        subprocess.run(["m68k-elf-as", "-mcpu=5407", "-o", o, s], check=True)
        subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text",
                        o, b], check=True)
        want = pathlib.Path(b).read_bytes()
        got = emit(labels)
        if got[:len(want)] != want:
            raise SystemExit(
                f"label_fmt.emit disagrees with m68k-elf-as for {labels}:\n"
                f"  emitted {got.hex(' ')}\n"
                f"  assembled {want.hex(' ')}")


if __name__ == "__main__":
    import sys
    from remix import registry
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    bad = 0
    for key, m in registry.modules().items():
        if m.is_stock:
            continue
        for i, p in enumerate(m.params):
            if not (p.active and p.labels):
                continue
            try:
                verify(p.labels)
                print(f"  [PASS] {key} slot {i} {p.name.decode():<5} "
                      f"{len(emit(p.labels)):>3} B  {' '.join(p.labels)}")
            except SystemExit as e:
                bad += 1
                print(f"  [FAIL] {e}")
    print("OK" if not bad else f"{bad} FAILED")
    sys.exit(1 if bad else 0)
