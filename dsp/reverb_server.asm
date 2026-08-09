; ---------------------------------------------------------------------------
; EIGHT-LINE TANK (PLAN.md step 1.2). The tank has been grown from 4 lines to
; 8, with a rolled write-back loop, an 8x8 fast Walsh-Hadamard, and 8
; independent LFOs. Lines are 4096 words each (relayout increment 2: back to
; the 32K-era length, but EIGHT of them -- increment 1 emptied the private
; pool of everything else), stride 0x1000, modulo 0xFFF.
;
; This file is the refactored engine. The 4-line shipping engine lives at
; dsp/reverb_server.asm and is still the reference for verify_roll.py.
;
; Original header follows.
;
; BUS.md task 8: REVERB SERVER. Same engine as dsp/reverb89.asm (all of the
; commentary below this point describes that lineage and is unchanged), with
; three differences:
;
; 1. HARDCODED BASE. init/proc no longer read x:0x213 or the per-instance
;    allocator table at all -- the buffer base is the literal Y:0x4000,
;    every instance, matching dsp/probe_hardcoded_base.asm (BUS.md's Memory
;    section, emulator-verified independent of the allocator table). The
;    "refuse to run on a slot that cannot hold the layout" check is gone
;    too: there is no wrong slot to refuse anymore. At most one REVERB
;    SERVER per bank is a self-enforced convention (BUS.md Known limitations),
;    not something this file checks.
;
; 2. SHARED BUS PLUMBING. Every proc() call now also runs the same
;    position-0 parity-flip-and-clear housekeeping as dsp/send_client.asm
;    (verbatim, BUS.md's documented duplication requirement, including the
;    split-aware frame-offset fix -- see that file's header for the full
;    reasoning). The engine's own input additionally sums in the shared
;    REVERB bus accumulator (one block of latency, built up by every SEND
;    client and by this track's own dry signal, which is also a client of
;    its own bus per BUS.md's Known limitations), and its own clean mono wet
;    (pre-WIDTH, pre-MIX -- the bus should carry the algorithm's output, not
;    this track's own colouring of it) is written to the shared REVERB WET
;    buffer for a future cross-bus consumer (task 10) to read.
;
; 3. Everything else -- the algorithm, the parameters, the memory layout
;    below, the warm-up, all of it -- is untouched.
;
; 4. CROSS-BUS SEND (BUS.md task 10): ->DELAY, dry only, one new knob on the
;    confirmed-dead $d (MONO) slot (REVERB.md's parameter table: proven on
;    hardware to do nothing, so free to repurpose). Taps this reverb's own
;    PRE-EFFECT dry mono signal -- never its processed wet -- and adds it,
;    scaled, into the shared DELAY bus accumulator alongside whatever SEND
;    clients contribute that block. Dry-only is not a simplification, it is
;    the safety argument: BUS.md's Cross-bus sends section forbids a
;    reverb->delay WET path because it would close a loop with DELAY
;    SERVER's own ->VERB wet send (task 10's other half, dsp/delay_server.asm)
;    -- delay's wet reaching reverb, reverb's wet reaching delay, round again,
;    the same shape of instability that self-oscillated during this engine's
;    own development (DSP.md's "flat envelope is proof of instability"). A
;    dry tap can never close that loop: it only ever reads a track's own
;    pre-effect signal, the same guarantee dsp/send_client.asm's two knobs
;    already rely on.
; ---------------------------------------------------------------------------

; ---------------------------------------------------------------------------
; ROLLED TANK (PLAN.md step 1.1). The four tank taps -- read, interpolate,
; damp, low-cut -- were four copies of one 25-instruction block differing only
; in which r7 slots they touched. They are now ONE `do #4` loop over a per-line
; state table in absolute Y (layout below), which does two things:
;
;   * the line count becomes a LOOP BOUND, so an eight-line tank costs the
;     same code as a four-line one. That was the whole argument for doing this
;     before growing the tank rather than after.
;   * per-line state stops competing for r7, which is FULL ($10..$83 used and
;     $84+ hangs the DSP). Eight lines want forty state words; r7 has none.
;
; 2018 -> 1925 program words, and +15 cycles/sample against 1,392 measured
; spare -- the loop pays a little arithmetic for the indexing that fixed r7
; displacements got for free. Proved BIT-IDENTICAL to the unrolled engine
; across all four MODE characters and a TIME=127 SIZE=127 DIFF=127 wet case
; (`make verify-roll`), with a sensitivity control and a one-nop relocation
; control alongside, because a bit-identical claim without a control is a
; claim about the test.
;
; STILL UNROLLED, and next in line: the feedback/write-back section and the
; 4x4 Hadamard. They are not four copies of one block -- lines 0 and 1 carry
; an in-loop allpass and lines 2 and 3 do not -- so rolling them is a design
; question, not a transcription.
;
; v61 = v59 + LO, and the page-1 knobs put under the names that fit them:
;   HP ($3) -> LO, a NEW one-pole low cut inside the feedback path
;   LP ($4) -> HI, the existing high cut (moved off $1)
;   SHVG ($1) -> MOD depth (moved off $4)
; TIME, SHVF/SIZE, MIX and PRE already matched and do not move. First
; build in the enlarged SPRING+DARK space (2037 words).
;
; v59 = v58 + the PRE slot fix ($e was a flag word; stock DARK uses $c).
;
; v58 = v57 + v46's PRE-DELAY restored (m5 modulo on the base+0x3000 region,
; seven instructions in the loop). Dropped in v50 only to test the modulo
; theory of the two-track freeze, which was wrong: the cause was the $83
; phase load saturating the AGU (v55), and v50 froze with every M register
; linear. PRE is a real parameter again, 0..2032 samples (0..46 ms).
;
; v57 = v56 + run the body on BOTH dispatcher calls. The a=0 call is not a
; control call: it is the FIRST SUB-BLOCK, frames [0,split) at r0=0 with
; n7=split, made only when the track's split is nonzero -- and every trig
; sets the split to its landing offset inside the block, persisting until
; the next trig. rts'ing it (v44..v56) leaves the wet absent from
; [0,split) of every block after a trig: a 2.7 kHz gap train in the tail,
; the "static after a trig". Only the LFO advance gates on the a flag.
;
; v56 = v55 + the warm-up: a tagged block counter in r7+$82 (stock DARK's
; own warmed-flag slot) zeroes the whole allocation 128 words a
; block over 256 blocks, output dry until warm. Kills the "laddering
; static" -- the lines held boot garbage and the tank recirculated it.
;
; v46 -- generated by tools/gen_reverb.py, do not hand-edit
;
; Four series allpasses into a four-line FDN with a 4x4 Hadamard, one-pole
; damping inside the feedback path, and interpolated modulation on two lines.
;
; All buffers are relative to the hardcoded base Y:0x4000. BUS.md pools the
; bank's whole FX2 allocation into 0x8000 words per server (0x4000..0xBFFF).
;
; RELAYOUT INCREMENT 2 (9 Aug 2026): lines DOUBLED to 4096 words each --
; 8 x 4096 = 0x8000, the whole private allocation. Increment 1 moved every
; other buffer to the shared window precisely so the lines could take all of
; it. Round 11's measurement is the reason: 9-20 ms lines circulate 50-110
; times a second, so damping strong enough to kill the late HF zing also
; kills the early top end -- no constant bridges that; only longer lines do.
; Tap fractions are ratios of line length and do not change -- only the
; shift counts, the spacing and the modulos move (the same shape as the two
; re-layouts before it):
;   lines      base+0x0000 .. base+0x7fff   4096 words each, spacing 0x1000
;              taps to ~3914 (89 ms) at SIZE max, 8 lines
;
; In the SHARED window since increment 1 (unchanged by increment 2 -- all
; still 2048-word/512-word buffers with their own modulos):
;   input APs  shared+0x2000 .. 0x3fff      2048 words each, taps 179..547
;   pre-delay  shared+0x1000 .. 0x1fff      4096 words (93 ms)
;   SHIMMER    shared+0x0800 ..             2048 words (excised by default)
;   in-loop AP shared+0x4000/0x4200         512 words each, taps 298 446
;   tank state shared+0x4500 ..             per-line tables A and B
;
; THE TANK STATE TABLE is what makes the rolled loops possible. r7 is full --
; $10..$83 are all taken and $84+ HANGS the DSP -- and rolling needs state the
; loop can INDEX, which a fixed r7 displacement can never be.
;
; Thirteen words per line, in two groups:
;   GROUP A -- tank tap loop (words +0..+5, stride 6 within group):
;     +0  read offset   (4096 - tap) - LFO offset        per block
;     +1  interpolation fraction                         per block
;     +2  d0 carry: last sample's tap                    per sample, seeded per block
;     +3  damping state                                  PERSISTENT
;     +4  LO state                                       PERSISTENT
;     +5  this line's output                             per sample
;
;   GROUP B -- write-back params (words +6..+12, read by the write-back loop):
;     +6  wb_left        Hadamard source index, left term   constant
;     +7  wb_right       Hadamard source index, right term  constant
;     +8  wb_left_sign   +1 or -1, Q23 encoded              constant
;     +9  wb_input_sign  +1, -1, or 0                       constant
;    +10  wb_input_scale 1.0, 0.5, or 0.25                  constant
;    +11  wb_has_ap      0 = plain write, nonzero = allpass  constant
;    +12  fb_scratch     write-back result, per sample       per sample
;
; Total: 8 lines × 13 words = 104 of 256 words.
;
; The persistent words need no save/restore because Y memory is per-instance
; by construction here (one REVERB SERVER per bank, BUS.md), and the warm-up
; already zeroes the whole 0x8000-word allocation, this table included.
;
; The tap CONSTANTS do not change: they are stored as fractions of the line
; length ($3DD800 = 1979/2048), so halving the line and shifting one bit MORE
; after the multiply yields a tap half the length from the same word. Only
; the modulo, the spacing and the shift counts move -- same shape as the
; 32K re-layout (which doubled the lines and shifted one bit LESS).
;
; The allpasses are long on purpose. Four lines at ~50 ms is only ~80 echoes a
; second, which on its own reads as a stutter rather than a wash; the density
; has to come from diffusion, so the allpasses run 9-24 ms instead of the 3-8 ms
; they were when the whole engine had to fit in 6K. Eight lines at half the
; length doubles the modal overlap (0.157 -> ~0.31).
;
; State (all in the per-instance r7 block, not absolute Y):
;   r7+$83        write phase (persistent, masked on load as well as save)
;   r7+$82        warm-up counter, $2c0000 | blocks, capped at 0x100
;   base+0x7000   shimmer pitch shifter, 2048 words (v127)
;   base+0x7a00   2 in-loop allpasses, 512 words each (v127; were 1024)
;   r7+$40        LO coefficient
;   r7+$0b        state table base (base+0x7f00)
;   r7+$0c        bus auto-gain 1/N (housekeeper block; read per sample)
;   r7+$6c        lines 4-7 tap scale (per-mode, parked by md_* block).
;                 Was $0c until 9 Aug 2026: the md_* store LANDED ON the bus
;                 gain (housekeeper writes $0c first, md_* runs after), so the
;                 per-sample auto-gain multiplied by ~0.72-0.79 instead of 1/N
;                 and v121's fix was silently un-done in source. $6c is the ER
;                 level's old slot, freed when ER was removed (Direction A).
;   r7+$0d        write-back table base (base+0x7f00 + 8*6 = base+0x7f30)
;   r7+$16..$19   Hadamard inputs/outputs u0..u3 (lines 0..3)
;   r7+$3a..$3d   Hadamard inputs/outputs u4..u7 (lines 4..7)
;   r7+$1a..$1d   write-back scratch (fb values for lines 0..3)
;   r7+$41..$44   write-back scratch (fb values for lines 4..7)
;   r7+$3e        LFO phase, line 0
;   r7+$4f        LFO phase, line 1
;   r7+$50        LFO phase, line 2
;   r7+$51        LFO phase, line 3
;   r7+$47        LFO phase, line 4
;   r7+$48        LFO phase, line 5
;   r7+$49        LFO phase, line 6
;   r7+$4a        LFO phase, line 7
;   r7+$00..$07   LFO tank int/frac for lines 4..7 ($00/$01 line 4, etc.)
;   r7+$08..$0a   per-block (2048-tap) temp for lines 4..6
;   r7+$4b        per-block (2048-tap) temp for line 7
;   r7+$15..$66   per-sample scratch
;   r7+$68        this call's DELAY ACC write address (BUS.md task 10,
;                 per-call, advances per sample -- same shape as $63/$64)
;   r7+$69        ->DELAY send level (per block, from knob $d)
;   r7+$6a        this sample's own pre-effect dry mono, stashed before it's
;                 combined with the REVERB bus accumulator into $1b (BUS.md
;                 task 10 -- the ->DELAY send must tap dry alone, not dry+bus)
;
; Parameters:
;   p0 TIME -> feedback, 0.875 .. 0.999
;   p1 DAMP -> one-pole coefficient. s += c*(d-s), so a LARGE c keeps highs.
;              DAMP up lowers c: 0 = bright, 127 = dark.
;   p5 MIX  -> wet gain
;   $d MONO (confirmed dead on hardware, REVERB.md) -> repurposed as ->DELAY
;      send level, dry only (BUS.md task 10)
; ---------------------------------------------------------------------------

; LINES = 8 -- the tank loop bound. Hardcoded rather than an equ because
; this assembler (dsp_asm) does not support symbol definitions.

init:
; BUS.md task 8: hardcoded base, no per-instance stash needed at all -- the
; literal is the same for every instance, so there is nothing to derive here.
        rts

proc:
; ---- BOTH calls are audio; the A accumulator says which sub-block --------
; The dispatcher (P:0x4b8..0x4d7 for FX1, mirrored at 0x4ec.. for FX2):
;
;   split != 0:  move #$0,r0 / clr a  b,n7 / jsr    a=0, r0=0,       n7=split
;   always:      x:$20d,n7 / x:$20e,r0 / #$1,a/jsr  a=1, r0=split*2, n7=16-split
;
; The a=0 call is NOT a control call: it is the first sub-block, frames
; [0,split) of the SAME 16-frame buffer at X:0, made only when split is
; nonzero -- the dispatcher skips it at split=0 (steady state, whole block
; on the a=1 call). Every trig sets the split (+$1e bits 8..11) to its
; landing offset inside the block and it PERSISTS until the next trig, so
; rts'ing the a=0 call (v44..v56) leaves the wet absent from [0,split) of
; every block once a trig lands: a 2.7 kHz gap train in the tail, and the
; tank never hears those frames. That was the "static after a trig".
;
; So the body runs on BOTH calls. Everything re-derives from r7/$83 per
; call, and the phase and damping states are saved per call, so the two
; sub-blocks are sample-continuous by construction. Only once-per-block
; state gates on the flag: the LFO advance (below). The warm-up counter
; deliberately counts CALLS -- under a nonzero split it just warms faster.
; DARK's own body runs on both calls too (its a=0 `beq $172e` skips only
; the warm-up bump).
        move    a,x:(r7+$14)            ; call flag: $010000 = the a=1 call
                                        ; (the dispatcher's #$1 is left-
                                        ; aligned), 0 = the split sub-call

; ---- BUS.md: split-aware frame offset within the shared bus buffers, and
; the gate for whether THIS track (if it happens to be position 0) may run
; the parity flip on THIS call. Identical mechanism to dsp/send_client.asm
; -- see its header for the full reasoning -- keyed off the SAME r7+$14
; call flag this engine already keeps for its own LFO-advance gating, so no
; new stash of the raw incoming accumulator is needed here.
        clr     a
        move    a,x:(r7+$67)            ; default: offset 0 (first call)
        move    x:(r7+$14),a
        tst     a
        bne     bus_a1
        move    #>$1,a
        move    a,x:(r7+$65)            ; "a=0 ran this block"
        move    n7,a
        and     #>$f,a                  ; same mask on the way in
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$66)            ; stash split for the matching a=1
        bra     bus_off_done
bus_a1:
; COLD-BOOT SAFETY. These slots hold boot garbage the first time an instance
; runs, and x:(r7+$67) feeds straight into r1/r2 as a Y pointer below -- an
; unmasked garbage value there makes the per-sample loop write through a wild
; address, which hangs the DSP. Reproduced on hardware: selecting SEND on any
; track from a clean boot froze the unit. Same class as DSP.md's masked-garbage
; AGU saturation, so the same discipline -- mask AND A2-clean before use.
        move    x:(r7+$65),a
        and     #>$ff,a                 ; flag field only
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        move    #>$1,x0
        cmp     x0,a                    ; EXACTLY 1, not merely nonzero --
        bne     bus_off_done            ; "nonzero" accepts almost any garbage
        clr     a
        move    a,x:(r7+$65)            ; consume the flag
        move    x:(r7+$66),a
        and     #>$f,a                  ; a split point is 0..15 by
        move    a1,x0                   ; construction, so this cannot narrow a
        move    x0,a                    ; legitimate value -- it only makes
        move    a,x:(r7+$67)            ; garbage harmless
bus_off_done:

; ---- position-0 housekeeping: flip the shared bus parity, clear the new
; write-target ACC buffers. Gated on r7==0x6200 AND offset==0 -- copied from
; dsp/send_client.asm, must stay identical (BUS.md Known limitations).
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
; bus_notfirst, so it still finds this block's write targets but never elects.
; Inert in a normal build: it is a comment.
        move    x:(r7+$67),a
        tst     a
        bne     bus_notfirst                ; not this block's first call
        move    r7,a
        move    #>$6200,x0
        cmp     x0,a
        beq     bus_dohk                ; position 0: always the housekeeper
        move    #>$1,x0
        move    y:>$900,a
        and     x0,a
        move    a1,x0
        move    x0,a                    ; parity now, A2-clean
        move    x:(r7+$6b),x0
        cmp     x0,a
        bne     bus_seen                ; it moved: someone else housekept
bus_dohk:                               ; nobody did -- take over this block

        move    #>$1,x0
        move    y:>$900,a
        and     x0,a
        move    a,x1
        move    #>$1,a
        sub     x1,a
        and     x0,a
        move    a,y:>$900
        asl     #$4,a,a
        move    a,x0
        move    #>$901,a
        add     x0,a
        move    a,r1                    ; r1 = REVERB ACC[new] base
        move    #>$941,b
        add     x0,b
        move    b,r2                    ; r2 = DELAY  ACC[new] base
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        clr     a
        move    #>16,y0
        do      y0,>bus_zclr
        move    a,y:(r1)+
        move    a,y:(r2)+
bus_zclr:
        nop
; ---- release both server-role locks for this block (BUS.md hardware test 3)
; a is still 0 from the clear loop above. Whichever of the three effects is
; position 0 does this, so the locks are freed exactly once per block and
; re-claimed below in dispatch order.
        move    a,y:>$981               ; DELAY SERVER role owner
        move    a,y:>$982               ; REVERB SERVER role owner
; ---- reset the new write buffer's SEND COUNT, alongside its accumulators ---
; The housekeeping is duplicated between this file and dsp/send_client.asm and
; must stay in step (BUS.md). x1 still holds the OLD parity, so the buffer just
; made current is 1 - x1. Without this the count grows without bound and the
; auto-gain above divides by garbage.
        move    #>$1,a
        sub     x1,a                    ; new parity
        move    #>$983,x0
        add     x0,a
        move    a,r1
        clr     a
        move    a,y:(r1)
