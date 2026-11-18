#!/usr/bin/env python3
"""The card and the image, driven over USB through REMOTE (modules/remote/README.md): no panel step.

    python3 tools/hw/ot_card.py fingerprint
    python3 tools/hw/ot_card.py load  <project-dir> [--name NAME]    # put a project on the card, leave DISK MODE
    python3 tools/hw/ot_card.py boot  "<NAME>.RMX"                   # switch image through REMIX SWITCH
    python3 tools/hw/ot_card.py copy  <file> [<file> ...]            # files into /BRAIN/REMIXES/, then rescan

`load` enters USB DISK MODE (COMMAND 1), waits for the card to mount, replaces PRESETS/<NAME> with the project,
removes the `._*` files the copy writes, syncs, compares every file, unmounts, and leaves DISK MODE (COMMAND 2).
Leaving reloads the unit's current project from the card, so NAME must be the project the unit has loaded
(default RMT_SFX_01). Load it from the panel once to start; every later load is this command. The replaced
directory is the one NAME names under PRESETS and nothing else.

`boot` sends COMMAND 3 and waits for the unit to leave the bus and return. A unit that does not return in
--wait seconds is stopped on the boot screen (FAILURE_MODES.md): power-cycle it.

`fingerprint` prints the ring header's three addresses (RMT_TRACE, REMIX SWITCH's name list and its count). They
are linked addresses, so they differ between images; compare with the line a build's own run printed to see which
image is running. Nothing over USB carries the image's name.

Needs pyusb and libusb (load_meter.py) and an image with REMOTE, STORE, USB and, for `boot`, REMIX SWITCH.
"""
import argparse
import filecmp
import os
import shutil
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ot_events as ev  # noqa: E402

CARD = "/Volumes/OCTATRACK"
DEFAULT_NAME = "RMT_SFX_01"


class Unit:
    """The unit's REMOTE requests, reopened after every reset or DISK MODE change."""

    def __init__(self):
        self.dev = None
        self.open()

    def open(self):
        import load_meter
        self.dev = load_meter.libusb_device()
        self.ctrl, self.peek1, self.cmd1 = ev.unit_ctrl(self.dev), ev.unit_peek(self.dev), ev.unit_command(self.dev)

    def present(self):
        try:
            self.open()
            ev.read_bytes(self.ctrl, 0, 32)
            return True
        except (SystemExit, Exception):  # noqa: BLE001
            return False

    def wait_present(self, timeout, gone_first=False):
        t0 = time.monotonic()
        if gone_first:
            while self.present():
                if time.monotonic() - t0 > timeout:
                    return False
                time.sleep(0.5)
        while time.monotonic() - t0 < timeout:
            if self.present():
                return True
            time.sleep(1.0)
        return False

    def fingerprint(self):
        h = struct.unpack(">8I", ev.read_bytes(self.ctrl, 0, 32))
        return tuple(f"0x{x:08x}" for x in h[4:7])

    def command(self, cid, arg=0):
        return ev.command(self.cmd1, cid, arg)


