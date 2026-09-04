#!/usr/bin/env python3
"""The GRAIN cycle lever changes GRAIN and nothing else.

    python3 tools/verify_grains.py [remix]      (default: bamsep27)

`schema.Remix.grains = 2` rolls BusDelay's reader from four grains per line
to two, for the cycles: the delay's core cannot carry four active stations
beside a four-grain GRAIN. Three things have to hold.

 1. THE SUBSTITUTION IS THE ONE THE BUILD USES. Both the builder and the
    pricer import tools/remix/grains.py, and the markers are censused, so a
    reader that moved stops the build instead of quietly assembling four
    grains under a two-grain report.
 2. THE PRICER SEES IT. The rolled engine must price CHEAPER than the source
    -- the whole point of the lever is a number, and the first version of it
    was invisible to `make cycles`, which is the tool that measures the thing
    it exists for.
 3. IT TOUCHES GRAIN AND NOTHING ELSE, rendered through the real send path.
    `tools/verify_delay.py` renders both engines into the delay hatch and
    compares: every non-GRAIN case must be BIT-IDENTICAL, and the GRAIN cases
    must DIFFER. Both halves matter -- all-identical would mean the lever did
    nothing, and a difference in CLEAN would mean it did too much.

What this does NOT check is how two grains SOUND. That is an ear pass, and
the arithmetic that makes it checkable at all -- two triangle windows a half
period apart sum to exactly 1, so DC in comes back flat -- needs a DC feed
over the delay bus that this harness does not have yet.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
SRC = pathlib.Path("modules/busdelay/delay_server.asm")


def main():
    from remix import grains, registry
    name = sys.argv[1] if len(sys.argv) > 1 else "bamsep27"
    remix = registry.remix(name)
    if remix.grains == 4:
        print(f"  [ -- ] {name} runs four grains -- no lever to check")
        return 0
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}"
              f"{'  ' + detail if detail else ''}")
        fails += 0 if ok else 1

    src = SRC.read_text()
    bad = grains.census(src)
    check("the engine carries exactly the markers the lever substitutes",
          not bad, "; ".join(f"{m.strip()} {f}/{n}" for m, f, n in bad))
    if bad:
        print(f"\n{fails} check(s) failed")
        return 1
    rolled = grains.roll(src, remix.grains)
    check("rolling changes the source", rolled != src)
    check("the rolled loops count the declared grains",
          rolled.count(f"do      #{remix.grains},") >= 2,
          f"{rolled.count(f'do      #{remix.grains},')} rolled loops")

    # ---- the pricer -------------------------------------------------------
    def price(env):
        r = subprocess.run([sys.executable, "tools/cycle_count.py"],
                           capture_output=True, text=True,
                           env={**os.environ, **env})
        for line in r.stdout.splitlines():
            if line.startswith("delay_server"):
                return int(line.split()[1])
        return None

    four = price({"REMIX": "bus"})
    two = price({"REMIX": name})
    if four and two:
        check("the pricer sees the lever: the rolled engine is cheaper",
              two < four, f"{four} -> {two} cycles, saving {four - two}")

    # ---- rendered: GRAIN differs, everything else is bit-identical --------
    tmp = pathlib.Path("out/_grains")
    tmp.mkdir(parents=True, exist_ok=True)
    cand = tmp / "delay_rolled.asm"
    cand.write_text(rolled)
    # ⚠️ REMIX MUST NOT LEAK INTO THE DELAY GATE. verify_delay builds its own
    # DELAY HATCH -- every server real, no SPEC -- and a remix that HIDES the
    # delay compiles the host guard into both engines, so the hatch it built
    # under an inherited REMIX rendered a guarded engine at a non-host slot
    # and produced no comparable cases at all (0/0, under `make verify` only,
    # because standalone the variable was unset). Pin it to the plain remix.
    r = subprocess.run([sys.executable, "tools/verify_delay.py", str(cand)],
                       capture_output=True, text=True,
                       env={**os.environ, "REMIX": "bus"})
    lines = [l for l in r.stdout.splitlines() if "[PASS]" in l or "[FAIL]" in l]
    if not lines:
        check("verify_delay ran", False, (r.stdout + r.stderr).strip()[-200:])
    else:
        ident = [l for l in lines if "bit-identical:" in l]
        grain = [l for l in ident if "GRAIN" in l]
        other = [l for l in ident if "GRAIN" not in l]
        check("every NON-GRAIN case is bit-identical",
              other and all("[PASS]" in l for l in other),
              f"{sum('[PASS]' in l for l in other)}/{len(other)}")
        check("every GRAIN case DIFFERS -- the lever did something",
              grain and all("[FAIL]" in l for l in grain),
              f"{sum('[FAIL]' in l for l in grain)}/{len(grain)}")
        sens = [l for l in lines if "sensitive" in l or "mode is LIVE" in l]
        check("the comparison could have seen a difference anywhere",
              sens and all("[PASS]" in l for l in sens),
              f"{sum('[PASS]' in l for l in sens)}/{len(sens)} controls")

    print(f"\n{fails} check(s) failed" if fails else "\nOK")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
