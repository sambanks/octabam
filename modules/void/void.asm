; ---------------------------------------------------------------------------
; VOID -- SCRAPE insert (FEED start: one-sample sat loop).
;
; Insert: x:(r0)/x:(r0+n0) in place, knobs r6, state r7. No bus, no buffers.
; Stages: white → HPF/COLR → FDBK+DRV (noise only) → AM → WID → BAL vs dry
; Law: modules/void/void_ref.py
;
; BAL = this track ↔ noise always (neighbour never replaces the dry source).
; SETUP SRC ($d companion, bottom left): LFO (default) or NBR. NBR AM’s noise
; from previous track’s KEYBUS X:($37f60+track−1); quiet → noise stops.
; X:$420 = absolute track (0..7); harness $420=0 invents abs from FX2 pos.
; KEYBUS publishes the block peak of |mono| in X:$37f60+track.
; Law: noise' = FDBK+DRV(noise);  noise'' = noise'·((1−DPTH)+DPTH·uni);
;       WID stereoizes noise'';  wet = (1−BAL)·dry + BAL·noise''.
;       Dry never AM/DRV/FDBK'd — BAL=0 is always exact dry.
; WID (SETUP $d): 0 = mono (L=R=mid); >0 = 2nd white → same HPF/COLR/DRV
;   (no FDBK) → same AM; L=mid+(w/2)·side, R=mid−(w/2)·side —
;   continuous at 0→1, balanced, mono sum keeps mid (LFO AM stays audible).
;   Mid keeps the FDBK loop.
;
; P table (ptable literal): RATE +0, HPF +129, COLOR +258 (129 words each).
;
; r7: $00 phase $01 noise LCG
;     $02 HPF mid  $03 HPF side  $04 COLR mid  $05 COLR side
;     $06 fbL   $07 fbR   (FDBK on mid only; both kept in step when mono)
;     $0c dcL   $0d dcR   (feedback DC tracker — high FDBK+DRV otherwise rails)
;     $10..$19 block knobs/flags ($16 = BAL)
;     $1b use_nbr (SRC=NBR)  $1c pos  $1d keybus X: address
;     $1e nbr uni (smoothed |mono|)  $1f env one-pole state
;     $20 nL after AM/width  $21 nR after AM/width  $22 dryL  $23 dryR
;     $24 scratch (u / pre-HP / m)
;     $25 noise sample / sqr osc (reused after src)
;     $26 uni / sin  $27 saw / u park  $28 driven mid
;     $2e LCG2 (side)  $37 WID (Q23)
;     $40..$4f RESERVED for FEED delay (kept zero)
;
; CYCLES_FORWARD_BRANCHES
; ---------------------------------------------------------------------------

init:
        move    r7,r5
        clr     a
        do      #$50,>norep_vd_zi
        move    a,x:(r5)+
norep_vd_zi:
        move    #>$2a5f31,x0
        move    x0,x:(r7+$01)
        move    #>$5f1a2b,x0            ; side LCG (≠ mid)
        move    x0,x:(r7+$2e)
        rts

proc:
        move    #>$ffffff,m5
        move    #>$fab1e0,r4
; BAL: kn<<16; kn=127 → exact 1.0 (pure noise, no dry floor)
        move    x:(r6+$0),a
        and     #>$7f0000,a
        move    #$7f,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$16)            ; BAL: 0 = full input, 127 = full noise
        move    r4,r5
        move    x:(r6+$1),a
        and     #>$7f0000,a             ; LFO-word trap: ignore low bits
        asr     #$10,a,a
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$10)            ; RATE step
; COLR page1 $2: kn; 127 → open flag; table +258
        move    x:(r6+$2),a
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #0,b
        move    #>$00007f,x0
        cmp     x0,a
        move    #>$000001,y0
        teq     y0,b
        move    b,x:(r7+$18)
        move    r4,r5
        move    #>$000102,n5
        move    (r5)+n5
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$15)
; HPF page1 $3: 0 = bypass; table +129
        move    x:(r6+$3),a
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #0,b
        tst     a
        move    #>$000001,y0
        tne     y0,b
        move    b,x:(r7+$19)
        move    r4,r5
        move    #>$000081,n5
        move    (r5)+n5
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$14)
        move    x:(r6+$4),a
        and     #>$7f0000,a
        move    a,x:(r7+$13)            ; DRV
        move    x:(r6+$5),a
        and     #>$7f0000,a
        move    a,x:(r7+$12)            ; FDBK
