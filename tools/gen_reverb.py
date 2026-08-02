#!/usr/bin/env python3
"""
Emit the reverb DSP source from a configuration.

    python3 tools/gen_reverb.py [name] > dsp/reverbNN.asm

Hand-editing stopped scaling once the same engine needed three voicings and a
set of buffer sizes that had to stay consistent across a dozen places (masks,
tap wrap constants, base addresses, N registers). Every one of those is derived
here from LINE_LEN / AP_LEN, so a size change cannot leave a stale mask behind.

The hardware constraints this encodes, all established by probe:

  * delay buffers live in Y memory, and Y ends at 0xC000 -- measured with
    dsp/ymemprobe.asm, which sweeps a wet-only echo buffer across Y a page at a
    time. It goes silent at page 47, so 0x400..0xBFFF is real and 0x7a5..0xBFFF
    is free of loaded modules.
  * init must not loop, and must not reset anything that has to survive: it
    appears to run far more often than once per effect selection, so resetting
    the write phase there empties the tank every frame.
  * M registers must be restored to $ffffff before returning.
  * the write phase persists at r7+$83 and must be masked on LOAD as well as on
    save -- it can come back as garbage.
  * the diffuser and the modulated reads must not use modulo addressing or the
    N register. Recomputing an r/n pair inside the sample loop hangs the DSP.
    Addresses are computed arithmetically and masked instead, with two
    instructions between writing r5 and using it.
"""
import os
import sys

# ---- memory ---------------------------------------------------------------
# Buffers are PER-INSTANCE. The host runs a bump allocator: X:0x213 holds a
# pointer into a table of per-instance buffer bases (X:0x255, one word each,
# advanced by one per effect), and X:0x20a does the same for the 0x100-word r7
# state blocks. An effect reads its own base with
#
#     move x:>$213,r4        move x:(r4),x0
#
# and places every buffer at base + a fixed offset. That is exactly what DARK
# REV does, and its offsets run to 0x3da0.
#
# The table shows the whole layout, and it is tight:
#
#     Y:0x0000-0x0FFF   system
#     Y:0x1000-0x3FFF   4 FX1 instances, 0xc00 words each
#     Y:0x4000-0xBFFF   2 FX2 instances, 0x4000 words each  -- exactly to 0xC000
#     Y:0x30000+        2 more FX2 instances
#
# So an FX2 effect gets 0x4000 = 16384 words, and FX1 only 3072 -- which is why
# the reverbs are FX2-only. Hardcoding absolute addresses, as every build up to
# v22 did, writes through all of them; it only worked because nothing else was
# running. Everything below is an OFFSET from the instance base and the total
# must not exceed 0x4000.
ALLOC_PTR = 0x213           # X: pointer to this instance's base
ALLOC_TAB = 0x255           # X: the table itself, one word per instance
STATE_TAB = 0x6000          # X: first r7 state block

# X:0x213 is only readable in init -- the dispatcher advances it before calling
# process, and the stock reverbs read it there too. Getting the value across to
# process is the hard part, because only r7+$83 persists and the tank phase owns
# it. So init stashes the base in absolute Y at an address unique to the
# instance:
#
#     Y:(STASH + (r7 >> 8))   ->  0x861..0x86f for r7 = 0x6100..0x6f00
#
# Absolute, but one word per instance, so instances do not collide.
#
# STASH WAS 0x735, AND THAT IS WHY v30/v31 HUNG ON TWO TRACKS. That put the
# stash at 0x796..0x79b, chosen as "the free window above the loaded coefficient
# module at 0x715..0x794" -- which is payload A's map. Payload B loads 21 Y
# modules below 0x1000 rather than A's 5, and its last one runs to Y:0x7a4. So
# on payload B every stash address landed INSIDE a live 128-word coefficient
# table: the effect corrupted another algorithm's coefficients, then read that
# algorithm's data back as its own buffer base and wrote 14K words from wherever
# that pointed.
#
# The free window is Y:0x7a5..0xFFF in both payloads (nothing else is loaded
# below the FX1 buffers at 0x1000), so 0x800-based addresses are clear in both.
#
# Deriving the base as x:(0x255 + ((r7 - 0x6000) >> 8)) does NOT work, though the
# arithmetic looked sound: measured on hardware, r7 = 0x6200, and table[2] is
# 0x1c00 -- a 3072-word FX1 slot. A 16K layout there runs to 0x53ff, through the
# other FX1 buffers and into FX2 slot 0. The pointers do advance together, but
# FX2 effects do not take even table entries -- each track allocates an FX1 slot
# and then an FX2 slot, so FX2 instance k takes table entry 1 + 2k and state
# block 0x6000 + (2 + 2k) * 0x100. That model reproduces both measurements:
# r7probe returned 0x6200 and baseprobe returned 0x4000 and 0x8000.
#
# Measured with dsp/baseprobe.asm: the stash returns 0x4000, an FX2 slot.
STASH     = 0x800