bus_seen:
        move    #>$1,x0                 ; remember this block's parity so next
        move    y:>$900,a               ; block we can tell whether anybody
        and     x0,a                    ; else housekept in between
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$6b)
bus_notfirst:

; ---- server-role lock: only ONE REVERB SERVER may run per bank -----------------
; Both servers use a FIXED, hardcoded Y base identical for every instance, so
; two of the same role would share one set of buffers and drive each other's
; feedback path -- measured on hardware as a solid, unchanging tone (BUS.md's
; hardware test 3). The lock is released once per block by whichever effect is
; position 0 (above) and claimed here in dispatch order: the first instance to
; arrive owns the role for that block, any duplicate rts's without touching
; the audio buffer at all, which is an exact dry passthrough.
;
; Keyed on r7 (this instance's own state block), so a split block's two calls
; both match the same owner and the second is not mistaken for a duplicate.
        move    y:>$982,a
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        tst     a
        beq     bus_claim               ; free: take it
        move    r7,x0
        cmp     x0,a
        beq     bus_mine                ; already ours (split block's 2nd call)
        rts                             ; a duplicate: pass audio through
bus_claim:
        move    r7,a
        move    a,y:>$982
bus_mine:

; ---- this call's REVERB ACC read address and WET write address ----------
; READ is the OTHER buffer from the current write parity -- the one every
; SEND client (and our own dry sum, below) finished filling last block
; (one-block latency, BUS.md's Mechanism section). WRITE uses the SAME
; parity clients currently write into, so it is complete and ready by the
; time next block flips -- for a future cross-bus reader (task 10), not
; consumed by anything yet.
        move    #>$1,x0
        move    y:>$900,a
        and     x0,a                    ; write_parity
        move    a,x1
        move    #>$1,a
        sub     x1,a                    ; a = 1 - write_parity = read_parity
        asl     #$4,a,a
        move    a,x0
        move    #>$901,a
        add     x0,a
        move    x:(r7+$67),b            ; this call's split-aware frame offset
        add     b,a
        move    a,x:(r7+$63)            ; this call's ACC read address
        move    x1,a
        asl     #$4,a,a                 ; write_parity*16
        move    a,x0
        move    #>$921,a
        add     x0,a
        add     b,a
        move    a,x:(r7+$64)            ; this call's WET write address

; ---- this call's DELAY ACC write address (BUS.md task 10: ->DELAY send) --
; x1 (write_parity) and b (split-aware frame offset) are both still valid
; from the block just above -- nothing between there and here touches them.
        move    x1,a
        asl     #$4,a,a                 ; write_parity*16
        move    a,x0
        move    #>$941,a
        add     x0,a
        add     b,a
        move    a,x:(r7+$68)            ; this call's DELAY ACC write address

; ---- bus auto-gain: resolve 1/N for this block's READ buffer ------------
; Eight tracks sending into one accumulator sum to eight times one track, and
; the accumulator CLAMPS at 1.0 -- measured, it breaks up at THREE sends and is
; destroyed by seven. Dividing by the number of clients that actually wrote the
; buffer holds total drive CONSTANT however many tracks send, so the send knob
; sets each track's SHARE of the reverb rather than how hard the tank is hit.
;
; The count belongs to the buffer being READ (the fully-summed, one-block-old
; one), so it is indexed by READ parity. x1 still holds write_parity from the
; block above, and read = 1 - write.
;
; Reciprocals live at base+0x7800 -- the 2048 words the shimmer used to occupy
; -- rebuilt each block. A compare chain was tried first and cost 72 program
; words, which OVERRAN the payload region; this is half that and the stores are
; free in cycle terms.
;
; Table order is deliberate: the count is masked to 0..7, so a full 8 senders
; wraps to index 0. Index 0 therefore holds 1/8, and index k holds 1/k. A count
; of 0 (nobody sent) also lands on 1/8, which is harmless -- the accumulator is
; zero in that case anyway.
        move    #>$30000,b              ; SHARED WINDOW + 0x4400. Built as base
        move    #>$4400,x0              ; + offset rather than one literal
        add     x0,b                    ; because only the bare `$30000` is
        move    b,r5                    ; rewritten to `$38000` for payload B --
                                        ; a fused `$34400` would silently keep
                                        ; core 1 pointing into core 0's memory.
                                        ; x:(r7+$31) is not written until AFTER
                                        ; this block, so reading it here would
                                        ; take the PREVIOUS block's value (and
                                        ; garbage on the very first). b is kept
                                        ; live for the index below, and x0 is
                                        ; free until the $983 load below.
        move    #>$ffffff,m5
        move    #>$100000,a
        move    a,y:(r5)+               ; [0] = 1/8  (count 8 wraps to here)
        move    #>$7fffff,a
        move    a,y:(r5)+               ; [1] = 1/1
        move    #>$400000,a
        move    a,y:(r5)+               ; [2] = 1/2
        move    #>$2aaaab,a
        move    a,y:(r5)+               ; [3] = 1/3
        move    #>$200000,a
        move    a,y:(r5)+               ; [4] = 1/4
        move    #>$199999,a
        move    a,y:(r5)+               ; [5] = 1/5
        move    #>$155555,a
        move    a,y:(r5)+               ; [6] = 1/6
        move    #>$124925,a
        move    a,y:(r5)                ; [7] = 1/7

        move    #>$1,a
        sub     x1,a                    ; read_parity
        move    #>$983,x0
        add     x0,a
        move    a,r5
        move    y:(r5),a                ; clients that wrote the buffer we read
        move    #>$7,x0
        and     x0,a                    ; masked: boot garbage cannot index wild
        move    a1,x0
        move    x0,a                    ; A2-clean before it becomes an address
        add     b,a                     ; b = table base, still live
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$0c)            ; this block's bus gain, used per sample.
                                        ; $0c, NOT $6d: $6d is the DIFFUSION
                                        ; allpass coefficient g. And $0c is
                                        ; the bus gain's ALONE: the md_* tap
                                        ; scale parked here for a day and every
                                        ; sample multiplied the bus by ~0.75
                                        ; instead of 1/N. It lives in $6c now.

; ---- hardcoded base: BUS.md task 8 (REVERB SERVER always Y:0x4000) ------
; No x:0x213 read, no per-instance stash -- every instance of this effect
; uses the same literal, the same technique dsp/probe_hardcoded_base.asm
; verified independent of the allocator table (BUS.md's Memory section).
        move    #>$ffffff,m0            ; audio is read and written via r0
        move    #>$4000,x0
        move    x0,x:(r7+$31)

; ---- warm-up: stock DARK's shape, adapted --------------------------------
; The delay lines are never cleared: init zeroes nothing, so the tank
; recirculates whatever the 0x8000-word allocation held -- the "laddering
; static". Stock DARK's answer (P:0x1718..0x172c in payload A) is a
; per-block counter in $83 up to 0x100 with $82 as the warmed flag. Our
; $83 already holds the tank phase, so the counter lives in $82 --
; TAGGED, because on the first call after enable $82 holds leftover
; garbage and init cannot be the reset point (the dispatcher re-invokes
; init most blocks). stageprobe4 proved the tagged-counter idiom stable.
;
; While warming: zero 128 words of the allocation per block (256 * 128 =
; 0x8000, all of it), zero the LFO/damping state block, and stay DRY --
; the engine does not run until the lines are clean.
;
; $82 = $2c0000 | count. The standing rule applies twice: the tag field
; and the count are each masked AND A2-cleaned before use -- the count
; feeds the zero pointer, and a bit-23 leftover would saturate it.
        move    x:(r7+$82),a
        move    #>$fffe00,x0
        and     x0,a                    ; tag field -- AND cleans A1 only
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        move    #>$2c0000,x0
        cmp     x0,a
        beq     warmtag
        clr     a                       ; garbage tag: warm-up starts at 0
        bra     warmrun
warmtag:
        move    x:(r7+$82),a
        move    #>$1ff,x0
        and     x0,a
        move    a1,x0
        move    x0,a                    ; the count, A2-clean
        move    #>$100,x0
        cmp     x0,a
        bge     warmdone                ; warmed: run the reverb
warmrun:
        move    a,x:(r7+$15)            ; count, for the save below
        asl     #$7,a,a                 ; count*128 -- clears the FULL private
                                        ; 0x8000 words: 256 blocks x 128 =
                                        ; 32,768. That allocation is now tank
                                        ; lines and nothing else.
        move    x:(r7+$31),x0
        add     x0,a
        move    a,r5                    ; base + count*128, count < 0x100 so
                                        ; the last word is base+0x7fff
        clr     b                       ; the zero source ...
        move    x:(r7+$31),x0           ; ... and both fill the AGU slot
        do      #128,>warmz
        move    b,y:(r5)+
warmz:
; ---- and the SHARED half, which the loop above no longer reaches ---------
; Everything that is not a tank line moved to the shared window, so it needs
; its own clear or the engine starts on whatever the last effect left there --
; the "laddering garbage" failure the private clear exists to prevent.
;
; 64 words x 256 blocks = 16,384, covering shared+0x0800 .. shared+0x47ff.
; That is a little more than the 15,872 actually occupied, which is harmless.
;
; ⚠️ THE BOUNDS ARE LOAD-BEARING, in both directions:
;   - it must start at +0x0800, because stock's per-frame parameter staging
;     sits at shared+0x0000..+0x0047 and is rewritten every frame
;   - it must end well below +0x6000, because THE BUS SCRATCH lives at
;     shared+0x6000..+0x7fff. Zeroing that would clear the accumulator parity
;     word and every client's contribution mid-block, on 256 consecutive
;     blocks, on a core the other core is talking to.
; +0x47ff leaves 6,145 words of margin. Do not grow this loop without moving
; the scratch first.
        move    #>$ffffff,m5            ; ISOLATION 9 Aug: the clear below wrote
                                        ; y:(r5)+ under whatever m5 the previous
                                        ; block left. Forced linear.
        move    x:(r7+$15),a            ; the count again, still A2-clean
        asl     #$6,a,a                 ; count*64
        move    #>$30000,x0             ; -> $38000 on payload B
        add     x0,a
        move    #>$800,x0
        add     x0,a
        move    a,r5
        clr     b                       ; TWO instructions between the r5 write
        move    x:(r7+$15),x0           ; and the AGU read in the loop -- the
                                        ; same spacing the private clear above
                                        ; uses ("two data moves before the loop,
                                        ; to clear the AGU write"). With only
                                        ; ONE, r5 is read before the write has
                                        ; landed, the loop walks from a garbage
                                        ; base and dsp_host SIGSEGVs. x0 is dead
                                        ; here; the value loaded is irrelevant.
        do      #64,>wshclr
        move    b,y:(r5)+
wshclr:
; the one-pole and LFO state now lives in r7, so zero it there
;
; The four tank damping states and the four LO states used to be zeroed here
; too ($3a..$3d, $41..$44). They live in the Y state table now, and the loop
; above has just cleared the whole allocation, so zeroing them a second time
; by hand would be eight dead instructions.
        move    b,x:(r7+$3e)
        move    b,x:(r7+$78)            ; wet high-cut states (Round 11): boot
        move    b,x:(r7+$79)            ; garbage here would click at warm-end
; The in-loop allpass interpolation carries $5c/$5d used to be zeroed here
; too (v90). DEAD since v127: the per-block priming above the sample loop
; seeds both from the buffer, unconditionally, before anything reads them --
; and the warm-up call itself branches to dry without reading either. Found
; by tools/verify_slots.py, the $0c bug's checker; deleting them is 2 words.
        move    b,x:(r7+$4f)
        move    b,x:(r7+$50)
        move    b,x:(r7+$51)
        move    b,x:(r7+$47)            ; LFO phase line 4 (8-line)
        move    b,x:(r7+$48)            ; LFO phase line 5
        move    b,x:(r7+$49)            ; LFO phase line 6
        move    b,x:(r7+$4a)            ; LFO phase line 7
        move    x:(r7+$15),a            ; reload count
        move    #>$1,x0
        add     x0,a
        move    #>$2c0000,x0
        add     x0,a                    ; tag | count+1
        move    a,x:(r7+$82)
        bra     dry                     ; output stays dry until warm
warmdone:
        move    x:(r7+$31),x0           ; the base again: everything below
                                        ; derives buffers from x0

; ---- every buffer base, derived once per block --------------------------
;
; TWO REGIONS SINCE THE SHARED-WINDOW RE-LAYOUT (9 Aug 2026).
;
; The private allocation Y:0x4000-0xBFFF now carries THE EIGHT TANK LINES AND
; NOTHING ELSE, so they are free to grow into all 32,768 words of it. Every
; other buffer moved to this core's own half of the 64K shared window.
;
; Why the lines get the private half and not the shared one: the lines are the
; only thing needing a single UNBROKEN, self-aligned 32K block, and the private
; allocation is the only unbroken 32K there is. The shared half is fragmented
; by two things we do not own -- stock's per-frame parameter staging at
; 0x30000-0x30047, rewritten EVERY FRAME, and the bus scratch at
; 0x36000-0x37FFF -- so it suits the small buffers, which fit around them.
;
; ✅ The shared half really is ours: stock's own FX2 allocator table at X:0x255
; hands payload A 0x30000/0x34000 and payload B 0x38000/0x3C000, measured from
; the raw image (XBUS.md). The cores' shared-window slots do not overlap.
;
; ⚠️ THE `$30000` BELOW IS REWRITTEN TO `$38000` ON PAYLOAD B by build_bus.py's
; blanket per-payload substitution, and that is CORRECT here -- a reverb on
; core 1 must use core 1's half or it would collide with core 0's reverb in the
; same physical memory. It also means this literal must not be spelled any
; other way, and that no unrelated `$30000` may appear in this file.
;
; Everything below still derives from x0, so the only change to the shape of
; this block is which base x0 holds.
        move    #>$0,a
        add     x0,a
        move    a,x:(r7+$10)            ; line 0 base
        move    #>$1000,a
        add     x0,a
        move    a,x:(r7+$11)            ; line 1 base
        move    #>$2000,a
        add     x0,a
        move    a,x:(r7+$12)            ; line 2 base
        move    #>$3000,a
        add     x0,a
        move    a,x:(r7+$13)            ; line 3 base
; $36/$37 and $10..$13 are line bases the rolled tap loop no longer reads.
; r1..r4 carry lines 0..3 inside the sample loop (built from the saved
; phase, below). $36/$37 and $4c/$4d carry the four new lines for the
; state-table priming carry seed -- those are the only places that need
; a bare line base (without phase) for lines 4..7.
        move    #>$4000,a               ; line 4 base (4 * 0x1000)
        add     x0,a
        move    a,x:(r7+$36)
        move    #>$5000,a               ; line 5 base (5 * 0x1000)
        add     x0,a
        move    a,x:(r7+$37)
        move    #>$6000,a               ; line 6 base (6 * 0x1000)
        add     x0,a
        move    a,x:(r7+$4c)
        move    #>$7000,a               ; line 7 base (7 * 0x1000)
        add     x0,a
        move    a,x:(r7+$4d)

; ---- everything that is NOT a tank line: the shared window --------------
; x0 is reloaded with the shared base and every derivation below keeps the
; same `add x0,a` shape it had against the private base.
        move    #>$30000,x0             ; -> $38000 on payload B (see above)
; Input allpasses, still 2048 words apart. Their taps are 179/293/419/547 so
; 1024 would do, but shrinking them is a SEPARATE change: this relocation is
; required to render bit-identically and a size change would forfeit that test.
        move    #>$2000,a
        add     x0,a
        move    a,x:(r7+$32)
        move    #>$2800,a
        add     x0,a
        move    a,x:(r7+$33)
        move    #>$3000,a
        add     x0,a
        move    a,x:(r7+$34)
        move    #>$3800,a
        add     x0,a
        move    a,x:(r7+$35)
        move    #>$1000,a
        add     x0,a
        move    a,x:(r7+$38)            ; pre-delay base, 4096-aligned
        move    #>$4500,a
        add     x0,a
        move    a,x:(r7+$0b)            ; the tank's per-line state table A
        move    #>$4530,a
        add     x0,a
        move    a,x:(r7+$0d)            ; table B: write-back params (8x2=16 words)

; ---- prime table B: input injection weight and allpass flag, all 8 lines --
; THE SIGNS ARE THE POINT, and the first eight-line build lost them.
;
; v4 injected the diffused input as [+1, -1, -1/2, +1/2] -- four inline
; add/sub sites, where the sign was carried by the CHOICE of `add` or `sub`
; (`sub x0,a` for line 1, `sub x:(r7+$27)` for line 2). Folding those sites
; into one table-driven loop moved the sign from the opcode into the stored
; weight, and the first table was primed [+1, +1, +1/2, +1/2] -- every entry
; positive, because a weight written as $7fffff/$400000 looks like the same
; constant the old code multiplied by.
;
; An all-positive input vector points straight down the all-ones direction,
; which is the Hadamard's own first row: the one direction where every line's
; contribution adds coherently on every pass instead of cancelling. That is
; the mode an FDN cannot damp by spreading, and it is what "ringy feedback
; mess" sounds like. The weights must SUM TO ZERO so the drive spreads across
; modes rather than pumping the common one. v4's did; this now does.
;
; Lines 4-7 were left at warmup zero on the reasoning that the Hadamard's
; cross-group terms would feed them anyway. They do -- but a line with zero
; input weight is not a driven line, it is a parasite hanging off the other
; four, so the "eight-line" tank was a four-line tank with four echoes
; bolted to it. All eight are driven here.
;
; Group B is the same multiset ROTATED, not copied: if in[k+4] were a fixed
; multiple of in[k], FWHT stage 3 (which pairs k with k+4) would collapse the
; drive onto one of each pair's two outputs. The rotation keeps both live.
;
;   line   0    1    2    3     4    5    6    7
;   weight +1   -1  -1/2  +1/2  +1/2 +1   -1  -1/2      sum = 0
;
; THE SECOND WORD IS NOT WRITTEN HERE. It was the dead has_allpass flag until
; 9 Aug 2026; it now carries the PER-LINE DECAY GAIN (PLAN.md 1.1), primed by
; its own block AFTER the TIME block folds TIME and MODE into $1e -- it cannot
; be written this early, because $1e is not final yet. This chain writes the
; weights only and n1=2 strides past the gain word, exactly as it always did.
;
; The chain generates all eight weights from ONE immediate. `neg`/`asr`/`asl`
; walk the accumulator +1 -> -1 -> -1/2 -> +1/2 -> (reuse) -> +1 -> -1 -> -1/2,
; which is worth ~11 words against eight `move #>$...,x0` loads. The values
; land an LSB shy of exact (neg of $7fffff is $800001) -- irrelevant at Q23
; against a decay gain that moves by more than that between knob steps.
        move    x:(r7+$0d),r1           ; straight to r1: one word cheaper than
                                        ; loading a and copying it across
        move    #2,n1                   ; SHORT immediate: 1 word, and safe
                                        ; because n1 is an ADDRESS register, so
                                        ; the 8-bit value is zero-extended.
        move    #$7f,a                  ; +0.992, the seed for the whole chain.
                                        ; SHORT immediate again -- and here the
                                        ; MSB placement that makes `move #1,y0`
                                        ; a trap is exactly what is wanted: the
                                        ; byte lands in A1's top, giving $7f0000
                                        ; in one word where $7fffff costs two.
                                        ; 0.992 vs 1.0 on an input weight is
                                        ; 0.07 dB, and it buys the last word.
        move    a,y:(r1)+n1             ; line 0 weight  +1
        neg     a
        move    a,y:(r1)+n1             ; line 1 weight  -1
        asr     a
        move    a,y:(r1)+n1             ; line 2 weight  -1/2
        neg     a
        move    a,y:(r1)+n1             ; line 3 weight  +1/2
        move    a,y:(r1)+n1             ; line 4 weight  +1/2  (unchanged)
        asl     a
        move    a,y:(r1)+n1             ; line 5 weight  +1
        neg     a
        move    a,y:(r1)+n1             ; line 6 weight  -1
        asr     a
        move    a,y:(r1)+n1             ; line 7 weight  -1/2

; ---- state lives in r7, which is already per-instance and persistent ----
; v74: the LFO phases and one-pole states used to be round-tripped through
; a 12-word block at the top of the allocation every call. That was never necessary --
; the r7 block is per-instance and survives between calls, which $83 has
; proven for seventy builds. Deleting the round-trip frees ~48 instructions
; a block AND the whole region at the top of the allocation, which is where
; the in-loop allpasses now live (base+0x7000 since the 32K re-layout).
; ---- rebuild the four delay pointers from the saved phase ----------------
        move    x:(r7+$83),a
        move    #>$fff,x0
        and     x0,a                    ; mask on LOAD: the phase may be garbage
        move    a1,x0                   ; -- but AND cleans A1 ONLY. Garbage with
        move    x0,a                    ; bit 23 set sign-extends A2 = $ff, and
                                        ; every move a,rN then SATURATES to
                                        ; $800000: the first line access goes to
                                        ; Y:0x800000, off-chip, and the bus waits
                                        ; forever. THIS WAS THE TWO-TRACK FREEZE:
                                        ; track 2's page held bit-23-set garbage,
                                        ; track 1's did not. Reproduced in the
                                        ; emulator by poisoning X:(r7+$83).
        move    x:(r7+$31),x0
        add     x0,a                    ; base + LINE_OFF(0x0)
        move    a,r1                    ; line 0
        move    #>$1000,x0
        add     x0,a
        move    a,r2                    ; line 1
        add     x0,a
        move    a,r3                    ; line 2
        add     x0,a
        move    a,r4                    ; line 3
        move    #>$fff,m1               ; MODULO 4096: r1..r4 are the four line
        move    #>$fff,m2               ; pointers and each wraps inside its own
        move    #>$fff,m3               ; line. Restored in v62 -- this is the
        move    #>$fff,m4               ; original design, and it is what makes
                                        ; n1/n4 live again so SIZE reaches all
                                        ; four lines. Bases are base+0/0x1000/
                                        ; 0x2000/0x3000 and base is the literal
                                        ; 0x4000, so every line is 4096-aligned
                                        ; as modulo requires.

; ---- MODE: character select, page-2 slot 7 ($c bits 8-15) (v93) ---------
; Three characters. MODE reconfigures tap length, diffusion depth, damping
; and modulation together — not merely rescaling SIZE.
;
; Read here, before the SIZE block, because it scales the tap lengths that
; block computes. The companion field carries a small step count (0..2), not
; a left-aligned knob -- see the page-2 rejig note above.
;
;   0 ROOM   short tap scale, high diffusion, fast damping — close walls
;   1 PLATE  medium tap scale, highest diffusion, bright — metallic sheet
;   2 BIG    longest tap scale, low diffusion, darkest — the Valhalla-flavoured one
;            HALL removed (9 Aug 2026): sat between PLATE and BIG on every
;            lever and was never distinguishable from BIG in blind A/B.
;            Early reflections: REMOVED (9 Aug 2026). Six discrete taps were a
;            flutter echo. The input diffuser (4-13 ms, Dattorro-scale) now fills
;            this role. See VOICING.md Round 7.
;
; SIZE, TIME, DIFF and the rest still work inside whichever character is
; chosen; MODE moves the centre, the knobs move around it.
        move    x:(r6+$c),a
        and     #>$ff00,a               ; slot 7's field, NOT the knob field
        move    a1,x0                   ; AND cleans A1 only
        move    x0,a
        asl     #$8,a,a                 ; -> 0..3, MSB-ALIGNED ($010000 per
                                        ; step) to match the short immediates
                                        ; the dispatch below compares against
; MODE_OVERRIDE
        move    a,x:(r7+$6e)

        move    x:(r7+$6e),a
        tst     a
        beq     md_room
        move    #$1,x0                  ; SHORT immediates, which the DSP56300
        cmp     x0,a                    ; places MSB-ALIGNED ($010000) -- which
        beq     md_plate                ; is why the extract above is `asl #$8`
; HALL removed (9 Aug 2026): the three remaining modes are well-separated on
; decay, damping, modulation and tap spread; HALL sat between PLATE and BIG on
; every lever and was never distinguishable from BIG in blind A/B (VOICING.md).
; Removing it frees the md_hall block (~50 words) and the beq dispatch.

; Per-mode levers — each md_* block sets these constants:
;
;   $72  damping scale  -- multiplies the HI-derived coefficient. SMALLER is
;                          darker, because the one-pole is s += c*(d-s).
;   $73  mod depth scale -- multiplies MOD. Only ever scales DOWN, so BIG sits
;                          at unity and the tighter spaces move less.
;
; A big space is darker and more moving in its tail, not merely longer; that
; is the part tap scale was never going to express.
md_big:                                 ; 2, and anything unexpected
; DECAY SCALE, 1.00 -> ~11.6 s, unchanged; BIG is the long one.
; MODE did not touch decay time AT ALL. Measured at TIME=64 the four modes
; ran 6.9 / 9.8 / 10.3 / 11.6 s -- and what spread there was came only
; incidentally, from shorter lines circulating more often. Decay time is
; the single biggest room-vs-hall cue, so ROOM vs HALL stayed the weakest
; pair however the other five levers were set.
;
; Parked in $1e for the TIME block below to fold in -- the r7 block ends at
; $83 and $7e..$81 went to the diffuser taps, so there is no spare slot.
; Scaling g DOWN is always safe; it is scaling UP that self-oscillates.
        move    #>$4CCCCD,a               ; 0.60 2/√8 headroom, was $5A8279 (exact)
        move    a,x:(r7+$1e)
; INPUT DIFFUSER taps, Dattorro-scale (4-13 ms) — short, dense buildup
; replaces the removed ER section. All four modes share the same tap set;
; the diffusion CHARACTER comes from the coefficient at $3f, not the lengths.
; The four original allpass taps (1994/1706/1438/1226) were too long to
; diffuse — they dispersed (same mechanism documented in VOICING.md Round 7
; for the in-loop allpasses). Stored as (2048 - tap) for the modulo read.
        move    #>1869,a
        move    a,x:(r7+$7e)            ; allpass 0, tap 179 (4.1 ms)
        move    #>1755,a
        move    a,x:(r7+$7f)
        move    #>1629,a
        move    a,x:(r7+$80)
        move    #>1501,a
        move    a,x:(r7+$81)            ; allpass 3, tap 547 (12.4 ms)
        move    #>$200000,a             ; MODE's LFO RATE scale -- slowest -- a huge space barely moves.
        move    a,x:(r7+$2f)            ; parked in $2f, which the RATE block
                                        ; below folds into its own result. The
                                        ; r7 block ends at $83 ($84+ is host-
                                        ; owned and HANGS, DSP.md), so there is
                                        ; no spare slot for this.
; EARLY-REFLECTION ARRIVALS removed — six discrete taps were a flutter echo.
; A short input diffuser now fills this role (see the allpass tap constants above).
; TAP SPREAD, 1.69 : 1 (longest:shortest) -- wide, CAPPED by the buffer.
; The four line lengths used to be hardcoded once and merely SCALED by
; MODE, so every mode was ONE modal pattern transposed. That is why they
; sounded alike however the scale moved.
;
; The MEAN tap is held at 3178 in every mode, so MODE's tap scale keeps its
; full effect on size and the spread varies INDEPENDENTLY of it. Pinning the
; longest instead (first attempt) moved each mode's mean delay -- PLATE +12%,
; BIG -13% -- so the new lever pushed against the one already working, and
; the modes measured CLOSER together. See VOICING.md Round 3.
        move    #>$3F4800,a             ; line 0: 4050 of 4096
        move    a,x:(r7+$74)
        move    #>$352C00,a             ; line 1: 3403 of 4096
        move    a,x:(r7+$75)
        move    #>$2CB000,a             ; line 2: 2860 of 4096
        move    a,x:(r7+$76)
        move    #>$258C00,a             ; line 3: 2403 of 4096
        move    a,x:(r7+$77)
        move    #>$7fffff,a             ; tap scale 1.00 -- the largest space
        move    a,x:(r7+$6f)
        move    #>$040000,a             ; diffusion offset, lowest
        move    a,x:(r7+$3f)
        move    #>$480000,a             ; damping 0.5625, was 0.445 -- compensate lower loop gain
        move    a,x:(r7+$72)            ; against PASS RATE, not per pass: the
                                        ; (Round 11: BIG keeps 0.5625 -- already
                                        ; darkest, its HF hang was the scatter,
                                        ; which the wet high-cut now handles)
                                        ; first attempt used 0.60 against HALL's
                                        ; 0.75 and measured BIG the BRIGHTER of
                                        ; the two, because damping applies once
                                        ; per circulation and BIG's lines are
                                        ; 1.39x longer, so it damps 0.72x as
                                        ; often per second. Retention over equal
                                        ; time goes as c^(1/tapscale), which is
                                        ; what these constants are chosen on.
        move    #>$7fffff,a             ; full modulation: the Valhalla-flavoured
        move    a,x:(r7+$73)            ; scale comes from movement, not length
        move    #>$4ccccd,a             ; wet high-cut 0.60 (~7 kHz) -- between
        move    a,x:(r7+$7a)            ; ROOM's dark and PLATE's bright
        move    #>$650000,a             ; lines 4-7 tap scale 0.789 -- wide
        move    a,x:(r7+$6c)            ; interleave suits the 1.69 spread
        bra     md_done
md_room:
; DECAY SCALE, 0.92 -> RT60 ~2.0 s. A room is SHORT; 6.9 s is a cathedral.
; MODE did not touch decay time AT ALL. Measured at TIME=64 the four modes
; ran 6.9 / 9.8 / 10.3 / 11.6 s -- and what spread there was came only
; incidentally, from shorter lines circulating more often. Decay time is
; the single biggest room-vs-hall cue, so ROOM vs HALL stayed the weakest
; pair however the other five levers were set.
;
; Parked in $1e for the TIME block below to fold in -- the r7 block ends at
; $83 and $7e..$81 went to the diffuser taps, so there is no spare slot.
; Scaling g DOWN is always safe; it is scaling UP that self-oscillates.
        move    #>$534307,a               ; 2/√8 = H8 normalization (was $75C000 for H4)
        move    a,x:(r7+$1e)
; INPUT DIFFUSER taps, Dattorro-scale (4-13 ms) — short, dense buildup
; replaces the removed ER section. All modes share the same tap set.
        move    #>1869,a
        move    a,x:(r7+$7e)            ; allpass 0, tap 179 (4.1 ms)
        move    #>1755,a
        move    a,x:(r7+$7f)
        move    #>1629,a
        move    a,x:(r7+$80)
        move    #>1501,a
        move    a,x:(r7+$81)            ; allpass 3, tap 547 (12.4 ms)
        move    #>$599999,a             ; MODE's LFO RATE scale -- moderate.
        move    a,x:(r7+$2f)            ; parked in $2f, which the RATE block
                                        ; below folds into its own result. The
                                        ; r7 block ends at $83 ($84+ is host-
                                        ; owned and HANGS, DSP.md), so there is
                                        ; no spare slot for this.
; EARLY-REFLECTION ARRIVALS removed — six discrete taps were a flutter echo.
; A short input diffuser now fills this role (see the allpass tap constants above).
; TAP SPREAD, 1.60 : 1 (longest:shortest) -- the reference -- unchanged.
; The four line lengths used to be hardcoded once and merely SCALED by
; MODE, so every mode was ONE modal pattern transposed. That is why they
; sounded alike however the scale moved.
;
; The MEAN tap is held at 3178 in every mode, so MODE's tap scale keeps its
; full effect on size and the spread varies INDEPENDENTLY of it. Pinning the
; longest instead (first attempt) moved each mode's mean delay -- PLATE +12%,
; BIG -13% -- so the new lever pushed against the one already working, and
; the modes measured CLOSER together. See VOICING.md Round 3.
        move    #>$3DD800,a             ; line 0: 3958 of 4096
        move    a,x:(r7+$74)
        move    #>$34E800,a             ; line 1: 3386 of 4096
        move    a,x:(r7+$75)
        move    #>$2D3800,a             ; line 2: 2894 of 4096
        move    a,x:(r7+$76)
        move    #>$26A800,a             ; line 3: 2474 of 4096
        move    a,x:(r7+$77)
        move    #>$399999,a             ; tap scale 0.45 -- close walls
        move    a,x:(r7+$6f)
        move    #>$0c0000,a             ; diffusion offset, high
        move    a,x:(r7+$3f)
        move    #>$600000,a             ; damping 0.75 (was 0.95: Round 11's
        move    a,x:(r7+$72)            ; inverted-HF finding -- VV room's HF
                                        ; dies FASTEST, ours hung on)
        move    #>$400000,a             ; least movement: a small room does not
        move    a,x:(r7+$73)            ; wobble, and at this size it would chorus
        move    #>$466666,a             ; wet high-cut 0.55 (~6 kHz) -- VV room
        move    a,x:(r7+$7a)            ; is "darker tone"
        move    #>$5c0000,a             ; lines 4-7 tap scale 0.71875 -- tighter
        move    a,x:(r7+$6c)            ; interleave for a smaller space
        bra     md_done
md_plate:
; DECAY SCALE, 0.965 -> ~4.8 s.
; MODE did not touch decay time AT ALL. Measured at TIME=64 the four modes
; ran 6.9 / 9.8 / 10.3 / 11.6 s -- and what spread there was came only
; incidentally, from shorter lines circulating more often. Decay time is
; the single biggest room-vs-hall cue, so ROOM vs HALL stayed the weakest
; pair however the other five levers were set.
;
; Parked in $1e for the TIME block below to fold in -- the r7 block ends at
; $83 and $7e..$81 went to the diffuser taps, so there is no spare slot.
; Scaling g DOWN is always safe; it is scaling UP that self-oscillates.
        move    #>$50A000,a               ; was $5753E3 (2/√8 exact). Round 12:
        move    a,x:(r7+$1e)            ; on the doubled lines PLATE's fastest
                                        ; decay (TIME=0) measured MF -15.1 dB/s
                                        ; against VV plate's -18.9 -- the knob
                                        ; could not reach a real plate's
                                        ; tightness. Set EMPIRICALLY, not by
                                        ; gain accounting: $1e feeds the per-
                                        ; line formula through the 1/√8 anchor
                                        ; spread, so a naive x0.972 delivered
                                        ; only 2.5 dB/s of the needed 6.9
                                        ; (measured sensitivity ~2.5 dB/s per
                                        ; 0.019 of scale). This value targets
                                        ; VV plate's rate at TIME~32, whole
                                        ; upper knob left for longer tails.
; INPUT DIFFUSER taps, Dattorro-scale (4-13 ms) — short, dense buildup
; replaces the removed ER section. All modes share the same tap set.
        move    #>1869,a
        move    a,x:(r7+$7e)            ; allpass 0, tap 179 (4.1 ms)
        move    #>1755,a
        move    a,x:(r7+$7f)
        move    #>1629,a
        move    a,x:(r7+$80)
        move    #>1501,a
        move    a,x:(r7+$81)            ; allpass 3, tap 547 (12.4 ms)
        move    #>$7fffff,a             ; MODE's LFO RATE scale -- fastest -- a plate shimmers.
        move    a,x:(r7+$2f)            ; parked in $2f, which the RATE block
                                        ; below folds into its own result. The
                                        ; r7 block ends at $83 ($84+ is host-
                                        ; owned and HANGS, DSP.md), so there is
                                        ; no spare slot for this.
; EARLY-REFLECTION ARRIVALS removed — six discrete taps were a flutter echo.
; A short input diffuser now fills this role (see the allpass tap constants above).
; TAP SPREAD, 1.24 : 1 (longest:shortest) -- TIGHTEST -- most homogeneous.
; The four line lengths used to be hardcoded once and merely SCALED by
; MODE, so every mode was ONE modal pattern transposed. That is why they
; sounded alike however the scale moved.
;
; The MEAN tap is held at 3178 in every mode, so MODE's tap scale keeps its
; full effect on size and the spread varies INDEPENDENTLY of it. Pinning the
; longest instead (first attempt) moved each mode's mean delay -- PLATE +12%,
; BIG -13% -- so the new lever pushed against the one already working, and
; the modes measured CLOSER together. See VOICING.md Round 3.
        move    #>$372000,a             ; line 0: 3528 of 4096
        move    a,x:(r7+$74)
        move    #>$334C00,a             ; line 1: 3283 of 4096
        move    a,x:(r7+$75)
        move    #>$2FC000,a             ; line 2: 3056 of 4096
        move    a,x:(r7+$76)
        move    #>$2C7400,a             ; line 3: 2845 of 4096
        move    a,x:(r7+$77)
        move    #>$480000,a             ; tap scale 0.5625 (was 0.65)
        move    a,x:(r7+$6f)
        move    #>$100000,a             ; diffusion offset, highest: a plate is
        move    a,x:(r7+$3f)            ; dense from the first millisecond
        move    #>$640000,a             ; damping 0.78 (was 0.953 ~= none: the
        move    a,x:(r7+$72)            ; tail literally BRIGHTENED as it
                                        ; decayed -- Round 11. Still the
                                        ; brightest mode of the three.)
        move    #>$599999,a             ; some movement, less than a hall
        move    a,x:(r7+$73)
        move    #>$570000,a             ; wet high-cut 0.68 (~8 kHz) -- plate
        move    a,x:(r7+$7a)            ; stays the bright one
        move    #>$620000,a             ; lines 4-7 tap scale 0.765625 -- moderate
        move    a,x:(r7+$6c)            ; interleave for a dense plate
        bra     md_done
