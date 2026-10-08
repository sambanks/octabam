"""RECORDER LOOP FIX -- the recorder loop click: eight ColdFire caves, no DSP
code, for a FLEX voice playing its own recorder buffer every bar.

At a tempo whose bar is not a whole number of samples (82,687.5 at 128 BPM)
the sequencer arms the recorder at floor(k x period), 82,687 and 82,688
samples apart, while stock records one constant length. Four faults sat on
that, one cave group each (README.md, "The caves"):

- seek bind (seekbind.s, hook 0x4000f8cc): a same-slot/type/generation
  FLEX re-bind takes the bind's same-sample path, so the DSP seeks the
  running voice instead of re-priming it as a new note (a chirp, then hash
  at 140 % of the signal over 300 samples).
- seek-bind counter (seekbind_ctr.s, hook 0x4000f834): on that re-bind the
  voice's per-bind counter (+0x90) is left alone, so the frame builder does
  not re-send the voice as new (a +/-1.5-sample seam).
- spacing (spacing_cave.s, hook 0x40006e0c): a fixed-RLEN recording is
  exactly as long as the gap to the next arm, L' = q + floor((k+1)r/D) -
  floor(k r/D) with q, r = divmod(RLEN x 15,876,000, tempo24) and
  k = arm/q, from the current arm alone (a -26 dB, ~1 ms scuff on
  alternate bars).
- hold (hold_*.s + fix.inc, five hooks): in sound-on-sound the voice plays
  the previous pass; where its window is one sample longer than the
  recording, the sample past END is the last one repeated instead of a zero
  (the three fetch caves when the fetch past END comes back empty; the two
  guard caves where the copies' cap on a buffer being recorded into would
  stop the voice and zero-fill, after a second transport start).

On hardware: the first three as OCTABAM83 (Sam's MKII, 12 Sep 2026, the
self-recording loop); all eight as Bryan T's sos-capture BUILD=95
(3 Oct 2026, sound-on-sound). Formerly four modules: FLEX SEEK BIND,
FLEX SEEK BIND CTR, RECORDER SPACING, RECORDER HOLD.

Assemble (from the repo root, for the .include): `m68k-elf-as -mcpu=5475
-o x.o modules/recorder-loop-fix/<cave>.s`; the build re-assembles each
cave and compares against the pinned bytes below. objdump prints every
divu.l in spacing_cave.s as `remul` (0x4c4x is one encoding family, named
after the remainder form); with the extension's Dq and Dr fields equal,
ColdFire writes the quotient.
"""

import hashlib

from remix.schema import Category, Proof, Detour, Kind, Linked, Module

# The audio arena base, stock; the build resolves ARENA_BASE to the moved base.
_ARENA = (("ARENA_BASE", 0x40a955e0),)


def _ref(pinned):
    """The ratified bytes as a Linked.reference: position-independent, so
    linked anywhere; 0x400d7000 is a ROM address the caves floated to."""
    return (0x400d7000, hashlib.sha256(pinned).hexdigest())

SEEKBIND_HOOK = 0x4000f8cc
SEEKBIND_HOOK_STOCK = bytes.fromhex("4a2f0037" "6718")       # tstb (55,sp) / beqs 0x4000f8ea

SPACING_HOOK = 0x40006e0c
SPACING_HOOK_STOCK = bytes.fromhex("2800" "5284" "e284")   # movel d0,d4; addql #1,d4; asrl #1,d4

SPACING_CAVE_BYTES = bytes.fromhex(
    "2800" "5284" "e284"                     # displaced: L = (product + 1) >> 1
    "4fefffe8" "48d7030f"                    # save d0-d3/a0-a1 (24 bytes)
    "2239" "80001814" "6700" "0072"          # d1 = tempo24; 0 -> keep
    "2004" "4c010000"                        # d0 = L x D
    "0680" "00791fd0"                        # + 7,938,000  (round to nearest)
    "243c" "00f23fa0"                        # d2 = 15,876,000
    "4c420000" "6700" "0058"                 # d0 = RLEN = (L x D + K/2) / K; 0 -> keep
    "4c020000" "2600"                        # d0 = N = RLEN x K; d3 = N
    "4c410000" "6700" "004a"                 # d0 = q = N / D; 0 -> keep
    "2400" "4c010000" "9680" "6700" "002c"   # d2 = q; d3 = r = N - q x D; 0 -> guard
    "202f00a4" "e588"                        # d0 = track x 4  (caller's sp(136) + 4 + 24)
    "41f946c7fa84" "20300800"                # d0 = arm sample[track]
    "4c420000"                               # d0 = k = arm / q
    "4c030000" "2240"                        # d0 = k x r; a1 = k x r
    "d083" "2609"                            # d0 = (k+1) x r; d3 = k x r
    "4c410000" "4c413003"                    # d0 = floor((k+1)r/D); d3 = floor(k x r/D)
    "9083" "d480"                            # d0 = overflow (0|1); d2 = L' = q + overflow
    "2002" "9084" "5280" "0c8000000002" "6200" "0004"  # |L' - L| <= 1 ?
    "2802"                                   # d4 = L'
    "4cd7030f" "4fef0018" "4e75")            # restore, rts

