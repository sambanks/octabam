; ---------------------------------------------------------------------------
; reverb v4 -- longer lines, later output taps, TIME on the knob
;
; Brief: long smooth tails, bright but not harsh, slow bloom.
;
;   long tails   high feedback AND long lines. Decay per pass is set by
;                feedback, but decay per SECOND also depends on how long a pass
;                takes, so doubling the delays roughly doubles RT60 for the same
;                gain. Lines are now 4096 words with taps 1867..3271 (42-74 ms).
;   slow bloom   the output is taken from lines 1 and 3, NOT the line the input
;                is injected into. Energy has to traverse the matrix before it
;                reaches the outputs, so the tail arrives rather than starts.
;   smooth       coprime taps PLUS a 4-stage allpass diffuser on the input,
;                which is what turns a handful of discrete echoes into a wash,
;                PLUS fractional-delay modulation on two tank lines. Diffusion
;                fixes density; it does not move the tank's modes, which is what
;                is heard as metallic. Slowly detuning two of the four delays
;                smears the modes so no fixed resonance can establish itself.
;                Interpolated, not integer-stepped: whole-sample jumps inside a
;                feedback loop click.
;   bright       one-pole damping INSIDE the loop, light, so highs decay
;                gradually rather than being filtered off at the input the way
;                the stock reverbs do
;
; v2 adds the input diffusion. Four series allpasses smear the input before it
; reaches the tank, so the early response is dense instead of four discrete
; echoes -- the single biggest factor in whether a small FDN sounds like a room
; or like a comb filter.
;
;   ap0  X:0xb000  tap 142      ap2  X:0xb400  tap 379
;   ap1  X:0xb200  tap 107      ap3  X:0xb600  tap 277
;
; 512-word buffers, one shared phase. r5 is borrowed for each allpass in turn
; and then reused as the audio write pointer, since r1-r4 are the delay lines.
;
; Buffers are in the free region confirmed on hardware (X:0x08d98-0x0ffff), so
; nothing the stock effects use is disturbed:
;
;   line 0  X:0x9000  tap 1789      line 2  X:0xa000  tap 1201
;   line 1  X:0x9800  tap 1523      line 3  X:0xa800  tap  967
;
; 2048-word power-of-2 buffers so modulo addressing costs one M register each;
; the tap is a negative N offset from the write pointer, which is how you take
; an arbitrary delay out of a power-of-2 buffer.
;
; The ABI fixes r0 (audio), r6 (params), r7 (state), leaving r1-r4 for the delay
; lines and r5 for the audio write pointer. Everything else spills to state.
;
; State at r7+$50:
;   +$50..53  damping filter state      +$56..59  damped taps d0..d3
;   +$54      write phase (persists)    +$5a..5d  Hadamard intermediates
;   +$55      diffused input     +$5e  allpass stage signal
;                                      +$5f  allpass phase
;   +$61,62   two slow LFO phases, different rates so the lines decorrelate
; ---------------------------------------------------------------------------

init:
        move    #>$9000,r1
        move    #>$ffff,m1              ; linear addressing for the clear
        move    #>$4800,x0              ; 4x4096 lines + 4x512 allpasses, contiguous
        clr     a
        do      x0,>iclr
        move    a,x:(r1)+
iclr:
        clr     a
        move    a,x:(r7+$50)
        move    a,x:(r7+$51)
        move    a,x:(r7+$52)
        move    a,x:(r7+$53)
        move    a,x:(r7+$54)            ; write phase
        move    a,x:(r7+$5f)            ; allpass phase
        move    a,x:(r7+$61)            ; LFO A
        move    a,x:(r7+$62)            ; LFO B
        rts

proc:
; ---- rebuild delay pointers from the saved phase -------------------------
; r1-r4 do not survive between calls, so the phase lives in state. Each base is
; 2048-aligned, so M=$7ff wraps inside its own buffer.
        move    x:(r7+$54),a
        move    #>$9000,x0
        add     x0,a
        move    a,r1
        move    #>$1000,x0
        add     x0,a
        move    a,r2
        add     x0,a
        move    a,r3
        add     x0,a
        move    a,r4
        move    #>$fff,m1
        move    #>$fff,m2
        move    #>$fff,m3
        move    #>$fff,m4
        move    #>$fff339,n1            ; -3271
        move    #>$fff527,n2            ; -2777
        move    #>$fff6f9,n3            ; -2311
        move    #>$fff8b5,n4            ; -1867
        move    #>$ffff,m0              ; audio pointer is linear
        move    #>$1ff,m5               ; allpass buffers are 512 words

        do      n7,>rvend