# WHERE OUR r7 SCRATCH LIVES.
#
# Every build that writes r7 slots hangs on two tracks; every build that writes
# none survives. dsp/minimal.asm and dsp/baseprobe.asm both run two instances
# and neither writes a single r7 word, while v30, v31, v33, v37 and v38 all
# write 41 of them and all hang. That is a clean split across seven builds.
#
# Two earlier findings say the same thing and were read as curiosities at the
# time: r7+$71..$78 do NOT survive between calls, which means something else is
# writing them, and r7+$84..$8a hangs outright. The block is not ours to use
# from $50 up -- it is the host's.
#
# DARK REV keeps its per-instance state at r7+$1a..$4x, carries buffer addresses
# through it from init into process, and runs on every track at once. So that
# region is per-instance and safe. Slots $50..$7f are shifted down into it;
# the phase stays at $83, which is where the stock tank phase lives and is the
# one slot already proven to persist.
SLOT_LO, SLOT_HI = 0x50, 0x7f       # the range the generator emits
SLOT_SHIFT = 0x40                   # -> $10..$3f, inside DARK REV's region

# How process gets hold of the base:
#
#   "stash"     init reads X:0x213 and leaves it at Y:(STASH + (r7 >> 8)).
#               The only one that is correct with more than one instance.
#   "procread"  process reads X:0x213 itself. Works on one track by luck and
#               hangs on two; kept because it is the shortest and it is what
#               v33 shipped, so builds can be compared against it.
#   "fixed"     ALLOC_FIXED, for bisecting only -- it pins every instance to the
#               same region, so two tracks collide by construction.
BASE_MODE = "stash"

# Which stages of the engine to emit. dsp/minimal.asm -- a bare rts init and a
# five-instruction copy loop -- runs happily on two tracks, so the hang is in
# something the algorithm does, and this is how we find out what. Drop a stage
# and the data flow closes over the gap: without "pre" the mono input goes
# straight to the diffuser, without "diff" it goes straight to the tank, without
# "mod" every line uses its fixed N-register tap and the LFO is not emitted.
#
#   "tank"  the four delay lines, the Hadamard, the damping and the output
#   "pre"   the pre-delay, which is the only other user of r5/m5 modulo
#   "diff"  the four series allpasses, which use computed addressing
#   "mod"   the LFO and the interpolated modulated reads on MOD_LINES
#   "size"  SIZE scaling the taps; without it every tap is a constant
#   "lines" the delay-line reads and writes themselves. Without it the pointers
#           still advance under modulo and every other thing proc does still
#           happens -- there is simply no Y buffer traffic. That splits "what the
#           setup does" from "touching the buffer", which is the last division
#           left after instprobe proved the base and r7 both arrive correctly.
#
# "tank" is not optional -- without it there is no effect, and dsp/minimal.asm
# already covers that case.
# Override without editing, so a bisect build is reproducible from its command:
#     RV_STAGES=tank python3 tools/gen_reverb.py v37 > dsp/reverb37.asm
STAGES = set((os.environ.get("RV_STAGES") or "tank,pre,diff,mod,size,lines").split(","))

# Only used when BASE_MODE == "fixed". 0x4000 is a real FX2 slot, so it is safe
# to run on one track.
ALLOC_FIXED = 0x4000

LINE_OFF  = 0x0000          # four tank lines, one per 0x800
LINE_LEN  = 2048
LINE_TAPS = [1567, 1249, 977, 733]          # 35.5 / 28.3 / 22.2 / 16.6 ms, prime

AP_OFF    = 0x2000          # four series allpasses, one per 0x400
AP_LEN    = 1024
AP_TAPS   = [907, 673, 487, 331]            # 20.6 / 15.3 / 11.0 / 7.5 ms

MOD_LINES = [1, 2]          # which tank lines get the interpolated read

# Where the diffused input is injected: {line: (op, scratch slot)}.
#
# Injecting into line 0 alone is what produces the bloom, but at these tap
# lengths it also produces a hole: nothing reaches an output-tapped line until
# line 0's tap fires (71 ms) and then the output line's does, so the reverb does
# not start for ~100 ms -- and it starts at different times per channel, which
# reads as the right side arriving first rather than as width.
#
# Injecting at two levels rather than one keeps the build-up -- the fully-fed
# lines still dominate and the Hadamard still has to spread the rest -- while
# putting first energy in every line immediately. Signs alternate so the lines
# decorrelate.
IN_FULL = 0x55
IN_HALF = 0x67
# Each output pair gets exactly one full-injected line and one half-injected
# line, so the channels come out level. Injecting full into line 0 only left R
# 3.7 dB hotter than L, because R is the pair that happens to contain line 0.
INJECT = {0: ("add", IN_FULL), 1: ("sub", IN_FULL),
          2: ("sub", IN_HALF), 3: ("add", IN_HALF)}

# Output taps, summed per channel. Two taps each rather than one: it doubles the
# output density and evens up the first-arrival times between channels.
OUT_L = [1, 2]              # 56 / 44 ms -> L starts at 44 ms
OUT_R = [0, 3]              # 71 / 33 ms -> R starts at 33 ms
LFO_INC   = 0xa0            # ~0.8 Hz at 44.1k over a 0x800000 phase
MOD_DEPTH = 8               # peak samples; set by the asl below, see split()

PRE_OFF   = 0x3000          # pre-delay; the base is 0x4000-aligned, so this is
PRE_LEN   = 0x800           # PRE_LEN-aligned too, which m5 modulo requires
PRE_MASK  = PRE_LEN - 1     # 2048 words = 46 ms
                            # total: 0x2000 + 0x1000 + 0x800 = 0x3800 of 0x4000

