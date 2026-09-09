"""OCTAKIT -- Em's Octakit: 256 Kits per Project in place of 64 bank-tied
Parts, built from her repo (emuyia/ems-octakit) as a git submodule.

THE MODULE IS A POINTER, ON PURPOSE. `upstream/` is her repository at a
pinned commit; `runtime/firmware.json` there is the recipe and `runtime/`
the sources, and octabam's build compiles, links, packs and appends them
itself (`tools/remix/runtime_build.py`) -- re-deriving every identity her
recipe pins and refusing on any mismatch. She keeps developing in her own
repo and her README explicitly invites this ("use this repo as a submodule
to combine with other efforts"); an update here is a submodule bump plus
the identity checks passing. Nothing of hers is vendored or rewritten, and
nothing of Elektron's is stored: the 411 stock routines her runtime
carries are sliced out of YOUR 1.40C at build time.

WHAT IT CHANGES (her README, 9 Sep 2026 commit ca3b527): 64 Parts become
256 Kits untethered from Banks; old Projects migrate their Parts into the
first 64 Kit slots on load (downgrading to stock may lose Kit data); on
MKII PART opens LOAD KIT and FUNC+PART opens SAVE KIT (MKI: FUNC+MIDI /
FUNC+BANK); FUNC+CUE reloads the assigned Kit; Kits have 7-char names;
LOAD/SAVE KIT menus copy/paste/clear/undo; the OS version becomes a date
stamp and the splash animation is removed. The Parts->Kits migration is
RUNTIME behaviour on the unit -- this module writes only the OS image
(598 guarded sparse writes plus a 73,111-byte append), never a project
file. Back up projects before flashing; do not work on anything critical.

WHERE IT LIVES. Not in the free zero runs every other ColdFire mod fights
over: a 73 KB append at the end of the OS image (0x4010fdf0 -- early loader
+ stage + the packed runtime) that one boot-path write detours into; the
loader depacks the 149,653-byte runtime with the firmware's OWN aPLib
routine into the reserved recorder pages at 0x45d0dde0 and runs it from
DRAM. That is the design octabam adopted as its "appended runtime"
placement class (schema.Runtime) -- the only one with tens of KB to give.

MEASURED (9 Sep 2026): with Homebrew's m68k-elf-gcc 16.2.0 the runtime,
the packed runtime and the append all rebuild BYTE-IDENTICAL to the
identities her recipe pins for gcc 16.1.0 (sha256 dda11aca...), and
`tools/verify/verify_octakit.py` shows stock + her writes + her append == her
own combined OS (`output.os`). In an octabam IMAGE her runtime is a
PAYLOAD of octabam's loader (tools/remix/loader.S, derived from hers):
her append is replaced, her 650 writes kept, her packed runtime staged at
her own stage address so her post-clear relocation finds it. Booted under
the ColdFire port (`tools/verify/verify_dram_boot.py`): her wrapper calls our
loader, her gate and post-load entry run with her hash, the boot reaches
the handoff, and her window reads back byte-identical (149,653 B). The
image is never identical to hers -- the build adds its own FX2 chooser and
DSP null-stub edits, and now its own loader -- and the build says so.
`elektron-firmware-tool` packs the grown section without changes.
NOT measured: nothing from this pipeline has been flashed; her own
development builds are what has run on hardware (via junes.website).

COLLISIONS. Her recipe rewrites the apply_part entry 0x40009094, which
midi-scenes (STOCK_APPLY) and octamax (scene_stub) also detour, and the
scene-parameter writer 0x40052ae8 (octamax too). The ledger refuses those
combinations until detour chaining exists; nothing else of hers overlaps
anything. `lofi-amf-fix` composes with it freely (`remixes/octakit-fix.py`).
"""

from remix.schema import Kind, Module, Runtime

MODULE = Module(
    name="octakit",
    key="OCTAKIT",
    kind=Kind.CF_PATCH,
    doc="Em's Octakit: 256 Kits per Project instead of 64 Parts, built from "
        "her repo (submodule) as a loader-appended DRAM runtime.",
    runtime=Runtime(
        recipe="modules/octakit/upstream/runtime/firmware.json",
        sources="modules/octakit/upstream/runtime",
        report_note=" -- Em's Octakit (emuyia/ems-octakit), submodule "
                    "modules/octakit/upstream",
    ),
)
