; ---------------------------------------------------------------------------
; reverb v15 -- four allpass stages + interpolated tank modulation
;
; v14 (four stages) runs and is a clear improvement. Modulation goes on in the
; same explicit-addressing style: no modulo, no N register, addresses computed
; arithmetically and masked. The v8 modulation hung because it recomputed r/n
; pairs with modulo inside the sample loop -- the same fault as the diffuser.
;
; LFO: a triangle from a persistent 23-bit phase at Y:0x7a2, ~0.8 Hz. Depth is
; a plain `asl #4` of the triangle, so the accumulator's extension byte holds
; the integer sample offset (0..8) and A1 holds the fraction -- no shift chain.
; Lines 1 and 2 get the triangle and its inverse, so they move in opposite
; directions and stay decorrelated for one LFO's worth of work.
;
; Each modulated tap reads d0 and d1 at adjacent indices and interpolates:
;   d = d0 + f*(d1 - d0)
; Lines 0 (the injected one) and 3 are left unmodulated for stability.
;
; v13 (two stages, addresses computed arithmetically) RUNS. The fault was the
; allpasses using modulo addressing with r5/n5 recomputed inside the sample loop;
; the delay lines work because theirs are set once in the per-block setup and only
; post-increment. Stage count was never the issue -- v11 proved that with two.
;
; v11 (two stages) and v12 (m5 hoisted out of the loop) both hang exactly as v9
; (four stages) does. Stage count is irrelevant, so it is not cycles, and m5
; placement is not it either. What remains is that the allpasses recompute r5 and
; n5 inside the loop and lean on modulo addressing, while the delay lines -- which
; work -- set r1-r4/n1-n4/m1-m4 once in the per-block setup.
;
; So the diffuser now computes its addresses arithmetically and reads and writes
; with plain y:(r5). No modulo, no N offset, m5 left linear. Costs about 20
; instructions per stage instead of 12, and removes the AGU from the picture.
;
;   lines      Y:0x800 0xc00 0x1000 0x1400   1024 words, taps 967/811/613/439
;   allpasses  Y:0x1800 0x1a00 0x1c00 0x1e00  512 words, taps 142/107/379/277
;   lines      Y:0x800 0xc00 0x1000 0x1400    1024 words, taps 967/811/613/439
;   Y:0x7a1 allpass phase   Y:0x7a2 LFO phase   Y:0x7f0-3 damping
;
; v6 runs. v9 (diffusion, no modulation) hangs. Two things separate them: the
; diffusion itself, and the audio moving from a separate write pointer in r5 to
; in-place through r0 -- which the diffuser forces, because it needs r5.
;
; v10 is v6 with just the r0 change and nothing else.
;   runs  -> the diffusion is at fault
;   hangs -> the r0 handling is
;
; v1-v4 used four 4096-word lines in self-chosen X memory with state in the r7
; block at +$50. None of that works on hardware. What does, established by
; probe:
;
;   * delay buffers live in Y memory (DARK REV: 103 y: instructions, and it
;     never loads an address above 0x200 into an address register)
;   * Y:0x800+ is usable -- an echo at Y:0x800-0xfff with tap 1376 works
;   * persistent state goes in r7+$83, which DARK read-modify-writes across
;     frames; r7+$50 does NOT survive, nor does absolute X:0x9000
;   * init must not loop -- any bulk work there stalls the frame
;   * M registers must be restored before returning
;   * the phase must be masked on load as well as on save
;
; Structure is unchanged from v4 in intent, resized to what the hardware gives:
;   4 delay lines, 2048 words each, Y:0x800 / 0x1000 / 0x1800 / 0x2000
;   taps 1789 1523 1201 967 (prime, so the modes do not stack)
;   one-pole damping inside the feedback path -> bright, not dark
;   4x4 Hadamard, g/2 folded into the feedback so the matrix is orthonormal
;   input injected into ONE line, output taken from two others -> bloom
;
; State:
;   r7+$83        write phase        (persistent, proven)
;   Y:0x7f0..7f3  damping states     (just below the buffers; if these do not
;                                     persist the damping merely resets, which
;                                     is not fatal)
;   r7+$55..$5d   per-sample scratch (nothing else runs mid-call)
;
; Parameters:
;   p0 TIME -> feedback        (0.875 .. 0.999)
;   p1 DAMP -> damping coefficient. The one-pole is s += c*(d-s), so a LARGE c
;              tracks the input closely and keeps highs, a small c rolls them
;              off. DAMP up therefore lowers c: 0 = bright, 127 = dark.
;   p5 MIX  -> wet gain. Was unity, so the wet always sat on top of the dry.
; ---------------------------------------------------------------------------

