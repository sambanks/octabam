; ---------------------------------------------------------------------------
; Nimbus -- a Mutable-Instruments-Clouds-flavoured granular texture insert.
;
; Same insert contract as the other outsider modules (r0 frames in place,
; knobs from r6, state in this instance's r7 block) -- plus, uniquely, a
; real BUFFER: the mono input sum records continuously into the core-private
; FX2-instance region Y:0x4000..0xBFFF (32,768 words = 743 ms @44.1k), and
; four unity-rate grains read it back.
;
; ⚠️ ONE NIMBUS PER CORE: that buffer is fixed, not per-instance. Safe in an
; insert remix (every other module is zero-Y-footprint -- the same argument
; BUS.md's hardcoded-base probe made), wrong the moment two instances on one
; core both select Nimbus. The legacy-stock-FX2 caveat from PLAN.md applies
; here exactly as it does to ChonVerb's tank.
;
; ---- structure ------------------------------------------------------------
; * Grain g's phase is (age + g*G/4) & (G-1): ONE age serves all four (the
;   GRAIN architecture), so a single advance moves the cloud, and the count
;   is EVEN -- odd grain counts ripple at the grain rate (BongDelay, 12 Aug).
;   Grains 0/2 sum to L, 1/3 to R: per channel two triangle windows at a
;   half-period offset, which sum to constant power by construction.
; * A grain reads W - (POSbase + s_g + G + 1 + phase): it plays FORWARD at unity
;   rate relative to the moving write head, always at least POSbase+s_g+1
;   behind it, so no head ever reads ahead of the write.
; * s_g is a per-grain scatter LATCHED AT THAT GRAIN'S OWN WRAP from the
;   xorshift PRNG (23-bit, shifts 15/15/8 -- BongDelay's, verbatim, with its
;   A2-clean dances). The latch is a branch over two moves, so no Tcc shares
;   condition codes with anything (the GRAIN 5d trap).
; * FRZE=1 stops the write head (write AND advance): the last 743 ms becomes
;   a static cloud, and every read stays behind the frozen W by construction.
; * WARM-UP, ChonVerb's tagged-counter idiom (tag $2d0000|count at r7+$31,
;   a garbage tag restarts at zero): the first 256 blocks clear 128 words
;   each -- the whole buffer -- zero the states, seed the PRNG, and leave the
;   frames untouched (pure dry out). Boot garbage is never played.
;
; ---- knobs ----------------------------------------------------------------
;   p0 POS   read-back distance base = 1024 + POS*120 (23..370 ms behind W)
;   p1 SIZE  grain length, power of two: <32: 1024  <64: 2048  <96: 4096
;            else 8192 samples (23/46/93/186 ms). Power-of-two G is what
;            makes every wrap a mask and the window gain one multiply.
;   p2 DENS  scatter depth: each grain's latched start offset is
;            prng * DENS, up to ~4064 samples (92 ms)
;   p3 MIX   out = dry + MIX*(wet - dry); MIX=0 is an exact passthrough
;   p7 FRZE  0 recording, 1 FROZEN (slot-7 companion, ChonVerb's decode)
;
; ---- r7 slots -------------------------------------------------------------
;   $20 m        $21 scat depth Q23   $22 POSbase    $23 G-1 mask
;   $24 G/4      $26 2^(23-k) window multiplier ($25 unused)
;   $27 FRZE     $28 write head W (PERSISTENT, masked on load AND save)
;   $29 age      (PERSISTENT, masked by G-1 every sample)
;   $2a..$2d latched scatter s_0..s_3 (PERSISTENT, integers 0..4064)
;   $2e PRNG state (PERSISTENT)       $2f wet L    $30 wet R (per sample)
;   $31 warm tag|count (PERSISTENT)   $32 mono in  $33 scatter candidate
;   $34 warm count stash (per call)
;
; ---- the window is one multiply, and a NEW TRAP: a0 IS NOT a1/2^24 -------
; phase is a small positive INTEGER (0..G-1, G = 2^k). Multiplying it by
; 2^(23-k) and reading the accumulator's LOW word gives a ramp that reaches
; bit 23 exactly at phase = G/2; read back as a SIGNED 24-bit word (move
; a0,x0 / move x0,a sign-extends, so A2 is clean) that is 0 -> +1 over the
; first half and -1 -> 0 over the second, and `abs` folds it into a TRIANGLE
; peaking at G/2. One multiply, one abs, no per-size shift chain.
;
; ⚠️ THE MULTIPLIER IS 2^(23-k) AND NOT 2^(24-k), because **a0 EXPOSES THE
; FRACTIONAL LEFT SHIFT THAT a1 HIDES**. `mpy` aligns the Q46 product into
; Q47, so reading a1 gives the plain fractional product -- which is why the
; project's standing note that "mpy does not double here" is true and stays
; true for every other module, all of which read a1. Reading a0 sees the RAW
; 48-bit content, shift included, so the effective integer scale is 2x the
; multiplier. Getting this wrong is invisible: 2^(24-k) assembles, renders,
; and makes a plausible granular noise -- it just runs the window at DOUBLE
; RATE, so the two grains of a pair land in phase instead of interleaving.
; MEASURED, 29 Aug 2026: DC in came back with 2x-DC ripple on a DC mean
; (the double-rate signature) and went flat when the multiplier was halved.
; The DC gate is what pins this: two triangles a half period apart sum to
; EXACTLY 1, so DC in must come back flat and unrippled.
;
; Every mpy is `mpy x0,y1` (known-signed); audited by disassembly.
;
; ; CYCLES_FORWARD_BRANCHES -- the five conditional branches in the sample
; loop (the freeze gate and the four per-grain scatter latches) are all
; FORWARD skips, so tools/cycle_count.py may price the fall-through path and
; call the result a ceiling. It enforces the forward part rather than taking
; this word for it.
; ---------------------------------------------------------------------------

init:
        rts

proc:
        move    #>$ffffff,m1
        move    #>$ffffff,m2

; ---- warm-up: ChonVerb's tagged counter, buffer-sized ---------------------
        move    x:(r7+$31),a
        move    #>$fffe00,x0
        and     x0,a                    ; tag field -- AND cleans A1 only
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        move    #>$2d0000,x0
        cmp     x0,a
        beq     nb_wtag
        clr     a                       ; garbage tag: warm-up starts at 0
        bra     nb_wrun
nb_wtag:
        move    x:(r7+$31),a
        move    #>$1ff,x0
        and     x0,a
        move    a1,x0
        move    x0,a                    ; the count, A2-clean
        move    #>$100,x0
        cmp     x0,a
        bge     nb_wdone                ; warmed: run the grains
nb_wrun:
        move    a,x:(r7+$34)            ; count, for the save below
        asl     #$7,a,a                 ; count*128: 256 blocks x 128 = 32,768
        add     #>$4000,a               ; = the whole buffer
        move    a,r1
        clr     b
        do      #128,>nb_wz
        move    b,y:(r1)+
nb_wz:
        nop
        move    b,x:(r7+$28)            ; W = 0
        move    b,x:(r7+$29)            ; age = 0
        move    b,x:(r7+$2a)            ; scatters = 0
        move    b,x:(r7+$2b)
        move    b,x:(r7+$2c)
        move    b,x:(r7+$2d)
        move    #>$345678,a             ; PRNG seed: any nonzero word
        move    a,x:(r7+$2e)
        move    x:(r7+$34),a
        add     #>$1,a
        add     #>$2d0000,a             ; tag | count+1
        move    a,x:(r7+$31)
        rts                             ; frames untouched: pure dry out
nb_wdone:

; ---- per-block knob decode ------------------------------------------------
        move    x:(r6+$3),x0            ; m = MIX
        move    x0,x:(r7+$20)
        move    x:(r6+$2),x0            ; scat depth, straight Q23
        move    x0,x:(r7+$21)
; POSbase = 1024 + POS*120  (val*128 - val*8)
        move    x:(r6+$0),a
        asr     #$10,a,a                ; the integer knob value 0..127
        move    a,b
        asl     #$7,a,a                 ; val*128
        asl     #$3,b,b                 ; val*8
        sub     b,a
        add     #>$400,a
        move    a,x:(r7+$22)
; SIZE -> G family: the wrap mask, G/4 (the grain-to-grain offset)
; and the window multiplier 2^(23-k)
        move    x:(r6+$1),a
        asr     #$10,a,a
        move    #>$20,x0
        cmp     x0,a
        blt     nb_s10
        move    #>$40,x0
        cmp     x0,a
        blt     nb_s11
        move    #>$60,x0
        cmp     x0,a
        blt     nb_s12
        move    #>$1fff,x0              ; G = 8192
        move    x0,x:(r7+$23)
        move    #>$800,x0
        move    x0,x:(r7+$24)
        move    #>$400,x0              ; 2^(23-13)
        move    x0,x:(r7+$26)
        bra     nb_sdone
nb_s12:
        move    #>$fff,x0               ; G = 4096
        move    x0,x:(r7+$23)
        move    #>$400,x0
        move    x0,x:(r7+$24)
        move    #>$800,x0              ; 2^(23-12)
        move    x0,x:(r7+$26)
        bra     nb_sdone
nb_s11:
        move    #>$7ff,x0               ; G = 2048
        move    x0,x:(r7+$23)
        move    #>$200,x0
        move    x0,x:(r7+$24)
        move    #>$1000,x0             ; 2^(23-11)
        move    x0,x:(r7+$26)
        bra     nb_sdone
nb_s10:
        move    #>$3ff,x0               ; G = 1024
        move    x0,x:(r7+$23)
        move    #>$100,x0
        move    x0,x:(r7+$24)
        move    #>$2000,x0             ; 2^(23-10)
        move    x0,x:(r7+$26)
nb_sdone:
; FRZE: slot-7 companion (ChonVerb's decode); any nonzero value freezes.
; The marker is the DEV freeze hook's splice point (NFRZAT=n, build_bus.py's
; _dev_hooks): it replaces the decoded value in `a` with a block counter's
; verdict, so a render can capture real material and THEN freeze it. A
; static freeze can only ever hold the silence the warm-up just cleared.
        move    x:(r6+$c),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
; NFRZ_OVERRIDE
        move    a,x:(r7+$27)

; ---- per-sample loop ------------------------------------------------------
        move    #>$1,n0
        do      n7,>nb_end
; mono in
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$32)
; PRNG advance (BongDelay's 23-bit xorshift 15/15/8, verbatim)
        move    x:(r7+$2e),a
        move    a1,x0
        asl     #$f,a,a
        and     #>$7fffff,a
        eor     x0,a
        move    a1,x0
        move    x0,a
        asr     #$f,a,a
        eor     x0,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        and     #>$7fffff,a
        eor     x0,a
        move    a1,x0
        move    x0,a                    ; A2 clean before the store
        move    a,x:(r7+$2e)
; scatter candidate = prng * DENS, scaled to 0..4064 samples
        move    a,x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a                 ; fraction in [0,1)
        asr     #$b,a,a                 ; -> integer samples, <= 4064
        move    a1,x0
        move    x0,a
        and     #>$fff,a                ; belt and braces: it IS 0..4064
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$33)
; record + advance W, unless FROZEN
        move    x:(r7+$27),a
        tst     a
        bne     nb_fz
        move    x:(r7+$28),a
        and     #>$7fff,a               ; mask on LOAD -- boot garbage dies
        move    a1,x0
        move    x0,a
        add     #>$4000,a
        move    a,r1
        move    x:(r7+$32),x0
        move    x0,y:(r1)               ; buffer[W] = mono
        move    x:(r7+$28),a
        add     #>$1,a
        and     #>$7fff,a               ; mask on SAVE too
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$28)
nb_fz:
; age advance, masked by G-1 (also swallows size changes and boot garbage)
        move    x:(r7+$29),a
        add     #>$1,a
        move    x:(r7+$23),x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$29)
