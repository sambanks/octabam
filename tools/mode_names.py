#!/usr/bin/env python3
"""A MODE select's formatter that also RENAMES the knobs around it.

A multi-mode effect reuses its knobs. BongDelay's MDEP is the tape modulation
depth in CLEAN and the grain scatter in GRAIN; its MRAT is the modulation rate
and the grain density. The panel printed one name for both meanings until
this existed, and Sam said so plainly (3 Sep 2026): *"can we label the depth
and rate to make it clear it's mod depth and mod rate not effect depth"*, and
then *"it's only got four settings ... just feels a lil confusing"*.

WHERE THE NAMES LIVE. `docs/PARAM_PAGES.md`: a descriptor carries its twelve
parameter names as **12 x 6 bytes at E+0x4e**, NUL-padded. Our clones sit in
the ColdFire cave region and are ordinary writable RAM, so a rename is six
bytes copied into the clone.

WHY THE MODE FORMATTER IS THE HOOK, and this is the whole trick: PLAN §6
already gives every stepped select a cave of its own, called by the panel as
`fmt(buf, value)` **with the value in hand** whenever the page draws that
slot. So the rename needs no new hook site, no per-frame writer, no decode of
which track is selected and no read of the part -- the panel hands us the
mode, and we write the names before printing its word.

⚠️ ONE DRAW LATE, BY CONSTRUCTION. If the panel draws the other slots' names
BEFORE it formats the MODE value, a rename lands on the next redraw rather
than this one. Turning the encoder redraws immediately, so it is invisible in
use -- but it is inferred, not measured, and the falsifier is a panel that
shows the old names until you touch something else.

⚠️ AND IT RENAMES THE DESCRIPTOR, WHICH IS SHARED BY EVERY TRACK. Two tracks
running the same effect in different modes have one set of names between
them: whichever drew last wins. The panel draws one track at a time, so what
you are looking at is right; what a photograph of another track's page would
have shown is not.

The bytes are EMITTED here rather than assembled, the same discipline as
tools/label_fmt.py and for the same reason: the build must not need an m68k
toolchain. `verify()` re-derives them through `m68k-elf-as -mcpu=5407`
whenever one is on PATH, and `make check` runs it.
"""
from __future__ import annotations

SPRINTF = 0x40013a08
NAMES_AT = 0x4e                    # descriptor + 0x4e = 12 x 6-byte names
NAME_LEN = 6
CODE_LEN = 88                      # rtab starts here: the code runs to the jmp


def _blocks(renames: dict[int, dict[int, bytes]], modes: int) -> list[bytes]:
    """One 8-byte record per renamed slot, per mode: slot, pad, six name bytes.

    EIGHT, not six: the copy is a move.l plus a move.w, and ColdFire wants
    those aligned. The pad byte is what keeps every record on an even
    boundary however many slots a mode renames.
    """
    out = []
    for m in range(modes):
        rec = b""
        for slot in sorted(renames.get(m, {})):
            nm = renames[m][slot]
            if len(nm) > NAME_LEN - 1:
                raise ValueError(f"mode {m} slot {slot}: {nm!r} is longer than "
                                 f"{NAME_LEN - 1} characters")
            rec += bytes([slot, 0]) + nm.ljust(NAME_LEN, b"\0")
        out.append(rec + b"\xff\x00" + b"\0" * 6)      # terminator, padded
    return out


def emit(labels: tuple[str, ...], desc: int,
         renames: dict[int, dict[int, bytes]]) -> bytes:
    """The cave for a MODE select: rename the neighbours, then print the word.

    labels  -- what each value prints, exactly as tools/label_fmt.py takes it
    desc    -- the descriptor whose names are rewritten (our clone's address)
    renames -- {mode value: {slot: 4-char name}}, already made COMPLETE by the
               caller: every mode must restore every slot any mode renames, or
               a name would stick after the mode that set it.
    """
    n = len(labels)
    if not 1 <= n <= 128:
        raise ValueError(f"a select needs 1..128 labels, got {n}")
    for s in labels:
        if "%" in s or not s.isascii():
            raise ValueError(f"label {s!r}: the label IS the format string")
    blocks = _blocks(renames, n)
    # rtab and tab are both offset tables, each relative to ITS OWN address,
    # so the cave stays position independent wherever the placer puts it.
    rtab, rblob, off = b"", b"", 2 * n
    for b in blocks:
        rtab += off.to_bytes(2, "big")
        rblob += b
        off += len(b)
    tab, blob, off = b"", b"", 2 * n
    for s in labels:
        tab += off.to_bytes(2, "big")
        enc = s.encode("ascii") + b"\0"
        blob += enc
        off += len(enc)
    # The pc-relative displacement to `tab`. ⚠️ MEASURED FROM THE
    # INSTRUCTION'S OWN ADDRESS, not from its extension word -- checked
    # against m68k-elf-as, which is the only reason this is right (the first
    # attempt was 6 bytes long and would have indexed off the end of the
    # table into the strings).
    tab_disp = (CODE_LEN - 64) + len(rtab) + len(rblob)
    code = bytes([
        0x20, 0x2f, 0x00, 0x08,                       # move.l 8(sp),d0
        0x0c, 0x80, *n.to_bytes(4, "big"),            # cmp.l  #n,d0
        0x65, 0x02,                                   # blo.s  ok
        0x70, 0x00,                                   # moveq  #0,d0
        0x43, 0xfa, 0x00, 0x4a,                       # lea    rtab(pc),a1
        0x32, 0x31, 0x0a, 0x00,                       # move.w (a1,d0.l*2),d1
        0x02, 0x81, 0x00, 0x00, 0xff, 0xff,           # and.l  #0xffff,d1
        0xd3, 0xc1,                                   # adda.l d1,a1
        0x12, 0x19,                                   # move.b (a1)+,d1
        0x0c, 0x01, 0x00, 0xff,                       # cmpi.b #0xff,d1
        0x67, 0x1a,                                   # beq.s  rdn
        0x52, 0x89,                                   # addq.l #1,a1
        0x02, 0x81, 0x00, 0x00, 0x00, 0xff,           # and.l  #0xff,d1
        0xc2, 0xfc, 0x00, 0x06,                       # mulu.w #6,d1
        0x41, 0xf9, *desc.to_bytes(4, "big"),         # lea    desc+0x4e,a0
        0xd1, 0xc1,                                   # adda.l d1,a0
        0x20, 0xd9,                                   # move.l (a1)+,(a0)+
        0x30, 0xd9,                                   # move.w (a1)+,(a0)+
        0x60, 0xde,                                   # bra.s  rlp
        0x41, 0xfa, *tab_disp.to_bytes(2, "big"),     # lea    tab(pc),a0
        0x32, 0x30, 0x0a, 0x00,                       # move.w (a0,d0.l*2),d1
        0x02, 0x81, 0x00, 0x00, 0xff, 0xff,           # and.l  #0xffff,d1
        0xd1, 0xc1,                                   # adda.l d1,a0
        0x2f, 0x48, 0x00, 0x08,                       # move.l a0,8(sp)
        0x4e, 0xf9, *SPRINTF.to_bytes(4, "big"),      # jmp    sprintf
    ])
    out = code + rtab + rblob + tab + blob
    return out + b"\0" * (len(out) % 2)


