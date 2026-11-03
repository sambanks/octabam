#!/usr/bin/env python3
"""SCREENSHOT under the port: the Elektron screenshot SysEx request is
answered on MIDI OUT with the LCD plane, and everything else still reaches
stock.

Builds the `screenshot` remix, boots it on a staged project, and injects at
emulated frame 395 of 400 (the plane changes at the playhead, so it is read
at the run's end):

  1. `F0 00 20 3C 10 00 00 00 01 00 00 04 F7` (screendump's default probe)
     and `... 05 00 ...` (the OT's own id): each draws exactly one reply.
  2. The reply: the request's two id bytes, then 7-bit groups that decode to
     msgId, replyTo = the request's msgId, cmd 0x84, ver 1, 128 x 64, len 1024,
     1,024 pixel bytes, then F7; 1,194 bytes.
  3. The pixels are the firmware's plane (`--mem-dump 0x46c7e0ea`) within the
     playhead's few bytes, and unpacked column-major (row 0 at the least
     significant bit) equal the PANEL.md reading of the plane.
  4. A request with a different cmd, a different manufacturer id and one
     stock SysEx message (`F0 00 20 3C 05 00 50 ...`) draw no reply.
  5. The `screenshot-usb` remix (USB + SCREENSHOT): the request sent as USB-MIDI
     events on EP2 OUT is answered on EP2 IN only (the same reply, 1,194 bytes
     in 1,592 bytes of events; nothing on DIN), the pixels equal the plane
     exactly (nothing animates without the sequencer), and a request on DIN in
     that image is still answered on DIN only.

The 7-bit decoder and the unpacker here are written from the format
(MSB-first leader byte per 7 data bytes; each column is two big-endian
32-bit words, row y at bit y), not from any other implementation.
"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "tools/emu"))
import toolpath  # noqa: E402,F401
import emu_card  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
PLANE = 0x46c7e0ea
REQ_BODY = "00 00 01 00 00 04"


def decode7(b):
    out = bytearray()
    for i in range(0, len(b), 8):
        lead, grp = b[i], b[i + 1:i + 8]
        out += bytes(x | (0x80 if lead >> (6 - j) & 1 else 0) for j, x in enumerate(grp))
    return bytes(out)


def unpack(px, w, h):
    stride = (h + 31) // 32
    g = [[0] * w for _ in range(h)]
    for x in range(w):
        v = int.from_bytes(px[x * stride * 4:(x + 1) * stride * 4], "big")
        for y in range(h):
            g[y][x] = v >> (stride * 32 - h + y) & 1
    return g


def plane_grid(plane):
    """PANEL.md: 128 rows of 8 bytes, MSB left; pixel (x, y) = column 63-y of row x."""
    return [[plane[x * 8 + (63 - y) // 8] >> (7 - (63 - y) % 8) & 1 for x in range(128)] for y in range(64)]


def events(raw):
    """USB-MIDI event packets (cable 0) for one SysEx."""
    out = b""
    for i in range(0, len(raw), 3):
        c = raw[i:i + 3]
        cin = 4 if len(c) == 3 and i + 3 < len(raw) else {1: 5, 2: 6, 3: 7}[len(c)]
        out += bytes([cin]) + c + bytes(3 - len(c))
    return out


def unevents(d):
    ln = {4: 3, 5: 1, 6: 2, 7: 3}
    return b"".join(d[i + 1:i + 1 + ln[d[i] & 15]] for i in range(0, len(d), 4))


def build(remix, work):
    import os
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT,
                       env={**os.environ, "REMIX": remix, "XBUS": "1", "SPEC": "1"}, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    img = work / f"{remix}.bin"
    img.write_bytes((ROOT / "out/mainos_bus.bin").read_bytes())
    return img


def main():
    work = pathlib.Path(tempfile.mkdtemp(prefix="screenshot_"))
    image = build("screenshot", work)
    src = pathlib.Path(open(pathlib.Path.home() / ".octabam_project").read().strip())
    card, _ = emu_card.stage_project(src, "OCTABAM", "BASS", tree=work / "tree")
    (work / "card.img").write_bytes(card)

    fails = []

    def check(label, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
        if not ok:
            fails.append(label)

    def run(name, msgs, img=image):
        mid = work / f"{name}.in"
        mid.write_text("".join(f"395 {m}\n" for m in msgs))
        out, dump = work / f"{name}.out", work / f"{name}.fb"
        cmd = [str(EMU), "--image", str(img), "--card", str(work / "card.img"),
               "--set", "OCTABAM", "--project", "BASS", "--mkii", "--sequencer", "--internal-clock",
               "--frames", "400", "--load-ms", "90000", "--midi", str(mid), "--midi-out", str(out),
               "--mem-dump", f"{PLANE:#x},1024={dump}"]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout[-1500:]
        return (out.read_bytes() if out.exists() else b""), dump.read_bytes()

    for ident in ("10 00", "05 00"):
        got, plane = run("id" + ident[:2], [f"f0 00 20 3c {ident} {REQ_BODY} f7"])
        check(f"{ident}: one reply of 1,194 bytes", len(got) == 1194, f"{len(got)} bytes")
        check(f"{ident}: F0 00 20 3C + the request's id bytes, F7 last",
              got[:6] == bytes.fromhex("f0 00 20 3c " + ident) and got[-1:] == b"\xf7")
        body = decode7(got[6:-1])
        check(f"{ident}: msgId?, replyTo 1, cmd 0x84, ver 1, 128 x 64, len 1024",
              body[2:14] == bytes.fromhex("0001 84 01 0080 0040 00000400"), body[:14].hex(" "))
        px = body[14:]
        check(f"{ident}: 1,024 pixel bytes", len(px) == 1024, f"{len(px)}")
        diff = sum(a != b for a, b in zip(px, plane))
        check(f"{ident}: pixels = the firmware plane (playhead aside)", diff <= 16, f"{diff} bytes differ")
        gp, gl = unpack(px, 128, 64), plane_grid(plane)
        bad = sum(gp[y][x] != gl[y][x] for y in range(64) for x in range(128))
        check(f"{ident}: column-major unpack = PANEL.md reading", bad <= 64, f"{bad} pixels differ")
        check(f"{ident}: not blank, not full", 0 < sum(map(sum, gp)) < 128 * 64)
        if ident == "10 00":
            ref = got
    for name, msg in (("cmd05", "f0 00 20 3c 10 00 00 00 01 00 00 05 f7"),
                      ("othermfr", "f0 00 20 3d 10 00 00 00 01 00 00 04 f7"),
                      ("stock50", "f0 00 20 3c 05 00 50 00 00 00 00 04 f7")):
        got, _ = run(name, [msg])
        check(f"{name}: no screenshot reply", len(got) != 1194, f"{len(got)} bytes")

    # ---- USB
    import os
    sys.path.insert(0, str(ROOT / "tools/harness"))
    import usb_host
    uimg = build("screenshot-usb", work)
    sock = f"/tmp/ot-screenshot-{os.getpid()}.sock"
    din_out, fb = work / "usb.dout", work / "usb.fb"
    with (work / "usb.log").open("w") as lf:
        emu = subprocess.Popen([str(EMU), "--image", str(uimg), "--usb-host", sock, "--usb-hold-ms", "60000",
                                "--midi-out", str(din_out), "--mem-dump", f"{PLANE:#x},1024={fb}"],
                               cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
    data = b""
    try:
        import time
        b = usb_host.Bench(sock, timeout=60.0)
        usb_host.enumerate_device(b, hs=True)
        b.ep_out(2, events(bytes.fromhex("f0 00 20 3c 10 00 " + REQ_BODY + " f7")))
        time.sleep(3)
        data = b.ep_in(2, 4096, timeout=20)
        b.sock.close()
    except Exception as e:  # noqa: BLE001
        check(f"usb: the host script completed ({type(e).__name__}: {e})", False)
    emu.wait(timeout=180)
    check("usb: reply is 1,592 bytes of events", len(data) == 1592, f"{len(data)}")
    raw = unevents(data) if len(data) % 4 == 0 and data else b""
    check("usb: 1,194 MIDI bytes, F0 00 20 3C 10 00 ... F7", len(raw) == 1194 and raw[:6] == bytes.fromhex("f0 00 20 3c 10 00") and raw[-1:] == b"\xf7")
    body = decode7(raw[6:-1]) if raw else b""
    check("usb: replyTo 1, cmd 0x84, ver 1, 128 x 64, len 1024", body[2:14] == bytes.fromhex("0001 84 01 0080 0040 00000400"), body[:14].hex(" "))
    check("usb: pixels = the plane exactly", len(body) == 1038 and body[14:] == fb.read_bytes() if fb.exists() else False)
    check("usb: nothing on DIN", not din_out.exists() or din_out.stat().st_size == 0)
    got, _ = run("usbdin", [f"f0 00 20 3c 10 00 {REQ_BODY} f7"], img=uimg)
    check("usb image, request on DIN: answered on DIN", len(got) == 1194, f"{len(got)} bytes")
    print("verify_screenshot:", "FAIL " + ", ".join(fails) if fails else "ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
