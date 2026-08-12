#!/usr/bin/env python3
"""Static cycle count of each server's per-sample loop.

Why this exists: `tools/dsp_host` CANNOT measure this. Its instructions/sample
is g_lastCycles/procCalls/frames and g_lastCycles does not scale with the frame
count, so the figure it prints is a constant divided by whatever you asked for.
The count has to come from the code. It used to be done by hand, which is how
REVERB.md ended up quoting 529 and BUS.md quoting ~700 for the same bank.

Method. Each server's sample loop is `do n7,>END` -- n7 is the frame count, and
that is what distinguishes it from the init-time loops (`do y0,...`, `do #128,...`).
We inject a label immediately after that `do` (labels emit no words, so this
cannot change codegen -- --verify proves it), assemble, and take the word span
from there to END.

Words, not decoded instructions, is the cycle number here. On the 56300 a
one-word instruction is one cycle and a two-word instruction (a `#>` long
immediate, an absolute address) is two, so for straight-line code the word span
IS the cycle count. That holds only because these loop bodies contain no
branches and no nested `do`/`rep` -- both are checked below, and the count is
refused if either appears, because then this arithmetic would be wrong.

What it still does not model: memory-contention stalls (two accesses to the
same bank in one cycle), which inflate the real figure, and the `do` hardware
loop's own zero-overhead behaviour, which is already free. So treat the result
as a floor. It is exact for the code and optimistic about the bus.

Usage:  python3 tools/cycle_count.py [--verify] [--json]
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASM = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"

# Budget per CORE, MEASURED on hardware with dsp/burn_probe's cycle meter,
# 7 Aug 2026. This replaces 1080, which was never a ceiling: it is the load
# stageprobe5 happened to SURVIVE, written down as a budget and then priced
# against by every design decision from the density pass onward. Retracted
# twice in the docs and still printed here until 8 Aug.
#
#   FILTER on all four core-0 tracks   froze at 32*76 = 1392 spare
#   FILTER disabled everywhere         2032 and never broke (probe ran out)
#
# 1392 spare was measured with the FULL BANK plus the heaviest FX1 config
# already running, so the budget for OUR code is that spare plus what the bank
# already costs. That makes it a WORST CASE that needs no further derating --
# which is the opposite of how 1080 behaved.
#
# ⚠️ SPARE IS NOT INVARIANT TO THE BANK, and this tool used to print it as if
# it were. `budget = bank + BURN_SPARE` against the CURRENT bank made "room for
# new work" come out at 1392 no matter how much the bank grew -- which says
# capacity grows with our own code. The dependency was backwards, and the
# comment above it claimed the opposite ("tracks the bank rather than being a
# fixed number that goes stale").
#
# It went stale immediately: the eight-line tank took the reverb from 763 to
# 1145 cycles/sample (8 Aug 2026), ~382 more per bank, and the tool went on
# reporting 1392 of headroom. (Real headroom at that point was ~1010;
# the tool now subtracts bank growth itself -- its own output is the live
# number, 819 as of 11 Aug 2026.)
#
# What is actually fixed is the FREEZE POINT. The 7 Aug run measured
#   bank_then + 4x FX1 FILTER + 1392 = the load at which it froze
# so spare for new work today is BURN_SPARE minus however much the bank has
# grown since. Anything else prices FX1 against cycles we do not have -- and
# FX1 spends them x4 per core, so the error is multiplied by four.
BURN_SPARE = 1392       # measured, worst realistic FX1 load, 7 Aug 2026
# 🟡 RECONSTRUCTED, not measured: the bank the 1392 was measured on top of.
# Pre-roll four-line reverb 763 (PLAN records the roll as 763 -> 778) + delay
# 163 + 2x send 19. Falsified by re-running the burn sweep, which is the only
# thing that can re-measure BURN_SPARE itself -- see PLAN, the probe currently
# does not build.
BANK_AT_MEASURE = 763 + 163 + 2 * 19
CORE_TOTAL = 4535       # 200 MIPS / 44100, arithmetic


def room_for_new_work(bank):
    """Headroom left after the bank grew past what BURN_SPARE was measured on."""
    return BURN_SPARE - (bank - BANK_AT_MEASURE)

# A full bank's four FX2 slots: one reverb, one delay, two sends.
BANK = {"reverb_server": 1, "delay_server": 1, "send_client": 2}

# Kept in step with build_bus.py's BURN block -- same include files, same
# anchors. Duplicated rather than imported because build_bus.py runs a whole
# image build at import time.
BURN_INJECT = [
    ("dsp/burn_block1.inc",
     "        move    a,x:(r7+$14)            ; call flag: $010000 = the a=1 call\n"
     "                                        ; (the dispatcher's #$1 is left-\n"
     "                                        ; aligned), 0 = the split sub-call\n"),
    ("dsp/burn_block2.inc",
     "        move    a,x:(r7+$40)            ; LO coefficient\n"),
]

MARKER = "__cyc_body"
INNER_MARKER = "__cyc_inner"
SAMPLE_LOOP = re.compile(r"^\s*do\s+n7\s*,\s*>?(\w+)\s*(?:;.*)?$", re.I)
# A COUNTED inner loop: `do #4,>tankend`. The tank is rolled over its lines,
# so words != cycles for its body -- but the count is a literal, so the cycles
# are still exactly computable: the body simply runs N times. Anything else in
# CONTROL_FLOW below is still refused, because for a branch they would not be.
INNER_LOOP = re.compile(r"^\s*do\s+#>?\$?(\w+)\s*,\s*>?(\w+)\s*(?:;.*)?$", re.I)
# Anything that makes "one word == one cycle" false inside the body.
CONTROL_FLOW = re.compile(r"^\s*(j\w*|b(?:ra|sr|cc|cs|eq|ne|ge|lt|gt|le|mi|pl)\w*"
                          r"|do|rep|rti|rts)\b", re.I)

# A `do` is not free the way its ITERATIONS are. Entering one costs a few
# cycles to push LA/LC and set up, and the count below leaves that out -- the
# same class of omission as the memory-contention stalls the docstring already
# flags. Both push the real figure UP, so the result stays a floor.
DO_SETUP = 5


def prep(name):
    """Source text as the real build assembles it (build_bus.py)."""
    if name == "burn_probe":
        # There is no dsp/burn_probe.asm any more. It was a verbatim COPY of
        # reverb_server.asm plus two blocks, it silently went stale (forked
        # before v121, so it carried no bus auto-gain), and a cycle meter that
        # measures an engine we do not ship is worse than none. build_bus.py
        # now SPLICES the two blocks into the live source under BURN=1, so
        # "burn_probe" here means exactly that splice -- reproduced by the same
        # anchors, so this cannot drift from what the build actually assembles.
        src = (ROOT / "dsp" / "reverb_server.asm").read_text()
        for inc, anchor in BURN_INJECT:
            if src.count(anchor) != 1:
                sys.exit(f"burn_probe: anchor for {inc} appears "
                         f"{src.count(anchor)} times, expected 1 -- keep this "
                         f"in step with build_bus.py's BURN block")
            src = src.replace(anchor, anchor + (ROOT / inc).read_text(), 1)
        return src
    src = (ROOT / "dsp" / f"{name}.asm").read_text()
    if name == "delay_server":
        # build_bus.py rewrites this per payload; the value cannot change the
        # word count, but assert the shape it relies on so a drift is loud.
        if src.count("$30000") != 1:
            sys.exit(f"{name}: expected exactly one $30000 literal")
    return src


def assemble(src, tag):
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / "s.asm").write_text(src)
        r = subprocess.run([str(ASM), "-in", str(d / "s.asm"), "-org", "1000",
                            "-out", str(d / "s.bin"), "-sym", str(d / "s.sym")],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"{tag}: assembler failed\n{r.stderr}")
        syms = {}
        for line in (d / "s.sym").read_text().split("\n"):
            if line.strip():
                k, v = line.split()
                syms[k] = int(v, 16)
        return (d / "s.bin").read_bytes(), syms


def measure(name):
    src = prep(name)
    lines = src.split("\n")

    hits = [i for i, l in enumerate(lines) if SAMPLE_LOOP.match(l)]
    if len(hits) != 1:
        sys.exit(f"{name}: expected exactly one `do n7,>...` sample loop, "
                 f"found {len(hits)}")
    i = hits[0]
    end_label = SAMPLE_LOOP.match(lines[i]).group(1)

    # The body is everything between the `do` and its end label. Refuse to
    # report a number if it contains anything that breaks words==cycles.
    end_line = next((j for j, l in enumerate(lines)
                     if l.strip().startswith(end_label + ":")), None)
    if end_line is None:
        sys.exit(f"{name}: no `{end_label}:` label found")
    inner = [(j, INNER_LOOP.match(lines[j])) for j in range(i + 1, end_line)
             if INNER_LOOP.match(lines[j])]
    # Allow multiple counted inner loops — they are sequential (not nested),
    # so the total cycles are still exactly computable: the word span already
    # includes one copy of each body, and we add the remaining trips.
    if len(inner) > 1:
        print(f"  {name}: {len(inner)} counted inner loops — pricing each",
              file=sys.stderr)
    # Find SHIMMER_BEGIN/END boundaries. The shimmer contains short branch
    # sequences (bgt/blt/bra per head) where the path difference is 2 words —
    # negligible against ~2400 total. Skip those branches rather than refusing.
    shim_lines = set()
    for si, sl in enumerate(lines):
        if sl.strip().startswith("; SHIMMER_BEGIN"):
            for sj in range(si + 1, min(len(lines), si + 500)):
                if lines[sj].strip() == "; SHIMMER_END":
                    shim_lines.update(range(si, sj + 1))
                    break
    # MODEFORK_BEGIN/MID.../END: a mode dispatch. BEGIN..first MID is the
    # DISPATCH and always runs; each MID..next-MID-or-END is one MUTUALLY
    # EXCLUSIVE alternative, of which at most one runs per sample. Branches
    # inside are exempt like the shimmer's (short window ramps, +-2 words),
    # and the span is corrected below from "every alternative summed" to
    # "dispatch + the worst alternative", so the count stays a per-sample
    # ceiling for whichever mode is selected instead of pricing every engine
    # at once. N MIDs are allowed: BongDelay has CLEAN/PITCH/TAPE, and
    # pricing PITCH+TAPE together would overstate it by a whole engine.
    fork = {}
    mids = []
    for si, sl in enumerate(lines):
        if sl.strip().startswith("; MODEFORK_BEGIN"):
            fork["begin"] = si
        elif sl.strip().startswith("; MODEFORK_MID"):
            mids.append(si)
        elif sl.strip().startswith("; MODEFORK_END"):
            fork["end"] = si
    if mids:
        fork["mid"] = mids[0]
    if fork and set(fork) != {"begin", "mid", "end"}:
        sys.exit(f"{name}: incomplete MODEFORK markers ({sorted(fork)})")
    fork_lines = set(range(fork["begin"], fork["end"] + 1)) if fork else set()
    bad = [(j + 1, lines[j].strip()) for j in range(i + 1, end_line)
           if j not in shim_lines and j not in fork_lines
           and CONTROL_FLOW.match(lines[j]) and not INNER_LOOP.match(lines[j])]
    if bad:
        print(f"{name}: loop body is not straight-line -- words != cycles here.",
              file=sys.stderr)
        for ln, txt in bad:
            print(f"  {name}.asm:{ln}: {txt}", file=sys.stderr)
        sys.exit(1)

    # All label insertions (body marker, inner-loop markers, fork markers) go
    # through one list, applied in descending line order so no insertion
    # shifts another's position.
    inserts = [(i, f"{MARKER}:")]
    inner_at = []
    for j, m in inner:
        trips = int(m.group(1), 16 if lines[j].count("$") else 10)
        label = f"{INNER_MARKER}{len(inner_at)}"
        inserts.append((j, f"{label}:"))
        inner_at.append((trips, m.group(2), label))
    fork_labels = {}
    fork_mid_labels = []
    if fork:
        for key in ("begin", "end"):
            lbl = f"__cyc_fk{key}"
            inserts.append((fork[key], f"{lbl}:"))
            fork_labels[key] = lbl
        for n, si in enumerate(mids):
            lbl = f"__cyc_fkmid{n}"
            inserts.append((si, f"{lbl}:"))
            fork_labels[f"mid{n}"] = lbl
            fork_mid_labels.append(lbl)
    marked = list(lines)
    for j, txt in sorted(inserts, reverse=True):
        marked = marked[:j + 1] + [txt] + marked[j + 1:]

    blob, syms = assemble("\n".join(marked), name)
    if MARKER not in syms or end_label not in syms:
        sys.exit(f"{name}: assembler dropped a label")

    words = syms[end_label] - syms[MARKER]
    cycles, notes = words, []
    for trips, inner_end, label in inner_at:
        if label not in syms or inner_end not in syms:
            sys.exit(f"{name}: assembler dropped the inner-loop label {label}")
        inner_words = syms[inner_end] - syms[label]
        # The span already counts the body ONCE, so add the other trips.
        cycles += (trips - 1) * inner_words + DO_SETUP
        notes.append(f"{inner_words}w x{trips}")
    if fork_labels:
        if any(l not in syms for l in fork_labels.values()):
            sys.exit(f"{name}: assembler dropped a MODEFORK label")
        bounds = ([syms[l] for l in fork_mid_labels] + [syms[fork_labels["end"]]])
        disp_w = bounds[0] - syms[fork_labels["begin"]]
        alts = [bounds[k + 1] - bounds[k] for k in range(len(bounds) - 1)]
        # The span priced EVERY alternative; at most one runs per sample.
        # Charge the dispatch (always) plus the worst alternative.
        cycles -= sum(alts) - max(alts)
        notes.append("fork worst-path (dispatch %dw, alts %s)"
                     % (disp_w, "/".join(f"{w}w" for w in alts)))
    note = ", ".join(notes) if notes else ""
    return dict(name=name, words=words, cycles=cycles, inner=note,
                loop_end=end_label, total_words=len(blob) // 3, marked=marked)


def verify(name, m):
    """A label emits no words: assembling with and without it must be identical."""
    plain, _ = assemble(prep(name), name)
    withlbl, _ = assemble("\n".join(m["marked"]), name)
    return plain == withlbl


def main():
    if not ASM.exists():
        sys.exit(f"missing {ASM} -- run 'make setup'")
    args = sys.argv[1:]

    rows = [measure(n) for n in BANK]

    if "--verify" in args:
        for m in rows:
            ok = verify(m["name"], m)
            print(f"  {m['name']}: marker is a no-op ... "
                  f"{'identical' if ok else 'DIFFERS'}")
            if not ok:
                sys.exit("marker changed codegen -- the count is not trustworthy")

    bank = sum(m["cycles"] * BANK[m["name"]] for m in rows)

    room = room_for_new_work(bank)

    if "--json" in args:
        print(json.dumps(dict(per_effect={m["name"]: m["cycles"] for m in rows},
                              bank=bank, headroom=room,
                              burn_spare_measured=BURN_SPARE,
                              bank_at_measure=BANK_AT_MEASURE,
                              core_total=CORE_TOTAL), indent=2))
        return

    w = max(len(m["name"]) for m in rows)
    print(f"{'':{w}}  cycles/sample   in a bank")
    for m in rows:
        n = BANK[m["name"]]
        extra = f"   [rolled: {m['inner']}]" if m["inner"] else ""
        print(f"{m['name']:{w}}  {m['cycles']:>13}   x{n} = {m['cycles'] * n}{extra}")
    print(f"{'full bank':{w}}  {'':>13}   {bank}")
    # The measured spare is what was left ON TOP of a full bank plus four FX1
    # FILTERs, so it is headroom for NEW work, not a number the bank is scored
    # against. Printing "% used" against a fixed budget is exactly what made
    # 1080 dangerous -- it turned an unknown into a pass/fail.
    print(f"{'budget/core':{w}}  {CORE_TOTAL:>13}   (200 MIPS / 44.1 kHz)")
    print(f"{'MEASURED spare':{w}}  {BURN_SPARE:>13}   on a {BANK_AT_MEASURE}-cycle bank "
          f"+ 4x FX1 FILTER (hardware, 7 Aug 2026)")
    grown = bank - BANK_AT_MEASURE
    print(f"{'bank has grown by':{w}}  {grown:>13}   since that measurement")
    print(f"{'room for new work':{w}}  {room:>13}   cycles/sample"
          + (f"  ({room / max(bank, 1):.2f}x the current bank)" if room > 0 else
             "   *** THE BANK HAS EATEN THE MEASURED HEADROOM ***"))
    if grown > BURN_SPARE // 3:
        print()
        print(f"  NOTE: the bank has consumed {grown} of the {BURN_SPARE} measured spare.")
        print(f"  FX1 spends cycles x4 per core, so price new FX1 work against {room},")
        print(f"  not {BURN_SPARE}. Only a re-run of the burn sweep can re-measure this.")


if __name__ == "__main__":
    main()
