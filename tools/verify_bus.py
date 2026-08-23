#!/usr/bin/env python3
"""Bit-identity gate for the SHARED BUS scratch layout.

The same shape as tools/verify_roll.py (reverb engine) and tools/verify_delay.py
(delay engine), for the third thing that has no gate of its own: the bus itself
-- the parity word, the accumulator/wet buffers, the per-buffer send counts and
the three copies of the housekeeping block that must stay identical across
dsp/send_client.asm, dsp/reverb_server.asm and dsp/delay_server.asm.

WHY THIS EXISTS. The bus is the one piece of this project whose defining
property cannot be measured locally at all: dsp_host is single-core, so it is
always trivially in lockstep and can never show a cross-core race (CLAUDE.md's
"a measurement can be structurally blind" entry -- this is the instance that
cost months). What CAN be checked locally is the other half: that a change to
the bus layout does not alter what the bus DOES. A single core writes the
current buffer and reads the previous one whatever the rotation length is, so
going from two buffers to three is invisible here -- and that invisibility is
exactly what makes it a usable gate rather than a weak one.

So: this proves behaviour-preservation, and says nothing about the race. Both
halves of that sentence matter. Do not quote a green run here as evidence that
a timing fix works.

    make verify-bus SAVE=1     # on the tree you trust, BEFORE the edit
    ...make the bus change...
    make verify-bus            # must come back 19/19 bit-identical

⚠️ THIS IS AN ON-DEMAND GATE AROUND ONE EDIT, NOT A MEMBER OF `make check` --
and the reason is worth stating so nobody "fixes" it by adding it. The hashes
cover the WHOLE render: reverb engine, delay engine and bus together, because
the only way to see the bus is through a server that consumes it. So any
voicing change to either engine fails this gate for a reason that has nothing
to do with the bus. Stamp, edit, compare, and let the reference go stale --
exactly how verify_roll is used. The reference lives under out/ (gitignored)
for the same reason: it is scaffolding for one change, not a committed
baseline that some later engine edit would be pressured to match.

THE CONTROLS, without which a passing run means nothing (verify_roll's lesson:
a blind harness passes everything). --selftest perturbs the inputs in two ways
that MUST both fail:
  * a knob nudge -- proves the cases reach the engine at all
  * one extra SEND in the layout -- proves the cases reach the BUS, i.e. that
    the per-buffer counts and the auto-gain are actually in the signal path
A harness that passes its own selftest is not measuring the bus.

⚠️ A BLOCK IS 15 SAMPLES HERE, NOT 16. dsp_host caps a block at 15 frames
(send_probe.FRAMES) while the bus accumulators are 16 words wide for the
hardware's 16. A deliberate one-block latency change therefore shows up as a
15-sample shift, and expecting 16 cost a detour chasing an off-by-one in the
addressing that did not exist. The way that was settled is worth copying: point
the candidate's read at the SAME buffer generation as the reference, and the
whole restructure must come back bit-identical at lag 0 -- which separates
"the layout changed" from "the latency changed" completely.

⚠️ The nudged knob has to be one EVERY case carries, and the obvious choice is
wrong: the first version nudged the delay's FDBK, which left all seven
reverb-only cases matching because those layouts contain no delay at all. The
selftest reported it as seven blind cases, which is what it is for. The SEND
level is the only knob on every path here -- every case has a sender, by
construction, because the bus is what is being measured.
"""
import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import send_probe  # noqa: E402

REF = ROOT / "out/dsp/bus_reference.json"
REF_MEM = ROOT / "out/dsp/mem_ref_A.mem"      # only needed by --allow-lag
DEV_MEM = ROOT / "out/dsp/mem_dev_A.mem"

# dsp_host caps a block at 15 frames, so one block is 15 samples here even
# though the accumulator buffers are 16 words wide for the hardware's 16.
BLOCK = send_probe.FRAMES

