; ---------------------------------------------------------------------------
; reverb v6 -- v5 plus DAMP and MIX on the knobs
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
        move    #>$7ff,x0
        and     x0,a                    ; mask on LOAD: the phase may be garbage
        move    #>$800,x0
        add     x0,a
        move    a,r1                    ; line 0  Y:0x800
        move    #>$800,x0
        add     x0,a
        move    a,r2                    ; line 1  Y:0x1000
        add     x0,a
        move    a,r3                    ; line 2  Y:0x1800
        add     x0,a
        move    a,r4                    ; line 3  Y:0x2000
        move    #>$7ff,m1
        move    #>$7ff,m2
        move    #>$7ff,m3
        move    #>$7ff,m4
        move    #>$fff903,n1            ; -1789
        move    #>$fffa0d,n2            ; -1523
        move    #>$fffb4f,n3            ; -1201
        move    #>$fffc39,n4            ; -967
        move    r0,r5
        move    #>$ffffff,m0
        move    #>$ffffff,m5

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
        move    x:(r0)+,a
        move    x:(r0)+,x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$55)

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

        move    y:(r2+n2),a
        move    y:>$7f1,b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,y:>$7f1
        move    a,x:(r7+$57)

        move    y:(r3+n3),a
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
        move    x:(r5),x0               ; + dry
        add     x0,a
        move    a,x:(r5)+
        move    x:(r7+$59),a
        move    a,x0
        mpy     x0,y1,a
        move    x:(r5),x0
        add     x0,a
        move    a,x:(r5)+
rvend:

; ---- save the phase, restore the M registers ----------------------------
        move    r1,a
        move    #>$7ff,x0
        and     x0,a
        move    a,x:(r7+$83)
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
