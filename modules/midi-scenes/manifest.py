"""MIDI SCENES -- MIDI-driven scene locks (bkkbrls-del/midisc), built from
source as linker-placed units.

Octatrack 1.40C has no per-scene parameter lock over MIDI: XF morph reads a
live 8x30 lock table that only the panel can write. midisc adds a second,
addressable table -- MSC, `scene<<8 | track<<5 | flat`, 4096 bytes -- and
rewires scene hold, XF morph, part save/reload and the scene
clear/copy/paste menu rows to read and write it when a MIDI event, not the
panel, is driving. The panel path is untouched. (Its author started from
this project's own reverse-engineering.)

WHERE THE CODE COMES FROM. `upstream/` is Sam's fork of his repository on
the branch `octabam-gas`, rebuilt 10 Sep 2026 on his 1.40MIDISC tree
(he rewrote the repo's history, so the branch is re-cut, not rebased) (a PR to him waits until he has finished his own
changes; then it rebases). His caves are written in a small Python encoder
(`tools/ot3_asm.py`); that branch adds `tools/gas_port.py`, which drives
his own build_* functions with an encoder subclass that also records one
GNU-as line per instruction, writes `gas/*.s`, and then assembles and
links every region at HIS address and compares -- all five regions
reproduce his bytes exactly (`tools/verify/verify_midiscenes.py` re-runs that
proof in `make verify`). Cross-cave references are linker symbols in the
`.s` form, so this build can place each region where there is room. His
build.py is untouched; the .s files are generated from it.

PLACEMENT: DRAM, all of it. Every unit is `dram=True`, so the build links
the seven together as octabam's platform runtime (tools/remix/
platform_build.py), packs it (~2 KB), appends it behind the loader and
depacks it at boot into the platform's reserve at the bottom of the audio
page arena (0x40a955e0, 10 MiB taken off the sample/recorder pool the
way Octakit and octamax take theirs; docs/remixer/PLACEMENT.md) -- MSC's
0xff fill included, so no boot-time initialisation is needed. The 8 KB of
OS zero runs the pinned snapshot filled to within 52 bytes are untouched
now; the only bytes this module changes inside the OS are the 35 detour
sites, the two pokes, and (when Octakit is not in the image) the boot
site's three-byte redirect into the loader.

THE DETOURS are his 38 sites -- 34 Detours and 4 Pokes, 236 bytes -- each
asserted against stock before it is rewritten, wired by SYMBOL: jmp for
the stubs that replay what they displaced and jump on, jsr for the
callable ones, one `lea` operand rewrite (SAVE_ALL), two `bne->bra` flips
(never re-apply the part after Part Save/Clear) and two `bne->nop` flips
(the MIDI lock LEDs scan MSC as well as the panel table).
TRACK_GATE/PAGE_GATE jump straight to stock code.

WHAT 1.40MIDISC CHANGED (10 Sep 2026, his commits since 1.40MSC): taddi/
paddi `rts` instead of jumping back, so the same cave serves two new
MIDI lock-LED paint sites (`jsr`, 0x40034764/0x40034950) beside the two
it already had; a scene-lock clamp routine in SAFE_CAVE (ARP page LEG/
MODE/SPD/RNGE get their own ranges, everything else 0-127); `xf1` moved
out of SAFE_CAVE into the stub; scene hold ENSURES MSC instead of
unpacking it every tick (his fix for locks vanishing between encoder
events); and bank switch/invalidate now preserve d1-d7/a0-a6 across the
sample load. octabam tracks all of it by regenerating `gas/*.s` from his
builders -- no transcription -- and re-proving the five regions.

MEASURED (10 Sep 2026, 1.40MIDISC): five regions byte-identical to his
encoder at his addresses; the linked units, 34 detours and 4 pokes
install with every assertion passing; `make check REMIX=midi-scenes` and
`REMIX=mods` green, the reserve reading back equal to the linked runtime
(8,622 B solo) under the port. NOT measured: nothing flashed from this
pipeline (his own builds are what has run on hardware). His `apply_part`
hook (0x40009094) is shared with Octakit; SCENES KITS bridges it, and
the ledger still refuses the pair without that module. None of the four
new 1.40MIDISC sites collides with anything Octakit writes.
"""

from remix.schema import Detour, Kind, Linked, Module, Poke

UP = "modules/midi-scenes/upstream/gas/"
H = bytes.fromhex

# ORDER IS LINK ORDER: a unit can only reference symbols of units before
# it (the build hands each link the globals of everything already placed).
# The two data units go first; then safe_cave, which everything calls;
# code2 last but one because it calls into safe_cave. msc floats into the
# room right after the chooser; state and code2 are pinned to the bytes
# after it (the 0x80 rounding a floating unit gets would waste the tail).
UNITS = (
    Linked("msc", UP + "msc.s", dram=True),
    Linked("state", UP + "state.s", dram=True),
    Linked("safe_cave", UP + "safe_cave.s", dram=True),
    Linked("cave2", UP + "cave2.s", dram=True),
    Linked("stub", UP + "stub.s", dram=True),
    Linked("code2", UP + "code2.s", dram=True),
    Linked("enc_unlock", UP + "enc_unlock.s", dram=True),
)

