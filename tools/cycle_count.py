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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from remix import registry  # noqa: E402
ASM = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"

# Budget per CORE, MEASURED on hardware with dsp/burn_probe's cycle meter,
# 7 Aug 2026. This replaces 1080, which was never a ceiling: it is the load
# stageprobe5 happened to SURVIVE, written down as a budget and then priced
# against by every design decision from the density pass onward. Retracted
# twice in the docs and still printed here until 8 Aug.
#
#   FILTER on all four core-0 tracks   froze at BURN=87 on the 16x probe -> 1392
#   FILTER disabled everywhere         froze at BURN=76 on the 32x probe -> 2432
# (⚠️ the arithmetic here read "32*76 = 1392" until 30 Aug 2026, which is
# neither row: it fused the two, used the filters-OFF freeze point, and got a
# product of 2432 while printing 1392. CHIP.md section 2 has both rows.)
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
# ⚠️ SUPERSEDED AS A HEADLINE, kept because the delta arithmetic below is
# anchored to it. The 23 Aug 2026 sweeps re-measured this properly and
# CHIP.md section 2 is the authority: spare 704 with the R46 reverb + 4x
# FILTER, 1088 with 2x, one FILTER = 192 (not the old ~260 inference), total
# DSP-usable budget ~3120, stock's own share ~1410. Those are what the
# WORST-CORE line below prices against; this constant only feeds the legacy
# 7 Aug comparison, which is labelled as such.
BURN_SPARE = 1392       # measured, worst realistic FX1 load, 7 Aug 2026
# 🟡 RECONSTRUCTED, not measured: the bank the 1392 was measured on top of.
# Pre-roll four-line reverb 763 (PLAN records the roll as 763 -> 778) + delay
# 163 + 2x send 19. Falsified by re-running the burn sweep, which is the only
# thing that can re-measure BURN_SPARE itself -- see PLAN, the probe currently
# does not build.
BANK_AT_MEASURE = 763 + 163 + 2 * 19
CORE_TOTAL = 4535       # 200 MIPS / 44100, arithmetic
# ✅ hardware, 23 Aug 2026 (CHIP.md section 2), triangulated from three sweeps.
USABLE = 3120           # what our code may actually spend, per core
STOCK_SHARE = CORE_TOTAL - USABLE      # ~1410, by subtraction
# ⚠️ THE PRICER IS KNOWN TO BE OFF, and by how much: CHIP.md measures the R46
# reverb's true cost at ~1650 against the 1384 counted here (~270 LOW), and
# the delay ~264 HIGH since the phead roll. The counts below are exact for the
# code as written and blind to memory contention; treat them as a floor and
# the hardware sweep as the authority.


def room_for_new_work(bank):
    """Headroom left after the bank grew past what BURN_SPARE was measured on."""
    return BURN_SPARE - (bank - BANK_AT_MEASURE)

# Module sources, keyed by filename stem, resolved from the manifests --
# so a module moving its own source cannot leave this pointing at nothing.
_ASM = registry.asm_by_stem()

# The LEGACY bank composition -- one reverb, one delay, two sends. This is
# the shape BANK_AT_MEASURE was measured with on 7 Aug 2026, so the headroom
# arithmetic below is only comparable to that measurement while the bank is
# counted the same way. It is NOT what a core actually runs (see bank_worst).
BANK = {"reverb_server": 1, "delay_server": 1, "send_client": 2}

FX2_SLOTS = 4           # per core: four tracks, one FX2 each
# AND FOUR FX1 SLOTS, on the same four tracks. Stock's own FX1 load is
# already inside STOCK_SHARE (the 7 Aug sweep measured the spare with four
# FILTERs running), so a module of ours listed on FX1 is charged ON TOP
# without crediting back the stock effect it displaces. That is the
# conservative direction, and the same one the FX2 slots are priced in.
FX1_SLOTS = 4


