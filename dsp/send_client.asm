; ---------------------------------------------------------------------------
; BUS.md task 7: SEND client stub.
;
; Two knobs, page 1: x:(r6+0) = ->DELAY level, x:(r6+1) = ->REVERB level.
; Dry, parallel taps -- SEND never touches its own audio buffer at all, so it
; is the zero-footprint client both bus servers rely on (see BUS.md's Memory
; section and dsp/probe_hardcoded_base.asm, which proved a hardcoded-base
; server can safely encroach on a neighbour's real per-instance slot only
; because whatever really owns that slot is SEND and never writes to it).
;
; ---- shared absolute-Y bus scratch (>= 0x800, safe in both payloads, DSP.md
; section 11) -- this layout is shared with REVERB SERVER / DELAY SERVER and
; must stay identical across dsp/send_client.asm, and whatever tasks 8/9
; build, or the buses will not agree on where anything lives:
;
;   Y:0x900            this block's WRITE OFFSET into the accumulators below:
;                       0, 16, 32 or 48 -- the buffer index ALREADY SCALED by
;                       the 16-word buffer stride. Masked on load AND save
;                       (REVERB.md's write-phase rule) since it may start as
;                       boot garbage; here the mask that does the modulo does
;                       the sanitising too, for free.
;
;                       ⚠️ FOUR ACCUMULATOR BUFFERS, NOT TWO, AND THAT IS THE
;                       WHOLE CROSS-CORE RACE FIX (docs/XBUS.md step 3;
;                       hardware-confirmed 17 Aug 2026 by moving BongDelay
;                       between tracks 1 and 4, which killed the stutter --
;                       a dispatch-position dependency no algorithmic cause
;                       has). TWO CANNOT BE MADE SAFE AT ANY CLEAR TIME: at
;                       every instant one buffer is the write target and the
;                       other the read target, so the only buffer that can be
;                       cleared is the one transitioning read -> write, and
;                       that transition IS the flip a skewed reader on the
;                       other core may still be inside. With four, a buffer is
;                       written at block n, rests at n+1, read at n+2, rests
;                       at n+3 and is cleared again at n+4 -- a full idle
;                       block between the reader and the housekeeper on BOTH
;                       sides, so either core may lead the other by up to a
;                       block and still never touch the same words.
;
;                       Four rather than three because the count is a power of
;                       two: the rotation is `+16 & $30` and the read offset is
;                       `+32 & $30`, two instructions each with no compare and
;                       no conditional transfer -- CHEAPER than the two-buffer
;                       code it replaces, where three needs a clamp. Three
;                       would also tolerate ±1 block; it just costs more and
;                       lets illegal boot garbage through the modulo.
;
;                       ⚠️ It held the bare index 0/1 until 17 Aug 2026. Every
;                       consumer then multiplied by 16 (`asl #$4`) to get an
;                       address, and every one of them re-derived the other
;                       buffer as `1 - parity` -- which hard-codes the ROTATION
;                       LENGTH into nine sites across three files that must
;                       stay identical. Storing the scaled offset is what made
;                       going to four buffers a change the housekeeper makes
;                       alone.
;   Y:0x901..0x940      REVERB bus accumulator, FOUR buffers of 16 words (one
;                       word per sample slot within a block), at +0/+16/+32/+48
;   Y:0x941..0x960      REVERB bus wet, TWO buffers          (SERVER writes,
;                                                             SEND never reads)
;   Y:0x961..0x9a0      DELAY  bus accumulator, FOUR buffers of 16 words
;   Y:0x9a1..0x9c0      DELAY  bus wet, TWO buffers
;                       ⚠️ THE WET BUFFERS STAY AT TWO. Nothing reads them --
;                       they are a hook for BUS.md task 10's cross-bus reader
;                       and are write-only today -- so they cannot carry a
;                       race, and giving them four would have pushed the layout
;                       past Y:0x9ff. That matters: build_bus.py relocates this
;                       scratch by a BLANKET regex over `$9xx` literals, so a
;                       layout that outgrows the 0x900 page would need the
;                       substitution widened, which is exactly the class of
;                       change CLAUDE.md's trap list is about. Their write
;                       offset is therefore masked to `& $10` at the two sites
;                       that address them, and nowhere else.
;   Y:0x9c1             DELAY SERVER role owner (lock)
;   Y:0x9c2             REVERB SERVER role owner (lock)
;   Y:0x9c3..0x9c6      REVERB send COUNT, one per accumulator buffer -- how
;                        many SEND clients wrote that buffer this block.
;                        Indexed by the same rotation as the accumulators,
;                        because the server reads LAST block's sum and so needs
;                        LAST block's count. The server divides by it, so N
;                        tracks sending at full drive the reverb exactly as hard
;                        as one track does, and the shared accumulator can no
;                        longer be summed into its rail.
;                        ⚠️ One word per buffer where the accumulators have
;                        sixteen, so these are the ONLY sites that scale the
;                        offset back down to a bare index (`asr #$4`).
;   Y:0x9c7..0x9ca      DELAY send COUNT, one per accumulator buffer -- the same
;                        mechanism for the DELAY bus (landed with BongDelay's
;                        auto-gain). Every DELAY-bus writer registers here:
;                        SEND (this file) and REVERB SERVER's ->DEL send, both
;                        unconditionally, because both write the accumulator
;                        unconditionally (zeros count too).
;   Y:0x9cb..0x9d2      DELAY SERVER's 1/N reciprocal table, rebuilt by it
;                        each block. Lives in the shared scratch because the
;                        delay's own half-window is entirely line buffer.
;                        Nobody else reads or writes these eight words.
;
;   The layout ends at Y:0x9d2 -- 211 words, from 144 before the fourth
;   buffer. Under XBUS it relocates whole to 0x36000..0x360d2.
;
; Latency, pinned per BUS.md: every block, whichever track is "position 0"
; (r7 == 0x6200 -- the FIRST FX2 dispatched in this bank, fixed by hardware
; order regardless of which of SEND/DELAY SERVER/REVERB SERVER it is running,
; DSP.md section 11's instance table) advances the rotation and clears the NEW
; write-target buffers, before anyone -- including itself -- accumulates into
; them this block. Every other track just reads whatever rotation that leaves.
; This makes every track's send land in the SAME buffer every block and read a
; fully-summed, one-block-old buffer back, regardless of dispatch order -- the
; alternative BUS.md rejected, where whoever runs first each block sees stale
; data and whoever runs last sees fresh.
;
; The READ target is two buffers behind the write target, not one. With four
; buffers that is what puts an idle block on each side of the reader (see the
; layout note above); with two it was forced, since "the other one" was the
; only choice there was. The cost is one extra block of bus latency -- 16
; samples, ~0.36 ms -- against a mechanism whose whole job is to be a block
; late already.
;
; No stash, no read of x:>$213 anywhere: SEND's own per-instance table entry
; is irrelevant, because SEND never uses it for anything.
; ---------------------------------------------------------------------------

init:
        rts

proc:
; ---- split-aware frame offset (BUS.md fix, found while wiring the REVERB
; SERVER): a track's proc() runs TWICE in a block that has a nonzero split
; (dsp/reverb89.asm's dispatcher note, reproduced here since this file has
; no other comment on it) -- a=0 first for frames [0,split), then always
; a=1 for [split,16). Naively gating position-0's flip on "r7==0x6200"
; alone flips the shared parity ONCE PER CALL, i.e. TWICE in a split block,
; which cancels itself out and silently desyncs the bus. And without an
; offset, every call's per-sample ACC/WET writes start back at index 0,
; so a split a=1 call stomps the START of the block instead of continuing
; from where a=0 left off.
;
; x:(r7+$67) ends this section holding the correct write offset for THIS
; call (0 if it is the first dispatch of the block -- either the a=0 call,
; or the a=1 call when there was no a=0 this block -- else the stashed
; split point). x:(r7+$65)/(r7+$66) are private bookkeeping, consumed by
; the a=1 call that matches an a=0.
        move    a,x:(r7+$14)             ; stash the dispatcher's incoming call
                                          ; flag before it's clobbered: 0 for
                                          ; a=0 (first sub-block), left-aligned
                                          ; $010000 for a=1 (reverb89.asm's
                                          ; same idiom, r7+$14)
        clr     a
        move    a,x:(r7+$67)             ; default: offset 0 (first call)
        move    x:(r7+$14),a
        tst     a
        bne     bus_a1
        move    #>$1,a
        move    a,x:(r7+$65)             ; "a=0 ran this block"
        move    n7,a
        and     #>$f,a                   ; same mask on the way in
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$66)             ; stash split for the matching a=1
        bra     bus_off_done
bus_a1:
; COLD-BOOT SAFETY. These three slots hold boot garbage the first time an
; instance runs, and x:(r7+$67) feeds straight into r1/r2 as a Y pointer
; below -- an unmasked garbage value there makes the per-sample loop write
; through a wild address, which hangs the DSP. Reproduced on hardware:
; selecting SEND on any track from a clean boot froze the unit. Same class
; as DSP.md's masked-garbage AGU saturation, so the same discipline applies
; -- mask AND A2-clean every one of them before use.
        move    x:(r7+$65),a
        and     #>$ff,a                  ; flag field only
        move    a1,x0
        move    x0,a                     ; A2-clean before the compare
        move    #>$1,x0
        cmp     x0,a                     ; EXACTLY 1, not merely nonzero:
        bne     bus_off_done             ; garbage is unlikely to be 1, where
                                         ; "nonzero" accepts almost any garbage
        clr     a
        move    a,x:(r7+$65)             ; consume the flag
        move    x:(r7+$66),a
        and     #>$f,a                   ; a split point is 0..15 by
        move    a1,x0                    ; construction, so this cannot narrow
        move    x0,a                     ; a legitimate value -- it only makes
        move    a,x:(r7+$67)             ; garbage harmless
bus_off_done:

; ---- position-0 housekeeping: flip parity, clear the new write targets ---
; Gated on offset==0 too (not just r7==0x6200): only the FIRST dispatch of
; position-0's block may flip, so a split block flips exactly once, on
; whichever call that is.
; Housekeeping is normally done by position 0 (r7 == 0x6200, the bank's first
; FX2 call). That alone breaks the moment the first track's FX2 is NONE: our
; code never runs there, so nobody flips the parity or clears the
; accumulators, and the bus saturates. NONE became selectable with the task-11
; menu, so this is reachable in ordinary use.
;
; Self-healing election instead. Position 0 still housekeeps whenever it runs.
; Any other instance takes over if it sees that the parity has NOT changed
; since the last time it ran -- which can only mean nobody housekept in
; between. Costs one r7 word (the parity this instance last saw) and no new
; global signal, so it needs nothing the bus does not already have.
;
; Gated on the split offset FIRST: only a block's first call may housekeep, so
; a split block's second call can never flip a second time -- the same trap
; the original position-0 code was written around.
; XBUS_GATE -- build_bus.py substitutes a payload gate here when XBUS=1.
; A shared-memory bus is housekept by ONE core only: both cores number their
; own instances from zero, so each core's position 0 believes it is the
; housekeeper and they would flip the shared parity TWICE a block, cancelling
; out and silently desyncing the bus -- the same trap the split-call gate
; below was written around, one level up. Payload B is sent straight to
; notfirst, so it still finds this block's write targets but never elects.
; Inert in a normal build: it is a comment.
        move    x:(r7+$67),a
        tst     a
        bne     notfirst                ; not this block's first call
        move    r7,a
        move    #>$6200,x0
        cmp     x0,a
        beq     bus_dohk                ; position 0: always the housekeeper
        move    #>$30,x0
        move    y:>$900,a
        and     x0,a
        move    a1,x0
        move    x0,a                    ; offset now, A2-clean
        move    x:(r7+$68),x0
        cmp     x0,a
        bne     bus_seen                ; it moved: someone else housekept
bus_dohk:                               ; nobody did -- take over this block

        move    y:>$900,a
        move    #>$10,x0
        add     x0,a                     ; advance one buffer
        move    #>$30,x0
        and     x0,a                     ; mod 4 -- and the SAME mask sanitises
                                          ; boot garbage, which is why four
                                          ; buffers cost less than three
        move    a,y:>$900
        move    a,x1                     ; x1 = the NEW offset, live until the
                                          ; count reset below
        move    a,x0                     ; x0 = offset into this block's buffers
        move    #>$901,a
        add     x0,a
        move    a,r1                     ; r1 = REVERB ACC[new] base
        move    #>$961,b
        add     x0,b
        move    b,r2                     ; r2 = DELAY  ACC[new] base
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        clr     a
        move    #>16,y0
        do      y0,>zclr
        move    a,y:(r1)+
        move    a,y:(r2)+
zclr:
        nop
; ---- reset the new write buffer's SEND COUNT, alongside its accumulators ----
; y:>$900 already holds the NEW offset (written just above), so this indexes the
; same buffer the loop just cleared. A2-cleaned before it becomes an address,
; per the standing rule -- a garbage value here is a wild Y write.
; The counts are ONE word per buffer where the accumulators are sixteen, so
; this is the one consumer that wants the bare index and has to scale the
; offset back DOWN. x1 holds the NEW offset from the rotation above, so this
; no longer re-reads y:>$900.
        move    x1,a
        asr     #$4,a,a                 ; offset -> buffer index (0..3)
        move    a1,x0
        move    x0,a
        move    #>$9c3,x0
        add     x0,a
        move    a,r3
        move    #>$ffffff,m3
        clr     a
        move    a,y:(r3)                ; REVERB count = 0
        move    #4,n3                   ; SHORT immediate: 1 word (address reg).
        move    (r3)+n3                 ; 4, not 2: four buffers -> four counts
        move    a,y:(r3)                ; DELAY count = 0; a stays 0 for the
                                        ; locks below
; ---- release both server-role locks for this block (BUS.md hardware test 3)
; a is still 0 from the clear loop above. Whichever of the three effects is
; position 0 does this, so the locks are freed exactly once per block and
; re-claimed below in dispatch order.
        move    a,y:>$9c1               ; DELAY SERVER role owner
        move    a,y:>$9c2               ; REVERB SERVER role owner

bus_seen:
        move    #>$30,x0                ; remember this block's offset so next
        move    y:>$900,a               ; block we can tell whether anybody
        and     x0,a                    ; else housekept in between
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$68)
notfirst:
; ---- everyone: find this block's write targets (the offset may have just
; changed above, so re-read it fresh rather than trust a stale copy) -------
; No `asl #$4` here any more: y:>$900 holds the offset already scaled.
        move    #>$30,x0
        move    y:>$900,a
        and     x0,a                     ; masked on load here too
        move    a,x0
        move    #>$901,a
        add     x0,a
        move    x:(r7+$67),b             ; this call's split-aware frame offset
        add     b,a
        move    a,r1                     ; r1 = REVERB ACC[write] base + offset
        move    #>$961,a
        add     x0,a
        add     b,a
        move    a,r2                     ; r2 = DELAY  ACC[write] base + offset
        move    #>$ffffff,m1
        move    #>$ffffff,m2