md_done:

    ; ---- SIZE: scale all four tap lengths -----------------------------------
    ; tap = 3958*f on the longest line, so f = 0.400 .. 0.989 gives 1583..3914
    ; samples, 36..89 ms. The nominal taps are the MAXIMUM -- SIZE only ever
    ; shrinks the space.
    ;
    ; 32K RE-LAYOUT: the fraction words below are UNCHANGED -- $3DD800 is
    ; 1979*2048, and shifting back by 10 instead of 11 turns the same word
    ; into 3958*f against the now 4096-word line. That is the whole point of
    ; storing taps as fractions of the line: doubling the line doubles the
    ; space and leaves the character alone.
    ;
    ; These are the ORIGINAL constants, restored in v64. v62 rescaled them to
    ; cap the tap at 2046 "because mpy doubles", and it does not: measured,
    ; 0.5*0.5 = $200000 exactly. The tap was never 3134*f, never ran off the end
    ; of the 2048-word line, and SIZE was never non-monotonic. All the rescale
    ; achieved was shrinking the range to 125..574 samples -- a much smaller and
    ; ringier space, which is what came back from hardware.
    ;
    ; What WAS real, and stays fixed: SIZE reached only two of the four lines,
    ; because n1/n4 were computed every block and thrown away. The v62 modulo
    ; conversion made them live, and that is kept.
    ; Setup only -- this runs once per block, not per sample.
            move    x:(r6+$2),x0
            move    #>$4c0000,y1            ; v77: SIZE FLOOR RAISED.
            mpy     x0,y1,a
            move    #>$333000,x0            ; f = 0.400 .. 0.989, was
            add     x0,a                    ; 0.125 .. 0.993
            move    a,x0                    ; then scaled by MODE's tap scale,
            move    x:(r7+$6f),y1           ; so SIZE moves within a character
            mpy     x0,y1,a                 ; rather than replacing it
            move    a,x1
