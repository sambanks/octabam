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
    time. It goes silent at page 47, so 0x400..0xBFFF is real and 0x795..0xBFFF
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
import sys

# ---- memory ---------------------------------------------------------------
# Sized against the measured 0x400..0xBFFF. Everything here tops out at 0x6FFF,
# which leaves 0x7000..0xBFFF (20K words, 465 ms) for the pre-delay.
LINE_BASE = 0x1000          # four tank lines, contiguous, one per 0x1000
LINE_LEN  = 4096
LINE_TAPS = [3121, 2477, 1949, 1453]        # 71 / 56 / 44 / 33 ms, all prime

AP_BASE   = 0x5000          # four series allpasses, one per 0x800
AP_LEN    = 2048
AP_TAPS   = [1051, 773, 557, 379]           # 24 / 17.5 / 12.6 / 8.6 ms

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

PRE_BASE  = 0x8000          # pre-delay; 0x4000-ALIGNED so m5 modulo works
PRE_LEN   = 0x4000          # 16384 words = 371 ms
PRE_MASK  = PRE_LEN - 1

PHASE     = 0x7a1           # Y: shared allpass phase
LFOPH     = 0x7a2           # Y: LFO phase
PREPH     = 0x7a3           # Y: pre-delay phase
DAMPST    = 0x7f0           # Y: four one-pole states, 0x7f0..0x7f3

# ---- parameters -----------------------------------------------------------
# Layout follows Blackhole's primary page (Mix, Gravity, Feedback, Size, Lo, Hi)
# and Supermassive's core set, which agree on what belongs where. LO is the one
# gap: a low cut inside the feedback loop needs four more filter states and ~24
# instructions a sample, and the cycle headroom is not measured yet.
P_TIME, P_HI, P_SIZE, P_PRE, P_MOD, P_MIX, P_RATE, P_WIDTH = range(8)

LINE_MASK = LINE_LEN - 1
AP_MASK   = AP_LEN - 1


def neg24(n):
    return (-n) & 0xffffff


