"""LOFI AMF FIX -- stock LO-FI's AMF knob computes with the wrong multiply.

Ported from bryantysinger/octa-bt-pt, a parameter-default patch tool for
1.40C (Sam's repo was its starting point, per the same conversation that
found `midi-scenes`). Almost everything that tool does is a per-user
PREFERENCE generator (pick your own defaults for any of the 14 stock
effects' knobs, pick FX1/FX2's default effect) -- there is no single right
answer to port as a fixed module, so none of that is here. This is the one
thing in it that IS a fixed, objective correctness fix rather than a
preference: LO-FI's AMF coefficient computation uses `mpysu x0,y0,a`
(signed x unsigned) where the intended arithmetic is unsigned x unsigned.

CLAUDE.md already documents this exact defect class for THIS project's own
`dsp_asm` (`mpy x0,y0` assembling to `mpysu`, found 9 Aug 2026) -- this is
the same instruction pair, the same bug, but in Elektron's SHIPPED,
compiled LO-FI code rather than anything this project assembles. `mpysu`
treats its second operand as unsigned and its first as signed; when the
first operand is actually a magnitude that should never go negative
(upstream: "LO-FI's AMF knob currently jumps the pitch backward at certain
values"), a `mpysu` silently corrupts exactly those values. `mpyuu`
(unsigned x unsigned) is the correct op for two magnitudes.

MEASURED, independently of upstream's own claim: this session disassembled
both 3-byte words with `vendor/dsp56300/build/source/disassemble/
dsp56kDisassemble` --

    001bef: mpysu   x0,y0,a   ; 01278d   (stock, both payloads)
    001bef: mpyuu   x0,y0,a   ; 0127cd   (the fix)

against octabam's own copy of the stock firmware -- not re-derived from
upstream's say-so. Upstream also reports a full 128x128 (AMF x Fine) sweep
with zero monotonicity violations after the fix; that sweep was not
reproduced here (no hardware/emulator harness for LO-FI's own DSP payload
code was built for this pass) -- INFERRED from upstream, not measured by
this module.

TWO ADDRESSES, ONE PER PAYLOAD. LO-FI is stock and un-replaced in every
octabam remix so far, so its code sits at the same DSP P address in every
image today -- P:0x01bef (payload A, tracks 1-4), P:0x019af (payload B,
tracks 5-8) -- resolved to their ColdFire-vaddr-equivalent file offsets
with this project's own `tools/build/dsp_modmap.py` (upstream vendors an
identical copy of that same file; not a coincidence -- same starting
point as midisc). Both resolved offsets hold the expected stock bytes.

⚠️ NOT A CAVE. Nothing here plants new code: it is two 3-byte pokes on
EXISTING, non-zero stock bytes, so this can only be `CavePatch.emit`
returning pokes, never a plain pinned cave (`build_bus.py` requires a
cave's destination to be free/zero space). If a future remix ever harvests
LO-FI's P-region as donor space for a new module's code, the `expect`
assertion on each poke refuses the build rather than silently overwriting
someone else's code with a stale address -- the same protection every
poke in `midi-scenes` relies on.
"""

from remix.schema import CavePatch, Kind, Module

# vaddr-equivalent = BASE + (payload_va - BASE) + module_data_offset
#                    + (dsp_word_addr - module_p_addr) * 3
# -- i.e. the exact file byte offset dsp_modmap.py's own parser resolves
# P:0x01bef/P:0x019af to, expressed the way every other poke in this repo
# addresses ColdFire/DSP bytes: as one flat vaddr into the image.
AMF_VADDR_A = 0x400F4BBB   # payload A (tracks 1-4), DSP P:0x01bef
AMF_VADDR_B = 0x40107B0C   # payload B (tracks 5-8), DSP P:0x019af

MPYSU_X0_Y0_A = bytes.fromhex("8d2701")   # mpysu x0,y0,a (little-endian 24-bit)
MPYUU_X0_Y0_A = bytes.fromhex("cd2701")   # mpyuu x0,y0,a

POKES = (
    ("LO-FI AMF coefficient, payload A (tracks 1-4)",
     AMF_VADDR_A, MPYSU_X0_Y0_A, MPYUU_X0_Y0_A),
    ("LO-FI AMF coefficient, payload B (tracks 5-8)",
     AMF_VADDR_B, MPYSU_X0_Y0_A, MPYUU_X0_Y0_A),
)


def emit_pokes(_addr):
    pokes = tuple((addr, expect, write) for _label, addr, expect, write in POKES)
    return b"", pokes


MODULE = Module(
    name="lofi-amf-fix",
    key="LOFI AMF FIX",
    kind=Kind.CF_PATCH,
    doc="Fixes stock LO-FI's AMF knob: mpysu -> mpyuu, both payloads. "
        "Ported from bryantysinger/octa-bt-pt.",
    cf_patches=(
        CavePatch(
            label="lofi amf fix: mpysu -> mpyuu (2 sites)",
            # Placeholder only -- emit_pokes plants no cave content of its
            # own (pinned=b""), only the two pokes above, so this address is
            # never written. It still has to pass build_bus.py's checks: a
            # DSP-payload address (AMF_VADDR_A) is far above SAFE_CAVE_CEIL
            # and would be refused outright, so this is a neutral point in
            # the decoded ColdFire free band instead -- below CLONE_BASE, so
            # it also never enters the descriptor-clone ordering assertion
            # that a cave INSIDE that window is subject to. Safe regardless
            # of what else shares this remix.
            cave_addr=0x400D2000,
            pinned=b"",
            emit=emit_pokes,
            report_note=" (LO-FI AMF: signed x unsigned -> unsigned x "
                        "unsigned, both payloads)",
        ),
    ),
)