; At the old floor the whole tank was 566 samples -- a mode spacing of 78 Hz,
; which is a metallic comb by construction and no amount of diffusion fixes
; it. Confirmed by ear ("smallest size sounds worst") and by measurement
; (at SIZE=16 nearly half the spectrum's energy sits in 1% of the bins).
; Raising the floor costs the smallest spaces, which were the bad ones.
            move    #>$1,y1                 ; the odd-forcing mask, hoisted for
                                            ; all eight lines (see below)
            move    #>$1000,n0              ; likewise: 4096, used 8 times below.
                                            ; An address register is free during
                                            ; setup and move n0,b is 1 word where
                                            ; move #>$1000,b is 2.
            move    x:(r7+$74),x0           ; this MODE's line 0 fraction
            mpy     x0,x1,a
            asr     #$a,a,a                 ; back to an integer tap (4096-word lines)
            or      y1,a                    ; force the tap ODD. y1 = 1, hoisted
                                            ; above: SIZE scales and truncates the
                                            ; prime nominals and the results share
                                            ; factors -- gcd hit 204 at SIZE=104,
                                            ; two lines locked at 216 Hz. x0 cannot
                                            ; hold it (each line loads its fraction
                                            ; there), y1 is free across this block.
            move    n0,b
            sub     a,b                     ; 4096 - tap, for the modulated read
            move    b,x:(r7+$45)            ; line 0 -- was n1, which only worked
                                            ; for a STATIC tap. All four lines are
                                            ; modulated now, so all four go through
                                            ; the interpolated path.
            move    x:(r7+$75),x0           ; this MODE's line 1 fraction
            mpy     x0,x1,a
            asr     #$a,a,a                 ; back to an integer tap (4096-word lines)
            or      y1,a                    ; force the tap ODD. y1 = 1, hoisted
                                            ; above: SIZE scales and truncates the
                                            ; prime nominals and the results share
                                            ; factors -- gcd hit 204 at SIZE=104,
                                            ; two lines locked at 216 Hz. x0 cannot
                                            ; hold it (each line loads its fraction
                                            ; there), y1 is free across this block.
            move    n0,b
            sub     a,b                     ; 4096 - tap, for the modulated read
            move    b,x:(r7+$2a)
            move    x:(r7+$76),x0           ; this MODE's line 2 fraction
            mpy     x0,x1,a
            asr     #$a,a,a                 ; back to an integer tap (4096-word lines)
            or      y1,a                    ; force the tap ODD. y1 = 1, hoisted
                                            ; above: SIZE scales and truncates the
                                            ; prime nominals and the results share
                                            ; factors -- gcd hit 204 at SIZE=104,
                                            ; two lines locked at 216 Hz. x0 cannot
                                            ; hold it (each line loads its fraction
                                            ; there), y1 is free across this block.
            move    n0,b
            sub     a,b                     ; 4096 - tap, for the modulated read
            move    b,x:(r7+$2b)
            move    x:(r7+$77),x0           ; this MODE's line 3 fraction
            mpy     x0,x1,a
            asr     #$a,a,a                 ; back to an integer tap (4096-word lines)
            move    n0,b
            sub     a,b                     ; 4096 - tap
            move    b,x:(r7+$46)            ; line 3                    ; -tap, line 3 reads y:(r4+n4)
            ; ---- lines 4-7: the SAME four MODE fractions, RESCALED --------
            ; They used to be the same four fractions used raw, which gave the
            ; tank four DUPLICATE PAIRS of delay lengths -- only four distinct
            ; delays, each doubled. Degenerate delays do not add modal density,
            ; they reinforce each other, and the tail arrives as a coherent
            ; echo train: the STUTTER heard 8 Aug 2026. It also means the
            ; "modal overlap 0.157 -> 0.31" this step was justified by never
            ; happened.
            ;
            ; Scaling x1 ONCE here rescales all four of the remaining lines,
            ; because every line multiplies this MODE's fraction by it. One
            ; multiply buys four new lengths.
            ;
            ; 0.789 is chosen to interleave, not to divide: lines 0-3 land at
            ; 989/846/723/618 samples at SIZE max, lines 4-7 at 781/667/571/488,
            ; and sorted the eight are 488 571 618 667 723 781 846 989 -- every
            ; gap >= 47 samples, no pair near a small-integer ratio. A factor
            ; near 0.5 would have been free but puts every new line an octave
            ; below an old one, which reinforces rather than fills.
            ;
            ; Paid for by hoisting the odd-forcing mask into y1 above: that
            ; freed 10 words, this costs 4.
            ;
            ; Per-mode scale factor, parked in $6c by the md_* block above.
            ; ($6c, NOT $0c: $0c is the bus auto-gain 1/N, and parking the
            ; scale there overwrote it -- see the slot map at the top.)
            ; Each mode gets its own interleave (BIG 0.789, ROOM 0.719,
            ; PLATE 0.766), voiced per mode rather than derived.
            move    x:(r7+$6c),y0           ; this MODE's lines 4-7 tap scale
            mpy     x1,y0,a                 ; x1 is dead after this block (the
            move    a,x1                    ; decay block reloads it at ~1300)
            move    x:(r7+$74),x0           ; this MODE's line 0 fraction, rescaled
            mpy     x0,x1,a
            asr     #$a,a,a                 ; back to an integer tap (4096-word lines)
            or      y1,a                    ; force the tap ODD (y1=1)
            move    n0,b
            sub     a,b                     ; 4096 - tap
            move    b,x:(r7+$08)            ; line 4
            move    x:(r7+$75),x0           ; this MODE's line 1 fraction, rescaled
            mpy     x0,x1,a
            asr     #$a,a,a
            or      y1,a                    ; force the tap ODD (y1=1)
            move    n0,b
            sub     a,b
            move    b,x:(r7+$09)            ; line 5
            move    x:(r7+$76),x0           ; this MODE's line 2 fraction, rescaled
            mpy     x0,x1,a
            asr     #$a,a,a
            or      y1,a                    ; force the tap ODD (y1=1)
            move    n0,b
            sub     a,b
            move    b,x:(r7+$0a)            ; line 6
            move    x:(r7+$77),x0           ; this MODE's line 3 fraction, rescaled
            mpy     x0,x1,a
            asr     #$a,a,a
            move    n0,b
            sub     a,b                     ; 4096 - tap
            move    b,x:(r7+$4b)            ; line 7
            move    #>$fff,m6           ; PRE-DELAY modulo (4096, unchanged --
                                        ; the pre-delay buffer did not shrink
                                        ; in the 8-line re-layout). Moved off
                                        ; m5 in v70 so m5 can carry the
                                        ; allpasses. r6 is unused inside the
                                        ; sample loop, so it costs nothing.
            move    #>$fff,m5           ; LINE modulo, 4096 (increment 2): what
                                        ; runs under m5 between here and the
                                        ; sample loop is the lines 4-7 priming,
                                        ; whose y:(r5+n5) reads must wrap
                                        ; inside a 4096-word LINE. The gain-
                                        ; table writes in between never cross a
                                        ; 4096 boundary (16 words inside
                                        ; shared+0x4530), so the modulo is
                                        ; transparent to them. The in-loop AP
                                        ; priming below switches m5 to $1ff
                                        ; itself and leaves it at $7ff, which
                                        ; is what the sample loop's DIFFUSERS
                                        ; need. Set here, AFTER the warm-up's
                                        ; linear r5 walk (which m5 is forced
                                        ; linear for at entry); the state save
                                        ; at the end forces it linear again.

; ---- feedback gain from TIME --------------------------------------------
; p0 arrives as value<<16. The 8x8 Walsh-Hadamard has unnormalised row norm
; √8, and the MODE blocks above have been scaled by 2/√8 so that the stored
; value already folds in the orthonormalising factor. Loop gain equals g.
;
; g spans 0.875..0.999 (stored as g/2; the per-line gain block doubles it).
; Decay is g^n where n is passes, so RT60 scales with the loop time. When the
; 16K squeeze halved the mean tap to ~26 ms, g was remapped to g_old^0.5
; (0.935..0.9995) to keep the same RT60 over the knob. INCREMENT 2 doubles
; the lines back to the ~51 ms mean tap that mapping compensated for, so the
; compensation comes OFF again -- keeping it would double every decay and
; push TIME's usable range off the top of the knob. These are the original
; constants: base $380000 = 0.875/2, span $080000 = 0.124/2 over the knob.
        move    x:(r6),x0
        move    #>$080000,y1
        mpy     x0,y1,a
        move    #>$380000,x0
        add     x0,a
        move    a,x1                    ; fold in MODE's decay scale, parked in
        move    x:(r7+$1e),y1           ; $1e by the md_ block above. TIME still
        mpy     x1,y1,a                 ; spans its full range inside a character.
        move    a,x:(r7+$1e)

; ---- per-line decay gains (PLAN.md 1.1) ---------------------------------
; $1e is one decay gain, but the lines circulate at different rates, so equal
; gain per PASS is unequal decay per SECOND: at ROOM's defaults the longest
; line (tap 882, 50 passes/s) loses ~50 dB/s while the shortest (tap 400,
; 110 passes/s) loses ~110 dB/s. An eight-line tank decaying into a two- or
; three-line one IS the tail that starts lush and turns metallic.
;
; Jot's fix is g_i = g^(T_i/T_ref), linearised about the loop-neutral point:
;
;     stored_i = a + r_i*($1e - a),   r_i = T_i/T_0 (line 0 is the longest),
;     a = 1/sqrt(8) = $2D413C
;
; THE ACCOUNTING, all of it measured 9 Aug 2026 (this block shipped twice
; before with wrong constants and self-oscillated both times):
;   - The multiplies in this toolchain DO NOT DOUBLE. mpy/mpysu produce the
;     plain product x*y. Measured two independent ways: $1e peeked at three
;     TIME values fits TIME_val*md exactly (0.4674/0.5001/0.4999 * 0.6505 =
;     0.3040/0.3146/0.3251), and the first build's peeked gains solve to
;     k = 1.0002 for the priming mpy. Every "mpy doubles" claim in older
;     comments is about the CHIP's fractional convention, not this emulator.
;     ⚠ VERIFY ON HARDWARE (BURN trip): if silicon's mpy shifts left where
;     the emulator's does not, every decay time halves-or-doubles on the
;     unit and this block's anchor is wrong there.
;   - So the line's per-pass multiplier IS the stored word, and the loop is
;     diag(stored_i)*H8 with ||H8|| = sqrt(8): the UNIFORM engine is already
;     norm-stable (max $1e = 0.3252, radius <= 0.92). The two explosions were
;     nothing exotic: gains of 0.41..0.48 pushed the norm over 1.
;   - Loop-neutral is stored = 1/sqrt(8). $1e can never reach it (max
;     TIME_val 0.4999 * max md 0.6505 = 0.3252 < 0.3536), so ($1e - a) is
;     ALWAYS negative and stored_i = a + r_i*($1e - a) is a weighted average
;     sitting strictly below a: max stored ~ 0.341 at the shortest line,
;     radius <= 0.341*sqrt(8) = 0.965. Stable BY NORM at every knob in every
;     mode -- no cancellation argument, no measured-F fudge.
;   - r_i wants T_i/T_0. The fractions in $74..$77 are HALF-scale (frac_0 =
;     0.4832), so r_i = 2*frac_i (times $6c's scale for lines 4-7) -- and
;     since the mpy does NOT double, the 2 is paid with an explicit asl.
;
; Primed HERE, after TIME and MODE have both folded into $1e -- the table-B
; weight chain near the top of the block runs before $1e is final. Gains land
; in table B's SECOND word (base $0d, +1, stride 2), which was primed zero
; and read once purely to step r6 -- the write-back loops read it as the live
; per-line gain at the same instruction count. Per block, nothing per sample.
; m5 is linear here (set $ffffff by the auto-gain block, untouched until the
; loop seeding below), so r5 walks clean.
;
; ($1e - a) is NEGATIVE, so it rides in y1, never y0: `mpy x0,y0` assembles
; as mpysu (the documented dsp_asm trap) and an unsigned second operand
; corrupts a negative multiplier. `mpy x0,y1` is a pairing that encodes
; signed (verified in the disassembly).
        move    x:(r7+$0d),a            ; table B base
        move    #>$1,x0
        add     x0,a
        move    a,r5                    ; -> line 0's gain word
        move    #2,n5                   ; stride 2 (short immediate: address
                                        ; register, zero-extended -- safe)
        move    #>$2d413c,x1            ; anchor a = 1/sqrt(8), held for sub/add
        move    x:(r7+$1e),a
        sub     x1,a
        move    a,y1                    ; ($1e - a), group A's multiplier
        move    x:(r7+$74),x0           ; line 0 fraction (half-scale)
        mpy     x0,y1,a                 ; frac*($1e-a) -- plain product
        asl     a                       ; r_0*($1e-a), r_0 = 2*frac_0 = 0.966
        add     x1,a                    ; + a
        move    a,y:(r5)+n5             ; line 0 gain
        move    x:(r7+$75),x0
        mpy     x0,y1,a
        asl     a
        add     x1,a
        move    a,y:(r5)+n5             ; line 1 gain
        move    x:(r7+$76),x0
        mpy     x0,y1,a
        asl     a
        add     x1,a
        move    a,y:(r5)+n5             ; line 2 gain
        move    x:(r7+$77),x0
        mpy     x0,y1,a
        asl     a
        add     x1,a
        move    a,y:(r5)+n5             ; line 3 gain