init:
; No loop. Any bulk work here stalls the audio frame.
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
        move    #>$3ff,x0
        and     x0,a                    ; mask on LOAD: the phase may be garbage
        move    #>$800,x0
        add     x0,a
        move    a,r1                    ; line 0  Y:0x800
        move    #>$400,x0
        add     x0,a
        move    a,r2                    ; line 1  Y:0x1000
        add     x0,a
        move    a,r3                    ; line 2  Y:0x1800
        add     x0,a
        move    a,r4                    ; line 3  Y:0x2000
        move    #>$3ff,m1
        move    #>$3ff,m2
        move    #>$3ff,m3
        move    #>$3ff,m4
        move    #>$fffc39,n1            ; -967
        move    #>$fffcd5,n2            ; -811
        move    #>$fffd9b,n3            ; -613
        move    #>$fffe49,n4            ; -439
        move    #>$ffffff,m0            ; audio read AND written in place via r0

; ---- feedback gain from TIME --------------------------------------------
; p0 arrives as value<<16 = v/128 as a fraction. g/2 spans 0.4375..0.4995,
; so g spans 0.875..0.999. The 4x4 Hadamard has row norm 2, so folding the
; half into the gain makes the matrix orthonormal and the loop gain equal g.
        move    x:(r6),x0
        move    #>$080000,y1
        mpy     x0,y1,a
        move    #>$380000,x0
        add     x0,a
        move    a,x:(r7+$5e)            ; g/2 for this block

; ---- DAMP: p1 -> damping coefficient ------------------------------------
        move    x:(r6+$1),x0
        move    #>$700000,y1
        mpy     x0,y1,a
        move    #>$7fffff,b
        sub     a,b                     ; c = 0x7fffff - p1*0.875
        move    b,x:(r7+$5f)

; ---- MIX: p5 -> wet gain ------------------------------------------------
        move    x:(r6+$5),x0
        move    x0,x:(r7+$60)

        do      n7,>rvend

; ---- input: mono sum -----------------------------------------------------
        move    #>$1,n0
        move    x:(r0),a                ; L
        move    x:(r0+n0),x0            ; R
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$5b)            ; into the diffuser

; -- allpass 0x1800, tap 142: addresses computed, no modulo, no N --
        move    y:>$7a1,a               ; phase
        move    #>370,x0
        add     x0,a
        move    #>$1ff,x0
        and     x0,a                    ; (phase - tap) mod 512
        move    #>$1800,x0
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
        move    y:>$7a1,a               ; write v at base + phase
        move    #>$1800,x0
        add     x0,a
        move    a,r5
        move    x:(r7+$5c),a            ; reload v, fills the AGU slot
        move    a,y:(r5)

; -- allpass 0x1a00, tap 107: addresses computed, no modulo, no N --
        move    y:>$7a1,a               ; phase
        move    #>405,x0
        add     x0,a
        move    #>$1ff,x0
        and     x0,a                    ; (phase - tap) mod 512
        move    #>$1a00,x0
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
        move    y:>$7a1,a               ; write v at base + phase
        move    #>$1a00,x0
        add     x0,a
        move    a,r5
        move    x:(r7+$5c),a            ; reload v, fills the AGU slot
        move    a,y:(r5)

; -- allpass 0x1c00, tap 379: addresses computed, no modulo, no N --
        move    y:>$7a1,a               ; phase
        move    #>133,x0
        add     x0,a
        move    #>$1ff,x0
        and     x0,a                    ; (phase - tap) mod 512
        move    #>$1c00,x0
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
        move    y:>$7a1,a               ; write v at base + phase
        move    #>$1c00,x0
        add     x0,a
        move    a,r5
        move    x:(r7+$5c),a            ; reload v, fills the AGU slot
        move    a,y:(r5)

; -- allpass 0x1e00, tap 277: addresses computed, no modulo, no N --
        move    y:>$7a1,a               ; phase
        move    #>235,x0
        add     x0,a
        move    #>$1ff,x0
        and     x0,a                    ; (phase - tap) mod 512
        move    #>$1e00,x0
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
        move    y:>$7a1,a               ; write v at base + phase
        move    #>$1e00,x0
        add     x0,a
        move    a,r5
        move    x:(r7+$5c),a            ; reload v, fills the AGU slot
        move    a,y:(r5)

        move    y:>$7a1,a               ; advance the shared allpass phase
        move    #>$1,x0
        add     x0,a
        move    #>$1ff,x0
        and     x0,a
        move    a,y:>$7a1
        move    x:(r7+$5b),a
        move    a,x:(r7+$55)            ; diffused input -> tank


; ---- LFO: one triangle, and its inverse, split into integer + fraction ---
        move    y:>$7a2,a               ; persistent phase, [0,0x7fffff]
        move    #>$0000a0,x0            ; ~0.8 Hz at 44.1k
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap; A1 is right even if A2 carried
        move    a1,x0                   ; extract without saturating on A2
        move    x0,y:>$7a2
        move    x0,a                    ; clean copy, A2 = 0
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle, 0 .. 0.5
        move    #>$400000,b
        move    a,x1
        move    x1,x0
        sub     x0,b                    ; inverse triangle, 0.5 .. 0
        asl     #$4,a,a                 ; A2 = integer samples, A1 = fraction
        asl     #$4,b,b
        move    a2,x0
        move    x0,x:(r7+$61)           ; line 1 integer offset
        move    a1,x0
        move    x0,x:(r7+$62)           ; line 1 fraction
        move    b2,x0
        move    x0,x:(r7+$63)           ; line 2 integer offset
        move    b1,x0
        move    x0,x:(r7+$64)           ; line 2 fraction

