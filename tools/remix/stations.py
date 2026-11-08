"""The SLOTS build setting of the stations (SPECTRUM, CHARACTER, MODULATION).

A station is FX1-only by default: at init it reads its allocator base and an
FX2 slot (base at or above 0x4000) sets a flag that makes `proc` return dry.
SLOTS = FX1+FX2 removes that flag in the build, so an FX2 instance runs live,
and lifts `Claims.fx1_only`, so the remix lists a real FX2 row. A remix with
a bus keeps the default: its cycle envelope is priced with the stations on
FX1 only.
"""

import dataclasses

from remix.schema import Apply, Option, Setting

SLOTS = ("FX1", "FX1+FX2")
# The one line each station's init carries (an exact substring of its source).
DRY_FLAG = "tpl     x0,b                    ; base >= 0x4000: an FX2 slot"
LIVE_FLAG = "nop                             ; SLOTS FX1+FX2: an FX2 slot runs live"


def setting():
    return Setting(1, "SLOTS", Option(*SLOTS), default="FX1", apply=Apply.BUILD,
                   doc="FX1 only (an FX2 instance is a dry pass), or live on FX1 and FX2")


def variant(module):
    """`module` is a callable returning the station's own MODULE."""
    def _variant(values):
        if values["SLOTS"] != "FX1+FX2":
            return {}
        m = module()
        # merged into the station's own subst (CHARACTER's keybus addresses), never in place of it
        own = m.dsp.subst or {}
        return {"dsp": dataclasses.replace(m.dsp, subst={p: {**own.get(p, {}), DRY_FLAG: LIVE_FLAG} for p in ("A", "B")}),
                "claims": dataclasses.replace(m.claims, fx1_only=False)}
    return _variant
