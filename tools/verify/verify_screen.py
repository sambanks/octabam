#!/usr/bin/env python3
"""SCREEN under the port: the Elektron screenshot SysEx request is
answered on MIDI OUT with the frame the panel shows, and everything else
still reaches stock.

The truth the pixels are held to is the panel link itself: the port's
UART1 stream (`--serial-out`, `.a`) decoded by `tools/panel/panel_link.py`
(PANEL.md section 9), not the page plane 0x46c7e0ea. The plane is only the
page layer; MIXER, the menus, SETUP windows and popups are other layers the
flush composites into the back buffer it sends (on a unit, 4 Nov 2026: a
reply read from the plane showed the page screens only).

  0. Windows, no project needed: on an empty card the boot raises the
     "NOT WORKING IN ANY PROJECT" popup; a request then, and one after YES
     and MIXER, are answered with a frame the panel stream reached, and
     the last frame differs from the plane by over 1,000 pixels (so the
     check can see a reply read from the plane).

"A frame the panel was sent, near the last": the stream is decoded a byte
at a time and the reply's 1,024 bytes must equal the decoder's frame at
some point, exactly (the reply is copied between two flushes), and be
within NEAR pixels of the last frame (an early frame alone would let the
page plane through: it is what the panel showed before the window).

Then it boots the `screen` remix on a staged project, and injects at
emulated frame 395 of 400 (the screen changes at the playhead, so it is
read at the run's end):

  1. `F0 00 20 3C 10 00 00 00 01 00 00 04 F7` (screendump's default probe)
     and `... 05 00 ...` (the OT's own id): each draws exactly one reply.
  2. The reply: the request's two id bytes, then 7-bit groups that decode to
     msgId, replyTo = the request's msgId, cmd 0x84, ver 1, 128 x 64, len 1024,
     1,024 pixel bytes, then F7; 1,194 bytes.
  3. The pixels, unpacked column-major (row 0 at the least significant
     bit), are a frame the panel was sent, near the last.
  4. A request with a different cmd, a different manufacturer id and one
     stock SysEx message (`F0 00 20 3C 05 00 50 ...`) draw no reply.
  5. The `screen-usb` remix (USB + SCREEN): the request sent as USB-MIDI
     events on EP2 OUT is answered on EP2 IN only (the same reply, 1,194 bytes
     in 1,592 bytes of events; nothing on DIN), the pixels are a frame the
     panel was sent, near the last, and a request on DIN in
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
sys.path.insert(0, str(ROOT / "tools/verify"))
import gate_cache  # noqa: E402
sys.path.insert(0, str(ROOT / "tools/panel"))
from panel_link import PanelLink  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
PLANE = 0x46c7e0ea
# A frame the stream reached is not enough on its own: before a window is
# drawn the panel shows the page, so a reply read from the plane matches an
# early frame (measured: the pre-fix build passed that alone). The reply
# must also be within NEAR pixels of the last frame. Measured 4 Nov 2026:
# fixed 0 (popup, MIXER) and 45-47 (USB, redrawn after the reply); the
# plane-reading build 2,314, 3,132 and 2,188.
NEAR = 200
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


def panel_grid(path):
    """The frame the panel was sent: the port's UART1 stream, decoded."""
    link = PanelLink()
    link.feed(path.read_bytes() if path.exists() else b"")
    return [[1 if v else 0 for v in row] for row in link.lcd_rows()]


def panel_match(path, px):
    """Whether the reply's 1,024 bytes are a frame the panel stream reached.
    The stream is fed a byte at a time and the decoder's frame compared
    after each: the reply is copied between two flushes, so it is the state
    after one, whatever the run did after it. The reply's byte x*8 + p is
    panel page p of column x; PanelLink keeps page-major frame[p*128 + x]."""
    if len(px) != 1024:
        return False
    want = bytes(px[x * 8 + p] for p in range(8) for x in range(128))
    link = PanelLink()
    data = path.read_bytes() if path.exists() else b""
    for i in range(len(data)):
        link.feed(data[i:i + 1])
        if link.frame == want:
            return True
    return False


def differ(a, b):
    return sum(a[y][x] != b[y][x] for y in range(64) for x in range(128))