# Each case pins one property of the bus. The layout string is dispatch order,
# slot 0 being position 0 -- the housekeeper -- so varying it varies WHO elects
# itself, which is the part with three copies that must stay identical.
#
# `dur`/`tail` are short on purpose: this gate compares bytes, so it needs
# enough blocks to exercise several parity rotations, not enough to voice
# anything. Every case runs both servers' cross-sends where the layout allows.
CASES = [
    # --- who housekeeps -----------------------------------------------------
    ("RS      reverb is position 0 (housekeeper), one sender",
     dict(layout="RS")),
    ("SR      SEND is position 0 -- the other copy of the housekeeping block",
     dict(layout="SR")),
    ("DS      delay is position 0 -- the third copy",
     dict(layout="DS", pick="D")),
    ("SD      SEND housekeeps, delay is a plain client",
     dict(layout="SD", pick="D")),
    (".RS     position 0 is NEITHER -- the self-healing election takes over",
     dict(layout=".RS")),
    ("..DS    election takeover with the delay as the server",
     dict(layout="..DS", pick="D")),

    # --- the per-buffer counts and the 1/N auto-gain ------------------------
    # Sender count is the thing indexed by parity alongside the accumulators,
    # so a layout change that breaks the count indexing shows up here and
    # nowhere else. Swept because 1/N is a table lookup, not a formula.
    ("SSR     two senders -- 1/N = 1/2 on the reverb bus",
     dict(layout="SSR")),
    ("SSSR    three senders",
     dict(layout="SSSR")),
    ("SSSSSSSR  seven senders -- the top of the reciprocal table",
     dict(layout="SSSSSSSR")),
    ("SSD     two senders into the delay bus",
     dict(layout="SSD", pick="D")),
    ("SSSSSSSD  seven senders into the delay bus",
     dict(layout="SSSSSSSD", pick="D")),

    # --- the cross-sends: the paths that write the OTHER bus ----------------
    # ->VERB (delay writes the REVERB accumulator) and ->DEL (reverb writes the
    # DELAY accumulator) are the two places a client of one bus is a writer on
    # the other, so they are the cases a half-applied layout change survives.
    ("RDS     both servers, reverb picked -- the delay's ->VERB write lands",
     dict(layout="RDS", pick="R", dvrbw=127)),
    ("RDS/D   both servers, delay picked -- the reverb's ->DEL write lands",
     dict(layout="RDS", pick="D", dvrbw=127)),
    ("DRS     both servers, dispatch order reversed",
     dict(layout="DRS", pick="D", dvrbw=127)),

    # --- split blocks: proc() runs twice, the bookkeeping actually executes --
    # split 0 never touches r7+$65/$66/$67, so a bug in the split-aware frame
    # offset is invisible without these. The offset is added to every bus
    # address, which is precisely what a layout change moves.
    ("RS s7   split block, reverb server",
     dict(layout="RS", split=7)),
    ("DS s7   split block, delay server",
     dict(layout="DS", pick="D", split=7)),
    ("RDS s5  split block with both servers and both cross-sends",
     dict(layout="RDS", pick="D", split=5, dvrbw=127)),

    # --- the hosts' own sends: paths every DEFAULT render leaves at zero ----
    # ⚠️ Added 18 Aug 2026 after the delay's IN decode was silently DELETED by
    # a splice (6d2690b) and 17/17 still passed -- every case had IN at 0, so
    # "IN multiplies garbage" rendered identically to "IN works". A knob whose
    # default is 0 is INVISIBLE to this gate unless a case drives it.
    ("DS IN   the delay host's own send, nonzero (inall)",
     dict(layout="DS", pick="D", dmix=64, inall=True)),
    ("RS IN   the reverb host's own send, nonzero (inall)",
     dict(layout="RS", mix=64, inall=True)),
]

# Knobs held away from their defaults so the paths under test are actually
# carrying signal -- a case rendered at FDBK 0 through a silent send proves
# nothing about the accumulator it never reads.
BASE = dict(dur=0.12, tail=0.25, amp=0.5, level=100, dlevel=100,
            mix=127, dtime=20, dfdbk=70, dmix=40)
# dmix 127 -> 40 (23 Aug 2026, with the delay's IN-keyed wet makeup): at 127
# the x3 makeup pinned every D-layout render at the rail, and a clipped
# fixture is a BLIND fixture -- rail-pinned samples compare equal no matter
# what the code did. 40 keeps IN exercised (the 18 Aug lesson above) with
# the makeup active and the peak well off the clamp.


