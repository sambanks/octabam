#!/usr/bin/env python3
"""USB AUDIO IN under the ColdFire port: the host's channels on EP3 OUT reach
core 0's RX blocks as the module's inputs (AB, CD or ABCD), the other inputs
stay the jacks', and closing the stream gives them all back to the jacks.

The bench plays the host: it enumerates, opens interface 4 alt 1 (the input
stream, the implicit-feedback source) and interface 5 alt 1, then each poll
sends one OUT packet carrying as many frames as the previous IN packet did --
what implicit feedback asks of a host. The IN poll and the OUT packet are
queued TOGETHER so the port serves both in one 250 us slot, as a host's
microframe does: issued one after the other, each costs the bench a slot of
device time, the device runs two frames' worth per host packet, and both
rings fail for the bench's reasons (measured 26 Sep 2026: 1.39 state-7
visits per poll against 0.692 pipelined; the unit runs 0.689). Every OUT
sample is coded: v = ch << 20 | frame (ch = the host channel - 1, frame = a
running count), so a DSP word says which channel and which frame it came
from. The IN poll's frame size is the remix's USB AUDIO
layout's (verify_usb.LAYOUTS): 16 B with USB AUDIO OUT MAIN CUE, 64 with OUT TRACKS,
80 with OUT TRACKS MAIN CUE, 8 with OUT MAIN.

  run 1 (streaming): hang up while the stream is running; the RX ring's
    completed blocks must hold the coded samples in the module's slots
    (2/3 = A/B, 0/1 = C/D), bit-exact (default GAIN = unity, gate open),
    consecutive frames, with the other slots untouched -- silence under the
    port -- and so must the recorder's input ring.
  run 2 (closed): alt 0 on interface 5, then keep EP3 IN's stream running;
    word 0 of the transfer must be clear and the RX blocks the jacks'
    (silence under the port).

Needs the port (make emu-cf), a built image carrying USB AUDIO IN, and the
linked runtime (out/platform/runtime/runtime.elf) for the unit's addresses.
"""
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402  (tools/harness)
from remix import registry, store  # noqa: E402
from verify_usb import LAYOUTS  # noqa: E402  (the input layouts: channels, packet cap, bInterval, taps)

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
ELF = ROOT / "out/platform/runtime/runtime.elf"
COUNTERS = ("produced", "consumed", "pkts", "lastn", "lastfill", "underruns",
            "overruns", "reprimes", "bad", "frames", "seconds", "minfill", "maxfill",
            "err", "partial")
# RX block slot -> host channel (0-based) per INPUTS value ("USB AUDIO IN <INPUTS>"); a slot not listed
# is a jack and must read zero under the port
IN_SLOTS = {"USB AUDIO IN AB": {2: 0, 3: 1},
            "USB AUDIO IN CD": {0: 0, 1: 1},
            "USB AUDIO IN ABCD": {2: 0, 3: 1, 0: 2, 1: 3}}
SLOT_CH = IN_SLOTS["USB AUDIO IN AB"]      # main() sets it from the remix
CHANNELS = 2
fails = []


def check(what, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + str(detail) if detail else ''}")
    if not ok:
        fails.append(what)


def symbols():
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    out = subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout
    return {p[2]: int(p[0], 16) for p in (l.split() for l in out.splitlines()) if len(p) == 3}


def coded(ch, frame):
    return (ch << 20) | (frame & 0xFFFFF)


def packet(frame0, n):
    """n frames from frame0, CHANNELS channels, 24 bits in the top of 4-byte LE subslots."""
    b = bytearray()
    for f in range(frame0, frame0 + n):
        for ch in range(CHANNELS):
            v = coded(ch, f)
            b += bytes((0, v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF))
    return bytes(b)


def replies(b, n):
    """The next n reply lines, in order (Bench.wait would drop the other one)."""
    out = []
    while len(out) < n:
        i = b.buf.find(b"\n")
        if i >= 0:
            out.append(b.buf[:i].decode())
            b.buf = b.buf[i + 1:]
            continue
        chunk = b.sock.recv(65536)
        if not chunk:
            raise RuntimeError("bench closed the socket")
        b.buf += chunk
    return out


