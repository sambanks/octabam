#!/usr/bin/env python3
"""A real project on the built image under the ColdFire port: the routing
facts a flash used to be the first test of.

    python3 tools/verify/verify_set.py bottleservice --project ~/octa/backups/.../OCTABAM88 [--bank 2] [--frames 900]
    OT_PROJECT=... [OT_BANK=2] make check REMIX=bottleservice   # the same, from make verify

Stages the project (banks, project.work with [STATES] BANK= set to the
tested bank, and every STATIC/FLEX sample the tested part's tracks name)
onto a card image, boots the remix's image in `ot_emu`, LOAD PROJECTs, runs
the sequencer with both DSP cores live and tones on the inputs, and reads
the machine back:

  load      LOAD PROJECT completed and the frames ran to the target
  ids       the live FX1/FX2 id arrays (0x80000ec4/0x80000ecc) == the part's
  page 2    every track's DSP record carries its page-2 lane: halfwords
            18-20 = FX1 p2, 21-23 = AMP p2, 24-26 = FX2 p2 (the tempo cave
            wrote over 18-21 on every bus host until 15 Sep 2026)
  audio     every track whose record carries audio has a chain output
            (the read-back slot); the main out's TX0 counts are printed
  midi      CC 40 and 41 (DEL and REV, FX2 page 1 slots 0/1) at 100 on T2's channel over the
            port's MIDI IN (UART0) moves T2's record halfword 12 to 100;
            with CC MAP in the remix, CC 68 at 77 on T1's channel lands
            in T1's FX1 page-2 lane and record halfword 18 (the queue ->
            main -> DSP leg verify_ccmap cannot run); on a bus remix each
            engine's host track must then carry T2's send (the wet comes
            out on the host since 20 Sep 2026), and an engine on the wrong
            core (BusVerb on T1-4, BusDelay on T5-8: it runs as SEND there)
            is refused
  card      the card as the firmware left it (--card-out, read back with
            emu_card.extract_image): which project files it rewrote, and
            its own LOG 000000.txt -- every ERROR line that is not a FILE
            NOT FOUND for a sample the gate did not stage is a failure
            (a PART record with the wrong index byte logs "Couldn't read
            bank file ... ('PARSE ERROR')" here, as the unit does)

SKIPs without a project (OT_PROJECT / --project), without the port
(`make emu-cf`) or without the emulator .venv. What it cannot see: the
panel (edits arrive by --call), cross-core timing, the cycle wall.
"""
import argparse, math, os, pathlib, re, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import registry, stock  # noqa: E402
import ot_project as otp  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/setverify"
LIVE_IDS, RECORDS, LANES = 0x80000ec4, 0x80000110, 0x80000810
TYPE_NAME = {0: "STATIC", 1: "FLEX", 2: "THRU", 3: "NEIGH", 4: "PICKUP"}
# lane offset -> record halfword: the copier 0x4000cae8 (PARAM_PAGES.md 5c)
P2_LANES = (("FX1 p2", 0x32, 18), ("AMP p2", 0x2c, 21), ("FX2 p2", 0x38, 24))


def db(x):
    return 20 * math.log10(x / 8388608) if x > 0 else -200.0


def rms(v):
    return math.sqrt(sum(x * x for x in v) / len(v)) if v else 0.0


def part_of(pdir, bank, part):
    """The tested part's ids, machine types and sample slots (0-based), and
    the pattern->part map of the bank."""
    data = (pdir / f"bank{bank:02d}.work").read_bytes()
    pat_part, _ = otp.bank_info(pdir, bank)
    c = data[otp.PART_BASE + (part - 1) * otp.PART_STRIDE:][:otp.PART_STRIDE]
    return dict(fx1=list(c[otp.FX1_OFF:otp.FX1_OFF + 8]), fx2=list(c[otp.FX2_OFF:otp.FX2_OFF + 8]),
                mtype=list(c[otp.MTYPE_OFF:otp.MTYPE_OFF + 8]),
                static=[c[0x2d3 + t * 5] for t in range(8)], flex=[c[0x2d3 + t * 5 + 1] for t in range(8)],
                levels=list(c[0x01b:0x02b:2]),
                pat_part=pat_part)


