"""LOFI AMF FIX -- the minimal build: the LO-FI AMF correctness fix, alone.

Two DSP-word pokes, no cave, no menu, no FX2 id -- the smallest image the
module system can produce with it. Unlike `midi-scenes`, this one has no
known address conflicts with anything else in the repo (it claims no free
ColdFire space at all), so it is expected to compose freely into bigger
remixes too -- this solo build is the reference/pipeline-canary shape,
matching `remixes/hello.py`.
"""

from remix.schema import Remix

REMIX = Remix(
    name="lofi-amf-fix",
    doc="Reference minimal build: the LO-FI AMF mpysu->mpyuu fix, alone.",
    modules=("LOFI AMF FIX",),
    fallback="NONE",
)
