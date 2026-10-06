"""INPUT HOLD -- audio through the inputs keeps playing, at its level, while
a project loads.

Stock (measured under the port, 1.40C): every LOAD PROJECT runs the settings
reset 0x40025848 first. It makes the factory mixer live (GAIN 64, DIR 0,
MASTER_TRACK 0, PHONES_MIX 64, the input gates, INPUT_DELAY_COMPENSATION 0),
sets 120 BPM, and zeroes the current Part, so for the length of the load the
engine plays Part A; the empty-project init re-initialises the working
bank's Parts. Inputs are silent (DIR 0) until [SETTINGS] is read, and a
THRU or PICKUP that carried them stays gone until the bank file is read and
its Part applied (~75 % of the bar on a unit).

With INPUT HOLD the reset changes nothing audible: the output settings,
the tempo and the current Part stay as they are, the current Part is not
re-initialised, and the active pickup's input routing is resent, until the
new project's own values arrive -- its input levels included; they then
take over as stock. The first reset after a cold boot (empty battery
memory), where the live block is not yet valid, runs as stock.

Nine ColdFire sites, one ROM-cave unit (hold.s), no DSP code.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex
U = "modules/input-hold/hold.s"

MODULE = Module(
    name="input-hold",
    key="INPUT HOLD",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="dougdoesmusic", author_url="https://github.com/dougdoesmusic",
    proof=Proof.HARDWARE, proof_note="the author's MKII, 6 Oct 2026 (with the 14 stock effects): no dropout, no level dip, no FX jump on a project reload",
    gates=(Gate("tools/verify/verify_input_hold.py", venv=True, stage="image"),),
    doc="For audio on the inputs while you load a new project: it keeps playing through "
        "the load, at its level -- no dropout, no dip, no tempo jump.",
    linked=(
        Linked("hold", U, dram=False),
    ),
    detours=(
        Detour(0x4001FB78, H("4eb940025770"), "hold", "ih_boot_restore",
               "power-up restore of the saved state: the live block is valid, hold from now on",
               kind="jsr"),
        Detour(0x40025A80, H("45f940020898"), "hold", "ih_prep_defaults",
               "settings reset: the live output block replaces the defaults before they go live",
               kind="jsr"),
        Detour(0x4000D206, H("2239461054f8"), "hold", "ih_isr_pick",
               "frame ISR: the pickup's input monitoring words resent while a load holds"),
        Detour(0x4000D2A0, H("2079800000ec"), "hold", "ih_isr_keep",
               "frame ISR: keep the pickup words sent this frame"),
        Detour(0x400907E4, H("4eb940009094"), "hold", "ih_part_applied",
               "the load's current-bank Part apply: the pickup hold ends", kind="jsr"),
        Detour(0x4008534C, H("4eb9400909d8"), "hold", "ih_load_init",
               "LOAD PROJECT's empty-project init: the current Part is kept", kind="jsr"),
        Detour(0x400258CC, H("4eb94009c708"), "hold", "ih_tempo_reset",
               "settings reset: the 120 BPM default is not applied while holding", kind="jsr"),
        Detour(0x40025AAA, H("13c0100b14cf"), "hold", "ih_part_reset",
               "settings reset: the current Part is not zeroed while holding"),
        Detour(0x4000FCD4, H("48720800" "4e94"), "hold", "ih_part_init",
               "bank init, live Part block: skipped for the current Part while a load holds"),
    ),
)
