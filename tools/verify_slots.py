#!/usr/bin/env python3
"""
Static dead-store check for the r7 state block in dsp/reverb_server.asm.

WHY. Three shipped bugs share one family: a state slot meaning two things at
once. $83 (bit-23 garbage saturating the AGU -> the two-track freeze), $84+
(host-owned, hangs the unit), and on 8 Aug 2026 the $0c collision: the bus
housekeeper wrote the auto-gain 1/N into r7+$0c, the md_* block unconditionally
overwrote it with the lines-4-7 tap scale, and every per-sample auto-gain
multiply read ~0.75 instead of 1/N -- silently, for a day, blessed by every
green check. The signature of that whole class is mechanical:

    a WRITE whose value is unconditionally overwritten before any READ.

So that is what this checks. It is deliberately a dead-store check rather than
a slot-ownership ledger: a ledger blesses whatever baseline it was generated
from, while a dead store is wrong on its face.

HOW.
- Every `x:(r7+$xx)` access is classified read or write by its side of the
  comma (`move a,x:(r7+$xx)` writes; `move x:(r7+$xx),a` reads; the dual-read
  `mpy`/`mac` operand forms never address x:(r7+n) directly in this source).
- The scan is LINEAR with two structural refinements:
  * Mutually exclusive arms (the md_* MODE blocks: label group between
    `md_big:` and `md_done:`, each arm ending in `bra md_done`) are MERGED --
    a write inside one arm cannot kill a value for the path through another
    arm, but a slot written by EVERY arm still kills a pre-branch write, which
    is exactly the $0c shape and must still be caught. Merging the arms into
    one combined write-set at md_done: does both.
  * Liveness WRAPS: the r7 block persists across calls ($83 has proven it for
    seventy builds), so a write near the end of proc is read by next call's
    top. The scan runs the file twice and only trusts kills seen in the first
    pass that a first-pass-or-second-pass read did not interrupt.
- Slots accessed through COMPUTED pointers (the fbA/fbB walks derive r4/r5
  from `move r7,a / add`) can be read invisibly to this parser, so they are
  exempt from kill reports. The exemption list is explicit and each entry
  says why. Adding a slot here to silence a report is the wrong move unless a
  pointer walk really reaches it -- write the reason down.

A finding is fatal (exit 1): either fix the collision or, if the store is
genuinely dead, delete it -- both are wins.

Falsifiable: run against the pre-fix engine and it must FAIL on $0c:

    git show 5d73073~1:dsp/reverb_server.asm > /tmp/prefix.asm
    python3 tools/verify_slots.py /tmp/prefix.asm   # must report $0c
"""

import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "dsp/reverb_server.asm"

# Slots reachable through computed pointers, invisible to the direct-address
# parser. Each entry: why it is exempt.
POINTER_EXEMPT = {
    **{s: "u0..u3: read by the fbA loop through r4 (move r7,a / add #>$16)"
       for s in range(0x16, 0x1A)},
    **{s: "fb scratch 0..3: read by Step 2/3/4 partly via walked r5"
       for s in range(0x1A, 0x1E)},
    **{s: "u4..u7: read by the fbB loop through r4 (add #>$3a)"
       for s in range(0x3A, 0x3E)},
    **{s: "fb scratch 4..7: read by Step 4 via walked r5 (add #>$41)"
       for s in range(0x41, 0x45)},
}

WRITE_RE = re.compile(r"^\s*move\s+\S+,x:\(r7\+\$([0-9a-fA-F]{1,2})\)")
READ_RE = re.compile(r"^\s*(?:move|mpy|mac|add|sub)\s+x:\(r7\+\$([0-9a-fA-F]{1,2})\)")
ARM_START = re.compile(r"^md_\w+:")
ARM_END = re.compile(r"^md_done:")
LABEL = re.compile(r"^\w+:")
COND_BR = re.compile(r"^\s*b(?:ne|eq|lt|gt|le|ge|cs|cc|mi|pl|vs|vc|hi|ls)\s")