; SHPE = $c knob (SETUP); DPTH = $c companion
        move    x:(r6+$c),a
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #>$000002,x0
        cmp     x0,a
        move    #0,y0
        tgt     y0,a
        move    a,x:(r7+$17)            ; SHPE
        move    x:(r6+$c),a
        and     #>$007f00,a
        asr     #$8,a,a
        asl     #$10,a,a                ; kn<<16
        move    #$7f,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$11)            ; DPTH (127 → exact 1.0)
; WID = $d knob; SRC = $d companion
        move    x:(r6+$d),a
        and     #>$7f0000,a
        move    #$7f,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$37)            ; WID
        move    x:(r6+$d),a
        and     #>$007f00,a             ; SRC companion
        asr     #$8,a,a
        tst     a
        move    #0,a
        move    #>$000001,x0
        tne     x0,a
        move    a,x:(r7+$1b)            ; use_nbr (0=LFO, 1=NBR)
        clr     a
        move    a,x:(r7+$1d)
        move    x:(r7+$1b),a
        tst     a
        beq     vd_nbr_go               ; LFO — no keybus
; FX2 pos from r7 (harness invents abs track when X:$420 is 0)
        move    #0,a
        move    r7,b
        move    #>$6500,x0
        cmp     x0,b
        move    #>$000001,y0
        teq     y0,a
        move    #>$6800,x0
        cmp     x0,b
        move    #>$000002,y0
        teq     y0,a
        move    #>$6b00,x0
        cmp     x0,b
        move    #>$000003,y0
        teq     y0,a
        move    a,x:(r7+$1c)
        move    x:>$420,b
        tst     b
        bne     vd_abs
        move    a,b                     ; harness: abs = pos
        tst     b
        bne     vd_abs
        move    #>$000001,b             ; pos0 harness → model T2 reading T1
vd_abs:
        move    b,a
        move    #>$000001,x0
        sub     x0,a                    ; previous absolute track
        move    #>$37f60,x0
        add     x0,a                    ; X:keybus word for previous track
        move    a,x:(r7+$1d)
vd_nbr_go:
        move    #$1,n0

        do      n7,>vd_end
        move    x:(r0),a
        move    a,x:(r7+$22)
        move    x:(r0+n0),a
        move    a,x:(r7+$23)
; neighbour AM uni: smoothed published keybus peak (BAL source stays this track)
        move    x:(r7+$1b),a
        tst     a
        beq     vd_have_in
        move    x:(r7+$1d),b
        tst     b
        beq     vd_have_in
        move    b,r5
        move    x:(r5),a
        abs     a                       ; KEYBUS publishes |mono| peak in X
        move    x:(r7+$1f),b            ; env one-pole
        sub     b,a
        move    a,x0
        move    #>$051eb8,y1            ; ≈0.04 — kill clicks, keep grit
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$1f)
        move    a,x:(r7+$1e)
vd_have_in:
; white LCG -> $25 at -6 dB (shape with COLR/HPF only)
        move    x:(r7+$01),x0
        move    #>$19660d,y1
        mpy     x0,y1,b
        asr     b
        move    b0,x0
        move    x0,b
        add     #>$6ef35f,b
        move    b1,x:(r7+$01)
        move    b1,a
        asr     #$1,a,a                 ; × 1/2
        move    a,x0
        move    x0,x:(r7+$25)
; HPF + COLR on mid ($02/$04); side uses $03/$05 under WID.
        move    x0,x1                   ; the word just stored, from its register
        move    x1,x:(r7+$24)
        move    x:(r7+$14),y0
        move    x:(r7+$02),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,x:(r7+$02)
        move    x1,b
        sub     a,b
        move    b,a
        move    x:(r7+$19),b
        tst     b
        move    x:(r7+$24),x0
        teq     x0,a
        move    a,x:(r7+$25)