DETOURS = (
    Detour(0x400534CE, H("4ab98000001266000586"), "stub", "hold_a", "scene-hold dispatch, engine A", pad_to=10),
    Detour(0x40052ECE, H("4ab980000012660005b6"), "stub", "hold_b", "scene-hold dispatch, engine B", pad_to=10),
    Detour(0x4004E348, H("71b9100b14cc"), "stub", "dial", "scene-held dial readout"),
    Detour(0x400343BC, H("4ab980000012"), note="per-track ADDI dispatch -> stock", target=0x400343C4),
    Detour(0x4003445E, H("4ab980000012"), note="per-page ADDI dispatch -> stock", target=0x40034466),
    Detour(0x400343E8, H("06800008f3e2"), "stub", "taddi", "scene-locked track offset", kind="jsr"),
    Detour(0x4003448E, H("06810008f3e2"), "stub", "paddi", "scene-locked page offset", kind="jsr"),
    Detour(0x40034764, H("06800008f3e2"), "stub", "taddi", "MIDI lock-LED paint, engine A", kind="jsr"),
    Detour(0x40034950, H("06800008f3e2"), "stub", "taddi", "MIDI lock-LED paint, engine B", kind="jsr"),
    Detour(0x40031F44, H("4fefffe448d704fc"), "stub", "pad", "pad-has-locks indicator", pad_to=8),
    Detour(0x400434CA, H("4ebae414241f"), "stub", "press", "encoder-press refresh"),
    Detour(0x40054CB6, H("42b9460d1694"), "stub", "release", "scene-pad release mix"),
    Detour(0x40062F24, H("4eb940038c30"), "stub", "clr_sc", "CLEAR SCENE menu row", kind="jsr"),
    Detour(0x40062FBE, H("4eb9400274cc"), "stub", "cpy_sc", "COPY SCENE menu row", kind="jsr"),
    Detour(0x40062E3C, H("4eb940027578"), "stub", "pst_sc", "PASTE SCENE menu row", kind="jsr"),
    Detour(0x4002E828, H("4eb94004a9d0"), "safe_cave", "clr_pt", "FUNC+Part clear", kind="jsr"),
    Detour(0x40053A9E, H("4ab980000012660008aa"), "enc_unlock", "hook_a", "scene+encoder unlock, engine A", pad_to=10),
    Detour(0x40054392, H("4ab980000012660008b8"), "enc_unlock", "hook_b", "scene+encoder unlock, engine B", pad_to=10),
    Detour(0x4003F3A2, H("4ef94003577c"), "stub", "morph", "XF morph tail"),
    Detour(0x40061E78, H("71398000004a"), "stub", "xf1", "post-XF continuation 1"),
    Detour(0x40062C32, H("71b980000003"), "safe_cave", "xf2", "post-XF continuation 2"),
    Detour(0x40052AE0, H("4ef94007e8d8"), "code2", "scene_done", "scene-recall completion A"),
    Detour(0x40052A10, H("4ef94007e8d8"), "code2", "scene_done", "scene-recall completion B"),
    Detour(0x4005538A, H("1a82223c0000"), "code2", "write_mix", "part-window write, remixed"),
    Detour(0x4009D1DE, H("4cd73cfc4fef00284e75"), "safe_cave", "plock", "post-plock scene rebuild", pad_to=10),
    Detour(0x40009094, H("4fefff9848d77cfc"), "code2", "apply", "apply_part wrapper", pad_to=8),
    Detour(0x4002DD12, H("4eb94004a908"), "safe_cave", "save", "Part Save menu action", kind="jsr"),
    Detour(0x4002DD56, H("4eb94004aab4"), "code2", "reload", "Part Reload, menu path", kind="jsr"),
    Detour(0x4005E05A, H("4eb94004aab4"), "code2", "reload", "Part Reload, non-menu path", kind="jsr"),
    Detour(0x400622AA, H("23c046c82456"), "code2", "bank_sw", "bank-pointer refresh on switch A", kind="jsr"),
    Detour(0x40087D44, H("23c046c82456"), "code2", "bank_sw", "bank-pointer refresh on switch B", kind="jsr"),
    Detour(0x4001FBD0, H("23c046c82456"), "code2", "bank_inv", "bank-pointer refresh on init A", kind="jsr"),
    Detour(0x40025AA2, H("23c046c82456"), "code2", "bank_inv", "bank-pointer refresh on init B", kind="jsr"),
    Detour(0x4002DCD4, H("45f94004a908"), "safe_cave", "save", "SAVE ALL's lea -> the ported Save", kind="lea"),
)

POKES = (
    Poke(0x40034754, H("665a"), H("4e71"), "MIDI lock LEDs: scan MSC too, engine A (bne->nop)"),
    Poke(0x4003493E, H("6648"), H("4e71"), "MIDI lock LEDs: scan MSC too, engine B (bne->nop)"),
    Poke(0x4004A9B0, H("6612"), H("6012"), "never re-apply the part after Part Save (bne->bra)"),
    Poke(0x4004AA8E, H("6612"), H("6012"), "never re-apply the part after Part Clear (bne->bra)"),
)

MODULE = Module(
    name="midi-scenes",
    key="MIDI SCENES",
    kind=Kind.CF_PATCH,
    doc="MIDI-driven scene locks (hold/morph/save/reload/clear/copy/paste), "
        "built from bkkbrls-del/midisc as linker-placed units.",
    linked=UNITS,
    detours=DETOURS,
    pokes=POKES,
)
