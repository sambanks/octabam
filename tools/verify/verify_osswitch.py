#!/usr/bin/env python3
"""OS SWITCH under the ColdFire port: the switcher stages an image, the
chainloader boots it, and every refusal boots the flashed image instead.

    python3 tools/verify/verify_osswitch.py os-switch
    make check REMIX=os-switch                      # the same, as the module's gate

Builds the remix (the HOME image: what NOR would hold), then:

  layout   the platform runtime and its stage end below the mailbox: the
           top of the reserve is the switch's, in every remix carrying it
  ui       an MKII (`--mkii`: the reset sends the panel `60 02` first) with a
           card holding STOCK140.OBI (the user's own stock MAIN OS, copied
           at run time); PROJ opens MAIN MENU > CONTROL > OS SWITCH,
           YES on the row, YES in the dialog. The row's action, the dialog's
           answer, the deferred load and the reset sequence each run; the
           stage reads back equal to the file and the mailbox carries its
           length, hash, check word and name; the port does not reset, so
           the switcher reaches its fallback and records RCR
  chain    the home image booted with the memory the ui run left (its
           mailbox and stage, as a reset that keeps SDRAM would leave them):
           the chainloader runs, the stub runs from the stage, stock's entry
           runs a second time, the home loader never does, the OS entry
           site holds stock's instruction again, and the boot reaches the
           RTOS handoff
  self     the home image staged as its own target: the second boot's
           chainloader (the target carries OS SWITCH) turns BOOT into RUN,
           the mailbox is spent, the home loader runs once
  none     no mailbox: status NONE, the normal boot
  hash     one byte of the stage changed after the mailbox was written:
           status HASH, the normal boot, the mailbox spent
  bver     NOR's bootstrap version not the image's (the port's NOR reads 0
           unless preloaded): status BVER, the normal boot -- a staged image
           that would reprogram the bootstrap never runs
  size     a length past the stage: status SIZE, the normal boot
  dsp      the DSP across a switch, without the reset the port cannot do:
           with the cores running their payloads, osw_park sends each host
           command $12 (both must take it), then the stock upload's own
           steps (0x40001d4c, 0x40001b18: bootstrap and payload, core 0 then
           core 1, from copies of the blobs -- the running OS has reused the
           image's copy) go through the parked loaders. Each core enters its
           stock bootstrap a SECOND time (P:$31000, P:$32000) and core 0 its
           payload's start (P:$30000): the loader handed over exactly as the
           boot ROM does

What this cannot see (docs/proposals/FIRMWARE_SWITCHER.md): the reset
itself (the port does not reset; the ui case stops at the reset sequence),
whether SDRAM keeps the stage across it, caches (the port has none), and
the DSP after a chainload (the port boots from reset state either way).
SKIPs without the port (make emu-cf) or when the remix does not carry OS
SWITCH.
"""
import os
import pathlib
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
INC = ROOT / "modules/os-switch/osw.inc"
OUT = ROOT / "out/osswitch"
KEY_YES, KEY_NO, KEY_DOWN, KEY_PROJ = 0x31, 0x32, 0x20, 0x1c


def consts():
    c = {}
    for m in re.finditer(r"^\s*\.set\s+(\w+),\s*(0x[0-9a-fA-F]+|\d+)", INC.read_text(), re.M):
        c[m.group(1)] = int(m.group(2), 0)
    return c


def roll(b):
    h = 0
    for x in b:
        h = (h * 33 + x) & 0xFFFFFFFF
    return h


