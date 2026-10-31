#!/usr/bin/env python3
"""What STEMS must look like, drawn by the firmware itself (verify_stems_menu).

Yves chose STEMS's look on 27 Oct 2026 from mockups made this way: stock
SYSTEM > PERSONALIZE opened under the port, with its title, its icon and
its rows swapped for STEMS's through memory, so the frame, the set and
project band, the font, the checkboxes, the rule, the arrows and the bar
are what the unit draws. The pair rows (AB, CD) have no stock form: their
fields are drawn with the firmware's own text and invert calls at the
columns of the approved mockup, which come from the font's widths here,
not from stems.s.

    ref = Reference(p, s)          # before PERSONALIZE first draws (it pokes
                                   # the draw routine's two table operands)
    ref.load(rows, sel, field)     # then open SYSTEM > PERSONALIZE and draw

A row is ("text", label, value) or ("pair", name, stereo, (on1, on2)).
PERSONALIZE's draw routine (0x40068e00) calls each row's getter after its
label; a pair row's getter is a stub that draws the fields, and on the
cursor's row inverts all but the picked field's name before stock's own
bar (an XOR over 3..107) inverts the whole row, which leaves just that name
inverted, as stock MIDI SYNC marks the field under its cursor."""
import pathlib
import shutil
import struct
import subprocess
import tempfile

TITLE, ICON_REC = 0x400b62e0, 0x400cbc48    # PERSONALIZE's title string and icon record
LABELS_AT, GETTERS_AT = 0x40068efe, 0x40068f0a  # its draw routine's table operands (MUTE_MODES moves the tables)
LIST = 0x460e4668                           # its list: top, the cursor's place in the pane, its row, rows shown, rows
FONT, TEXT, BOX = 0x400ba876, 0x40012bd8, 0x40012254
WIDTHS, OFFSETS = 0x400c246a, 0x400c256a    # the small UI font's tables
BOX_ON, BOX_OFF = "\x16", "\x15"            # its checkbox glyphs, as PERSONALIZE draws them
NROWS = 15
B_X = 28                                    # a mono pair's second input, as the approved mockup put it


def be(v):
    return struct.pack(">I", v & 0xffffffff)


class Font:
    """The small UI font's text width, the rule of 0x40012f30: a glyph's
    width (3 where the table says 0), one pixel between glyphs, a missing
    glyph skipped."""

    def __init__(self, p):
        self.w = p.peek(WIDTHS, 256)
        self.o = struct.unpack(">256h", p.peek(OFFSETS, 512))

    def width(self, text):
        n = 0
        for ch in text.encode("latin1"):
            if self.o[ch] < 0:
                continue
            n += (1 if n else 0) + (self.w[ch] or 3)
        return n


def pair_fields(font, name, stereo, on):
    """A pair row's fields as (name, x, its box's x, on): the first box on
    one column whatever the pair is, B's name at B_X, STEREO's box on the
    value column (77)."""
    box1 = 4 + font.width(name + " ") + 1
    st_x = 77 - font.width("STEREO ") - 1
    if stereo:
        fields = [(name, 4, box1, on[0])]
    else:
        fields = [(name[0], 4, box1, on[0]), (name[1], B_X, B_X + font.width(name[1] + " ") + 1, on[1])]
    return fields + [("STEREO", st_x, 77, stereo)]


