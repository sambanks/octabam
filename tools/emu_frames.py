#!/usr/bin/env python3
"""Run the firmware's audio-frame interrupt handler cold, one frame at a time,
and log the per-track trigger word the per-frame dispatcher reads.

Why: Bryan T's session-5 ask (docs/EXTERNAL.md §6, 6 Sep 2026) — with a
project loaded and the sequencer running, does the low nibble of the
per-track trigger word (the trig's sample offset within the 16-sample frame)
walk from pass to pass when the pattern length in samples is not an integer
number of frames? Static reading cannot show an accumulator moving; a
frame-by-frame trace can.

What runs: the frame builder `0x4000aad0` is the DSP-frame INTERRUPT handler
(prologue `lea sp@(-252) / moveml d0-fp`, re-entry guard `0x46104d4e`, ping
swap `0x800000e0 -> e4`, ..., the per-track dispatcher `0x4000d2a0`, the
packer `0x4000d3fc`, `rte`). We push a ColdFire exception frame whose return
PC is the detour sentinel and run it to the `rte`. The dispatcher reads each
track's word through the slot `%sp@(144)` = `0x46104d26 + 2*track` at
`0x4000d32e` (Bryan's anchor; the pointer is planted at `0x4000c87c`) — a hook
there logs (frame, track, word).

Run:  .venv/bin/python3 tools/emu_frames.py --project <dir> --frames 3000 [--bpm 128]
"""
import argparse
import collections
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emu_bringup as eb  # noqa: E402
import emu_card as ec     # noqa: E402

FW_FRAME_ISR = 0x4000aad0        # DSP-frame interrupt handler = the frame builder
FW_TICK_ISR = 0x400a1e10         # sequencer tick interrupt handler (MIDI clock rate, 24 PPQN):
                                 # acks the INTC, sends 0xF8, advances the tick clock 0x4610757c by
                                 # 2,646,000 (= a 16th step / 6) and re-syncs the frame clock
                                 # 0x46104cf4 to it, then steps the sequencer
TICK_UNITS = 2_646_000           # tick clock units: 1 sample = tempo24 units
FW_FORCE_TICKS = (0x4000ae00, 0x4000aea0)  # frame handler: `orl %d0,0xfc048010` — the regular tick force
                                 # forced interrupt when its countdown (0x46107568, decremented by
                                 # tempo24<<4 per frame) expires; the tick handler acks it on entry
FW_MIDI_SETTINGS = 0x80000028    # project MIDI byte: bit 0 = clock receive (external clock)
FW_DISPATCH_READ = 0x4000d32e    # `mvzw %a0@,%d2` — the per-track trigger word
FW_TRIG_WORDS = 0x46104d26       # 8 x u16, one per track (Bryan T §14.10)
FW_SEQ_STATE = 0x800065b8        # 0 stopped, 1 playing, 2 (seen in 0x4009f5bc)
FW_TRANSPORT = 0x4009b964        # (arg) sequencer transport routine; start case at 0x4009c458
FW_TEMPO24 = 0x80001814
FW_TEMPO_SHADOW = 0x80000020
FRAME_SP = 0x47f70000            # stack for the cold-run interrupt handler


def run_frame(s):
    """One frame: fake exception frame, run the handler to its rte."""
    uc = s.uc
    sp = FRAME_SP - 8
    # ColdFire exception stack frame: format/vector word, SR, return PC
    uc.mem_write(sp, (0x40C0).to_bytes(2, "big") + (0x2000).to_bytes(2, "big")
                 + eb.CALL_RET.to_bytes(4, "big"))
    uc.reg_write(eb.UC_M68K_REG_A7, sp)
    uc.reg_write(eb.UC_M68K_REG_SR, 0x2700)
    trap = eb._run_until(uc, FW_FRAME_ISR, eb.CALL_RET)
    if trap is not None and trap[0] == 256:
        return                      # the handler's own `rte` (0x4000d9ae): the frame is done
    if trap is not None:
        raise eb.DetourTrap(trap[0], trap[1], "frame handler")


def run_isr(s, entry, sp_top):
    uc = s.uc
    sp = sp_top - 8
    uc.mem_write(sp, (0x40C0).to_bytes(2, "big") + (0x2000).to_bytes(2, "big")
                 + eb.CALL_RET.to_bytes(4, "big"))
    uc.reg_write(eb.UC_M68K_REG_A7, sp)
    uc.reg_write(eb.UC_M68K_REG_SR, 0x2700)
    trap = eb._run_until(uc, entry, eb.CALL_RET)
    if trap is not None and trap[0] == 256:
        return
    if trap is not None:
        raise eb.DetourTrap(trap[0], trap[1], f"isr {entry:#x}")