# Persistent state moves OUT of absolute Y and into the r7 block, which is
# already per-instance and 0x100 words long. r7+$83 is proven to survive between
# frames -- it is where the tank write phase lives -- and these sit beside it.
# The stock code writes r7+$82/$84/$8b, so the region is real.
# Where persistent state lives, established by bisection on hardware:
#
#   r7+$83        persists          (the stock tank phase lives here)
#   r7+$71..$78   fine WITHIN a call, but not across calls
#   r7+$84..$8a   does NOT persist -- putting state here hangs the DSP
#
# DARK REV's init writes $1a $1b $1f $82 $83 $84 $8b and pointedly skips
# $85..$8a, which now looks like it was avoiding host-owned words.
#
# So only ONE persistent r7 word is available, and that is enough:
#
#  * the tank, allpass and pre-delay phases all advance by exactly 1 per sample
#    and differ only in their mask, so they are the SAME counter. r1 already
#    carries it (base + phase, with the base aligned), so each is just r1 masked.
#  * the LFO phase and the four damping states cannot be derived. They go in the
#    instance's own Y region and are loaded and saved once per BLOCK -- the LFO
#    already runs per block, and a one-pole's state only has to survive the gap.
#
# Nothing here costs a per-sample instruction; it is ~30 per block.
STATE_OFF = 0x3800          # Y, inside the instance: LFO phase + 4 damping states
PHASE  = "x:(r7+$79)"       # allpass phase, recomputed from r1 each sample
LFOPH  = "x:(r7+$7e)"       # per-block working copy of the Y word
DAMP   = [f"x:(r7+${0x7a+i:02x})" for i in range(4)]
BASE      = "x:(r7+$71)"    # this instance's buffer base
APB       = 0x72            # the four allpass bases, r7+$72..$75

# ---- parameters -----------------------------------------------------------
# Layout follows Blackhole's primary page (Mix, Gravity, Feedback, Size, Lo, Hi)
# and Supermassive's core set, which agree on what belongs where. LO is the one
# gap: a low cut inside the feedback loop needs four more filter states and ~24
# instructions a sample, and the cycle headroom is not measured yet.
# Page 1 is r6+0..5. Page 2 is NOT r6+6..8, and it is not in display order
# either -- mapped on hardware with dsp/pagemap_probe.asm, which put an
# unmistakable behaviour on each candidate offset:
#
#     knob PRE   -> r6+$e        knob MONO  -> r6+$d
#     knob BAL   -> r6+$b        knob MIXF  -> r6+$c   (boolean mix/send)
#
# That also explains the stock code: DARK REV and PLATE REV read r6+0..5 plus
# r6+$c and r6+$e -- the mix/send mode and the PRE knob, which really is their
# pre-delay. They leave BAL and MONO to the host.
#
# Our pre-delay therefore sits on the knob already labelled PRE, and page 1's
# fourth slot is freed for LO.
P_TIME, P_HI, P_SIZE, P_SPARE, P_MOD, P_MIX = range(6)
P_PRE   = 0xe               # knob PRE
P_WIDTH = 0xb               # knob BAL
P_RATE  = 0xd               # knob MONO

LINE_MASK = LINE_LEN - 1
AP_MASK   = AP_LEN - 1


def neg24(n):
    return (-n) & 0xffffff


def allpass(i):
    off, tap = AP_OFF + i * AP_LEN, AP_TAPS[i]
    return f"""
; -- allpass {i}: base+{off:#06x}, tap {tap} ({tap/44.1:.1f} ms) --
        move    {PHASE},a
        move    #>{AP_LEN - tap},x0
        add     x0,a
        move    #>${AP_MASK:x},x0
        and     x0,a                    ; (phase - tap) mod {AP_LEN}
        move    x:(r7+${APB+i:02x}),x0
        add     x0,a
        move    a,r5
        move    #>$400000,y0            ; coefficient, and fills the AGU slot
        move    y:(r5),b                ; d
        move    b,x0
        mpy     x0,y0,a
        move    x:(r7+$5b),x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$5c)
        move    a,x1
        mpy     x1,y0,a
        sub     a,b                     ; out = d - g*v
        move    b,x:(r7+$5b)
        move    {PHASE},a               ; write v at base + phase
        move    x:(r7+${APB+i:02x}),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$5c),a            ; reload v, fills the AGU slot
        move    a,y:(r5)
"""


def split(mi, mf, who):
    """Integer + fraction from a triangle already in A, both positive.

    The fraction MUST NOT be taken straight out of A1: it is unsigned there, and
    mpy reads its operand as signed, so anything above 0.5 comes back negative
    and the interpolation turns into an extrapolation with gain up to 2. That is
    what made an earlier build self-oscillate. Masking to the low 19 bits and
    shifting left 4 caps it at $7ffff0, which is always positive.
    """
    return f"""        move    a1,x1                   ; T
        asl     #$5,a,a
        move    a2,x0
        move    x0,x:(r7+${mi:02x})     ; {who}: integer offset, 0..{MOD_DEPTH}
        move    x1,a                    ; T again, A2 = 0 because T is positive
        move    #>$07ffff,x0
        and     x0,a
        asl     #$4,a,a                 ; fraction, at most $7ffff0 -> positive
        move    a,x0
        move    x0,x:(r7+${mf:02x})
"""


