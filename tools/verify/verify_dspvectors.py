#!/usr/bin/env python3
"""The DSP interrupt vectors OS SWITCH's park could live in are unarmed.

    python3 tools/verify/verify_dspvectors.py [remix]

OS SWITCH costs 40 DSP words in both payloads, out of the region modules
place their effects in. The words are there for the taking in the vector
table: stock leaves a contiguous run of slots as `jmp *` -- a self-jump
that would freeze the core for good if that interrupt ever fired, which is
how you know stock never enables them (payload A `P:$1E..$3F` = 34 words,
payload B `P:$14..$3F` = 44).

Putting code there is safe only while that stays true, and it stays true
only as long as nothing ARMS one of those interrupts. Today the freeze is
its own alarm: a fire kills the audio, which is why weeks of play are
already evidence that none of them fires. Once the park is resident in the
table the alarm goes away -- a fire would run park words mid-session
instead -- so the check has to move into the build.

This gate reads the user's own image and refuses if any vector in either
free run is armed, or if the runs are not where they are believed to be.
It is the audit AGENTS.md asks for in place of a hardware canary: a thing
that cannot be forgotten, rather than a session nobody repeats.

Three checks, and `--selftest` shows each of them failing on a doctored
listing -- a gate that cannot fail is worth nothing (AGENTS.md: ask what
the instrument cannot see):
  1. every slot in each run is a self-jump plus a zero word;
  2. no DMA channel whose vector is in a run has DIE set, and no ESAI
     control word has an interrupt enable set;
  3. the SET of peripheral registers either payload writes is exactly the
     recorded one. That is the check that catches a source this gate has
     never heard of: a new peripheral being configured at all fails it,
     and whoever adds it has to say which vector it can interrupt into.

WHAT IT CANNOT SEE: a control register written from a REGISTER rather than
an immediate (checks 2 reads decoded immediates; check 3 sees the write
whatever its source), a computed peripheral address, and anything a
ColdFire module arms through the host port. A core whose PC sits in a run
at the end of a port session would show it directly.
"""
import pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
ASM = ROOT / "out/dsp"

# The contiguous self-jump runs the park may live in, per payload: (first
# vector, last vector). Read from the user's image 29 Sep 2026; the gate
# re-derives and compares. The LOW run is the processor exceptions -- stack
# error, illegal, debug, trap, NMI and two reserved slots -- and OS SWITCH
# deliberately takes only $06 upward, leaving $02 (stack error) and $04
# (illegal instruction) as stock's freeze-traps: those two fire when
# something is already wrong, and a frozen core is easier to diagnose than
# one running park words.
RUNS = {"A": [(0x02, 0x0F), (0x1E, 0x3F)], "B": [(0x02, 0x0F), (0x14, 0x3F)]}

# Which vector each interrupt source lands on (DSP56300 / DSP5636x).
DMA_VECTOR = {0: 0x18, 1: 0x1A, 2: 0x1C, 3: 0x1E, 4: 0x20, 5: 0x22}
ESAI_VECTORS = (0x30, 0x32, 0x34, 0x36, 0x38, 0x3A, 0x3C, 0x3E)

# Every peripheral register either payload writes, read from the user's own
# image 29 Sep 2026. An addition is not a failure in itself -- it is a
# question: can the new peripheral interrupt, and into which vector?
PERIPHERALS = {
    "M_DCO0", "M_DCO1", "M_DCO2", "M_DCO3", "M_DCR0", "M_DCR1", "M_DCR2", "M_DCR3",
    "M_DDR0", "M_DDR1", "M_DDR2", "M_DDR3", "M_DOR2", "M_DOR3",
    "M_DSR0", "M_DSR1", "M_DSR2", "M_DSR3", "M_HCR", "M_HOTX", "M_PCRC", "M_PRRC",
    "M_RCCR", "M_RCCR_1", "M_RCR", "M_RCR_1", "M_RSMA", "M_RSMA_1", "M_RSMB", "M_RSMB_1",
    "M_SAICR", "M_SAICR_1", "M_TCCR", "M_TCCR_1", "M_TCR", "M_TCR_1",
    "M_TSMA", "M_TSMA_1", "M_TSMB", "M_TSMB_1", "M_TX0",
}

DIE = 22                       # DMA control register: the interrupt enable
# ESAI transmit/receive control: the disassembler prints every set bit by
# name, so an enable that is set shows up here by name.
ESAI_ENABLES = ("M_TIE", "M_TEIE", "M_TLIE", "M_TEDIE",
                "M_RIE", "M_REIE", "M_RLIE", "M_REDIE")

MOVEP = re.compile(r"movep\s+#>\$([0-9a-f]+),[xy]:<<(M_\w+)\s*;\s*\(bits: ([^)]*)\)")
ANY_WRITE = re.compile(r"movep\s+\S+,[xy]:<<(M_\w+)")


def listing(tag):
    p = ASM / f"payload_{tag}.asm"
    if not p.exists():
        subprocess.run([sys.executable, str(ROOT / "tools/build/dsp_disasm_all.py")],
                       check=True, capture_output=True, cwd=ROOT)
    return p.read_text()


