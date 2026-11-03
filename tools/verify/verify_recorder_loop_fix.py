#!/usr/bin/env python3
"""verify_recorder_loop_fix -- the spacing cave's memo answers what the
hardware-ratified cave answers, call for call.

RECORDER LOOP FIX's spacing cave (hook 0x40006e0c, spacing_cave.s) runs about
1.4 times a recording track a frame. Since 2 Nov 2026 it keeps a memo per
track 0..7 of {L, tempo24, arm, L'} and answers from it when all three inputs
match the last call's. The cave as ratified on hardware before the memo is
SPACING_CAVE_BYTES_V1 in the manifest; the build already proves the source
assembles to SPACING_CAVE_BYTES (its Linked reference). This gate runs both
byte strings under unicorn (ColdFire V4e) through the same long sequence of
calls and refuses any difference:

  - d4 (the length the cave hands back) equal on every call;
  - every other data and address register, and the stack pointer, as the
    caller left them;
  - memo hits (the same inputs again), misses (a new bar's arm, a tempo
    change, a new RLEN, L one off so the +/-1 guard refuses), tempo 0,
    a length too short to have an RLEN, an exact (r = 0) tempo, and tracks
    8 and 9, which never touch the memo.

No stock bytes: the two caves read only 0x80001814 (tempo24), the arm table
at 0x46c7fa84 and the track on the caller's stack, which the gate supplies.
It also prints the instructions a call costs on a memo hit and a miss.
"""
import importlib.util
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
try:
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn import m68k_const as R
except ImportError:
    print("  [SKIP] verify_recorder_loop_fix: no unicorn (the .venv: make emu-setup)")
    sys.exit(0)

ROOT = pathlib.Path(__file__).resolve().parents[2]
V1_AT = 0x40300000              # each cave on its own RWX page, away from the OS image
MEMO_AT = 0x40310000
STOP = 0x40320000               # the return address: emulation stops here
STACK = 0x40330000              # a page for the stack; the entry sp sits mid-page
TEMPO24 = 0x80001814
ARMS = 0x46c7fa84
K = 15_876_000                  # samples per (RLEN step x tempo24): 44,100 x 60 x 24 / 4
DREGS = [getattr(R, f"UC_M68K_REG_D{i}") for i in range(8)]
AREGS = [getattr(R, f"UC_M68K_REG_A{i}") for i in range(7)]


