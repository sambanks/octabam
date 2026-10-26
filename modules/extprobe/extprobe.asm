; ---------------------------------------------------------------------------
; EXTPROBE -- how far into its slot does a stock reverb write?
; (modules/extprobe/README.md: how to run it and read it.)
;
; An insert: frames in place at x:(r0) / x:(r0+n0), knobs from r6, state in this instance's
; r7 block, no bus, no buffers. It replaces its track's audio with a status word per
; 16-sample frame (the layout of PEXT PROBE and DLPROBE) and works on the shared window's X view
; of the FX2 slot at BASE, which the FX2 buffer of one track (T8, core A) owns:
; the words BASE .. BASE + N - 1, N = $3da3, stopping short of LOAD METER's code at $37da3.
;
; GO is a select: 0 OFF (touches nothing), 1 FILL (writes PATTERN over the region, 128 words a
; frame, then SCANs), 2 SCAN (no fill: statistics from zero over what is there, for a region
; that is already filled or seeded). A SCAN pass reads 128 words a frame and counts the words
; that are not PATTERN: in total, in each 1,024-word bucket, and the highest offset.
; A reverb running on the slot's track changes the words it writes; a pass is 124 frames (46 ms).
; Turning GO to 0 and back to 1 refills and restarts the statistics.
;
; ---- what the frames carry (read by modules/extprobe/decode.py) ----------------------
; A cycle of 23 frames, each a value of up to 24 bits: L word = the value's low 16 bits; R word =
; $c000 + 256 i + the value's bits 16..23, i the frame's index; one bit per sample slot, a one is
; +0.5, a zero -0.5.
;   0 the value $e57a01    1 state (0 off, 1 filling, 2 scanning)    2 generation (restarts)
;   3 cursor in the region   4 passes completed   5 highest offset found (since the restart)
;   6 non-pattern words in the last completed pass   7..22 the same in buckets 0..15
; ---- r7 slots -----------------------------------------------------------------------
;   $10 i   $15 L word   $16 R word   $18 the last GO seen
;   $40 + i the value of frame i (above)   $60 non-pattern words so far this pass
;   $61..$70 the buckets so far this pass
; ---------------------------------------------------------------------------

init:
        clr     a
        move    a,x:(r7+$10)
        move    a,x:(r7+$18)
        move    a,x:(r7+$41)
        move    a,x:(r7+$42)
        move    a,x:(r7+$43)
        move    a,x:(r7+$44)
        move    a,x:(r7+$45)
        move    a,x:(r7+$46)
        move    #>$e57a01,x0
        move    x0,x:(r7+$40)
        rts

proc:
        move    #$1,n0
        move    #>$ffffff,m2             ; the pointers below are linear
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    x:(r6+$0),a              ; GO, slot 0: the value in bits 22..16
        and     #>$7f0000,a
        asr     #$10,a,a
        move    x:(r7+$18),x0
        cmp     x0,a
        beq     ep_same
        move    a1,x:(r7+$18)
        tst     a
        beq     ep_off
        move    #>$2,x0                  ; GO 2: scan from zero; GO 1: fill, then scan
        cmp     #>$1,a
        bne     ep_rs
        move    #>$1,x0
ep_rs:
        move    x0,x:(r7+$41)            ; the state
        move    x:(r7+$42),a             ; the generation
        add     #>$1,a
        move    a1,x:(r7+$42)
        clr     a
        move    a,x:(r7+$43)
        move    a,x:(r7+$44)
        move    a,x:(r7+$45)
        move    a,x:(r7+$46)
        move    a,x:(r7+$60)
        move    r7,r2
        move    #>$47,n2
        move    (r2)+n2
        do      #16,>ep_c1
        move    a,x:(r2)+
ep_c1:
        move    r7,r2
        move    #>$61,n2
        move    (r2)+n2
        do      #16,>ep_c2
        move    a,x:(r2)+
ep_c2:
        bra     ep_same
ep_off:
        clr     a
        move    a,x:(r7+$41)
ep_same:
        move    x:(r7+$41),a
        cmp     #>$1,a
        beq     ep_fill
        cmp     #>$2,a
        beq     ep_scan
        bra     ep_pub
; ---- fill: PATTERN over BASE + cursor .. + step - 1 ------------------------------
ep_fill:
        bsr     ep_step                  ; x1 = the step, r2 = BASE + cursor
        move    #>$a5a5a5,x0
        do      x1,>ep_f1
        move    x0,x:(r2)+
