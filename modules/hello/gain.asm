; ---------------------------------------------------------------------------
; HELLO WORLD -- a linear volume knob. The reference minimal insert.
;
; A per-track INSERT: reads this track's stereo frames from x:(r0) (L) and
; x:(r0+n0) (R) and writes them back IN PLACE, warpfold's exact convention.
; No bus role, no shared window, no absolute Y, and -- unlike every other
; module -- no r7 state at all: the effect is stateless, so nothing persists
; and the two-track-freeze discipline has nothing to protect.
;
; ---- knobs ----------------------------------------------------------------
;   p0 GAIN  x:(r6+$0)  val<<16, so as a Q23 fraction it is raw/128
;            (0 .. 0.9921875). out = in * GAIN/128.
;            GAIN >= $7f0000 takes the early-out below: frames are already
;            in place, so unity gain is "touch nothing" -- a BIT-EXACT
;            passthrough, and the render harness's null gate. `bge`, not
;            `beq`, so any nonzero low bits in the knob word cannot defeat
;            it. GAIN=0 is exact silence (zero coefficient through mpy).
;
; ---- arithmetic notes -----------------------------------------------------
; * The one mpy is `mpy x0,y1` -- one of the two operand orders dsp_asm is
;   known to encode SIGNED (CLAUDE.md). The SAMPLE sits in x0 and goes
;   negative every other half-cycle; a silent mpysu here is precisely the
;   stock AMF bug class, and the render's negative-sample check is aimed
;   at it. Audit by disassembly, not by reading this source.
; * mpy is the toolchain's plain product (warpfold's DRV block is the
;   precedent: gq = 0.125 + DRV*0.875, mpy with no shift). in (-1,1) times
;   g [0,1) needs no pre-halve and no asl.
; * No logical ops anywhere, so no A1/A2 staleness to clean. The only
;   accumulator loads are plain moves.
; ---------------------------------------------------------------------------

init:
        rts                             ; stateless: nothing to seed

proc:
; ---- per-block: fetch GAIN, take the unity early-out ----------------------
        move    x:(r6+$0),a             ; GAIN, val<<16, positive
        move    #>$7f0000,x0
        cmp     x0,a                    ; a - $7f0000
        bge     hw_unity                ; raw 127 (or above): exact pass
        move    a,y1                    ; g = GAIN/128, Q23, in [0, 0.992)

; ---- per-frame: out = in * g, both channels, in place ---------------------
        move    #>$1,n0
        do      n7,>hw_end
        move    x:(r0),x0               ; L
        mpy     x0,y1,a                 ; signed encoding order
        move    a,x:(r0)                ; L in place
        move    x:(r0+n0),x0            ; R
        mpy     x0,y1,a
        move    a,x:(r0+n0)             ; R in place
        move    #>$2,n0
        move    (r0)+n0                 ; next stereo frame
        move    #>$1,n0
hw_end:
        nop
        rts

hw_unity:
        rts                             ; in place already: unity is a no-op
