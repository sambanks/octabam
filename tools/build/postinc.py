"""Find instructions whose source operand post-increments or pre-decrements an address register that the
destination also reads: `move.b (%a0)+,(%a0,%d0.l)` (sambanks/octabam#1134).

GCC's RTL gives every other use of the register in the same instruction the value before the side effect,
and compiled a byte copy to this form with d0 = dst - src. The port's CPU (Unicorn, QEMU's m68k) computes
the destination with the register already incremented, so each byte landed one late (measured: two bytes
copied from 0x1000 to 0x2000 land at 0x2001..0x2002). Which order a unit follows is not measured here; the
form means two different things on the two readings, so no committed unit may contain it, whichever is
right. A C module avoids it by hiding one pointer from the optimiser: `__asm__("" : "+a"(src));`.

Both GAS syntaxes: Motorola `(%a0)+` / `-(%a0)` and MIT `%a0@+` / `%a0@-`."""
import re

_AREG = r"(?:a[0-7]|sp|fp)"
_LINE = re.compile(
    r"^\s*(?:[\w.$]+:\s*)?(?P<op>[a-z][a-z0-9.]*)\s+"
    rf"(?:\(%(?P<r1>{_AREG})\)\+|-\(%(?P<r2>{_AREG})\)|%(?P<r3>{_AREG})@[+-])"
    r",(?P<dst>[^|;\n]*)")


def ambiguous(text):
    """[(line number, line)] of every instruction in `text` whose destination reads the register its
    source steps."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        m = _LINE.match(line)
        if not m:
            continue
        reg = m.group("r1") or m.group("r2") or m.group("r3")
        if re.search(rf"%{reg}\b", m.group("dst")):
            out.append((n, line.strip()))
    return out