def allpass(i):
    base, tap = AP_BASE + i * AP_LEN, AP_TAPS[i]
    return f"""
; -- allpass {i}: Y:{base:#07x}, tap {tap} ({tap/44.1:.1f} ms) --
        move    y:>${PHASE:x},a
        move    #>{AP_LEN - tap},x0
        add     x0,a
        move    #>${AP_MASK:x},x0
        and     x0,a                    ; (phase - tap) mod {AP_LEN}
        move    #>${base:x},x0
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
        move    y:>${PHASE:x},a         ; write v at base + phase
        move    #>${base:x},x0
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
        move    y:>${LFOPH:x},a         ; persistent phase, [0,$7fffff]
        move    x:(r7+$6f),x0           ; increment, from RATE
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap; A1 is right even if A2 carried
        move    a1,x0                   ; extract without saturating on A2
        move    x0,y:>${LFOPH:x}
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
    base, tap = LINE_BASE + i * LINE_LEN, LINE_TAPS[i]
    return f"""; -- line {i} modulated: Y:{base:#07x}, tap {tap}, interpolated --
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
        move    #>${base:x},x0
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
    if i == MOD_LINES[0]:
        head = modread(i, 0x61, 0x62)
    elif i == MOD_LINES[1]:
        head = modread(i, 0x63, 0x64)
    else:
        head = f"        move    y:(r{i+1}+n{i+1}),a         ; line {i}, fixed tap {LINE_TAPS[i]}\n"
    return head + f"""        move    y:>${DAMPST+i:x},b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,y:>${DAMPST+i:x}
        move    a,x:(r7+${0x56+i:02x})
"""


def main():
    tail_ms = LINE_LEN / 44.1
    body = f"""; ---------------------------------------------------------------------------
; {sys.argv[1] if len(sys.argv) > 1 else 'reverb'} -- generated by tools/gen_reverb.py, do not hand-edit
;
; Four series allpasses into a four-line FDN with a 4x4 Hadamard, one-pole
; damping inside the feedback path, and interpolated modulation on two lines.
;
; Sized against the measured end of Y memory at 0xC000:
;   lines      Y:{LINE_BASE:#07x} .. {LINE_BASE + 4*LINE_LEN - 1:#07x}   {LINE_LEN} words each ({tail_ms:.0f} ms)
;              taps {' '.join(str(t) for t in LINE_TAPS)}  ({' '.join(f'{t/44.1:.0f}' for t in LINE_TAPS)} ms)
;   allpasses  Y:{AP_BASE:#07x} .. {AP_BASE + 4*AP_LEN - 1:#07x}   {AP_LEN} words each
;              taps {' '.join(str(t) for t in AP_TAPS)}  ({' '.join(f'{t/44.1:.0f}' for t in AP_TAPS)} ms)
;   free       Y:0x7000 .. 0xBFFF  (20K words, 465 ms) for the pre-delay
;
; The allpasses are long on purpose. Four lines at ~50 ms is only ~80 echoes a
; second, which on its own reads as a stutter rather than a wash; the density
; has to come from diffusion, so the allpasses run 9-24 ms instead of the 3-8 ms
; they were when the whole engine had to fit in 6K.
;
; State:
;   r7+$83        write phase (persistent, masked on load as well as save)
;   Y:{PHASE:#05x}        shared allpass phase
;   Y:{LFOPH:#05x}        LFO phase
;   Y:{DAMPST:#05x}..{DAMPST+3:#05x}  damping states
;   r7+$55..$66   per-sample scratch
;
; Parameters:
;   p0 TIME -> feedback, 0.875 .. 0.999
;   p1 DAMP -> one-pole coefficient. s += c*(d-s), so a LARGE c keeps highs.
;              DAMP up lowers c: 0 = bright, 127 = dark.
;   p5 MIX  -> wet gain
; ---------------------------------------------------------------------------

init:
; No loop, and nothing reset that has to survive: this runs far more often than
; once per effect selection.
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts

proc:
; ---- rebuild the four delay pointers from the saved phase ----------------
        move    x:(r7+$83),a
        move    #>${LINE_MASK:x},x0
        and     x0,a                    ; mask on LOAD: the phase may be garbage
        move    #>${LINE_LEN:x},x0
        add     x0,a
        move    a,r1                    ; line 0  Y:{LINE_BASE:#07x}
        add     x0,a
        move    a,r2                    ; line 1  Y:{LINE_BASE+LINE_LEN:#07x}
        add     x0,a
        move    a,r3                    ; line 2  Y:{LINE_BASE+2*LINE_LEN:#07x}
        add     x0,a
        move    a,r4                    ; line 3  Y:{LINE_BASE+3*LINE_LEN:#07x}
        move    #>${LINE_MASK:x},m1
        move    #>${LINE_MASK:x},m2
        move    #>${LINE_MASK:x},m3
        move    #>${LINE_MASK:x},m4
"""
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
        if i in MOD_LINES:
            slot = 0x6a if i == MOD_LINES[0] else 0x6b
            body += f"""        move    #>${LINE_LEN:x},b
        sub     a,b                     ; {LINE_LEN} - tap, for the modulated read
        move    b,x:(r7+${slot:02x})
"""
        else:
            body += f"""        neg     a
        move    a,n{i+1}                    ; -tap, line {i} reads y:(r{i+1}+n{i+1})
"""
    body += f"""        move    #>$ffffff,m0            ; audio read AND written in place via r0
        move    #>${PRE_MASK:x},m5           ; pre-delay modulo. Harmless to the
                                        ; diffuser: it only ever does plain
                                        ; y:(r5), never a post-increment, and
                                        ; modulo affects updates, not reads.

; ---- feedback gain from TIME --------------------------------------------
; p0 arrives as value<<16. g/2 spans 0.4375..0.4995, so g spans 0.875..0.999.
; The 4x4 Hadamard has row norm 2, so folding the half into the gain makes the
; matrix orthonormal and the loop gain equal to g.
        move    x:(r6),x0
        move    #>$080000,y1
        mpy     x0,y1,a
        move    #>$380000,x0
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
        move    x:(r6+${P_WIDTH}),x0
        move    x0,x:(r7+$6c)

; ---- RATE: LFO increment, ~0.34 Hz .. ~3 Hz -----------------------------
; 8x what it would be per sample, because the LFO is stepped once per block.
        move    x:(r6+${P_RATE}),a
        asr     #$b,a,a
        move    #>$200,x0
        add     x0,a
        move    a,x:(r7+$6f)

; ---- PRE: pre-delay in samples, 0 .. 16256 (369 ms) ----------------------
; v * 128, not v * 256: the buffer is 16384 words, and 127*256 = 32512 would
; overrun it. The mask would then wrap the top half of the knob back round to
; short delays instead of clamping.
        move    x:(r6+${P_PRE}),a
        asr     #$9,a,a
        move    a,x:(r7+$69)
        move    #>$1,x0                 ; the read happens BEFORE the write, so
        add     x0,a                    ; the offset is -(PRE+1): at PRE=0 that
        neg     a                       ; is one sample, not a whole buffer of
        move    a,n5                    ; staleness
        move    y:>${PREPH:x},a         ; rebuild the pre-delay pointer
        move    #>${PRE_MASK:x},x0
        and     x0,a
        move    #>${PRE_BASE:x},x0
        add     x0,a
        move    a,x:(r7+$70)            ; NOT $6d: the width matrix uses that
"""

    # The LFO runs ONCE PER BLOCK, not per sample. At 0.8 Hz it moves about
    # 0.0024 samples of delay per block, so stepping it 8 frames at a time is
    # inaudible -- and it buys back ~35 instructions a sample, which is the
    # difference between fitting in the frame budget and hanging the DSP.
    body += lfo()
    body += """
        do      n7,>rvend

; ---- input: mono sum -----------------------------------------------------
        move    #>$1,n0
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$5b)

; ---- pre-delay ----------------------------------------------------------
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
    for i in range(4):
        body += allpass(i)
    body += f"""
        move    y:>${PHASE:x},a         ; advance the shared allpass phase
        move    #>$1,x0
        add     x0,a
        move    #>${AP_MASK:x},x0
        and     x0,a
        move    a,y:>${PHASE:x}
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
        body += f"        move    a,y:(r{i+1})+\n\n"
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
    body += f"""; ---- save the phases, restore the M registers ---------------------------
        move    x:(r7+$70),a
        move    #>${PRE_MASK:x},x0
        and     x0,a
        move    a,y:>${PREPH:x}
        move    r1,a
"""
    body += f"""        move    #>${LINE_MASK:x},x0
        and     x0,a
        move    a,x:(r7+$83)
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
"""
    sys.stdout.write(body)


if __name__ == "__main__":
    main()