; clear the wet accumulators
        clr     a
        move    a,x:(r7+$2f)
        move    a,x:(r7+$30)

; ---- grain 0 (L, offset 0) ------------------------------------------------
        move    x:(r7+$29),a            ; phase = age (already masked)
        tst     a
        bne     nb_g0
        move    x:(r7+$33),x0           ; wrap: latch this grain's scatter
        move    x0,x:(r7+$2a)
nb_g0:
        move    a,x1                    ; phase, kept for the dist calc
        move    a,x0
        move    x:(r7+$26),y1           ; 2^(23-k)
        mpy     x0,y1,a                 ; a0 = wrap(2*phase/G), signed Q23
        move    a0,x0
        move    x0,a                    ; reloaded clean: A2 consistent
        abs     a
        move    a,y1                    ; window gain = |wrap(2*phase/G)|
        move    x:(r7+$22),a            ; dist = POSbase + s_g + G + 1 + phase
        move    x:(r7+$2a),x0
        add     x0,a
        move    x:(r7+$23),x0
        add     x0,a
        add     #>$1,a
        add     x1,a                    ; + phase: unity is a FIXED tap behind
                                        ; the moving head (3 Sep 2026; was
                                        ; `- phase`, an octave up -- README)
        move    a,x0
        move    x:(r7+$28),a
        sub     x0,a                    ; W - dist
        and     #>$7fff,a
        move    a1,x0
        move    x0,a
        add     #>$4000,a
        move    a,r2
        move    y:(r2),x0
        mpy     x0,y1,a                 ; grain sample * window
        move    x:(r7+$2f),b
        add     b,a
        move    a,x:(r7+$2f)            ; wet L +=
