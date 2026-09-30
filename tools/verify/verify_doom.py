#!/usr/bin/env python3
"""verify_doom -- DOOM (modules/doom) under the ColdFire port.

    python3 tools/verify/verify_doom.py [REMIX]          (default: doom)

Needs DOOM1.WAD, which is the user's and never in the repo: $DOOM_WAD, else
out/doom/DOOM1.WAD. Without it the gate SKIPs. Six boots of the built
image, run side by side:

  play     fresh battery SRAM (the port's), the WAD on the card: DOOM takes
           the boot at the LOAD PROJECT post, initialises, and a scripted
           PLAY x4 (title -> NEW GAME -> episode -> skill) puts it in E1M1;
           UP walks, YES fires (the clip drops below a new game's 50). The panel and
           Doom's own 320x200 frame are written to out/doom/ as PNGs.
  known    the SRAM a first boot leaves (every power-on after the first):
           the LOADING FILES post comes first, and DOOM takes that one.
  nowad    the same card without the WAD: DOOM hands the boot to OS
           SWITCH's picker hook exactly as its own detour would, and never
           runs a tic.
  exit     FUNC + STOP: FUNC's sub-layer calls OS SWITCH's reset (the port
           does not reset; reaching osw_reset is the claim).
  switch   the image staged by OS SWITCH (mailbox, body, stage as osw_load
           leaves them) and booted: the chainloader hands over, status RUN,
           and the switched-to image goes straight into Doom.

What none of this can show: the frame rate on the unit (the port's
instruction count is not the chip's cycle count), whether the panel shows
the plane the way lcd_view composites it, and the soft reset itself.
"""
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
INC = ROOT / "modules/os-switch/osw.inc"
OUT = ROOT / "out/doom"
K_PLAY, K_UP, K_YES, K_FUNC, K_STOP = 0x28, 0x33, 0x31, 0x2D, 0x27
GS_LEVEL = 0


