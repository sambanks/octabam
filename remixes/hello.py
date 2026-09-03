"""HELLO -- the reference minimal build: one gain insert, nothing else.

The smallest image the module system can produce: HELLO WORLD (a linear
volume knob) and nothing else at all. It used to carry SEND as well, for
the fallback alias -- 250 words for a bus client nothing in an insert-only
image reads. Unimplemented ids resolve to the firmware's own NONE instead
(schema.NO_FALLBACK), which costs one chooser row and no words. This remix
is the worked example `modules/_template` points at, and doubles as a
pipeline canary: if this stops building or stops nulling at GAIN=127, the
build system moved under everyone.
"""

from remix.schema import Remix

REMIX = Remix(
    name="hello",
    doc="Reference minimal build: the HELLO WORLD gain insert, alone.",
    modules=("HELLO WORLD",),
    fallback="NONE",
)