def bank_worst(rows, mods, fx1=()):
    """The worst per-core load the SELECTED remix can actually be asked for.

    Four FX2 slots on a core, and the modules that can occupy them are the
    remix's own. Two rules shape the answer:

      * AT MOST ONE SERVER per core. That is the standing design rule and
        what SPEC enforces by placing only one engine per payload -- so the
        legacy `reverb + delay + 2 sends` figure prices a core for two
        engines no core ever pays, which PLAN.md already flags as a
        single-core floor rather than a real configuration.
      * INSERTS ARE UNLIMITED. Nothing stops all four tracks selecting the
        same insert, so the worst case is four copies of the dearest one --
        the number that matters for a card of inserts, and the one no
        previous version of this tool could produce.

    AND FX1 IS A SECOND SET OF FOUR SLOTS on the same four tracks. A module
    the remix lists on FX1 (Remix.fx1) can be selected there as well, on top
    of whatever that track's FX2 slot is running -- which is why PLAN.md s2
    puts FX1's real ceiling at "cycles x4". The dearest FX1-listed module is
    charged four times, without crediting back the stock effect it displaces
    (stock's own FX1 load is inside STOCK_SHARE already).

    Returns (total, [(name, count), ...]).
    """
    cyc = {r["name"]: r["cycles"] for r in rows}
    servers = sorted((m for m in mods if m["server"] and m["stem"] in cyc),
                     key=lambda m: -cyc[m["stem"]])
    others = sorted((m for m in mods if not m["server"] and m["stem"] in cyc),
                    key=lambda m: -cyc[m["stem"]])
    picks = []
    if servers:
        picks.append(servers[0]["stem"])
    if others:
        picks += [others[0]["stem"]] * (FX2_SLOTS - len(picks))
    elif servers:
        # A remix of nothing but servers cannot fill the other slots with
        # anything of ours; those tracks run stock, which this tool does not
        # price. Say so rather than inventing a number for them.
        pass
    fx1_mods = [m for m in mods if m["key"] in fx1 and m["stem"] in cyc]
    if fx1_mods:
        picks += [max(fx1_mods, key=lambda m: cyc[m["stem"]])["stem"]] \
            * FX1_SLOTS
    counts = {}
    for n in picks:
        counts[n] = counts.get(n, 0) + 1
    return sum(cyc[n] * c for n, c in counts.items()), sorted(counts.items())

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
        src = _ASM["reverb_server"].read_text()
        for inc, anchor in BURN_INJECT:
            if src.count(anchor) != 1:
                sys.exit(f"burn_probe: anchor for {inc} appears "
                         f"{src.count(anchor)} times, expected 1 -- keep this "
                         f"in step with build_bus.py's BURN block")
            src = src.replace(anchor, anchor + (ROOT / inc).read_text(), 1)
        return src
    src = _ASM[name].read_text()
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
    """Cycles for one module's per-sample work.

    A module may carry SEVERAL `do n7` loops -- the insert modules dispatch
    their MODE before the loop and give each mode its own, which is cheaper
    than testing the mode per sample. Those loops are mutually exclusive by
    construction (the dispatch branches to exactly one), so the module's
    per-sample cost is the WORST of them, not their sum. That is the same
    reasoning MODEFORK applies to alternatives INSIDE one loop; this is the
    case where the fork sits outside it.

    ⚠️ Summing them instead would price every mode at once -- charging a
    five-mode module five engines and making it look unaffordable.
    """
    src = prep(name)
    lines = src.split("\n")

    hits = [i for i, l in enumerate(lines) if SAMPLE_LOOP.match(l)]
    if not hits:
        sys.exit(f"{name}: no `do n7,>...` sample loop found")
    if len(hits) > 1:
        alts = [_measure_loop(name, src, lines, i) for i in hits]
        worst = max(alts, key=lambda m: m["cycles"])
        others = "/".join(str(a["cycles"]) for a in alts)
        worst = dict(worst)
        worst["inner"] = ((worst["inner"] + ", ") if worst["inner"] else "") + \
            f"worst of {len(alts)} mode loops ({others})"
        return worst
    return _measure_loop(name, src, lines, hits[0])


