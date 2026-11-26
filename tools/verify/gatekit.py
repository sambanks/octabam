"""What every gate script writes for itself: its check lines and its symbol lookups.

A gate reports each check on a line of its own, and the runners read those
lines: acceptance.py and check_shards.py count a run as failed when a line
starts with `[FAIL]` (after spaces), and as missing evidence when one
starts with `[SKIP]`, whatever the exit code; a failure spelled any other
way (`FAIL x`) is invisible to them. Gate writes the forms they read
(docs/contributing/TESTING.md, "The verdict vocabulary"):

    GATE = gatekit.Gate()
    check, FAILS = GATE.check, GATE.fails   # the names the gates already use
    check("the kit file loads", ok, f"crc {crc:#x}")
    ...
    sys.exit(GATE.exit_code())

        [PASS] the kit file loads -- crc 0x1234abcd

runtime_symbol reads a symbol's address from the linked platform runtime's
map (out/platform/runtime/runtime.map, written by `make bus`).

Stdlib only.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNTIME_MAP = ROOT / "out/platform/runtime/runtime.map"


class Gate:
    """A gate's checks. `fails` lists the names of the checks that failed.
    `detail_on_pass=False` prints a check's detail only when it fails."""

    def __init__(self, detail_on_pass=True, out=print):
        self.fails = []
        self.checks = 0
        self.detail_on_pass = detail_on_pass
        self._out = out

    def _line(self, tag, name, detail=""):
        self._out(f"  [{tag}] {name}" + (f" -- {detail}" if detail else ""))

    def check(self, name, ok, detail=""):
        """One check: a [PASS] or [FAIL] line. Returns ok, as a bool."""
        ok = bool(ok)
        self.checks += 1
        self._line("PASS" if ok else "FAIL", name, detail if (detail and (self.detail_on_pass or not ok)) else "")
        if not ok:
            self.fails.append(name)
        return ok

    def skip(self, name, why):
        """Evidence this run could not gather: the runners report the gate as skipped."""
        self._line("SKIP", name, why)

    def na(self, name, why):
        """A branch that does not apply here (not missing evidence)."""
        self._line("N/A", name, why)

    def exit_code(self):
        return 1 if self.fails else 0


def runtime_symbol(name, who, path=RUNTIME_MAP, hint="", need=True):
    """`name`'s address in the linked runtime's map. A missing name ends the
    gate, `who: NAME not in the runtime map<hint>`; with need=False it is None."""
    for line in pathlib.Path(path).read_text().splitlines():
        w = line.split()
        if len(w) == 2 and w[1] == name and w[0].startswith("0x"):
            return int(w[0], 16)
    if need:
        raise SystemExit(f"{who}: {name} not in the runtime map{hint}")
    return None
