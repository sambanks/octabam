; CYCLES_SEQUENTIAL_LOOPS
; CYCLES_FORWARD_BRANCHES
; ---------------------------------------------------------------------------
; SHATTER -- fold, clip, crush, chaotic feedback, brickwall after MIX.
;
; Insert: frames in place at x:(r0)/x:(r0+n0), knobs from r6, state in r7.
; No bus, no buffers, no shared window.
;
;   fb  = FDBK * tone_lp * polarity      (NOT driven — drive×fb self-oscillates)
;   d   = dry * (1 + 8*DRV) + fb         DRV 0 = unity; 127 ≈ ×9 on dry only
;   f   = fold(d*(1+8*FOLD)) or d        FOLD 0 = unity skip; 1+ only louder/more fold
;   c   = hard/soft clip(f)              MODE HARD / SOFT / CHAOS
;   w   = srr then brr(c)                CRSH (LOFI2-style $400000 phase)
;   fb  = tone_lp(w)                     TONE in the loop
;   m   = dry + MIX * (w - dry)
;   out = lim(m)                         LIM brickwall after MIX; 0 = skip
;
; CHAOS: a block-rate phase advances by RATE; each wrap flips polarity (+/-1).
;
; LIM: shared current-block stereo peak limiter, one div outside sample DO.
; Ceiling = 1 - LIM*0.25/128 (LIM 0 bypass), near 0..-2.5 dBFS.
; Unity below ceiling, no makeup gain; approximately 63 ms block release.
; The second pass controls the first transient without nested DO/div.
;
; r7: $00 fb L  $01 fb R  $02 hold L  $03 hold R  $04 srr phase
;     $05 tone L  $06 tone R  $07 polarity (+1/-1)  $08 chaos phase
;     $09 srr wrap (1 this sample)  $0a brr n (0..12)  $0b srr inc
;     $0c clip thresh  $0d lim level_s  $19 lim thresh (0 = LIM off)
;     $1a lim gain  $1b mixed L  $1c mixed R  $1d block peak  $1e block start
;     $10..$18 per-block: drv, fold, clip, crsh, fdbk, mix, mode, tone, rate
; Every mpy is x0,y1 or y0,x0 (signed). No rep. init preserves r1.
; SRR phase is stored from a1 (never move a,x: -- that saturates and sticks).
; ---------------------------------------------------------------------------

init:
        clr     a
        move    a,x:(r7+$00)
        move    a,x:(r7+$01)
        move    a,x:(r7+$02)
        move    a,x:(r7+$03)
        move    a,x:(r7+$04)
        move    a,x:(r7+$05)
        move    a,x:(r7+$06)
        move    a,x:(r7+$08)
        move    a,x:(r7+$09)
        move    a,x:(r7+$0a)
        move    a,x:(r7+$0b)            ; srr inc (set each block)
        move    a,x:(r7+$0c)            ; clip thresh
        move    a,x:(r7+$0d)            ; lim level_s
        move    a,x:(r7+$19)            ; lim thresh (0 = off)
        move    a,x:(r7+$1a)            ; lim gain
        move    a,x:(r7+$1b)            ; mixed L stash
        move    a,x:(r7+$1c)            ; mixed R stash
        move    #>$7fffff,x0            ; polarity +1
        move    x0,x:(r7+$07)
        rts

proc:
; ---- knobs (mask LFO dirt) ------------------------------------------------
        move    x:(r6+$0),a             ; DRV (×8 applied in sample loop)
        and     #>$7f0000,a             ; LFO low byte must not leak
        move    a,x:(r7+$10)
        move    x:(r6+$1),a             ; FOLD
        and     #>$7f0000,a             ; LFO low byte must not arm the stage
        move    a,x:(r7+$11)
        move    x:(r6+$2),a             ; CLIP -> thresh = 1 - CLIP*0.875/128
        and     #>$7f0000,a
        move    a,x:(r7+$12)            ; raw CLIP (0 = skip stage)
        move    a,x0
        move    #>$700000,y1            ; 0.875
        mpy     x0,y1,a
        move    #>$7fffff,b
        sub     a,b
        move    #>$100000,x0            ; floor ~0.125 so it never gates to 0
        cmp     x0,b
        tlt     x0,b
        move    b,x:(r7+$0c)            ; thresh
        move    x:(r6+$3),a             ; CRSH
        and     #>$7f0000,a
        move    a,x:(r7+$13)
; BRR depth n = 1 + kn/8 (1..16), clamp 12 -- asr n / asl n keeps level
        asr     #$13,a,a                ; kn>>3 → 0..15
        add     #>$1,a
        move    #>$c,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x:(r7+$0a)