; ---- grain 1 (R, offset G/4) ----------------------------------------------
        move    x:(r7+$29),a
        move    x:(r7+$24),x0
        add     x0,a
        move    x:(r7+$23),x0
        and     x0,a
        move    a1,x0
        move    x0,a
        tst     a
        bne     nb_g1
        move    x:(r7+$33),x0
        move    x0,x:(r7+$2b)
nb_g1:
        move    a,x1
        move    a,x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        move    a0,x0
        move    x0,a
        abs     a
        move    a,y1
        move    x:(r7+$22),a
        move    x:(r7+$2b),x0
        add     x0,a
        move    x:(r7+$23),x0
        add     x0,a
        add     #>$1,a
        add     x1,a                    ; + phase: unity is a FIXED tap behind
                                        ; the moving head (3 Sep 2026; was
                                        ; `- phase`, an octave up -- README)
        move    a,x0
        move    x:(r7+$28),a
        sub     x0,a
        and     #>$7fff,a
        move    a1,x0
        move    x0,a
        add     #>$4000,a
        move    a,r2
        move    y:(r2),x0
        mpy     x0,y1,a
        move    x:(r7+$30),b
        add     b,a
        move    a,x:(r7+$30)            ; wet R +=
; ---- grain 2 (L, offset G/2) ----------------------------------------------
        move    x:(r7+$29),a
        move    x:(r7+$24),x0
        add     x0,a
        add     x0,a
        move    x:(r7+$23),x0
        and     x0,a
        move    a1,x0
        move    x0,a
        tst     a
        bne     nb_g2
        move    x:(r7+$33),x0
        move    x0,x:(r7+$2c)