; ---- register as a REVERB bus client, once per block ---------------------
; The server divides the accumulator by this count, which is what keeps eight
; tracks from summing into the rail (measured: the bus clamps at 1.0, and with
; no scaling it breaks up at THREE sends).
;
; Gated on the split offset, so a block whose proc() runs twice still counts
; ONCE -- the same trap the parity flip and the housekeeping election were both
; written around. Counted per block rather than per sample because every sample
; slot in the block receives exactly one contribution from this track.
        move    x:(r7+$67),a
        tst     a
        bne     cnt_done                ; not this block's first call
        move    y:>$900,a               ; WRITE offset: count the buffer we are
        asr     #$4,a,a                 ; about to add into, not the one being
        move    a1,x0                   ; read. Scaled back down to a bare index
        move    x0,a                    ; because the counts are one word each
        move    #>$9c3,x0
        add     x0,a
        move    a,r3
        move    #>$ffffff,m3
        move    y:(r3),a
        move    #>$1,x0
        add     x0,a
        move    a,y:(r3)                ; REVERB count += 1
        move    #4,n3                   ; four buffers -> four counts per bus
        move    (r3)+n3                 ; -> the DELAY count, same buffer --
        move    y:(r3),a                ; this client writes BOTH accumulators
        add     x0,a                    ; unconditionally (zeros count too),
        move    a,y:(r3)                ; so it registers on both buses
