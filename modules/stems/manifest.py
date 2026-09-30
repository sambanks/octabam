"""STEM REC -- tracks to the card while the sequencer plays, streamed.

MAIN MENU > STEMS > REC arms a recording, or starts one if the
sequencer is running; selecting it again stops it, and so does the
sequencer stopping or 60 minutes. T1 to T8 turn tracks on and off (all
eight at boot; locked during a take). Each enabled track is a file,
<set>/AUDIO/YYMMDD-HHMM/T<n>.wav, 16-bit stereo. stems_peak keeps the
take's largest ring fill, for the menu's PEAK row. Design:
docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md; the menu,
docs/superpowers/specs/2026-09-28-stem-rec-menu-design.md.
Every stock fact the unit uses: docs/firmware/STEM_REC.md.

HOW, in one breath: a detour at the per-frame routine's only call site
(0x40004b12) packs each enabled track's post-FX2 read-back block into a
4 MiB ring each frame; an RTOS task of the module's own streams the ring
to the card while the take runs, through the file layer's raw sector
routines from its own buffers (never the buffered API or its shared
staging buffer), then rewrites each file's header and sets its length;
the ring and the task's stack are DramRegions at the free top of the
platform reserve, so the module costs no sample memory beyond what any
DRAM remix already gives up. The writer's sector buffers are a third
region, `stems_buf`: eight 33,280-byte stream buffers and eight 512-byte
sector-0 copies.

⚠️ UNFLASHED. No module upstream hooks the frame site or grows MAIN
MENU's root (29 Sep 2026); the ledger refuses one that does, by name.
"""

from remix.schema import Category, Detour, DramRegion, Gate, Kind, Linked, Module, Poke, Proof, TableGrow

# The per-frame routine's only call site, inside the audio interrupt at
# IPL 5: `jsr %pc@(0x400031a0)` then `move.w #0x2700,%sr` (cfprobe's site).
# The hook performs both, so a jsr + nop replaces them.
FRAME_SITE = 0x40004B12
FRAME_STOCK = bytes.fromhex("4ebae68c" "46fc2700")

# The stock PIO write routine (0x40014c48), right after its wait for DRQ:
# `movea.l 0x46c8c594,%a0`, the first sector's data. The stub streams the
# sector after advancing the handler's pointer and count, not before
# (docs/firmware/STEM_REC.md 11.7), and returns through stock's epilogue.
ATA_FIRST_SITE = 0x40014CFE
ATA_FIRST_STOCK = bytes.fromhex("207946c8c594")

# MAIN MENU's root (docs/firmware/MAINMENU.md sections 1-5): count at
# +0x00, row array pointer at +0x18. TableGrow copies the four stock
# categories from the user's image at build time and appends STEMS: a
# category row has a window (its icon) and a child (its list), no action,
# no getter, id 0. The STEMS list and its rows are in stems.s.
ROOT_DESC = 0x400CBD8C
ROOT_ROWS = 0x400CC698
ROOT_N, ROW_WORDS = 4, 6

MODULE = Module(
    name="stems",
    key="STEM REC",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES, author="yvesrosius", author_url="https://github.com/yvesrosius",
    proof=Proof.PORT, proof_note="`verify_stems` under the ColdFire port; never flashed",
    doc="MAIN MENU > STEMS: every track to the card while the sequencer plays "
        "(streamed: 16-bit, up to 60 min).",
    linked=(Linked("stems", "modules/stems/stems.s", dram=True),),
    detours=(Detour(FRAME_SITE, FRAME_STOCK, "stems", "stems_frame_hook",
                    "per-frame tap: the enabled tracks into the ring, then the stock routine",
                    kind="jsr", pad_to=8),
             Detour(ATA_FIRST_SITE, ATA_FIRST_STOCK, "stems", "stems_ata_first",
                    "the PIO write's first sector, pointer and count advanced first",
                    kind="jmp"),),
    tables=(TableGrow("MAIN MENU root + STEMS", old=ROOT_ROWS,
                      count=ROOT_N * ROW_WORDS,
                      symbols=(("stems", "stems_cat_label"), ("stems", "stems_icon"),
                               ("stems", "stems_zero"), ("stems", "stems_zero"),
                               ("stems", "stems_list"), ("stems", "stems_zero")),
                      refs=((ROOT_DESC + 0x18, ROOT_ROWS),)),),
    pokes=(Poke(ROOT_DESC, expect=(ROOT_N).to_bytes(4, "big"),
                write=(ROOT_N + 1).to_bytes(4, "big"), note="MAIN MENU categories 4 -> 5 (STEMS)"),),
    dram_regions=(DramRegion("stems_ring", 0x400000),
                  DramRegion("stems_stack", 0x2000),
                  DramRegion("stems_buf", 270336, align=512),),
    # verify_stems builds its own stems image and its fixture cards (from the
    # project template STEMS_TEMPLATE names, default out/projects/Ultimate FX
    # 1.5.3; it SKIPs the port runs by name without one) and runs the takes
    # under the port. The card reader's round trip is remix-independent:
    # every take is read back through it. verify_stems_menu boots the image
    # twice (MKII, MKI) under `ot_emu --interactive` and presses the menu's
    # keys; it SKIPs by name without the port or the template.
    gates=(Gate("tools/verify/verify_card_reader.py", remix_arg=False, venv=True),
           Gate("tools/verify/verify_stems.py", venv=True),
           Gate("tools/verify/verify_stems_menu.py", venv=True)),
)
