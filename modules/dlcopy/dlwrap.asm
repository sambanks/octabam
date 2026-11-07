; ---------------------------------------------------------------------------
; DLWRAP -- keeps the stock buffered reverbs off demand-loaded code
; (docs/contributing/DEMAND_LOADER.md). One body, in the window once, serves every guarded
; reverb on both payloads. The build puts a pair of trampolines per reverb and payload
; in front of it (the stock entries differ between payloads) and points the reverbs'
; ids at them.
;
; A reverb writes its instance buffer from the base the allocator hands the slot (the
; entry whose address is in x:$213 at init) up to a measured extent. When that range
; covers words a loaded effect occupies, the reverb must not run: the instance passes the
; audio through. The check is made at init and every frame, so code that arrives later is
; never written over; an instance that has gone dry runs again, without a reselect, as
; soon as the range is clear (running the stock init first if it never had).
;
; A trampoline leaves, before it enters `init` or `proc`:
;   x:$3fd1  the stock entry to jump to (the init, or the proc)   x:$3fd2  the extent: one more
;   than the highest word the reverb writes above its base   x:$3fd3 (proc only) the stock init
;
; Per core (X, private), one word per instance at idx = (r7 >> 8) & $3f:
;   x:$3dc0+idx  0 never initialised, 1 running, 2 dry and its init has not run, 3 dry after it ran
;   x:$3e00+idx  the buffer base the instance was given
; x:$3fd0 the proc's entry a   x:$3fe0..$3fe7 registers kept across a resumed init
; Shared (DLCOPY writes the entry of each loaded effect, x:$33da3 + 8 k): +0 BOUND,
; +3 and +4 the span [first word, word after the last).
; ---------------------------------------------------------------------------

init:
        move    x:>$213,r5               ; the address of this slot's entry in the allocator table
        bsr     dw_ix
        move    x:(r5),x1                ; the buffer base: the entry's contents
        move    x1,x:(r3)                ; remember it
        bsr     dw_over
        tst     a
        bne     dw_off
        move    #>$1,x0
        move    x0,x:(r4)                ; running
        move    x:>$3fd1,r2
        jmp     (r2)
dw_off:
        move    #>$2,x0
        move    x0,x:(r4)                ; dry, the init not run
        rts

proc:
        move    a1,x:>$3fd0              ; proc is called with a = 0 or 1 in a: kept for the stock proc
        bsr     dw_ix
        move    x:(r4),a
        cmp     #>$1,a
        beq     dw_run
        tst     a
        beq     dw_pass                  ; never initialised
        move    x:(r3),x1                ; dry: is the range clear now?
        bsr     dw_over
        tst     a
        bne     dw_pass
        move    x:(r4),a
        cmp     #>$3,a
        beq     dw_go                    ; its init had run
        move    r0,x:>$3fe0              ; the stock init, run now for this instance, as the dispatcher would
        move    n0,x:>$3fe1
        move    r6,x:>$3fe2
        move    r7,x:>$3fe3
        move    n7,x:>$3fe4
        move    m0,x:>$3fe5
        move    m1,x:>$3fe6
        move    x:>$213,x0
        move    x0,x:>$3fe7
        move    r3,x:>$213               ; the init reads its base through x:$213: the cell that holds it
        move    x:>$3fd3,r2
        jsr     (r2)
        move    x:>$3fe7,x0
        move    x0,x:>$213
        move    x:>$3fe0,r0
        move    x:>$3fe1,n0
        move    x:>$3fe2,r6
        move    x:>$3fe3,r7
        move    x:>$3fe4,n7
        move    x:>$3fe5,m0
        move    x:>$3fe6,m1
        bsr     dw_ix
        bra     dw_go
dw_run:
        move    x:(r3),x1
        bsr     dw_over
        tst     a
        bne     dw_dry
dw_go:
        move    #>$1,x0
        move    x0,x:(r4)                ; running
        move    x:>$3fd0,a
        move    x:>$3fd1,r2
        jmp     (r2)
dw_dry:
        move    #>$3,x0
        move    x0,x:(r4)                ; dry, its init had run
dw_pass:
        move    r0,r1
        do      n7,>dw_end
        move    x:(r0)+,a
        move    x:(r0)+,b
        move    a,x:(r1)+
        move    b,x:(r1)+
dw_end:
        rts

; r3 = the instance's base cell, r4 = its state word.
dw_ix:
        move    r7,a
        asr     #$8,a,a
        and     #>$3f,a
        move    #>$3e00,x0               ; not x:$3f7f..$3fbf: payload B's frame routine at P:$7a writes those every frame
        add     x0,a
        move    a1,r3
        lua     (r3-64),r4
        rts

; a = 1 when the range [x1, x1 + extent) covers any word of any loaded effect's code, else 0. The build sets the loop's
; count to the remix's entries (4, or more when it has more demand effects).
dw_over:
        clr     b
        move    #>$33da3,r5
        do      #4,>dw_next
        move    x:(r5),a
        move    #>$b0a5ed,x0
        cmp     x0,a
        bne     dw_skip
        move    x1,a
        move    x:(r5+4),x0
        cmp     x0,a
        bge     dw_skip                  ; the range starts at or after the end of the code
        move    x:>$3fd2,x0
        add     x0,a
        move    x:(r5+3),x0
        cmp     x0,a
        ble     dw_skip                  ; the range ends at or before the start of the code
        move    #>$1,b
dw_skip:
        lua     (r5+8),r5
dw_next:
        move    b,a
        rts
