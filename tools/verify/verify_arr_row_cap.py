#!/usr/bin/env python3
"""ARR ROW CAP under the ColdFire port: the arranger's row insert stops at 256 rows at END OF ARR. (#1257).

Boots out/mainos_bus.bin under --interactive (no card), points the open
arrangement at arrangement 1's working state in CS1 (0x10000004, 5652 bytes
an arrangement: 20 bytes, then 256 rows of 22), plants a row count and a
marker over arrangement 2's first 22 bytes, and calls stock's insert
0x4009e4c8(row) as the arranger does. Checked:

- 100 rows, insert at END OF ARR.: 101 rows (the append still works);
- 255 rows, insert at END OF ARR.: 256 rows, the marker intact;
- 256 rows, insert at END OF ARR.: still 256, the marker intact, ROW LIMIT
  REACHED shown (the toast routine 0x4005a2b8 called with 0x400b94ab);
- 256 rows, insert in the middle (row 10): still 256 (stock's own check).

On stock 1.40C the third case writes row 257 over the marker and reads 257.
SKIPs when the remix has no ARR ROW CAP or the port is not built. What this
cannot see: the arranger's panel and its redraw (the insert is called, not
pressed), and a save (the files follow the RAM state).
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
INSERT = 0x4009E4C8
TOAST = 0x4005A2B8
FULL_TEXT = 0x400B94AB          # "ROW LIMIT REACHED"
OPEN_ARR = 0x10000000           # pointer to the open arrangement's working state
ARR1 = 0x10000004
ARR_SIZE = 5652
COUNT = 18                      # word, the row count
ROW0, ROW = 20, 22
MARK = bytes(range(0xA0, 0xA0 + ROW))


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_arr_row_cap: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_arr_row_cap: no out/mainos_bus.bin (make bus)")
        return 1
    remix = os.environ.get("REMIX") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if "ARR ROW CAP" not in registry.remix(remix).modules:
        print("  [SKIP] verify_arr_row_cap: the remix has no ARR ROW CAP")
        return 0
    emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--interactive", "--main-level", "off"],
                           cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    fails = []

    def check(what, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + detail if detail else ''}")
        if not ok:
            fails.append(what)

    def reply():
        while True:
            line = emu.stdout.readline()
            if not line:
                raise RuntimeError("the port exited")
            if line.startswith(("ready", "ok", "err", "peek", "status", "hits")):
                return line.split()

    def cmd(c):
        emu.stdin.write(c + "\n")
        emu.stdin.flush()
        r = reply()
        if r[0] == "err":
            raise RuntimeError(f"{c}: {' '.join(r)}")
        return r

    def peek(addr, n):
        return bytes.fromhex(cmd(f"peek {addr:#x} {n}")[1])

    def poke(addr, data):
        for i in range(0, len(data), 4096):          # the port takes up to 4096 bytes a poke
            cmd(f"poke {addr + i:#x} {data[i:i + 4096].hex()}")

    def count():
        return int.from_bytes(peek(ARR1 + COUNT, 2), "big")

    def setup(n):
        poke(OPEN_ARR, ARR1.to_bytes(4, "big"))
        poke(ARR1 + COUNT, n.to_bytes(2, "big"))
        row = bytes([0, 0x20, 0, 0, 0, 0, 0, 0, 0xff, 0xff, 0, 0, 0, 0x40] + [0] * 8)   # a C01 000-064 row
        poke(ARR1 + ROW0, row * n)
        poke(ARR1 + ARR_SIZE, MARK)

    def insert(row):
        cmd(f"watch {TOAST:#x}")
        cmd("hits")
        cmd(f"call {INSERT:#x} {row}")
        cmd("run 20")
        hits = cmd("hits")
        cmd("watch off")
        n = int(hits[1].split("=")[1])
        args = [h.split(":") for h in hits[2:]]
        return any(int(a[8], 16) == FULL_TEXT for a in args if len(a) > 8) if n else False

    try:
        reply()
        cmd("run 3000")
        setup(100)
        full = insert(100)
        check(f"100 rows, insert at END OF ARR.: {count()} rows, want 101", count() == 101 and not full)
        setup(255)
        full = insert(255)
        check(f"255 rows, insert at END OF ARR.: {count()} rows, want 256", count() == 256 and not full)
        check("... arrangement 2's first 22 bytes unchanged", peek(ARR1 + ARR_SIZE, ROW) == MARK)
        setup(256)
        full = insert(256)
        check(f"256 rows, insert at END OF ARR.: {count()} rows, want 256", count() == 256)
        check("... arrangement 2's first 22 bytes unchanged", peek(ARR1 + ARR_SIZE, ROW) == MARK,
              peek(ARR1 + ARR_SIZE, ROW).hex())
        check("... ROW LIMIT REACHED is shown", full)
        setup(256)
        full = insert(10)
        check(f"256 rows, insert in the middle (row 10): {count()} rows, want 256 (stock's check)",
              count() == 256 and full)
    except Exception as e:  # noqa: BLE001 -- a hang or a fault is the finding
        check(f"the probe completed ({type(e).__name__}: {e})", False)
    finally:
        try:
            cmd("quit")
            emu.wait(timeout=30)
        except Exception:  # noqa: BLE001
            emu.kill()
    print(f"verify_arr_row_cap: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