class Reference:
    def __init__(self, p, s):
        self.p = p
        self.code = s["stems_trace_buf"]        # 4 KB, written only while stems_trace is set
        self.valp = self.code + 0x400           # per row: its value's pointer; then the empty string's
        self.items = self.valp + 0x40           # per row: 0x60 bytes of items for its stub
        self.lblt = self.items + 0x600
        self.gett = self.lblt + 0x40
        self.strs = self.gett + 0x40
        code, self.sym = self._assemble()
        p.poke(self.code, code)
        p.poke(LABELS_AT, be(self.lblt))
        p.poke(GETTERS_AT, be(self.gett))
        self.font = Font(p)

    def _assemble(self):
        """draw_items (a0: {x, str}... -1, then {x1, x2}... -1: draws each
        string on the row, inverts each span, returns the empty string),
        then per row a value getter and a pair stub. PERSONALIZE's loop
        holds the surface in a3, the row's bar in a2 and its text's y in d4."""
        src = [".text", "draw_items:", " move.l %a0,-(%sp)",
               "1: move.l (%sp),%a0", " move.l (%a0)+,%d0", " bmi.s 3f", " move.l (%a0)+,%d1",
               " move.l %a0,(%sp)", " move.l %d1,-(%sp)", " pea -1", " move.l %d4,-(%sp)",
               " move.l %d0,-(%sp)", " move.l %a3,-(%sp)", f" pea {FONT:#x}", f" jsr {TEXT:#x}",
               " lea 24(%sp),%sp", " bra.s 1b",
               "3: move.l %a0,(%sp)",
               "4: move.l (%sp),%a0", " move.l (%a0)+,%d0", " bmi.s 5f", " move.l (%a0)+,%d1",
               " move.l %a0,(%sp)", " pea -1", " pea 6(%a2)", " move.l %d1,-(%sp)",
               " move.l %a2,-(%sp)", " move.l %d0,-(%sp)", " move.l %a3,-(%sp)", f" jsr {BOX:#x}",
               " lea 24(%sp),%sp", " bra.s 4b",
               "5: addq.l #4,%sp", f" move.l {self.valp + 4 * NROWS:#x},%d0", " rts"]
        for k in range(NROWS):
            src += [f"val{k}: move.l {self.valp + 4 * k:#x},%d0", " rts",
                    f"pair{k}: lea {self.items + 0x60 * k:#x},%a0", " bra.w draw_items"]
        d = pathlib.Path(tempfile.mkdtemp(prefix="stems_ref_"))
        try:
            (d / "r.s").write_text("\n".join(src) + "\n")
            subprocess.run(["m68k-elf-as", "-mcpu=54455", "-o", str(d / "r.o"), str(d / "r.s")], check=True)
            subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text", str(d / "r.o"), str(d / "r.bin")],
                           check=True)
            nm = subprocess.run(["m68k-elf-nm", str(d / "r.o")], check=True, capture_output=True, text=True).stdout
            sym = {n: self.code + int(a, 16) for a, _, n in (line.split() for line in nm.splitlines())}
            return (d / "r.bin").read_bytes(), sym
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def load(self, title, icon, rows, sel, field=None):
        """The title, the icon record's five longs and the rows into
        PERSONALIZE's place; `sel` the cursor's row (the bar's), `field`
        the field picked on it when it is a pair row (0, 1 or "ST")."""
        p, f = self.p, self.font
        assert len(rows) == NROWS
        strings = bytearray()

        def put(text):
            a = self.strs + len(strings)
            strings.extend(text.encode("latin1") + b"\0")
            return a

        empty = put("")
        lbl, get, valp = [], [], []
        for k, row in enumerate(rows):
            if row[0] == "text":
                lbl.append(put(row[1]))
                get.append(self.sym[f"val{k}"])
                valp.append(put(row[2]))
                continue
            _, name, stereo, on = row
            lbl.append(empty)
            get.append(self.sym[f"pair{k}"])
            valp.append(empty)
            fields = pair_fields(f, name, stereo, on)
            items = b"".join(be(x) + be(put(n)) + be(bx) + be(put(BOX_ON if v else BOX_OFF))
                             for n, x, bx, v in fields) + be(-1)
            if k == sel and field is not None:
                n, x, _, _ = fields[-1] if field == "ST" else fields[field]
                for a, b in ((3, x - 2), (x + f.width(n) + 1, 107)):  # all but x-1 .. x+width
                    if a <= b:
                        items += be(a) + be(b)
            items += be(-1)
            assert len(items) <= 0x60
            p.poke(self.items + 0x60 * k, items)
        assert len(strings) <= 0x800, len(strings)
        p.poke(self.strs, bytes(strings))
        p.poke(self.valp, b"".join(be(a) for a in valp + [empty]))
        p.poke(self.lblt, b"".join(be(a) for a in lbl))
        p.poke(self.gett, b"".join(be(a) for a in get))
        p.poke(TITLE, title.encode("latin1") + b"\0")
        p.poke(ICON_REC, b"".join(be(v) for v in icon))

    def place(self, top, row):
        """With PERSONALIZE open (it sets its list as it opens): STEMS's
        row count, pane and cursor. UP and DOWN move the cursor's place in
        the pane (+4) and set its row (+8, the one the draw marks) from it
        and the top, so both are set: opened again, PERSONALIZE kept place
        3 (measured under the port, 27 Oct 2026)."""
        self.p.poke(LIST + 16, be(NROWS))
        self.p.poke(LIST, be(top))
        self.p.poke(LIST + 4, be(row))
        self.p.poke(LIST + 8, be(row))
