#!/usr/bin/env python3
"""The port's panel, one key at a time, for a gate (STEM REC piece 3).

    from stems_panel import MenuPort
    with MenuPort(image, card, "STEMS", "ULTFX", mkii=True) as p:
        p.settle()                  # CLOCK RECEIVE cleared, the date prompt dismissed, frames on
        p.open_menu()               # PROJ on an MKII, FUNC+MIXER on an MKI
        p.press("down")
        p.png("out/stems_runs/menu.png")

Built on tools/panel/panel_server.py's PortProc and PortRt (`ot_emu
--interactive`: `run <ms>`, `key <row> <mask>`, `peek`, `poke`) and
panel_link.PanelLink (the screen, decoded from the bytes the CPU sends the
panel). Emulated time advances only in run(), in exact steps, so a run is
deterministic. A key is a bit in its matrix row, and the port takes a row's
whole bitmap, so held keys are kept per row. Key names:
tools/panel/key_map.json."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "tools" / "panel"))
from panel_link import PanelLink  # noqa: E402
from panel_server import PORT_BIN, PortProc, PortRt  # noqa: E402

KEYS = json.loads((ROOT / "tools/panel/key_map.json").read_text())["keys"]
MENU_FOCUS = 0x400cbda8     # the list descriptor the menu's cursor is in (MAINMENU.md 4)


def diff_box(a, b):
    """The box around every pixel that differs between two screens, as
    (x0, x1, y0, y1), or None when they are the same."""
    pts = [(x, y) for y in range(64) for x in range(128) if a[y][x] != b[y][x]]
    if not pts:
        return None
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    return min(xs), max(xs), min(ys), max(ys)


class MenuPort:
    def __init__(self, image, card, set_name, project, mkii, log_path=None, extra=()):
        self.mkii = mkii
        # --mount makes the port's boot post the card mount and LOAD PROJECT
        # (panel_server.py's _port_argv): without it --set/--project load
        # nothing, the set path stays empty, and a take fails on its folder
        # (29 Sep 2026: PATH FAILED in the gate's first key-driven take).
        argv = [str(PORT_BIN), "--image", str(image), "--card", str(card), "--mount", "--set", set_name,
                "--project", project, "--internal-clock", "--load-ms", "20000", "--dsp", "--card-rw",
                "--interactive", *(["--mkii"] if mkii else []), *extra]
        self.proc = PortProc(argv, log_path=log_path)
        self.proc.wait_ready(900)
        self.rt = PortRt(self.proc)
        self.link = PanelLink()
        self.pos = 0
        self.held = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self.proc.command("quit", "ok", timeout=60)
        except Exception:
            self.proc.kill()

    def run(self, ms):
        self.rt.run(ms=ms)
        self.rt.poll_tx()
        tx = self.rt.uart64.tx
        self.link.feed(bytes(tx[self.pos:]))
        self.pos = len(tx)

    def key(self, name, down):
        row, bit = KEYS[name]
        m = self.held.get(row, 0)
        m = m | (1 << bit) if down else m & ~(1 << bit)
        self.held[row] = m
        self.proc.command(f"key {row:#x} {m:#x}", "ok")

    def press(self, name, hold=60, settle=200):
        self.key(name, True)
        self.run(hold)
        self.key(name, False)
        self.run(settle)

    def chord(self, hold_name, name, settle=300):
        self.key(hold_name, True)
        self.run(60)
        self.press(name, settle=60)
        self.key(hold_name, False)
        self.run(settle)

    def settle(self):
        """What the panel server does before play (panel_server.py): CLOCK
        RECEIVE cleared, 300 ms, the boot's SET DATE/TIME prompt dismissed
        with NO, then the frame interrupt on for good, so PLAY steps the
        sequencer."""
        self.rt.internal_clock()
        self.run(300)
        self.press("no", settle=300)
        self.rt.frame = True
        self.run(300)

    def open_menu(self):
        if self.mkii:
            self.press("proj", settle=400)
        else:
            self.chord("func", "mixer", settle=400)

    def peek(self, addr, n):
        return bytes(self.rt.uc.mem_read(addr, n))

    def long(self, addr):
        return int.from_bytes(self.peek(addr, 4), "big")

    def cstr(self, addr, n=32):
        return self.peek(addr, n).split(b"\0")[0].decode("latin1")

    def poke(self, addr, data):
        self.rt.uc.mem_write(addr, bytes(data))

    def screen(self):
        return [list(r) for r in self.link.lcd_rows()]

    def png(self, path):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.link.render_png(3))

    def card_flush(self):
        return self.proc.command("card flush", "card")