def nm(elf):
    out = subprocess.run(["m68k-elf-nm", str(elf)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    if "OS SWITCH" not in registry.remix(remix).modules:
        print(f"  [SKIP] verify_osswitch: {remix} does not carry OS SWITCH")
        return 0
    if not EMU.exists():
        print("  [SKIP] verify_osswitch: the ColdFire port is not built (make emu-cf)")
        return 0
    C = consts()
    cached = lambda a: a - 0x08000000                  # the port folds the alias; dumps read either
    MBOX, IMG = cached(C["OSW_MBOX"]), cached(C["OSW_IMG"])

    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_osswitch: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    work = pathlib.Path(tempfile.mkdtemp(prefix="osswitch."))
    home = work / "home.bin"
    home.write_bytes((ROOT / "out/mainos_bus.bin").read_bytes())
    chain = nm(ROOT / "out/linked/os-switch/osw_chain/u.elf")
    rt = nm(ROOT / "out/platform/runtime/runtime.elf")
    loader = nm(ROOT / "out/platform/loader.elf")["octabam_bootstrap"]
    stub = C["OSW_STUB"]
    norver = work / "norver.bin"
    stock = STOCK.read_bytes()
    norver.write_bytes(stock[C["OS_VEROFF"]:C["OS_VEROFF"] + 2])  # what NOR holds after a 1.40C flash
    OUT.mkdir(parents=True, exist_ok=True)

    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_osswitch: {label}{'  (' + detail + ')' if detail else ''}")

    def boot(tag, preload, watch, dumps, extra=(), max_instr=150_000_000):
        args = [str(EMU), "--image", str(home), "--max", str(max_instr),
                "--watch-pc", ",".join(f"0x{a:x}" for a in watch)]
        if preload:
            args += ["--preload", ";".join(f"0x{a:x}={p}" for a, p in preload)]
        paths = {}
        if dumps:
            spec = []
            for name, (a, n) in dumps.items():
                paths[name] = work / f"{tag}_{name}.bin"
                spec.append(f"0x{a:x},{n}={paths[name]}")
            args += ["--mem-dump", ";".join(spec)]
        args += list(extra)
        out = subprocess.run(args, capture_output=True, text=True, cwd=ROOT).stdout
        (work / f"{tag}.log").write_text(out)
        hits = {}
        for m in re.finditer(r"^\s*\[\s*\d+\] at 0x([0-9a-f]+)", out, re.M):
            a = int(m.group(1), 16)
            hits[a] = hits.get(a, 0) + 1
        return out, hits, {k: p.read_bytes() for k, p in paths.items() if p.exists()}

    def mailbox(image, status=0, name=b"TEST.OBI", length=None, check_ok=True):
        n = len(image) if length is None else length
        h = roll(image)
        chk = C["OSW_MAGIC"] ^ n ^ h
        if not check_ok:
            chk ^= 1
        p = work / f"mbox_{len(list(work.glob('mbox_*')))}.bin"
        p.write_bytes(struct.pack(">IIIII", C["OSW_MAGIC"], n, h, chk, status)
                      + b"\0" * 4 + name.ljust(32, b"\0"))
        return p

    status = lambda mb: mb[C["MB_STATUS"]:C["MB_STATUS"] + 4].decode("latin1")
    magic = lambda mb: struct.unpack(">I", mb[:4])[0]
    ST = {k: struct.pack(">I", C[k]).decode() for k in ("ST_BOOT", "ST_RUN", "ST_NONE", "ST_SIZE",
                                                         "ST_BVER", "ST_HASH")}

    # ---- layout: the runtime stays below the switch's pages ---------------
    import json
    lay = json.loads((ROOT / "out/platform/layout.json").read_text())
    check("layout: the platform runtime and its stage end below the mailbox",
          lay.get("stage_end", 0) <= MBOX,
          f"runtime ..0x{lay.get('stage_end', 0):08x}, mailbox 0x{MBOX:08x}")

    # ---- ui: the row, the dialog, the load, the reset sequence ------------
    tree = work / "card"
    tree.mkdir()
    (tree / "STOCK140.OBI").write_bytes(stock)
    import emu_card
    card = work / "card.img"
    card.write_bytes(emu_card.build_image(str(tree), size_mb=64))
    lines, t = [], [1500.0]

    def send(line, pause=50.0):
        lines.append(f"{t[0]:.0f} {line}")
        t[0] += pause

    def key(code, pause=150.0):
        send(f"key {code:#x} down", 20.0)
        send(f"key {code:#x} up", pause)

    key(KEY_NO, 250)                                   # the boot's date prompt
    key(KEY_PROJ, 400)                                 # an MKII: the reset sends the panel `60 02`
    key(KEY_DOWN); key(KEY_DOWN); key(KEY_YES, 300)    # root: PROJECT SYSTEM [CONTROL] MIDI
    for _ in range(6):
        key(KEY_DOWN)                                  # AUDIO .. METRONOME, OS SWITCH
    key(KEY_YES, 600)                                  # the row: STOCK140.OBI offered
    key(KEY_YES, 3000)                                 # the dialog: boot it
    send("quit")
    script = work / "panel.txt"
    script.write_text("\n".join(lines) + "\n")
    ui_watch = [rt["osw_action"], rt["osw_answer"], rt["osw_load"], rt["osw_reset"], rt["putpanel"]]
    out, hits, d = boot("ui", [(0x3FFC, norver)], ui_watch,
                        {"mbox": (MBOX, 64), "stage": (IMG, len(stock))},
                        extra=["--card", str(card), "--live-script", str(script), "--mkii"],
                        max_instr=4_000_000_000)
    ran = [s for s, a in zip(("osw_action", "osw_answer", "osw_load", "osw_reset"), ui_watch)
           if hits.get(a)]
    check("ui: the row, the dialog's YES, the deferred load and the reset sequence ran",
          len(ran) == 4, "ran: " + ", ".join(ran))
    check("ui: an MKII sends the panel its two start-up bytes (`60 02`) before the reset",
          hits.get(rt["putpanel"]) == 2, f"{hits.get(rt['putpanel'], 0)} byte(s)")
    mb, stage = d.get("mbox", b""), d.get("stage", b"")
    check("ui: the stage reads back equal to STOCK140.OBI", stage == stock,
          f"{len(stage):,} B")
    ok = (len(mb) == 64 and magic(mb) == C["OSW_MAGIC"]
          and struct.unpack(">III", mb[4:16]) == (len(stock), roll(stock),
                                                   C["OSW_MAGIC"] ^ len(stock) ^ roll(stock))
          and mb[C["MB_NAME"]:].split(b"\0")[0] == b"STOCK140.OBI")
    check("ui: the mailbox holds its length, hash, check word and name", ok, mb[:40].hex())
    check("ui: the port does not reset, so the switcher reached its RCR fallback and said so",
          mb[C["MB_RESET"]:C["MB_RESET"] + 4] == struct.pack(">I", C["RS_RCR"]),
          mb[C["MB_RESET"]:C["MB_RESET"] + 4].decode("latin1"))
    (work / "ui_mbox.bin").write_bytes(mb)
    (work / "ui_stage.bin").write_bytes(stage)

    # ---- chain: the memory the ui run left, booted ------------------------
    watch = [0x40000400, chain["osw_chain"], stub, loader]
    out, hits, d = boot("chain", [(0x3FFC, norver), (MBOX, work / "ui_mbox.bin"),
                                  (IMG, work / "ui_stage.bin")],
                        watch, {"site": (0x40000412, 6), "mbox": (MBOX, 64)})
    check("chain: the chainloader ran, the stub ran from the stage, stock's entry ran again",
          hits.get(chain["osw_chain"]) == 1 and hits.get(stub) == 1 and hits.get(0x40000400) == 2,
          f"chain {hits.get(chain['osw_chain'], 0)}, stub {hits.get(stub, 0)}, entry {hits.get(0x40000400, 0)}")
    check("chain: the home image's loader never ran", not hits.get(loader),
          f"{hits.get(loader, 0)}x")
    check("chain: 0x40000412 holds stock's `movea.l #0x48000000,%sp` again",
          d.get("site") == bytes.fromhex("2e7c48000000"), (d.get("site") or b"").hex())
    check("chain: the staged OS reached the RTOS handoff", "HANDOFF" in out)

    # ---- self: the home image as its own target ---------------------------
    homeb = home.read_bytes()
    stage_self = work / "stage_self.bin"
    stage_self.write_bytes(homeb)
    out, hits, d = boot("self", [(0x3FFC, norver), (MBOX, mailbox(homeb, name=b"HOME.OBI")),
                                 (IMG, stage_self)], watch, {"mbox": (MBOX, 64)})
    mb = d.get("mbox", b"\0" * 64)
    check("self: status RUN after the handover, the mailbox spent, the loader ran once",
          status(mb) == ST["ST_RUN"] and magic(mb) == 0 and hits.get(loader) == 1
          and hits.get(chain["osw_chain"]) == 2 and "HANDOFF" in out,
          f"status {status(mb)!r}, magic {magic(mb):#x}, loader {hits.get(loader, 0)}, "
          f"chain {hits.get(chain['osw_chain'], 0)}")

    # ---- the refusals: each boots the home image -------------------------
    def refused(tag, preload, want):
        out, hits, d = boot(tag, preload, watch, {"mbox": (MBOX, 64)})
        mb = d.get("mbox", b"\0" * 64)
        check(f"{tag}: status {want.strip()}, the normal boot, no stub",
              status(mb) == ST[want] and not hits.get(stub) and hits.get(loader) == 1
              and "HANDOFF" in out,
              f"status {status(mb)!r}, stub {hits.get(stub, 0)}, loader {hits.get(loader, 0)}")
        return mb

    stage_stock = work / "stage_stock.bin"
    stage_stock.write_bytes(stock)
    refused("none", [(0x3FFC, norver)], "ST_NONE")
    bad = bytearray(stock)
    bad[len(bad) // 2] ^= 0x01
    stage_bad = work / "stage_bad.bin"
    stage_bad.write_bytes(bytes(bad))
    mb = refused("hash", [(0x3FFC, norver), (MBOX, mailbox(stock)), (IMG, stage_bad)], "ST_HASH")
    check("hash: the mailbox is spent (one-shot)", magic(mb) == 0, f"{magic(mb):#x}")
    refused("bver", [(MBOX, mailbox(stock)), (IMG, stage_stock)], "ST_BVER")
    refused("size", [(0x3FFC, norver), (MBOX, mailbox(stock, length=C["OSW_MAXLEN"] + 4)),
                     (IMG, stage_stock)], "ST_SIZE")
    # ---- dsp: park the running cores, boot them through the loaders --------
    B = 0x40000400
    blobs = {"bootA": (0x400E21E0, 0x96), "payA": (0x400E2324, 0x136CB),
             "bootB": (0x400E2276, 0xAE), "payB": (0x400F59EF, 0x12D05)}   # dsp_modmap
    at, where, cmds = 0x41300000, {}, ["frame on", "run 300", "frame off", "run 20"]
    for k, (a, n) in blobs.items():
        where[k] = at
        for o in range(0, n, 4096):
            m = min(4096, n - o)
            cmds.append(f"poke {at + o:#x} " + homeb[a - B + o:a - B + o + m].hex())
        at = (at + n + 0xFF) & ~0xFF
    cmds += [f"call {rt['osw_park']:#x}",
             "poke 0xfc0a400c 00", "poke 0x20000000 0081",
             f"call 0x40001d4c {where['bootA']:#x} 0x96 0x31000", f"call 0x40001b18 {where['payA']:#x}",
             "poke 0xfc0a400c 01", "poke 0x20000000 0081",
             f"call 0x40001d4c {where['bootB']:#x} 0xae 0x32000", f"call 0x40001b18 {where['payB']:#x}",
             "run 5", "dsp pcwatch", "quit"]

    def interactive(pcwatch):
        r = subprocess.run([str(EMU), "--image", str(home), "--preload", f"0x3ffc={norver}", "--dsp",
                            "--dsp-pcwatch", pcwatch, "--interactive"],
                           input="\n".join(cmds) + "\n", capture_output=True, text=True, cwd=ROOT)
        oks = [l for l in r.stdout.splitlines() if l.startswith(("ok d0=", "err"))]
        w = [l for l in r.stdout.splitlines() if l.startswith("dsp n=")]
        arrivals = len(w[-1].split()) - 2 if w else 0
        return oks, arrivals

    res = {pc: interactive(pc) for pc in ("0:0x31000", "0:0x30000", "1:0x32000")}
    oks = res["0:0x31000"][0]
    check("dsp: both cores took the park command, every upload step returned",
          len(oks) == 5 and oks[0] == "ok d0=0x3" and all(o.startswith("ok") for o in oks), "; ".join(oks))
    check("dsp: core 0 entered bootstrap A and its payload's start again, core 1 bootstrap B",
          all(res[pc][1] >= 2 for pc in res),
          ", ".join(f"{pc} x{res[pc][1]}" for pc in res))

    if fails:
        print(f"  verify_osswitch: logs in {work}")
    else:
        import shutil
        shutil.rmtree(work, ignore_errors=True)       # a 64 MB card and three stages per run
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
