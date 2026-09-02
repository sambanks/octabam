"""HELLO -- the reference minimal build: one gain insert, nothing else.

The smallest image the module system can produce: HELLO WORLD (a linear
volume knob) plus SEND, which every insert remix carries because the
absent-server alias needs its entry points to exist. This remix is the
worked example `modules/_template` points at, and doubles as a pipeline
canary: if this stops building or stops nulling at GAIN=127, the build
system moved under everyone.
"""

from remix.schema import Remix

REMIX = Remix(
    name="hello",
    doc="Reference minimal build: HELLO WORLD gain insert + SEND.",
    modules=("HELLO WORLD", "SEND"),
    fallback="SEND",
)