def parse(path):
    """-> list of (kind, slot, lineno, in_arms, conditional) in file order.

    `conditional` is True for a write sitting between a conditional branch
    and the next label -- the default-then-conditional-override pattern
    (e.g. $67's cold-boot default at the top of the bus housekeeper). Such a
    write executes on only one path, so it cannot KILL an earlier write. A
    label resets the flag: the md_* arm bodies start at their own labels and
    stay unconditional, which is what lets an every-arm store (the $0c shape)
    still register as a kill.
    """
    events = []
    in_arms = False
    conditional = False
    for n, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        code = line.split(";", 1)[0]
        if LABEL.match(code):
            conditional = False
        if ARM_START.match(code):
            in_arms = True
        if ARM_END.match(code):
            in_arms = False
        if COND_BR.match(code):
            conditional = True
        m = WRITE_RE.match(code)
        if m:
            events.append(("w", int(m.group(1), 16), n, in_arms, conditional))
            continue
        m = READ_RE.match(code)
        if m:
            events.append(("r", int(m.group(1), 16), n, in_arms, conditional))
    return events


def find_dead_stores(events):
    """Linear liveness with md-arm merging and a wrap-around second pass.

    pending[slot] = lineno of a write not yet read. A second write to the
    slot before any read reports the FIRST write as dead -- unless either
    write sits inside the md arms and the other does not... except that a
    pre-arm write killed by writes in the arms IS the $0c bug, so arm writes
    do kill pre-arm pending writes; but arm writes never kill EACH OTHER
    (only one arm runs). Wrap: pass 2 replays reads (and stops a slot's
    tracking at its first pass-2 write) so end-of-proc state stores survive.
    """
    dead = []
    pending = {}      # slot -> (lineno, was_in_arms)
    for kind, slot, n, in_arms, conditional in events:
        if kind == "r":
            pending.pop(slot, None)
        else:
            if conditional:
                # executes on one path only: cannot kill, and the earlier
                # write stays pending (if a later unconditional write kills
                # it, it was dead on EVERY path -- with or without this one)
                continue
            if slot in pending:
                p_line, p_arms = pending[slot]
                # two writes inside the arms are alternative paths, not a kill
                if not (p_arms and in_arms):
                    if slot not in POINTER_EXEMPT:
                        dead.append((slot, p_line, n))
            pending[slot] = (n, in_arms)
    # wrap-around: a read anywhere (top of next call) clears a pending write;
    # a pass-2 write means next call overwrites it -- but only AFTER that
    # call's intervening reads, already replayed by then, so stop tracking.
    for kind, slot, n, in_arms, conditional in events:
        if not pending:
            break
        if kind == "r":
            pending.pop(slot, None)
        else:
            pending.pop(slot, None)  # reached its own write again: cycle closed
    # anything STILL pending was written and never read on any path: dead too
    for slot, (n, _) in sorted(pending.items()):
        if slot not in POINTER_EXEMPT:
            dead.append((slot, n, None))
    return dead


def main():
    events = parse(SRC)
    if not events:
        print(f"  [FAIL] verify_slots: no r7 accesses parsed from {SRC} -- "
              "the regexes no longer match the source; fix the parser, do not skip it")
        return 1
    dead = find_dead_stores(events)
    if dead:
        for slot, w1, w2 in dead:
            if w2:
                print(f"  [FAIL] r7+${slot:02x}: write at line {w1} is overwritten "
                      f"at line {w2} with no read in between -- the $0c bug shape. "
                      "Fix the collision or delete the dead store.")
            else:
                print(f"  [FAIL] r7+${slot:02x}: write at line {w1} is never read "
                      "on any path (including next call's top).")
        return 1
    slots = sorted({e[1] for e in events})
    print(f"  [PASS] verify_slots: {len(events)} r7 accesses across "
          f"{len(slots)} slots, no dead stores ({SRC})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