; Lines 4-7 share the fractions, scaled by $6c: r_i = 2*frac_i*scale. The
; scale folds into y1 once (plain product again -- no asr compensation, the
; first build's asr was undoing a doubling that never happens).
        move    x:(r7+$6c),x0           ; lines 4-7 tap scale (positive)
        mpy     x0,y1,a                 ; scale*($1e-a)
        move    a,y1                    ; group B's multiplier
        move    x:(r7+$74),x0
        mpy     x0,y1,a
        asl     a
        add     x1,a
        move    a,y:(r5)+n5             ; line 4 gain
        move    x:(r7+$75),x0
        mpy     x0,y1,a
        asl     a
        add     x1,a
        move    a,y:(r5)+n5             ; line 5 gain
        move    x:(r7+$76),x0
        mpy     x0,y1,a
        asl     a
        add     x1,a
        move    a,y:(r5)+n5             ; line 6 gain
        move    x:(r7+$77),x0
        mpy     x0,y1,a
        asl     a
        add     x1,a
        move    a,y:(r5)                ; line 7 gain

; ---- HI: high cut, on the knob LABELLED LP ($4) --------------------------
; The one-pole is s += c*(d-s), so a LARGE c tracks the input and keeps highs.
; HI reads as an EQ control, so it has to run the other way from the old DAMP:
; HI=0 gives c=0.125 (dark), HI=127 gives c~0.99 (bright).
;
; MOVED from $1 (labelled SHVG) to $4 (labelled LP) in v61. A one-pole in
; the feedback path IS a low-pass, so this control finally sits under the
; name that describes it. See the LO block below for the other half.
        move    x:(r6+$4),x0
        move    #>$700000,y1
        mpy     x0,y1,a
        move    #>$100000,x0
        add     x0,a
        move    a,x1                    ; v95: scale by MODE's damping constant
        move    x:(r7+$72),y1           ; before it lands. The scale is <= 1.0,
        mpy     x1,y1,a                 ; so c stays inside its safe range and
        move    a,x:(r7+$1f)            ; the knob still spans within a mode

; ---- LO: low cut inside the feedback path, on the knob LABELLED HP ($3) --
; The Blackhole/Supermassive pair is a low AND a high cut inside the loop,
; shaping the decay per band rather than the wet EQ. gen_reverb.py reserved
; page-1 slot $3 for exactly this from the start ("P_SPARE ... freed for
; LO") and never built it, because at the time the cycle headroom was not
; measured. It is now: stageprobe5/6 put ~1080 instructions a sample per
; DSP within reach and this engine uses ~135, so the ~44 this costs is
; affordable several times over.
;
; $3 is the knob labelled HP, and a low cut IS a high-pass, so the label is
; honest. HP=0 gives coefficient 0 -- the state never moves, nothing is
; subtracted, and the filter is bypassed exactly. HP=127 gives ~0.155,
; sits INSIDE the loop and its cut compounds every pass. Measured:
; the late tail falls 775 -> 308 -> 128 across the knob at TIME=64,
; while RT60 stays ~4.2-4.6 s. A larger coefficient annihilates it.
        move    x:(r6+$3),x0
        move    #>$040000,y1
        mpy     x0,y1,a
        move    a,x:(r7+$40)            ; LO coefficient

; ---- ER level: REMOVED (9 Aug 2026) -----------------------------------------
; The six-tap ER section was a flutter echo. The input diffuser (4-13 ms,
; Dattorro-scale) now fills this role. $6c is left at zero (warm-up default)
; and is never written — the per-mode ER-level constants at $6c were removed.
; See VOICING.md Round 7.

; ---- MIX: a real crossfade, not wet added on top of unity dry (v94) ------
; It used to be out = dry + wet*MIX, so dry stayed at full scale however wet
; the effect was set. That cannot help clipping on a hot source -- 1.0 + 0.78
; is 1.78 -- and it means MIX never actually removes the dry signal, so the
; top of the knob is not "wet" in the sense every other reverb means it.
;
; out = dry*(1-MIX) + wet*MIX. MIX arrives as value<<16, so 1-MIX is just
; $7fffff minus it.
        move    x:(r6+$5),x0
        move    x0,x:(r7+$20)           ; wet gain, unchanged: rises the whole way
; v96: HOLD the dry at unity for the bottom half of the knob, then crossfade it
; away over the top half. A straight 1-MIX crossfade measured the knob getting
; ~7 dB QUIETER as it was turned up (-22.0 dBFS at MIX=0 down to -28.8 at 96),
; because a reverb's wet is inherently far below its dry: the tail spreads the
; same energy over seconds, so swapping dry for wet at equal gain loses level.
; Turning a reverb up should not shrink the sound.
;
; dry = 1                 for MIX <= 0.5      -- pure "mix more in"
;     = 2 * (1 - MIX)     for MIX >  0.5      -- reaches fully wet at the top
;
; Keeps what v94 was actually after (the top of the knob IS wet, which the old
; additive law could never reach) and drops what made it feel wrong.
        move    #>$400000,a             ; 0.5
        move    x0,b
; `cmp a,b` HERE ENCODED AS `max a,b` -- disassembled 8 Aug 2026, opcode
; $20001d. Accumulator-to-accumulator CMP is part of the dsp_asm mis-encoding
; family this project already lost two attempts to (`tfr a,b` -> `rnd b`), and
; this was the ONE live instance of it in shipping code.
;
; Why it was not caught by ear or by measurement: MAX updates ONLY the C bit
; (emulator `op_Max`: `ccr_update_ifLess(CCRB_C)`), while `blt` tests N^V. So
; the branch was reading flags this block never set, and the v96 MIX sweep
; still measured exactly the intended law -- flat to MIX=64, falling above it.
; It was right by accident, on whatever set N^V earlier in the parameter block.
; MAX also writes B = max(A,B); harmless only because b is dead below.
;
; SUB is the documented workaround (ADD/SUB encode correctly in this form and
; SUB sets N^V exactly as CMP would). `sub a,b` leaves b = MIX - 0.5, which is
; the comparison this always meant to make.
        sub     a,b                     ; MIX - 0.5, and sets N^V for the blt
        blt     mixhold
        move    #>$7fffff,a
        sub     x0,a                    ; 1 - MIX, and <= $3fffff on this branch
        asl     #$1,a,a                 ; so the double cannot overflow into sign
        bra     mixset
mixhold:
        move    #>$7fffff,a             ; dry at unity across the bottom half
mixset:
        move    a,x:(r7+$70)            ; dry gain

; ---- ->DELAY send level -- page-2 slot 11, the LOW bits of $e (v92) -----
; Moved off slot 8 ($d's knob field) so DIFFUSION can have it. A companion
; field carries a plain 0..127 integer in the low bits, not a left-aligned
; knob, so it is masked and shifted UP to knob scale. DSP.md section 9: all
; six page-2 slots reach the DSP with a full 0..127 range -- measured, and it
; took seven probe builds, so do not re-derive it.
        move    x:(r6+$e),a
        and     #>$7f,a                 ; 0..127 in the companion field. The
                                        ; 8-step restriction is gone: what made
                                        ; this control unusable was the
                                        ; inherited DISPLAY FORMATTER, not the
                                        ; value count, and with that zeroed it
                                        ; draws as an ordinary knob. $7f, not
                                        ; $ff, so a stale byte cannot exceed
                                        ; full scale after the shift.
        move    a1,x0                   ; AND cleans A1 only
        move    x0,a
        asl     #$10,a,a                ; left-align like a knob
        move    a,x:(r7+$69)

; ---- MOD: modulation depth, scales the LFO triangle ---------------------
; MOVED from $4 to $1 (labelled SHVG) in v61, swapping with HI above: $4
; is labelled LP and now carries the high cut, which is what it says.
        move    x:(r6+$1),x0
        move    x:(r7+$73),y1           ; v95: scaled per MODE, only ever down
        mpy     x0,y1,a                 ; (BIG sits at unity), so the knob keeps
        move    a,x:(r7+$28)            ; its full range inside each character

; ---- WIDTH: 0 = mono, 127 = full stereo -- slot 9, $d's LOW bits (v92) --
; Moved off slot 6 so MOD SPEED can have it. Same companion-field handling as
; ->DELAY above.
        move    x:(r6+$d),a
        and     #>$7f,a                 ; 0..127, as above
        move    a1,x0
        move    x0,a
        asl     #$10,a,a                ; mono .. full stereo
        move    a,x:(r7+$2c)

; ---- DIFFUSION: allpass coefficient -- slot 8, $d's KNOB field (v92) -----
; New control. It scales the allpass coefficient g, which was the fixed
; literal $5a0000 (0.703) in all six allpasses. Range 0.35 .. 0.78: below
; that an allpass stops diffusing and starts sounding like a plain delay,
; above ~0.8 the ringing this file documents gets worse rather than better.
;
; MUST mask the knob field -- $d's low bits now carry WIDTH, and reading the
; whole word would add WIDTH into the coefficient.
        move    x:(r6+$d),a
        and     #>$7f0000,a             ; knob field only
        move    a1,x0
        move    x0,a
        move    a,x0
        move    #>$2a0000,y1            ; span sized so that base + full DIFF +
        mpy     x0,y1,a                 ; the LARGEST mode offset still lands
        move    #>$2d0000,x0            ; under ~0.80. At the old $380000 span
        add     x0,a                    ; PLATE overflowed $7fffff at DIFF=127
        move    x:(r7+$3f),x0           ; and g read NEGATIVE; the others sat at
        add     x0,a                    ; 0.88-0.97, where an allpass is a
                                        ; near-oscillator, not a diffuser.
                                        ;
                                        ; v95: the mode offset was added TWICE
                                        ; here. The span above is sized so that
                                        ; base + full DIFF + the largest offset
                                        ; lands at 0.352+0.326+0.125 = 0.802 --
                                        ; the "under ~0.80" this comment claims,
                                        ; and only true with ONE add. The second
                                        ; put PLATE at 0.93 at DIFF=127, back in
                                        ; the near-oscillator range the comment
                                        ; warns about, which is the opposite of
                                        ; diffusion and blurs the modes together.
        move    a,x:(r7+$6d)            ; g, for every allpass

; ---- RATE: LFO increment, ~0.34 Hz .. ~3 Hz -----------------------------
; 8x what it would be per sample, because the LFO is stepped once per block.
; ---- LFO RATE: fixed and SLOW, decoupled from MOD -----------------------
; v84, and this is the whole seasickness. MOD used to drive the RATE as
; well as the depth, reaching 2.84 Hz at full. Pitch shift comes from the
; RATE OF CHANGE of the delay, not its depth:
;
;     63 samples at 2.84 Hz -> 716 samples/s -> ~28 cents of vibrato
;     63 samples at 0.25 Hz ->  63 samples/s -> ~2.5 cents, inaudible
;
; So the depth was never the problem. v78 halved it, which halved the
; vibrato AND halved the smearing -- "less seasick but more ringy". Keeping
; the depth and slowing the sweep gives the smearing without the pitch
; artifact.
;
; r6+$d is not read: hardware confirmed the page-2 knob does nothing, so
; that slot is host-side, not a parameter.
; MOD SPEED is now a knob -- page-2 slot 6, reading $b (v92). v84 fixed the
; rate deliberately, because coupling it to MOD made the reverb seasick: 63
; samples at 2.84 Hz is ~28 cents of vibrato, the same depth at 0.25 Hz is
; ~2.5 cents and inaudible. Exposing it is right, but the range is
; deliberately capped LOW -- $180 to ~$680, roughly 0.12 to 0.55 Hz -- so the
; top of the knob still lands well under where v84 found it unusable. It also
; never reaches zero: a static tank rings.
; v101: SPEED is now SHMR. The LFO rate is PINNED at 40, which VOICING Round 5
; measured as its shallow optimum -- the knob's default was 64, so this is a
; small improvement in its own right, not merely a sacrifice.
;
; The knob is read HERE, once per block, and cached in $0e. It cannot be read
; inside the sample loop: r6 is the PRE-DELAY POINTER in there (y:(r6+n6)), not
; the parameter block, so x:(r6+$b) in the loop reads whatever the pre-delay
; buffer happens to be near. That cost a debugging round.
        move    x:(r6+$b),a             ; SHMR amount, value<<16
        and     #>$7f0000,a
        move    a1,x0                   ; SCALED TO A QUARTER. The raw knob is a
        move    #>$600000,y1            ; loop gain on TOP of the tank's own
        mpy     x0,y1,a                 ; feedback, and by ear 25/127 raw (0.20)
        move    a,x:(r7+$0e)            ; is the sweet spot while 45 at TIME=90
                                        ; already runs away. A quarter puts that
                                        ; sweet spot near the top of the travel
                                        ; instead of a fifth of the way up.
        move    #>$280000,a             ; 40 << 16, where the knob used to land
        move    a1,x0
        move    x0,a
        move    a,x0
        move    #>$500000,y1
        mpy     x0,y1,a
        asr     #$b,a,a                 ; 2048-word lines: 11-bit shift, not 10
                                        ; 1.0 Hz) was reported as barely
                                        ; audible. This doubles the top to
                                        ; ~1.9 Hz, still under the 2.84 Hz v84
                                        ; measured as outright seasick, and the
                                        ; floor stays where a static tank
                                        ; cannot happen.
        move    #>$180,x0
        add     x0,a
        move    a,x1                    ; fold in MODE's LFO rate scale, which the
        move    x:(r7+$2f),y1           ; md_ block parked here. SPEED still spans
        mpy     x1,y1,a                 ; its full range inside each character, the
        move    a,x:(r7+$2f)            ; same shape as MOD depth and damping.

; ---- PRE: pre-delay in samples, 0 .. 4064 (93 ms) -----------------------
; v * 32 since the 32K re-layout doubled PRE_LEN to 4096 (it was v * 16 into
; a 2048-word buffer, 0..46 ms). The scale MUST keep this below PRE_LEN: the
; read is y:(r6+n6) under m6 modulo, and a modulo offset larger than the buffer is
; undefined on the DSP56300. It does not wrap -- the read returns nothing, the
; tank gets no input, and the reverb goes completely silent.
;
; THE SLOT IS $c, NOT $e. v58 read $e, the pre-delay was inaudible on
; hardware and did not respond to the knob, and stock DARK says why:
;
;   $e is a FLAG word -- stock does `move x:(r6+$e),a / btst #$8,a` at
;   P:0x173c and P:0x1a0d and branches on it. A knob arrives as
;   value<<16, so bit 8 is always clear and `asr #$c` of it is 0: a
;   one-sample pre-delay, forever, whatever the knob does.
;   $c is stock's own PRE. At P:0x17d4 it does exactly what this code
;   does: mask the knob field, scale it, set m5 = $7ff (the same 2048
;   modulo), back a pointer up by the offset, read delayed / write
;   input, and persist the pointer in its own r7 slot.
;
; Stock's scale is `mpy #$7f0 / add #$10` = v*~16 + 16, max 2031 -- our
; v*16 (max 2032) was the same ramp, so only the slot was ever wrong; the
; re-layout doubles it to v*32 to reach the end of the bigger buffer.
; The mask is stock's too: the slot can carry bits outside the knob
; field, and asr alone would drag them into the sample count.
; SLOT MOVED $c -> $e. Measured with dsp/page2_probe.asm on hardware: page-2
; display slots drive $b (slot 6), $d (slot 8) and $e (slot 10) -- and NOTHING
; drives $c. Stock DARK reads its own pre-delay from $c, which is why earlier
; builds read it here, but no page-2 knob can reach $c, so PRE was dead by
; construction. $e carries a full 0..127 knob value (the probe's slot-10 test
; triggered on it), so PRE lives there now. See DSP.md section 9.
        move    x:(r6+$e),a
        and     #>$7f0000,a             ; knob field only, as stock does
        asr     #$b,a,a                 ; v*32 (was #$c, v*16)
        move    a,x:(r7+$29)
        move    #>$1,x0                 ; the read happens BEFORE the write, so
        add     x0,a                    ; the offset is -(PRE+1): at PRE=0 that
        neg     a                       ; is one sample, not a whole buffer of
        move    a,n6                    ; staleness
        move    a,x:(r7+$62)            ; ...and stash for the tank input below
                                        ; now use n6 as their own index, so
                                        ; the pre-delay reloads it each sample
        move    x:(r7+$83),a            ; the same counter again
        move    #>$fff,x0               ; phase is 0..4095 now, and the
        and     x0,a                    ; pre-delay buffer is 4096 to match
        move    a1,x0                   ; A2-clean here too: same garbage, same
        move    x0,a                    ; saturation, same bus hang
        move    x:(r7+$38),x0
        add     x0,a
        move    a,x:(r7+$30)            ; NOT $6d: the width matrix uses that

; ---- EIGHT INDEPENDENT LFOs, one per tank line --------------------------
; v72. Before this, ONE phase accumulator produced a triangle and its
; inverse, so four lines shared two phases at a single rate --
; correlated by construction, which is exactly what leaves a periodic tail.
; Each of the eight lines now free-runs at its own rate, the multipliers
; chosen so the periods do not align (and the new four are prime-relative
; to the existing four). PLAN.md step 1.2.
;
; Per BLOCK, not per sample, so ~5 cycles/sample amortised.

        move    x:(r7+$3e),a            ; line 0  (1.000x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #>$7f0000,y1               ; rate x0.992
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf3e
        move    x0,x:(r7+$3e)
lf3e:
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle, 0 .. $400000
        move    a,x:(r7+$5a)            ; stash: the AP modulator below clobbers it
        move    a,x0
; ---- in-loop allpass modulation (Dattorro): FIXED depth, never zero ------
; The in-loop allpasses were static. Dattorro modulates his, and a moving
; allpass smears the modes on every circulation -- which REVERB.md names as
; the only structural fix for the ringing at this delay budget. Costs cycles
; and NO memory, which is the right shape now: the 32K re-layout filled the
; allocation, but the cycle budget has ~551 spare.
;
; Depth is fixed at $200000 rather than following MOD, so it can never reach
; zero -- the same rule this file already records for the tank ("modulation
; must never reach zero"; a completely static tank rings). MOD stays the
; tank's control alone.
        move    #>$200000,y1
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$52)            ; AP integer offset, 0..~31 samples
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; shift by n-1, never n (REVERB.md's
        move    a,x0                    ; interpolation fraction rule)
        move    x0,x:(r7+$53)            ; AP fraction
        move    x:(r7+$5a),a            ; triangle back for the tank's own use
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$21)           ; integer offset, 0..126 samples
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
                                        ; scales by 2^7. v95: this had regressed
                                        ; to #$8 -- REVERB.md's "live from v72 to
                                        ; v79" bug, back again, with the rule
                                        ; still written next to it.
        move    x0,x:(r7+$22)           ; interpolation fraction

        move    x:(r7+$4f),a            ; line 1  (1.168x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #>$6cc000,y1               ; rate x0.850
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf4f
        move    x0,x:(r7+$4f)
lf4f:
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle, 0 .. $400000
        move    a,x:(r7+$5b)            ; stash: the AP modulator below clobbers it
        move    a,x0
; ---- in-loop allpass modulation (Dattorro): FIXED depth, never zero ------
; The in-loop allpasses were static. Dattorro modulates his, and a moving
; allpass smears the modes on every circulation -- which REVERB.md names as
; the only structural fix for the ringing at this delay budget. Costs cycles
; and NO memory, which is the right shape now: the 32K re-layout filled the
; allocation, but the cycle budget has ~551 spare.
;
; Depth is fixed at $200000 rather than following MOD, so it can never reach
; zero -- the same rule this file already records for the tank ("modulation
; must never reach zero"; a completely static tank rings). MOD stays the
; tank's control alone.
        move    #>$200000,y1
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$54)            ; AP integer offset, 0..~31 samples
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; shift by n-1, never n (REVERB.md's
        move    a,x0                    ; interpolation fraction rule)
        move    x0,x:(r7+$55)            ; AP fraction
        move    x:(r7+$5b),a            ; triangle back for the tank's own use
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$23)           ; integer offset, 0..126 samples
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
                                        ; scales by 2^7. v95: this had regressed
                                        ; to #$8 -- REVERB.md's "live from v72 to
                                        ; v79" bug, back again, with the rule
                                        ; still written next to it.
        move    x0,x:(r7+$24)           ; interpolation fraction

        move    x:(r7+$50),a            ; line 2  (0.887x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #>$5b0000,y1               ; rate x0.711
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf50
        move    x0,x:(r7+$50)
lf50:
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle, 0 .. $400000
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$56)           ; integer offset, 0..126 samples
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
                                        ; scales by 2^7. v95: this had regressed
                                        ; to #$8 -- REVERB.md's "live from v72 to
                                        ; v79" bug, back again, with the rule
                                        ; still written next to it.
        move    x0,x:(r7+$57)           ; interpolation fraction

        move    x:(r7+$51),a            ; line 3  (1.426x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #>$4a0000,y1               ; rate x0.578
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf51
        move    x0,x:(r7+$51)
lf51:
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle, 0 .. $400000
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$58)           ; integer offset, 0..126 samples
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
                                        ; scales by 2^7. v95: this had regressed
                                        ; to #$8 -- REVERB.md's "live from v72 to
                                        ; v79" bug, back again, with the rule
                                        ; still written next to it.
        move    x0,x:(r7+$59)           ; interpolation fraction

; ---- LFOs lines 4-7 (8-line), no allpass modulation ----------------------
; Rates chosen prime-relative to lines 0-3 (0.992, 0.850, 0.711, 0.578) so
; the eight periods do not align.

        move    x:(r7+$47),a            ; line 4  (0.922x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #>$760000,y1               ; rate x0.922
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf47
        move    x0,x:(r7+$47)
lf47:
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle, 0 .. $400000
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$00)           ; integer offset, line 4
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
        move    x0,x:(r7+$01)           ; interpolation fraction, line 4

        move    x:(r7+$48),a            ; line 5  (0.758x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #>$610000,y1               ; rate x0.758
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf48
        move    x0,x:(r7+$48)
lf48:
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle, 0 .. $400000
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$02)           ; integer offset, line 5
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
        move    x0,x:(r7+$03)           ; interpolation fraction, line 5

        move    x:(r7+$49),a            ; line 6  (0.602x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #>$4d0000,y1               ; rate x0.602
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf49
        move    x0,x:(r7+$49)
lf49:
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle, 0 .. $400000
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$04)           ; integer offset, line 6
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
        move    x0,x:(r7+$05)           ; interpolation fraction, line 6

        move    x:(r7+$4a),a            ; line 7  (0.430x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #>$370000,y1               ; rate x0.430
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a                    ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf4a
        move    x0,x:(r7+$4a)
lf4a:
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle, 0 .. $400000
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$06)           ; integer offset, line 7
        move    x1,a
        move    #>$00ffff,x0
        and     x0,a
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
        move    x0,x:(r7+$07)           ; interpolation fraction, line 7

; ---- STAGE 1: loop constants preloaded into spare AGU registers ---------
; `move #>$7ff,x0` is a TWO-WORD instruction: opcode plus a 24-bit immediate,
; and the extra program fetch costs an extra CYCLE. `move n1,x0` is one word
; and one cycle. The masks and the allpass coefficient are loop-invariant and
; were being re-fetched every time -- 17 wasted cycles a sample.
;
; n1..n4 and n6 are genuinely free: v65 moved lines 0 and 3 onto arithmetic
; interpolated reads, which orphaned n1/n4, and n2/n3/n6 were never used. The
; tank pointers r1..r4 use modulo (m1..m4) but never indexed (rN+nN)
; addressing, so nothing reads these as offsets.
;
; Written here, well before the loop, with data moves following -- an AGU
; register write next to its address register is the interlock that froze v47.
                                        ; (n6 now carries the pre-delay offset;
                                        ; the allpass mask is gone -- the AGU
                                        ; masks for free under m5 = $7ff)
        move    x:(r7+$31),x0           ; two data moves before the loop, to
        move    x:(r7+$31),x0           ; clear the AGU write


; ---- in-loop allpass setup (v74) ---------------------------------------
; Dattorro puts a MODULATED allpass inside each tank half, before the long
; delay -- not in the input diffusion chain (v73 tried that and measured
; worse). An allpass in the feedback path multiplies echo density on every
; circulation, which is how a smooth tail comes out of finite memory. We had
; none at all: one echo per line per pass, where Dattorro gets a burst.
;
; Two of them, 512 words each, now in the SHARED WINDOW at +0x4000/+0x4200.
; They share m5 = $7ff with the input diffusers, so no M write.
;
; x0 held the PRIVATE base from the two AGU-clearing loads above, and the
; private allocation now carries tank lines only, so it is reloaded here.
; Those two loads still have to happen -- they exist to space the AGU write,
; not to deliver a value -- so this costs one instruction, not three.
        move    #>$30000,x0             ; -> $38000 on payload B
        move    #>$4000,a
        add     x0,a
        move    a,x:(r7+$5e)            ; allpass A base, on line 0
        move    #>$4200,a
        add     x0,a
        move    a,x:(r7+$5f)            ; allpass B base, on line 1
; v85: SHORTER. 401 and 601 were 26-64% of the line they feed, where the
; classic figure is ~15%. Above roughly 20% an allpass in a feedback loop
; stops diffusing and starts DISPERSING -- delaying frequencies by different
; amounts -- which is the mechanism a spring reverb is built on, and which
; the user hears as metallic when the wet is turned up.
;
; 32K RE-LAYOUT: the taps DOUBLE with the lines they feed (149->298,
; 223->446). What v85 fixed was a PROPORTION, not an absolute length, so
; holding 9.7%/14.5% against a line that is now twice as long means doubling
; the tap -- leaving them at 149/223 would halve the proportion to 4.8%/7.3%
; and change the character the re-layout is meant to preserve.
        move    #>214,a
        move    a,x:(r7+$60)            ; 512 - 298    (9.7% of the longest line)
        move    #>66,a
        move    a,x:(r7+$61)            ; 512 - 446    (14.5%)
; v127: the in-loop allpass buffers are 512 words, halved again from v100's
; 1024. Their taps are 298 and 446 and the modulation adds at most ~31, so 477
; is the longest read they can ever make -- 512 is the smallest power of two
; that still clears it. Halving frees the 2048 CONTIGUOUS, 2048-ALIGNED words
; at base+0x7000 that the shimmer needs, and it is bit-identical because the
; tap distance behind the write pointer is unchanged; only the wrap point
; moves, and nothing reads far enough back to see it. VERIFIED, not argued:
; a shimmer-excised build renders byte-identical audio (1241ac86c3ba).
;
; They also MOVED, to base+0x7a00/0x7c00. Putting allpass A at base+0x7800 --
; the obvious choice -- silently overwrote the bus auto-gain RECIPROCAL TABLE
; that lives there, which cost 2.5 dB of level and stretched the tail from
; 1.40 s to 5.90 s. The null test above is what caught it.

; ---- STAGE 2: read offsets for the four modulo-indexed line reads -------
; offset_k = (4096 - tap_k) - lfo_k, so y:(r+offset) lands on the delayed
; sample with no masking, no base add and no second address. Each line is
; primed one sample further back first, which seeds the interpolation carry
; for the first sample of the block.
;
; ROLLED: these used to land in n1..n4, one N register per line, which is
; exactly the thing that cannot scale past four lines -- there are only four
; spare N registers and eight lines would want eight. They go into the state
; table instead, where the loop indexes them, and n1..n4 stop being per-line
; resources altogether. n1 is reloaded below with the line stride, the one
; constant the rolled loop does still want in an AGU register (`move n1,x0`
; is one word where `move #>$1000,x0` is two -- STAGE 1's rule, still true).
;
; The seeding read still goes through r1..r4, because they are already sitting
; on the four line bases here and the priming happens once per block, not per
; sample: there is nothing to save by rolling it.
        move    #>$4,n6                 ; w2 -> the NEXT line's w0
        move    x:(r7+$0b),a            ; the per-line state table
        move    a,r6
        move    #>$1,x1                 ; "one sample further back", hoisted:
                                        ; `move x1,x0` is one word, `move
                                        ; #>$1,x0` is two, and it is used
                                        ; once per line
        move    x:(r7+$45),a            ; -- line 0: (4096 - tap)
        move    x:(r7+$23),x0           ;    its own LFO integer offset
        sub     x0,a
        move    a,y:(r6)+               ; w0: the read offset
        move    x1,x0
        sub     x0,a
        move    a,n1                    ; primed one sample further back
        move    x:(r7+$24),a            ; w1: the interpolation fraction --
        move    a,y:(r6)+               ;     and it spaces the n1 write
        move    y:(r1+n1),a
        move    a,y:(r6)+n6             ; w2: seed the interpolation carry
        move    x:(r7+$2a),a            ; -- line 1
        move    x:(r7+$21),x0
        sub     x0,a
        move    a,y:(r6)+
        move    x1,x0
        sub     x0,a
        move    a,n2
        move    x:(r7+$22),a
        move    a,y:(r6)+
        move    y:(r2+n2),a
        move    a,y:(r6)+n6
        move    x:(r7+$2b),a            ; -- line 2
        move    x:(r7+$56),x0
        sub     x0,a
        move    a,y:(r6)+
        move    x1,x0
        sub     x0,a
        move    a,n3
        move    x:(r7+$57),a
        move    a,y:(r6)+
        move    y:(r3+n3),a
        move    a,y:(r6)+n6
        move    x:(r7+$46),a            ; -- line 3
        move    x:(r7+$58),x0
        sub     x0,a
        move    a,y:(r6)+
        move    x1,x0
        sub     x0,a
        move    a,n4
        move    x:(r7+$59),a
        move    a,y:(r6)+
        move    y:(r4+n4),a
        move    a,y:(r6)+n6
; ---- lines 4..7 (8-line) -- same priming, new lines -----------------------
; Line bases are in $36/$37/$4c/$4d (init), LFO offsets in $00-$07, tap
; bases in $08-$0a/$4b. n1..n4 are free after line 3's priming and are
; reused here for the carry-seed index; the stride reload below will
; overwrite them anyway.
;
; Phase comes from r1 (all eight lines share one write phase, stored in
; $83, and r1 was rebuilt from it). The priming reads from the delay line
; at (line_base + phase + offset), one sample before the block's first
; tap, under m5 = $fff -- same modulo the sample loop's tank walk uses.
        move    x:(r7+$08),a            ; -- line 4: (4096 - tap)
        move    x:(r7+$00),x0           ;    its LFO integer offset
        sub     x0,a
        move    a,y:(r6)+               ; w0
        move    x1,x0
        sub     x0,a
        move    a,n5                    ; carry seed index (reuses n5)
        move    x:(r7+$01),a            ; w1: the interpolation fraction
        move    a,y:(r6)+
        move    r1,a                    ; line 0 base + phase
        and     #>$fff,a                ; just the phase (m5=$fff wraps it)
        move    x:(r7+$36),x0           ; line 4 base
        add     x0,a
        move    a,r5
        move    y:(r5+n5),a
        move    a,y:(r6)+n6             ; w2: seed the interpolation carry
        move    x:(r7+$09),a            ; -- line 5
        move    x:(r7+$02),x0
        sub     x0,a
        move    a,y:(r6)+
        move    x1,x0
        sub     x0,a
        move    a,n5
        move    x:(r7+$03),a
        move    a,y:(r6)+
        move    r1,a
        and     #>$fff,a
        move    x:(r7+$37),x0           ; line 5 base
        add     x0,a
        move    a,r5
        move    y:(r5+n5),a
        move    a,y:(r6)+n6
        move    x:(r7+$0a),a            ; -- line 6
        move    x:(r7+$04),x0
        sub     x0,a
        move    a,y:(r6)+
        move    x1,x0
        sub     x0,a
        move    a,n5
        move    x:(r7+$05),a
        move    a,y:(r6)+
        move    r1,a
        and     #>$fff,a
        move    x:(r7+$4c),x0           ; line 6 base
        add     x0,a
        move    a,r5
        move    y:(r5+n5),a
        move    a,y:(r6)+n6
        move    x:(r7+$4b),a            ; -- line 7
        move    x:(r7+$06),x0
        sub     x0,a
        move    a,y:(r6)+
        move    x1,x0
        sub     x0,a
        move    a,n5
        move    x:(r7+$07),a
        move    a,y:(r6)+
        move    r1,a
        and     #>$fff,a
        move    x:(r7+$4d),x0           ; line 7 base
        add     x0,a
        move    a,r5
        move    y:(r5+n5),a
        move    a,y:(r6)+n6
; n1 now carries the LINE STRIDE, not a read offset: the rolled loop steps its
; single read pointer from one line to the next by adding 0x1000, and the eight
; lines are 0x1000 apart by construction (base is the literal 0x4000 and every
; line is 4096-aligned, which is what modulo addressing requires anyway).
        move    #>$1000,a
        move    a,n1

; ---- prime the IN-LOOP ALLPASS interpolation carries ---------------------
; The same seeding the four tank lines get above, for the same reason, and
; the allpasses (v90) never had it.
;
; The carried d1 is only "last sample's d0" while the READ OFFSET holds
; still. Inside a block it does: r5 walks one per sample and n5 is fixed.
; Across a block boundary the AP offsets ($52/$54) step with their LFO, and
; then the carry is off by one -- it is d0 or d2, not d1. On a DOWNWARD step
; the fraction is near 1.0, so the interpolator outputs that wrong neighbour
; almost in full: a one-sample error at tail amplitude, fed straight back
; into the loop by the allpass it sits in. Once per block per allpass, at
; the LFO's integer-crossing rate.
;
; Priming costs ~26 instructions per BLOCK -- under 2 cycles/sample
; amortised, against the ~551 spare -- and needs no extra N register, which
; is what the in-loop comment ("no other way to do this") ruled out. That
; was true per SAMPLE; it is not true once per block.
        move    x:(r7+$60),a            ; allpass A: (512 - tap) - offset - 1
        move    x:(r7+$52),x0
        sub     x0,a
        move    #>$1,x0
        sub     x0,a
        move    a,n5
        move    #>$1ff,m5               ; v127: the in-loop allpasses are 512
        move    r1,a                    ; the AP phase IS the tank phase
        and     #>$1ff,a                ; (same derivation as $39 in the loop)
        move    x:(r7+$5e),x0           ; base A
        add     x0,a
        move    a,r5
        move    x:(r7+$61),b            ; spaces the r5 write, and preloads
        move    y:(r5+n5),a             ; d1 for the block's first sample
        move    a,x:(r7+$5c)
        move    x:(r7+$54),x0           ; allpass B: b still holds (512 - tap)
        move    b,a
        sub     x0,a
        move    #>$1,x0
        sub     x0,a
        move    a,n5
        move    r1,a
        and     #>$1ff,a
        move    x:(r7+$5f),x0           ; base B
        add     x0,a
        move    a,r5
        move    x:(r7+$5c),b            ; spaces the r5 write
        move    y:(r5+n5),a
        move    a,x:(r7+$5d)
        move    #>$7ff,m5               ; v100: back to the diffusers' 2048

        do      n7,>rvend

; ---- input: mono sum, plus the shared REVERB bus accumulator (BUS.md) ----
        move    #>$1,n0
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$1b)
        move    a,x:(r7+$6a)            ; own dry mono, stashed BEFORE the bus
                                        ; is folded in below -- the ->DELAY
                                        ; send (BUS.md task 10) taps dry alone
        move    x:(r7+$63),a            ; this sample's ACC read address
        move    a,r5                    ; borrow r5: free here, every use
                                        ; below recomputes it from scratch
        move    y:(r5),b                ; last block's fully-summed sends
        move    b1,x1                   ; auto-gain: divide by the number of
        move    x:(r7+$0c),y1           ; clients that wrote it, so eight tracks
        mpy     x1,y1,b                 ; drive the tank exactly as hard as one
        asl     #$3,b,b                 ; undo the 3 bits of headroom the clients
                                        ; write with (dsp/send_client.asm): the
                                        ; scaled sum is sum/8, so sum/8 * 1/N * 8
                                        ; = sum/N, and the intermediate never
                                        ; leaves range -- with N clients writing,
                                        ; the scaled sum is at most N/8.
        move    x:(r7+$1b),a
        add     b,a
        move    a,x:(r7+$1b)            ; own dry + scaled bus, feeding the tank
        move    x:(r7+$63),a
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$63)            ; advance the read pointer one sample

; ---- ->DELAY: dry parallel send into the shared DELAY bus (BUS.md task 10)
        move    x:(r7+$6a),x0           ; own dry mono, this sample
        move    x:(r7+$69),y1           ; ->DELAY level
        mpy     x0,y1,a
        move    x:(r7+$68),b            ; this call's DELAY ACC write address
        move    b,r5
        move    y:(r5),b
        add     b,a
        move    a,y:(r5)                ; DELAY ACC[write][i] += contribution
        move    x:(r7+$68),a
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$68)            ; advance DELAY ACC write pointer

        move    r1,a                    ; the allpass phase IS the tank phase:
        and     #>$7ff,a                ; both advance by 1 a sample, and the
                                        ; line base is aligned, so r1 masked is
                                        ; it. $7ff ON PURPOSE, not the lines'
                                        ; $fff: the diffusers and in-loop APs
                                        ; are 2048/512-word SHARED buffers, so
                                        ; this truncates the 0..4095 tank phase
                                        ; to their own wrap. Masking $fff here
                                        ; would walk r5 into the neighbouring
                                        ; buffer for half of every lap.
                                        ; Immediate, not n6: n6 now carries
                                        ; the pre-delay offset.
        move    a,x:(r7+$39)