def render(mem, case, bump_level=0, extra_send=""):
    kw = dict(BASE)
    kw.update(case)
    kw["level"] = kw["level"] + bump_level
    kw["dlevel"] = kw["dlevel"] + bump_level
    if extra_send:
        kw["layout"] = extra_send + kw["layout"]

    rev = list(send_probe.REV_PARAMS)
    rev[0] = 40                      # TIME
    rev[5] = kw["mix"] if "mix" in case else 0   # p5 = IN post-v4; BASE's old
                                                 # "mix" default must NOT leak
                                                 # a phantom host client into
                                                 # every case
    snd = list(send_probe.SEND_PARAMS)
    snd[1] = kw["level"]             # ->REVERB
    snd[0] = kw["dlevel"]            # ->DELAY
    dpar = list(send_probe.DELAY_PARAMS)
    # idx4 = IN, idx... ⚠️ dvrbw is p4 (-VRB) since the 18 Aug swap; dmix (IN)
    # is p5. The KEYS keep their historical names; the indices follow the map.
    for idx, key in ((0, "dtime"), (1, "dfdbk"), (5, "dmix"), (4, "dvrbw")):
        if key in kw:
            dpar[idx] = kw[key]

    L, R = send_probe.run(str(mem), kw["dur"], kw["tail"], rev, snd,
                          verbose=False, amp=kw["amp"], direct=False,
                          wave_src=None, split=kw.get("split", 0),
                          layout=kw["layout"], delay_params=dpar,
                          pick=kw.get("pick"), inall=kw.get("inall", False))
    h = hashlib.sha256()
    for v in L:
        h.update(v.to_bytes(4, "little", signed=True))
    for v in R:
        h.update(v.to_bytes(4, "little", signed=True))
    # The hash alone cannot distinguish "identical" from "both silent", which
    # is the failure mode a bus change produces most often. Carry the peak so a
    # dead render is a loud error rather than a green tick.
    peak = max((abs(v) for v in L + R), default=0)
    # Samples are kept only when a lag search may need them -- 17 cases of raw
    # audio is a lot to hold for a run that is going to compare hashes.
    return h.hexdigest(), peak, len(L), (L, R)


def lag_match(cur_lr, ref_lr, max_lag):
    """Smallest shift (0..max_lag) at which the candidate IS the reference.

    The candidate is shifted LATER, which is the only direction a buffer moving
    further back down the rotation can go."""
    for lag in range(max_lag + 1):
        if all(c[lag:lag + len(r) - lag] == r[:len(r) - lag]
               for c, r in zip(cur_lr, ref_lr)):
            return lag
    return None


