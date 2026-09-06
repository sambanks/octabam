#!/usr/bin/env python3
"""Run the firmware's audio-frame interrupt handler cold, one frame at a time,
with the sequencer transport started, and log what a step trig actually does
to the per-track state the frame dispatcher reads.

Why: Bryan T's session-5 ask (docs/EXTERNAL.md §6, 6 Sep 2026) — with a
project loaded and the sequencer running, does the low nibble of a trig's
per-track word (its sample offset within the 16-sample frame) walk from pass
to pass when the pattern length in samples is not an integer number of
frames? Static reading cannot show an accumulator moving; a frame-by-frame
trace can.

What runs, measured in the emulator (docs/EMU.md M5 has the full account):

- The frame builder `0x4000aad0` is the DSP-frame interrupt handler; `run_frame`
  pushes a ColdFire exception frame and runs it to its own `rte`.
- The sequencer tick `0x400a1e10` is a FORCED interrupt the frame handler
  raises itself (a countdown at `0x46107570`, decremented by `tempo24<<4` per
  frame); `Clock` hooks the force sites and runs the tick right after the
  frame that raised it.
- The transport `0x4009b964(0)` + per-track `0x4009b5c8(t)` start the
  sequencer; with a mask bit set, the per-track step handler `0x4009d1e8`
  schedules an absolute fire time into the event table `0x80001904[track]`.
- Each frame, the trig-time loop `0x4000aef6` turns "time - now" into a
  clamped sample offset for every entry and stores it per track at
  `0x800017d6[]`. The per-frame gate at `0x4000b800` (NOT `0x4000d32e`/
  `0x46104d26` -- see below) tests the event against the frame clock and,
  when due and the track isn't muted for it, copies that byte into
  `0x46104d15[track]` and ORs in flag bits (`0x10` = hold, confirmed here).
  This is the live artifact: FW_TRIG_WORDS never moved in any run so far.

**Open finding, not yet resolved**: `FW_TRIG_WORDS` (`0x46104d26`, the array
Bryan named and the one `0x4000d32e` reads) stayed all-zero through every
run here, including one where a trig demonstrably fired and reached
`0x46104d15`. `0x4000d378` (its only writer found so far) writes zero to it
every frame regardless. Bryan's literal ask needs a RECORDER ARMED on the
track, which this harness has not set up (the test project has an ordinary
playback trig, not a record-enabled track) -- that is the next step, not
something this run answers.

Run:  .venv/bin/python3 tools/emu_frames.py --project <dir> --frames 3000 [--bpm 128] --start --internal-clock --poke-trig N
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
FW_FORCE_TICKS = (0x4000ae00, 0x4000aea0)  # frame handler: `orl %d0,0xfc048010` -- the regular tick force
                                 # forced interrupt when its countdown (0x46107568, decremented by
                                 # tempo24<<4 per frame) expires; the tick handler acks it on entry
FW_MIDI_SETTINGS = 0x80000028    # project MIDI byte: bit 0 = clock receive (external clock)
FW_DISPATCH_READ = 0x4000d32e    # `mvzw %a0@,%d2` -- reads FW_TRIG_WORDS[track]; stayed zero here
FW_TRIG_WORDS = 0x46104d26       # 8 x u16, one per track (Bryan T §14.10); NOT the live artifact
                                 # in an ordinary-trig test -- see module docstring
FW_LIVE_NIBBLE = 0x46104d15      # 8 x u8, one per track: the byte that DOES change on a fired trig
                                 # (sub-frame sample offset in the low bits, flags OR'd in above it:
                                 # 0x10 = hold, confirmed 6 Sep); written at 0x4000b910 (copy) and
                                 # 0x4000b9bc/0x4000b9f2 (flag OR), gated by the due-check at
                                 # 0x4000b84c and the mute-check at 0x4000b8de
FW_SEQ_STATE = 0x800065b8        # 0 stopped, 1 playing, 2 (seen in 0x4009f5bc)
FW_TRANSPORT = 0x4009b964        # (arg) sequencer transport routine; start case at 0x4009c458
FW_START_TRACK = 0x4009b5c8      # (track): sets the per-track running state 0x80006500[t] := 1 if
                                 # the playing pattern marks the track active (pattern rec +84 +
                                 # 2330*t); the PLAY key path calls it per track, the transport
                                 # start only promotes tracks already in state 2
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
    one thing not modelled -- on hardware the forced tick may pre-empt the
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
        self.sample += 16
        return ran


def set_tempo(s, bpm, tenths=0):
    t24 = 24 * int(bpm) + (23 * tenths + 4) // 9
    for a in (FW_TEMPO24, FW_TEMPO_SHADOW):
        s.uc.mem_write(a, t24.to_bytes(4, "big"))
    return t24


def install_trig_log(s):
    """Log every nonzero byte written to FW_LIVE_NIBBLE (a trig actually
    landing) and every nonzero write FW_TRIG_WORDS ever gets (Bryan's named
    array; empty in every ordinary-trig run so far -- see module docstring)."""
    uc = s.uc
    live = []
    words = []
    state = {"frame": 0}

    def on_live(u, acc, addr, size, val, d):
        val &= 0xFF
        if val:
            live.append((state["frame"], addr - FW_LIVE_NIBBLE, val))

    def on_word(u, acc, addr, size, val, d):
        val &= 0xFFFF
        if val:
            words.append((state["frame"], (addr - FW_TRIG_WORDS) // 2, val))

    uc.hook_add(eb.UC_HOOK_MEM_WRITE, on_live, begin=FW_LIVE_NIBBLE, end=FW_LIVE_NIBBLE + 7)
    uc.hook_add(eb.UC_HOOK_MEM_WRITE, on_word, begin=FW_TRIG_WORDS, end=FW_TRIG_WORDS + 15)
    uc.ctl_flush_tb()
    s.live_nibble_log = live
    s.trig_words_log = words
    s.frame_state = state
    return live


def start_transport(s):
    """Run the transport start case, then promote every track. Returns the
    disassembled block path taken (for diagnosing a cold-start divergence
    from the PLAY key's path -- see docs/EMU.md M5)."""
    tblocks = []
    h = s.uc.hook_add(eb.UC_HOOK_BLOCK,
                       lambda u, ad, sz, d: 0x4009b964 <= ad < 0x4009c600 and len(tblocks) < 300 and tblocks.append(ad))
    eb._call(s.uc, FW_TRANSPORT, [0])
    s.uc.hook_del(h)
    for t in range(8):
        eb._call(s.uc, FW_START_TRACK, [t])
    path = []
    for b in tblocks:
        if not path or path[-1] != b:
            path.append(b)
    return path


def poke_trig(s, step):
    """Set a trig on track 1 at `step` (1-8) directly in the loaded pattern
    record (head = track 1's 64-step trig mask, big-endian; byte 7 bit 0 =
    step 1). Useful for exercising the sequencer without re-saving a
    project from the unit each time."""
    blob = int.from_bytes(s.uc.mem_read(0x46c82456, 4), "big")
    v = s.uc.mem_read(blob + 7, 1)[0] | (1 << (step - 1))
    s.uc.mem_write(blob + 7, bytes([v]))
    return v


def _cli():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--set", default="OCTABAM")
    ap.add_argument("--name", default=None)
    ap.add_argument("--firmware", default=None)
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--bpm", type=float, default=None)
    ap.add_argument("--start", action="store_true", help="start the sequencer via the transport routine")
    ap.add_argument("--poke-trig", type=int, default=0, help="set a trig on track 1 at this step (1-8) in RAM after load")
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
        path = start_transport(s)
        print("transport path:", " ".join(hex(b) for b in path))
        print("transport  : state", int.from_bytes(s.uc.mem_read(FW_SEQ_STATE, 4), "big"),
              " phase inc 0x46107570:", int.from_bytes(s.uc.mem_read(0x46107570, 4), "big"),
              " track states 0x80006500:", bytes(s.uc.mem_read(0x80006500, 8)).hex())
    if a.poke_trig:
        v = poke_trig(s, a.poke_trig)
        print(f"poke trig  : track 1 step {a.poke_trig} -> mask byte 7 = {v:#04x}")

    live = install_trig_log(s)
    t24 = int.from_bytes(s.uc.mem_read(FW_TEMPO24, 4), "big")
    clock = Clock(s, t24)
    for f in range(a.frames):
        s.frame_state["frame"] = f
        try:
            run_frame(s)
            if a.start:
                clock.advance(s)
        except (eb.DetourTrap, eb.DetourStall) as e:
            print(f"frame {f}: {e}  pc={s.uc.reg_read(eb.UC_M68K_REG_PC):#x}")
            break
    print(f"frames run : {f + 1}  ticks: {clock.ticks}")
    print(f"FW_LIVE_NIBBLE (0x46104d15) writes ({len(live)}):")
    for fr, track, val in live:
        print(f"   frame {fr:5d} track {track} byte {val:#04x}  nibble {val & 0xF:x}  flags {val & 0xF0:#04x}")
    print(f"FW_TRIG_WORDS (0x46104d26) nonzero writes ({len(s.trig_words_log)}):", s.trig_words_log[:20])
    print("final FW_TRIG_WORDS bytes  :", bytes(s.uc.mem_read(FW_TRIG_WORDS, 16)).hex())
    print("final FW_LIVE_NIBBLE bytes :", bytes(s.uc.mem_read(FW_LIVE_NIBBLE, 8)).hex())


if __name__ == "__main__":
    _cli()