; ---- pre-delay ----------------------------------------------------------
; r5 with m5 modulo and a plain post-increment -- the same shape as the tank
; lines, which are proven safe. The earlier version computed the addresses
; arithmetically like the diffuser does, which cost 28 instructions a sample;
; that is only necessary when r5 and n5 are RECOMPUTED inside the loop, and
; here they are set once per block.
;
; RESTORED in v58. It was dropped in v50 to test the modulo theory of the
; two-track freeze; that theory was wrong -- the freeze was the $83 phase
; load saturating the AGU (v55). Nothing about modulo addressing was ever
; implicated, and v50 froze without any M register non-linear.
;
; Split-safe like everything else: $30 is re-derived from $83 + the
; pre-delay base once per CALL (in the PRE setup, A2-cleaned there), and
; the running pointer is saved back per sample, so the two sub-blocks of a
; split block continue each other exactly.
        move    x:(r7+$30),r6           ; r6, not r5: the allpasses own r5 now
        move    x:(r7+$1b),a            ; input, and fills the AGU slot
        move    #>$1,n0
        move    x:(r7+$62),n6           ; pre-delay offset back
                                        ; below borrow n6 every sample)
        move    y:(r6+n6),b             ; delayed
        move    a,y:(r6)+               ; write, and advance
        move    r6,x:(r7+$30)
        move    b,x:(r7+$1b)            ; delayed input -> the diffuser

; ---- EARLY REFLECTIONS: REMOVED (9 Aug 2026) ------------------------------
; Six discrete taps summed onto the output IS a flutter echo by construction
; -- the comb notches are 47-222 Hz apart, sparse enough to be heard as pitch.
; Fixing it needs 20+ taps, which needs program space payload A does not have.
; The input diffuser, shortened to Dattorro-scale (4-13 ms), now fills the
; role these taps were meant to: dense early buildup from allpass diffusion
; rather than discrete echoes. ER=0 for all four modes is the clean setting.
; See VOICING.md Round 7 for the measurements that settled this.

; -- allpass 0: base+0x4000, tap 1994 (45.2 ms) --
; v70: modulo. n5 = 2048-tap, m5 = $7ff, r5 = base + phase. The AGU then
; does the wrap and the base add for free: y:(r5+n5) is the tap read and
; y:(r5) is the write, so the second address build disappears entirely.
        move    x:(r7+$7e),n5        ; this MODE's allpass 0
        move    x:(r7+$39),a            ; phase   (also spaces the n5 write)
        move    x:(r7+$32),x0            ; base
        add     x0,a
        move    a,r5                    ; = write address
        move    x:(r7+$6d),y0           ; g, from DIFFUSION (was the fixed
                                        ; literal 0.703). Loaded once and held
                                        ; across all four input allpasses.
        move    x:(r7+$1b),x1           ; input, and spaces the r5 write
        move    y:(r5+n5),b             ; d, at (phase - tap) mod 2048
        move    b,x0
        mpy     x0,y0,a
        move    x1,x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$1c)
        move    a,x1
        mpy     x1,y0,a
        sub     a,b                     ; out = d - g*v
        move    b,x:(r7+$1b)
        move    x:(r7+$1c),a
        move    a,y:(r5)                ; write v at base + phase

; -- allpass 1: base+0x4800, tap 1706 (38.7 ms) --
; v70: modulo. n5 = 2048-tap, m5 = $7ff, r5 = base + phase. The AGU then
; does the wrap and the base add for free: y:(r5+n5) is the tap read and
; y:(r5) is the write, so the second address build disappears entirely.
        move    x:(r7+$7f),n5        ; this MODE's allpass 1
        move    x:(r7+$39),a            ; phase   (also spaces the n5 write)
        move    x:(r7+$33),x0            ; base
        add     x0,a
        move    a,r5                    ; = write address
        move    x:(r7+$1b),x1           ; input, and spaces the r5 write
        move    y:(r5+n5),b             ; d, at (phase - tap) mod 2048
        move    b,x0
        mpy     x0,y0,a
        move    x1,x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$1c)
        move    a,x1
        mpy     x1,y0,a
        sub     a,b                     ; out = d - g*v
        move    b,x:(r7+$1b)
        move    x:(r7+$1c),a
        move    a,y:(r5)                ; write v at base + phase

; -- allpass 2: base+0x5000, tap 1438 (32.6 ms) --
; v70: modulo. n5 = 2048-tap, m5 = $7ff, r5 = base + phase. The AGU then
; does the wrap and the base add for free: y:(r5+n5) is the tap read and
; y:(r5) is the write, so the second address build disappears entirely.
        move    x:(r7+$80),n5        ; this MODE's allpass 2
        move    x:(r7+$39),a            ; phase   (also spaces the n5 write)
        move    x:(r7+$34),x0            ; base
        add     x0,a
        move    a,r5                    ; = write address
        move    x:(r7+$1b),x1           ; input, and spaces the r5 write
        move    y:(r5+n5),b             ; d, at (phase - tap) mod 2048
        move    b,x0
        mpy     x0,y0,a
        move    x1,x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$1c)
        move    a,x1
        mpy     x1,y0,a
        sub     a,b                     ; out = d - g*v
        move    b,x:(r7+$1b)
        move    x:(r7+$1c),a
        move    a,y:(r5)                ; write v at base + phase

; -- allpass 3: base+0x5800, tap 1226 (27.8 ms) --
; v70: modulo. n5 = 2048-tap, m5 = $7ff, r5 = base + phase. The AGU then
; does the wrap and the base add for free: y:(r5+n5) is the tap read and
; y:(r5) is the write, so the second address build disappears entirely.
        move    x:(r7+$81),n5        ; this MODE's allpass 3
        move    x:(r7+$39),a            ; phase   (also spaces the n5 write)
        move    x:(r7+$35),x0            ; base
        add     x0,a
        move    a,r5                    ; = write address
        move    x:(r7+$1b),x1           ; input, and spaces the r5 write
        move    y:(r5+n5),b             ; d, at (phase - tap) mod 2048
        move    b,x0
        mpy     x0,y0,a
        move    x1,x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$1c)
        move    a,x1
        mpy     x1,y0,a
        sub     a,b                     ; out = d - g*v
        move    b,x:(r7+$1b)
        move    x:(r7+$1c),a
        move    a,y:(r5)                ; write v at base + phase

        move    x:(r7+$1b),a