def lfo():
    return f"""
; ---- LFO: one triangle and its inverse ----------------------------------
        move    {LFOPH},a               ; persistent phase, [0,$7fffff]
        move    x:(r7+$6f),x0           ; increment, from RATE
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap; A1 is right even if A2 carried
        move    a1,x0                   ; extract without saturating on A2
        move    x0,{LFOPH}
        move    x0,a                    ; clean copy, A2 = 0
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle T, 0 .. $400000
        move    a,x0
        move    x:(r7+$68),y1           ; MOD depth
        mpy     x0,y1,a                 ; scaled triangle
        move    a1,x0
        move    x0,x:(r7+$66)           ; stash for the inverse
""" + split(0x61, 0x62, "line %d" % MOD_LINES[0]) + f"""        move    #>$400000,a
        move    x:(r7+$66),x0
        sub     x0,a                    ; inverse triangle
""" + split(0x63, 0x64, "line %d" % MOD_LINES[1])


def modread(i, mi, mf):
    """Interpolated read for tank line i: d = d0 + f*(d1-d0), f in [0,1)."""
    off, tap = LINE_OFF + i * LINE_LEN, LINE_TAPS[i]
    slot = 0x76 if i == MOD_LINES[0] else 0x77
    return f"""; -- line {i} modulated: base+{off:#06x}, tap {tap}, interpolated --
        move    r1,b
        move    #>${LINE_MASK:x},x0
        and     x0,b                    ; shared write phase
        move    x:(r7+${mi:02x}),x0
        sub     x0,b                    ; phase - offset
        move    x:(r7+${0x6a if i == MOD_LINES[0] else 0x6b:02x}),x0    ; {LINE_LEN} - tap, from SIZE
        add     x0,b
        move    #>${LINE_MASK:x},x0
        and     x0,b                    ; i0
        move    b,a
        add     x0,a
        and     x0,a                    ; i1 = (i0-1) mod {LINE_LEN}
        move    x:(r7+${slot:02x}),x0
        add     x0,b
        add     x0,a
        move    a,x1
        move    b,r5
        move    x:(r7+${mf:02x}),y1     ; fraction -- y1, NOT y0: y0 holds DAMP
        move    x1,a
        move    y:(r5),b                ; d0
        move    a,r5
        move    b,x:(r7+$65)
        move    b,x0                    ; both fill the AGU slot
        move    y:(r5),a                ; d1
        sub     x0,a
        move    a,x0
        mpy     x0,y1,a                 ; f*(d1-d0)
        move    x:(r7+$65),x0
        add     x0,a                    ; interpolated tap
"""


def tap(i):
    """One tank tap, damped inside the feedback path, result to r7+$56+i."""
    if "mod" in STAGES and i == MOD_LINES[0]:
        head = modread(i, 0x61, 0x62)
    elif "mod" in STAGES and i == MOD_LINES[1]:
        head = modread(i, 0x63, 0x64)
    else:
        head = (f"        move    y:(r{i+1}+n{i+1}),a         ; line {i}, fixed tap {LINE_TAPS[i]}\n"
                if "lines" in STAGES else
                f"        clr     a                       ; line {i} NOT READ -- no buffer traffic\n")
    return head + f"""        move    {DAMP[i]},b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,{DAMP[i]}
        move    a,x:(r7+${0x56+i:02x})
"""


def remap_slots(text):
    """Shift every r7+$NN in SLOT_LO..SLOT_HI down by SLOT_SHIFT.

    Done on the finished text rather than at each emission site: there are ~40
    of them across a dozen f-strings, and one missed reference would read a slot
    nobody wrote. This cannot miss one, and it is checked below.
    """
    import re

    def sub(m):
        n = int(m.group(1), 16)
        if SLOT_LO <= n <= SLOT_HI:
            n -= SLOT_SHIFT
            assert n >= 0x10, f"slot ${n:02x} shifted below $10"
        return f"r7+${n:02x}"

    out = re.sub(r"r7\+\$([0-9a-f]{2})", sub, text)
    left = sorted({int(x, 16) for x in re.findall(r"r7\+\$([0-9a-f]{2})", out)})
    bad = [n for n in left if SLOT_LO <= n <= SLOT_HI or n in (0x00, 0x01)]
    assert not bad, f"slots still in the host's range: {[hex(n) for n in bad]}"
    return out


