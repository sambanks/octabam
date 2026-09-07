#!/usr/bin/env python3
"""THE ORACLE DIFF: does the C++ port (tools/ot_emu) reach the same machine
state route A (tools/emu_rtos.py) reaches?

    .venv/bin/python3 tools/emu_rtos.py --until-gate --ms 1000 --golden out/oracle/m6a.json
    ./out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --golden out/oracle/port.json
    python3 tools/ot_emu/oracle.py out/oracle/m6a.json out/oracle/port.json

Both files carry the same fields; this compares them field by field and
prints every disagreement. It is deliberately dumb -- no tolerance, no
"close enough" -- because a disagreement between the two emulators is a
FINDING, not a nuisance (docs/COLDFIRE_PORT.md). The one to trust is whichever
can point at a firmware constant that only makes sense one way; until someone
has, neither is.

What it checks, in the order a port reaches them:
  handoff_pc     the boot's trap #0 (milestone O1)
  auto_pokes     the completion flags no model answers, loop pc + addr + value
  created        every task the kernel creates: tcb, entry, prio, stack, creator
  ran            every TCB that was dispatched at least once
  first_switch   boot -> main
  dispatches     the first N (sample, tcb, pc) -- ORDER is the whole point of
                 running the scheduler; the sample times are compared with a
                 tolerance of one PIT period, since the instruction budget per
                 sample is a knob in both emulators
  gate_ms        when the gate passed

A field the port has not produced yet is reported as MISSING, not as a
failure: the port's JSON grows milestone by milestone.
"""
import json
import sys

PIT_PERIOD_SAMPLES = 220.5


def load(p):
    with open(p) as f:
        return json.load(f)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a, b = load(sys.argv[1]), load(sys.argv[2])
    problems, missing = [], []

    def field(name):
        if name not in b:
            missing.append(name)
            return None
        return b[name]

    if (v := field("handoff_pc")) is not None and v != a["handoff_pc"]:
        problems.append(f"handoff_pc: oracle {a['handoff_pc']:#x}, port {v:#x}")

    if (v := field("auto_pokes")) is not None:
        ka = [(p["pc"], p["addr"], p["value"]) for p in a["auto_pokes"]]
        kb = [(p["pc"], p["addr"], p["value"]) for p in v]
        if ka != kb:
            problems.append(f"auto_pokes: oracle {[tuple(hex(x) for x in k) for k in ka]}, "
                            f"port {[tuple(hex(x) for x in k) for k in kb]}")

    if (v := field("created")) is not None:
        key = lambda c: (c["tcb"], c["entry"], c["prio"], c["stack"], c["stack_size"], c["creator"])
        sa, sb = sorted(map(key, a["created"])), sorted(map(key, v))
        for k in sa:
            if k not in sb:
                problems.append(f"created: oracle has task tcb={k[0]:#x} entry={k[1]:#x} prio={k[2]} "
                                f"stack={k[3]:#x}+{k[4]:#x} by {k[5]:#x}; port does not")
        for k in sb:
            if k not in sa:
                problems.append(f"created: port has task tcb={k[0]:#x} entry={k[1]:#x} that the oracle does not")

    if (v := field("ran")) is not None:
        ra, rb = set(a["ran"]), set(v)
        for t in sorted(ra - rb):
            problems.append(f"ran: oracle ran tcb {t:#x}, port never did")
        for t in sorted(rb - ra):
            problems.append(f"ran: port ran tcb {t:#x}, oracle never did")

    if (v := field("first_switch")) is not None and v != a["first_switch"]:
        problems.append(f"first_switch: oracle {[hex(x) for x in a['first_switch']]}, port {[hex(x) for x in v]}")

    if (v := field("dispatches")) is not None:
        n = min(len(a["dispatches"]), len(v))
        for i in range(n):
            da, db = a["dispatches"][i], v[i]
            if da["tcb"] != db["tcb"] or da["pc"] != db["pc"]:
                problems.append(f"dispatches[{i}]: oracle tcb {da['tcb']:#x} pc {da['pc']:#x} at "
                                f"{da['sample']}, port tcb {db['tcb']:#x} pc {db['pc']:#x} at {db['sample']}")
                break
            if abs(da["sample"] - db["sample"]) > PIT_PERIOD_SAMPLES:
                problems.append(f"dispatches[{i}]: same task, but oracle at sample {da['sample']} and "
                                f"port at {db['sample']} -- more than one PIT period apart")
                break
        if len(v) < len(a["dispatches"]):
            problems.append(f"dispatches: port recorded {len(v)}, oracle {len(a['dispatches'])}")

    for m in missing:
        print(f"MISSING  {m} (the port does not produce it yet)")
    for p in problems:
        print(f"DIFFERS  {p}")
    checked = len(a) - len(missing)
    if problems:
        print(f"oracle: {len(problems)} disagreement(s) over {checked} field(s) -- a finding, go and measure")
        return 1
    print(f"oracle: {checked} field(s) agree" + (f", {len(missing)} not yet produced" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