; ---- input: mono sum ------------------------------------------------------
        move    #>$1,n0
        move    x:(r0),a                ; L
        move    x:(r0+n0),x0            ; R  -- read in place, written back below
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$5e)            ; stage signal into the diffuser

; ---- 4-stage allpass input diffusion -------------------------------------
; each stage:  v = x + g*d ;  out = d - g*v ;  store v
; r5 is borrowed per stage, then reused below as the audio write pointer.
        move    #>$400000,y0            ; allpass coefficient

        move    x:(r7+$5f),a
        move    #>$d000,x0
        add     x0,a
        move    a,r5
        move    #>$ffff72,n5   ; tap 142
        move    x:(r5+n5),b
        move    b,x0
        mpy     x0,y0,a
        move    x:(r7+$5e),x0
        add     x0,a                    ; v
        move    a,x:(r5)+
        move    a,x1
        mpy     x1,y0,a                 ; g*v
        sub     a,b                     ; d - g*v
        move    b,x:(r7+$5e)

        move    x:(r7+$5f),a
        move    #>$d200,x0
        add     x0,a
        move    a,r5
        move    #>$ffff95,n5   ; tap 107
        move    x:(r5+n5),b
        move    b,x0
        mpy     x0,y0,a
        move    x:(r7+$5e),x0
        add     x0,a                    ; v
        move    a,x:(r5)+
        move    a,x1
        mpy     x1,y0,a                 ; g*v
        sub     a,b                     ; d - g*v
        move    b,x:(r7+$5e)

        move    x:(r7+$5f),a
        move    #>$d400,x0
        add     x0,a
        move    a,r5
        move    #>$fffe85,n5   ; tap 379
        move    x:(r5+n5),b
        move    b,x0
        mpy     x0,y0,a
        move    x:(r7+$5e),x0
        add     x0,a                    ; v
        move    a,x:(r5)+
        move    a,x1
        mpy     x1,y0,a                 ; g*v
        sub     a,b                     ; d - g*v
        move    b,x:(r7+$5e)

        move    x:(r7+$5f),a
        move    #>$d600,x0
        add     x0,a
        move    a,r5
        move    #>$fffeeb,n5   ; tap 277
        move    x:(r5+n5),b
        move    b,x0
        mpy     x0,y0,a
        move    x:(r7+$5e),x0
        add     x0,a                    ; v
        move    a,x:(r5)+
        move    a,x1
        mpy     x1,y0,a                 ; g*v
        sub     a,b                     ; d - g*v
        move    b,x:(r7+$5e)

        move    x:(r7+$5f),a            ; advance the shared allpass phase
        move    #>$1,x0
        add     x0,a
        move    #>$1ff,x0
        and     x0,a
        move    a,x:(r7+$5f)
        move    x:(r7+$5e),a
        move    a,x:(r7+$55)            ; diffused input -> tank injection

; ---- four taps, each damped inside the feedback path ---------------------
; one-pole: s += c*(d-s), c light so the tail stays bright
        move    #>$600000,y0            ; damping coefficient
; --- modulated tap: LFO -> triangle -> integer + fractional delay ---
        move    x:(r7+$61),a
        move    #>$110,x0
        add     x0,a
        move    a,x:(r7+$61)
        move    x:(r7+$61),a       ; reload: 24-bit, sign-extended
        abs     a                       ; sawtooth -> triangle
        move    a,x1
        asr     #$13,a,a                ; integer part, 0..15 samples
        move    #>3271,b
        add     a,b
        neg     b
        move    b,n1                    ; -(tap + int)
        move    x1,a
        asl     #$5,a,a                 ; remaining bits = the fraction
        move    a,y1
        move    x:(r1+n1),a             ; s0
        move    n1,b
        dec     b
        move    b,n1
        move    x:(r1+n1),b             ; s1, one sample older
        sub     a,b
        move    b,x0
        mpy     x0,y1,b                 ; frac * (s1-s0)
        add     b,a                     ; linear interpolation
        move    x:(r7+$50),b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$50)
        move    a,x:(r7+$56)

        move    x:(r2+n2),a
        move    x:(r7+$51),b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$51)
        move    a,x:(r7+$57)

