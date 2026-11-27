"""VCA160 (modelled on the dbx 160) on FX1 and FX2 with an id of its own, and KEYBUS for its KEY, beside the stock effects but PLATE REV, whose words it runs in."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="vca160",
    family="effects",
    evidence=(Evidence(Level.EMULATOR, ref="verify_vca160",
        note="this remix, as test/db666 in the author's fork: make check on Sam's main bc14452, 29 Oct 2026 (cloud, "
             "no project, no .venv); not flashed. The module's unit runs are in its manifest"),),
    doc="VCA160 on FX1 and FX2 with its own id, and KEYBUS for its KEY, beside the stock effects but PLATE REV, whose words it runs in.",
    modules=(
        "VCA160", "KEYBUS",
        *stock.effects("PLATE REV"),
    ),
    fx1=("VCA160",
         *stock.FX1),
    fallback="NONE",
)