; SRR inc: $400000 = 1.0. CRSH>0 starts at $200000 (hold ~2), then
; asr by kn/16 more. Floor $008000 (~128-sample hold).
        move    x:(r7+$13),a
        and     #>$7f0000,a
        asr     #$14,a,a                ; kn>>4 → 0..7
        move    #>$200000,b             ; at least 2-sample hold
        tst     a
        beq     shc0
        asr     #$1,b,b
        move    #>$1,x0
        cmp     x0,a
        ble     shc0
        asr     #$1,b,b
        move    #>$2,x0
        cmp     x0,a
        ble     shc0
        asr     #$1,b,b
        move    #>$3,x0
        cmp     x0,a
        ble     shc0
        asr     #$1,b,b
        move    #>$4,x0
        cmp     x0,a
        ble     shc0
        asr     #$1,b,b
        move    #>$5,x0
        cmp     x0,a
        ble     shc0
        asr     #$1,b,b
        move    #>$6,x0
        cmp     x0,a
        ble     shc0
        asr     #$1,b,b
shc0:
        move    #>$008000,x0
        cmp     x0,b
        tlt     x0,b
        move    b,x:(r7+$0b)
        move    x:(r6+$4),a             ; FDBK / 2 (headroom)
        and     #>$7f0000,a
        asr     #$1,a,a
        move    a,x:(r7+$14)
        move    x:(r6+$5),a             ; MIX; 127 -> full scale
        and     #>$7f0000,a
        move    #>$7f0000,x0
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$15)
; Page 2: PARAM_PAGES §6 — slot 6/7 share $c (knob / companion), slot 8 is $d.
; Reading $6/$7/$8 left MODE/TONE/RATE dead on the unit and in dsp_host.
        move    x:(r6+$c),a             ; MODE slot 6 = $c bits 16-23
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a,x:(r7+$16)
        move    x:(r6+$c),a             ; TONE slot 7 = $c bits 8-15
        and     #>$7f00,a
        asl     #$8,a,a                 ; -> TONE<<16 like page-1 knobs
        asr     #$1,a,a                 ; /2 for lp coeff
        move    #>$040000,x0            ; floor so dark still moves
        add     x0,a
        move    a,x:(r7+$17)
        move    x:(r6+$d),a             ; RATE slot 8 = $d bits 16-23
        and     #>$7f0000,a
        asr     #$4,a,a                 ; /16 so wraps are audible
        move    #>$001000,x0
        add     x0,a
        move    a,x:(r7+$18)
; LIMIT_THRESHOLD
; ---- CHAOS polarity (block rate) ------------------------------------------
        move    x:(r7+$16),a
        move    #>$2,x0
        cmp     x0,a
        bne     sh00
        move    x:(r7+$08),a
        move    x:(r7+$18),x0
        add     x0,a
        move    a,x:(r7+$08)
        move    a1,b                    ; wrap when high bits flip through 0
        tst     b
        bpl     sh00
        move    x:(r7+$07),a
        neg     a
        move    a,x:(r7+$07)
        clr     a
        move    a,x:(r7+$08)
sh00:
        move    #$1,n0
; LIMIT_PREPARE
        do      n7,>sh16
; ---- dry * (1+8*DRV) + feedback (fb not driven) ---------------------------
        move    x:(r0),x0               ; dry L
        move    x:(r7+$10),y0           ; DRV (>=0)
        mpy     y0,x0,a                 ; DRV * dry
        asl     #$3,a,a                 ; 8 * DRV * dry
        add     x0,a                    ; dry * (1 + 8*DRV)
        move    a,b
        move    x:(r7+$00),x0           ; fb tone L
        move    x:(r7+$14),y1           ; fdbk (>=0)
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$07),y1           ; polarity (+/-1)
        mpy     x0,y1,a
        add     b,a                     ; driven dry + undriven fb
        move    a,y0
; ---- FOLD (skip at 0 = unity; else fold(v*(1+8*FOLD)) — never below unity)
        move    x:(r7+$11),a
        tst     a
        beq     sh01
        move    y0,x0                   ; v
        move    a,y1                    ; FOLD
        mpy     x0,y1,a     #$40,b      ; FOLD*v ; 0.5
        asl     #$3,a,a                 ; 8*FOLD*v
        add     x0,a                    ; v*(1+8*FOLD)  (>= v)
        add     b,a                     ; +0.5 into triangle fold
        move    a1,x1
        move    x1,a
        abs     a
        sub     b,a
        asl     a
        move    a,y0                    ; folded L in [-1,1)
sh01:
; ---- CLIP (skip at 0; leave y0 alone) ------------------------------------
        move    x:(r7+$12),a            ; raw CLIP
        tst     a
        beq     sh03
        move    x:(r7+$0c),x0           ; thresh
        move    y0,a
        abs     a
        cmp     x0,a
        tgt     x0,a
        move    y0,b
        tst     b
        bpl     sh02
        neg     a
sh02:
        move    x:(r7+$16),b            ; MODE
        move    #>$1,x0
        cmp     x0,b
        bne     sh18                    ; HARD/CHAOS
; SOFT: cubic on the hard-limited value
        move    a,x0
        mpy     x0,x0,b
        move    b,y1
        mpy     x0,y1,b
        asr     #$2,b,b
        sub     b,a