nb_g2:
        move    a,x1
        move    a,x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        move    a0,x0
        move    x0,a
        abs     a
        move    a,y1
        move    x:(r7+$22),a
        move    x:(r7+$2c),x0
        add     x0,a
        move    x:(r7+$23),x0
        add     x0,a
        add     #>$1,a
        add     x1,a                    ; + phase: unity is a FIXED tap behind
                                        ; the moving head (3 Sep 2026; was
                                        ; `- phase`, an octave up -- README)
        move    a,x0
        move    x:(r7+$28),a
        sub     x0,a
        and     #>$7fff,a
        move    a1,x0
        move    x0,a
        add     #>$4000,a
        move    a,r2
        move    y:(r2),x0
        mpy     x0,y1,a
        move    x:(r7+$2f),b
        add     b,a
        move    a,x:(r7+$2f)
; ---- grain 3 (R, offset 3G/4) ---------------------------------------------
        move    x:(r7+$29),a
        move    x:(r7+$24),x0
        add     x0,a
        add     x0,a
        add     x0,a
        move    x:(r7+$23),x0
        and     x0,a
        move    a1,x0
        move    x0,a
        tst     a
        bne     nb_g3
        move    x:(r7+$33),x0
        move    x0,x:(r7+$2d)
nb_g3:
        move    a,x1
        move    a,x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        move    a0,x0
        move    x0,a
        abs     a
        move    a,y1
        move    x:(r7+$22),a
        move    x:(r7+$2d),x0
        add     x0,a
        move    x:(r7+$23),x0
        add     x0,a
        add     #>$1,a
        add     x1,a                    ; + phase: unity is a FIXED tap behind
                                        ; the moving head (3 Sep 2026; was
                                        ; `- phase`, an octave up -- README)
        move    a,x0
        move    x:(r7+$28),a
        sub     x0,a
        and     #>$7fff,a
        move    a1,x0
        move    x0,a
        add     #>$4000,a
        move    a,r2
        move    y:(r2),x0
        mpy     x0,y1,a
        move    x:(r7+$30),b
        add     b,a
        move    a,x:(r7+$30)

; ---- mix: out = dry + m*(wet - dry), per channel --------------------------
        move    x:(r7+$2f),a            ; wet L
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r7+$30),a            ; wet R
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
nb_end:
        nop
        rts