; ---- TANK INPUT ATTENUATION: -12 dB of headroom -------------------------
; The tank runs at a loop gain approaching 1, so energy circulating in it
; reaches Q1.23 saturation long before the OUTPUT does -- measured: on a
; dense source at TIME=110, 6 dB less input gave only 2.3 dB less output,
; and on bass it clipped 26,741 samples. Confirmed audible in a
; loudness-matched A/B, and -12 dB is the figure that was chosen by ear.
;
; The matching makeup gain is FREE: the output sum below used to divide the
; four-line sum by 4, and it no longer does. Attenuating by 4 here and
; dropping that /4 there leaves the output level and the shared WET bus
; EXACTLY where they were, with the whole 12 dB spent on headroom inside the
; loop. It also removes a reliance on A2 during the output sum, which used
; to run up to 4x full scale before being shifted back down.
;
; Deliberately NOT tied to TIME. The compression was measured at FIXED TIME
; while varying input, so it is about absolute level in a high-gain loop.
; (1-g) scaling -- the textbook answer -- was tried and over-corrected by
; 30 dB, because 1/(1-g) is a steady-state result and music never gets
; there. See REVERB.md.
        asr     #$2,a,a                 ; -12 dB
        move    a,x:(r7+$15)            ; diffused input -> tank
; ---- STAGE 3b: coefficients held in registers across all four lines -----
; y0 = DAMP and x1 = the LO coefficient. Neither is clobbered between here
; and the write-back: the line reads use y1, the damping uses y0, the LO
; uses x1. Both were being re-fetched once per line. The allpasses above do
; use y0 and x1, which is why this sits after them.
        move    x:(r7+$1f),y0           ; DAMP, for all four lines
        move    x:(r7+$40),x1           ; LO coefficient, for all four lines
        asr     #$1,a,a
        move    a,x:(r7+$27)            ; and at half, for the other three lines

; ---- the tank's four taps, damped and low-cut inside the feedback path ---
; ROLLED. This was 4 x 25 instructions of identical arithmetic differing only
; in which r7 slots it touched -- 265 words doing 66 words' work, and the
; shape that makes an eight-line tank cost twice as much code as a four-line
; one. Rolled, the line count is a loop bound: DATA, not code.
;
; Two registers carry the loop:
;   r6  walks the per-line state table, six words a line (see the layout at
;       the top of this file). Every word is touched exactly once for read and
;       once for write, so a plain post-increment walk covers the line.
;   r5  is the read pointer, starting at r1 -- line 0's base plus the phase --
;       and stepping 0x1000 a line. m5 = $fff so the AGU wraps the indexed
;       read inside whichever 4096-word line r5 currently sits in, which is
;       exactly what m1..m4 were doing per line before.
;
; PAIRING RULE, unchanged and now structural: each line's interpolation
; fraction MUST come from the same LFO as the integer offset it was built
; from ($23/$24, $21/$22, $56/$57, $58/$59). Lines 0 and 2 once had B's and
; C's fractions swapped, which put a 1-sample sawtooth on their delay at the
; foreign LFO's wrap rate -- the loudest artifact ever measured in this
; engine. The two halves are now written into ADJACENT words of one line's
; state (w0 and w1) by one block of setup code, so they cannot drift apart
; again. The four LFO PHASES are deliberately crosswise (REVERB.md); the two
; halves of one offset are not.
;
; y is parked in y1 rather than round-tripped through memory the way $16..$19
; used to be. That is bit-identical, not merely equivalent: a move from a
; 56-bit accumulator to any 24-bit destination -- register or memory -- goes
; through the same limiter, and reloading either one back into A sets A1 and
; sign-extends A2 identically. The fraction in y1 is dead by then.
        move    #>$fff,m5               ; r5 walks a 4096-word LINE now
        move    x:(r7+$0b),a            ; the per-line state table
        move    a,r6
        move    r1,x0                   ; line 0: base + phase, the same
        move    x0,r5                   ; pointer r1 has always been
        do      #8,>tankend
        move    y:(r6)+,n5              ; w0: this line's read offset
        move    y:(r6)+,y1              ; w1: its interpolation fraction
        move    n1,x0                   ; the line stride, 0x1000
        move    y:(r5+n5),b             ; d0 -- the AGU wraps inside the line
        move    r5,a
        add     x0,a
        move    a,r5                    ; on to the next line
; The interpolation partner needs no second address: the read pointer advances
; one per sample, so d1 THIS sample is d0 LAST sample. The write head stays
; >=55 samples away even at the longest tap and deepest modulation, so the
; carried value is never overwritten. Seeded one sample further back before
; the loop, so sample 0 is exact too.
        move    y:(r6),a                ; w2: d1 = last sample's d0
        move    b,y:(r6)+               ; carry forward
        sub     b,a                     ; d1 - d0
        move    a,x0
        mpy     x0,y1,a                 ; f*(d1-d0)
        add     b,a                     ; + d0 -> the interpolated tap
        move    y:(r6),b                ; w3: damping state
        sub     b,a
        move    a,x0
        mpy     x0,y0,a                 ; y0 = DAMP, held across every line
        add     b,a
        move    a,y:(r6)+               ; damping state back
    ; -- LO: one-pole high-pass on the damped tap, still inside the loop --
        move    a,y1                    ; park y, the damped tap
        move    y:(r6),b                ; w4: LO state
        sub     b,a                     ; y - lo
        move    a,x0
        mpy     x0,x1,a                 ; x1 = the LO coefficient
        add     b,a                     ; lo += cl*(y - lo)
        move    a,y:(r6)+               ; LO state back
        move    a,x0                    ; the low-passed part
        move    y1,a                    ; y again
        sub     x0,a                    ; y - lo, the low cut
        move    a,y:(r6)+               ; w5: this line's output
tankend:

; ---- collect the LINES outputs to r7 slots for the Hadamard ---------------
; The loop leaves them in the state table at stride 6. Lines 0-3 go to
; $16..$19, lines 4-7 to $3a..$3d -- the two 4-word groups the 8x8 FWHT
; operates on in-place.
        move    #>$6,n6                 ; the table's stride
        move    x:(r7+$0b),a
        move    #>$5,x0
        add     x0,a
        move    a,r6                    ; -> line 0's output word
        move    #>$7ff,m5               ; back to the input diffusers' 2048
        nop                             ; two instructions between writing r6
                                        ; and addressing through it
        move    y:(r6)+n6,a
        move    a,x:(r7+$16)            ; line 0
        move    y:(r6)+n6,a
        move    a,x:(r7+$17)            ; line 1
        move    y:(r6)+n6,a
        move    a,x:(r7+$18)            ; line 2
        move    y:(r6)+n6,a
        move    a,x:(r7+$19)            ; line 3
        move    y:(r6)+n6,a
        move    a,x:(r7+$3a)            ; line 4
        move    y:(r6)+n6,a
        move    a,x:(r7+$3b)            ; line 5
        move    y:(r6)+n6,a
        move    a,x:(r7+$3c)            ; line 6
        move    y:(r6)+n6,a
        move    a,x:(r7+$3d)            ; line 7

; ---- wet output: eight lines summed per channel -------------------------
; THIS MUST RUN BEFORE THE FWHT, and that placement is the whole fix.
;
; The transform below rewrites $16..$19/$3a..$3d IN PLACE. This block reads
; those same slots, so downstream of the transform it was summing Hadamard
; OUTPUTS, not line outputs -- and the two sign patterns here are exactly
; rows 1 and 2 of the Sylvester H8. A Hadamard row applied to a Hadamard
; transform collapses it: p'(H8 d) = 8*d_k. So L was 8*d1 and R was 8*d2 --
; ONE delay line per channel at 8x gain, with none of the eight-line
; averaging this block exists to do, and ~9 dB of stray level that made the
; engine read as hotter than the four-line it was supposed to match.
;
; The output never needed the mixing matrix; only the feedback does. Run the
; sums first, on the raw line outputs the collect step just deposited, and
; the transform is free to overwrite the slots afterwards. Pure reordering:
; no new instructions.
;
; Register lifetimes checked: ER ($5a/$5b) is final well before the collect;
; y0 is dead here (the tank's DAMP is finished with, and the write-back
; reloads y0 with g/2 itself); a, b and x0 are all free before the FWHT.
; y1 is NOT touched here -- the MIX wet gain is still loaded after the
; write-back, which clobbers y1.
;   L = (l0-l1+l2-l3) + (l4-l5+l6-l7) + ER_L
;   R = (l0+l1-l2-l3) + (l4+l5-l6-l7) + ER_R
        move    x:(r7+$16),a            ; line 0
        move    x:(r7+$17),x0           ; line 1
        sub     x0,a
        move    x:(r7+$18),x0           ; line 2
        add     x0,a
        move    x:(r7+$19),x0           ; line 3
        sub     x0,a                    ; a = l0-l1+l2-l3
        move    x:(r7+$3a),x0           ; line 4
        add     x0,a
        move    x:(r7+$3b),x0           ; line 5
        sub     x0,a
        move    x:(r7+$3c),x0           ; line 6
        add     x0,a
        move    x:(r7+$3d),x0           ; line 7
        sub     x0,a                    ; a = (l0-l1+l2-l3)+(l4-l5+l6-l7)
        move    a,x:(r7+$2d)            ; wet L
        move    x:(r7+$16),a
        move    x:(r7+$17),x0
        add     x0,a
        move    x:(r7+$18),x0
        sub     x0,a
        move    x:(r7+$19),x0
        sub     x0,a                    ; a = l0+l1-l2-l3
        move    x:(r7+$3a),x0           ; line 4
        add     x0,a
        move    x:(r7+$3b),x0           ; line 5
        add     x0,a
        move    x:(r7+$3c),x0           ; line 6
        sub     x0,a
        move    x:(r7+$3d),x0           ; line 7
        sub     x0,a                    ; a = (l0+l1-l2-l3)+(l4+l5-l6-l7)
        move    a,x:(r7+$2e)            ; wet R

; ---- 8x8 Fast Walsh-Hadamard Transform -----------------------------------
; Three stages of 4 butterflies each. Inputs/outputs are in-place across
; two 4-word groups: $16..$19 (u0..u3) and $3a..$3d (u4..u7).
;
; Stage 1 (step=1): within each group — (0,1)(2,3) and (4,5)(6,7)
; Stage 2 (step=2): within each group — (0,2)(1,3) and (4,6)(5,7)
; Stage 3 (step=4): cross-group     — (0,4)(1,5)(2,6)(3,7)
;
; r6 is free here; y1 is free (last used in the damping mpy, next used in
; the write-back). m6 is forced linear and restored to the pre-delay's
; modulo-4096 after the transform: the pre-delay runs earlier in the loop
; so the restore keeps the NEXT iteration correct.
;
; NOTE `move a,b`, not `tfr a,b`: this assembler silently encodes `tfr a,b`
; as `rnd b`, and the FDN matrix quietly stops being orthogonal.

        move    #>$ffffff,m6            ; linear for the walk

; -- Stage 1: step=1, within each 4-word group --
        lua     (r7+$16),r6
        move    x:(r6)+,a               ; d0
        move    x:(r6)+,x0              ; d1
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r6-2)              ; u0 = d0+d1
        move    b,x:(r6-1)              ; u1 = d0-d1
        move    x:(r6)+,a               ; d2
        move    x:(r6)+,x0              ; d3
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r6-2)              ; u2 = d2+d3
        move    b,x:(r6-1)              ; u3 = d2-d3

        lua     (r7+$3a),r6
        move    x:(r6)+,a               ; d4
        move    x:(r6)+,x0              ; d5
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r6-2)              ; u4 = d4+d5
        move    b,x:(r6-1)              ; u5 = d4-d5
        move    x:(r6)+,a               ; d6
        move    x:(r6)+,x0              ; d7
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r6-2)              ; u6 = d6+d7
        move    b,x:(r6-1)              ; u7 = d6-d7

; -- Stage 2: step=2, within each group --
        move    x:(r7+$16),a            ; u0
        move    x:(r7+$18),x0           ; u2
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$16)            ; u0' = u0+u2
        move    b,x:(r7+$18)            ; u2' = u0-u2
        move    x:(r7+$17),a            ; u1
        move    x:(r7+$19),x0           ; u3
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$17)            ; u1' = u1+u3
        move    b,x:(r7+$19)            ; u3' = u1-u3

        move    x:(r7+$3a),a            ; u4
        move    x:(r7+$3c),x0           ; u6
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$3a)            ; u4' = u4+u6
        move    b,x:(r7+$3c)            ; u6' = u4-u6
        move    x:(r7+$3b),a            ; u5
        move    x:(r7+$3d),x0           ; u7
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$3b)            ; u5' = u5+u7
        move    b,x:(r7+$3d)            ; u7' = u5-u7

; -- Stage 3: step=4, cross-group --
        move    x:(r7+$16),a            ; u0
        move    x:(r7+$3a),x0           ; u4
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$16)            ; u0' = u0+u4
        move    b,x:(r7+$3a)            ; u4' = u0-u4
        move    x:(r7+$17),a            ; u1
        move    x:(r7+$3b),x0           ; u5
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$17)            ; u1' = u1+u5
        move    b,x:(r7+$3b)            ; u5' = u1-u5
        move    x:(r7+$18),a            ; u2
        move    x:(r7+$3c),x0           ; u6
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$18)            ; u2' = u2+u6
        move    b,x:(r7+$3c)            ; u6' = u2-u6
        move    x:(r7+$19),a            ; u3
        move    x:(r7+$3d),x0           ; u7
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$19)            ; u3' = u3+u7
        move    b,x:(r7+$3d)            ; u7' = u3-u7

        move    #>$fff,m6               ; back to the pre-delay's modulo-4096

; SHIMMER_BEGIN -- excised unless SHIMMER=1 (build_bus.py)
; ---- SHIMMER v3: +12 octave up, half-traverse windows (2026-08-09) -------
; WHAT WAS ACTUALLY WRONG, found with an impulse and nothing else. Feed the
; shifter ONE sample and count what comes out:
;
;   v101 / v127 window:  4 events, +18/41/64/87 ms, ALL AT -25 dB
;   this window:         2 events, +18/41 ms,       both at -13 dB
;
; Four equal copies of every transient at 23 ms spacing IS the stutter. Sam,
; 9 Aug, on a same-buffer same-loudness A/B of exactly this one change:
; "B sounded like a single pitch shifted tone where A had the stutter."
;
; WHY FOUR. A slot lives 2N samples (the write pointer advances half a slot a
; sample) and a read head crosses the whole buffer in N, so each head passes
; every slot TWICE before it is overwritten -- 4 passes for 2 heads. The old
; window was a function of the head's ABSOLUTE BUFFER INDEX, so head 1 read
; slot k at the SAME gain on both passes and nothing was ever suppressed.
;
; THE FIX: window on the AGE of the data under the head -- its distance behind
; the write pointer -- and make that window ZERO over half the age range. Each
; head then emits a given slot on one pass and mutes it on the other, so two
; copies come out instead of four. Head 2's age runs exactly 1024 behind head
; 1's, so the halves are complementary and one head is always live: no gap.
;
; TWO COPIES IS THE FLOOR, not a compromise. Doubling pitch in the time domain
; means replaying every piece of material once -- that is what the algorithm
; IS. A phase vocoder would avoid it and does not fit in this budget.
;
; RETRACTED ALONG THE WAY, all measured better on a metric and all inaudible
; or worse to Sam: a longer buffer (1024 vs 2048 "basically the same"), the
; crossfade period (made it much worse -- moved lap energy onto a bare 86 Hz
; drone), and an equal-power crossfade law ("sounds the same"). The 1.83 dB
; midpoint dip a linear crossfade causes is real and is NOT what was audible.
; Only the copy count ever mattered. Measure the impulse response first.
;
; WINDOW SHAPE. g(age) = clamp01( (512 - |age-512|) / 256 ): a trapezoid that
; rises over age 0..256, holds at 1 to 768, falls to zero by 1024, and stays
; zero for the whole upper half. Zero AT age 0 is what puts the splice where
; the head is silent -- age 0 is exactly where the head sits on the write
; pointer's discontinuity. The flat top is what keeps the pair summing to ~1;
; a pure triangle over the half-range would dip to zero twice a lap.
;
; TRAP (CLAUDE.md): `cmp a,b` has silently encoded as `max a,b`, which updates
; only C while bge tests N^V. No cmp here at all -- the two comparisons are
; done as `sub` + branch, which sets N and V properly. Disassembled and
; checked, along with every mpy (x0,y1 / x1,x0 -- never the mpy x0,y0 form
; that assembles as mpysu).
;
; STATE: r7+$0e SHMR (cached per block at the TIME block), r7+$0f phase mod
; 4096, r7+$4e one-pole. The last two free slots in the r7 block.
; BUFFER: base+0x7000, 2048 words, 2048-aligned so the AGU wraps it free.

        move    #>$7ff,m5               ; 2048-word shimmer buffer
        move    x:(r7+$5e),a            ; in-loop allpass A base = shared+0x4000,
        move    #>$3800,x0              ; so the shimmer buffer is 0x3800 BELOW
        sub     x0,a                    ; it, at shared+0x0800 -- which is
        move    a,r5                    ; 2048-ALIGNED, as the AGU wrap requires
                                        ; (m5 = $7ff above). Still derived from
                                        ; $5e because the r7 block has no slot
                                        ; to cache it, and still the only reason
                                        ; the two are placed 0x3800 apart.

        move    x:(r7+$0f),a            ; phase, mod 4096 = 2N. May be GARBAGE
        move    #>$1,x0                 ; on the first call -- the mask cleans
        add     x0,a                    ; it, which is why no init is needed
        move    #>$fff,x0               ; and why every address here is DERIVED
        and     x0,a                    ; from the phase rather than kept as a
        move    a1,x1                   ; walking pointer (AND cleans A1 only;
        move    x1,x:(r7+$0f)           ; x1 is 24-bit so this IS the value)

; ---- one-pole, then the decimated write ---------------------------------
; c = 0.35 -> corner ~2.7 kHz. It sits BEFORE the shift, so it lands ~5.4 kHz
; on the way out, and below the SR/4 the decimation folds about: this is the
; anti-alias filter and the shimmer path's HF rolloff doing one job twice.
        move    x:(r7+$25),a            ; MONO WET SUM ($25 = M from prev sample).
; $25 is (wet_L + wet_R)/2, the raw tank output before WIDTH and MIX. It was
; computed at the end of the previous sample, so it includes every previous
; shimmer contribution that has circulated through the delay lines. Reading it
; here puts the shifted signal back into $15 -- which flows through the tank,
; appears in the next wet sum, and is shifted AGAIN. That IS the cascade.
;
; Cross-core tracks feed the reverb bus accumulator into the tank. They appear
; in $25 the same way local tracks do, so this one-register change also solves
; the cross-core shimmer limitation ($6a was pre-bus, local-only).
;
; $15 flutter note (archived): the diffuser-smear stutter was real, but it was
; specific to reading $15 directly. $25 is post-tank, smoothed by the delay
; line integration -- the echo-train structure is gone by the time the signal
; reaches the wet sum.
        asr     #$2,a,a                 ; -12 dB, matching the attenuation $15
                                        ; already carries, so SHMR's range is
                                        ; unchanged by the move
        move    x:(r7+$4e),b            ; previous filter output
        sub     b,a
        move    a,x0
        move    #>$2ccccd,y1            ; c = 0.35
        mpy     x0,y1,a
        add     b,a                     ; y = y_prev + c*(x - y_prev)
        move    a,x:(r7+$4e)
        move    a,y1                    ; hold the filtered sample

        move    x1,a
        asr     #$1,a,a                 ; write index = phase >> 1, 0..2047 --
        move    a1,y0                   ; advances once per TWO samples, which
        move    a1,n5                   ; IS the decimation. y0 keeps it: every
        move    y1,a                    ; age below is measured against it and
        move    a,y:(r5+n5)             ; nothing past here clobbers y0.

