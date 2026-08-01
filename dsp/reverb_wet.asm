; ---------------------------------------------------------------------------
; reverb MINIMAL -- cost bisection build
;
; v4 (~200 instructions/sample) hangs the DSP on hardware even with the M
; registers restored. The DSP has a hard frame deadline; blowing it stalls the
; audio engine, which presents exactly as audio stopping and the sequencer
; freezing on a trig. This strips back to the bare 4-line FDN (~60
; instructions/sample) with the M-register fixes applied, to find out whether
; the problem is COST or something structural.
;
;   runs  -> cost. Add diffusion/modulation back until it breaks, and tune down.
;   hangs -> structural, and the delay buffers or their addressing are suspect,
;            not the amount of work.
;
; original v1 header follows
; reverb v1 -- 4-line feedback delay network
;
; Brief: long smooth tails, bright but not harsh, slow bloom.
;
;   long tails   high feedback -- decay comes from feedback, not buffer length
;   smooth       coprime taps so modes do not stack (modulation is v2)
;   bright       one-pole damping INSIDE the loop, light, so highs decay
;                gradually rather than being filtered off at the input the way
;                the stock reverbs do
;   slow bloom   inject into ONE line and let the Hadamard spread energy over
;                successive passes -- build-up for free, no envelope needed
;
; Deliberately minimal: no input diffusion, no modulation, fixed coefficients.
; v1 is about hearing whether the topology is right.
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
;   +$55      mono input
; ---------------------------------------------------------------------------

init:
; NO buffer clear. init is called from the audio frame path, and any bulk loop
; there blows the frame deadline and stalls the engine permanently. Evidence:
; every build whose init contains a long loop hangs -- 1024 or 4096 iterations,
; one or two instructions per iteration, X memory or Y memory, all identical.
; Every build whose init is a handful of moves works. Memory space was never the
; variable.
;
; The delay buffers are simply left as they are. Whatever they contain decays
; away through the feedback loop, and DSP RAM is generally zero after boot.
        clr     a
        move    a,x:(r7+$50)
        move    a,x:(r7+$51)
        move    a,x:(r7+$52)
        move    a,x:(r7+$53)
        move    a,x:(r7+$54)            ; write phase

; restore the M registers -- the caller's addressing breaks otherwise
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts

proc:
; ---- rebuild delay pointers from the saved phase -------------------------
; r1-r4 do not survive between calls, so the phase lives in state. Each base is
; 2048-aligned, so M=$7ff wraps inside its own buffer.
        move    x:(r7+$54),a
        move    #>$9000,x0
        add     x0,a
        move    a,r1
        move    #>$800,x0
        add     x0,a
        move    a,r2
        add     x0,a
        move    a,r3
        add     x0,a
        move    a,r4
        move    #>$7ff,m1
        move    #>$7ff,m2
        move    #>$7ff,m3
        move    #>$7ff,m4
        move    #>$fff903,n1            ; -1789
        move    #>$fffa0d,n2            ; -1523
        move    #>$fffb4f,n3            ; -1201
        move    #>$fffc39,n4            ; -967
        move    r0,r5                   ; audio write pointer trails the read

        do      n7,>rvend

; ---- input: mono sum ------------------------------------------------------
        move    x:(r0)+,a
        move    x:(r0)+,x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$55)

; ---- four taps, each damped inside the feedback path ---------------------
; one-pole: s += c*(d-s), c light so the tail stays bright
        move    #>$600000,y0            ; damping coefficient
        move    x:(r1+n1),a
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

        move    x:(r3+n3),a
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
        move    #>$3d0000,y0            ; feedback g/2: the 4x4 Hadamard has row norm 2,
                                       ; so H/2 is orthonormal and the loop gain is g

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

; ---- DIAGNOSTIC: wet ONLY, dry discarded ---------------------------------
; The reverb plays without hanging but is inaudible. Either the tank has no
; energy, or the wet is simply too quiet against the dry. Writing wet only
; separates the two:
;   reverb audible -> it was a level problem
;   silence        -> the tank is dead: nothing is circulating
;   dry unchanged  -> our writes are not reaching the audio buffer at all
        move    x:(r7+$56),a
        move    a,x:(r5)+
        move    x:(r7+$58),a
        move    a,x:(r5)+
rvend:

; ---- save the phase for the next block -----------------------------------
        move    r1,a
        move    #>$7ff,x0
        and     x0,a
        move    a,x:(r7+$54)

; restore the M registers -- the caller's addressing breaks otherwise
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