; LP (forward skip when COLOR open)
        move    x:(r7+$18),a
        tst     a
        bne     vd_nz_open
        move    x:(r7+$15),y0
        move    x:(r7+$25),x1
        move    x:(r7+$04),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,x:(r7+$04)
        move    a,x:(r7+$25)
vd_nz_open:
        move    x:(r7+$18),a
        tst     a
        beq     vd_nz_drv               ; closed → LP already wrote $04
        move    x:(r7+$25),x0
        move    x0,x:(r7+$04)
vd_nz_drv:
; FDBK + DRV on mono noise only (dry stays clean through BAL)
        move    x:(r7+$12),y0           ; FDBK
        move    x:(r7+$06),a
        move    x:(r7+$0c),x1
        sub     x1,a
        move    a,x1
        mpy     x1,y0,a
        move    x:(r7+$25),b
        add     b,a                     ; noise + FDBK·(last−dc)
        move    a,x:(r7+$24)            ; pre-DRV noise
        move    x:(r7+$13),x0           ; DRV
        move    a,x1
        mpy     x1,x0,a
        move    a,y1
        asl     #$1,a,a
        add     y1,a
        add     x1,a                    ; u
        move    #>$7fffff,x0
        cmp     x0,a
        tgt     x0,a
        move    #$80,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        tlt     x0,a
        move    a,x:(r7+$27)            ; park u
        move    a,x0
        move    x0,y1
        mpy     x0,y1,a
        move    a,y1
        mpy     x0,y1,a
        move    a,y1
        move    #>$2aaaaa,x0
        mpy     x0,y1,a                 ; u^3/3
        move    x:(r7+$27),b
        sub     a,b                     ; soft
        move    b,a
        move    x:(r7+$24),b
        sub     b,a                     ; soft − noise
        move    a,x0
        move    x:(r7+$13),y1
        mpy     x0,y1,a
        add     b,a                     ; noise + d·(soft−noise)
        move    a,x:(r7+$25)
        move    a,x:(r7+$06)
        move    a,x:(r7+$07)            ; keep R fb in step (mono noise)
        move    x:(r7+$0c),b
        sub     b,a
        move    a,x0
        move    #>$028f5c,y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$0c)
        move    a,x:(r7+$0d)
        move    x:(r7+$25),x0
        move    x0,x:(r7+$28)            ; park driven mid
; AM modulator → apply to noise only (dry never gated). Forward skips only.
; Neighbour slot: envelope only (no LFO). First slot / harness: LFO.
        move    x:(r7+$1b),a
        tst     a
        beq     vd_am_lfo               ; not nbr → skip nbr uni
        move    x:(r7+$1e),a
        asl     #$2,a,a                 ; ×4 makeup
        move    #>$7fffff,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x:(r7+$26)            ; park uni'
vd_am_lfo:
        move    x:(r7+$1b),a
        tst     a
        bne     vd_am_apply             ; nbr → skip LFO osc
        move    x:(r7+$00),a
        move    x:(r7+$10),x0
        add     x0,a
        move    a1,x:(r7+$00)
        move    a1,x0
        move    x0,x:(r7+$27)           ; SAW
        move    x0,a
        tst     a
        move    #>$7fffff,a
        move    #$80,b                   ; (short immediate: bits 23-16)
        tlt     b,a
        move    a,x:(r7+$25)            ; SQR scratch
        move    x0,a
        abs     a
        move    #$80,b                   ; (short immediate: bits 23-16)
        add     b,a
        neg     a
        move    a,y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r7+$26)            ; SIN → will become uni park
        move    x:(r7+$27),a
        move    x:(r7+$17),b
        tst     b
        move    x:(r7+$26),x0
        teq     x0,a
        move    #>$000001,x1
        cmp     x1,b
        move    x:(r7+$25),x0
        teq     x0,a
        asr     #$1,a,a
        add     #>$400000,a
        move    a,x:(r7+$26)            ; uni