ep_f1:
        move    x:(r7+$43),a             ; cursor += step
        move    x1,x0
        add     x0,a
        move    a1,x:(r7+$43)
        move    #>$3da3,x0
        cmp     x0,a
        blt     ep_pub
        move    #>$2,x0                  ; filled: scan from the start
        move    x0,x:(r7+$41)
        clr     a
        move    a,x:(r7+$43)
        bra     ep_pub
; ---- scan: count what is not PATTERN -----------------------------------------------
ep_scan:
        bsr     ep_step                  ; x1 = the step, r2 = BASE + cursor
        move    x:(r7+$43),a
        move    a1,r3                    ; r3 = the offset of the word being read
        move    r7,a
        add     #>$61,a
        move    a1,r4                    ; r4 = the buckets so far
        move    #>$a5a5a5,x0
        do      x1,>ep_s1
        move    x:(r2)+,a
        cmp     x0,a
        beq     ep_s0
        move    r3,a                     ; not PATTERN: its bucket
        asr     #$a,a,a
        move    a1,n4
        move    x:(r4+n4),b
        add     #>$1,b
        move    b,x:(r4+n4)
        move    x:(r7+$60),b
        add     #>$1,b
        move    b,x:(r7+$60)
        move    r3,a                     ; the highest offset
        move    x:(r7+$45),b
        cmp     b,a
        ble     ep_s0
        move    a1,x:(r7+$45)
ep_s0:
        move    (r3)+
ep_s1:
        move    x:(r7+$43),a             ; cursor += step
        move    x1,x0
        add     x0,a
        move    a1,x:(r7+$43)
        move    #>$3da3,x0
        cmp     x0,a
        blt     ep_pub
        clr     a                        ; a pass is done: publish its counts
        move    a,x:(r7+$43)
        move    x:(r7+$44),a
        add     #>$1,a
        move    a1,x:(r7+$44)
        move    x:(r7+$60),a
        move    a1,x:(r7+$46)
        clr     a
        move    a,x:(r7+$60)
        move    r7,r2
        move    #>$61,n2
        move    (r2)+n2
        move    r7,r3
        move    #>$47,n3
        move    (r3)+n3
        do      #16,>ep_s2
        move    x:(r2),b
        move    b,x:(r3)+
        move    a,x:(r2)+
ep_s2:
; ---- publish the frame ---------------------------------------------------------------
ep_pub:
        move    r7,r2
        move    x:(r7+$10),a
        add     #>$40,a
        move    a1,n2
        move    x:(r2+n2),b              ; the value of frame i
        move    b,x:(r7+$11)
        move    b,a
        and     #>$ffff,a
        move    a1,x:(r7+$15)
        move    x:(r7+$11),a
        asr     #$10,a,a
        and     #>$ff,a
        move    a1,x1
        move    x:(r7+$10),a
        asl     #$8,a,a
        add     x1,a
        add     #>$c000,a
        move    a1,x:(r7+$16)
        move    x:(r7+$10),a             ; the next frame; the cycle is 23 long
        add     #>$1,a
        cmp     #>23,a
        bne     ep_k
        clr     a
ep_k:
        move    a1,x:(r7+$10)
        do      n7,>epfin                ; 16 on the unit
        move    x:(r7+$15),a
        and     #>$1,a
        move    #>$c00000,b
        move    #>$400000,x1
        tne     x1,b
        move    b,x:(r0)
        move    x:(r7+$16),a
        and     #>$1,a
        move    #>$c00000,b
        tne     x1,b
        move    b,x:(r0+n0)
        move    x:(r7+$15),a
        asr     #$1,a,a
        move    a1,x:(r7+$15)
        move    x:(r7+$16),a
        asr     #$1,a,a
        move    a1,x:(r7+$16)
        move    (r0)+n0
        move    (r0)+n0
epfin:
        rts

; x1 = min(128, N - cursor); r2 = BASE + cursor.
ep_step:
        move    #>$3da3,a
        move    x:(r7+$43),x0
        sub     x0,a
        move    #>$80,x1
        cmp     x1,a
        bge     ep_cl
        move    a1,x1
ep_cl:
        move    #>$34000,a
        add     x0,a
        move    a1,r2
        rts