def collect(mem, keep_samples=False, **kw):
    out = {}
    for name, case in CASES:
        digest, peak, n, lr = render(mem, case, **kw)
        out[name] = dict(sha=digest, peak=peak, n=n)
        if keep_samples:
            out[name]["lr"] = lr
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mem", default=str(DEV_MEM),
                    help="candidate dump (default: the DEV delay hatch)")
    ap.add_argument("--save", action="store_true",
                    help="stamp the candidate as the new reference")
    ap.add_argument("--selftest", action="store_true",
                    help="prove the harness can fail (see the module docstring)")
    ap.add_argument("--allow-lag", type=int, default=0, metavar="N",
                    help="accept a case that is bit-identical after shifting the\n"
                         "candidate LATER by up to N samples, and report the shift.\n"
                         "For deliberate LATENCY changes only -- moving the bus read\n"
                         "one buffer further back adds exactly one block, and this is\n"
                         "how you show that the added latency is the ONLY difference.\n"
                         "⚠️ A block here is 15 samples, not 16: dsp_host caps a block\n"
                         "at 15 frames (send_probe.FRAMES) while the accumulators are\n"
                         "16 words wide for the hardware's 16. Expecting 16 sent one\n"
                         "session chasing an off-by-one that did not exist.\n"
                         "⚠️ Engines with per-block state do NOT shift with the bus:\n"
                         "the reverb's LFOs advance once per block regardless, so its\n"
                         "cases legitimately fail this while the delay's pass. Prove\n"
                         "the restructure separately, at zero lag, by pointing the read\n"
                         "at the same buffer generation as the reference.")
    a = ap.parse_args()

    mem = pathlib.Path(a.mem)
    if not mem.exists():
        sys.exit(f"missing {mem} -- build the hatch first:\n"
                 f"  DEV=1 XBUS=1 python3 tools/build_bus.py")

    print(f"bus gate: {len(CASES)} cases against {mem.relative_to(ROOT)}")
    if a.allow_lag and not a.save:
        # A lag search needs the reference's SAMPLES, and the stamped file holds
        # only hashes -- so the reference build has to still be on disk. Rather
        # than guess where, require it explicitly: silently comparing against
        # the candidate would report lag 0 for everything.
        if not REF_MEM.exists():
            sys.exit(f"--allow-lag needs the reference dump's samples, not just\n"
                     f"its hashes. Put the build the reference was stamped from\n"
                     f"at {REF_MEM.relative_to(ROOT)} and rerun.")
    cur = collect(mem, keep_samples=bool(a.allow_lag))

    dead = [k for k, v in cur.items() if v["peak"] == 0]
    if dead:
        print("\n  DEAD RENDERS -- these cases produced digital silence, so a\n"
              "  matching hash would prove nothing:")
        for k in dead:
            print(f"    {k}")
        sys.exit(1)

    if a.save:
        REF.parent.mkdir(parents=True, exist_ok=True)
        REF.write_text(json.dumps(cur, indent=1, sort_keys=True))
        print(f"  wrote {REF.relative_to(ROOT)} ({len(cur)} cases)")
        for name, v in sorted(cur.items()):
            print(f"    {name:52s} peak {v['peak']:8d}  {v['sha'][:16]}")
        return 0

    if not REF.exists():
        sys.exit(f"no reference at {REF.relative_to(ROOT)} -- stamp one with --save\n"
                 f"(do that on a build you TRUST, not on the candidate)")
    ref = json.loads(REF.read_text())

    if a.selftest:
        print("\n  SELFTEST -- both perturbations MUST fail:")
        ok = True
        for label, kw in (("knob nudge (send level +1)", dict(bump_level=1)),
                          ("one extra SEND on the bus", dict(extra_send="S"))):
            per = collect(mem, **kw)
            same = [k for k in ref if k in per and per[k]["sha"] == ref[k]["sha"]]
            if same:
                print(f"    ✗ {label}: {len(same)} case(s) STILL MATCHED -- "
                      f"the harness is blind to them:")
                for k in same:
                    print(f"        {k}")
                ok = False
            else:
                print(f"    ✓ {label}: all {len(per)} cases changed")
        if not ok:
            print("\n  THE HARNESS IS NOT MEASURING WHAT IT CLAIMS TO. Fix it "
                  "before trusting a green run.")
            return 1
        print("  selftest passed: the harness can fail.")

    refsamp = {}
    if a.allow_lag:
        print(f"  reference samples from {REF_MEM.relative_to(ROOT)}")
        for k, v in collect(REF_MEM, keep_samples=True).items():
            refsamp[k] = v["lr"]

    print()
    bad, lagged = [], []
    for name, _ in CASES:
        c = cur[name]
        r = ref.get(name)
        if r is None:
            print(f"  NEW   {name:52s} (not in the reference)")
            continue
        if c["sha"] == r["sha"]:
            print(f"  ok    {name:52s} peak {c['peak']:8d}")
        elif a.allow_lag:
            lag = lag_match(c["lr"], refsamp[name], a.allow_lag)
            if lag is None:
                print(f"  FAIL  {name:52s} peak {c['peak']:8d} vs ref "
                      f"{r['peak']:8d}  (no lag <= {a.allow_lag} matches)")
                bad.append(name)
            else:
                print(f"  ok    {name:52s} peak {c['peak']:8d}  "
                      f"BIT-IDENTICAL at lag {lag} ({lag / BLOCK:g} block)")
                lagged.append((name, lag))
        else:
            print(f"  FAIL  {name:52s} peak {c['peak']:8d} vs ref {r['peak']:8d}")
            bad.append(name)

    missing = [k for k in ref if k not in cur]
    for k in missing:
        print(f"  GONE  {k:52s} (in the reference, not in this run)")

    if bad or missing:
        print(f"\n  {len(bad)} case(s) differ, {len(missing)} missing -- the "
              f"candidate is NOT bit-identical to the reference.")
        print("  Note what this does and does not mean: a FAIL here is a real\n"
              "  behaviour change. A PASS says nothing about cross-core timing,\n"
              "  which no local test can reach.")
        return 1

    if lagged:
        lags = sorted({l for _, l in lagged})
        print(f"\n  {len(lagged)} case(s) bit-identical only after a shift: "
              f"lag {lags} samples.")
        print("  That is a LATENCY change and nothing else -- every sample of "
              "those\n  renders is the reference's, just later.")
    print(f"\n  all {len(CASES)} cases bit-identical to the reference.")
    print("  ⚠️  This proves the bus still DOES the same thing. It does NOT\n"
          "     prove anything about the cross-core race -- dsp_host is\n"
          "     single-core and is always trivially in lockstep.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