; ---- four taps, damped inside the feedback path -------------------------
        move    x:(r7+$5f),y0           ; damping coefficient, from DAMP
        move    y:(r1+n1),a
        move    y:>$7f0,b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,y:>$7f0
        move    a,x:(r7+$56)

; -- line 1  Y:0xc00 tap 811: interpolated read, addresses computed, no modulo, no N --
        move    r1,b
        move    #>$3ff,x0
        and     x0,b                    ; shared write phase
        move    x:(r7+$61),x0
        sub     x0,b                    ; phase - offset
        move    #>213,x0
        add     x0,b
        move    #>$3ff,x0
        and     x0,b                    ; i0
        move    b,a
        add     x0,a
        and     x0,a                    ; i1 = (i0-1) & 0x3ff
        move    #>$c00,x0
        add     x0,b
        add     x0,a
        move    a,x1
        move    b,r5
        move    x:(r7+$62),y0     ; fraction, and fills the AGU slot
        move    x1,a
        move    y:(r5),b                ; d0
        move    a,r5
        move    b,x:(r7+$65)
        move    b,x0                    ; both fill the AGU slot
        move    y:(r5),a                ; d1
        sub     x0,a
        move    a,x0
        mpy     x0,y0,a                 ; f*(d1-d0)
        move    x:(r7+$65),x0
        add     x0,a                    ; interpolated tap
        move    y:>$7f1,b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,y:>$7f1
        move    a,x:(r7+$57)

; -- line 2  Y:0x1000 tap 613: interpolated read, addresses computed, no modulo, no N --
        move    r1,b
        move    #>$3ff,x0
        and     x0,b                    ; shared write phase
        move    x:(r7+$63),x0
        sub     x0,b                    ; phase - offset
        move    #>411,x0
        add     x0,b
        move    #>$3ff,x0
        and     x0,b                    ; i0
        move    b,a
        add     x0,a
        and     x0,a                    ; i1 = (i0-1) & 0x3ff
        move    #>$1000,x0
        add     x0,b
        add     x0,a
        move    a,x1
        move    b,r5
        move    x:(r7+$64),y0     ; fraction, and fills the AGU slot
        move    x1,a
        move    y:(r5),b                ; d0
        move    a,r5
        move    b,x:(r7+$65)
        move    b,x0                    ; both fill the AGU slot
        move    y:(r5),a                ; d1
        sub     x0,a
        move    a,x0
        mpy     x0,y0,a                 ; f*(d1-d0)
        move    x:(r7+$65),x0
        add     x0,a                    ; interpolated tap
        move    y:>$7f2,b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,y:>$7f2
        move    a,x:(r7+$58)

        move    y:(r4+n4),a
        move    y:>$7f3,b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,y:>$7f3
        move    a,x:(r7+$59)

; ---- 4x4 Hadamard: adds and subtracts only ------------------------------
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

; ---- feedback and write back; input into line 0 only --------------------
        move    x:(r7+$5e),y0           ; g/2
        move    x:(r7+$5c),x0
        move    x:(r7+$5a),a
        add     x0,a
        move    a,x0
        mpy     x0,y0,a
        move    x:(r7+$55),x0           ; mono in -- one line only -> slow bloom
        add     x0,a
        move    a,y:(r1)+

        move    x:(r7+$5d),x0
        move    x:(r7+$5b),a
        add     x0,a
        move    a,x0
        mpy     x0,y0,a
        move    a,y:(r2)+

        move    x:(r7+$5c),x0
        move    x:(r7+$5a),a
        sub     x0,a
        move    a,x0
        mpy     x0,y0,a
        move    a,y:(r3)+

        move    x:(r7+$5d),x0
        move    x:(r7+$5b),a
        sub     x0,a
        move    a,x0
        mpy     x0,y0,a
        move    a,y:(r4)+

; ---- wet added to dry, from lines 1 and 3 (not the injected line) --------
        move    x:(r7+$60),y1           ; wet gain
        move    x:(r7+$57),a
        move    a,x0
        mpy     x0,y1,a                 ; wet * MIX
        move    x:(r0),x0               ; + dry
        add     x0,a
        move    a,x:(r0)                ; L in place
        move    x:(r7+$59),a
        move    a,x0
        mpy     x0,y1,a
        move    x:(r0+n0),x0
        add     x0,a
        move    a,x:(r0+n0)             ; R in place
        move    #>$2,n0
        move    (r0)+n0                 ; advance one stereo frame
rvend:

; ---- save the phase, restore the M registers ----------------------------
        move    r1,a
        move    #>$3ff,x0
        and     x0,a
        move    a,x:(r7+$83)
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
