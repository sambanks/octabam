"""_probe_collide -- deliberate collision, to watch the ledger refuse it."""
from remix.schema import Remix
REMIX = Remix(name="_probe_collide", doc="deliberate collision",
              modules=("REVERB SERVER", "NIMBUS", "SEND"), fallback="SEND")
