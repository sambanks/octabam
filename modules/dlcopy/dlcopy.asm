; ---------------------------------------------------------------------------
; DLCOPY -- the demand loader's copier, a frame hook on payload B
; (docs/proposals/DEMAND_LOAD.md).
;
; Every frame, at the frame head, a block the ColdFire has staged in this core's X
; is moved into the shared window and published; or an effect's words are
; withdrawn. The window is one memory for both cores, so a copy made here is
; resident for the tracks of core A as well.
;
; Staging (X, written by the ColdFire's host transfer, 16 bits a word: the byte above them is whatever
; the port last held, so every word is read through a 16-bit mask):
;   x:$2900  doorbell, written last: $a55a when the block is complete
;   x:$2901  the effect's index k, 0..3
;   x:$2902  destination, as an offset into the window (the host carries 16 bits)
;   x:$2903  the number of code words N; 0 withdraws the effect
;   x:$2904  the real init, as an offset   x:$2905  the real proc, as an offset
;   x:$2906.. 2 N + 2 words: each 24-bit code word as its high 16 bits, then its low 8; the last
;   pair is the sum of the N code words, modulo 2^24, in the same form
; The doorbell is cleared when the block is consumed. A block whose sum does not match is
; not published (BOUND stays clear); the ColdFire sends every block three times.
;
; The effect's entry in the window, x:$33da3 + 8 k (five words used):
;   +0 BOUND  $b0a5ed while the code is resident   +1 the real init   +2 the real proc
;   +3 the first window word the code occupies     +4 the word after its last
;   +5 blocks received   +6 blocks refused for their sum   +7 blocks published (counters, read by DLPROBE)
; BOUND is cleared before any other word of the entry or the code changes and set
; last, so a stub on either core sees the code whole or not at all.
;
; Registers: a, x0, x1, r0, r1 only, and b, kept in x:$3fe8..$3fea; the stock code after the hook
; site (P:$7a) writes the others before it reads them.
; ---------------------------------------------------------------------------

dlc_start:
        move    x:>$2900,a
        and     #>$ffff,a                ; the host write delivers 16 bits; the byte above them is whatever it was (0x40 measured)
        move    #>$a55a,x0
        cmp     x0,a
        bne     dlc_exit
        move    #>$2901,r0               ; the header words, cleaned the same way
        do      #5,>dlc_hn
        move    x:(r0),a
        and     #>$ffff,a
        move    a1,x:(r0)+
dlc_hn:
        move    x:>$2901,a
        asl     #$3,a,a
        move    #>$33da3,x0
        add     x0,a
        move    a1,r1                    ; the entry
        clr     a
        move    a,x:(r1)                 ; unbound while its words change
        move    x:>$2903,x0              ; N
        move    x0,a
        tst     a
        beq     dlc_off
        move    x:(r1+5),a
        add     #>$1,a
        move    a1,x:(r1+5)
        lua     (r1+3),r1
        move    x:>$2902,a
        move    #>$30000,x1
        add     x1,a
        move    a1,x:(r1)+               ; the span
        add     x0,a
        move    a1,x:(r1)
        move    x:>$2902,a
        add     x1,a
        move    a1,r1                    ; the destination
        move    b2,x:>$3fe8              ; b is the running sum
        move    b1,x:>$3fe9
        move    b0,x:>$3fea
        clr     b
        move    #>$2906,r0
        do      x0,>dlc_cpy
        move    x:(r0)+,a
        and     #>$ffff,a
        asl     #$8,a,a
        move    a1,x1
        move    x:(r0)+,a
        and     #>$ff,a
        move    x1,x0
        add     x0,a
        add     a,b
        move    a1,x0
        move    x0,p:(r1)+
dlc_cpy:
        move    x:(r0)+,a                ; the staged sum
        and     #>$ffff,a
        asl     #$8,a,a
        move    a1,x1
        move    x:(r0)+,a
        and     #>$ff,a
        move    x1,x0
        add     x0,a
        move    b1,x0
        sub     x0,a
        move    a1,a
        tst     a
        bne     dlc_refused              ; not published
        move    #>$30000,x1
        move    x:>$2901,a
        asl     #$3,a,a
        move    #>$33da3,x0
        add     x0,a
        move    a1,r1
        lua     (r1+1),r1
        move    x:>$2904,a
        add     x1,a
        move    a1,x:(r1)+               ; the real init
        move    x:>$2905,a
        add     x1,a
        move    a1,x:(r1)                ; the real proc
        lua     (r1-2),r1
        move    #>$b0a5ed,x0
        move    x0,x:(r1)                ; BOUND, after the code and both entries
        move    x:(r1+7),a
        add     #>$1,a
        move    a1,x:(r1+7)
        bra     dlc_bad
dlc_refused:
        move    #>$30000,x1
        move    x:>$2901,a
        asl     #$3,a,a
        move    #>$33da3,x0
        add     x0,a
        move    a1,r1
        move    x:(r1+6),a
        add     #>$1,a
        move    a1,x:(r1+6)
dlc_bad:
        move    x:>$3fe8,b2
        move    x:>$3fe9,b1
        move    x:>$3fea,b0
        bra     dlc_done
dlc_off:
        lua     (r1+3),r1                ; withdrawn: the span is empty too
        move    a,x:(r1)+
        move    a,x:(r1)
dlc_done:
        clr     a
        move    a,x:>$2900               ; consumed
dlc_exit:
        move    r6,x:>$207               ; the displaced stock instruction
        rts