sh18:
        move    a,y0
sh03:
; ---- CRSH: SRR ($400000 phase) then BRR asr/asl --------------------------
        clr     a
        move    a,x:(r7+$09)
        move    x:(r7+$13),b
        tst     b
        beq     sh08
        move    x:(r7+$04),b
        move    x:(r7+$0b),x0
        add     x0,b
        move    #>$400000,x1
        move    b,a
        sub     x1,a
        move    a,y1
        tge     y1,b
        move    b1,x:(r7+$04)
        move    #>$0,a                  ; move #imm keeps the sub's CC (clr would not)
        move    #>$1,x0
        tge     x0,a
        move    a,x:(r7+$09)
        tst     a
        beq     sh06
        move    y0,x:(r7+$02)
sh06:
        move    x:(r7+$02),a
        move    y0,x0
        tst     a
        teq     x0,a                    ; first samples: hold still 0
        move    a,x:(r7+$02)
        move    x:(r7+$0a),y1           ; BRR n
        move    y1,b
        tst     b
        beq     sh07
        asr     y1,a,a
        asl     y1,a,a
sh07:
        move    a,y0
sh08:
; ---- feedback tone LP + MIX L ---------------------------------------------
        move    x:(r7+$05),a
        move    a,x0                   ; prev lp
        move    y0,a
        sub     x0,a                    ; in - lp
        move    a,x0                    ; (in-lp) for mpy
        move    x:(r7+$17),y1
        mpy     x0,y1,b
        move    x:(r7+$05),a            ; restore lp
        add     b,a
        move    a,x:(r7+$05)
        move    a,x:(r7+$00)
        move    x:(r0),b                ; dry L
        move    y0,a
        sub     b,a                     ; wet - dry
        move    a,x0
        move    x:(r7+$15),y1           ; MIX
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$1b)            ; mixed L stash; r0 stays on L
; ============================= R channel ===================================
; Dry R via (r0+n0); r0 stays on L until the unified write below.
        move    x:(r0+n0),x0            ; dry R
        move    x:(r7+$10),y0           ; DRV
        mpy     y0,x0,a
        asl     #$3,a,a                 ; 8 * DRV * dry
        add     x0,a                    ; dry * (1 + 8*DRV)
        move    a,b
        move    x:(r7+$01),x0
        move    x:(r7+$14),y1
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$07),y1
        mpy     x0,y1,a
        add     b,a                     ; driven dry + undriven fb
        move    a,y0
        move    x:(r7+$11),a
        tst     a
        beq     sh09
        move    y0,x0                   ; v
        move    a,y1                    ; FOLD
        mpy     x0,y1,a     #$40,b      ; FOLD*v ; 0.5
        asl     #$3,a,a                 ; 8*FOLD*v
        add     x0,a                    ; v*(1+8*FOLD)
        add     b,a
        move    a1,x1
        move    x1,a
        abs     a
        sub     b,a
        asl     a
        move    a,y0
sh09:
; CLIP R
        move    x:(r7+$12),a
        tst     a
        beq     sh11
        move    x:(r7+$0c),x0
        move    y0,a
        abs     a
        cmp     x0,a
        tgt     x0,a
        move    y0,b
        tst     b
        bpl     sh10
        neg     a
sh10:
        move    x:(r7+$16),b
        move    #>$1,x0
        cmp     x0,b
        bne     sh19
        move    a,x0
        mpy     x0,x0,b
        move    b,y1
        mpy     x0,y1,b
        asr     #$2,b,b
        sub     b,a
sh19:
        move    a,y0
sh11:
; CRSH R (phase/wrap already done on L)
        move    x:(r7+$13),b
        tst     b
        beq     sh15
        move    x:(r7+$09),a
        tst     a
        beq     sh13
        move    y0,x:(r7+$03)
sh13:
        move    x:(r7+$03),a
        move    y0,x0
        tst     a
        teq     x0,a
        move    a,x:(r7+$03)
        move    x:(r7+$0a),y1
        move    y1,b
        tst     b
        beq     sh14
        asr     y1,a,a
        asl     y1,a,a
sh14:
        move    a,y0
sh15:
        move    x:(r7+$06),a
        move    a,x0                    ; prev lp
        move    y0,a
        sub     x0,a                    ; in - lp
        move    a,x0
        move    x:(r7+$17),y1
        mpy     x0,y1,b
        move    x:(r7+$06),a
        add     b,a
        move    a,x:(r7+$06)
        move    a,x:(r7+$01)
        move    x:(r0+n0),b             ; dry R (r0 still on L)
        move    y0,a
        sub     b,a
        move    a,x0
        move    x:(r7+$15),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$1c)            ; mixed R stash (LIM)
; LIMIT_COLLECT
        move    x:(r7+$1b),a
        move    a,x:(r0)+n0
        move    x:(r7+$1c),a
        move    a,x:(r0)+
sh16:
        nop
; LIMIT_FINISH
        rts