vd_am_apply:
; noise'' mid = noise' · ((1−DPTH)+DPTH·uni)  — dry untouched
        move    x:(r7+$26),b            ; uni
        move    x:(r7+$11),x0           ; DPTH
        move    #>$7fffff,a
        sub     x0,a
        move    b,y0
        mpy     y0,x0,b
        add     b,a
        move    a,y0                    ; AM gain (also used for ch2)
        move    x:(r7+$28),x1           ; driven mid
        mpy     x1,y0,a
        move    a,x:(r7+$20)            ; nL
        move    y0,x:(r7+$26)           ; park gain
        move    x:(r7+$37),a            ; WID
        tst     a
        beq     vd_wid0                 ; 0 → exact mono (nR := nL)
; side: white → HPF($03) → COLR($05) → DRV (no FDBK) → same AM
        move    x:(r7+$2e),x0
        move    #>$19660d,y1
        mpy     x0,y1,b
        asr     b
        move    b0,x0
        move    x0,b
        add     #>$6ef35f,b
        move    b1,x:(r7+$2e)
        move    b1,a
        asr     #$1,a,a                 ; white2 @ -6 dB
        move    a,x1
        move    x1,x:(r7+$24)
        move    x:(r7+$14),y0
        move    x:(r7+$03),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,x:(r7+$03)
        move    x1,b
        sub     a,b
        move    b,a
        move    x:(r7+$19),b
        tst     b
        move    x:(r7+$24),x0
        teq     x0,a
        move    a,x:(r7+$25)
        move    x:(r7+$18),a
        tst     a
        bne     vd_side_open
        move    x:(r7+$15),y0
        move    x:(r7+$25),x1
        move    x:(r7+$05),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,x:(r7+$05)
        move    a,x:(r7+$25)
vd_side_open:
        move    x:(r7+$18),a
        tst     a
        beq     vd_side_drv
        move    x:(r7+$25),x0
        move    x0,x:(r7+$05)
vd_side_drv:
        move    x:(r7+$25),a
        move    a,x:(r7+$24)            ; pre-DRV side (no FDBK)
        move    x:(r7+$13),x0
        move    a,x1
        mpy     x1,x0,a
        move    a,y1
        asl     #$1,a,a
        add     y1,a
        add     x1,a
        move    #>$7fffff,x0
        cmp     x0,a
        tgt     x0,a
        move    #$80,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        tlt     x0,a
        move    a,x:(r7+$27)
        move    a,x0
        move    x0,y1
        mpy     x0,y1,a
        move    a,y1
        mpy     x0,y1,a
        move    a,y1
        move    #>$2aaaaa,x0
        mpy     x0,y1,a
        move    x:(r7+$27),b
        sub     a,b
        move    b,a
        move    x:(r7+$24),b
        sub     b,a
        move    a,x0
        move    x:(r7+$13),y1
        mpy     x0,y1,a
        add     b,a                     ; driven side
        move    a,x1
        move    x:(r7+$26),y0           ; AM gain
        mpy     x1,y0,a                 ; side after AM
; L=mid+(w/2)·side, R=mid−(w/2)·side  (mono keeps mid+LFO; w=0 → L=R=mid)
        move    x:(r7+$37),b            ; w
        asr     #$1,b,b                 ; g = w/2
        move    b,y1
        move    a,x0                    ; side
        mpy     x0,y1,a                 ; g·side
        move    a,y1
        move    x:(r7+$20),b            ; mid
        move    b,a
        add     y1,a
        move    a,x:(r7+$20)            ; outL
        move    b,a
        sub     y1,a
        move    a,x:(r7+$21)            ; outR
        move    x:(r7+$37),a
        tst     a
        bne     vd_bal
vd_wid0:
        move    x:(r7+$20),x0
        move    x0,x:(r7+$21)
vd_bal:
; BAL: wet = (1−BAL)·dry + BAL·noise''  (per channel)
        move    x:(r7+$16),y1
        move    x:(r7+$22),a
        move    x:(r7+$20),b
        sub     a,b
        move    b,x0
        mpy     x0,y1,a
        move    x:(r7+$22),b
        add     b,a
        move    a,x:(r0)
        move    x:(r7+$23),a
        move    x:(r7+$21),b
        sub     a,b
        move    b,x0
        mpy     x0,y1,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r0+n0)
        lua     (r0+$2),r0              ; the frame advance: one stereo frame, n0 stays 1
vd_end:
        rts