def source(labels: tuple[str, ...], desc: int,
           renames: dict[int, dict[int, bytes]]) -> str:
    """The same cave as assembler, for verify() and for a human reading it."""
    n = len(labels)
    blocks = _blocks(renames, n)
    rt = ",".join(f"r{i}-rtab" for i in range(n))
    tb = ",".join(f"s{i}-tab" for i in range(n))
    rb = "\n".join(
        f"r{i}:     .byte   " + ",".join(str(b) for b in blocks[i])
        for i in range(n))
    ss = "\n".join(f's{i}:     .asciz  "{s}"' for i, s in enumerate(labels))
    return (f'        .text\n'
            f'fmt:    move.l  8(%sp),%d0\n'
            f'        cmp.l   #{n},%d0\n'
            f'        blo.s   ok\n'
            f'        moveq   #0,%d0\n'
            f'ok:     lea     rtab(%pc),%a1\n'
            f'        move.w  (%a1,%d0.l*2),%d1\n'
            f'        and.l   #0xffff,%d1\n'
            f'        adda.l  %d1,%a1\n'
            f'rlp:    move.b  (%a1)+,%d1\n'
            f'        cmpi.b  #0xff,%d1\n'
            f'        beq.s   rdn\n'
            f'        addq.l  #1,%a1\n'
            f'        and.l   #0xff,%d1\n'
            f'        mulu.w  #{NAME_LEN},%d1\n'
            f'        lea     0x{desc:08x},%a0\n'
            f'        adda.l  %d1,%a0\n'
            f'        move.l  (%a1)+,(%a0)+\n'
            f'        move.w  (%a1)+,(%a0)+\n'
            f'        bra.s   rlp\n'
            f'rdn:    lea     tab(%pc),%a0\n'
            f'        move.w  (%a0,%d0.l*2),%d1\n'
            f'        and.l   #0xffff,%d1\n'
            f'        adda.l  %d1,%a0\n'
            f'        move.l  %a0,8(%sp)\n'
            f'        jmp     0x{SPRINTF:08x}\n'
            f'rtab:   .word   {rt}\n'
            f'{rb}\n'
            f'tab:    .word   {tb}\n'
            f'{ss}\n'
            f'        .balign 2\n')


def verify(labels: tuple[str, ...], desc: int,
           renames: dict[int, dict[int, bytes]]) -> None:
    """Re-derive emit() through the real assembler. No-op without one."""
    import os, pathlib, shutil, subprocess, tempfile
    if not (shutil.which("m68k-elf-as") and shutil.which("m68k-elf-objcopy")):
        return
    with tempfile.TemporaryDirectory() as td:
        s = os.path.join(td, "m.s")
        pathlib.Path(s).write_text(source(labels, desc, renames))
        o, b = os.path.join(td, "m.o"), os.path.join(td, "m.bin")
        subprocess.run(["m68k-elf-as", "-mcpu=5407", "-o", o, s], check=True)
        subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text",
                        o, b], check=True)
        want = pathlib.Path(b).read_bytes()
        got = emit(labels, desc, renames)
        if got[:len(want)] != want:
            raise SystemExit(
                f"mode_names.emit disagrees with m68k-elf-as:\n"
                f"  emitted   {got[:len(want)].hex(' ')}\n"
                f"  assembled {want.hex(' ')}")


def complete(mod) -> dict[int, dict[int, bytes]]:
    """Every mode's FULL rename set for the slots ANY of its views touches.

    A sparse table would leave a name behind: land on GRAIN (MDEP -> SCAT),
    go back to CLEAN, and the knob would still read SCAT because CLEAN never
    said otherwise. So each mode restores the Param's own name for every slot
    any view renames.
    """
    touched = sorted({sl for v in mod.mode_views for sl in v.names})
    if not touched:
        return {}
    out = {}
    n = mod.params[mod.mode_slot].count or len(mod.mode_views)
    for m in range(n):
        v = mod.view_for(m)
        out[m] = {sl: (v.names.get(sl) if v else None) or mod.params[sl].name
                  for sl in touched}
    return out