def main():
    tail_ms = LINE_LEN / 44.1
    body = f"""; ---------------------------------------------------------------------------
; {sys.argv[1] if len(sys.argv) > 1 else 'reverb'} -- generated by tools/gen_reverb.py, do not hand-edit
;
; Four series allpasses into a four-line FDN with a 4x4 Hadamard, one-pole
; damping inside the feedback path, and interpolated modulation on two lines.
;
; All buffers are relative to the per-instance base at x:(x:>$213), so two
; tracks running this effect do not write through each other. An FX2 instance is
; given 0x4000 words:
;   lines      base+{LINE_OFF:#06x} .. base+{LINE_OFF + 4*LINE_LEN - 1:#06x}   {LINE_LEN} words each
;              taps {' '.join(str(t) for t in LINE_TAPS)}  ({' '.join(f'{t/44.1:.0f}' for t in LINE_TAPS)} ms)
;   allpasses  base+{AP_OFF:#06x} .. base+{AP_OFF + 4*AP_LEN - 1:#06x}   {AP_LEN} words each
;              taps {' '.join(str(t) for t in AP_TAPS)}  ({' '.join(f'{t/44.1:.0f}' for t in AP_TAPS)} ms)
;   pre-delay  base+{PRE_OFF:#06x} .. base+{PRE_OFF + PRE_LEN - 1:#06x}   {PRE_LEN} words ({PRE_LEN/44.1:.0f} ms)
;   total      {AP_OFF + 4*AP_LEN + PRE_LEN:#06x} of the 0x4000 an FX2 instance is given
;
; The allpasses are long on purpose. Four lines at ~50 ms is only ~80 echoes a
; second, which on its own reads as a stutter rather than a wash; the density
; has to come from diffusion, so the allpasses run 9-24 ms instead of the 3-8 ms
; they were when the whole engine had to fit in 6K.
;
; State (all in the per-instance r7 block, not absolute Y):
;   r7+$83        write phase (persistent, masked on load as well as save)
;   r7+$83        the ONE persistent word: tank / allpass / pre-delay phase
;   base+{STATE_OFF:#06x}   LFO phase and 4 damping states, loaded per block
;   r7+$71..$78   this instance's base, and the bases derived from it
;   r7+$55..$66   per-sample scratch
;
; Parameters:
;   p0 TIME -> feedback, 0.875 .. 0.999
;   p1 DAMP -> one-pole coefficient. s += c*(d-s), so a LARGE c keeps highs.
;              DAMP up lowers c: 0 = bright, 127 = dark.
;   p5 MIX  -> wet gain
; ---------------------------------------------------------------------------

init:
; No loop, and nothing reset that has to survive.
;
; Reading X:${ALLOC_PTR:x} is only valid HERE. Stash the base where process can
; find it: absolute Y, but at an address unique to this instance.
""" + ("" if BASE_MODE != "stash" else f"""        move    x:>${ALLOC_PTR:x},r4
        move    r7,a
        asr     #$8,a,a                 ; r7 >> 8; also fills the AGU slot
        move    x:(r4),x0               ; this instance's buffer base
        move    #>${STASH:x},y0
        add     y0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m0            ; both fill the AGU slot
        move    x0,y:(r5)
""") + f"""        move    #>$ffffff,m5
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        rts

proc:
; ---- this instance's buffer base ----------------------------------------
; X:${ALLOC_PTR:x} points at this instance's entry in the base table, but ONLY
; during init: the dispatcher advances it per effect, so by the time blocks are
; running it sits wherever the last init left it. With one effect loaded that
; happens to still be a valid FX2 slot, which is why reading it in process
; (v33) worked on one track and hung on two -- both instances then read the SAME
; entry and one of them wrote 14K words through memory it does not own.
;
; So read it in init and carry it across in the per-instance stash. See the
; STASH note above for why the address moved from 0x735 to 0x800.
;
; Deriving it instead as x:({ALLOC_TAB:#x} + ((r7 - {STATE_TAB:#x}) >> 8)) does not work:
; measured, r7 = 0x6200 while the base is table[1], not table[2].
""" + (f"""        move    #>${ALLOC_FIXED:x},x0            ; BASE HARDCODED -- bisect build
        move    #>$ffffff,m0            ; audio is read and written via r0
        move    #>${LINE_MASK:x},m1
        move    x0,x:(r7+$71)""" if BASE_MODE == "fixed" else f"""        move    x:>${ALLOC_PTR:x},r4
        move    #>$ffffff,m0            ; audio is read and written via r0
        move    #>${LINE_MASK:x},m1     ; both fill the AGU slot
        move    x:(r4),x0
        move    x0,x:(r7+$71)""" if BASE_MODE == "procread" else f"""        move    r7,a
        move    #>$ffffff,m0            ; audio is read and written via r0
        asr     #$8,a,a
        move    #>${STASH:x},y0
        add     y0,a
        move    a,r5
        move    #>${LINE_MASK:x},m1     ; both fill the AGU slot
        move    #>$ffffff,m5
        move    y:(r5),x0               ; the base init stashed for us
        move    x0,x:(r7+$71)""") + f"""

; ---- refuse to run on a slot that cannot hold the layout -----------------
; The bump allocator advances ONE entry per EFFECT, of any type, so which table
; entry we get depends on how many effects the project loaded before us -- not
; on how many reverbs. Of the eight entries only two can hold this layout:
;
;   0x1000 0x1c00 0x2800 0x3400   FX1 slots, 0xc00 words. A {STATE_OFF:#x}-word
;                                 layout here runs through the neighbouring
;                                 buffers and into FX2 slot 0.
;   0x4000 0x8000                 FX2 slots, 0x4000 words. The only safe ones.
;   0x30000 0x34000               past the end of Y, which stops at 0xC000.
;                                 dsp/ymemprobe.asm hangs when it writes there.
;
; So check, and pass audio through untouched if the slot is not ours. A dry
; track is a diagnosis; a hung machine is not. y0/b are used rather than x0/a
; because the block below needs x0 to still hold the base.
        move    x:(r7+$71),b
        move    #>${LINE_OFF + 0x4000:x},y0
        cmp     y0,b
        blt     dry
        move    #>${0xc000 - STATE_OFF + 1:x},y0
        cmp     y0,b
        bge     dry

; ---- every buffer base, derived once per block --------------------------
        move    #>${AP_OFF:x},a
        add     x0,a
        move    a,x:(r7+${APB:02x})
        move    #>${AP_OFF+AP_LEN:x},a
        add     x0,a
        move    a,x:(r7+${APB+1:02x})
        move    #>${AP_OFF+2*AP_LEN:x},a
        add     x0,a
        move    a,x:(r7+${APB+2:02x})
        move    #>${AP_OFF+3*AP_LEN:x},a
        add     x0,a
        move    a,x:(r7+${APB+3:02x})
        move    #>${LINE_OFF+MOD_LINES[0]*LINE_LEN:x},a
        add     x0,a
        move    a,x:(r7+$76)
        move    #>${LINE_OFF+MOD_LINES[1]*LINE_LEN:x},a
        add     x0,a
        move    a,x:(r7+$77)
        move    #>${PRE_OFF:x},a
        add     x0,a
        move    a,x:(r7+$78)

; ---- per-block: load the state that cannot be derived -------------------
; The LFO phase and the four one-pole states are the only things that must
; survive between calls and cannot be recomputed. They live in the instance's
; own Y region, so they are per-instance, and touching them once per block costs
; nothing per sample.
        move    #>${STATE_OFF:x},a
        add     x0,a
        move    a,x:(r7+$7f)            ; keep the address for the save
        move    a,r5
        move    #>$ffffff,m5            ; linear for the walk
        move    x:(r7+$71),x0           ; base again; fills the AGU slot after r5
        move    y:(r5)+,a
        move    a,{LFOPH}
        move    y:(r5)+,a
        move    a,{DAMP[0]}
        move    y:(r5)+,a
        move    a,{DAMP[1]}
        move    y:(r5)+,a
        move    a,{DAMP[2]}
        move    y:(r5)+,a
        move    a,{DAMP[3]}

; ---- rebuild the four delay pointers from the saved phase ----------------
        move    x:(r7+$83),a
        move    #>${LINE_MASK:x},x0
        and     x0,a                    ; mask on LOAD: the phase may be garbage
        move    x:(r7+$71),x0
        add     x0,a                    ; base + LINE_OFF({LINE_OFF:#x})
        move    a,r1                    ; line 0
        move    #>${LINE_LEN:x},x0
        add     x0,a
        move    a,r2                    ; line 1
        add     x0,a
        move    a,r3                    ; line 2
        add     x0,a
        move    a,r4                    ; line 3
        move    #>${LINE_MASK:x},m1
        move    #>${LINE_MASK:x},m2
        move    #>${LINE_MASK:x},m3
        move    #>${LINE_MASK:x},m4
"""
    if "size" in STAGES:
        body += f"""
    ; ---- SIZE: scale all four tap lengths -----------------------------------
    ; Each tap is held as a fraction of LINE_LEN (tap << 11), multiplied by a factor
    ; f = 0.125 .. 0.992, and shifted back to an integer. The nominal taps are the
    ; MAXIMUM, so SIZE only ever shrinks the space: {LINE_TAPS[0]} samples down to
    ; about {LINE_TAPS[0] // 8}, i.e. {LINE_TAPS[0]/44.1:.0f} ms down to {LINE_TAPS[0]/8/44.1:.0f} ms on the longest line.
    ; Setup only -- this runs once per block, not per sample.
            move    x:(r6+${P_SIZE}),x0
            move    #>$700000,y1
            mpy     x0,y1,a                 ; * 0.875 FIRST -- $100000 + $7f0000 is
            move    #>$100000,x0            ; $8f0000, which reads as NEGATIVE, and
            add     x0,a                    ; a negative f flips every tap
            move    a,x1                    ; f = 0.125 .. 0.995
    """
        for i, t in enumerate(LINE_TAPS):
            body += f"""        move    #>${t << 11:06x},x0            ; {t} as a fraction of {LINE_LEN}
            mpy     x0,x1,a
            asr     #$b,a,a                 ; back to an integer tap
    """
            if "mod" in STAGES and i in MOD_LINES:
                slot = 0x6a if i == MOD_LINES[0] else 0x6b
                body += f"""        move    #>${LINE_LEN:x},b
            sub     a,b                     ; {LINE_LEN} - tap, for the modulated read
            move    b,x:(r7+${slot:02x})
    """
            else:
                body += f"""        neg     a
            move    a,n{i+1}                    ; -tap, line {i} reads y:(r{i+1}+n{i+1})
    """
    else:
        # Every tap is a compile-time constant, so NOTHING a parameter can hold
        # reaches an N register. An N-register offset larger than the modulus is
        # undefined on the DSP56300 -- it is the one documented way to hang this
        # part instantly -- and with SIZE in the path a bad read of x:(r6+2) puts
        # an arbitrary value there. This build removes the mechanism rather than
        # clamping it, so a "runs" result is unambiguous.
        body += "\n; ---- fixed taps: no parameter reaches an address ------------------------\n"
        for i, t in enumerate(LINE_TAPS):
            if "mod" in STAGES and i in MOD_LINES:
                slot = 0x6a if i == MOD_LINES[0] else 0x6b
                body += f"""        move    #>${LINE_LEN - t:x},a
        move    a,x:(r7+${slot:02x})    ; {LINE_LEN} - {t}, for the modulated read
"""
            else:
                body += f"""        move    #>${(-t) & 0xffffff:06x},n{i+1}         ; -{t}, line {i} reads y:(r{i+1}+n{i+1})
"""

    m5_init = PRE_MASK if "pre" in STAGES else 0xffffff
    body += f"""        move    #>${m5_init:x},m5           ; pre-delay modulo. Harmless to the
                                        ; diffuser: it only ever does plain
                                        ; y:(r5), never a post-increment, and
                                        ; modulo affects updates, not reads.

; ---- feedback gain from TIME --------------------------------------------
; p0 arrives as value<<16. The 4x4 Hadamard has row norm 2, so folding the half
; into the gain makes the matrix orthonormal and the loop gain equal to g.
;
; g now spans 0.935..0.9995, not 0.875..0.999. Decay is g^n where n is passes,
; so RT60 scales with the loop time -- and fitting a real 16K allocation halved
; the mean tap from ~51 ms to ~26 ms, which halved every decay time and made
; TIME feel like it had stopped doing anything. g_new = g_old^0.5 restores the
; old RT60 range over the same knob travel.
        move    x:(r6),x0
        move    #>$043000,y1
        mpy     x0,y1,a
        move    #>$3bd000,x0
        add     x0,a
        move    a,x:(r7+$5e)

; ---- HI: high cut, as an EQ rather than a damping amount -----------------
; The one-pole is s += c*(d-s), so a LARGE c tracks the input and keeps highs.
; HI reads as an EQ control, so it has to run the other way from the old DAMP:
; HI=0 gives c=0.125 (dark), HI=127 gives c~0.99 (bright).
        move    x:(r6+${P_HI}),x0
        move    #>$700000,y1
        mpy     x0,y1,a
        move    #>$100000,x0
        add     x0,a
        move    a,x:(r7+$5f)

; ---- MIX -----------------------------------------------------------------
        move    x:(r6+${P_MIX}),x0
        move    x0,x:(r7+$60)

; ---- MOD: modulation depth, scales the LFO triangle ---------------------
        move    x:(r6+${P_MOD}),x0
        move    x0,x:(r7+$68)

; ---- WIDTH: 0 = mono, 127 = full stereo ---------------------------------
        move    x:(r6+${P_WIDTH:x}),x0
        move    x0,x:(r7+$6c)

; ---- RATE: LFO increment, ~0.34 Hz .. ~3 Hz -----------------------------
; 8x what it would be per sample, because the LFO is stepped once per block.
        move    x:(r6+${P_RATE:x}),a
        asr     #$b,a,a
        move    #>$200,x0
        add     x0,a
        move    a,x:(r7+$6f)

"""
    if "pre" in STAGES:
        body += f"""; ---- PRE: pre-delay in samples, 0 .. 2032 (46 ms) -----------------------
; v * 16. The scale MUST keep this below PRE_LEN ({PRE_LEN}): the read is
; y:(r5+n5) under m5 modulo, and a modulo offset larger than the buffer is
; undefined on the DSP56300. It does not wrap -- the read returns nothing, the
; tank gets no input, and the reverb goes completely silent.
        move    x:(r6+${P_PRE:x}),a
        asr     #$c,a,a
        move    a,x:(r7+$69)
        move    #>$1,x0                 ; the read happens BEFORE the write, so
        add     x0,a                    ; the offset is -(PRE+1): at PRE=0 that
        neg     a                       ; is one sample, not a whole buffer of
        move    a,n5                    ; staleness
        move    x:(r7+$83),a            ; the same counter again
        move    #>${PRE_MASK:x},x0
        and     x0,a
        move    x:(r7+$78),x0
        add     x0,a
        move    a,x:(r7+$70)            ; NOT $6d: the width matrix uses that
"""

    # The LFO runs ONCE PER BLOCK, not per sample. At 0.8 Hz it moves about
    # 0.0024 samples of delay per block, so stepping it 8 frames at a time is
    # inaudible -- and it buys back ~35 instructions a sample, which is the
    # difference between fitting in the frame budget and hanging the DSP.
    if "mod" in STAGES:
        body += lfo()
    body += f"""
        do      n7,>rvend

; ---- input: mono sum -----------------------------------------------------
        move    #>$1,n0
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$5b)
        move    r1,a                    ; the allpass phase IS the tank phase:
        move    #>${AP_MASK:x},x0       ; both advance by 1 a sample, and the
        and     x0,a                    ; line base is aligned, so r1 masked is it
        move    a,{PHASE}

"""
    if "pre" in STAGES:
        body += """; ---- pre-delay ----------------------------------------------------------
; r5 with m5 modulo and a plain post-increment -- the same shape as the tank
; lines, which are proven safe. The earlier version computed the addresses
; arithmetically like the diffuser does, which cost 28 instructions a sample;
; that is only necessary when r5 and n5 are RECOMPUTED inside the loop, and
; here they are set once per block.
        move    x:(r7+$70),r5           ; restore: the allpasses clobber r5
        move    x:(r7+$5b),a            ; input, and fills the AGU slot
        move    #>$1,n0
        move    y:(r5+n5),b             ; delayed
        move    a,y:(r5)+               ; write, and advance
        move    r5,x:(r7+$70)
        move    b,x:(r7+$5b)            ; delayed input -> the diffuser
"""
    body += ""
    if "diff" in STAGES:
        for i in range(4):
            body += allpass(i)
    body += f"""
        move    x:(r7+$5b),a
        move    a,x:(r7+$55)            ; diffused input -> tank
        asr     #$1,a,a
        move    a,x:(r7+$67)            ; and at half, for the other three lines
"""
    body += "\n; ---- four taps, damped inside the feedback path -------------------------\n"
    body += "        move    x:(r7+$5f),y0           ; damping coefficient, from DAMP\n"
    for i in range(4):
        body += tap(i) + "\n"
    body += """; ---- 4x4 Hadamard: adds and subtracts only ------------------------------
        move    x:(r7+$57),x0
        move    x:(r7+$56),a
        add     x0,a
        move    a,x:(r7+$5a)            ; u0 = d0+d1
        move    x:(r7+$56),a
        sub     x0,a
        move    a,x:(r7+$5b)            ; u1 = d0-d1
        move    x:(r7+$59),x0
        move    x:(r7+$58),a
        add     x0,a
        move    a,x:(r7+$5c)            ; u2 = d2+d3
        move    x:(r7+$58),a
        sub     x0,a
        move    a,x:(r7+$5d)            ; u3 = d2-d3

; ---- feedback and write back --------------------------------------------
        move    x:(r7+$5e),y0           ; g/2
"""
    # o0=u0+u2  o1=u1+u3  o2=u0-u2  o3=u1-u3
    for i, (hi, lo, op) in enumerate(((0x5c, 0x5a, "add"), (0x5d, 0x5b, "add"),
                                      (0x5c, 0x5a, "sub"), (0x5d, 0x5b, "sub"))):
        body += f"""        move    x:(r7+${hi:02x}),x0
        move    x:(r7+${lo:02x}),a
        {op}     x0,a
        move    a,x0
        mpy     x0,y0,a
"""
        if i in INJECT:
            op, slot = INJECT[i]
            body += f"""        move    x:(r7+${slot:02x}),x0           ; diffused input{'' if slot == IN_FULL else ', half'}
        {op}     x0,a
"""
        body += (f"        move    a,y:(r{i+1})+\n\n" if "lines" in STAGES else
                 f"        move    (r{i+1})+                 ; advance only -- nothing written\n\n")
    body += """; ---- wet added to dry, two tank taps per channel -------------------------
        move    x:(r7+$60),y1           ; wet gain
"""
    for taps, slot, label in ((OUT_L, 0x6d, "L"), (OUT_R, 0x6e, "R")):
        body += f"""        move    x:(r7+${0x56+taps[0]:02x}),a            ; line {taps[0]}, tap {LINE_TAPS[taps[0]]}
        move    x:(r7+${0x56+taps[1]:02x}),x0           ; line {taps[1]}, tap {LINE_TAPS[taps[1]]}
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+${slot:02x})            ; wet {label}
"""
    body += """
; ---- WIDTH: mid/side, then MIX, then onto the dry -----------------------
; M = (L+R)/2, S = (L-R)/2, out = M +/- w*S. w=0 collapses to mono, w=1 gives
; back exactly the two tap sums.
        move    x:(r7+$6d),a
        move    x:(r7+$6e),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$65)            ; M
        move    x:(r7+$6d),a
        sub     x0,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$6c),y0           ; WIDTH
        mpy     x0,y0,a
        move    a,x:(r7+$66)            ; w*S
        move    x:(r7+$65),a
        move    x:(r7+$66),x0
        add     x0,a
        move    a,x0
        mpy     x0,y1,a                 ; * MIX
        move    x:(r0),x0
        add     x0,a
        move    a,x:(r0)                ; L in place
        move    x:(r7+$65),a
        move    x:(r7+$66),x0
        sub     x0,a
        move    a,x0
        mpy     x0,y1,a
        move    x:(r0+n0),x0
        add     x0,a
        move    a,x:(r0+n0)             ; R in place
"""
    body += """        move    #>$2,n0
        move    (r0)+n0                 ; advance one stereo frame
rvend:

"""
    body += f"""; ---- per-block: write the underivable state back -------------------------
        move    x:(r7+$7f),r5
        move    #>$ffffff,m5
        move    {LFOPH},a               ; fills the AGU slot
        move    a,y:(r5)+
        move    {DAMP[0]},a
        move    a,y:(r5)+
        move    {DAMP[1]},a
        move    a,y:(r5)+
        move    {DAMP[2]},a
        move    a,y:(r5)+
        move    {DAMP[3]},a
        move    a,y:(r5)+
noloop:

; ---- save the phase, restore the M registers ---------------------------
        move    r1,a
"""
    body += f"""        move    #>${LINE_MASK:x},x0
        and     x0,a
        move    a,x:(r7+$83)
dry:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
"""
    sys.stdout.write(remap_slots(body))


if __name__ == "__main__":
    main()