; ---- head 0: pos = phase & $7ff, age = (write - pos) & $7ff -------------
        move    x1,a
        move    #>$7ff,x0
        and     x0,a
        move    a1,n5                   ; n5 = pos0, held across the gain
        move    a1,x0
        move    y0,a                    ; write index
        sub     x0,a                    ; write - pos0, may go negative
        move    #>$7ff,x0
        and     x0,a                    ; age0 (AND of the two's complement low
                                        ; bits IS the correct value mod 2048)
        move    a1,x0                   ; A2-CLEAN. `and` masks A1 and leaves A2
        move    x0,a                    ; alone, and wr-pos is NEGATIVE for most
                                        ; of the lap (wr = p>>1, pos = p & $7ff,
                                        ; so it is -p/2 over the first half), so
                                        ; A2 is $ff here. The `sub #640` below
                                        ; works on the WHOLE accumulator and
                                        ; would see a huge negative number.
                                        ; Reloading through a 24-bit register
                                        ; zero-extends (bit 23 is clear at <2048)
                                        ; and clears A2. Same dance as $39 at the
                                        ; in-loop allpasses, and the same class
                                        ; of fault as the masked $83 load that
                                        ; froze two tracks (reverb55).
        move    #>640,x0
        sub     x0,a
        abs     a
        neg     a
        add     x0,a                    ; t = 640 - |age-640|
        tst     a
        bgt     shp0                    ; t > 0 -> the LIVE half of the age
        clr     a                       ; range. The upper half is silent, and
        bra     shd0                    ; that zero is what turns 4 copies
shp0:                                   ; into 2 -- the whole fix.
        move    #>256,x0
        sub     x0,a                    ; t - 256
        blt     shr0                    ; still climbing the ramp
        move    #>$7fffff,a             ; past it -> full gain. The flat top is
        bra     shd0                    ; what keeps the pair summing to ~1;
shr0:                                   ; a pure triangle would dip to zero
        add     x0,a                    ; twice a lap.
        asl     #$f,a,a                 ; g = t/256 in Q23
shd0:
        move    a1,y1                   ; g0
        move    y:(r5+n5),a             ; tap 0
        move    a1,x0
        mpy     x0,y1,a
        move    a,b                     ; b = head 0's contribution

; ---- head 1: half a buffer on, so its age runs 1024 behind head 0's -----
        move    x1,a
        move    #>1024,x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a                    ; MASKED -- a modulo offset larger than
        move    a1,n5                   ; the buffer is undefined (REVERB.md)
        move    a1,x0
        move    y0,a
        sub     x0,a
        move    #>$7ff,x0
        and     x0,a                    ; age1
        move    a1,x0                   ; A2-CLEAN, exactly as head 0 above
        move    x0,a
        move    #>640,x0
        sub     x0,a
        abs     a
        neg     a
        add     x0,a
        tst     a
        bgt     shp1                    ; t > 0 -> the LIVE half of the age
        clr     a                       ; range. The upper half is silent, and
        bra     shd1                    ; that zero is what turns 4 copies
shp1:                                   ; into 2 -- the whole fix.
        move    #>256,x0
        sub     x0,a                    ; t - 256
        blt     shr1                    ; still climbing the ramp
        move    #>$7fffff,a             ; past it -> full gain. The flat top is
        bra     shd1                    ; what keeps the pair summing to ~1;
shr1:                                   ; a pure triangle would dip to zero
        add     x0,a                    ; twice a lap.
        asl     #$f,a,a                 ; g = t/256 in Q23
shd1:
        move    a1,y1                   ; g1
        move    y:(r5+n5),a             ; tap 1
        move    a1,x0
        mpy     x0,y1,a
        add     b,a                     ; the octave-up signal, g0+g1 ~= 1

; ---- back into the tank input -------------------------------------------
; At SHMR = 0 this multiply is exactly zero and the block is silent, which is
; the "it must be able to reach zero and actually turn off" constraint. The
; knob still has to be proved to PUBLISH on hardware (dsp_host pokes r6, so
; every slot looks live here) -- PLAN.md step 2's BURN=1 trip.
        move    a1,x1
        move    x:(r7+$0e),x0           ; SHMR, cached per block by the TIME
        mpy     x1,x0,a                 ; block -- NOT read in the sample loop,
        move    x:(r7+$15),x0           ; where r6 is the pre-delay pointer
        add     x0,a
        move    a,x:(r7+$15)            ; tank input, with the octave folded in

        move    #>$7ff,m5               ; the input diffusers' modulo, unchanged
; SHIMMER_END

; ---- feedback and write back (ROLLED, 8-line) ----------------------------
; The 8x8 Hadamard leaves u0..u7 in r7+$16..$19 (group A) and $3a..$3d
; (group B). Table B at r7+$0d: 2 words per line — +0 input_weight (sign
; * scale, combined), +1 per-line decay gain stored_k (PLAN.md 1.1; this
; word was the dead has_allpass flag until 9 Aug 2026).
;
; Step 1: compute fb[k] = u[k]*G_k + input*weight[k] for all 8 lines,
;         G_k the per-line decay gain primed after the TIME block.
;         fb[0..3] → scratch $1a..$1d, fb[4..7] → scratch $41..$44.
; Step 2: allpass A processes fb[0], writes to r1 (line 0).
; Step 3: allpass B processes fb[1], writes to r2 (line 1).
; Step 4: write fb[2..7] to lines 2-7 via a rolled loop.

        move    x:(r7+$0d),a            ; table B base
        move    a,r6                    ; (the global $1e load into y0 that
                                        ; lived here is GONE: each line's gain
                                        ; now arrives from table B inside the
                                        ; loops, one word later in the same
                                        ; read that used to be discarded)

; -- Step 1a: rolled feedback, group A (u[0..3] at $16..$19) --------------
; r4 walks u[0..3] (post-increment), r5 walks scratch[0..3] ($1a..$1d).
; r6 already walks table B (weight + gain, 2 words per line). Input reloaded
; from $15 each iteration because mpy x0,y1,b overwrites b.
        move    r7,a
        move    #>$16,x0
        add     x0,a
        move    a,r4                    ; r4 -> u0
        move    r7,a
        move    #>$1a,x0
        add     x0,a
        move    a,r5                    ; r5 -> scratch0
        move    x:(r7+$15),b            ; input, also spaces the r5 write
        nop
        do      #4,>fbA
        move    y:(r6)+,x0             ; weight[k]
        move    x:(r7+$15),b           ; input (fresh each iteration)
        move    b,y1
        mpy     x0,y1,b                ; input * weight[k]
        move    x:(r4)+,a              ; u[k]
        move    a,x0
        move    y:(r6)+,y0             ; gain[k]: the read that used to be
                                       ; discarded is the live per-line gain.
                                       ; ALWAYS POSITIVE (>= min($1e, 1/√8)),
                                       ; so mpy-as-mpysu is harmless here
        mpy     x0,y0,a                ; u[k] * G_k  (a PLAIN product -- the
                                       ; multiplies here do NOT double; see
                                       ; the priming block's accounting)
        add     b,a                    ; fb = u*G_k + input*weight
        move    a,x:(r5)+              ; store fb[k] to scratch
        nop                            ; one instruction between r5 write and use
fbA:

; -- Step 1b: rolled feedback, group B (u[4..7] at $3a..$3d) --------------
; r4 walks u[4..7], r5 walks scratch[4..7] ($41..$44).
        move    r7,a
        move    #>$3a,x0
        add     x0,a
        move    a,r4                    ; r4 -> u4
        move    r7,a
        move    #>$41,x0
        add     x0,a
        move    a,r5                    ; r5 -> scratch4
        move    x:(r7+$15),b            ; input, also spaces the r5 write
        nop
        do      #4,>fbB
        move    y:(r6)+,x0             ; weight[k]
        move    x:(r7+$15),b           ; input (fresh each iteration)
        move    b,y1
        mpy     x0,y1,b                ; input * weight[k]
        move    x:(r4)+,a              ; u[k]
        move    a,x0
        move    y:(r6)+,y0             ; gain[k], as in fbA
        mpy     x0,y0,a                ; u[k] * G_k
        add     b,a                    ; fb = u*G_k + input*weight
        move    a,x:(r5)+              ; store fb[k] to scratch
        nop
fbB:

; -- Step 2: in-loop allpass, line 0: diffuses the feedback before storage --
        move    #>$1ff,m5               ; these two are 512. The input
                                        ; diffusers share m5, so it is switched
                                        ; here and put back after line 1.
        move    x:(r7+$1a),a            ; fb0 from scratch
        move    a,x1                    ; x = the value bound for the line
        move    x:(r7+$60),a
        move    x:(r7+$52),x0           ; LFO integer offset -- the allpass is
        sub     x0,a                    ; MODULATED now, not static
        move    a,n5                    ; (512 - tap) - offset
        move    x:(r7+$39),a            ; phase (masked to $7ff above)
        and     #>$1ff,a                ; ...but these buffers are 512. A2 is
                                        ; already 0 (the phase loads positive),
                                        ; so no A2-clean dance is needed here.
        move    x:(r7+$5e),x0
        add     x0,a
        move    a,r5                    ; = write address
        move    x:(r7+$6d),y1           ; g -- y1 by convention (y0 carried the
        move    x:(r7+$15),x0           ; global gain before PLAN.md 1.1; it is
                                        ; per-line now and y0 is free here)
        move    y:(r5+n5),b             ; d0
; Interpolate against the PREVIOUS sample's d0.
        move    x:(r7+$5c),a            ; d1 = last sample's d0
        move    b,x:(r7+$5c)            ; carry forward
        sub     b,a                     ; d1 - d0
        move    a,x0
        move    x:(r7+$53),y1           ; fraction (g is reloaded below)
        mpy     x0,y1,a                 ; f*(d1-d0)
        add     b,a                     ; + d0 -> interpolated tap
        move    a,b
        move    x:(r7+$6d),y1           ; g back
        move    b,x0
        mpy     x0,y1,a
        move    x1,x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$14)
        move    a,x0
        mpy     x0,y1,a
        sub     a,b                     ; out = d - g*v
        move    x:(r7+$14),a
        move    a,y:(r5)                ; store v
        move    b,a                     ; out -> the line
        move    a,y:(r1)             ; write at the line's own modulo pointer

; -- Step 3: in-loop allpass, line 1 --
        move    x:(r7+$1b),a            ; fb1 from scratch
        move    a,x1                    ; x = the value bound for the line
        move    x:(r7+$61),a
        move    x:(r7+$54),x0           ; LFO integer offset -- the allpass is
        sub     x0,a                    ; MODULATED now, not static
        move    a,n5                    ; (512 - tap) - offset
        move    x:(r7+$39),a            ; phase (masked to $7ff above)
        and     #>$1ff,a                ; ...but these buffers are 512
        move    x:(r7+$5f),x0
        add     x0,a
        move    a,r5                    ; = write address
        move    x:(r7+$6d),y1           ; g -- y1, NOT y0
        move    x:(r7+$15),x0
        move    y:(r5+n5),b             ; d0
        move    x:(r7+$5d),a            ; d1 = last sample's d0
        move    b,x:(r7+$5d)            ; carry forward
        sub     b,a                     ; d1 - d0
        move    a,x0
        move    x:(r7+$55),y1           ; fraction (g is reloaded below)
        mpy     x0,y1,a                 ; f*(d1-d0)
        add     b,a                     ; + d0 -> interpolated tap
        move    a,b
        move    x:(r7+$6d),y1           ; g back
        move    b,x0
        mpy     x0,y1,a
        move    x1,x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$14)
        move    a,x0
        mpy     x0,y1,a
        sub     a,b                     ; out = d - g*v
        move    x:(r7+$14),a
        move    a,y:(r5)                ; store v
        move    #>$7ff,m5               ; back to the input diffusers' 2048
        move    b,a                     ; out -> the line
        move    a,y:(r2)             ; write at the line's own modulo pointer

; -- Step 4: write fb[2..7] to lines 2-7 via r5-indexed loop --------------
; Lines 2-3 from scratch $1c/$1d, lines 4-7 from scratch $41..$44.
; r5 walks the line write positions (base[k] + phase), advancing by stride.
;
; THE ADDRESS LIVES IN b, NOT a, AND THAT IS THE WHOLE POINT. The first
; version advanced the pointer in a -- `move r5,a / add x0,a / move a,r5` --
; which is correct exactly once, for the line 2 -> 3 step. From line 3 on,
; `a` had already been reloaded with the fb value to be stored, so `add x0,a`
; computed **fb + 0x800** and every write from line 4 onward went to an
; address made out of AUDIO DATA.
;
; Lines 4-7 were therefore never written. They were still READ, every sample,
; so the tank circulated their frozen click-era contents forever: a tail that
; sat flat within 0.5 dB from second 1 to second 12, broadband, indifferent to
; TIME, SIZE, MOD and DIFF, and periodic at exactly 2048 samples -- one full
; line -- because a buffer that is read but never written replays itself. It
; survived replacing the FWHT with the identity matrix and survived collapsing
; the decay gain to 0.15, which is what proved it was not the FDN at all.
; Confirmed by dumping Y memory: 0 of 96 words of line 4 changed between an
; 11.0 s and an 11.5 s render, against 96 of 96 for line 0.
;
; The stray writes also scattered single large values across the whole
; allocation, which is what the sparse spikes in those buffers were.
;
; b is dead here (Step 3 finished with it) and nothing below reloads it, so
; carrying the address there costs NOTHING: same instruction count, same
; one-instruction spacing between `move b,r5` and the access through r5.
        move    r3,x0
        move    x0,r5                   ; start at line 2's pointer
        move    n1,x0                   ; line stride, hoisted
        move    r5,b                    ; b carries the ADDRESS from here down
        move    x:(r7+$1c),a            ; fb2
        move    a,y:(r5)                ; write to line 2
        add     x0,b
        move    b,r5                    ; -> line 3
        move    x:(r7+$1d),a            ; fb3
        move    a,y:(r5)                ; write to line 3
        add     x0,b
        move    b,r5                    ; -> line 4
        move    x:(r7+$41),a            ; fb4
        move    a,y:(r5)
        add     x0,b
        move    b,r5                    ; -> line 5
        move    x:(r7+$42),a            ; fb5
        move    a,y:(r5)
        add     x0,b
        move    b,r5                    ; -> line 6
        move    x:(r7+$43),a            ; fb6
        move    a,y:(r5)
        add     x0,b
        move    b,r5                    ; -> line 7
        move    x:(r7+$44),a            ; fb7
        move    a,y:(r5)             ; write to line 7

; ---- wet gain for the MIX below ----------------------------------------
; Loaded HERE, not with the sums above: the write-back clobbers y1, so this
; has to come after it. The sums themselves never use y1.
        move    x:(r7+$20),y1           ; wet gain

; ---- WIDTH: mid/side, then MIX, then onto the dry -----------------------
; M = (L+R)/2, S = (L-R)/2, out = M +/- w*S. w=0 collapses to mono, w=1 gives
; back exactly the two tap sums.
        move    x:(r7+$2d),a
        move    x:(r7+$2e),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$25)            ; M
        move    x:(r7+$2d),a
        sub     x0,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$2c),y0           ; WIDTH
        mpy     x0,y0,a
        move    a,x:(r7+$26)            ; w*S

; ---- wet high-cut (Round 11) --------------------------------------------
; VintageVerb runs an output high-shelf/high-cut ON TOP of its in-loop
; damping; we had none, and the measured result was an INVERTED HF ladder --
; HF outliving the mids in every mode (VOICING.md Round 11), because the
; in-loop damping cannot reach the HF that the always-on AP modulation
; scatters up from the mids (Round 11's shelf finding). One-pole low-pass on
; M and w*S -- filtering the two components IS filtering L and R, since
; L = M + wS and R = M - wS. Sits BEFORE the bus write below, so the shared
; REVERB WET carries the voiced signal.
; Coefficient per mode in $7a (md_* block), states $78/$79 (free slots,
; zeroed in warm-up). y1 holds MIX and must survive -- the coefficient rides
; y0, which is free here (WIDTH is done, dry gain reloads it later). The
; mpy encodes as mpysu; the coefficient is always positive, so it is safe,
; and it is a plain product (no doubling) -- c is stored as-is.
        move    x:(r7+$25),a            ; M
        move    x:(r7+$78),b            ; high-cut state, M channel
        sub     b,a
        move    a,x0
        move    x:(r7+$7a),y0           ; per-mode wet high-cut coefficient
        mpy     x0,y0,a                 ; c*(x - y)
        add     b,a                     ; y += c*(x - y)
        move    a,x:(r7+$78)
        move    a,x:(r7+$25)            ; M, high-cut
        move    x:(r7+$26),a            ; w*S
        move    x:(r7+$79),b            ; state, S channel
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$79)
        move    a,x:(r7+$26)            ; w*S, high-cut

; ---- write M to the shared REVERB WET buffer (BUS.md task 8) ------------
; Pre-WIDTH, pre-MIX: the bus carries this reverb's own clean output, not
; this track's own colouring of it. x0/a/b/r5 are all free here (x0's old
; value, S, is done -- w*S is already stashed above -- and the next line
; reloads x0 fresh).
        move    x:(r7+$64),a
        move    a,r5
        move    x:(r7+$25),b
        move    b,y:(r5)
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$64)

        move    x:(r7+$25),a
        move    x:(r7+$26),x0
        add     x0,a
        move    a,x0
        mpy     x0,y1,a                 ; * MIX
        move    a,x:(r7+$71)            ; stash the wet half
        move    x:(r0),x0               ; dry
        move    x:(r7+$70),y0           ; dry gain -- y0 is free here, y1 must
        mpy     x0,y0,a                 ; keep holding MIX for the R channel
        move    x:(r7+$71),x0
        add     x0,a                    ; dry*(1-MIX) + wet*MIX
        move    a,x:(r0)                ; L in place
        move    x:(r7+$25),a
        move    x:(r7+$26),x0
        sub     x0,a
        move    a,x0
        mpy     x0,y1,a
        move    a,x:(r7+$71)            ; same crossfade on the right
        move    x:(r0+n0),x0
        move    x:(r7+$70),y0
        mpy     x0,y0,a
        move    x:(r7+$71),x0
        add     x0,a
        move    a,x:(r0+n0)             ; R in place
        move    (r1)+                   ; all four line pointers advance together
        move    (r2)+                   ; and each wraps inside its own line
        move    (r3)+                   ; under m1..m4 = $fff
        move    (r4)+
        move    #>$2,n0
        move    (r0)+n0                 ; advance one stereo frame
rvend:

noloop:

; ---- save the phase, restore the M registers ---------------------------
        move    r1,a
        move    #>$fff,x0               ; 4096-word lines (increment 2), so
        and     x0,a                    ; the phase is 0..4095 -- which is what
                                        ; the pre-delay derivation ($30, masked
                                        ; $fff into a 4096 buffer) was already
                                        ; shaped for; PRE above ~46 ms read
                                        ; never-written memory while the phase
                                        ; wrapped at 2048.
        move    a,x:(r7+$83)
dry:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
