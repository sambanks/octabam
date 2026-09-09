"""OCTAKIT -- Em's Octakit, alone: the reference minimal build.

One module, no menu rows, no DSP. Her runtime, her 650 writes and her
73 KB append each rebuild byte-identical to the identities her recipe
pins, and the build prints that. The COMBINED image is not identical to
hers even here, and the build says so too: octabam always writes its own
FX2 chooser (NONE row + terminator, row count, list refs, id aliases) and
the DSP null stubs, none of which her build has. The pure statement --
stock + her writes + her append == her `output.os`, with nothing of ours
in the way -- is `tools/verify/verify_octakit.py`, in `make verify`.
"""

from remix.schema import Remix

REMIX = Remix(
    name="octakit",
    doc="Em's Octakit alone -- must reproduce her own build byte for byte.",
    modules=("OCTAKIT",),
    fallback="NONE",
)