MODULE = Module(
    name="recorder-loop-fix",
    key="RECORDER LOOP FIX",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE,
    proof_note="OCTABAM83, 12 Sep 2026 (self-loop); Bryan T's MKII, sos-capture BUILD=95, 3 Oct 2026 (sound-on-sound)",
    doc="ColdFire caves: the recorder loop click -- seek on a same-sample FLEX re-bind, keep its "
        "counter, record exactly the arm spacing, and repeat the last sample where sound-on-sound "
        "would play a zero.",
    # DRAM units since 8 Oct 2026 (floating ROM caves until then). Each is
    # linked alone at 0x400d7000 with ARENA_BASE at stock's 0x40a955e0 and
    # compared against its ratified bytes; the image carries ARENA_BASE at
    # the remix's moved base.
    linked=(
        Linked("rlf_seekbind", "modules/recorder-loop-fix/seekbind.s", dram=True, defsyms=_ARENA,
               reference=_ref(bytes.fromhex("4a2f003b670a7001588f4ef94000f8ec588f4ef94000f8ea"))),
        Linked("rlf_seekbind_ctr", "modules/recorder-loop-fix/seekbind_ctr.s", dram=True, defsyms=_ARENA,
               reference=_ref(bytes.fromhex("4a2f003b660452aa0090254800984e75"))),
        Linked("rlf_spacing", "modules/recorder-loop-fix/spacing_cave.s", dram=True, defsyms=_ARENA,
               reference=_ref(SPACING_CAVE_BYTES)),
        Linked("rlf_hold_copy", "modules/recorder-loop-fix/hold_copy.s", dram=True, defsyms=_ARENA,
               reference=_ref(bytes.fromhex("225f206f0004508f6100000826004a814ed10c8040a955e0660000504a816f00004a4a2a00156c000042b1ea00646600003a538820086b00002c2f012f092f002f0a206effbc4e90508f225f0c8040a955e06700000e4a816f000008588f72014e75221f203c40a955e04e75"))),
        Linked("rlf_hold_xfade_a", "modules/recorder-loop-fix/hold_xfade_a.s", dram=True, defsyms=_ARENA,
               reference=_ref(bytes.fromhex("225f206f00046100000c264028012f2a004c4ed10c8040a955e0660000504a816f00004a4a2a00156c000042b1ea00646600003a538820086b00002c2f012f092f002f0a206effbc4e90508f225f0c8040a955e06700000e4a816f000008588f72014e75221f203c40a955e04e75"))),
        Linked("rlf_hold_xfade_b", "modules/recorder-loop-fix/hold_xfade_b.s", dram=True, defsyms=_ARENA,
               reference=_ref(bytes.fromhex("225f206f00046100000c2e004fef00104a844ed10c8040a955e0660000504a816f00004a4a2a00156c000042b1ea00646600003a538820086b00002c2f012f092f002f0a206effbc4e90508f225f0c8040a955e06700000e4a816f000008588f72014e75221f203c40a955e04e75"))),
        Linked("rlf_hold_guard", "modules/recorder-loop-fix/hold_guard.s", dram=True, defsyms=_ARENA,
               reference=_ref(bytes.fromhex("588f93c0b3c26c00000424094a826e000040b3fc00000000660000364a816f000030202a006453806b0000262f012f002f0a206effbc4e90508f0c8040a955e06700000c4a816f00000626007401221f4ef94000871e"))),
        Linked("rlf_hold_xguard", "modules/recorder-loop-fix/hold_xguard.s", dram=True, defsyms=_ARENA,
               reference=_ref(bytes.fromhex("588f9a80ba826c00000424054a826e0000604a856600005a4a846f0000544a816f00004e4a2a001766000046202a006453806b00003c2f012f002f0a206effbc4e90508f0c8040a955e0670000224a816f00001c2a2a0064baaa0048660000042640baaa004c660000042e007401221f4ef9400085e0"))),
    ),
    detours=(
        Detour(SEEKBIND_HOOK, SEEKBIND_HOOK_STOCK, "rlf_seekbind", "rlf_seekbind",
               "seek bind: same-sample re-bind -> seek path", kind="jsr"),
        Detour(0x4000f834, bytes.fromhex("52aa0090" "25480098"), "rlf_seekbind_ctr", "rlf_seekbind_ctr",
               "seek-bind counter: same-sample re-bind keeps +0x90", kind="jsr", pad_to=8),
        Detour(SPACING_HOOK, SPACING_HOOK_STOCK, "rlf_spacing", "rlf_spacing",
               "spacing: fixed-RLEN length := the next arm's spacing, from the current arm", kind="jsr"),
        Detour(0x400086c2, bytes.fromhex("2600" "508f" "4a81"),       # move.l d0,d3 / addq.l #8,sp / tst.l d1
               "rlf_hold_copy", "rlf_hold_copy",
               "hold (copy): recorder voice at END reads END - 1, not the null block", kind="jsr"),
        Detour(0x4000853e, bytes.fromhex("2640" "2801" "2f2a004c"),   # movea.l d0,a3 / move.l d1,d4 / move.l (76,a2),-(sp)
               "rlf_hold_xfade_a", "rlf_hold_xfade_a",
               "hold (crossfade, +0x48): the crossfade copy's first read", kind="jsr", pad_to=8),
        Detour(0x4000854e, bytes.fromhex("2e00" "4fef0010" "4a84"),   # move.l d0,d7 / lea (16,sp),sp / tst.l d4
               "rlf_hold_xfade_b", "rlf_hold_xfade_b",
               "hold (crossfade, +0x4c): the crossfade copy's second read", kind="jsr", pad_to=8),
        Detour(0x40008716, bytes.fromhex("93c0" "b3c2" "6c02"),       # suba.l d0,a1 / cmpa.l d2,a1 / bge.s
               "rlf_hold_guard", "rlf_hold_guard",
               "hold (copy guard): the cap at END while recording, END - 1 once", kind="jsr"),
        Detour(0x400085d8, bytes.fromhex("9a80" "ba82" "6c02"),       # sub.l d0,d5 / cmp.l d2,d5 / bge.s
               "rlf_hold_xguard", "rlf_hold_xguard",
               "hold (crossfade guard): the crossfade copy's cap at END", kind="jsr"),
    ),
)
