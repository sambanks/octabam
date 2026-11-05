"""BAR LED -- the tempo LED flashes green on the pattern's 1 while the
sequencer plays; every other flash stays stock red.

Stock routines changed: one call. The clock-message loop's beat flash,
`jsr set_led` at 0x40056f24 (set_led(38, 3): the tempo LED's red half),
goes through bl_flash, which turns LED id 38 into 39 (its green half) on
the first flash after the master step (0x800065b4) wraps, and on the first
flash after PLAY, then calls stock's set_led with the same arguments.
Stopped, nothing changes. unit.s has the ground; README.md what was
measured and what ran on a unit.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

MODULE = Module(
    name="bar-led",
    key="BAR LED",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES, author="nathangroth", author_url="https://github.com/nathangroth",
    proof=Proof.HARDWARE, proof_note="the author's MKI (author's report): a private octabam remix through "
        "REMIX SWITCH, 2 Nov 2026, and the same unit.s loaded over USB by Modwerk's loader, 4 Nov 2026; "
        "`verify_bar_led` under the port",
    doc="The tempo LED flashes green on the pattern's 1 while playing; the other beats stay red.",
    linked=(Linked("bar_led", "modules/bar-led/unit.s", dram=True),),
    detours=(
        # The displaced instruction: `jsr 0x40013784` (set_led), replayed as bl_flash's tail jump.
        Detour(0x40056F24, bytes.fromhex("4eb940013784"), "bar_led", "bl_flash",
               "tempo LED beat flash (set_led(38, 3)): id 39, green, on the pattern's 1 while playing",
               kind="jsr"),
    ),
    gates=(Gate("tools/verify/verify_bar_led.py", venv=True, stage="image"),),
)
