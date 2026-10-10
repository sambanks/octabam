"""KITS -- 255 Kits per project; a Kit is a saved Part.

The stock Part engine runs as it is: four working Part slots per bank, the
pattern's Part byte names one. KITS keeps a library of 255 Parts and, per
pattern, the Kit it plays; before a pattern is scheduled its Kit is copied
into a slot of its bank that nothing is playing and the pattern's Part byte
names that slot. LOAD KIT and SAVE KIT run the stock Part Reload and Part
Save; FUNC+CUE is the stock reload. kits.work / kits.strd hold the library
beside the bank files. docs/firmware/PARTS.md says what of stock this reads.
"""

from remix.schema import Category, Claims, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex
PART_WINDOW = 0x8ed80


def kits_inc(modules):
    """MSCKIT: 1 with MIDI SCENES in the remix: a Kit record then carries the Part's
    lock table and kits.work is version 2. PWSKIP_LO / PWSKIP_HI: the Part bytes KITS leaves out when it asks
    whether a slot still holds its Kit -- MIDI SCENES' Claims.part_window,
    which his code rewrites in the current Part after a project load from
    its own table (measured under ok-ms, 6 Oct 2026). 0, 0 without him."""
    m = modules.get("MIDI SCENES")
    pw = m.claims.part_window if (m is not None and m.claims) else ()
    lo = min(o for o, _l, _w in pw) - PART_WINDOW if pw else 0
    hi = max(o + l for o, l, _w in pw) - PART_WINDOW if pw else 0
    msc = 1 if m is not None else 0
    return (f"        .set    PWSKIP_LO, {lo:#x}\n        .set    PWSKIP_HI, {hi:#x}\n"
            f"        .set    MSCKIT, {msc}\n")


MODULE = Module(
    name="kits",
    key="KITS",
    kind=Kind.CF_PATCH,
    category=Category.PARTS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="Sam's MKII (image A6, 6 Oct 2026): the Octakit import, ems-octakit #5, STOP/PTN+TRIG/PLAY with the Rytm, a rejected bank file, power cycles; `verify_kits` under the port",
    doc="255 Kits per project: PART = LOAD KIT, FUNC+PART = SAVE KIT (MKI: FUNC+MIDI, "
        "then FUNC+BANK); each pattern plays its Kit through the stock Part slots. After Em's Octakit.",
    linked=(Linked("kits", "modules/kits/kits.s", dram=True, include=kits_inc),),
    detours=(
        Detour(0x400A0570, H("4fefffec48d7007c"), "kits", "kits_sched",
               "the pattern schedule (every request): the pattern's Kit into a free slot",
               pad_to=8),
        Detour(0x4009C634, H("2f02242f0008"), "kits", "kits_chain",
               "the chain append: each chained pattern's Kit staged"),
        Detour(0x4002E7B8, H("4ab9460d1060"), "kits", "kits_partkey",
               "PART (MKII), FUNC+MIDI (MKI): LOAD KIT"),
        Detour(0x4002DC9C, H("71b9100b14cf"), "kits", "kits_savekey",
               "the Part edit menu (MKII FUNC+PART): SAVE KIT"),
        Detour(0x40058A64, H("2f032f02262f000c"), "kits", "kits_mkisave",
               "the MKI FUNC+BANK dispatch: SAVE KIT from LOAD KIT, else stock", pad_to=8),
        Detour(0x4004C146, H("41f9400a7230"), "kits", "kits_status",
               "the status line's Part field: NNN name of the Kit in the current slot"),
        Detour(0x4005E3D8, H("4feffff448d7001c"), "kits", "kits_funcyes",
               "FUNC+YES: with the SAVE KIT list open, quick save", pad_to=8),
        Detour(0x40060F34, H("2f032f02262f000c"), "kits", "kits_lcopy",
               "FUNC+REC: with a KITS list open, copy the Kit under the cursor", pad_to=8),
        Detour(0x40060DB0, H("2f032f02262f000c"), "kits", "kits_lpaste",
               "FUNC+STOP: with a KITS list open, paste onto it (again: undo)", pad_to=8),
        Detour(0x40060EB4, H("2f032f02262f000c"), "kits", "kits_lclear",
               "FUNC+PLAY: with a KITS list open, clear it (again: undo)", pad_to=8),
        Detour(0x40026EB0, H("202f0004223c00008ed8"), "kits", "kits_pcopy",
               "the pattern copy: the pattern's Kit goes with it", pad_to=10),
        Detour(0x40026EF0, H("202f000841ef0004"), "kits", "kits_psnap",
               "the paste's undo snapshot: the target's Kit kept", pad_to=8),
        Detour(0x4002B9B0, H("4feffff048d7041c"), "kits", "kits_pstore_ptn",
               "a pattern written from the clipboard or the undo buffer: its Kit", pad_to=8),
        Detour(0x40056B2C, H("2f0a2f02242f000c"), "kits", "kits_ptrig",
               "a pattern trig with PTN held: with FUNC held too, the target of PTN+FUNC+TRIG",
               pad_to=8),
        Detour(0x400503C4, H("222f0004202f0008"), "kits", "kits_fright",
               "FUNC+RIGHT with PTN held: the pattern and its Kit copied to the next empty ones",
               pad_to=8),
    ),
    requires=("STORE",),
    # CS1 (battery SRAM), unused by stock beyond its whole-CS1 init
    # (docs/firmware/STEP_LOCKS.md section 6): RESID with a magic and a sum,
    # and ASSIGN, over a power-off.
    claims=Claims(sram=((0x100F85A0, 0x48, "KITS: which Kit each Part slot holds"),
                        (0x100FFE00, 0x100, "KITS: each pattern's Kit"))),
    gates=(Gate('tools/verify/verify_kits.py', once=True),),
)