def midi_channels(pdir):
    """MIDI_TRIG_CHn from project.work, 0-based, per track."""
    raw = (pdir / "project.work").read_bytes().decode("latin1")
    return [int(m) for m in re.findall(r"MIDI_TRIG_CH\d=(-?\d+)", raw)][:8]


def sample_paths(pdir):
    """(type, slot 1-based) -> PATH= from project.work."""
    _, slots = otp.read_project(pdir)
    return {(s["type"], s["slot"]): s["path"] for s in slots if s["path"]}


def stage(pdir, part, set_name, name, tree, image_mb, bank, card):
    """A scratch copy of the project with [STATES] BANK= set to the tested
    bank, staged by stage_card.py (under the emulator .venv) with the
    tested part's samples at their card paths."""
    paths = sample_paths(pdir)
    audio, staged = [], set()
    for t in range(8):
        kind = TYPE_NAME.get(part["mtype"][t])
        if kind not in ("STATIC", "FLEX"):
            continue
        slot = (part["static"] if kind == "STATIC" else part["flex"])[t] + 1
        rel = paths.get((kind, slot))
        if not rel or rel in staged:
            continue
        staged.add(rel)
        src = (pdir / rel).resolve()
        card_path = rel[3:] if rel.startswith("../") else f"{name}/{rel}"
        for f, c in ((src, card_path), (src.with_suffix(".ot"), card_path[:-4] + ".ot")):
            if f.is_file():
                audio.append(f"{f}:{c}")
    total_mb = sum(pathlib.Path(x.split(":", 1)[0]).stat().st_size for x in audio) / 2**20
    mb = max(image_mb, 64 * math.ceil((total_mb * 1.5 + 16) / 64))
    copy = tree.parent / "project"
    if copy.exists():
        shutil.rmtree(copy)
    copy.mkdir(parents=True)
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)
    # The emulated load applies bank A's part and ends on bank A whatever
    # BANK= says (RTOS_FORK.md section 7), and the transport start's
    # refresher re-applies the saved bank's ids only for tracks it touches
    # (T1-T3, T7, T8 of the rig; T4-T6 kept bank A's, by --bank and by a
    # program change alike, 15 Sep 2026). The tested bank goes in as bank
    # A too, so both paths carry its part.
    if bank != 1:
        shutil.copy2(copy / f"bank{bank:02d}.work", copy / "bank01.work")
    pw = copy / "project.work"
    raw = pw.read_bytes()
    m = re.search(rb"\r\nBANK=(\d+)\r\n", raw)
    if not m:
        sys.exit("verify_set: project.work has no [STATES] BANK= line")
    raw = raw[:m.start()] + b"\r\nBANK=%d\r\n" % (bank - 1) + raw[m.end():]
    # Pattern 1: the part the gate reads is pattern 1's, and --poke-trig
    # lands in pattern 1 (a saved PATTERN=1 played pattern 2 with no trig
    # of its own and the whole set read silent, 15 Sep 2026).
    m = re.search(rb"\r\nPATTERN=(\d+)\r\n", raw)
    if m:
        raw = raw[:m.start()] + b"\r\nPATTERN=0\r\n" + raw[m.end():]
    # As port_compare: with the master track on nothing reaches TX0 under
    # the port (ring words 0..7 all zero, T8's read-back live); unmeasured
    # whether that is the port's or the unit's.
    raw = raw.replace(b"MASTER_TRACK=1", b"MASTER_TRACK=0")
    pw.write_bytes(raw)
    cmd = [str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), set_name, name,
           "--tree", str(tree), "--out", str(card), "--image-mb", str(mb)]
    for x in audio:
        cmd += ["--audio", x]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_set: stage_card failed:\n{r.stdout[-1000:]}{r.stderr[-1000:]}")
    return audio, mb


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--bank", type=int, default=int(os.environ.get("OT_BANK", "0")),
                    help="1-based (or OT_BANK); default: the project's saved bank")
    ap.add_argument("--frames", type=int, default=900,
                    help="after the transport start; the delay and the reverb each warm up 256 blocks, in series")
    ap.add_argument("--load-ms", type=int, default=90000, help="ceiling for the load (the port ends it when the engine's queue is idle; bottleservice needs ~32 s)")
    ap.add_argument("--set-name", default="OCTABAM")
    ap.add_argument("--name", default="RIG")
    ap.add_argument("--image-mb", type=int, default=64)
    ap.add_argument("--reuse", action="store_true", help="skip the port run when its dumps are there")
    ap.add_argument("--stage-only", action="store_true",
                    help="stage the image and the card and record the command line, run nothing: what the "
                         "image-stage gates that boot this card (TEMPO BUS) need, as their own shard job")
    ap.add_argument("--image", default="", help="a built image to boot instead of building the remix (a bisect)")
    ap.add_argument("--extra", default="", help="extra ot_emu arguments, e.g. '--dsp-dirty' (garbage DSP RAM, as hardware)")
    ap.add_argument("--midi-file", default="", help="extra MIDI IN lines appended to the gate's own "
                    "('<frame> <status> <d1> <d2>' in hex, one per line; T<n> in the status is that "
                    "track's channel): a knob script through the panel's real path")
    a = ap.parse_args()

    if not a.project:
        print("  [SKIP] verify_set: no project (OT_PROJECT=<dir> or --project)")
        return 0
    pdir = pathlib.Path(a.project).expanduser()
    if not (pdir / "project.work").is_file():
        sys.exit(f"verify_set: {pdir} is not an Octatrack project directory")
    if not EMU.exists():
        print("  [SKIP] verify_set: the ColdFire port is not built (make emu-cf)")
        return 0
    if not PY.exists():
        print("  [SKIP] verify_set: no .venv (make emu-setup)")
        return 0

    raw = (pdir / "project.work").read_bytes()
    m = re.search(rb"\r\nBANK=(\d+)\r\n", raw)
    bank = a.bank or (int(m.group(1)) + 1 if m else 1)
    if not (pdir / f"bank{bank:02d}.work").is_file():
        sys.exit(f"verify_set: no bank{bank:02d}.work in {pdir}")
    pat_part, _ = otp.bank_info(pdir, bank)
    part_no = pat_part[0] + 1                       # the port plays pattern 1
    part = part_of(pdir, bank, part_no)

    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "image.bin"
    if a.image:
        shutil.copy2(a.image, image)
    else:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_set: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    # MIDI IN: AUX to 100 on T2 at frame 40; with CC MAP, FX1 page-2 slot 6
    # to 77 on T1 at frame 40 (the page-1 slew takes ~30 frames).
    chans = midi_channels(pdir)
    ccmap = "CC MAP" in registry.remix(a.remix).modules
    midi = OUT / "in.midi"
    lines = [f"40 B{chans[1] & 0xf:X} 28 64",      # CC 40: DEL (slot 0)
             f"40 B{chans[1] & 0xf:X} 29 64"]      # CC 41: REV (slot 1), so T2 reaches both hosts
    ccmap = ccmap and part["fx1"][0] != 0          # the cave guards FX1 id 0 (NONE)
    if ccmap:
        lines.append(f"40 B{chans[0] & 0xf:X} 44 4D")
    # the bus engines' hosts: each prints its wet on its own track, so T2's
    # send must reach every host's chain output. Payload A serves T5-8 and
    # B T1-4 (measured 10 Aug 2026); an engine picked on the other core runs
    # as SEND under SPEC, which a set must not rely on.
    mods = registry.remix(a.remix).modules
    hosts = []
    for key, cores in (("REVERB SERVER", range(4, 8)), ("DELAY SERVER", range(0, 4))):
        if key not in mods:
            continue
        fid = registry.by_key(key).menu.fx2_id
        for t in (i for i, v in enumerate(part["fx2"]) if v == fid):
            if t not in cores:
                sys.exit(f"{key} on T{t + 1}: payload {'A' if t >= 4 else 'B'} does not carry it "
                         f"(it runs as SEND there); host it on T{cores[0] + 1}-T{cores[-1] + 1}")
            hosts.append((key, t))
    # BusVerb's DLY (FX2 page-2 slot 10 = CC 66 under CC MAP) at 55 on its
    # host's channel: the reverb publishes the knob field to the shared word
    # the delay reads (Y:0x982, 0x36082 under XBUS), read back on both cores.
    dly_host = next((t for key, t in hosts if key == "REVERB SERVER"), None) \
        if "CC MAP" in mods else None
    if dly_host is not None:
        lines.append(f"40 B{chans[dly_host] & 0xf:X} 42 37")
    # The hosts' own sends (26 Sep 2026: DEL / REV on page-1 slots 0 / 1, as
    # SEND's) and the delay's TIME on page-2 slot 11 (CC 67 under CC MAP):
    # each must reach its engine's own word, read back from the DSP --
    # a slot can draw a knob and publish nothing.
    verb_host = next((t for key, t in hosts if key == "REVERB SERVER"), None)
    del_host = next((t for key, t in hosts if key == "DELAY SERVER"), None)
    if del_host is not None:
        lines.append(f"40 B{chans[del_host] & 0xf:X} 29 32")      # CC 41: T1's REV = 50
        if "CC MAP" in mods:
            lines.append(f"40 B{chans[del_host] & 0xf:X} 43 28")  # CC 67: T1's TIME = 40
    if verb_host is not None:
        lines.append(f"40 B{chans[verb_host] & 0xf:X} 28 46")     # CC 40: T5's DEL = 70
        lines.append(f"40 B{chans[verb_host] & 0xf:X} 29 1E")     # CC 41: T5's REV = 30
    if a.midi_file:
        for ln in pathlib.Path(a.midi_file).read_text().splitlines():
            ln = ln.split("#")[0].strip()
            if not ln:
                continue
            m = re.match(r"(\S+)\s+B?T(\d)\s+(\S+)\s+(\S+)$", ln)
            if m:      # "<frame> BT<n> cc val" -> that track's channel
                ln = f"{m.group(1)} B{chans[int(m.group(2)) - 1] & 0xf:X} {m.group(3)} {m.group(4)}"
            lines.append(ln)
    midi.write_text("\n".join(lines) + "\n")

    dumps = {k: OUT / f"{k}.bin" for k in ("ids", "records", "lanes")}
    midi_out = OUT / "midi_out.bin" if "CC FEEDBACK" in mods else None
    if midi_out:
        # the stock emitter's per-channel cache and dirty bitmap, the engine's queue
        dumps.update(cccache=OUT / "cccache.bin", ccbits=OUT / "ccbits.bin", engq=OUT / "engq.bin")
    blocks, cmds, log, card_after = OUT / "port.dump", OUT / "port.cmds", OUT / "port.txt", OUT / "card_after.img"
    if not (a.reuse and blocks.is_file() and all(p.is_file() for p in dumps.values())):
        card = OUT / "card.img"
        audio, mb = stage(pdir, part, a.set_name, a.name, OUT / "tree", a.image_mb, bank, card)
        print(f"  card: {mb} MB, {len(audio)} sample file(s) staged for bank {bank} part {part_no}")
        cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", a.set_name, "--project", a.name,
               "--sequencer", "--internal-clock", "--frames", str(a.frames), "--load-ms", str(a.load_ms),
               "--dsp", "--main-level", "64", "--audio-in", "tones", "--poke-trig", "2", "--midi", str(midi),
               "--block-dump", str(blocks), "--cmd-log", str(cmds), "--card-out", str(card_after),
               "--mem-dump", f"{LIVE_IDS:#x},16={dumps['ids']};{RECORDS:#x},512={dumps['records']};{LANES:#x},576={dumps['lanes']}"
               + (f";0x46c7bf2c,2048={dumps['cccache']};0x46c7d7d8,256={dumps['ccbits']};0x460d17ce,16={dumps['engq']}" if midi_out else ""),
               "--dsp-peek", "0:Y:36082,1;1:Y:36082,1;1:X:6229,1;1:X:6275,1;0:Y:36081,1;0:Y:9f4,1"] \
            + (["--midi-out", str(midi_out)] if midi_out else []) + a.extra.split()
        if a.stage_only:
            log.write_text(" ".join(cmd) + "\n")
            print(f"verify_set: staged {image.name} and {card.name} for bank {bank} part {part_no}, nothing run -- {OUT}")
            return 0
        with open(log, "w") as f:
            f.write(" ".join(cmd) + "\n"); f.flush()
            r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode:
            sys.exit(f"verify_set: ot_emu exit {r.returncode} -- {log}")
    text = log.read_text()

    fails = 0
    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    # load
    loaded = "LOAD PROJECT posted: yes" in text
    ran = re.search(r"frames run : (\d+) since transport start \(target (\d+)\), run ended (\w+)", text)
    check("load: LOAD PROJECT completed and the frames ran",
          loaded and ran is not None and ran.group(3) == "REACHED",
          f"frames {ran.group(1)}/{ran.group(2)} {ran.group(3)}" if ran else "no frames line")

    # ids
    ids = dumps["ids"].read_bytes()
    live1, live2 = list(ids[:8]), list(ids[8:16])
    check(f"ids: live FX1/FX2 == bank {bank} part {part_no}", live1 == part["fx1"] and live2 == part["fx2"],
          f"FX1 {bytes(live1).hex(' ')} FX2 {bytes(live2).hex(' ')}"
          + ("" if live1 == part["fx1"] and live2 == part["fx2"]
             else f" (part: FX1 {bytes(part['fx1']).hex(' ')} FX2 {bytes(part['fx2']).hex(' ')})"))

    # page 2: the record carries the lane
    recs, lanes = dumps["records"].read_bytes(), dumps["lanes"].read_bytes()
    for t in range(8):
        rec, lane = recs[64 * t:64 * t + 64], lanes[72 * t:72 * t + 72]
        bad = []
        for what, lo, hw in P2_LANES:
            want, got = lane[lo:lo + 6], rec[2 * hw:2 * hw + 6]
            if want != got:
                bad.append(f"{what} lane {want.hex()} record {got.hex()}")
        check(f"page 2: T{t + 1} record halfwords 18-26 == the lane", not bad, "; ".join(bad))

    # midi
    def sent(knob, t):
        """The DSP-bound halfword of a send knob on track t: the knob << 8, or
        with POST FADER in the remix the knob << 8 x (LEVEL/128)^2 from the
        Part's LEVEL (modules/post-fader; no track these checks use is muted)."""
        hw = knob << 8
        return hw * part["levels"][t] ** 2 >> 14 if "POST FADER" in mods else hw

    def word(knob, t):                     # as the engines read it: masked, << 8
        return f"{(sent(knob, t) & 0x7f00) << 8:06x}"

    aux = recs[64 + 24] << 8 | recs[64 + 25]                     # T2 halfword 12
    t2_fx2 = registry.by_id(part["fx2"][1])
    if t2_fx2 is not None and t2_fx2.key in mods:
        want = sent(100, 1)
        check("midi: CC 40 = 100 on T2's channel reached T2's AUX halfword"
              + (" (post-fader)" if "POST FADER" in mods else ""),
              (aux >> 8) == 100 if "POST FADER" not in mods else aux == want,
              f"halfword 12 = {aux:#06x} (want {want:#06x}; the lane's slew takes ~30 frames)")
    else:
        # an unimplemented id runs the fallback, whose page publishes no slot 0
        print(f"  [skip] midi: CC 40 -> T2 slot 0: the part's T2 FX2 id 0x{part['fx2'][1]:02x} "
              f"is not a module of this remix")
    if ccmap:
        # the cave clamps to the slot's count from the descriptor: slot 6 is
        # every effect's MODE since 16 Sep 2026, so 77 lands as count - 1
        # The id's module in THIS remix: a station's id is a stock effect's
        # (Character = LO-FI 0x1c), and a remix without the station runs
        # stock's, whose slot 6 counts 128 -- kits and scenes read 77 back
        # while the check wanted Character's count of 3 (27 Sep 2026).
        fx1_id = part["fx1"][0]
        fx1_mod = registry.by_id(fx1_id)
        if fx1_mod is None or fx1_mod.key not in mods:
            fx1_mod = next((m for m in stock.MODULES if m.menu.fx2_id == fx1_id), None)
        cnt = (fx1_mod.params[6].count or 128) if fx1_mod is not None and fx1_mod.params else 128
        want = min(77, cnt - 1)
        lane_v, rec_v = lanes[0x32], recs[2 * 18]
        check(f"midi: CC 68 = 77 on T1's channel reached T1's FX1 page-2 slot 6 (CC MAP; count {cnt} -> {want})",
              lane_v == want and rec_v == want, f"lane +0x32 = {lane_v}, record halfword 18 high byte = {rec_v}")
    if dly_host is not None:
        pk = dict(re.findall(r"core (\d) Y:0x36082: ([0-9a-f]{6})", text))
        check(f"midi: CC 66 = 55 on T{dly_host + 1}'s channel reached BusVerb's DLY, published to "
              f"Y:0x36082 on both cores", pk.get("0") == pk.get("1") == "370000",
              f"core 0 {pk.get('0', '?')}, core 1 {pk.get('1', '?')}")
    # the hosts' sends and the delay's TIME, as their engines read them
    peek = {(c, sp, int(ad, 16)): v for c, sp, ad, v in
            re.findall(r"core (\d) ([XY]):0x([0-9a-f]+): ([0-9a-f]{6})", text)}
    if del_host is not None:
        v = peek.get(("1", "X", 0x6229))
        check(f"midi: CC 41 = 50 on T{del_host + 1}'s channel reached BusDelay's REV "
              f"(raw $29 of its block, X:0x6229 on core 1)", v == word(50, del_host),
              f"{v} (want {word(50, del_host)})")
        if "CC MAP" in mods:
            v = peek.get(("1", "X", 0x6275))
            n = int(v, 16) if v else -1
            want = 64 + 40 * 256                      # 10,304 samples; the sticky
            check(f"midi: CC 67 = 40 on T{del_host + 1}'s channel reached BusDelay's TIME "  # snap may pull
                  f"(page-2 slot 11; X:0x6275 on core 1, samples)",                           # it within free/16
                  abs(n - want) <= want // 16, f"{n} (want {want} +-{want // 16})")
    if verb_host is not None:
        v = peek.get(("0", "Y", 0x36081))
        check(f"midi: CC 41 = 30 on T{verb_host + 1}'s channel reached BusVerb's REV flag "
              f"(Y:0x36081 on core 0)", v == word(30, verb_host), f"{v} (want {word(30, verb_host)})")
        v = peek.get(("0", "Y", 0x9f4))
        check(f"midi: CC 40 = 70 on T{verb_host + 1}'s channel reached BusVerb's DEL ramp "
              f"(Y:0x09f4 on core 0)", v == word(70, verb_host), f"{v} (want {word(70, verb_host)})")
    m = re.search(r"midi in    : (\d+) byte\(s\) still queued", text)
    check("midi: the firmware took every byte", m is not None and m.group(1) == "0",
          f"{m.group(1) if m else '?'} queued at the end")
    if midi_out:
        # CC FEEDBACK (modules/cc-feedback). The stock emitter 0x40033e3c
        # queues: its cache 0x46c7bf2c + ch*128 + cc holds the last value
        # queued per (channel, CC), its bitmap the CCs not yet on the wire,
        # and the drainer paces the wire to MIDI bandwidth (DTIM2 re-armed
        # for the batch's wire time). The module's contract is the CACHE:
        # every mapped lane byte (page 1 = CC 16-45, FX1 page 2 = 68-73,
        # FX2 page 2 = 62-67) equals it within eight UI ticks while the
        # engine is idle. The wire is checked for shape: every CC sent is a
        # mapped slot on a track's channel, with the cache's value at the
        # time (the stream carries only values the cache held).
        cfmap = [(i, 16 + i) for i in range(30)] + [(0x32 + i, 68 + i) for i in range(6)] + [(0x38 + i, 62 + i) for i in range(6)]
        cache, bits, engq = dumps["cccache"].read_bytes(), dumps["ccbits"].read_bytes(), dumps["engq"].read_bytes()
        engine_idle = int.from_bytes(engq[12:16], "big") != 0
        pending = sum(bin(int.from_bytes(bits[ch * 16 + 4 * k:ch * 16 + 4 * k + 4], "big")).count("1") for ch in range(16) for k in range(4))
        msgs, st, buf = [], None, []
        for x in (midi_out.read_bytes() if midi_out.is_file() else b""):
            if x >= 0xf8:
                continue
            if x & 0x80:
                st, buf = x, []
            else:
                buf.append(x)
                if st is not None and st >> 4 == 0xb and len(buf) == 2:
                    msgs.append((st & 15, buf[0], buf[1])); buf = []
        ch_track = {chans[t] & 0xf: t for t in range(8) if chans[t] >= 0}
        mapped = {cc for _, cc in cfmap}
        # CC 48 is stock's own crossfader echo (MIDI.md section 4), sent on the
        # current track's channel from the panel path, not the module's
        stray = [(ch, cc) for ch, cc, _ in msgs if cc != 48 and (ch not in ch_track or cc not in mapped)]
        wrong = []
        for t in range(8):
            if chans[t] < 0:
                continue
            ch = chans[t] & 0xf
            for off, cc in cfmap:
                want, got = lanes[72 * t + off], cache[ch * 128 + cc]
                if got != want:
                    wrong.append(f"T{t + 1} CC {cc} cache {got} lane {want}")
        check(f"midi out: every CC sent is a mapped slot on a track's channel ({len(msgs)} CCs on {len({(c, n) for c, n, _ in msgs})} slots)",
              bool(msgs) and not stray, f"stray {sorted(set(stray))[:6]}" if stray else "")
        if engine_idle:
            check("midi out: the emitter's cache holds every mapped lane byte (CC FEEDBACK swept every change)",
                  not wrong, "; ".join(wrong[:6]))
        else:
            print(f"  [N/A] midi out: the engine was running a command at the end; the sweep waits, {len(wrong)} slot(s) differ")
        # Informational: the bytes after the transport start are the dump's
        # tail (the load's part, dumped once the engine is idle, drained at
        # MIDI bandwidth), the echo of the CCs sent in, and any change the
        # pattern made. A step-rate stream from locks would show here; this
        # fixture plays no locks under the port (no pattern trig fires,
        # tools/emu/README.md).
        m = re.search(r"midi out   : (\d+) byte\(s\) on UART0 \((\d+) after the transport start\)", text)
        print(f"  [info] midi out: {m.group(1) if m else '?'} bytes on UART0, {m.group(2) if m else '?'} after the transport start, "
              f"{pending} CC(s) still queued, {a.frames} frames")

    # audio
    import blockdump as bd, recloop as rl
    c = bd.classes(bd.read(str(blocks)))
    silent_chain = []
    rows = []
    for t in range(1, 9):
        inL, outL = rl.track_audio(c, t), rl.readback_audio(c, t)
        i_db, o_db = db(rms(inL[-2000:])), db(rms(outL[-2000:]))
        kind = TYPE_NAME.get(part["mtype"][t - 1], "?")
        rows.append(f"T{t} {kind:6} in {i_db:7.1f} out {o_db:7.1f}")
        if i_db > -120 and o_db <= -120:
            silent_chain.append(f"T{t}")
    print("        " + "  ".join(rows[:4]) + "\n        " + "  ".join(rows[4:]))
    check("audio: every track with record audio has a chain output", not silent_chain,
          f"silent chain: {', '.join(silent_chain)}" if silent_chain else "")
    for key, t in hosts:
        wet = db(rms(rl.readback_audio(c, t + 1)[-2000:]))
        check(f"audio: {key}'s host T{t + 1} carries T2's send", wet > -60,
              f"T{t + 1} chain output {wet:.1f} dBFS in the last 2000 samples")
    # the report prints both cores' audio lines at the boot, the load and
    # the end; core 0's at the end is the ESAI's, and it carries the counts.
    # Informational: on OCTABAM89_setgate bank 3 part 1 only T8's chain
    # output ever reached TX0 under the port (20 Sep 2026: with T8's station
    # silent the words read all-zero while T1, T2 and T5's chain outputs
    # were live, on the image with the return and on the one without).
    # Which tracks reach TX0 under the port is open.
    tx = re.findall(r"TX0 non-zero per RING WORD \(slot \+ rotation [0-9.]+\) ([0-9 ]+);", text)
    nz = max(([int(x) for x in t.split()] for t in tx), key=sum, default=[])
    print(f"  [info] audio: the main out (TX0) non-zero frames per ring word {nz or 'no TX0 line'}")

    # the card as the firmware left it
    n_writes = sum(1 for l in cmds.read_text().splitlines() if l.startswith("WRITE"))
    r = subprocess.run([str(PY), "-c", "import sys, json, pathlib; sys.path.insert(0, 'tools'); import toolpath; "
                        "import emu_card as ec; b = ec.extract_image(pathlib.Path(sys.argv[1]).read_bytes()); "
                        "a = ec.extract_image(pathlib.Path(sys.argv[2]).read_bytes()); "
                        "print(json.dumps({'changed': sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k)), "
                        "'log': a.get('LOG 000000.txt', b'').decode('latin1')}))",
                        str(OUT / "card.img"), str(card_after)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_set: reading the card back failed:\n{r.stderr[-1000:]}")
    import json
    cd = json.loads(r.stdout)
    rewritten = [k for k in cd["changed"] if not k.startswith("LOG ")]
    if "OCTAKIT" in mods:
        # Octakit's load migrates Parts into kits*.strd/.work files (modules/octakit)
        kits = [k for k in rewritten if pathlib.Path(k).name.startswith("kits")]
        rewritten = [k for k in rewritten if k not in kits]
        check("card: with Octakit the load rewrote only kits files", not rewritten,
              f"{n_writes} WRITE command(s); kits: {', '.join(kits) or 'none'}"
              + (f"; other: {', '.join(rewritten)}" if rewritten else ""))
    else:
        check("card: the load rewrote no project file", not rewritten,
              f"{n_writes} WRITE command(s); " + (", ".join(rewritten) if rewritten else "the firmware's LOG only"))
    unstaged = re.compile(r"Couldn't load (STATIC|FLEX)\[\d+\] with '.*' \('FILE NOT FOUND'\)")
    errors = [l for l in cd["log"].splitlines() if " ERROR " in l and not unstaged.search(l)]
    n_nf = sum(1 for l in cd["log"].splitlines() if unstaged.search(l))
    check("card: the firmware's LOG has no error beyond the unstaged samples", not errors,
          f"{n_nf} FILE NOT FOUND" + ("; " + " | ".join(l.split(" ERROR ", 1)[1] for l in errors[:4]) if errors else ""))

    print(f"verify_set: bank {bank} part {part_no} of {pdir.name} on {a.remix}: {fails} failure(s) -- {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