def run_tick(s):
    """One sequencer tick (the timer interrupt), run cold like the frame."""
    run_isr(s, FW_TICK_ISR, FRAME_SP - 0x4000)


class Clock:
    """The tick is a FORCED interrupt the frame handler raises when its own
    countdown expires (no hardware timer): hook that write, and run the tick
    handler right after the frame that raised it. Interrupt priority is the
    one thing not modelled — on hardware the forced tick may pre-empt the
    frame handler before it finishes rather than follow it."""
    def __init__(self, s, t24):
        self.t24 = t24
        self.sample = 0                  # first sample of the next frame
        self.ticks = 0
        self.pending = False
        for site in FW_FORCE_TICKS:
            s.uc.hook_add(eb.UC_HOOK_CODE, lambda u, a, sz, d: setattr(self, "pending", True),
                          begin=site, end=site)
        s.uc.ctl_flush_tb()

    def advance(self, s):
        """Call AFTER run_frame: run the tick the frame forced, if any."""
        ran = 0
        while self.pending:
            self.pending = False
            run_tick(s)
            self.ticks += 1; ran += 1
            if getattr(s, "tick_trace", None) is not None and self.ticks <= 60:
                u = s.uc
                r32 = lambda a: int.from_bytes(u.mem_read(a, 4), "big")
                s.tick_trace.append((self.ticks, self.sample, r32(0x4610757c), r32(0x46104cf4),
                                     r32(0x46107568), r32(0x4610756c), r32(0x46107564),
                                     r32(FW_SEQ_STATE), u.mem_read(0x80006511, 1)[0],
                                     u.mem_read(0x8000005b, 1)[0], r32(0x800066d4),
                                     u.mem_read(0x80000028, 1)[0], u.mem_read(0x80001860, 1)[0],
                                     bytes(u.mem_read(0x80001904, 16)).hex()))
        self.sample += 16
        return ran


def set_tempo(s, bpm, tenths=0):
    t24 = 24 * int(bpm) + (23 * tenths + 4) // 9
    for a in (FW_TEMPO24, FW_TEMPO_SHADOW):
        s.uc.mem_write(a, t24.to_bytes(4, "big"))
    return t24


def install_trig_log(s):
    uc = s.uc
    log = []
    state = {"frame": 0, "track": 0}

    def on_read(u, addr, size, user):
        a0 = u.reg_read(eb.UC_M68K_REG_A0)
        d3 = u.reg_read(eb.UC_M68K_REG_D3)          # the dispatcher's track counter
        w = int.from_bytes(u.mem_read(a0, 2), "big")
        state["reads"] = state.get("reads", 0) + 1
        if w:
            log.append((state["frame"], d3, w))
    uc.hook_add(eb.UC_HOOK_CODE, on_read, begin=FW_DISPATCH_READ, end=FW_DISPATCH_READ)
    uc.ctl_flush_tb()
    s.trig_log = log
    s.frame_state = state
    return log