def manifest():
    spec = importlib.util.spec_from_file_location("rlf_manifest", ROOT / "modules/recorder-loop-fix/manifest.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Machine:
    """One unicorn with both caves, the tempo word, the arm table and a stack."""

    def __init__(self, v1, memo):
        uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(R.UC_CPU_M68K_CFV4E)
        for base in (V1_AT, MEMO_AT, STOP, STACK, TEMPO24 & ~0xFFFF, ARMS & ~0xFFFF):
            uc.mem_map(base, 0x10000)
        uc.mem_write(V1_AT, v1)
        uc.mem_write(MEMO_AT, memo)
        uc.mem_write(STOP, b"\x4e\x71")              # nop; emulation ends before it runs
        self.uc = uc
        self.count = 0
        uc.hook_add(UC_HOOK_CODE, self._tick)

    def _tick(self, uc, addr, size, data):
        self.count += 1

    def call(self, at, product, tempo24, arms, track, regs):
        """The cave at `at` with d0 = product; -> (d4, the other registers, sp, instructions)."""
        uc = self.uc
        uc.mem_write(TEMPO24, tempo24.to_bytes(4, "big"))
        uc.mem_write(ARMS, b"".join(a.to_bytes(4, "big") for a in arms))
        sp = STACK + 0x8000
        uc.mem_write(sp, STOP.to_bytes(4, "big"))          # the return address
        uc.mem_write(sp + 140, track.to_bytes(4, "big"))   # the caller's 136(sp)
        for r, v in zip(DREGS + AREGS, regs):
            uc.reg_write(r, v)
        uc.reg_write(R.UC_M68K_REG_D0, product)
        uc.reg_write(R.UC_M68K_REG_A7, sp)
        self.count = 0
        uc.emu_start(at, STOP, count=10_000)
        if uc.reg_read(R.UC_M68K_REG_PC) != STOP:
            sys.exit(f"verify_recorder_loop_fix: the cave at {at:#x} did not return "
                     f"(pc {uc.reg_read(R.UC_M68K_REG_PC):#x})")
        out = [uc.reg_read(r) for r in DREGS + AREGS]
        return out[4], out[:4] + out[5:], uc.reg_read(R.UC_M68K_REG_A7), self.count


def bar(rlen, tempo24):
    """The recording's exact length in samples, as a fraction (num, den)."""
    return rlen * K, tempo24


def calls(rng, n):
    """A long run of plausible and edge-case calls: (product, tempo24, arms[10], track)."""
    arms = [0] * 10
    bars = [0] * 10
    tempo24 = 128 * 24
    rlens = [16] * 10
    for i in range(n):
        roll = rng.random()
        if roll < 0.01:
            tempo24 = 0                                    # no tempo: the cave keeps RLEN
        elif roll < 0.03:
            tempo24 = 120 * 24                             # r == 0 at RLEN 16: an integer period
        elif roll < 0.10:
            tempo24 = rng.randrange(30 * 24, 300 * 24 + 1)  # a tempo change
        track = rng.choice((0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 8, 9))
        if rng.random() < 0.05:
            rlens[track] = rng.choice((1, 2, 4, 8, 16, 32, 64, 128))
        if rng.random() < 0.15:                            # a new bar: the next arm
            bars[track] += 1
        if rng.random() < 0.02:
            bars[track] = rng.randrange(0, 200_000)        # far along a long session
        d = tempo24 or 128 * 24
        num, den = bar(rlens[track], d)
        arms[track] = ((bars[track] * num) // den) & 0xFFFFFFFF   # floor(k x the bar); the counter is 32 bits
        if rng.random() < 0.01:
            arms[track] = rng.getrandbits(32)              # anything at all
        length = (num + den // 2) // den                   # the length converter's L
        jitter = rng.choice((0, 0, 0, 0, 0, 0, 1, -1, 2, -2))
        if rng.random() < 0.01:
            length = rng.randrange(0, 40)                  # too short to recover an RLEN
        product = max(0, 2 * (length + jitter) - 1) & 0xFFFFFFFF
        repeat = rng.choice((1, 1, 2, 3, 6))               # the cave runs about 1.4 times a frame
        for _ in range(repeat):
            yield product, tempo24, list(arms), track


def main():
    m = manifest()
    v1, memo = m.SPACING_CAVE_BYTES_V1, m.SPACING_CAVE_BYTES
    mc = Machine(v1, memo)
    rng = random.Random(0x5bac1)
    n = hits = 0
    cost = {"hit": [], "miss": []}
    last = {}
    for product, tempo24, arms, track in calls(rng, 30_000):
        regs = [rng.getrandbits(32) for _ in range(15)]    # d0-d7, a0-a6: anything the caller left
        want, keep_v1, sp_v1, _ = mc.call(V1_AT, product, tempo24, arms, track, regs)
        got, keep_m, sp_m, ins = mc.call(MEMO_AT, product, tempo24, arms, track, regs)
        n += 1
        if got != want:
            sys.exit(f"  [FAIL] verify_recorder_loop_fix: call {n}: d4 {got:#x}, the ratified cave {want:#x} "
                     f"(product {product:#x}, tempo24 {tempo24}, track {track}, arm {arms[track]:#x})")
        expect = regs[:4] + regs[5:]
        expect[0] = product
        if keep_m != expect or sp_m != sp_v1 or keep_v1 != expect:
            sys.exit(f"  [FAIL] verify_recorder_loop_fix: call {n}: a register other than d4 changed "
                     f"(track {track}, tempo24 {tempo24})")
        key = (product, tempo24, arms[track] if track < 10 else None)
        if tempo24 and track < 8:
            kind = "hit" if last.get(track) == key else "miss"
            cost[kind].append(ins)
            hits += kind == "hit"
        last[track] = key
    print(f"  PASS  the memoised spacing cave matches the ratified one on {n} calls "
          f"({hits} memo hits; d4 and every other register)")
    for kind in ("hit", "miss"):
        c = cost[kind]
        if c:
            print(f"        a {kind}: {min(c)}..{max(c)} instructions, mean {sum(c) / len(c):.0f}")
    v1_ins = mc.call(V1_AT, 2 * 82_688 - 1, 128 * 24, [82_687 * 3] + [0] * 9, 0, [0] * 15)[3]
    print(f"        the ratified cave at 128 BPM, RLEN 16: {v1_ins} instructions a call")


if __name__ == "__main__":
    main()
