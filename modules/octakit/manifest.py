"""OCTAKIT -- Em's Octakit: 256 Kits per Project in place of 64 bank-tied
Parts, built from her repository (emuyia/ems-octakit, submodule `upstream/`).

`upstream/runtime/firmware.json` is the recipe; the build compiles, links,
packs and appends her runtime itself (tools/remix/runtime_build.py),
re-deriving every identity the recipe pins and refusing on a mismatch.
Nothing of hers is vendored or rewritten; the stock routines her runtime carries
(459 distinct stock/NNNN.bin names in her sources; an earlier count was 411) are sliced out of the user's 1.40C at build time.

What it changes on the unit (her README): 64 Parts become 256 Kits
untethered from Banks (3.6 % of the flex pool); old Projects migrate their
Parts into the first 64 Kit slots on load, and downgrading may lose Kit
data; MKII PART = LOAD KIT, FUNC+PART = SAVE KIT (MKI FUNC+MIDI / FUNC+BANK);
FUNC+CUE reloads the assigned Kit; 7-character Kit names; copy/paste/clear/
undo in the LOAD/SAVE KIT menus; the splash animation is removed. This
module writes only the OS image; the migration is runtime behaviour.

Placement: her packed runtime is a payload of octabam's loader
(tools/remix/loader.S, derived from hers), staged at her own stage address
so her post-clear relocation finds it; her guarded sparse writes are kept;
her own append is replaced. Her runtime, Kit store and backup are the top
528 pages of the audio page arena, declared as an ArenaReserve so the build
stacks her pages with the platform's and computes the arena geometry once.

Measured: the runtime, packed runtime and append rebuild byte-identical to
her pinned identities with Homebrew m68k-elf-gcc 16.2.0 (recipe pins
16.1.0); tools/verify/verify_octakit.py reproduces her combined OS image from
stock + her writes + her append; under the ColdFire port her window reads
back byte-identical after boot. On hardware as OKMS1 (remix
ok-ms, her 92cf70b / ot-26914 + midisc 1.40MIDISC8), confirmed by midisc's
author -- and a Part Reload then trapped in her caller check
(modules/kits-reload; `pinned_returns` below is how the ledger sees that
class).
15 Sep 2026: pinned at her 7ba0ad6 (ot-26914-152100: an empty Kit slot's
payload is initialised through the stock part initialiser on load; 48 B
of runtime, one internal pointer literal, the stamp). abi.inc and the
reload routine unchanged, so the bridge and the pinned returns stand;
verify_octakit byte-exact, ok-ms green. 23 Sep 2026: c6d3f39, her README
only (four feature descriptions: UNDO KIT, FUNC+PASTE+PART, the
PTN+FUNC+RIGHT chain, PTN+FUNC+TRIG on inactive Patterns); no source
changed, the build is byte-identical.

Her recipe rewrites the apply_part entry 0x40009094 and the scene-parameter
writer 0x40052ae8; the ledger refuses any other module on those sites. CC
PAGE 2 shares her MIDI CC dispatch entry through the SCENES KITS bridge.
The page-1 writer 0x40054cd8 stays at its stock address but its dirty
store checks her token above the arguments: TEMPO BUS and MODE DEFAULTS
push it (P1TOKEN below; README "Calling the page-1 writer beside her").
"""

import pathlib
import re

from remix import arena
from remix.schema import Gate, Category, Proof, ArenaReserve, Kind, Module, Runtime

_ABI = pathlib.Path(__file__).parent / "upstream/runtime/abi.inc"


def _pinned_returns() -> tuple[int, ...]:
    """The stock return addresses her replacement routines compare the
    caller's against (`move.l (%sp),%d0; cmpi.l #GK_STOCK_..._RETURN`) and
    trap on any other -- read from her abi.inc, one `.equ` per site."""
    return tuple(sorted(int(m.group(1), 16) for m in
                        re.finditer(r"^\.equ\s+GK_STOCK_\w+_RETURN,(0x[0-9a-f]+)",
                                    _ABI.read_text(), re.M)))


# TEMPO BUS and MODE DEFAULTS call the stock page-1 writer with this token
# pushed above its arguments (P1TOKEN in their sources), which is what lets
# the call through her write marker. Read from her abi.inc so a change there
# stops the build instead of halting the unit.
P1TOKEN = 0x54500000
_armed = re.search(r"^\.equ\s+GK_TRACK_PARAMETER_TOKEN_ARMED,(0x[0-9a-f]+)", _ABI.read_text(), re.M)
if _armed is None or int(_armed.group(1), 16) != P1TOKEN:
    raise SystemExit(f"OCTAKIT: abi.inc's GK_TRACK_PARAMETER_TOKEN_ARMED is "
                     f"{_armed.group(1) if _armed else 'gone'}, not 0x{P1TOKEN:08x}: "
                     f"update P1TOKEN in modules/tempo-bus/helpers.s and modules/mode-defaults/modedef.s")


MODULE = Module(
    name="octakit",
    key="OCTAKIT",
    kind=Kind.CF_PATCH,
    category=Category.PARTS, author="emuyia/ems-octakit", author_url="https://github.com/emuyia/ems-octakit",
    proof=Proof.HARDWARE, proof_note="her build reproduced byte for byte; `ok-ms` on midisc's author's unit, 14 Sep 2026",
    doc="Em's Octakit: 256 Kits per Project instead of 64 Parts, built from "
        "her repo (submodule) as a loader-appended DRAM runtime.",
    runtime=Runtime(
        recipe="modules/octakit/upstream/runtime/firmware.json",
        sources="modules/octakit/upstream/runtime",
        report_note=" -- Em's Octakit (emuyia/ems-octakit), submodule "
                    "modules/octakit/upstream",
        pinned_returns=_pinned_returns(),
        patches=("modules/octakit/patches/0001-banks-load-error-applies-current-bank.patch",
                 "modules/octakit/patches/0002-part-refresh-busy-runs-stock.patch"),
        patched={
            "raw": {"size": 155062, "sha256": "6bcf51f7fbb60a333f6899cfea991fc5d56489483d4f9cb4f53a2da2cd1464bb"},
            "packed": {"size": 75784, "sha256": "e6660ea2aac228cf23d0c34b55751f40168a305683ee0654f71504018fb2489e"},
            "append": {"size": 75948, "sha256": "eb3e5d66a0e35abd797004bd474c7997a81e8ca12ff7b35701a661043b40c309"},
        },
    ),
    # Her runtime, Kit store and backup: the top 528 pages of the audio page
    # arena (0x45d0dde0..0x46025de0). Her four recipe writes shrink the arena
    # by exactly that; declared so the build stacks every reservation and
    # computes the geometry literals from the total (for her alone, her bytes).
    arena=ArenaReserve(pages=528, where="top",
                       recipe_writes=arena.OCTAKIT_RECIPE_WRITES),
    gates=(Gate('tools/verify/verify_octakit.py', remix_arg=False),),
)
