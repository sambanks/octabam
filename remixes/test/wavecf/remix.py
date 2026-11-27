"""WAVE (ColdFire) alone: the 4-voice wavetable machine with the stock effects."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="wavecf",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_wavecf_ui",
        note="built; the engine and note layer under Unicorn (modules/wavecf/test_wavecf.py); the machine's UI and"
             " sound under the port (verify_wavecf_ui.py, verify_wavecf_port.py); not flashed"),),
    doc="the WAVE machine (a 4-voice wavetable voice on the ColdFire) with the stock effects.",
    modules=("WAVE CF", *stock.EFFECTS),
    fallback="NONE",
)