def mount_card():
    """The Mac does not always mount the card on its own after COMMAND 1 (seen 18 Nov 2026 after an image switch)."""
    out = subprocess.run(["diskutil", "list", "external"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "OCTATRACK" in line and "Windows_FAT" in line:
            subprocess.run(["diskutil", "mount", line.split()[-1]], capture_output=True)
            return


def wait_card(mounted, timeout=60):
    t0 = time.monotonic()
    last = 0.0
    while time.monotonic() - t0 < timeout:
        if os.path.isdir(os.path.join(CARD, "BRAIN")) == mounted:
            return True
        if mounted and time.monotonic() - t0 > 8 and time.monotonic() - last > 4:
            mount_card()
            last = time.monotonic()
        time.sleep(0.5)
    return False


DISK_FLAG = 0x460e76a0          # nonzero while the unit is in USB DISK MODE (modules/remote/README.md)


def enter_disk(u, attempts=4):
    """COMMAND 1 and the card's mount. The unit sometimes clears the flag within 4 s and the card never appears
    (18 Nov 2026, `octabam-bus` 05 and, later, `octabam-verbs` 05 and `octabam` 05); each attempt is logged."""
    if os.path.isdir(os.path.join(CARD, "BRAIN")):
        return
    for n in range(1, attempts + 1):
        taken = u.command(ev.CMD_DISK_ENTER)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 30:
            if wait_card(True, timeout=2):
                return
            if time.monotonic() - t0 > 8:
                mount_card()
            try:
                flag = ev.peek(u.peek1, DISK_FLAG, 4)[0]
            except (SystemExit, Exception):  # noqa: BLE001
                flag = None
            if flag == 0 and time.monotonic() - t0 > 6:
                break
        print(f"attempt {n}: COMMAND 1 {'taken' if taken else 'refused'}, disk-mode flag {flag}, no card after {time.monotonic() - t0:.0f} s")
        time.sleep(3.0)
    sys.exit(f"{CARD} did not mount in {attempts} attempts")


def leave_disk(u):
    os.chdir("/")
    for _ in range(10):
        r = subprocess.run(["diskutil", "unmount", CARD], capture_output=True, text=True)
        if r.returncode == 0:
            break
        time.sleep(1.0)
    else:
        sys.exit(f"could not unmount {CARD}: {r.stderr.strip()}")
    # `diskutil unmount` leaves the device node (`diskN`) on the Mac: after it, every later COMMAND 1 enters DISK MODE
    # on the unit (BANKW in the ring) and the Mac never mounts the card (18 Nov 2026). Ejecting removes the node.
    for line in subprocess.run(["diskutil", "list", "external"], capture_output=True, text=True, timeout=30).stdout.splitlines():
        if "OCTATRACK" in line and "Windows_FAT" in line:
            disk = line.split()[-1].rsplit("s", 1)[0]
            subprocess.run(["diskutil", "eject", disk], capture_output=True, timeout=60)
    if not u.command(ev.CMD_DISK_LEAVE):
        sys.exit("COMMAND 2 refused")


def same_tree(a, b):
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(same_tree(os.path.join(a, d), os.path.join(b, d)) for d in cmp.common_dirs)


def wait_running(u, timeout=90.0):
    """Seconds until LOAD METER's health rule holds (the DSP's frame count advances, the frame interrupt keeps its
    rate), or None at the timeout. The count is 0 a second for a while after a project load or a boot: a phase that
    starts first reads a stopped DSP (18 Nov 2026: `pc-soak`, `kits-identity` and `scenes-sweep` each failed in under
    3 s, back to back, right after a load)."""
    import load_meter
    t0 = time.monotonic()
    why = "no reading"
    while time.monotonic() - t0 < timeout:
        try:
            ok, why = load_meter.healthy(u.dev)
            if ok:
                return time.monotonic() - t0
        except (SystemExit, Exception) as e:  # noqa: BLE001
            why = str(e)
        time.sleep(1.0)
    print(f"the unit is not running normally after {timeout:.0f} s: {why}")
    return None


def cmd_load(a):
    src = os.path.abspath(a.project)
    if not os.path.isfile(os.path.join(src, "project.work")):
        sys.exit(f"{src} has no project.work")
    if "/" in a.name or a.name in ("", ".", ".."):
        sys.exit("--name is a directory name under PRESETS")
    u = Unit()
    head0 = ev.Events(u.ctrl).head()
    enter_disk(u)
    dst = os.path.join(CARD, "PRESETS", a.name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    subprocess.run(["dot_clean", "-m", dst], check=True)
    subprocess.run(["sync"], check=True)
    if not same_tree(src, dst):
        sys.exit(f"{dst} differs from {src} after the copy; nothing was left")
    print(f"card: PRESETS/{a.name} equals {src}")
    leave_disk(u)
    if not u.wait_present(a.wait):
        sys.exit(f"the unit did not answer {a.wait} s after leaving DISK MODE")
    r = ev.Events(u.ctrl, from_start=True)
    r.seen = head0                  # records written by this reload only
    try:
        rec = r.wait_for(("NEWPROJ", "LOADMASK"), timeout=a.wait)
    except TimeoutError as e:
        print(f"the unit did not reload the project ({e}); is {a.name} the project it has loaded?")
        return 1
    print("the unit reloaded the project:", rec["name"], rec["arg"])
    t = wait_running(u)
    if t is None:
        return 1
    print(f"the DSP's frame count advances {t:.1f} s after the reload record")
    return 0


def wait_list(u, name=None, timeout=45):
    """REMIX SWITCH's list once the scan has filled it (a few seconds after COMMAND 4, and after DISK MODE ends)."""
    t0 = time.monotonic()
    while True:
        names = ev.remixes(u.ctrl, u.peek1)
        if names and (name is None or name.encode() in names):
            return names
        if time.monotonic() - t0 > timeout:
            return names
        time.sleep(1.0)


def cmd_copy(a):
    u = Unit()
    enter_disk(u)
    dst = os.path.join(CARD, "BRAIN", "REMIXES")
    for f in a.files:
        d = os.path.join(dst, os.path.basename(f))
        shutil.copyfile(f, d)
        subprocess.run(["dot_clean", "-m", dst], check=True)
        if not filecmp.cmp(f, d, shallow=False):
            sys.exit(f"{d} differs from {f}")
        print("card:", os.path.basename(f))
    subprocess.run(["sync"], check=True)
    leave_disk(u)
    if not u.wait_present(a.wait):
        sys.exit("the unit did not answer after leaving DISK MODE")
    for _ in range(30):             # refused while COMMAND 2's routine is still pending
        if u.command(ev.CMD_SCAN):
            break
        time.sleep(1.0)
    else:
        sys.exit("COMMAND 4 refused for 30 s")
    names = wait_list(u)
    print([n.decode() for n in names])
    return 0


def cmd_boot(a):
    u = Unit()
    before = u.fingerprint()
    if a.name.encode() not in wait_list(u, a.name, timeout=5):
        u.command(ev.CMD_SCAN)      # a fresh image's list stays empty until a scan
        wait_list(u, a.name)
    if not ev.boot(u.cmd1, u.ctrl, u.peek1, a.name):
        sys.exit(f"{a.name}: refused or not in the unit's list (run `copy` or COMMAND 4 first)")
    print(f"COMMAND 3 taken for {a.name}; waiting for the unit to leave and return (up to {a.wait} s)")
    if not u.wait_present(a.wait, gone_first=True):
        print(f"STOPPED ON THE BOOT SCREEN? no answer in {a.wait} s: power-cycle the unit and record it in FAILURE_MODES.md")
        return 1
    t = wait_running(u)
    if t is None:
        return 1
    after = u.fingerprint()
    print(f"the DSP's frame count advances {t:.1f} s after the unit returned")
    print("fingerprint", before, "->", after, "(changed)" if after != before else "(same: the image did not change, or both share addresses)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fingerprint")
    p = sub.add_parser("load")
    p.add_argument("project")
    p.add_argument("--name", default=DEFAULT_NAME)
    p.add_argument("--wait", type=float, default=90.0)
    p = sub.add_parser("copy")
    p.add_argument("files", nargs="*", help="none: only rescan the list")
    p.add_argument("--wait", type=float, default=90.0)
    p = sub.add_parser("boot")
    p.add_argument("name")
    p.add_argument("--wait", type=float, default=150.0)
    a = ap.parse_args()
    if a.cmd == "fingerprint":
        print(*Unit().fingerprint())
        return 0
    return {"load": cmd_load, "copy": cmd_copy, "boot": cmd_boot}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
