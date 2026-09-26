"""MIDI SCENES -- MIDI-driven scene locks, built from bkkbrls-del/midisc.

Stock 1.40C has no per-scene parameter lock over MIDI: XF morph reads one
live 8x30 lock table only the panel writes. midisc adds a second table
(MSC, `scene<<8 | track<<5 | flat`, 4096 bytes) and rewires scene hold,
XF morph, part save/reload and the scene clear/copy/paste rows to read it
when a MIDI event is driving. The panel path is untouched.

Source: `upstream/` is his repository (submodule, tracking 1.40MIDISC8.2).
His caves are written in his Python encoder; his `tools/gas_port.py`
regenerates `gas/*.s` from the same builders and proves each region
assembles to his bytes at his addresses (`tools/verify/verify_midiscenes.py`
re-runs that). Nothing in `upstream/` is edited here.

Placement: every unit is `dram=True`, linked into octabam's platform
runtime and depacked at boot into the arena reserve (docs/remixer/
PLACEMENT.md). Inside the OS this module changes only the detour and poke
sites below, plus the boot redirect when no other module supplies it.

Not carried: his MIDI CONTROL CC48/55/56 tick rows (UI-table pokes, not a
cave); CCs behave as stock. The apply_part entry (0x40009094) stays stock
since his 1.40MSCN6, so Octakit owns it alone. His own 1.40MIDISC8 image
fails project load under the port because his CAVE2 (0x400d2ee6) overruns
a live descriptor's enable words at 0x400d3014/18; this build links every
unit into DRAM and is immune (measured).

On hardware as OKMS1 (remix ok-ms), confirmed by him -- and Part Reload
trapped on it: Octakit's replacement of the stock reload validates its
caller's return address and his `reload` stub substitutes it
(subst_return below). Refused by the ledger without KITS RELOAD
(modules/kits-reload), which keeps the stock jsr and hooks the return
sites for rel_after.
"""

from remix.schema import Claims, Detour, Kind, Linked, Module, Poke

UP = "modules/midi-scenes/upstream/gas/"
H = bytes.fromhex

# Link order: a unit can only reference symbols of units before it.
UNITS = (
    Linked("msc", UP + "msc.s", dram=True),
    Linked("state", UP + "state.s", dram=True),
    Linked("seam", UP + "seam.s", dram=True),                 # part_window: no deps
    Linked("cave2", UP + "cave2.s", dram=True),               # rebuild, freeze_alt
    Linked("safe_cave", UP + "safe_cave.s", dram=True),       # pack/unpack/... call part_window, rebuild
    Linked("reload_cave", UP + "reload_cave.s", dram=True),   # rel_after: freeze_alt + pack/unpack
    Linked("code2", UP + "code2.s", dram=True),               # reload -> rel_after
    Linked("scene_paste", UP + "scene_paste.s", dram=True),
    Linked("seam_bank", UP + "seam_bank.s", dram=True),       # bank_sw/bank_inv call pack/unpack
    Linked("stub", UP + "stub.s", dram=True),
    Linked("project_cave", UP + "project_cave.s", dram=True),
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
    Detour(0x40062E3C, H("4eb940027578"), "scene_paste", "pst_sc", "PASTE SCENE menu row", kind="jsr"),
    Detour(0x4002E828, H("4eb94004a9d0"), "project_cave", "clr_pt", "FUNC+Part clear", kind="jsr"),
    Detour(0x40053A9E, H("4ab980000012660008aa"), "enc_unlock", "hook_a", "scene+encoder unlock, engine A", pad_to=10),
    Detour(0x40054392, H("4ab980000012660008b8"), "enc_unlock", "hook_b", "scene+encoder unlock, engine B", pad_to=10),
    Detour(0x4003F3A2, H("4ef94003577c"), "safe_cave", "morph", "XF morph tail (SAFE_CAVE since 1.40MSCN6)"),
    Detour(0x40061E78, H("71398000004a"), "stub", "xf1", "post-XF continuation 1"),
    Detour(0x40062C32, H("71b980000003"), "safe_cave", "xf2", "post-XF continuation 2"),
    Detour(0x40052AE0, H("4ef94007e8d8"), "code2", "scene_done", "scene-recall completion A"),
    Detour(0x40052A10, H("4ef94007e8d8"), "code2", "scene_done", "scene-recall completion B"),
    Detour(0x4005538A, H("1a82223c000018b2"), "code2", "write_mix", "part-window write, remixed", pad_to=8),
    Detour(0x4009D1DE, H("4cd73cfc4fef00284e75"), "safe_cave", "plock", "post-plock scene rebuild", pad_to=10),
    Detour(0x4002DD12, H("4eb94004a908"), "safe_cave", "save", "Part Save menu action", kind="jsr"),
    # `reload` and `apply_bridge` park the site's return address in apply_ret
    # and return the stock callee through their own continuation
    # (subst_return): Octakit's part reload validates that address and traps
    # on his -- the two reload sites need the KITS RELOAD bridge beside her.
    Detour(0x4002DD56, H("4eb94004aab4"), "code2", "reload", "Part Reload, menu path", kind="jsr", subst_return=True),
    Detour(0x4005E05A, H("4eb94004aab4"), "code2", "reload", "Part Reload, non-menu path", kind="jsr", subst_return=True),
    Detour(0x400622AA, H("23c046c82456"), "seam_bank", "bank_sw", "bank-pointer refresh on switch A", kind="jsr"),
    Detour(0x40087D44, H("23c046c82456"), "stub", "bank_pub", "bank publish (no pack) on switch B", kind="jsr"),
    Detour(0x4001FBD0, H("23c046c82456"), "seam_bank", "bank_inv", "bank-pointer refresh on init A", kind="jsr"),
    Detour(0x40025AA2, H("23c046c82456"), "seam_bank", "bank_inv", "bank-pointer refresh on init B", kind="jsr"),
    Detour(0x400622C6, H("4eb9400418e0"), "project_cave", "after_proj", "post-project-load CKPT seed + unpack", kind="jsr"),
    Detour(0x4002DCD4, H("45f94004a908"), "safe_cave", "save", "SAVE ALL's lea -> the ported Save", kind="lea"),
    # The part-change UI sites go through his apply bridge (pack, stock
    # apply, unpack + mix); STOCK_APPLY itself stays stock.
    Detour(0x4002B59A, H("4eb940009094"), "safe_cave", "apply_bridge", "part-change UI apply -> bridge, site 1", kind="jsr", subst_return=True),
    Detour(0x4002B8F8, H("4eb940009094"), "safe_cave", "apply_bridge", "part-change UI apply -> bridge, site 2", kind="jsr", subst_return=True),
    Detour(0x4004A8FC, H("4eb940009094"), "safe_cave", "apply_bridge", "set pattern's part then apply -> bridge, site 3", kind="jsr", subst_return=True),
    Detour(0x40029AF8, H("4ef940009094"), "safe_cave", "apply_bridge", "part-change UI apply (jmp) -> bridge",
           subst_return=True),
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
    # his MIDI-track lock store: the 144-byte freeze twin (0x90492) then the
    # 144-byte sparse blob (0x90522) inside every Part window (his memory_map)
    claims=Claims(part_window=((0x90492, 288, "MSC freeze twin + sparse blob"),)),
)