def _measure_loop(name, src, lines, i):
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
    # A `bsr <label>` in the body is priced AS IF INLINED: the callee's word
    # span (label..rts, straight-line required) is charged at every call site,
    # plus a small constant for the call/return pair. Added 18 Aug 2026 when
    # satdrv rolled the two per-line sat+drive copies into one subroutine --
    # the roll is a WORD saving; the cycles are still paid per call, and this
    # keeps the tool honest about that instead of refusing the shape.
    BSR = re.compile(r"^\s*bsr\s+(\w+)", re.I)
    bsr_lines = {}
    for j in range(i + 1, end_line):
        m = BSR.match(lines[j])
        if m:
            lbl = m.group(1)
            # find the callee: label line .. its rts, all straight-line
            starts = [k for k, l in enumerate(lines) if l.strip() == lbl + ":"]
            if len(starts) != 1:
                sys.exit(f"{name}: bsr target {lbl} found {len(starts)} times")
            k0 = starts[0]
            k1 = next(k for k in range(k0, len(lines))
                      if re.match(r"^\s*rts\b", lines[k], re.I))
            inner_bad = [l for l in lines[k0 + 1:k1]
                         if CONTROL_FLOW.match(l)]
            if inner_bad:
                sys.exit(f"{name}: bsr callee {lbl} is not straight-line")
            bsr_lines[j] = (lbl, k0, k1)
    # ---- forward skips, opted into per module -----------------------------
    # A module may declare `; CYCLES_FORWARD_BRANCHES` in its header. Then a
    # CONDITIONAL branch whose target label sits LATER in the same loop body
    # is allowed, because such a branch can only SKIP code: the word span
    # already counts what it skips, so the figure stays a ceiling for that
    # path rather than becoming wrong. Nimbus needs this -- its per-grain
    # scatter latches and its freeze gate are all two-instruction skips.
    #
    # The FORWARD test is the whole safety of it and is enforced, not
    # trusted: a BACKWARD conditional branch is a loop, the span would count
    # its body once, and the count would understate by however many times it
    # went round. That is the shape this tool exists to refuse.
    fwd_ok = set()
    if "; CYCLES_FORWARD_BRANCHES" in src:
        COND = re.compile(r"^\s*b(?:cc|cs|eq|ne|ge|lt|gt|le|mi|pl)\s+(\w+)", re.I)
        for j in range(i + 1, end_line):
            m = COND.match(lines[j])
            if not m:
                continue
            tgt = m.group(1)
            at = next((k for k, l in enumerate(lines)
                       if l.strip().startswith(tgt + ":")), None)
            if at is not None and j < at <= end_line:
                fwd_ok.add(j)
    bad = [(j + 1, lines[j].strip()) for j in range(i + 1, end_line)
           if j not in shim_lines and j not in fork_lines and j not in bsr_lines
           and j not in fwd_ok
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
    bsr_marks = []
    for nidx, (j, (lbl, k0, k1)) in enumerate(sorted(bsr_lines.items())):
        mstart, mend = f"__cyc_bsr{nidx}", f"__cyc_bsre{nidx}"
        inserts.append((k0 + 1, f"{mstart}:"))   # after the label line
        inserts.append((k1 + 1, f"{mend}:"))     # after the rts
        bsr_marks.append((lbl, mstart, mend))
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
    rolls = []
    for lbl, mstart, mend in bsr_marks:
        if mstart not in syms or mend not in syms:
            sys.exit(f"{name}: assembler dropped a bsr marker for {lbl}")
        callee = syms[mend] - syms[mstart]        # body + rts, in words
        # the bsr word itself is already inside the body span; the callee
        # executes per call, plus a couple of cycles for the call/return pair
        cycles += callee + 4
        notes.append(f"bsr {lbl} {callee}w/call")
    for trips, inner_end, label in inner_at:
        if label not in syms or inner_end not in syms:
            sys.exit(f"{name}: assembler dropped the inner-loop label {label}")
        inner_words = syms[inner_end] - syms[label]
        # The span already counts the body ONCE, so add the other trips.
        surcharge = (trips - 1) * inner_words + DO_SETUP
        cycles += surcharge
        rolls.append((syms[label], surcharge))
        notes.append(f"{inner_words}w x{trips}")
    if fork_labels:
        if any(l not in syms for l in fork_labels.values()):
            sys.exit(f"{name}: assembler dropped a MODEFORK label")
        bounds = ([syms[l] for l in fork_mid_labels] + [syms[fork_labels["end"]]])
        disp_w = bounds[0] - syms[fork_labels["begin"]]
        alt_w = [bounds[k + 1] - bounds[k] for k in range(len(bounds) - 1)]
        # ⚠️ AN ALTERNATIVE'S COST IS ITS WORDS PLUS ITS OWN ROLLS, not its
        # words alone. Comparing alternatives by WORDS was right only while
        # every one of them was straight-line: GRAIN (v2 stage 5) is rolled,
        # so its 343 words run ~3x that in cycles, and a words-only max would
        # have picked PITCH as the worst path and then added GRAIN's roll
        # surcharge to it -- charging one engine's size with another's depth.
        # Attribute each roll to the alternative whose address range contains
        # it, then take the worst by CYCLES. Reduces exactly to the old
        # formula when no alternative is rolled.
        alt_sur = [sum(s for at, s in rolls if bounds[k] <= at < bounds[k + 1])
                   for k in range(len(alt_w))]
        alt_cyc = [w + s for w, s in zip(alt_w, alt_sur)]
        # The span priced EVERY alternative; at most one runs per sample.
        # Charge the dispatch (always) plus the worst alternative.
        cycles -= sum(alt_cyc) - max(alt_cyc)
        notes.append("fork worst-path (dispatch %dw, alts %s)"
                     % (disp_w, "/".join(f"{w}w" if not s else f"{w}w+{s}roll"
                                         for w, s in zip(alt_w, alt_sur))))
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

    # The modules to price come from the SELECTED REMIX, not a hard-coded
    # list -- a card of inserts and the shipping image are different loads,
    # and until 29 Aug this tool priced chongbong's engines whatever REMIX
    # said, which made every insert's cost an inspection guess.
    import os
    from remix.schema import BusRole
    remix = registry.remix(os.environ.get("REMIX") or registry.DEFAULT_REMIX)
    mods = [dict(stem=pathlib.Path(m.dsp.asm).stem, key=m.key,
                 server=(m.dsp.bus_role is BusRole.SERVER))
            for m in registry.selected(remix) if m.dsp is not None]
    rows = [measure(m["stem"]) for m in mods]

    if "--verify" in args:
        for m in rows:
            ok = verify(m["name"], m)
            print(f"  {m['name']}: marker is a no-op ... "
                  f"{'identical' if ok else 'DIFFERS'}")
            if not ok:
                sys.exit("marker changed codegen -- the count is not trustworthy")

    worst, picks = bank_worst(rows, mods, remix.fx1)
    # The legacy composition, and ONLY when the remix still carries the
    # modules it was measured with -- otherwise the comparison to the 7 Aug
    # hardware sweep is against a bank that shares nothing with it.
    legacy = ({m["name"]: m["cycles"] for m in rows}
              if all(k in {r["name"] for r in rows} for k in BANK) else None)
    bank = sum(legacy[k] * n for k, n in BANK.items()) if legacy else None
    room = room_for_new_work(bank) if bank is not None else None

    if "--json" in args:
        print(json.dumps(dict(remix=remix.name,
                              per_effect={m["name"]: m["cycles"] for m in rows},
                              worst_core=worst,
                              worst_core_mix=dict(picks),
                              # The same mix keyed by MODULE KEY rather than
                              # by asm stem, so a caller can print the name
                              # the operator reads on the panel: `reverb
                              # server` is a filename, `ChonVerb` is what the
                              # workbench calls it everywhere else.
                              worst_core_modules={
                                  next(m["key"] for m in mods
                                       if m["stem"] == stem): n
                                  for stem, n in picks},
                              bank=bank, headroom=room,
                              # What OUR code may spend, per core. The
                              # workbench's budget row is read against this
                              # rather than against core_total, and there
                              # must be one source for the figure.
                              usable=USABLE,
                              burn_spare_measured=BURN_SPARE,
                              bank_at_measure=BANK_AT_MEASURE,
                              core_total=CORE_TOTAL), indent=2))
        return

    w = max(max(len(m["name"]) for m in rows), 17)
    print(f"remix {remix.name!r}\n")
    print(f"{'':{w}}  cycles/sample")
    for m in rows:
        extra = f"   [{m['inner']}]" if m["inner"] else ""
        print(f"{m['name']:{w}}  {m['cycles']:>13}{extra}")
    stock_rows = [m.key for m in registry.selected(remix) if m.is_stock]
    if stock_rows:
        # A stock row runs stock code this tool does not count (it measures
        # our sources). FILTER is the one measured on hardware -- 192/instance,
        # docs/CHIP.md -- and, like an insert, a stock effect can be picked
        # on all four tracks of a core, so its cost is paid x4 at worst.
        print(f"{'stock rows':{w}}  {'NOT COUNTED':>13}   "
              f"[{', '.join(stock_rows)}] -- stock code; FILTER measured 192")
    print()
    mix = " + ".join(f"{n}x {k}" for k, n in picks) or "(nothing of ours)"
    print(f"{'WORST ONE CORE':{w}}  {worst:>13}   {mix}")
    print(f"{'':{w}}  {'':>13}   4 FX2 slots, at most one server (the design rule)")
    if remix.fx1:
        print(f"{'':{w}}  {'':>13}   + 4 FX1 slots: {', '.join(remix.fx1)} "
              f"listed on FX1 too")
    if worst > CORE_TOTAL:
        print(f"{'':{w}}  {'':>13}   *** OVER the arithmetic ceiling ***")
    # The measured spare is what was left ON TOP of a full bank plus four FX1
    # FILTERs, so it is headroom for NEW work, not a number the bank is scored
    # against. Printing "% used" against a fixed budget is exactly what made
    # 1080 dangerous -- it turned an unknown into a pass/fail.
    print(f"{'budget/core':{w}}  {CORE_TOTAL:>13}   (200 MIPS / 44.1 kHz)")
    print(f"{'usable by us':{w}}  {USABLE:>13}   measured 23 Aug 2026; stock takes "
          f"the other ~{STOCK_SHARE}")
    print(f"{'headroom':{w}}  {USABLE - worst:>13}   against the worst core above"
          + ("   *** OVER ***" if worst > USABLE else ""))
    print(f"{'':{w}}  {'':>13}   ⚠️ the counter reads ~270 LOW on the reverb "
          f"(CHIP.md s2); the wall is a CLIFF")
    if bank is None:
        print()
        print("  This remix carries none of the modules the 7 Aug hardware sweep")
        print("  was measured with, so the headroom arithmetic below does not")
        print(f"  apply to it. What can be said: the worst core costs {worst},")
        print(f"  against ~{CORE_TOTAL - 1410} usable after stock's own ~1410 -- and")
        print("  the wall is a CLIFF, not a slope. Only a burn sweep measures it.")
        return
    print(f"{'MEASURED spare':{w}}  {BURN_SPARE:>13}   on a {BANK_AT_MEASURE}-cycle bank "
          f"+ 4x FX1 FILTER (hardware, 7 Aug 2026)")
    print(f"{'legacy bank':{w}}  {bank:>13}   reverb + delay + 2 sends, the composition"
          f"\n{'':{w}}  {'':>13}   that measurement was made against (NOT a real core)")
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
