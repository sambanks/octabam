; ---------------------------------------------------------------------------
; X/Y ALIAS PROBE -- do Program, X and Y really map to the same physical words
; in the shared 64K, as the reference manual says?
;
; Built with BURN=1, in DELAY SERVER's slot (BusDelay is a placeholder, so its
; 507 words are the cheapest diagnostic space on the chip).
;
; ---------------------------------------------------------------------------
; WHY: THE MANUAL AND OUR OWN RECORDS DISAGREE
; ---------------------------------------------------------------------------
; DSP56720RM.pdf, Chapter 3: "When the DSP cores access the shared memory, the
; Program, X, and Y memory addresses are mapped into same physical location,
; which means that there is no difference in accessing the shared memory from
; Program, X, or Y memory space."
;
; Commit 0f93639 concluded the OPPOSITE -- "SETTLED: X:0x30000 and Y:0x30000 do
; not alias" -- by inference: stock's allocator hands FX2 slot bases 0x30000
; and 0x34000, stock's frame setup stages parameters at X:0x30000, and stock
; does not corrupt itself when a reverb sits on track 3; therefore they cannot
; be the same words.
;
; Both cannot be right, and it matters: dsp/delay_server.asm claims all 32,768
; words from that base. If the manual is right, one premise of that argument is
; false -- most likely the X:0x30000 staging claim -- and BusDelay's memory has
; to be re-planned before a single line of it is written.
;
; A manual describes the part; it does not describe how Elektron configured it.
; So measure it on the actual machine.
;
; ---------------------------------------------------------------------------
; THE TEST
; ---------------------------------------------------------------------------
; Write a tagged, INCREMENTING word through Y. Read the same address through X.
; Do they agree?
;
; The counter matters for the same reason it did in the shared probe: nothing
; clears this window, so a CONSTANT could be matched by a value that merely
; happens to already be sitting there. A word that changes every block can only
; agree if the two accesses really are the same memory.
;
; SELF-CHECK FIRST. Before asking about X, the probe reads its own Y write back
; and demands it match. Without that, "X does not agree" is ambiguous between
; "they are different memories" and "the write never landed at all" -- and a
; probe that cannot tell those apart answers nothing.
;
; ONE INSTANCE, ONE TRACK, ONE CORE. This deliberately needs no second copy:
; dsp/shared_probe.asm established on hardware (7 Aug) that TWO instances of
; the same effect corrupt audio after ~5.45 s, on the same bank or across
; banks, whatever address they use. That fault is unexplained and it does not
; need to be explained to run this test -- it just has to be avoided.
;
; ---------------------------------------------------------------------------
; READOUT -- three states, so a broken probe cannot masquerade as a result
; ---------------------------------------------------------------------------
;   FULL LEVEL   Y written, the other space agrees -> THEY ALIAS
;   -12 dB       Y written, it disagrees          -> they do NOT alias
;   -24 dB       the Y write did not read back -> probe broken, ignore it
;   silence      not running at all
;
; ---------------------------------------------------------------------------
; ADDRESSES
; ---------------------------------------------------------------------------
; build_bus.py substitutes the one 0x30000 literal for 0x38000 on payload B, so
; this file uses it as a BASE and adds a knob-selected offset. Payload A tests
; its own half, payload B tests its own -- both are valid alias tests, and it
; costs no new build machinery.
;
; p1 ADDR picks the offset, and every target deliberately misses the FX2 slot
; bases (0x30000 / 0x34000 / 0x38000 / 0x3C000), because a slot base is exactly
; where something else is most likely to live:
;
;   0  base+0x1000     1  base+0x3000     2  base+0x5000     3  base+0x7000
;
; Four targets, one flash: if the answer differs across them, the window is not
; uniform and that is itself the finding.
; ---------------------------------------------------------------------------

init:
        rts

proc:
; ---- ADDR: base (per payload) + knob-selected offset --------------------
; p1 arrives as value<<16; >>21 leaves the top 2 bits of a 0..127 knob = 0..3.
;
; `cmp x0,a` is register-to-accumulator and encodes correctly. The
; accumulator-to-accumulator form does NOT -- dsp_asm turns `cmp b,a` into
; `maxm a,b`. See the assembler-traps memory before touching these.
        move    x:(r6+$1),a
        asr     #$15,a,a                ; -> 0..3
        move    #>$1000,y0              ; 0: base + 0x1000
        move    #>$1,x0
        cmp     x0,a
        bne     ad1
        move    #>$3000,y0
ad1:
        move    #>$2,x0
        cmp     x0,a
        bne     ad2
        move    #>$5000,y0