def vectors(tag):
    """(vector -> the two words) for the table at P:0x00000."""
    blob = (ASM / f"{tag}_P00000.bin").read_bytes()
    w = [blob[i] | (blob[i + 1] << 8) | (blob[i + 2] << 16) for i in range(0, len(blob), 3)]
    return {v: (w[v], w[v + 1]) for v in range(0, 64, 2)}


def main():
    if "--selftest" in sys.argv:
        return selftest()
    fails, notes = [], []
    for tag, runs in RUNS.items():
      text = listing(tag)
      vec = vectors(tag)
      for lo, hi in runs:

          # 1. the run is a run: every slot a self-jump plus a zero word
          free = [v for v, (a, b) in vec.items() if a == 0x0C0000 | v and b == 0]
          run = [v for v in free if lo <= v <= hi]
          if len(run) * 2 != hi - lo + 1:
              fails.append(f"payload {tag}: P:${lo:02X}..${hi:02X} is not all self-jumps -- "
                           f"free slots there: {[hex(v) for v in run]}")
          used = sorted(v for v in vec if v not in free)
          notes.append(f"payload {tag}: free run P:${lo:02X}..${hi:02X} "
                       f"({hi - lo + 1} words), live vectors {[hex(v) for v in used]}")

          # 2. nothing arms an interrupt whose vector is in the run
          armed = []
          for imm, reg, bits in MOVEP.findall(text):
              val = int(imm, 16)
              m = re.fullmatch(r"M_DCR(\d)", reg)
              if m and val & (1 << DIE):
                  armed.append((DMA_VECTOR[int(m.group(1))], f"{reg} = ${val:06x} (DIE set)"))
              if reg.startswith(("M_TCR", "M_RCR")):
                  on = [e for e in ESAI_ENABLES if e in bits.split()]
                  if on:
                      for v in ESAI_VECTORS:
                          armed.append((v, f"{reg} = ${val:06x} ({', '.join(on)})"))
          # 3. no peripheral this audit has never seen is configured
          new = set(ANY_WRITE.findall(text)) - PERIPHERALS
          if new:
              fails.append(f"payload {tag}: peripheral(s) {sorted(new)} are configured and were "
                           f"not in the audit. Which vector can each interrupt into? If it is "
                           f"in P:${lo:02X}..${hi:02X}, the park cannot live there")
          for v, why in armed:
              if lo <= v <= hi:
                  fails.append(f"payload {tag}: vector P:${v:02X} IS ARMED -- {why}. The park "
                               f"cannot live in the run while that is so")
          if armed:
              notes.append(f"payload {tag}: armed vectors outside the run: "
                           f"{sorted({hex(v) for v, _ in armed})}")

    ok = not fails
    print(f"  [{'PASS' if ok else 'FAIL'}] verify_dspvectors: the free vector runs are "
          f"self-jumps and nothing arms an interrupt in them")
    for n in notes:
        print(f"         {n}")
    for f in fails:
        print(f"         {f}")
    return 0 if ok else 1


def selftest():
    """Each check, shown failing. A doctored copy of payload A's listing:
    DMA3's DIE set (its vector P:$1E is the first word of A's run), an ESAI
    transmit interrupt enabled (P:$30..$3E), and a peripheral nobody has
    audited. Each must be caught."""
    text = listing("A")
    cases = [
        ("a DMA whose vector is in the run has DIE set",
         text.replace("movep   #>$ac59c0,x:<<M_DCR3", "movep   #>$ec59c0,x:<<M_DCR3")),
        ("an ESAI transmit interrupt is enabled",
         text.replace("; (bits: M_PADC M_TFSR", "; (bits: M_TIE M_PADC M_TFSR")),
        ("a peripheral nobody has audited is configured",
         text + "\n000999: movep   #>$1,x:<<M_DAX_CTRL                ; (bits: $0) 000000 000001\n"),
    ]
    bad = []
    for why, doctored in cases:
        armed, new = [], set(ANY_WRITE.findall(doctored)) - PERIPHERALS
        for imm, reg, bits in MOVEP.findall(doctored):
            val = int(imm, 16)
            m = re.fullmatch(r"M_DCR(\d)", reg)
            if m and val & (1 << DIE):
                armed.append(DMA_VECTOR[int(m.group(1))])
            if reg.startswith(("M_TCR", "M_RCR")) and any(e in bits.split() for e in ESAI_ENABLES):
                armed += list(ESAI_VECTORS)
        caught = bool(new) or any(lo <= v <= hi for v in armed
                                  for lo, hi in RUNS["A"])
        print(f"  [{'ok  ' if caught else 'BLIND'}] {why}")
        if not caught:
            bad.append(why)
    print(f"  [{'PASS' if not bad else 'FAIL'}] verify_dspvectors --selftest: "
          f"{len(cases) - len(bad)}/{len(cases)} doctored listings caught")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