def _cli():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--set", default="OCTABAM")
    ap.add_argument("--name", default=None)
    ap.add_argument("--image", default="out/emu_card.img")
    ap.add_argument("--firmware", default=None)
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--bpm", type=float, default=None)
    ap.add_argument("--start", action="store_true", help="start the sequencer via the transport routine")
    ap.add_argument("--kick", type=int, default=0, help="force the step countdown word 0x80006514 after start")
    ap.add_argument("--internal-clock", action="store_true",
                    help="clear the project's CLOCK RECEIVE bit so the sequencer runs on its own clock")
    a = ap.parse_args()

    import shutil
    src = pathlib.Path(a.project); name = a.name or src.name
    tree = pathlib.Path("out/_emu_frames_tree")
    if tree.exists():
        shutil.rmtree(tree)
    dst = tree / a.set / name; dst.mkdir(parents=True); (tree / a.set / "AUDIO").mkdir()
    for p in sorted(src.iterdir()):
        if p.is_file() and not p.name.startswith("._") and p.suffix.lower() not in (".wav", ".ot"):
            shutil.copy2(p, dst / p.name)
    img = ec.build_image(str(tree), 64)
    # The frame handler's DSP handshake: the ping index arrives on the host
    # port 0x2000001c (must be 0 or 1, else `halt` at 0x4000ab40) and the
    # command register 0x20000004 is polled until bit 7 clears (0x4000ab26).
    ping = {"v": 0}
    def dsp_ping(uc, addr, size):
        ping["v"] ^= 1
        return ping["v"]
    eb.EXTRA_OVERRIDES[0x2000001c] = dsp_ping
    eb.EXTRA_OVERRIDES[0x20000004] = 0x0000
    r, s = ec.boot_with_card(a.firmware, img)
    print("boot       :", r.stopped)
    print("card init  :", ec.card_init(s))
    print("load       :", ec.load_project(s, a.set, name)[:3])
    if a.bpm is not None:
        print("tempo24    :", set_tempo(s, int(a.bpm), int(round((a.bpm - int(a.bpm)) * 10))))
    midi = s.uc.mem_read(FW_MIDI_SETTINGS, 1)[0]
    print(f"midi byte  : 0x{midi:02x} (bit 0 = clock receive)")
    if a.internal_clock and midi & 1:
        s.uc.mem_write(FW_MIDI_SETTINGS, bytes([midi & ~1]))
        print("midi byte  : clock receive cleared -> internal clock")
    if a.start:
        # the transport routine 0x4009b964(arg): with the sequencer stopped it
        # runs the start case (state := 1, phase increment := tempo24 << 4 at
        # 0x46107570, per-track states, a post to the timer queue 0x460d1664)
        eb._call(s.uc, FW_TRANSPORT, [0])
        print("transport  : state", int.from_bytes(s.uc.mem_read(FW_SEQ_STATE, 4), "big"),
              " phase inc 0x46107570:", int.from_bytes(s.uc.mem_read(0x46107570, 4), "big"))
    if a.kick:
        s.uc.mem_write(0x80006514, (a.kick).to_bytes(2, "big"))
        print(f"kick       : step countdown 0x80006514 := {a.kick}")
    w6514 = []
    s.uc.hook_add(eb.UC_HOOK_MEM_WRITE,
                  lambda u, acc, ad, sz, val, d: len(w6514) < 30 and w6514.append((s.frame_state.get("frame", -1) if hasattr(s, "frame_state") else -1, hex(u.reg_read(eb.UC_M68K_REG_PC)), val)),
                  begin=0x80006514, end=0x80006515)
    log = install_trig_log(s)
    # diagnostics: QREC scheduler calls, immediate-array writes, tick-advance calls
    diag = collections.Counter()
    imm_writes = []
    s.uc.hook_add(eb.UC_HOOK_CODE, lambda u, ad, sz, d: diag.update(["qrec 0x40005178"]), begin=0x40005178, end=0x40005178)
    s.uc.hook_add(eb.UC_HOOK_CODE, lambda u, ad, sz, d: diag.update(["advance 0x400a1608"]), begin=0x400a1608, end=0x400a1608)
    gate = []
    def on_gate(u, ad, sz, d):
        diag.update(["step engine 0x400a1f68"])
        if len(gate) < 24:
            r = lambda a: int.from_bytes(u.mem_read(a, 4), "big")
            gate.append((r(0x46107568), r(0x4610756c), r(0x46107570), r(0x4610757c)))
    s.uc.hook_add(eb.UC_HOOK_CODE, on_gate, begin=0x400a1f68, end=0x400a1f68)
    probe = []
    def on_probe(u, ad, sz, d):
        if len(probe) < 24:
            r = lambda a: int.from_bytes(u.mem_read(a, 4), "big")
            probe.append((hex(ad), r(0x46107568), r(0x4610756c), r(0x46107570)))
    for site in (0x400a1e68, 0x400a1eb0, 0x400a1eda, 0x400a1f22):
        s.uc.hook_add(eb.UC_HOOK_CODE, on_probe, begin=site, end=site)
    s.uc.hook_add(eb.UC_HOOK_CODE, lambda u, ad, sz, d: diag.update(["step engine skip 0x400a2530"]), begin=0x400a2530, end=0x400a2530)
    def on_imm(u, access, addr, size, val, d):
        if len(imm_writes) < 40:
            imm_writes.append((s.frame_state["frame"], hex(addr), hex(val), hex(u.reg_read(eb.UC_M68K_REG_PC))))
    s.uc.hook_add(eb.UC_HOOK_MEM_WRITE, on_imm, begin=0x46c7e9fa, end=0x46c7e9fa + 0x20)
    blocks = collections.Counter()
    s.uc.hook_add(eb.UC_HOOK_BLOCK, lambda u, ad, sz, d: blocks.update([ad >> 8]))
    s.uc.ctl_flush_tb()
    t24 = int.from_bytes(s.uc.mem_read(FW_TEMPO24, 4), "big")
    clock = Clock(s, t24)
    seq_before = bytes(s.uc.mem_read(0x800065b0, 0x150))
    s.tick_trace = []
    for f in range(a.frames):
        s.frame_state["frame"] = f
        try:
            run_frame(s)
            if a.start:
                clock.advance(s)
        except (eb.DetourTrap, eb.DetourStall) as e:
            print(f"frame {f}: {e}  pc={s.uc.reg_read(eb.UC_M68K_REG_PC):#x}")
            break
    print(f"frames run : {f + 1}  ticks: {clock.ticks}  trig words seen: {len(log)}")
    print("hot pages  :", [(hex(k << 8), v) for k, v in blocks.most_common(12)])
    for e in log[:24]:
        print("   frame %5d track %d word %04x nibble %x flags %02x" % (e[0], e[1], e[2], e[2] & 0xF, e[2] & 0xF0))
    # per track: sample position of each trig word, and the deltas between them
    by_track = collections.defaultdict(list)
    for fr, tr, w in log:
        by_track[tr].append(fr * 16 + (w & 0xF))
    for tr in sorted(by_track):
        pos = by_track[tr]
        deltas = [b - a for a, b in zip(pos, pos[1:])]
        print(f"track {tr + 1}: {len(pos)} trigs; positions {pos[:10]}; deltas {deltas[:12]}")
    print("tick trace (tick, sample, tickclk, frameclk, 7568, 756c, 7564, state, step, plen, 66d4, 0x28, 0x1860, events[0:16]):")
    for t in s.tick_trace[:40]:
        print("   ", t)
    u = s.uc
    r32 = lambda a: int.from_bytes(u.mem_read(a, 4), "big")
    print("dispatch reads:", s.frame_state.get("reads", 0), " bypass 0x800018fe:", r32(0x800018fe),
          " step 0x80006511:", u.mem_read(0x80006511, 1)[0], " plen 0x8000005b:", u.mem_read(0x8000005b, 1)[0],
          " 0x80006686:", u.mem_read(0x80006686, 1)[0], " countdown 0x46107570:", r32(0x46107570))
    print("trig words 0x46104d26:", bytes(u.mem_read(FW_TRIG_WORDS, 16)).hex())
    print("events 0x80001904:", bytes(u.mem_read(0x80001904, 64)).hex())
    print("tick trace rows:", len(s.tick_trace))
    seq_after = bytes(u.mem_read(0x800065b0, 0x150))
    print("seq block 0x800065b0 before:", seq_before[:0x60].hex())
    print("seq block 0x800065b0 after :", seq_after[:0x60].hex())
    diffs = [(hex(0x800065b0 + i), seq_before[i], seq_after[i]) for i in range(len(seq_before)) if seq_before[i] != seq_after[i]]
    print("changed bytes:", diffs[:40])
    print("playing bank 0x800065bd:", u.mem_read(0x800065bd, 1).hex(), " pattern 0x800065be:", u.mem_read(0x800065be, 1).hex(),
          " 0x800065bc:", u.mem_read(0x800065bc, 1).hex(), " preroll 0x80006687:", u.mem_read(0x80006687, 1).hex(),
          " cur bank 0x80000002:", u.mem_read(0x80000002, 1).hex(), " pattern 0x80000004:", u.mem_read(0x80000004, 1).hex())
    print("diag:", dict(diag))
    print("writes to 0x80006514 (frame, pc, val):", w6514[:30])
    print("at step-engine gate (7568, 756c, 7570, tickclk):", gate[:16])
    print("probes through the tick handler (site, 7568, 756c, 7570):", probe[:24])
    print("immediate-array writes:", imm_writes[:20])
    print("tick counter 0x46c7a19c:", r32(0x46c7a19c), " 0x46107574:", r32(0x46107574), " 0x800066d4:", r32(0x800066d4))
    print("tick clock 0x4610757c:", int.from_bytes(s.uc.mem_read(0x4610757c, 4), "big"),
          " frame clock 0x46104cf4:", int.from_bytes(s.uc.mem_read(0x46104cf4, 4), "big"))
    print("seq state  :", int.from_bytes(s.uc.mem_read(FW_SEQ_STATE, 4), "big"),
          " tempo24:", int.from_bytes(s.uc.mem_read(FW_TEMPO24, 4), "big"),
          " 0x8000181c:", int.from_bytes(s.uc.mem_read(0x8000181c, 4), "big"),
          " 0x80001820:", hex(int.from_bytes(s.uc.mem_read(0x80001820, 4), "big")))


if __name__ == "__main__":
    _cli()