cnt_done:

; ---- per-sample: mono dry sum, scaled into both accumulators -------------
        move    x:(r6+1),y0              ; ->REVERB level
        move    x:(r6),y1                ; ->DELAY level
        move    #>$1,n0
        do      n7,>send_end
        move    x:(r0),a                 ; L
        move    x:(r0+n0),x0             ; R
        add     x0,a
        asr     #$1,a,a                  ; a = mono
        move    a,x1                     ; x1 = mono, the mpy operand

        mpy     x1,y1,a                  ; a = mono * ->DELAY level
        asr     #$3,a,a                  ; 3 BITS OF BUS HEADROOM, mirror of
                                         ; the REVERB path below -- the DELAY
                                         ; SERVER shifts it back up by 3
        move    y:(r2),b
        add     b,a
        move    a,y:(r2)+                ; DELAY  ACC[write][i] += contribution

        mpy     x1,y0,a                  ; a = mono * ->REVERB level
        asr     #$3,a,a                  ; 3 BITS OF BUS HEADROOM. Eight clients
                                         ; at full scale now sum to exactly 1.0
                                         ; instead of 8.0, so the shared word can
                                         ; no longer be summed into its rail --
                                         ; measured, it clamped at seven sends
                                         ; even once the auto-gain divided right.
                                         ; The server shifts it back up by 3, so
                                         ; this costs resolution (21 bits of 24)
                                         ; and nothing else.
        move    y:(r1),b
        add     b,a
        move    a,y:(r1)+                ; REVERB ACC[write][i] += contribution

        move    #>$2,n0
        move    (r0)+n0                  ; next stereo frame
        move    #>$1,n0
send_end:
        nop
        rts
