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
  dispatches     the first N (sample, tcb) -- ORDER is the whole point of
                 running the scheduler; the sample times are compared with a
                 tolerance of one PIT period, since the instruction budget per
                 sample is a knob in both emulators.

                 ⚠️ The resumed PC is REPORTED, NOT COMPARED, and that is a
                 measurement rather than a concession. A task preempted by a
                 timer resumes wherever the interrupt happened to land, and
                 that address is a function of the `ips` knob -- which both
                 emulators document as a guess (RTOS_FORK section 6: "the
                 instruction budget per sample is a knob with a default, not a
                 truth"). Swept 8 Sep 2026 on the same image, same everything
                 else:

                     ips 3990  pc[1] 0x4001fab6  pc[2] 0x400209ac
                     ips 3995  pc[1] 0x4001faae  pc[2] 0x400209a8
                     ips 4100  pc[1] 0x4001faae  pc[2] 0x4009acf0
                     route A   pc[1] 0x4001fab6  pc[2] 0x400209a4

                 The PC moves with the knob; the task and the time do not. So
                 an equal PC here would be a coincidence of clock accounting,
                 and an unequal one is not evidence of anything. What a real
                 divergence looks like instead: a different TASK, a different
                 ORDER, or a time more than a period out -- all still fatal.
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
    problems, missing, notes = [], [], []

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
        # THE STRICT PART: the order in which each task FIRST runs, and when.
        # That is a real scheduling property -- priorities and creation order
        # decide it -- and ✅ it is clock-independent: measured identical at
        # ips 3990 and 4100, which change both the resumed PCs and the number
        # of timer preemptions (see the header).
        def firsts(ds):
            seen, order = set(), []
            for d in ds:
                if d["tcb"] not in seen:
                    seen.add(d["tcb"])
                    order.append((d["tcb"], d["sample"]))
            return order

        fa, fb = firsts(a["dispatches"]), firsts(v)
        if [t for t, _ in fa] != [t for t, _ in fb]:
            problems.append("the order tasks first run differs:\n"
                            f"    oracle {[hex(t) for t, _ in fa]}\n"
                            f"    port   {[hex(t) for t, _ in fb]}")
        else:
            for (t, sa), (_, sb) in zip(fa, fb):
                if abs(sa - sb) > PIT_PERIOD_SAMPLES:
                    problems.append(f"task {t:#x} first ran at sample {sa} (oracle) but {sb} (port) "
                                    f"-- more than one PIT period apart")

        # THE REPORTED PART: the full sequence, including how many times a
        # preempted task was re-entered. ⚠️ A timer preemption that lands a few
        # instructions either side of a task switch adds or removes a scheduler
        # visit, so this count is a function of the ips knob, not of the
        # firmware -- measured: at ips 3990 the port has one extra `sys` visit
        # between storage and keyrepeat, and at ips 4100 it has exactly the
        # oracle's sequence. Reported so a real reordering is still visible.
        if len(a["dispatches"]) != len(v):
            notes.append(f"{len(a['dispatches'])} dispatches in the oracle, {len(v)} in the port "
                         f"(timer preemptions between switches track the ips knob)")
        n = min(len(a["dispatches"]), len(v))
        for i in range(n):
            da, db = a["dispatches"][i], v[i]
            if da["tcb"] != db["tcb"]:
                notes.append(f"dispatches[{i}]: oracle {da['tcb']:#x}, port {db['tcb']:#x} -- the "
                             f"sequences diverge from here (first-run order is compared strictly above)")
                break
            if da["pc"] != db["pc"]:
                notes.append(f"dispatches[{i}]: same task at the same time, resumed at "
                             f"{da['pc']:#x} (oracle) vs {db['pc']:#x} (port)")

    for n in notes:
        print(f"NOTE     {n}")
    for m in missing:
        print(f"MISSING  {m} (the port does not produce it yet)")
    for p in problems:
        print(f"DIFFERS  {p}")
    checked = len(a) - len(missing)
    if problems:
        print(f"oracle: {len(problems)} disagreement(s) over {checked} field(s) -- a finding, go and measure")
        return 1
    print(f"oracle: {checked} field(s) agree" + (f", {len(missing)} not yet produced" if missing else "")
          + (f", {len(notes)} note(s)" if notes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