ad2:
        move    #>$3,x0
        cmp     x0,a
        bne     ad3
        move    #>$7000,y0
ad3:
        move    #>$30000,a              ; build_bus substitutes $38000 for B
        move    y0,x0
        add     x0,a                    ; a = the target address
        move    a,r5                    ; Y pointer
        move    a,r4                    ; X pointer -- the SAME address
        move    #>$ffffff,m5            ; both linear, and these two also space
        move    #>$ffffff,m4            ; the AGU writes from their use

; ---- build the tagged counter ------------------------------------------
; A2 is cleaned AFTER the mask, not before, and the order is the whole point:
; AND clears A1 only. Cleaning first and masking second leaves A2 holding the
; sign of the ORIGINAL garbage, and the store then limits through it -- the
; exact shape of the $83 bug that froze the instrument for fifty builds.
        move    y:(r5),a                ; whatever is there (garbage at boot)
        move    #>$1,x0
        add     x0,a
        and     #>$00ffff,a             ; keep the count
        move    a1,x0                   ; A2-clean, AFTER the mask
        move    x0,a
        move    #>$5a0000,x0
        or      x0,a                    ; tag it
        move    a,x1                    ; x1 = what we are about to write
        move    a,y:(r5)                ; WRITE, through Y

; ---- self-check: did that write actually land? -------------------------
        move    y:(r5),a
        move    x1,b
        sub     b,a                     ; `sub`, not `cmp` -- see above
        bne     wfail

; ---- THE QUESTION: does the same address agree, read through X or P? ----
; p2 SPACE picks which space to read the word back from, so ONE build asks two
; separate questions with a simple two-state readout each time, instead of one
; four-state readout nobody can judge by ear:
;
;   SPACE = 0   read back via X  -> does X alias Y? Settles the manual against
;                                   commit 0f93639, and decides whether
;                                   BusDelay's 32K claim is safe.
;   SPACE > 0   read back via P  -> does P alias Y? If it does, the shared 64K
;                                   is PROGRAM-ADDRESSABLE, and the program
;                                   space wall (11 words free) has a door in
;                                   it worth 64K.
;
; Reading P rather than JUMPING there is deliberate: it answers whether the
; memory is P-addressable without risking execution into a region we have never
; run code in. `move p:(r4),a` is the P-memory data move -- note `movem` does
; NOT assemble here, only this form does.
;
; SMALL RISK, stated plainly: if P genuinely does not extend to this address the
; read may hang rather than return garbage, the way Y:0x40000+ freezes. The
; manual's memory-map figure shows Program, X and Y all covering
; $030000-$03FFFF, so this should be safe -- but if SPACE>0 hangs the unit, that
; IS the answer (P is not accessible there) and it costs a reboot, not a flash.
        move    x:(r6+$2),a             ; SPACE knob
        asr     #$10,a,a
        tst     a
        beq     rd_x
        move    p:(r4),a                ; read back through PROGRAM memory
        bra     rd_cmp
rd_x:
        move    x:(r4),a                ; read back through X
rd_cmp:
        move    x1,b
        sub     b,a
        bne     noalias
        move    #>$7fffff,y1            ; ALIAS -- full level
        bra     gain
noalias:
        move    #>$200000,y1            ; -12 dB
        bra     gain
wfail:
        move    #>$080000,y1            ; -24 dB: the probe itself is broken

; ---- apply y1 to this track's audio ------------------------------------
; mpy x0,y1 and NOT x1,y1 -- the 56300 encodes only eight MPY operand pairs and
; x1*y1 is not one of them; dsp_asm silently emits `mpysu` instead of erroring.
;
; No `asr` after the mpy: MPY is FRACTIONAL and its shift-left is exactly what
; makes the result correctly scaled (dsp/send_client.asm multiplies a send
; level with a bare `mpy x1,y1,a`).
;
; m0 MUST be set -- r0 is WRITTEN here, not just read, and reverb_server sets
; `#>$ffffff,m0` for that reason ("audio is read and written via r0"). Left at
; whatever the previous effect happened to leave, the writes scatter to wrapped
; addresses: envelope survives, waveform does not.
gain:
        move    #>$ffffff,m0
        move    #>$1,n0
        do      n7,>gend
        move    x:(r0),x0               ; L
        mpy     x0,y1,a
        move    a,x:(r0)
        move    x:(r0+n0),x0            ; R
        mpy     x0,y1,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0                 ; next stereo frame
        move    #>$1,n0
gend:
        nop
        rts