; --- modulated tap: LFO -> triangle -> integer + fractional delay ---
        move    x:(r7+$62),a
        move    #>$d7,x0
        add     x0,a
        move    a,x:(r7+$62)
        move    x:(r7+$62),a       ; reload: 24-bit, sign-extended
        abs     a                       ; sawtooth -> triangle
        move    a,x1
        asr     #$13,a,a                ; integer part, 0..15 samples
        move    #>2311,b
        add     a,b
        neg     b
        move    b,n3                    ; -(tap + int)
        move    x1,a
        asl     #$5,a,a                 ; remaining bits = the fraction
        move    a,y1
        move    x:(r3+n3),a             ; s0
        move    n3,b
        dec     b
        move    b,n3
        move    x:(r3+n3),b             ; s1, one sample older
        sub     a,b
        move    b,x0
        mpy     x0,y1,b                 ; frac * (s1-s0)
        add     b,a                     ; linear interpolation
        move    x:(r7+$52),b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$52)
        move    a,x:(r7+$58)

        move    x:(r4+n4),a
        move    x:(r7+$53),b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$53)
        move    a,x:(r7+$59)

; ---- 4x4 Hadamard -- adds and subtracts only, no multiplies --------------
;   u0=d0+d1  u1=d0-d1  u2=d2+d3  u3=d2-d3
        move    x:(r7+$57),x0
        move    x:(r7+$56),a
        add     x0,a
        move    a,x:(r7+$5a)            ; u0
        move    x:(r7+$56),a
        sub     x0,a
        move    a,x:(r7+$5b)            ; u1
        move    x:(r7+$59),x0
        move    x:(r7+$58),a
        add     x0,a
        move    a,x:(r7+$5c)            ; u2
        move    x:(r7+$58),a
        sub     x0,a
        move    a,x:(r7+$5d)            ; u3

; ---- feedback and write back; input injected into line 0 only ------------
; feedback from the TIME knob. p0 arrives as value<<16, i.e. v/128 as a
; fraction, so g/2 spans 0.4375..0.4995 -> g 0.875..0.999.
        move    x:(r6),x0               ; p0 = TIME
        move    #>$080000,y0
        mpy     x0,y0,a
        move    #>$380000,x0
        add     x0,a
        move    a,y0                    ; g/2 (H/2 is orthonormal, loop gain = g)

        move    x:(r7+$5c),x0
        move    x:(r7+$5a),a
        add     x0,a                    ; o0 = u0+u2
        move    a,x0
        mpy     x0,y0,a
        move    x:(r7+$55),x0           ; mono in -- ONE line only = slow bloom
        add     x0,a
        move    a,x:(r1)+

        move    x:(r7+$5d),x0
        move    x:(r7+$5b),a
        add     x0,a                    ; o1 = u1+u3
        move    a,x0
        mpy     x0,y0,a
        move    a,x:(r2)+

        move    x:(r7+$5c),x0
        move    x:(r7+$5a),a
        sub     x0,a                    ; o2 = u0-u2
        move    a,x0
        mpy     x0,y0,a
        move    a,x:(r3)+

        move    x:(r7+$5d),x0
        move    x:(r7+$5b),a
        sub     x0,a                    ; o3 = u1-u3
        move    a,x0
        mpy     x0,y0,a
        move    a,x:(r4)+

; ---- wet added to dry, two different lines for width ---------------------
        move    x:(r7+$57),a            ; line 1, not the injected line -> bloom
        move    x:(r0),x0
        add     x0,a
        move    a,x:(r0)                ; L back in place
        move    x:(r7+$59),a            ; line 3
        move    x:(r0+n0),x0
        add     x0,a
        move    a,x:(r0+n0)             ; R back in place
        move    #>$2,n0
        move    (r0)+n0                 ; advance one stereo frame
rvend:

; ---- save the phase for the next block -----------------------------------
        move    r1,a
        move    #>$fff,x0
        and     x0,a
        move    a,x:(r7+$54)
        rts