def vendor(b):
    """USB AUDIO IN's counters over its vendor request (0xc0/0x56)."""
    raw = b.ctrl_in(0xc0, 0x56, 0, 0, 4 * len(COUNTERS))
    if len(raw) != 4 * len(COUNTERS):
        raise RuntimeError(f"vendor 0x56: {len(raw)} bytes")
    return dict(zip(COUNTERS, struct.unpack(f">{len(COUNTERS)}I", raw)))


def run(tag, sym, packets, close_first, in_frame, reset=False, unplug=False):
    sock = f"/tmp/ot-usbin-{os.getpid()}-{tag}.sock"
    log = ROOT / f"out/verify_usb_in_{tag}.log"
    dump = ROOT / f"out/verify_usb_in_{tag}"
    dump.mkdir(parents=True, exist_ok=True)
    peek = "0:X:8100,576;0:X:202,1"
    mem = (f"{sym['in_counters']:#x},{4 * len(COUNTERS)}={dump}/counters.bin;"
           f"{sym['in_tx']:#x},4={dump}/tx.bin;0x80005660,2048={dump}/ring.bin;"
           f"{sym['in_alt']:#x},1={dump}/in_alt.bin;{sym['in_running']:#x},1={dump}/in_running.bin;"
           f"{sym['usbaudio_alt']:#x},1={dump}/aud_alt.bin;{sym['aud_running']:#x},1={dump}/aud_running.bin")
    with open(log, "w") as lf:
        emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--usb-host", sock,
                                "--usb-hold-ms", "300000", "--frame", "--dsp",
                                "--dsp-peek", peek, "--mem-dump", mem],
                               cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
    try:
        b = usb_host.Bench(sock, timeout=120.0)
        usb_host.enumerate_device(b, hs=True)
        b.ctrl_nodata(0x01, 0x0b, 1, 4)                 # SET_INTERFACE 4 alt 1: EP3 IN (the remix's 250 us out layout)
        b.ctrl_nodata(0x01, 0x0b, 1, 5)                 # SET_INTERFACE 5 alt 1: EP3 OUT (USB AUDIO IN)
        frame, sizes, empty, last_n = 0, set(), 0, 11
        snaps = []
        for _k in range(packets):
            k = _k
            if k in (packets // 4, packets - packets // 4):
                snaps.append((k, vendor(b)))            # over EP0, as a host on the unit reads them
            pkt = packet(frame, last_n)
            frame += last_n
            b.sock.sendall(f"in 3 1024\nout 3 {pkt.hex()}\n".encode())
            for line in replies(b, 2):
                p = line.split()
                if p[0] == "err":
                    raise RuntimeError(line)
                if p[0] == "in":
                    last_n = (len(p[2]) // 2) // in_frame if len(p) > 2 else 0
                    sizes.add(last_n)
                    empty += last_n == 0
                    if last_n == 0:
                        print(f"  (empty IN poll at poll {_k})")
        if close_first:
            b.ctrl_nodata(0x01, 0x0b, 0, 5)             # alt 0: USB AUDIO IN's stream closed
            for _ in range(400):                        # 100 ms more of EP3 IN's stream
                b.ep_in(3, 1024)
        giface = None
        if reset:
            b.reset()                                   # bus reset (URI), no SET_INTERFACE alt 0 from the host
            for _ in range(400):                        # 100 ms more of EP3 IN's stream
                b.ep_in(3, 1024)
            giface = (b.ctrl_in(0x81, 0x0a, 0, 4, 1)[0], b.ctrl_in(0x81, 0x0a, 0, 5, 1)[0])
        if unplug:
            b.unplug()                                  # session end (OTGSC.BSVIS), answered once the ISR has handled it
            time.sleep(0.2)
            giface = None
        b.sock.close()
    finally:
        emu.wait(timeout=600)
    txt = log.read_text()
    m = re.search(r"core 0 X:0x08100:((?: [0-9a-f]{6})+)", txt)
    rx = [int(v, 16) for v in m[1].split()] if m else []
    cur = re.search(r"core 0 X:0x00202: ([0-9a-f]{6})", txt)
    cur = int(cur[1], 16) if cur else None
    cnt = dict(zip(COUNTERS, struct.unpack(f">{len(COUNTERS)}I", (dump / "counters.bin").read_bytes())))
    tx = (dump / "tx.bin").read_bytes()
    ring = (dump / "ring.bin").read_bytes()
    one = lambda n: (dump / n).read_bytes()[0]
    return dict(in_alt=one("in_alt.bin"), in_running=one("in_running.bin"), aud_alt=one("aud_alt.bin"),
                aud_running=one("aud_running.bin"), giface=giface, frames=frame, sizes=sorted(sizes), empty=empty, rx=rx, cur=cur,
                cnt=cnt, tx=tx, ring=ring, log=log, snaps=snaps)


def block_frame(words):
    """The first frame of a 64-word RX block if the module's slots hold the
    coded samples in consecutive frames and the other slots are zero (the
    jacks, silent under the port), else None."""
    s0 = next(s for s, ch in SLOT_CH.items() if ch == 0)
    f0 = words[s0] & 0xFFFFF                            # host channel 1, sample 0
    for smp in range(16):
        w = words[4 * smp:4 * smp + 4]
        for slot in range(4):
            want = coded(SLOT_CH[slot], f0 + smp) if slot in SLOT_CH else 0
            if w[slot] != want:
                return None
    return f0


def recorder_frame(w):
    """The first frame of one 64-long recorder block (slots 0/1 in the first
    32 longs, 2/3 in the second, samples in the top 24 bits) if it carries
    the coded samples on the module's slots and zero on the others, else None."""
    def at(slot, smp):
        return w[(32 if slot >= 2 else 0) + 2 * smp + (slot & 1)] >> 8
    s0 = next(s for s, ch in SLOT_CH.items() if ch == 0)
    f0 = at(s0, 0) & 0xFFFFF
    ok = all(at(slot, smp) == (coded(SLOT_CH[slot], f0 + smp) if slot in SLOT_CH else 0)
             for smp in range(16) for slot in range(4))
    return f0 if ok else None


def main():
    global SLOT_CH, CHANNELS
    if not EMU.is_file():
        print("  [SKIP] verify_usb_in: the port is not built (make emu-cf)")
        return 0
    if not ELF.is_file():
        print("  [FAIL] verify_usb_in: no linked runtime (build a remix with USB AUDIO IN)")
        return 1
    sym = symbols()
    if "in_counters" not in sym:
        print("  [FAIL] verify_usb_in: the runtime has no USB AUDIO IN unit")
        return 1
    remix = registry.remix(os.environ.get("REMIX"))
    inputs = store.value(remix, registry.modules(), "octabam.usb-audio-in", "INPUTS")
    ain = None if inputs is None else f"USB AUDIO IN {inputs}"
    if ain is None:
        print("  [FAIL] verify_usb_in: the remix carries no USB AUDIO IN module")
        return 1
    SLOT_CH = IN_SLOTS[ain]
    CHANNELS = len(SLOT_CH)
    print(f"  {ain}: {CHANNELS} host channels -> RX slots {sorted(SLOT_CH)}")
    layout = store.value(remix, registry.modules(), "octabam.usb-audio-out", "LAYOUT")
    audio = None if layout is None else f"USB AUDIO OUT {layout}"
    if audio is None or LAYOUTS[audio][2] != 2:
        print(f"  [FAIL] verify_usb_in: needs a 250 us USB AUDIO OUT layout (MAIN CUE, MAIN, TRACKS or TRACKS MAIN CUE) beside it, not {audio}")
        return 1
    in_frame = 4 * LAYOUTS[audio][0]
    print(f"  EP3 IN (the feedback source): {audio}, {in_frame} B a frame")

    print("== run 1: streaming ==")
    polls = int(os.environ.get("POLLS", "8000"))       # 2 s of device time
    r = run("stream", sym, polls, close_first=False, in_frame=in_frame)
    c = r["cnt"]
    print(f"  host: {r['frames']} frames in {polls} polls, IN packet sizes {r['sizes']} frames, {r['empty']} empty IN polls")
    print(f"  device counters: {c}")
    if len(r["snaps"]) == 2:
        (k0, s0), (k1, s1) = r["snaps"]
        rate = (s1["frames"] - s0["frames"]) / (k1 - k0)
        check("vendor request 0x56 reads the counters back over EP0",
              s0["pkts"] <= s1["pkts"] <= c["pkts"] and s1["frames"] > s0["frames"], f"{s0['pkts']} -> {s1['pkts']} pkts")
        # The port holds device time for the bench's next IN (usb.h,
        # isoPoll), so every poll is one 250 us slot: state 7 runs at the
        # unit's 0.689 per poll however loaded the machine is.
        # Both reads fall inside the stream, so between them every frame
        # transfers (the second visit); while the stream is closed the
        # transfer stops after four zero blocks, so the lifetime counts differ.
        check("state 7 runs once per 16-sample frame: 0.689 per 250 us poll, one transfer per frame (between the two reads)",
              abs(rate - 0.689) < 0.01
              and abs((s1["frames"] - s0["frames"]) - (s1["seconds"] - s0["seconds"])) <= 1,
              f"{rate:.4f} per poll; first {s1['frames'] - s0['frames']} / second {s1['seconds'] - s0['seconds']} visits between the reads")
    else:
        check("two counter reads over EP0 during the stream (POLLS >= 4)", False, f"{len(r['snaps'])} read(s)")
    tgt = re.search(r"^\.set IN_TARGET,\s+(\d+)", (ROOT / "modules/usb-audio-in/usbaudio_in.s").read_text(), re.M).group(1)
    print(f"  ring fill while consuming: min {c['minfill']} max {c['maxfill']} (target {tgt})")
    # up to NSLOTI (4) dTDs can still be queued when the bench hangs up
    check("every OUT packet retired, whole frames, no errors (up to 4 in flight at hangup)",
          c["pkts"] >= polls - 4 and c["bad"] == 0, f"pkts {c['pkts']} bad {c['bad']}")
    check("the ring took every frame the host sent (the last four packets may be in flight)",
          0 <= r["frames"] - c["produced"] <= 48, f"produced {c['produced']} sent {r['frames']}")
    check("no underrun after the cushion filled, no overrun, no re-prime",
          c["underruns"] == 0 and c["overruns"] == 0 and c["reprimes"] == 0,
          f"underruns {c['underruns']} overruns {c['overruns']} reprimes {c['reprimes']}")
    # Word 0 while streaming is proven by the RX blocks below: the DSP copies
    # the host's words only while it sees it. The in_tx dump lands at whatever
    # instruction the port stopped on, so it is read only after the stream
    # closes (run 2), where it is a constant zero.
    if r["rx"] and r["cur"] is not None:
        # X:$202 is the block the inject is writing at this frame head; the
        # port halts at any instruction, so that block may be half written
        # (seen: the first samples coded, the tail still zero), and the two
        # peeks (the ring, then X:$202) can land a block apart under a loaded
        # machine (28 Sep 2026: the oldest of seven read as the one the ESAI
        # was filling). The six before it are complete.
        cb = (r["cur"] - 0x8100) // 64
        got = []
        for back in range(1, 7):                        # the completed blocks, newest first
            blk = (cb - back) % 9
            got.append(block_frame(r["rx"][blk * 64:(blk + 1) * 64]))
        print(f"  RX blocks before the one under the pen, newest first: first frames {got}")
        check(f"the 6 completed RX blocks hold the host's channels on slots {sorted(SLOT_CH)}, the other slots untouched, bit-exact",
              all(g is not None for g in got), str(got))
        ok = all(g is not None for g in got) and all(a - b == 16 for a, b in zip(got, got[1:]))
        check("... in consecutive frames (no drop, no repeat)", ok)
    else:
        check("the port printed the RX ring", False)
    rf = [recorder_frame(struct.unpack(">64i", r["ring"][fr * 256:(fr + 1) * 256])) for fr in range(8)]
    print(f"  recorder input ring frames: {rf}")
    check("the recorder's input ring carries them on the same inputs (8 frames exact)", all(x is not None for x in rf))

    print("== run 2: the host's stream closed ==")
    r2 = run("closed", sym, 2000, close_first=True, in_frame=in_frame)
    print(f"  device counters: {r2['cnt']}")
    check("word 0 of the transfer is clear after alt 0", len(r2["tx"]) >= 2 and r2["tx"][0] == 0 and r2["tx"][1] == 0,
          r2["tx"][:2].hex())
    rx2 = r2["rx"]
    if rx2 and r2["cur"] is not None:
        cb = (r2["cur"] - 0x8100) // 64
        blks = [rx2[((cb - back) % 9) * 64:((cb - back) % 9 + 1) * 64] for back in range(1, 7)]
        coded_left = sum(1 for bl in blks if any(w != 0 for w in bl))
        check("the RX blocks are the jacks' again (no host samples in the 6 completed blocks)",
              coded_left == 0, f"{coded_left} block(s) with host words")
    print("== run 3: bus reset while both streams are open, no alt 0 from the host ==")
    r3 = run("reset", sym, 2000, close_first=False, in_frame=in_frame, reset=True)
    print(f"  device counters: {r3['cnt']}")
    print(f"  in_alt {r3['in_alt']} in_running {r3['in_running']} usbaudio_alt {r3['aud_alt']} aud_running {r3['aud_running']} "
          f"GET_INTERFACE(4), (5) = {r3['giface']}")
    check("in_alt and in_running are 0 after the reset (USB 2.0 9.1.1.5: alternate setting 0)",
          r3["in_alt"] == 0 and r3["in_running"] == 0, f"in_alt {r3['in_alt']} in_running {r3['in_running']}")
    check("usbaudio_alt and aud_running (EP3 IN) are 0 after the reset",
          r3["aud_alt"] == 0 and r3["aud_running"] == 0 and r3["giface"][0] == 0,
          f"usbaudio_alt {r3['aud_alt']} aud_running {r3['aud_running']} GET_INTERFACE(4) {r3['giface'][0]}")
    check("word 0 of the transfer is clear after the reset (the jacks, not the ring's silence)",
          len(r3["tx"]) >= 2 and r3["tx"][0] == 0 and r3["tx"][1] == 0, r3["tx"][:2].hex())
    check("GET_INTERFACE(5) answers 0 after the reset", r3["giface"][1] == 0, str(r3["giface"][1]))
    print("== run 4: cable pulled (session end) while both streams are open, no alt 0 from the host ==")
    r4 = run("unplug", sym, 2000, close_first=False, in_frame=in_frame, unplug=True)
    print(f"  in_alt {r4['in_alt']} in_running {r4['in_running']} usbaudio_alt {r4['aud_alt']} aud_running {r4['aud_running']}")
    check("in_alt and in_running are 0 after the session end",
          r4["in_alt"] == 0 and r4["in_running"] == 0, f"in_alt {r4['in_alt']} in_running {r4['in_running']}")
    check("usbaudio_alt and aud_running (EP3 IN) are 0 after the session end",
          r4["aud_alt"] == 0 and r4["aud_running"] == 0, f"usbaudio_alt {r4['aud_alt']} aud_running {r4['aud_running']}")
    check("word 0 of the transfer is clear after the session end",
          len(r4["tx"]) >= 2 and r4["tx"][0] == 0 and r4["tx"][1] == 0, r4["tx"][:2].hex())
    print(f"verify_usb_in: {'OK' if not fails else f'{len(fails)} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