def reply_pixels(got):
    body = decode7(got[6:-1]) if len(got) == 1194 else b""
    return unpack(body[14:], 128, 64) if len(body) == 1038 else None


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
    work = pathlib.Path(tempfile.mkdtemp(prefix="screen_"))
    image = build("screen", work) if gate_cache.project_dir() else None
    src = gate_cache.project_dir()
    have_project = src is not None and src.is_dir()
    if have_project:
        card, _ = emu_card.stage_project(src, "OCTABAM", "BASS", tree=work / "tree")
        (work / "card.img").write_bytes(card)
    else:
        print("  [SKIP] verify_screen: the DIN checks need a project (OT_PROJECT=<dir> or ~/.octabam_project); the USB checks run without one")

    fails = []

    def check(label, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
        if not ok:
            fails.append(label)

    def run(name, msgs, img=image):
        mid = work / f"{name}.in"
        mid.write_text("".join(f"395 {m}\n" for m in msgs))
        out, dump, ser = work / f"{name}.out", work / f"{name}.fb", work / f"{name}.ser"
        cmd = [str(EMU), "--image", str(img), "--card", str(work / "card.img"),
               "--set", "OCTABAM", "--project", "BASS", "--mkii", "--sequencer", "--internal-clock",
               "--frames", "400", "--load-ms", "90000", "--midi", str(mid), "--midi-out", str(out),
               "--mem-dump", f"{PLANE:#x},1024={dump}", "--serial-out", str(ser)]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout[-1500:]
        return (out.read_bytes() if out.exists() else b""), dump.read_bytes(), panel_grid(work / f"{name}.ser.a")

    # ---- 0. windows: the boot popup and MIXER, on an empty card (no project needed)
    import emu_card as ec
    (work / "empty" / "OCTABAM" / "AUDIO").mkdir(parents=True, exist_ok=True)
    (work / "empty.img").write_bytes(ec.build_image(str(work / "empty"), size_mb=64))
    wimg = image or build("screen", work)
    req = f"midi f0 00 20 3c 10 00 {REQ_BODY} f7"
    # live-script key codes are (row - 0x20) * 8 + bit (tools/panel/key_map.json): YES 0x31, MIXER 0x30
    for name, script in (("popup", [f"1500 {req}", "3000 quit"]),
                         ("mixer", ["1500 key 0x31 down", "1530 key 0x31 up", "2500 key 0x30 down",
                                    "2530 key 0x30 up", f"3500 {req}", "5000 quit"])):
        (work / f"{name}.script").write_text("\n".join(script) + "\n")
        out, dump, ser = work / f"{name}.out", work / f"{name}.fb", work / f"{name}.ser"
        r = subprocess.run([str(EMU), "--image", str(wimg), "--card", str(work / "empty.img"), "--mkii",
                            "--live-script", str(work / f"{name}.script"), "--midi-out", str(out),
                            "--serial-out", str(ser), "--mem-dump", f"{PLANE:#x},1024={dump}"],
                           cwd=ROOT, capture_output=True, text=True)
        ok = r.returncode == 0 and "ended on quit" in r.stdout
        check(f"{name}: the run ended on quit", ok, "" if ok else r.stdout[-300:])
        got = out.read_bytes() if out.exists() else b""
        check(f"{name}: one reply of 1,194 bytes", len(got) == 1194, f"{len(got)} bytes")
        gp, gs = reply_pixels(got), panel_grid(work / f"{name}.ser.a")
        gl = plane_grid(dump.read_bytes()) if dump.exists() else None
        d = differ(gp, gs) if gp else -1
        check(f"{name}: pixels = a frame the panel was sent, near the last",
              panel_match(work / f"{name}.ser.a", decode7(got[6:-1])[14:]) and 0 <= d <= NEAR,
              f"{d} pixels differ from the last")
        dl = differ(gs, gl) if gl else -1
        check(f"{name}: that frame is not the page plane (a window is up)", dl > 1000, f"{dl} pixels differ")

    for ident in (("10 00", "05 00") if have_project else ()):
        got, plane, gs = run("id" + ident[:2], [f"f0 00 20 3c {ident} {REQ_BODY} f7"])
        check(f"{ident}: one reply of 1,194 bytes", len(got) == 1194, f"{len(got)} bytes")
        check(f"{ident}: F0 00 20 3C + the request's id bytes, F7 last",
              got[:6] == bytes.fromhex("f0 00 20 3c " + ident) and got[-1:] == b"\xf7")
        body = decode7(got[6:-1])
        check(f"{ident}: msgId?, replyTo 1, cmd 0x84, ver 1, 128 x 64, len 1024",
              body[2:14] == bytes.fromhex("0001 84 01 0080 0040 00000400"), body[:14].hex(" "))
        px = body[14:]
        check(f"{ident}: 1,024 pixel bytes", len(px) == 1024, f"{len(px)}")
        gp = unpack(px, 128, 64)
        check(f"{ident}: pixels = a frame the panel was sent, near the last",
              panel_match(work / f"id{ident[:2]}.ser.a", px) and differ(gp, gs) <= NEAR,
              f"{differ(gp, gs)} pixels differ from the last")
        check(f"{ident}: not blank, not full", 0 < sum(map(sum, gp)) < 128 * 64)
        if ident == "10 00":
            ref = got
    for name, msg in ((("cmd05", "f0 00 20 3c 10 00 00 00 01 00 00 05 f7"),
                      ("othermfr", "f0 00 20 3d 10 00 00 00 01 00 00 04 f7"),
                      ("stock50", "f0 00 20 3c 05 00 50 00 00 00 00 04 f7")) if have_project else ()):
        got, _, _ = run(name, [msg])
        check(f"{name}: no screenshot reply", len(got) != 1194, f"{len(got)} bytes")

    # ---- USB
    import os
    sys.path.insert(0, str(ROOT / "tools/harness"))
    import usb_host
    uimg = build("screen-usb", work)
    sock = f"/tmp/ot-screen-{os.getpid()}.sock"
    din_out, fb, user = work / "usb.dout", work / "usb.fb", work / "usb.ser"
    with (work / "usb.log").open("w") as lf:
        emu = subprocess.Popen([str(EMU), "--image", str(uimg), "--usb-host", sock, "--usb-hold-ms", "60000",
                                "--midi-out", str(din_out), "--mem-dump", f"{PLANE:#x},1024={fb}",
                                "--serial-out", str(user)],
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
    ugs = panel_grid(work / "usb.ser.a")
    udiff = differ(unpack(body[14:], 128, 64), ugs) if len(body) == 1038 else -1
    check("usb: pixels = a frame the panel was sent, near the last",
          panel_match(work / "usb.ser.a", body[14:]) and 0 <= udiff <= NEAR, f"{udiff} pixels differ from the last")
    check("usb: nothing on DIN", not din_out.exists() or din_out.stat().st_size == 0)
    if have_project:
        got, _, _ = run("usbdin", [f"f0 00 20 3c 10 00 {REQ_BODY} f7"], img=uimg)
        check("usb image, request on DIN: answered on DIN", len(got) == 1194, f"{len(got)} bytes")
    print("verify_screen:", "FAIL " + ", ".join(fails) if fails else "ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
