"""STEM REC -- T1 to the card while the sequencer plays (proof of concept).

MAIN MENU > CONTROL > STEM REC arms a recording, or starts one if the
sequencer is running; selecting it again stops it, and so does the
sequencer stopping or 15 seconds. The file is <set>/AUDIO/YYMMDD-HHMM/T1.wav,
16-bit stereo. Design: docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md.
Every stock fact the unit uses: docs/firmware/STEM_REC.md.

HOW, in one breath: a detour at the per-frame routine's only call site
(0x40004b12) packs T1's post-FX2 read-back block into a 4 MiB ring each
frame; an RTOS task of the module's own drains the ring to the card
through the stock buffered file API; the ring and the task's stack are
DramRegions at the free top of the platform reserve, so the module costs
no sample memory beyond what any DRAM remix already gives up.

⚠️ UNFLASHED. It shares the frame site with CF PROBE and the CONTROL list
with MENU SHORTCUT; the ledger refuses both pairings by name.
"""

from remix.schema import Detour, DramRegion, Kind, Linked, Module, Poke, TableGrow

# The per-frame routine's only call site, inside the audio interrupt at
# IPL 5: `jsr %pc@(0x400031a0)` then `move.w #0x2700,%sr` (cfprobe's site).
# The hook performs both, so a jsr + nop replaces them.
FRAME_SITE = 0x40004B12
FRAME_STOCK = bytes.fromhex("4ebae68c" "46fc2700")

# The CONTROL list (docs/firmware/MAINMENU.md sections 2-5): count at +0x00,
# row array pointer at +0x18. TableGrow copies the stock rows from the user's
# image at build time and appends ours; an ACTION row has window, child and
# id 0.
CONTROL_DESC = 0x400CBD54
CONTROL_ROWS = 0x400CC5A8
ROW_N, ROW_WORDS = 6, 6

MODULE = Module(
    name="stems",
    key="STEM REC",
    kind=Kind.CF_PATCH,
    doc="MAIN MENU > CONTROL > STEM REC: T1 to the card while the sequencer plays "
        "(POC: 16-bit, 15 s).",
    linked=(Linked("stems", "modules/stems/stems.s", dram=True),),
    detours=(Detour(FRAME_SITE, FRAME_STOCK, "stems", "stems_frame_hook",
                    "per-frame tap: T1 into the ring, then the stock routine",
                    kind="jsr", pad_to=8),),
    tables=(TableGrow("CONTROL rows + STEM REC", old=CONTROL_ROWS,
                      count=ROW_N * ROW_WORDS,
                      symbols=(("stems", "stems_label"), ("stems", "stems_zero"),
                               ("stems", "stems_action"), ("stems", "stems_zero"),
                               ("stems", "stems_zero"), ("stems", "stems_zero")),
                      refs=((CONTROL_DESC + 0x18, CONTROL_ROWS),)),),
    pokes=(Poke(CONTROL_DESC, expect=(ROW_N).to_bytes(4, "big"),
                write=(ROW_N + 1).to_bytes(4, "big"), note="CONTROL count 6 -> 7"),),
    dram_regions=(DramRegion("stems_ring", 0x400000),
                  DramRegion("stems_stack", 0x2000)),
)