def nm(elf):
    out = subprocess.run(["m68k-elf-nm", str(elf)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def roll(b):
    h = 0
    for x in b:
        h = (h * 33 + x) & 0xFFFFFFFF
    return h


def png(path, w, h, rgb_rows):
    import zlib
    raw = b"".join(b"\0" + r for r in rgb_rows)
    c = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    pathlib.Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + c(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                                   + c(b"IDAT", zlib.compress(raw)) + c(b"IEND", b""))


def layout_of():
    """offsetof(player_t, ammo) and sizeof(boolean), from the compiler that
    built the image and doomgeneric's own headers: no offset typed here."""
    src = ('#include <stdint.h>\n#include "doomstat.h"\n#include <stddef.h>\n'
           'int ammo_off = offsetof(player_t, ammo);\nint bool_size = sizeof(boolean);\n')
    d = pathlib.Path(tempfile.mkdtemp(prefix="doomoff."))
    (d / "o.c").write_text(src)
    up = ROOT / "modules/doom/upstream/doomgeneric"
    inc = ROOT / "modules/doom/octa/include"
    gi = subprocess.run(["m68k-elf-gcc", "-print-file-name=include"], capture_output=True, text=True).stdout.strip()
    r = subprocess.run(["m68k-elf-gcc", "-mcpu=54455", "-O2", "-ffreestanding", "-nostdinc", "-isystem", str(inc), "-isystem", gi,
                        "-I", str(up), "-w", "-S", "-o", str(d / "o.s"), str(d / "o.c")],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_doom: the layout probe did not compile:\n{r.stderr[-800:]}")
    vals = {}
    cur = None
    for line in (d / "o.s").read_text().splitlines():
        m = re.match(r"^(\w+):", line)
        if m:
            cur = m.group(1)
        m = re.match(r"^\s*\.long\s+(\d+)", line)
        if m and cur:
            vals[cur] = int(m.group(1))
    return vals["ammo_off"], vals["bool_size"]


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX", "doom")
    if "DOOM" not in registry.remix(remix).modules:
        print(f"  [SKIP] verify_doom: {remix} does not carry DOOM")
        return 0
    wad = pathlib.Path(os.environ.get("DOOM_WAD", ROOT / "out/doom/DOOM1.WAD"))
    if not wad.exists():
        print(f"  [SKIP] verify_doom: no DOOM1.WAD ({wad}; set DOOM_WAD) -- the WAD is yours, "
              f"never the repo's")
        return 0
    if not EMU.exists():
        print("  [SKIP] verify_doom: the ColdFire port is not built (make emu-cf)")
        return 0
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    env.setdefault("VERSION", "DOOM")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_doom: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    work = pathlib.Path(tempfile.mkdtemp(prefix="doom."))
    image = work / "doom.bin"
    image.write_bytes((ROOT / "out/mainos_bus.bin").read_bytes())
    rt = nm(ROOT / "out/platform/runtime/runtime.elf")
    chain = nm(ROOT / "out/platform/loader.elf")
    lay = json.loads((ROOT / "out/platform/layout.json").read_text())
    raw = (ROOT / "out/platform/runtime.raw").read_bytes()
    C = {m.group(1): int(m.group(2), 0) for m in
         re.finditer(r"^\s*\.set\s+(\w+),\s*(0x[0-9a-fA-F]+|\d+)", INC.read_text(), re.M)}
    cached = lambda a: a - 0x08000000
    stock = STOCK.read_bytes()
    norver = work / "norver.bin"
    norver.write_bytes(stock[C["OS_VEROFF"]:C["OS_VEROFF"] + 2])
    OUT.mkdir(parents=True, exist_ok=True)

    musdir = ROOT / "out/doom/card/DOOMMUS"      # modules/doom/music.py's output, if made

    def card(tag, with_wad, music=False):
        import emu_card
        t = work / f"{tag}_tree"
        (t / "OSW" / "AUDIO").mkdir(parents=True)
        (t / "OSW" / "P").mkdir()
        if with_wad:
            shutil.copy(wad, t / "DOOM1.WAD")
        if music:
            shutil.copytree(musdir, t / "DOOMMUS")
        p = work / f"{tag}.img"
        p.write_bytes(emu_card.build_image(str(t), size_mb=64))
        return p

    wcard, ncard = card("wad", True), card("nowad", False)
    mcard = card("mus", True, music=True) if musdir.is_dir() else wcard
    # where DG_ScreenBuffer lands: the WAD sits at the heap's base (octa.h
    # DOOM_RAM_BASE, sector-rounded, no header), then the first malloc's
    # 8-byte header (doom_octa.c read_wad, libc.c malloc)
    wlen = (wad.stat().st_size + 511) & ~511
    FB = 0x45029DE0 + wlen + 8
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_doom: {label}{'  (' + detail + ')' if detail else ''}")

    W = {k: rt[k] for k in ("doom_boot", "doom_frame", "doom_projpost", "doom_files", "doom_home",
                            "osw_reset", "osw_bootpick", "osw_bootfiles", "I_Error", "D_DoomMain",
                            "m_start")}
    name_of = {a: k for k, a in W.items()}

    def boot(tag, crd, script, dumps=None, preload=(), boot_load=True, lcd=False, maxi=12_000_000_000,
             extra=()):
        args = [str(EMU), "--image", str(image), "--max", str(maxi), *extra,
                "--preload", ";".join(f"0x{a:x}={p}" for a, p in [(0x3FFC, norver), *preload]),
                "--card", str(crd), "--mount", "--set", "/OSW", "--project", "P", "--mkii",
                "--load-ms", "60000", "--watch-pc", ",".join(f"0x{a:x}" for a in W.values())]
        if boot_load:
            args.append("--boot-load")
        if script:
            s = work / f"{tag}.txt"
            s.write_text("\n".join(script) + "\n")
            args += ["--live-script", str(s)]
        if lcd:
            args += ["--lcd", str(work / f"{tag}.lcd")]
        paths = {}
        if dumps:
            spec = []
            for n, (a, ln) in dumps.items():
                paths[n] = work / f"{tag}_{n}.bin"
                spec.append(f"0x{a:x},{ln}={paths[n]}")
            args += ["--mem-dump", ";".join(spec)]
        out = subprocess.run(args, capture_output=True, text=True, cwd=ROOT).stdout
        (work / f"{tag}.log").write_text(out)
        seq = [name_of.get(int(m.group(1), 16)) for m in
               re.finditer(r"^\s*\[\s*\d+\] at 0x([0-9a-f]+)", out, re.M)]
        # osw_chain runs at every boot (the ROM gate): kept only where it is the claim
        seq = [s for s in seq if s and (s != "osw_chain" or tag == "switch")]
        return out, seq, {k: p.read_bytes() for k, p in paths.items() if p.exists()}

    kd = lambda code, t, hold=50: [f"{t} key {code:#x} down", f"{t + hold} key {code:#x} up"]
    start = kd(K_PLAY, 3000) + kd(K_PLAY, 3600) + kd(K_PLAY, 4200) + kd(K_PLAY, 4800)
    play = start + kd(K_UP, 6000, 1200) + kd(K_YES, 7400, 100) + ["9000 quit"]
    ammo_off, bsz = layout_of()
    dumps = {"logpos": (rt["octa_logpos"], 4), "log": (rt["octa_logbuf"], 8192),
             "gamestate": (rt["gamestate"], 4), "gametic": (rt["gametic"], 4),
             "sbp": (rt["DG_ScreenBuffer"], 4), "clip": (rt["players"] + ammo_off, 4),
             "demo": (rt["demoplayback"], bsz)}

    def sram_then_known():
        _, _, d1 = boot("known_sram", wcard, ["6000 quit"], {"sram": (0x10000000, 0x100000)})
        sram = work / "sram.bin"
        sram.write_bytes(d1.get("sram", b""))
        # --boot-load: without it the port posts LOAD PROJECT itself (from its idle
        # loop), a reload the unit never does -- its dialog stalls Doom (1 Oct 2026)
        return boot("known", wcard, ["6000 quit"], dumps, preload=[(0x10000000, sram)])

    # the switch: the mailbox, the body and the stage exactly as osw_load writes them
    body = raw[rt["osw_body"] - lay["base"]:rt["osw_body_end"] - lay["base"]]
    body_f = work / "body.bin"
    body_f.write_bytes(body)
    body_sum = sum(struct.unpack(f">{len(body) // 4}I", body)) & 0xFFFFFFFF
    img = image.read_bytes()
    n, h = len(img), roll(img)
    mbox = work / "mbox.bin"
    mbox.write_bytes(struct.pack(">IIIII", C["OSW_MAGIC"], n, h, C["OSW_MAGIC"] ^ n ^ h, 0)
                     + b"\0" * 4 + b"DOOM.OBI".ljust(32, b"\0")
                     + struct.pack(">III", 0, len(body) // 4, body_sum))
    sw_pre = [(cached(C["OSW_MBOX"]), mbox), (cached(C["OSW_BODY"]), body_f), (cached(C["OSW_IMG"]), image)]
    W["osw_chain"] = chain["osw_chain"]
    name_of[chain["osw_chain"]] = "osw_chain"

    with ThreadPoolExecutor(6) as ex:
        # the DSP too: the frame transfer's blocks, and what doomsnd adds to MAIN
        f_snd = ex.submit(boot, "sound", mcard, play,
                          {"blocks": (rt["doom_audio_blocks"], 4), "under": (rt["doom_audio_underruns"], 4),
                           "logpos": dumps["logpos"], "log": dumps["log"]},
                          extra=("--dsp", "--main-level", "64", "--audio-out", str(work / "sound")),
                          maxi=20_000_000_000)
        # DG_ScreenBuffer is the first malloc after the WAD's (doom_octa.c's heap
        # is deterministic); the log's own line says where, and the gate checks it
        f_play = ex.submit(boot, "play", wcard, play,
                           {**dumps, "fb": (FB, 320 * 200), "pal": (rt["colors"], 1024)}, lcd=True)
        f_known = ex.submit(sram_then_known)
        f_nowad = ex.submit(boot, "nowad", ncard, ["5000 quit"], dumps)
        f_exit = ex.submit(boot, "exit", wcard, kd(K_FUNC, 3000, 300)[:1] + kd(K_STOP, 3100)
                           + kd(K_FUNC, 3000, 300)[1:] + ["6000 quit"])
        f_sw = ex.submit(boot, "switch", wcard, ["6000 quit"],
                         {**dumps, "mbox": (cached(C["OSW_MBOX"]), 72)}, preload=sw_pre)

    u32 = lambda b: struct.unpack(">I", b[:4])[0] if len(b) >= 4 else -1

    def log_of(d):
        k = u32(d.get("logpos", b""))
        return d.get("log", b"")[:max(0, min(k, 8192))].decode("latin1")

    out, seq, d = f_play.result()
    lg = log_of(d)
    check("play: DOOM took the boot at the LOAD PROJECT post and read the WAD",
          seq[:2] == ["doom_projpost", "doom_boot"] and "DOOM1.WAD: 4196020 bytes" in lg,
          " > ".join(seq[:3]))
    check("play: D_DoomMain ran to the game loop (I_InitGraphics), no I_Error",
          "I_InitGraphics" in lg and "I_Error" not in seq, lg.strip().splitlines()[-1] if lg else "no log")
    tics = u32(d.get("gametic", b""))
    check("play: PLAY x4 put it in a level, and it kept ticking",
          u32(d.get("gamestate", b"")) == GS_LEVEL and tics > 500, f"gametic {tics}")
    check("play: tics ran in the UI task as deferred calls (doom_frame)", seq.count("doom_frame") > 500,
          f"{seq.count('doom_frame')}")
    sb = u32(d.get("sbp", b""))
    check("play: DG_ScreenBuffer where the gate dumped it", sb == FB and f"DG_ScreenBuffer 0x{FB:x}" in lg,
          f"0x{sb:x}")
    # a NEW game starts with 50 bullets; the title's demo fires too, so the
    # claim is: our own game (no demo playing) and fewer than 50 left
    clip, demo = u32(d.get("clip", b"")), int.from_bytes(d.get("demo", b"\1"), "big")
    check("play: our own game, not the title demo, and YES fired the pistol (clip < 50)",
          demo == 0 and 0 <= clip < 50, f"clip {clip}, demoplayback {demo}")
    # the panel, and Doom's own frame beside it
    # Doom's 8-bit frame (CMAP256) through its palette: struct color's
    # bitfields sit b, g, r, a from the MSB on this big-endian target
    fbd, pal = d.get("fb", b""), d.get("pal", b"")
    if len(fbd) == 320 * 200 and len(pal) == 1024:
        rgb = [bytes((pal[i * 4 + 2], pal[i * 4 + 1], pal[i * 4])) for i in range(256)]
        png(OUT / "frame.png", 320, 200,
            [b"".join(rgb[fbd[y * 320 + x]] for x in range(320)) for y in range(200)])
    lcd = work / "play.lcd"
    if lcd.exists():
        r = subprocess.run([str(ROOT / ".venv/bin/python3"), str(ROOT / "tools/emu/lcd_view.py"), str(lcd),
                            "--png", str(OUT / "panel.png")], capture_output=True, text=True)
        check("play: the panel's last frame written", (OUT / "panel.png").exists(), str(OUT / "panel.png"))
    shutil.copy(work / "play.log", OUT / "play.log")

    out, seq, d = f_known.result()
    check("known: with the card in SRAM the LOADING FILES post comes first and DOOM takes it",
          seq[:2] == ["doom_files", "doom_boot"] and seq.count("doom_frame") > 100,
          " > ".join(seq[:3]) + f", {seq.count('doom_frame')} tics")

    out, seq, d = f_nowad.result()
    check("nowad: no WAD, so DOOM hands the boot on to OS SWITCH's hook and never runs a tic",
          "doom_boot" in seq and ("osw_bootpick" in seq or "osw_bootfiles" in seq)
          and seq.index("doom_boot") < min(seq.index(k) for k in ("osw_bootpick", "osw_bootfiles") if k in seq)
          and "doom_frame" not in seq and "D_DoomMain" not in seq,
          " > ".join(seq[:4]))

    out, seq, d = f_exit.result()
    check("exit: FUNC + STOP reaches OS SWITCH's reset through FUNC's sub-layer",
          "doom_home" in seq and "osw_reset" in seq and seq.index("doom_home") < seq.index("osw_reset"),
          " > ".join(s for s in seq if s != "doom_frame")[:120])

    out, seq, d = f_sw.result()
    mb = d.get("mbox", b"\0" * 72)
    st = mb[C["MB_STATUS"]:C["MB_STATUS"] + 4].decode("latin1")
    check("switch: the chainloader handed the staged image over (status RUN, mailbox spent)",
          seq.count("osw_chain") == 2 and st == "RUN " and u32(mb) == 0, f"status {st!r}")
    check("switch: the switched-to image went straight into Doom",
          "doom_boot" in seq and seq.count("doom_frame") > 50, f"{seq.count('doom_frame')} tics")

    # ---- sound: the frame interrupt's blocks, and MAIN L/R after doomsnd ----
    out, seq, d = f_snd.result()
    blocks, under = u32(d.get("blocks", b"")), u32(d.get("under", b""))
    check("sound: one block a DSP frame went to core 0, and the ring kept up (< 10 % underruns)",
          blocks > 5000 and 0 <= under < blocks // 10, f"{blocks} blocks, {under} underruns")
    m = re.search(r"sound_core0\.wav, (\d+) frames.*transport start at frame (\d+)", out)
    rms = -999.0
    wavp = work / "sound_core0.wav"
    if m and wavp.exists():
        import math
        raw = wavp.read_bytes()
        i = 12
        while i < len(raw) and raw[i:i + 4] != b"data":
            i += 8 + struct.unpack("<I", raw[i + 4:i + 8])[0]
        pcm, start = raw[i + 8:], int(m.group(2))
        n = len(pcm) // 24
        acc = cnt = 0
        for f in range(start, n, 13):
            for c in (2, 3):                  # the ring's MAIN L/R words
                o = f * 24 + c * 3
                v = int.from_bytes(pcm[o:o + 3], "little", signed=True)
                acc += v * v
                cnt += 1
        if cnt:
            rms = 10 * math.log10(max(acc / cnt, 1) / (1 << 46))
    check("sound: MAIN L/R carry Doom (no project plays, so anything there is doomsnd's)",
          rms > -60, f"{rms:.1f} dBFS rms after the transport start")
    # the music opens a card file only from doom_frame's service, after a tic
    # has run -- never inside the boot hook, where the first build froze the
    # unit at power-on (1 Oct 2026, the DOOMNM/DOOM bisect)
    check("sound: the music's first card open comes after Doom's first tic, not in the boot hook",
          "m_start" in seq and "doom_frame" in seq and seq.index("doom_frame") < seq.index("m_start"),
          " > ".join(x for x in seq[:8] if x != "doom_frame" or True)[:120])
    # the card reads' destination must be sector-aligned: the port's card moves
    # sectors with a CPU loop and cannot see it, the unit froze on a 4-aligned one
    check("sound: the music's card-read buffer is sector-aligned (the port cannot see this; the unit can)",
          rt.get("mring_mem", 1) % 512 == 0, f"0x{rt.get('mring_mem', 0):08x}")
    lg = log_of(d)
    if mcard is not wcard:
        check("sound: the music came from the card (no 'music: no' in Doom's log)",
              "music: no" not in lg, lg.strip().splitlines()[-1] if lg else "no log")
    else:
        print(f"  [SKIP] verify_doom: sound: music -- no {musdir} (modules/doom/music.py makes it)")

    print(f"  verify_doom: {'PASS' if not fails else f'{fails} FAIL'} (work {work})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
