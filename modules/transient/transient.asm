; ---------------------------------------------------------------------------
; TRANSIENT -- a differential-envelope transient shaper.
;
; Insert contract: frames in place at x:(r0)/x:(r0+n0), knobs from r6,
; state in this instance's r7 block. No bus, no buffers, no shared window.
;
; ---- the law (modules/transient/DESIGN.md, transient_ref.py) ---------------
;   d   = max(|L|, |R|)                    stereo-linked
;   pk  = max(d, pk * r)                   instant attack, 10 ms release
;   v   = log2(max(pk, 2^-16)) / 32        clb + normf + the LOG table
;   F  += c * (v - F)   c = 0.5 ms up, 50 ms down
;   S  += c * (v - S)   c = TIME up, 50 ms down; then S >= F - 2 bits
;   H  += c * (v - H)   c = 0.5 ms up, 500 ms down (48-bit state);
;                       on a new hit (v > F + 0.5 bit), H <= v - 0.5 bit: each hit
;                       starts its own tail
;   g   = clamp(ATCK*max(F-S,0) + SUST*max(H-max(F,v-0.5 bit),0), +-2 bits) + OUT
;   y   = x * 2^g                          the EXP table holds 2^g / 16
;   out = x + MIX * (y - x)
; Log values are in bits/32: the -96 dB floor is -0.5, 2 bits is $080000.
; ATCK = SUST = 64 and OUT = 64 give g = 0 exactly and EXP[16] = 1/16
; exactly, so the defaults are a bit-exact passthrough; MIX 0 is one too.
;
; ---- the P table (the manifest's ptable, 99 words) -------------------------
;   +0  LOG   log2(0.5 + i/64)/32, i = 0..32
;   +33 EXP   2^(-4 + i/4)/16, i = 0..32
;   +66 TIMEC the slow follower's attack coefficient, TIME = 4i
;
; ---- r7 slots ---------------------------------------------------------------
; persistent, set at init:
;   $00 F   $01 S   $02 H (high word)   $03 H (low word)
;   $04 pk (high word)   $06 pk (low word)
; per sample scratch: $05 the clb count
; per block, from the knobs:
;   $10 ATCK as -1..+1   $11 SUST as -1..+1   $12 OUT in bits/32
;   $13 MIX (127 pinned to full scale)   $14 S's attack coefficient
; r4 holds the table base for the whole block; r5 walks it.
;
; Every mpy and mac is y0,x0 or x0,y1 (the signed encodings), mac -x0,y1 once. Every Tcc
; reads the compare or subtract directly above it with only moves between.
; No branch anywhere: the cycle count is the word span.
; ---------------------------------------------------------------------------

init:
        move    #$c0,x0                  ; -16 bits: the followers start at (short immediate: bits 23-16)
        move    x0,x:(r7+$00)           ; the floor, like the float reference
        move    x0,x:(r7+$01)
        move    x0,x:(r7+$02)
        clr     a
        move    a,x:(r7+$03)            ; every slot the loop reads before
        move    a,x:(r7+$04)            ; it writes (verify_dirty_state)
        move    a,x:(r7+$05)
        move    a,x:(r7+$06)
        rts

proc:
; ---- per block: the knobs ---------------------------------------------------
; Page-1 knob words carry the value in bits 22..16 (value/128) and the
; ColdFire's fraction below.
        move    x:(r6+$0),a             ; ATCK -> 2*(w - 0.5)
        and     #>$7fffff,a
        sub     #>$400000,a
        asl     #$1,a,a
        move    a,x:(r7+$10)
        move    x:(r6+$1),a             ; SUST, the same
        and     #>$7fffff,a
        sub     #>$400000,a
        asl     #$1,a,a
        move    a,x:(r7+$11)
        move    x:(r6+$3),a             ; OUT -> (w - 0.5)/8: +-2 bits in bits/32
        and     #>$7fffff,a
        sub     #>$400000,a
        asr     #$3,a,a
        move    a,x:(r7+$12)
        move    x:(r6+$4),a             ; MIX: value/128, 127 pinned to full
        and     #>$7f0000,a
        move    #$7f,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$13)
; TIME -> TIMEC[idx], interpolated: idx = bits 22..18, frac = the 18 below.
        move    #>$ffffff,m5
        move    #>$fab1e0,r4           ; the table base, held in r4 for the block
        move    r4,r5
        move    x:(r6+$2),a
        and     #>$7fffff,a
        move    a1,x1
        asr     #$12,a,a
        add     #>$000042,a             ; + 66, TIMEC
        move    a1,n5
        move    x1,a
        and     #>$3ffff,a
        asl     #$5,a,a
        move    (r5)+n5
        move    a,x0                    ; frac
        move    p:(r5)+,y0              ; T[i]
        move    p:(r5),b                ; T[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        move    a,x:(r7+$14)
        move    #$1,n0                  ; (short immediate, stock's own form)

        do      n7,>trnsh_end
; ---- detector: d = max(|L|, |R|), then the linear peak ---------------------
        move    x:(r0),a
        abs     a           x:(r0+n0),b
        abs     b
        move    b,x0
        cmp     x0,a
        tlt     x0,a                    ; a = max(|L|, |R|)
        move    a,x1                    ; d
; pk keeps 48 bits ($04 high, $06 low): pk*r is formed as pk - pk*(1-r), so
; the 10 ms release does not truncate a whole LSB per sample at low levels
; (24 bits made the release run fast below about -80 dBFS: 0.27 dB of level
; dependence in verify_transient, 3 Oct 2026).
        move    x:(r7+$04),a
        move    x:(r7+$06),a0
        move    a1,x0                   ; pk, high word
        move    #>$004a38,y1            ; 1 - r, r = exp(-1/441)
        mac     -x0,y1,a                ; pk*r
        cmp     x1,a
        tlt     x1,a                    ; pk*r < d -> d (a0 cleared)
        move    a1,x:(r7+$04)
        move    a0,x:(r7+$06)
; ---- v = log2(max(pk, 2^-16)) / 32 ------------------------------------------
        move    #>$000080,x0            ; 2^-16
        cmp     x0,a
        tlt     x0,a
        clb     a,b                     ; b1 = floor(log2 pk) + 1, in -15..0
        normf   b1,a                    ; a = the mantissa m, in [0.5, 1)
        move    b1,x:(r7+$05)
        move    r4,r5                   ; the table base
        sub     #>$400000,a             ; u = 2*(m - 0.5), in [0, 1)
        asl     #$1,a,a
        move    a1,x1
        asr     #$12,a,a                ; idx = bits 22..18 of u
        move    a1,n5
        move    x1,a
        and     #>$3ffff,a
        asl     #$5,a,a                 ; frac
        move    (r5)+n5
        move    a,x0
        move    p:(r5)+,y0              ; LOG[i]
        move    p:(r5),b                ; LOG[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a                    ; log2(m)/32
        move    x:(r7+$05),b
        asl     #$12,b,b                ; count * 2^18 = count/32
        add     b,a                     ; v
        move    a,x1                    ; v, kept for the three followers
; ---- F: 0.5 ms up, 50 ms down -----------------------------------------------
        move    x:(r7+$00),b
        sub     b,a                     ; v - F
        move    a,y0
        move    #>$000edb,a             ; 50 ms
        move    #>$05ace2,x0            ; 0.5 ms
        tgt     x0,a                    ; rising -> the attack coefficient
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,x:(r7+$00)            ; F
; ---- S: TIME up, 50 ms down, then S >= F - 2 bits ------------------------------
        move    x1,a
        move    x:(r7+$01),b
        sub     b,a                     ; v - S
        move    a,y0
        move    #>$000edb,a
        move    x:(r7+$14),x0           ; TIME's coefficient
        tgt     x0,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a                     ; S'
        move    x:(r7+$00),b
        sub     #>$080000,b             ; F - 2 bits
        move    b,x0
        cmp     x0,a
        tlt     x0,a                    ; S' < F - 2 bits -> F - 2 bits
        move    a,x:(r7+$01)            ; S
; ---- H: 0.5 ms up, 500 ms down, 48-bit state ----------------------------------
        move    x1,a
        move    x:(r7+$02),b
        move    x:(r7+$03),b0
        sub     b,a                     ; v - H
        move    a,y0
        move    #>$00017c,a             ; 500 ms
        move    #>$05ace2,x0            ; 0.5 ms
        tgt     x0,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
; a rising input starts its own tail: while v > F, H may not exceed v. Without
; this a quieter hit inside a louder one's tail took the tail's gain on its
; onset (+12 dB on every onset of a drum loop at SUST +63; heard, then
; measured, 3 Oct 2026).
; A new hit means v above F by 0.5 bit (3 dB): ripple in a tail stays below
; it. With no margin the tails clicked (19 gain steps of up to 12 dB on the
; drum loop; heard, then measured, 3 Oct 2026).
        move    x1,b
        sub     #>$040000,b             ; v - 0.5 bit
        move    b,y1                    ; the cap, if this is a new hit: with the
        move    x:(r7+$00),x0           ; cap at v the margin itself was gain
        cmp     x0,b                    ; (v - 0.5 bit) - F
        move    #>$7fffff,b             ; no cap
        tgt     y1,b                    ; a new hit -> the cap is v - 0.5 bit
        move    b,y1
        cmp     y1,a                    ; H - cap
        tgt     y1,a                    ; H > cap -> cap (a0 cleared)
        move    a1,x:(r7+$02)           ; H, both words
        move    a0,x:(r7+$03)
; ---- the gain: g = ATCK*max(F-S,0) + SUST*max(H-F,0), clamped, + OUT --------
        move    x:(r7+$00),a
        move    x:(r7+$01),x0
        sub     x0,a                    ; F - S
        move    #0,x0
        tmi     x0,a                    ; max(., 0)
        move    a,y0
        move    x:(r7+$10),x0           ; ATCK
        mpy     y0,x0,b
        move    x1,a
        sub     #>$040000,a             ; v - 0.5 bit
        move    x:(r7+$00),x0           ; F
        cmp     x0,a
        tlt     x0,a                    ; max(F, v - 0.5 bit): no sustain
        move    a,x0                    ; gain at the instant of a new hit
        move    x:(r7+$02),a
        sub     x0,a                    ; H - max(F, v - 0.5 bit)
        move    #0,x0
        tmi     x0,a
        move    a,y0
        move    x:(r7+$11),x0           ; SUST
        mac     y0,x0,b                 ; g in bits/32
        move    #$08,x0                  ; +2 bits (short immediate: bits 23-16)
        cmp     x0,b
        tgt     x0,b
        move    #$f8,x0                  ; -2 bits (short immediate: bits 23-16)
        cmp     x0,b
        tlt     x0,b
        move    x:(r7+$12),x0           ; OUT
        add     x0,b
; ---- 2^g from EXP: u = 4*g/32 + 0.5, in [0, 1) ---------------------------------
        asl     #$2,b,b
        add     #>$400000,b
        move    b1,x1                   ; u
        move    r4,r5                   ; the table base
        asr     #$12,b,b                ; idx
        add     #>$000021,b             ; + 33, EXP
        move    b1,n5
        move    x1,a
        and     #>$3ffff,a
        asl     #$5,a,a                 ; frac
        move    (r5)+n5
        move    a,x0
        move    p:(r5)+,y0              ; EXP[i]
        move    p:(r5),b                ; EXP[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a                    ; 2^g / 16
        move    a,y0
; ---- apply to L, then R: out = x + MIX*(x*2^g - x) -----------------------------
        move    x:(r0),b                ; L, dry
        move    b,x0
        mpy     y0,x0,a
        asl     #$4,a,a                 ; L * 2^g
        sub     b,a
        asr     #$1,a,a                 ; (wet - dry)/2, so the move below
        move    a,x0                    ; limits only past +6 dBFS of wet
        move    x:(r7+$13),y1           ; MIX
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)+               ; limited store
        move    x:(r0),b                ; R, dry
        move    b,x0
        mpy     y0,x0,a
        asl     #$4,a,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$13),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)+
trnsh_end:
        nop
        rts
