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
  serial_a/_b    the BYTES each UART transmitted, compared over the length
                 both reached: one must be a prefix of the other. The total
                 is reported, never compared -- it tracks the ips knob
                 because the transmit ring drains in bursts (milestone O5)
  gate_ms        when the gate passed

And, from the M6c goldens (milestone O6 -- a different configuration, so a
SEPARATE pair of files, written by `emu_rtos.py --sequencer --golden` and
`ot_emu --sequencer --m6c-golden`):

    .venv/bin/python3 tools/emu_rtos.py --project out/_testproj --set OCTABAM --name RIG \
        --sequencer --internal-clock --poke-trig 2 --frames 400 --ms 20000 \
        --golden out/oracle/m6c.json
    ./out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card out/o6_card.img \
        --set OCTABAM --project RIG --sequencer --internal-clock --poke-trig 2 \
        --frames 400 --load-ms 20000 --m6c-golden out/oracle/port_m6c.json
    python3 tools/ot_emu/oracle.py out/oracle/m6c.json out/oracle/port_m6c.json

  m6c_trig       every write into the per-track live nibble (0x46104d15), as
                 (frames since the transport start, track, byte) -- the trig
                 itself. Compared STRICTLY: unlike the dispatch PCs and the
                 serial count, none of the M6c fields tracks the ips knob.
  m6c_trig_words the per-track trig words (0x46104d26); empty in every run so far
  m6c_ticks      sequencer ticks (vector 0x60) since the transport start
  m6c_frames     frames delivered since the transport start
  m6c_bank       [saved bank, final bank, sequencer bank, sequencer pattern]

A field the port has not produced yet is reported as MISSING, not as a
failure: the port's JSON grows milestone by milestone. A field the ORACLE
does not carry is skipped entirely -- the two goldens measure different
configurations and each carries only its own.
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
    compared = []

    def field(name):
        # ⚠️ A FIELD THE ORACLE DOES NOT CARRY IS NOT THIS RUN'S BUSINESS.
        # The M6a golden and the M6c golden are different configurations
        # measuring different things, and each carries only its own fields;
        # without this the M6c diff would report every M6a field as missing
        # from the port and take credit for none of what it did compare.
        if name not in a:
            return None
        if name not in b:
            missing.append(name)
            return None
        compared.append(name)
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

    if field("serial_a") is not None and field("serial_b") is not None:
        # THE SERIAL STREAM. What is compared is the BYTES over the length
        # both emulators reached -- one must be a prefix of the other -- and
        # NOT the total, which is a clock artefact.
        #
        # ⚠️ Measured 8 Sep 2026, and it is the reason this is written the
        # awkward way. The firmware drains its transmit ring in bursts, so
        # whether the last ~900-byte drain lands before or after the M6a gate
        # depends on the instruction budget per sample. Same image, same
        # everything else:
        #
        #     ips 3900  5731 B     ips 4100  4831 B
        #     ips 3990  5731 B     ips 4200  4831 B
        #     route A   4831 B     ips 4300  4831 B
        #
        # and at ips 4100 the port's 4831 bytes are byte-for-byte route A's,
        # while at 3990 route A's 4831 are an exact prefix of the port's 5731.
        # So an equal COUNT would be a coincidence of clock accounting, and an
        # unequal one is not evidence of anything -- but a byte that differs
        # inside the common prefix is a different code path, and fatal.
        import base64
        for name in ("serial_a", "serial_b"):
            oa = base64.b64decode(a[name])
            ob = base64.b64decode(b[name])
            n = min(len(oa), len(ob))
            if oa[:n] != ob[:n]:
                first = next(i for i in range(n) if oa[i] != ob[i])
                problems.append(f"{name}: the streams differ at byte {first} of {n} "
                                f"(oracle {oa[first]:#04x}, port {ob[first]:#04x})")
            elif len(oa) != len(ob):
                notes.append(f"{name}: {len(oa)} bytes in the oracle, {len(ob)} in the port, "
                             f"identical over the first {n} -- the ring drains in bursts and "
                             f"the last one tracks the ips knob")

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

    # -- M6c, the sequencer's fidelity (milestone O6) ------------------------
    # Every one of these is compared STRICTLY. Unlike the dispatch PCs and the
    # serial count, none of them tracks the instruction-budget knob: a trig
    # either fires on the frame the other emulator fires it on or it does not,
    # and the tick count is a property of the tempo and the frame period.
    if (v := field("m6c_trig")) is not None:
        ta = [tuple(x) for x in a["m6c_trig"]]
        tb = [tuple(x) for x in v]
        if ta != tb:
            problems.append("m6c_trig: the live-nibble log differs\n"
                            f"    oracle {[(f, t, hex(x)) for f, t, x in ta]}\n"
                            f"    port   {[(f, t, hex(x)) for f, t, x in tb]}")

    if (v := field("m6c_trig_words")) is not None:
        if [tuple(x) for x in a["m6c_trig_words"]] != [tuple(x) for x in v]:
            problems.append(f"m6c_trig_words: oracle {a['m6c_trig_words']}, port {v}")

    if (v := field("m6c_ticks")) is not None and v != a["m6c_ticks"]:
        problems.append(f"m6c_ticks: oracle {a['m6c_ticks']}, port {v}")

    if (v := field("m6c_frames")) is not None and v != a["m6c_frames"]:
        problems.append(f"m6c_frames: oracle {a['m6c_frames']} frames since the transport start, port {v}")

    if (v := field("m6c_bank")) is not None and list(v) != list(a["m6c_bank"]):
        problems.append(f"m6c_bank: [saved, final, seq bank, seq pattern] "
                        f"oracle {a['m6c_bank']}, port {list(v)}")

    # ⚠️ COUNT ONLY WHAT WAS ACTUALLY COMPARED. The summary used to say
    # "N field(s) agree" where N was every field in the golden, which quietly
    # took credit for `gate_ms`, `pit0_fired` and `serial_sent` -- none of
    # which this script has ever compared, because all three track the ips
    # knob. A gate that reports fields it did not check is the same defect as
    # a watch that prints nothing (RTOS_FORK section 10.3b). Fixed 8 Sep 2026.
    reported = [k for k in a if k not in compared and k not in missing]
    for n in notes:
        print(f"NOTE     {n}")
    for m in missing:
        print(f"MISSING  {m} (the port does not produce it yet)")
    for p in problems:
        print(f"DIFFERS  {p}")
    if reported:
        print("REPORTED " + ", ".join(sorted(reported)) + " -- present in both, NOT compared "
              "(these track the instruction-budget knob; see the header)")
    if problems:
        print(f"oracle: {len(problems)} disagreement(s) over {len(compared)} compared field(s) "
              f"-- a finding, go and measure")
        return 1
    print(f"oracle: {len(compared)} compared field(s) agree"
          + (f", {len(reported)} reported only" if reported else "")
          + (f", {len(missing)} not yet produced" if missing else "")
          + (f", {len(notes)} note(s)" if notes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
