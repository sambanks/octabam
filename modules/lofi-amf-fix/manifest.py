"""LOFI AMF FIX -- stock LO-FI's AMF coefficient multiply is `mpysu x0,y0,a`
(signed x unsigned) on two magnitudes; the fix is `mpyuu`. Ported from
bryantysinger/octa-bt-pt (his report: "LO-FI's AMF knob jumps the pitch
backward at certain values"). The rest of that tool generates per-user
parameter defaults and is not ported.

Measured here: both words disassembled against the stock image --

    001bef: mpysu   x0,y0,a   ; 01278d   (stock, both payloads)
    001bef: mpyuu   x0,y0,a   ; 0127cd   (the fix)

at P:0x01bef (payload A) / P:0x019af (payload B), resolved to file offsets
with tools/build/dsp_modmap.py. Upstream's 128x128 AMF x Fine sweep (zero
monotonicity violations after the fix) is not reproduced here.

Two pokes on existing stock bytes, so this is `CavePatch.emit` returning
pokes, not a cave. If a remix ever harvested LO-FI's code, each poke's
`expect` refuses the build.
"""

from remix.schema import Category, Evidence, Level, CavePatch, Kind, Module

# Image vaddr of each DSP word: payload_va + module_data_offset
# + (dsp_word_addr - module_p_addr) * 3, as dsp_modmap.py resolves it.
AMF_VADDR_A = 0x400F4BBB   # payload A (tracks 5-8), DSP P:0x01bef
AMF_VADDR_B = 0x40107B0C   # payload B (tracks 1-4), DSP P:0x019af

MPYSU_X0_Y0_A = bytes.fromhex("8d2701")   # mpysu x0,y0,a (little-endian 24-bit)
MPYUU_X0_Y0_A = bytes.fromhex("cd2701")   # mpyuu x0,y0,a

POKES = (
    ("LO-FI AMF coefficient, payload A (tracks 5-8)",
     AMF_VADDR_A, MPYSU_X0_Y0_A, MPYUU_X0_Y0_A),
    ("LO-FI AMF coefficient, payload B (tracks 1-4)",
     AMF_VADDR_B, MPYSU_X0_Y0_A, MPYUU_X0_Y0_A),
)


def emit_pokes(_addr):
    pokes = tuple((addr, expect, write) for _label, addr, expect, write in POKES)
    return b"", pokes


MODULE = Module(
    name="lofi-amf-fix",
    key="LOFI AMF FIX",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="bryantysinger/octa-bt-pt", author_url="https://github.com/bryantysinger/octa-bt-pt",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); both words disassembled against stock"),),
    doc="Fixes stock LO-FI's AMF knob: mpysu -> mpyuu, both payloads. "
        "Ported from bryantysinger/octa-bt-pt.",
    cf_patches=(
        CavePatch(
            label="lofi amf fix: mpysu -> mpyuu (2 sites)",
            # Never written (pinned=b""): a neutral address in the ColdFire
            # free band that passes build_bus.py's cave checks. The pokes
            # carry the real addresses.
            cave_addr=0x400D2000,
            pinned=b"",
            emit=emit_pokes,
            report_note=" (LO-FI AMF: signed x unsigned -> unsigned x "
                        "unsigned, both payloads)",
        ),
    ),
)
