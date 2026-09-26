; ---------------------------------------------------------------------------
; BusVerb: an eight-line FDN reverb. Four series input allpasses into eight
; 4096-word lines (spacing 0x1000, modulo 0xFFF) with an 8x8 fast
; Walsh-Hadamard, one-pole damping and a low cut inside the feedback path,
; an interpolated LFO on every line, a shimmer pitch shifter, a gate and
; mid/side width. The tank tap loop and the write-back loop are rolled over
; a per-line state table in absolute Y; lines 0 and 1 carry an in-loop
; allpass, lines 2-7 do not.
;
; The buffer base is the literal Y:0x4000, every instance: the bank's whole
; FX2 allocation (0x4000..0xBFFF) is the eight lines. Every other buffer is
; in this core's half of the shared window (build_bus.py rewrites the base
; literal per payload):
;   lines      base+0x0000 .. base+0x7fff   4096 words each, spacing 0x1000
;              taps to ~3914 (89 ms) at SIZE max
;   pre-delay  shared+0x1000 .. 0x1fff      4096 words: mapped and cleared
;                                           by the warm-up, never read or
;                                           written otherwise
;   input APs  shared+0x2000 .. 0x3fff      2048 words each, taps
;                                           641/1051/1511/1949
;   shimmer    shared+0x0800 ..             2048 words (NOSHIM=1 excises it)
;   in-loop AP shared+0x4000/0x4200         512 words each, taps 298 446
;   tank state shared+0x4500 .. 0x453f      table A (6 words/line) at +0x4500,
;                                           table B (2 words/line) at +0x4530
;   bloom APs  shared+0x4800/0x5000         2048 words each, taps 1801/1291
;
; Tap constants are fractions of the line length ($3DD800 = 1979/2048), so a
; re-layout moves only the modulo, the spacing and the shift counts.
;
; The tank state tables, 64 words:
;   table A, six words per line, walked at stride 6 by the tank loop:
;     +0  read offset   (4096 - tap) - LFO offset        per block
;     +1  interpolation fraction                         per block
;     +2  d0 carry: last sample's tap                    per sample, seeded per block
;     +3  damping state                                  PERSISTENT
;     +4  LO state                                       PERSISTENT
;     +5  this line's output                             per sample
;   table B, two words per line, walked by the feedback loops fbA/fbB:
;     +0  input weight  (+1, -1 or 0, scaled)            per block
;     +1  line gain G_k                                  per block
; The persistent words need no save/restore (one REVERB SERVER per bank; the
; warm-up zeroes the whole allocation, these tables included).
;
; State in the per-instance r7 block ($00..$83; $84+ hangs the DSP). A slot
; census of the source, 23 Sep 2026:
;   r7+$00..$07   LFO int/frac, lines 4..7 ($00/$01 line 4, ...)   per block
;   r7+$08        line 4's (4096 - tap) (per block); the bloom output (per
;                 sample, for the wet sums)
;   r7+$09/$0a    (4096 - tap), lines 5/6                          per block
;   r7+$0b/$0d    table A / table B base                           per block
;   r7+$0c        REV bus auto-gain 1/sqrt(N)                      per block
;   r7+$0e        SHMR, glided                                     per block
;   r7+$0f        shimmer write phase (persistent, masked)
;   r7+$14        the dispatcher's call flag; a shimmer park (head 0's t0)
;   r7+$15        the tank input (per sample)
;   r7+$16..$19   Hadamard u0..u3 (lines 0..3), walked by pointer
;   r7+$1a..$1d   feedback scratch fb0..fb3 (fbA writes, the APs and the
;                 write-back read)
;   r7+$1e        k_mode, the TIME law's mode constant
;   r7+$1f        DAMP coefficient, glided
;   r7+$20        wet gain (wgain/2)
;   r7+$21..$24   LFO int/frac, lines 0/1                          per block
;   r7+$28        tank modulation depth (pinned, scaled per mode)
;   r7+$29        GHOLD; $30 GCNT; $62 GLVL (the gate)
;   r7+$2a/$2b    (4096 - tap), lines 1/2                          per block
;   r7+$2c        SHFT's read-phase step
;   r7+$2d/$2e    wet L / R (per sample)
;   r7+$2f        LFO base increment
;   r7+$31        the private line base
;   r7+$32..$35   input diffuser bases; $36/$37/$4c/$4d line 4..7 bases
;   r7+$38        shimmer read fraction (per sample)
;   r7+$3a..$3d   Hadamard u4..u7 (lines 4..7), walked by pointer
;   r7+$3e/$4f/$50/$51/$47/$48/$49/$4a   LFO phase, lines 0..7 (persistent)
;   r7+$3f        DIFF's mode offset; $6d g, glided
;   r7+$40        LO coefficient, glided
;   r7+$41..$44   feedback scratch fb4..fb7
;   r7+$45/$46    (4096 - tap), lines 0/3; $4b line 7              per block
;   r7+$4e        shimmer one-pole state
;   r7+$52..$55   in-loop AP LFO int/frac, A / B                   per block
;   r7+$56..$59   LFO int/frac, lines 2/3                          per block
;   r7+$5a/$5b    LFO triangle stash, lines 0/1                    per block
;   r7+$5c/$5d    in-loop AP d1 carry, A / B (per sample)
;   r7+$5e/$5f    in-loop AP bases; $60/$61 their (512 - tap)
;   r7+$63/$6a    this call's REV ACC read / write address (the loop walks
;                 them in n3 / n2)
;   r7+$64/$65    this call's chain read address (walked in the slot) / the
;                 chain gain, 1/8 while the delay is live, else 0
;   r7+$67        this call's frame offset; $6b last-seen rotation
;   r7+$6c        lines 4-7 tap scale; $6f SIZE's mode scale
;   r7+$70        WET, glided; $72/$73 damping / modulation scale per mode
;   r7+$74..$77   this mode's line fractions
;   r7+$78/$79    wet high-cut states M / S (persistent); $7a its coefficient
;   r7+$7b        bloom g; $7e..$81 the diffuser taps (n5 values)
;   r7+$82        warm-up counter, $2c0000 | blocks, capped at 0x100
;   r7+$83        write phase (persistent, masked on load as well as save)
;   $71 WET ramped per sample, $7c its per-sample step (per block)
;   free: $10..$13, $25..$27, $39, $66, $68, $69, $6e, $7d
;   (fourteen; $25/$26 and $39 went to registers 23 Sep 2026)
;
; Parameters (page 1 slots 0-5, page 2 slots 6-11):
;   p0 DEL  -> this host's own dry send into the delay (the AUX
;              accumulator, counted as an AUX client while nonzero; ramp
;              and pointer in core-private y:$09f4..$09f6)
;   p1 REV  -> this host's own dry send into the reverb (written to the
;              REV accumulator, flagged at y:$981); slot 0 until 26 Sep 2026
;   p2 SIZE, p3 SHMR (linked), p4 SHFT (6 intervals, -12..+24)
;   p5 WET  -> the reverb's level: the host prints wet*WET under its dry
;   page 2: MODE (slot 6, $c's KNOB field), TONE (slot 7, $c's companion:
;   LP and HP on one knob, the HI/LO blocks), DIFF (slot 8, $d's KNOB
;   field), GATE (slot 9, $d's companion), DLY (slot 10, $e's KNOB
;   field), TIME (slot 11, $e's companion: the decay law, README.md; page-1
;   slot 1 until 26 Sep 2026)
;   core-private y:$09f1 delay-liveness grace; $09f0 the REV level for
;   the loop; $09f3 SIZE's glide state; $09f4/$09f5 DEL's ramp and step;
;   $09f6 DEL's AUX write pointer; $0905/$0906 the shimmer's read
;   phase and HP state
;
; Every proc() call runs the position-0 rotation-flip-and-clear housekeeping
; modules/send/send_client.asm describes, sums the shared REVERB accumulator
; into its input (one block of latency) and prints its wet under the host's
; dry (20 Sep 2026: the wet leaves through the host and nowhere else; the
; published stage output and the T8 return went). The body runs on
; BOTH dispatcher calls: the a=0 call is the first sub-block, frames
; [0,split) at r0=0 with n7=split; only the LFO advance gates on the a flag.
; The warm-up (a tagged block counter in r7+$82) zeroes the allocation 128
; words a block over 256 blocks and outputs dry until warm.
; ---------------------------------------------------------------------------

; LINES = 8, the tank loop bound, is hardcoded: dsp_asm has no equ.

init:
; the glided coefficients (20 Sep 2026) start from 0: a short fade-in on
; select instead of a block of whatever the slot held
        clr     a
        move    a,x:(r7+$0e)            ; SHMR
        move    a,x:(r7+$1f)            ; TONE's c
        move    a,x:(r7+$40)            ; TONE's LO
        move    a,x:(r7+$6d)            ; DIFF's g
        move    a,x:(r7+$70)            ; WET
        move    a,y:>$09f3              ; SIZE's f (the glide state)
        move    a,y:>$09f4              ; DEL's ramp (the per-sample level)
        rts

proc:
; ---- HOSTGUARD: a remix that hides or locks this engine has the build put
; its host-slot test here (r7 == 0x6200, this core's position 0: T1 on
; core 1, T5 on core 0); elsewhere the call returns before touching any
; state, an exact dry pass. A comment in every other remix.
; HOSTGUARD
; ---- BOTH calls are audio; the A accumulator says which sub-block --------
        move    a,x:(r7+$14)            ; the dispatcher's call flag, stashed
                                        ; (0 = the a=0 sub-block, $010000 = a=1)
; ---- this call's frame offset, from r0 (21 Sep 2026) --------------------
; The dispatcher passes r0 = 0 on a block's first call and r0 = 2 x split on
; the a=1 call of a split block (measured under the port: r0 = $e for a trig
; at frame 7). Until 21 Sep 2026 the offset was reconstructed from a flag
; and a split the a=0 call stashed in $65/$66 for the matching a=1 call; on
; the unit a host with a trig on every step (T2 THRU, T3 STATIC) washed with
; white noise while the port stayed clean, the shape of a stash that does
; not survive between the two calls: a second call taken for a first one
; advances position 0's rotation tracker twice in a frame, and the tracker
; keeps a lead of one for ever (a metallic wash on every power cycle). r0
; needs no state.
        move    r0,a
        asr     #$1,a,a                 ; words -> frames
        and     #>$f,a                  ; 0..15 by construction; garbage masked
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$67)            ; this call's frame offset
bus_off_done:

; ---- position-0 housekeeping: flip the shared bus rotation, clear the new
; write-target ACC buffers. Gated on r7==0x6200 AND offset==0 -- copied from
; modules/send/send_client.asm, must stay identical (BUS.md Known limitations).
; Housekeeping is normally done by position 0 (r7 == 0x6200, the bank's first
; FX2 call). That alone breaks the moment the first track's FX2 is NONE: our
; code never runs there, so nobody flips the rotation or clears the
; accumulators, and the bus saturates. NONE became selectable with the task-11
; menu, so this is reachable in ordinary use.
;
; Self-healing election instead. Position 0 still housekeeps whenever it runs.
; Any other instance takes over if it sees that the rotation has NOT changed
; since the last time it ran -- which can only mean nobody housekept in
; between. Costs one r7 word (the rotation this instance last saw) and no new
; global signal, so it needs nothing the bus does not already have.
;
; Gated on the split offset FIRST: only a block's first call may housekeep, so
; a split block's second call can never flip a second time -- the same trap
; the original position-0 code was written around.
; XBUS_GATE -- build_bus.py substitutes a payload gate here when XBUS=1.
; A shared-memory bus is housekept by ONE core only: both cores number their
; own instances from zero, so each core's position 0 believes it is the
; housekeeper and they would flip the shared rotation TWICE a block, cancelling
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
        move    y:>$900,a
        and     #>$70,a
        move    a1,x0
        move    x0,a                    ; offset now, A2-clean
        move    x:(r7+$6b),x0
        cmp     x0,a
        bne     bus_seen                ; it moved: someone else housekept
bus_dohk:                               ; nobody did -- take over this block

; y:>$900 holds the WRITE OFFSET (0/16/32/48), not the bare buffer index --
; see the layout comment in modules/send/send_client.asm. FOUR buffers, so the rotation
; is +16 mod 4 and the mask that does the modulo sanitises boot garbage too.
; No `asl #$4` follows: the value is already scaled.
        move    y:>$900,a
        add     #>$10,a
        and     #>$70,a
        move    a1,x0                   ; A2-clean: a boot word with bit 23 set
        move    x0,a                    ; would saturate the store
        move    a,y:>$900               ; the new CURRENT rotation
; ⚠️ CLEAR THE BUFFER WRITTEN **NEXT** BLOCK, NOT THIS ONE.
; Clearing the buffer we are about to write races the OTHER core's writers:
; core 0 clears at the start of its block and everyone fills it during that
; block, so a core-1 writer that gets there BEFORE core 0's housekeeper has
; its contribution written and then wiped. Straddle that boundary and the
; sender drops out on some blocks and not others -- intermittent dropout,
; which is broadband hash exactly like the two defects before it.
; The four-buffer rotation fixed clear-vs-READ and the per-core tracking fixed
; which-buffer; NEITHER touches clear-vs-WRITE. This does, and it is free:
; with four buffers there is an idle slot. The buffer written next block was
; last READ a full block ago and will not be WRITTEN for another full block,
; so clearing it now has a block of margin on both sides.
        add     #>$20,a                 ; two on: written two blocks from now,
        and     #>$70,a                 ; last read three blocks ago
        move    a,x0                    ; bases for the clear AND the count

        move    #>$901,b                ; ONE BUS (6 Sep 2026): the AUX
        add     x0,b                    ; accumulator, the only one left
        move    b,r2                    ; r2 = AUX ACC[new] base
        move    #>$ffffff,m2
        clr     a
        do      #16,>bus_zclr
        move    a,y:(r2)+
bus_zclr:
        move    #>$9d8,b                ; the REV accumulator: the chain's
        add     #>$80,b                 ; base plus its length
        add     x0,b
        move    b,r2                    ; r2 = REV ACC[new] base
        do      #16,>bus_racclr
        move    a,y:(r2)+
bus_racclr:
        nop
; ---- release both server-role locks for this block (BUS.md hardware test 3)
; a is still 0 from the clear loop above. Whichever of the three effects is
; position 0 does this, so the locks are freed exactly once per block and
; re-claimed below in dispatch order.
        move    a,y:>$9c1               ; DELAY SERVER role owner
        move    a,y:>$9c2               ; REVERB SERVER role owner
; ---- reset the new write buffer's SEND COUNT, alongside its accumulators ---
; The housekeeping is duplicated between this file and modules/send/send_client.asm and
; must stay in step (BUS.md). x1 holds the NEW OFFSET from the rotation above.
; Without this the count grows without bound and the auto-gain above divides by
; garbage.
; The counts are one word per buffer, not sixteen, so this is one of the three
; places the offset is scaled back down to a bare index.
        move    x0,a                    ; the SAME buffer the clear loop just
        asr     #$4,a,a                 ; zeroed: count and accumulator move
        move    #>$9c7,x0               ; together (0..3); the AUX count
        add     x0,a
        move    a,r1
        clr     a
        move    a,y:(r1)                ; AUX count = 0
        move    r1,b                    ; the REV count, same index: 0x983
        move    #>$44,x0                ; sits 0x44 below the AUX count
        sub     x0,b                    ; 0x9c7 (both relocate together)
        move    b,r1
        nop
        move    a,y:(r1)                ; REV count = 0
bus_seen:
        move    y:>$900,a               ; remember this block's offset so next
        and     #>$70,a                 ; block we can tell whether anybody
                                        ; else housekept in between
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
        move    y:>$9c2,a
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
        move    a,y:>$9c2
bus_mine:
; MARKER_LOCK

; ---- this call's REVERB ACC read address and WET write address ----------
; READ is the OTHER buffer from the current write rotation -- the one every
; SEND client (and our own dry sum, below) finished filling last block
; (one-block latency, BUS.md's Mechanism section). WRITE uses the SAME
; rotation clients currently write into, so it is complete and ready by the
; time next block flips -- for a future cross-bus reader (task 10), not
; consumed by anything yet.
; y:>$900 holds the WRITE OFFSET already scaled by the 16-word buffer stride,
; so the write addresses need no shift at all. THE READ TARGET IS TWO BUFFERS
; BACK, `write + 32 & $30` -- with four buffers that leaves an idle block on
; each side of the reader, which is the cross-core race fix (see the layout
; note in modules/send/send_client.asm).
; ---- chain_live: is the delay (chain stage 1) running? -------------------
; The delay stamps y:$9c3 nonzero every block it processes (after its
; warm-up); this reads it, clears it (clear-on-read, single writer, single
; reader -- the station has its own word, $9c5) and keeps 3 blocks of grace
; in CORE-PRIVATE y:$09f1 (r7 is full). The tank hears the REV accumulator
; (every REV send and this host's own SEND) plus, while the delay is live,
; the chain buffer (the repeats x DLY); a chain gain of 0 keeps a stale
; chain out when it is not (25 Sep 2026: the sends split into DEL and REV;
; the aux was the reverb's input until then).
        move    y:>$09f1,b              ; blocks of grace left
        move    #>$9c3,r5               ; the delay's stamp word
        bsr     stampgr                 ; b = grace after this block's stamp
        move    b,y:>$09f1
        clr     a                       ; (BEFORE the tst: clr sets the CCR)
        move    #$10,x0                 ; 1/8: the loop's asl #3 lands the
        tst     b                       ; chain word untouched (mpy by
        tne     x0,a                    ; $100000 then <<3 is the identity)
        move    a,x:(r7+$65)            ; this block's chain gain, else 0

        move    y:>$900,a
        move    a,x1                    ; x1 = write offset (0..112)
        add     #>$50,a                    ; five buffers on == three buffers back
        and     #>$70,a                    ; mod 8
        move    a,x0                    ; x0 = the read offset
        move    x:(r7+$67),b            ; this call's split-aware frame offset
        move    #>$9d8,a                ; the CHAIN buffer
        add     x0,a
        add     b,a
        move    a,x:(r7+$64)            ; this call's chain read address
        add     #>$80,a                 ; the REV accumulator sits $80 above
        move    a,x:(r7+$63)            ; this call's REV read address
; ---- this call's REV ACC write address: the host's own SEND ---------------
; SEND's recipe: the REV base + write offset (x1, 0/16/../112) + the
; split-aware frame offset (b). The loop walks it in n2; the level is the
; knob's copy at y:$09f0.
        move    #>$9d8,a                ; the REV accumulator: the chain's
        add     #>$80,a                 ; base plus its length
        add     x1,a
        add     b,a
        move    a,x:(r7+$6a)            ; this call's REV ACC write address

; ---- bus auto-gain: resolve 1/sqrt(N) for this block's READ buffer ------
; ---- the module's P table: n4 holds its base for the block --
        move    #>$fab1e0,n4            ; the table -- rewritten by build_bus.py
        move    #>$ffffff,m5            ; r5 linear: for the read below and the
                                        ; warm-up's clear ("whatever m5 the
                                        ; previous block left", 9 Aug)

        move    x1,a
        add     #>$50,a                    ; read offset = write + 5 buffers = 3 back
        and     #>$70,a                    ; mod 8
        asr     #$4,a,a                 ; -> bare index (0..7)
        add     #>$983,a                ; the REV count
        move    a,r5
        move    #>$1,x0                 ; the "one more client" increment
        clr     b                       ; b = 0 -- BEFORE the tst below
        move    y:>$981,a               ; our own SEND flag (last block's: the
                                        ; write below runs after this) -- the
                                        ; host's dry is in the REV accumulator,
                                        ; as a REV send's is, so it counts the
                                        ; same way
        tst     a
        tne     x0,b                    ; sending -> b = 1
        move    y:(r5),a                ; clients that wrote the buffer we read
        add     b,a                     ; ... plus ourselves, if sending
        and     #>$7,a                  ; masked: boot garbage cannot index wild
        move    a1,x0
        move    x0,a                    ; A2-clean before it becomes an offset
        move    a,n5                    ; the count, 0..7
        move    n4,r5                   ; the table (m5 linear, set above)
        move    p:(r5+n5),a             ; 1/sqrt(N): the reciprocals lead the table
        move    a,x:(r7+$0c)            ; this block's REV bus gain, used per sample.
                                        ; $0c, NOT $6d: $6d is the DIFFUSION
                                        ; allpass coefficient g. And $0c is
                                        ; the bus gain's ALONE: the md_* tap
                                        ; scale parked here for a day and every
                                        ; sample multiplied the bus by ~0.75
                                        ; instead of 1/N. It lives in $6c now.

; ---- the SEND knob is the host's client flag ------------------------------
; The knob field goes to y:$981 every block (one writer, one word, idempotent
; across a split block); the REV auto-gain above counts it as one client
; while it is nonzero, so an idle host takes no share (the phantom-client
; rule). Sticky
; rather than clear-on-read: a stamp lost to the other core's timing would
; step the delay's gain for a block. Not $9d3..$9d7: per-block state there
; was dead on hardware, mechanism unknown. What would falsify this: a delay
; whose level drops by 1/sqrt(N) when the reverb host's SEND comes up with
; nothing playing on it.
        move    x:(r6+$1),a             ; REV (slot 1 since 26 Sep 2026, slot 0
        and     #>$7f0000,a             ; until then), the knob field: the
                                        ; host's own dry into the REV bus
        move    a1,y:>$981              ; the REV client flag (shared window)
; The sample loop's copy of the level. r6 walks the state table in the loop,
; so the knob is copied to core-private Y at $09f0: a zero-padded `$09xx`
; literal is the one form the XBUS pass leaves alone (build_bus.py).
; Core-private rather than the shared window because per-block
; shared-window state was dead on hardware for in-loop reads (mechanism
; unknown); the flag above is only ever read per block. Outside the delay's
; own core-private words ($0901-$0904, $0907-$090d).
        move    a1,y:>$09f0             ; REV level, for the loop

; ---- DEL: this host's own send into the delay's aux (26 Sep 2026) --------
; SEND's DEL recipe (modules/send/send_client.asm): the level ramped per
; sample from where the last block's ramp ended (core-private y:$09f4, zeroed
; at init; its step at $09f5), written with 3 bits of headroom into the AUX
; accumulator at this block's write offset (x1) plus this call's frame
; offset (the pointer at $09f6, walked per sample), and counted as an AUX
; client, on a block's first call, only while nonzero (an idle client that
; registers dilutes the real ones). Tapped from the dry at the loop's top,
; before the tank: T5's own wet never reaches the delay.
        move    x:(r6),a                ; DEL (slot 0), the knob field
        and     #>$7f0000,a
        move    y:>$09f4,b              ; the ramp's running value
        sub     b,a
        asr     #$4,a,a                 ; the change, spread over 16 frames
        move    a,y:>$09f5              ; ... its per-sample step
        move    #>$901,a                ; the AUX accumulator
        add     x1,a                    ; + this block's write offset
        move    x:(r7+$67),x0           ; + this call's frame offset
        add     x0,a
        move    a,y:>$09f6              ; the AUX write pointer, for the loop
        move    x:(r7+$67),a
        tst     a
        bne     rvdelcnt                ; not this block's first call
        move    x1,a                    ; the WRITE buffer's count, as a bare
        asr     #$4,a,a                 ; index
        move    a1,x0
        move    x0,a
        move    #>$9c7,x0               ; the AUX count region
        add     x0,a
        move    a,r5                    ; (m5 linear: set above)
        move    #>$1,x0
        clr     b                       ; b = 0 -- BEFORE the tst below
        move    x:(r6),a                ; DEL
        and     #>$7f0000,a
        tst     a
        tne     x0,b                    ; sending -> b = 1
        move    y:(r5),a
        add     b,a
        move    a,y:(r5)                ; AUX count += 1 ONLY if sending
rvdelcnt:

; ---- DLY: how much of the delay's repeats the chain carries ---------------
; Page-2 slot 10, $e's KNOB field, published to y:$982 every block (one
; writer, one word, like $981); the delay reads it per block and scales the
; wet it writes into the chain buffer. 0 = the tank hears the send alone.
        move    x:(r6+$e),a             ; DLY: page-2 slot 10
        and     #>$7f0000,a             ; knob field only
        move    a1,y:>$982              ; A1: the A2 an AND leaves is stale

        move    #>$ffffff,m0            ; audio is read and written via r0
        move    #>$4000,x0
        move    x0,x:(r7+$31)

; ---- warm-up: stock DARK's shape, adapted --------------------------------
        move    x:(r7+$82),a
        and     #>$fffe00,a                  ; tag field -- AND cleans A1 only
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        move    #$2c,x0
        cmp     x0,a
        beq     warmtag
        clr     a                       ; garbage tag: warm-up starts at 0
        bra     warmrun
warmtag:
        move    x:(r7+$82),a
        and     #>$1ff,a                
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
        move    #>$ffffff,m5            ; ISOLATION 9 Aug: the clear below wrote
                                        ; y:(r5)+ under whatever m5 the previous
                                        ; block left. Forced linear.
        move    x:(r7+$15),a            ; the count again, still A2-clean
        asl     #$4,a,a                 ; count*16 ...
        move    a,b
        move    x:(r7+$15),a
        asl     #$6,a,a                 ; ... + count*64 = count*80
        add     b,a
        move    #>$30000,x0             ; -> $38000 on payload B
        add     x0,a
        add     #>$800,a                
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
        do      #80,>wshclr
        move    b,y:(r5)+
wshclr:
        move    b,x:(r7+$3e)
        move    b,x:(r7+$78)            ; wet high-cut states (Round 11): boot
        move    b,x:(r7+$79)            ; garbage here would click at warm-end
        move    b,x:(r7+$4f)
        move    b,x:(r7+$50)
        move    b,x:(r7+$51)
        move    b,x:(r7+$47)            ; LFO phase line 4 (8-line)
        move    b,x:(r7+$48)            ; LFO phase line 5
        move    b,x:(r7+$49)            ; LFO phase line 6
        move    b,x:(r7+$4a)            ; LFO phase line 7
        move    x:(r7+$15),a            ; reload count
        add     #>$1,a                
        move    #$2c,x0
        add     x0,a                    ; tag | count+1
        move    a,x:(r7+$82)
        bra     dry                     ; output stays dry until warm
warmdone:
; MARKER_WARM
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
; ($10..$13, lines 0-3's bare bases, were still stored here until 14 Sep
; 2026 -- 20 words with no reader in this file, the roll source or the
; build's LFO slot tables.)
; $36/$37 are line bases the rolled tap loop no longer reads.
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
; Input allpasses, 2048 words apart: their taps are 641/1051/1511/1949
; (manifest _MODE_COMMON, as 2048 - tap), so 2048 is the smallest power of
; two that holds them.
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
        move    #>$4500,a
        add     x0,a
        move    a,x:(r7+$0b)            ; the tank's per-line state table A
        move    #>$4530,a
        add     x0,a
        move    a,x:(r7+$0d)            ; table B: write-back params (8x2=16 words)

; ---- prime table B: input injection weight and allpass flag, all 8 lines --
        move    x:(r7+$0d),r1           ; straight to r1: one word cheaper than
                                        ; loading a and copying it across
        move    #2,n1                   ; SHORT immediate: 1 word, and safe
        clr     a
        move    a,y:(r1)+n1             ; line 0 weight  0
        move    a,y:(r1)+n1             ; line 1 weight  0
        move    a,y:(r1)+n1             ; line 2 weight  0
        move    #$7f,a
        move    a,y:(r1)+n1             ; line 3 weight  +1  (shortest, group A)
        clr     a
        move    a,y:(r1)+n1             ; line 4 weight  0
        move    a,y:(r1)+n1             ; line 5 weight  0
        move    a,y:(r1)+n1             ; line 6 weight  0
        move    #$7f,a
        neg     a
        move    a,y:(r1)+n1             ; line 7 weight  -1  (shortest, group B)

; ---- state lives in r7, which is already per-instance and persistent ----
; ---- rebuild the four delay pointers from the saved phase ----------------
        move    x:(r7+$83),a
        and     #>$fff,a                  ; mask on LOAD: the phase may be garbage
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
        move    #>$fff,m3               ; line (the priming reads y:(rN+nN)
        move    #>$fff,m4               ; through them). Bases are base+0/0x1000/
                                        ; 0x2000/0x3000 and base is the literal
                                        ; 0x4000, so every line is 4096-aligned
                                        ; as modulo requires.

; ---- MODE: character select, page-2 slot 6 ($c bits 16-23) ----------------
        move    x:(r6+$c),a
        and     #>$ff0000,a             ; slot 6's KNOB field, not SHMR's
                                        ; companion byte below it
        move    a1,x0                   ; AND cleans A1 only
        move    x0,a                    ; -> 0..2, MSB-ALIGNED ($010000 per
                                        ; step) as the short immediates the
                                        ; dispatch below compares against
; MODE_OVERRIDE
; ---- MODE: one table copy ----------------------------------
        move    #$2,x0                  ; BIG, MSB-aligned like the index
        cmp     x0,a
        tgt     x0,a                    ; index > 2 -> 2
        asr     #$a,a,a                 ; $010000 per step -> 64 per step,
                                        ; the row stride
        move    a,n5
        move    n4,r5                   ; the table (n4 since the bus gain)
        move    (r5)+n5                 ; + 64 * MODE
        move    #8,n5                   ; + the eight reciprocals that lead
        move    (r5)+n5                 ; the table (short: zero-extended)
        move    n7,y1                   ; park the sample count
        do      #17,>mdcpy
        move    p:(r5)+,n7              ; the r7 slot
        move    p:(r5)+,a               ; this MODE's value for it
        move    a,x:(r7+n7)
mdcpy:
        move    y1,n7                   ; the sample count back

    ; ---- SIZE: scale all eight tap lengths ----------------------------------
            move    x:(r6+$2),x0            ; SIZE: page-1 slot 2 (16 Sep 2026,
                                            ; linked to TIME on its left)
            move    #$4c,y1                 ; SIZE span
            mpy     x0,y1,a
            add     #>$333000,a                  ; 0.125 .. 0.993 ; f = 0.400 .. 0.989, was
; SIZE GLIDES (20 Sep 2026): f moves 1/64 of the way to the knob per block,
; so the eight taps step by a sample now and then instead of all jumping
; on a detent. The state (y:$09f3, zeroed at init) starts AT the target
; and is clamped to f's own range, so a garbage word cannot fold a tap.
            move    a,x0                    ; target f
            move    y:>$09f3,b
            tst     b
            teq     x0,b                    ; first block: at the target
            sub     b,a                     ; target - state (a: the target)
            asr     #$6,a,a
            add     b,a
            move    #>$333000,y0
            cmp     y0,a
            tlt     y0,a                    ; floor
            move    #>$7f0000,y0
            cmp     y0,a
            tgt     y0,a                    ; ceiling
            move    a,y:>$09f3
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
            move    b,x:(r7+$45)            ; line 0 (all four lines read
                                            ; through the interpolated path)
            move    x:(r7+$75),x0           ; this MODE's line 1 fraction
            mpy     x0,x1,a
            asr     #$a,a,a                 ; back to an integer tap (4096-word lines)
            or      y1,a                    ; force the tap ODD (as line 0)
            move    n0,b
            sub     a,b                     ; 4096 - tap, for the modulated read
            move    b,x:(r7+$2a)
            move    x:(r7+$76),x0           ; this MODE's line 2 fraction
            mpy     x0,x1,a
            asr     #$a,a,a                 ; back to an integer tap (4096-word lines)
            or      y1,a                    ; force the tap ODD (as line 0)
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
            move    #>$fff,m6           ; r6 walks the state tables (the
                                        ; priming, the tank loop, the collect)
                                        ; inside one 4096-aligned block; set
                                        ; per block so whatever the previous
                                        ; effect left in m6 cannot wrap them.
                                        ; Left at $fff on rts (unchanged since
                                        ; the reverb first shipped)
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
        move    x:(r6+$e),a             ; TIME: page-2 slot 11, $e's companion
        and     #>$7f00,a               ; field (page-1 slot 1 until 26 Sep
        asl     #$8,a,a                 ; 2026) -> value<<16, t
; t GLIDES (26 Sep 2026): 1/32 of the way to the knob per block in $10,
; snapping to it when the step rounds to nothing; 0 (init) starts at the
; knob. The line gains below are per block, and a TIME jump stepped them.
        move    a1,y1                   ; t, the knob
        move    x:(r7+$10),b
        tst     b
        teq     y1,b                    ; the first block: at the knob
        move    y1,a
        move    b,x0
        sub     x0,a
        asr     #$5,a,a
        add     x0,a
        cmp     x0,a                    ; no progress: at the knob
        teq     y1,a
        move    a,x:(r7+$10)
        move    a,x0
        move    #>$3bbbbb,y1            ; the bloom's g: 0.40 + 0.467 t
        mpy     x0,y1,a
        add     #>$333333,a
        move    a,x:(r7+$7b)
        move    #>$7fffff,a
        sub     x0,a                    ; 1 - t
        move    a,x0
        move    x0,y1
        mpy     x0,y1,a                 ; (1 - t)^2  (signed order; both >= 0)
        move    a,x0
        move    #>$2e978d,y1            ; d_span 0.364
        mpy     x0,y1,a
        add     #>$072b02,a             ; + d_min 0.056
        move    a,x0
        move    x:(r7+$1e),y1           ; k_mode, parked by the md_ block
        mpy     x0,y1,a                 ; d = k * (...)
        neg     a
        add     #>$2d413c,a             ; $1e = a - d
        move    a,x:(r7+$1e)

        move    x:(r7+$0d),a            ; table B base
        add     #>$1,a                
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

; ---- TONE, upper half = HI: the high cut inside the feedback path ---------
; The one-pole is s += c*(d-s), so a LARGE c tracks the input and keeps
; highs: LP 0 gives c = 0.125 (dark), LP 127 gives c ~ 0.99 (bright).
; ONE TONE KNOB (page-2 slot 7, $c's companion) DRIVES BOTH CUTS. TONE 0..64
; is LP 0..127 with HP at 0 (dark to flat); 64..127 is HP 0..126 with LP
; wide open (flat to thin). Both halves come from ONE sub: b = (TONE-64)<<16
; sets N while TONE < 64, and the tmi floors it to a clean 0 for the LO
; block below (HP-equivalent = 2*(TONE-64), so 0 up to 64: bypassed exactly).
; The LP-equivalent is min(2*TONE, 127), the clamp a second Tcc off the same
; sub (moves between, so the CCR survives): TONE >= 64 loads 63.5<<16 before
; the doubling, which is 127<<16 after it -- the old default EXACTLY.
; ⚠️ Letting the store limiter clamp instead (drop the tpl: 2*TONE<<16 is
; >= 1.0 from TONE 64 up and `move a,x0` saturates it to $7fffff) was tried
; to save 3 words and rendered -1.7 dB different from the old default: LP
; 127.99 is c = 1.0, a one-pole with NO high loss per pass, where 127 is
; 0.993 and its -0.12 dB per pass compounds over the tail. TONE 63 vs old
; LP 126 (no limiter involved) rendered bit-identical, which is what pins
; the arithmetic; TONE 64 vs old HP 0 / LP 127 is the default's own gate.
        move    x:(r6+$c),a             ; TONE: page-2 slot 7, $c's companion
        and     #>$7f00,a               ; field (bits 8-15) since 16 Sep 2026
        asl     #$8,a,a                 ; TONE<<16
        move    a,x1                    ; parked: the two loads below are MOVES
        move    x1,b                    ; TONE<<16
        move    #$40,x0                 ; 64<<16
        sub     x0,b                    ; (TONE-64)<<16, N while TONE < 64
        move    x1,a                    ; TONE<<16 (moves leave the CCR alone)
        move    #>$3f8000,x0            ; 63.5<<16
        tpl     x0,a                    ; TONE >= 64 -> a = 63.5<<16
        move    #0,x0
        tmi     x0,b                    ; b = max(0, TONE-64)<<16, for LO
        asl     #$1,a,a                 ; a = min(2*TONE, 127)<<16, exact
        move    a,x0                    ; x0 = LP-equivalent knob field
        move    #$10,a                  ; c = 0.125 + 0.875*LP: the constant
        move    #$70,y1                 ; first, then mac -- one word fewer
        mac     x0,y1,a                 ; than mpy + add, and the same 56 bits
        move    a,x1                    ; scale by MODE's damping constant
        move    x:(r7+$72),y1           ; before it lands. The scale is <= 1.0,
        mpy     x1,y1,a                 ; so c stays inside its safe range and
        move    x:(r7+$1f),x0           ; the knob still spans within a mode;
        sub     x0,a                    ; glided: an eighth of the way per
        asr     #$3,a,a                 ; block (20 Sep 2026)
        add     x0,a
        move    a,x:(r7+$1f)

; ---- TONE, lower half = LO: the low cut inside the feedback path ----------
        move    b,x0                    ; x0 = (TONE-64)<<16, floored
        move    #$08,y1
        mpy     x0,y1,a
        move    x:(r7+$40),x0           ; LO coefficient, glided
        sub     x0,a
        asr     #$3,a,a
        add     x0,a
        move    a,x:(r7+$40)

; ---- WET: the reverb's level on top of the chain input -------------------
        move    x:(r6+$5),a             ; WET target
        move    x:(r7+$70),x0           ; last block's glided WET: where this
        move    x0,x:(r7+$71)           ; block's per-sample ramp starts
        sub     x0,a
        asr     #$3,a,a
        add     x0,a
        move    a,x:(r7+$70)            ; WET, glided (y:$09f3 is SIZE's
                                        ; glide state since 20 Sep 2026)
        sub     x0,a                    ; this block's change, spread over its
        asr     #$4,a,a                 ; 16 frames: the gain on the tail moved
        move    a,x:(r7+$7c)            ; in one step per block until 23 Sep
                                        ; 2026, a click per block while the
                                        ; knob turned (images 58-66)

; ---- the tank modulation depth, scales the LFO triangle -------------------
        move    #$1e,x0                 ; the tank modulation depth, PINNED at
                                        ; what the MOD knob's default (30) gave:
                                        ; the knob went 15 Sep 2026 (Sam: the
                                        ; modulation is the LFOs' and the
                                        ; station's; the tank must not go
                                        ; static), SHMR took its slot
        move    x:(r7+$73),y1           ; scaled per MODE, only ever down
        mpy     x0,y1,a                 ; (BIG sits at unity), so the knob keeps
        asl     #$1,a,a
        move    a,x:(r7+$28)            ; its full range inside each character

; ---- SHFT: shimmer interval select, page-1 slot 4 ------------------------
; The width is pinned at 0.75 at the output stage. SHFT selects the shimmer
; READ-PHASE STEP, in 11.12 fixed-point words per sample (the write is
; decimated 2:1, so step/0.5 is the pitch ratio), low to high:
;   0 -> $0400  ratio 0.5    -12  (sub-octave)
;   1 -> $0aab  ratio 4/3    +5   (fourth)
;   2 -> $0c00  ratio 3/2    +7   (fifth)
;   3 -> $1000  ratio 2      +12  (the default)
;   4 -> $1800  ratio 3      +19  (octave + fifth)
;   5 -> $2000  ratio 4      +24  (two octaves)
; An index past the table falls to -12. The step lands in $2c and the
; shimmer block integrates it into the read phase at y:$0905 (core-private,
; outside the delay's words, so a DEV build with both effects on one core
; cannot collide). Every `move #imm,b` below leaves the flags alone, so each
; beq tests the sub before it.
        move    x:(r6+$4),a             ; SHFT: page-1 slot 4
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a1,x0
        move    x0,a                    ; SHFT index, A2-clean
        move    #>$400,b                ; -12
        tst     a
        beq     shfst
        move    #>1,x0
        sub     x0,a
        move    #>$aab,b                ; +5
        beq     shfst
        sub     x0,a
        move    #>$c00,b                ; +7
        beq     shfst
        sub     x0,a
        move    #>$1000,b               ; +12
        beq     shfst
        sub     x0,a
        move    #>$1800,b               ; +19
        beq     shfst
        sub     x0,a
        move    #>$2000,b               ; +24
        beq     shfst
        move    #>$400,b                ; past the table: -12
shfst:
        move    b,x:(r7+$2c)            ; read-phase step (WIDTH's old slot)

; ---- DIFFUSION: allpass coefficient -- slot 8, $d's KNOB field -----
        move    x:(r6+$d),a
        and     #>$7f0000,a             ; knob field only
        move    a1,x0
        move    x0,a
        move    a,x0
        move    #$2a,y1                 ; span sized so that base + full DIFF +
        mpy     x0,y1,a                 ; the LARGEST mode offset still lands
        move    #$2d,x0                 ; under ~0.80. At the old $380000 span
        add     x0,a                    ; PLATE overflowed $7fffff at DIFF=127
        move    x:(r7+$3f),x0           ; and g read NEGATIVE; the others sat at
        add     x0,a                    ; 0.88-0.97, where an allpass is a
        move    x:(r7+$6d),x0           ; g, for every allpass -- glided, 1/64
        sub     x0,a                    ; per block (1/8 until 26 Sep 2026:
        asr     #$6,a,a                 ; a jump stepped the allpasses,
        add     x0,a                    ; tools/verify/verify_knob_clicks.py)
        move    a,x:(r7+$6d)

; ---- SHMR: page-1 slot 3 ------------------------------------------------
        move    x:(r6+$3),a
        and     #>$7f0000,a             ; knob field, value<<16
        move    a1,x0                   ; SCALED TO A QUARTER. The raw knob is a
        move    #$60,y1                 ; loop gain on TOP of the tank's own
        mpy     x0,y1,a                 ; feedback, and by ear 25/127 raw (0.20)
        move    x:(r7+$0e),x0           ; is the sweet spot while 45 at TIME=90
        sub     x0,a                    ; (glided per block, 20 Sep 2026)
        asr     #$3,a,a
        add     x0,a
        move    a,x:(r7+$0e)
                                        ; already runs away. A quarter puts that
                                        ; sweet spot near the top of the travel
                                        ; instead of a fifth of the way up.
; ---- the LFO increment: pinned at what RATE 40 gave (the knob went 15 Sep
; 2026); 8x what it would be per sample, because the LFO is stepped once per
; block.
        move    #$28,a                  ; 40 << 16
        move    a1,x0
        move    x0,a
        move    a,x0
        move    #$50,y1
        mpy     x0,y1,a
        asr     #$8,a,a                 ; Round 13: BASE RATE x8, ~2.2 Hz at a
                                        ; mode scale of 1.0. The pinned ~0.4 Hz
                                        ; rate could not spread a mode across
                                        ; FFT bins, and the surviving modes
                                        ; towered 50-65 dB over the diffuse
                                        ; tail -- THE metallic end-ring,
                                        ; measured (latetail probe). An earlier
                                        ; seasick 2.84 Hz was fast-DEEP; this
                                        ; is fast-SHALLOW: every mode's depth
                                        ; scale is set so vibrato stays under
                                        ; ~12 cents.
        add     #>$180,a                
        move    a,x1                    ; fold in MODE's LFO rate scale, which the
        move    x:(r7+$2f),y1           ; md_ block parked here. SPEED still spans
        mpy     x1,y1,a                 ; its full range inside each character, the
        move    a,x:(r7+$2f)            ; same shape as MOD depth and damping.

; (the RATE speed select on slot 11 went with the MOD knob, 15 Sep 2026:
; the LFO runs at 1x, the default it always had)

        move    x:(r6+$d),a             ; GATE: page-2 slot 9, $d's companion
        and     #>$7f00,a               ; field = val*256 samples as it stands
        tst     a
        beq     g_off                   ; GATE=0 -> ungated
        move    #>2048,x0
        add     x0,a                    ; 2048 + val*256
        bra     g_st
g_off:
        move    #>$7fffff,a
        move    a,x:(r7+$62)            ; GLVL: open now, not after an attack
        move    #$40,a                  ; ~4.19M samples ~= 95 s: never closes
        move    a,x:(r7+$30)            ; GCNT: never runs out at GATE=0
g_st:                                   ; (g_off falls through with a still
                                        ; $400000, so one load serves GCNT and
                                        ; GHOLD)
        move    a,x:(r7+$29)            ; GHOLD

; ---- EIGHT INDEPENDENT LFOs, one per tank line --------------------------

        move    x:(r7+$3e),a            ; line 0  (1.000x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #$7f,y1                    ; rate x0.992
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        and     #>$7fffff,a                  ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf3e
        move    x0,x:(r7+$3e)
lf3e:
        move    x0,a
        sub     #>$400000,a                
        abs     a                       ; triangle, 0 .. $400000
        move    a,x:(r7+$5a)            ; stash: the AP modulator below clobbers it
        move    a,x0
; ---- in-loop allpass modulation (Dattorro): FIXED depth, never zero ------
; A moving allpass in the feedback path smears the modes on every
; circulation (REVERB.md). Depth is fixed at $200000 so it can never reach
; zero: a completely static tank rings.
        move    #$20,y1
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$52)            ; AP integer offset, 0..~31 samples
        move    x1,a
        and     #>$00ffff,a                
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
        and     #>$00ffff,a                
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
        move    x0,x:(r7+$22)           ; interpolation fraction

        move    x:(r7+$4f),a            ; line 1  (1.168x) phase
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    #>$6cc000,y1               ; rate x0.850
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        add     x0,a
        and     #>$7fffff,a                  ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lf4f
        move    x0,x:(r7+$4f)
lf4f:
        move    x0,a
        sub     #>$400000,a                
        abs     a                       ; triangle, 0 .. $400000
        move    a,x:(r7+$5b)            ; stash: the AP modulator below clobbers it
        move    a,x0
; ---- in-loop allpass B modulation, as A above -----------------------------
        move    #$20,y1
        mpy     x0,y1,a
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+$54)            ; AP integer offset, 0..~31 samples
        move    x1,a
        and     #>$00ffff,a                
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
        and     #>$00ffff,a                
        asl     #$7,a,a                 ; n-1: n=8 for the integer part above and
        move    a,x0                    ; the mask is 2^(24-8)-1, so the fraction
        move    x0,x:(r7+$24)           ; interpolation fraction

; ---- LFO lines 2-7: ROLLED --------------------------------
        move    n7,a
        move    a,x:(r7+$15)            ; stash the sample count
        move    #>$facade,r5            ; LFOTAB -- rewritten by build_bus.py
        move    #>$ffffff,m5            ; r5 walks the table linearly
        do      #6,>lfrol
        move    p:(r5)+,y1              ; this line's rate constant
        move    x:(r7+$2f),x0           ; base increment, from RATE
        move    p:(r5)+,n7              ; phase slot -- hoisted 2 above its use
        mpy     x0,y1,b                 ; this line's own rate
        move    b1,x0
        move    x:(r7+n7),a             ; phase
        add     x0,a
        and     #>$7fffff,a                  ; wrap
        move    a1,x0                   ; extract without saturating on A2
        move    x:(r7+$14),b            ; call flag: advance once per block,
        tst     b                       ; but USE the advanced value on both
        beq     lfrsk
        move    x0,x:(r7+n7)
lfrsk:
        move    x0,a
        sub     #>$400000,a                
        abs     a                       ; triangle, 0 .. $400000
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    p:(r5)+,n7              ; integer slot -- hoisted 3 above use
        move    a1,x1
        asl     #$8,a,a
        move    a2,x0
        move    x0,x:(r7+n7)
        move    p:(r5)+,n7              ; fraction slot -- hoisted 5 above use
        move    x1,a
        and     #>$00ffff,a                
        asl     #$7,a,a                 ; n-1, never n (REVERB.md's rule)
        move    a,x0
        move    x0,x:(r7+n7)
lfrol:
        move    x:(r7+$15),a            ; restore the sample count
        move    a,n7
; RESTORE m5 = $fff. This block sits between the line-modulo set (the
; "LINE modulo, 4096" store above the TIME section) and the lines 4-7
; priming, whose y:(r5+n5) seed reads MUST wrap inside a 4096-word line --
; that section's own comment says so. Leaving m5 linear here sent the
; priming's seed reads past Y:0xC000 on any block whose phase+offset
; crossed a line end: the seeds read zeros, every line's tail detuned by a
; hair, and the render was off by LSBs that grew with recirculation. Found
; by instruction-level trace against the unrolled engine after
; THREE state-comparison passes (X, Y, registers) all came back identical
; at block boundaries -- the divergence lived entirely inside the block.
        move    #>$fff,m5               ; the priming's wrap, put back

; ---- in-loop allpass setup ------------------------------------------------
; Dattorro puts a MODULATED allpass inside each tank half, before the long
; delay -- not in the input diffusion chain (that placement measured
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
        move    #>214,a
        move    a,x:(r7+$60)            ; 512 - 298    (9.7% of the longest line)
        move    #>66,a
        move    a,x:(r7+$61)            ; 512 - 446    (14.5%)

; ---- STAGE 2: read offsets for the four modulo-indexed line reads -------
        move    #4,n6                   ; w2 -> the NEXT line's w0 (short:
                                        ; an address register, zero-extended)
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
; the allpasses did not have until later.
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
; amortised, against the measured spare (make cycles) -- and needs no extra N register, which
; is what the in-loop comment ("no other way to do this") ruled out. That
; was true per SAMPLE; it is not true once per block.
        move    x:(r7+$60),a            ; allpass A: (512 - tap) - offset - 1
        move    x:(r7+$52),x0
        sub     x0,a
        sub     #>$1,a                
        move    a,n5
        move    #>$1ff,m5               ; the in-loop allpasses are 512
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
        sub     #>$1,a                
        move    a,n5
        move    r1,a
        and     #>$1ff,a
        move    x:(r7+$5f),x0           ; base B
        add     x0,a
        move    a,r5
        move    x:(r7+$5c),b            ; spaces the r5 write
        move    y:(r5+n5),a
        move    a,x:(r7+$5d)
        move    #>$7ff,m5               ; back to the diffusers' 2048
        move    x:(r7+$6a),n2           ; this call's AUX write address and
        move    x:(r7+$63),n3           ; read address: the loop walks them
                                        ; through n2/n3 (free: the priming's
                                        ; use of n2/n3 is over)

        do      n7,>rvend

; ---- input: mono sum, plus the shared REVERB bus accumulator (BUS.md) ----
        move    x:(r0)+,a               ; L
        move    x:(r0)-,x0              ; R, and r0 back on L (m0 linear)
        add     x0,a
        asr     #$1,a,a
; The host's own sends: dry mono x DEL into the delay's AUX accumulator, and
; dry mono x REV (the knob's copy at y:$09f0: r6 walks the state table in
; this loop) into this call's REV ACC slot, each with the writers' 3-bit
; headroom; the REV bus is read back three blocks on through the auto-gain,
; so the host is one client among N. mpy x1,y1 is the mpysu-encoded order:
; safe because y1 = REV >= 0. The pointers advance
; through r5's post-increment under m5 = $7ff: the accumulators sit inside
; one 2048-aligned block, so the modulo never wraps there.
        move    a,x1
; DEL: the dry x the ramped DEL level into the delay's aux
        move    y:>$09f4,a              ; DEL, ramped per sample
        move    y:>$09f5,y1             ; + this block's step
        add     y1,a
        move    a,y:>$09f4
        move    a,y1
        move    x1,x0
        mpy     x0,y1,a                 ; dry x DEL: x0 signed, y1 >= 0
        asr     #$3,a,a                 ; 3 bits of bus headroom
        move    y:>$09f6,b              ; the AUX write pointer
        move    b1,r5
        move    y:>$09f0,y1             ; REV level (spaces the r5 use)
        move    y:(r5),b
        add     b,a
        move    a,y:(r5)+               ; AUX ACC[write][i] += contribution
        move    r5,b
        move    b,y:>$09f6
        mpy     x1,y1,a
        asr     #$3,a,a                 ; 3 bits of bus headroom
        move    n2,r5                   ; this call's REV write address
        move    y:(r5),b
        add     b,a
        move    a,y:(r5)+               ; REV ACC[write][i] += contribution
        move    r5,n2                   ; advanced one sample
        move    n3,r5                   ; this sample's REV read address
        move    x:(r7+$0c),y1           ; auto-gain 1/sqrt(N) (spaces the r5
                                        ; write)
        move    y:(r5)+,x1              ; the fully-summed REV sends three
        move    r5,n3                   ; blocks back, the pointer advanced
                                        ; (m5 = $7ff: the accumulators and the
                                        ; chain sit inside one 2048-aligned
                                        ; block, no wrap)
        mpy     x1,y1,a
        move    x:(r7+$64),r5           ; this sample's chain read address
        move    x:(r7+$65),y1           ; 1/8 while the delay is live, else 0
                                        ; (spaces the r5 write)
        move    y:(r5)+,x0              ; the repeats x DLY, three blocks back
        move    r5,x:(r7+$64)
        mac     x0,y1,a                 ; the signed order (x1,y1 encodes macsu)
        asl     #$3,a,a                 ; undo the writers' 3-bit headroom
        move    a,y1                    ; the averaged input, feeding the tank:
                                        ; the chain word, held in y1 through
                                        ; the four diffusers

        move    x:(r7+$30),a            ; GCNT
        sub     #>$1,a                  ; GCNT - 1  (sets N)
        move    #0,x0
        tmi     x0,a                    ; if < 0, floor to 0
        move    a,x1                    ; counted-down candidate
; B. retrigger: if |input| >= threshold, GCNT := GHOLD (else the countdown).
;    A `move` does not touch the condition codes, so the sub's N reaches tmi.
        move    y1,a                    ; full tank input (bus/send too)
        abs     a
        move    #>$008000,x0            ; threshold ~0.004 (-48 dBFS). WAS
        sub     x0,a                    ; N = 0 (plus) when triggered
        move    x:(r7+$29),a            ; GHOLD
        tmi     x1,a                    ; NOT triggered -> counted-down
        move    a,x:(r7+$30)            ; GCNT
; C. target = FULL if GCNT > 0 else 0:
        tst     a                       ; Z = (GCNT == 0)
        move    #>$7fffff,a             ; FULL
        move    #0,x0
        teq     x0,a                    ; GCNT == 0 -> target 0
; D. one-pole smooth toward target -- the slam ramp:
        move    x:(r7+$62),b            ; GLVL
        sub     b,a                     ; delta = target - GLVL  (N=1 if closing)
        move    a,x0                    ; delta
        move    #$02,a                  ; ATTACK coeff ~1.4 ms -- fast, keeps the
        move    #>$002500,x1            ; bloom's punch; RELEASE coeff ~20 ms
        tmi     x1,a                    ; delta<0 (closing) -> ease with release
        move    a,y0                    ; the moves above don't touch N, so tmi
        mpy     y0,x0,a                 ; sees the sub's flag. coeff * delta
        add     b,a
        move    a,x:(r7+$62)            ; GLVL += coeff*(target - GLVL)

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
        move    a,n0                    ; the phase, held in n0 for the loop

; The four diffusers sit 2048 words apart ($32..$35 = shared+0x2000 +
; 0x800 k), so allpasses 1-3 address from allpass 0's r5 + 0x800 each:
; apbody leaves r5 where it found it.
        move    x:(r7+$7e),n5        ; this MODE's allpass 0
        move    n0,a                    ; phase   (also spaces the n5 write)
        move    x:(r7+$32),x0            ; base
        add     x0,a
        move    a,r5                    ; = write address
        move    x:(r7+$6d),y0           ; g, from DIFFUSION; held across all
                                        ; four input allpasses
        bsr     apbody                  ; the rolled allpass body: reads $1b,
                                        ; writes $1b and y:(r5)

        move    x:(r7+$7f),n5        ; this MODE's allpass 1
        move    r5,a
        add     #>$800,a
        move    a,r5                    ; = write address
        bsr     apbody

        move    x:(r7+$80),n5        ; this MODE's allpass 2
        move    r5,a
        add     #>$800,a
        move    a,r5                    ; = write address
        bsr     apbody

        move    x:(r7+$81),n5        ; this MODE's allpass 3
        move    r5,a
        add     #>$800,a
        move    a,r5                    ; = write address
        bsr     apbody

; ---- BLOOM ALLPASSES ------------------------------------------
        move    x:(r7+$5e),a            ; in-loop AP A base = shared+0x4000
        add     #>$800,a                  ; -> shared+0x4800  (bloom AP a)
        move    a,x0
        move    n0,a                    ; phase mod 2048
        add     x0,a
        move    a,r5
        move    #247,n5                 ; 2048 - 1801 (41 ms; SHORT immediate,
                                        ; zero-extended in an address register)
        move    x:(r7+$7b),y0           ; g, both bloom APs: 0.40 .. 0.86 with
        move    y:(r5+n5),b             ; d
        move    b,x0
        mpy     x0,y0,a
        add     y1,a                    ; v = x + g*d (y1 = the chain out)
        move    a,x0                    ; x0 = v, limited as the store was
        mpy     x0,y0,a
        sub     a,b                     ; out = d - g*v
        move    x0,y:(r5)               ; write v (AP a)
        move    b,x1                    ; AP a out -> AP b in
        move    r5,a                    ; base_a + phase, still intact ...
        add     #>$800,a                  ; ... + 0x800 = base_b + phase
        move    a,r5
        move    #>757,n5                ; 2048 - 1291 (29 ms)
        move    y:(r5+n5),b             ; d
        move    b,x0
        mpy     x0,y0,a
        move    x1,x0
        add     x0,a                    ; v = x + g*d
        move    a,x0                    ; x0 = v, limited as the store was
        mpy     x0,y0,a
        sub     a,b                     ; out = d - g*v
        move    b,x:(r7+$08)            ; -> the bloom component, for the sums
        move    x0,y:(r5)               ; write v (AP b)

        move    y1,a                    ; the diffused chain
; ---- TANK INPUT ATTENUATION: -12 dB of headroom -------------------------
        asr     #$2,a,a                 ; -12 dB
        move    a,x:(r7+$15)            ; diffused input -> tank
; ---- STAGE 3b: coefficients held in registers across all eight lines ----
; y0 = DAMP and x1 = the LO coefficient. Neither is clobbered between here
; and the write-back: the line reads use y1, the damping uses y0, the LO
; uses x1. Both were being re-fetched once per line. The allpasses above do
; use y0 and x1, which is why this sits after them.
        move    x:(r7+$1f),y0           ; DAMP, for all eight lines
        move    x:(r7+$40),x1           ; LO coefficient, for all eight lines

; ---- the tank's eight taps, damped and low-cut inside the feedback path --
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

; ---- collect the LINES outputs for the Hadamard ---------------------------
; The tank loop leaves them in the state table at stride 6. Lines 0-3 go to
; $16..$19 and lines 4-7 to $3a..$3d, the two 4-word groups the 8x8 FWHT
; operates on in place; r4 (m4 = $fff) and r5 (m5 = $7ff) walk them, and
; both groups sit inside one aligned block of either modulo for every r7.
        move    #6,n6                   ; the table's stride (short: address
                                        ; register, zero-extended)
        move    r6,a                    ; the tank loop left r6 48 words past
        sub     #>43,a                  ; the table: back to line 0's output
        move    a,r6                    ; word (table + 5)
        move    #>$7ff,m5               ; back to the input diffusers' 2048
        lua     (r7+$16),r4             ; (these two space the r6 write)
        lua     (r7+$3a),r5
        move    y:(r6)+n6,a
        move    a,x:(r4)+               ; line 0
        move    y:(r6)+n6,a
        move    a,x:(r4)+               ; line 1
        move    y:(r6)+n6,a
        move    a,x:(r4)+               ; line 2
        move    y:(r6)+n6,a
        move    a,x:(r4)+               ; line 3
        move    y:(r6)+n6,a
        move    a,x:(r5)+               ; line 4
        move    y:(r6)+n6,a
        move    a,x:(r5)+               ; line 5
        move    y:(r6)+n6,a
        move    a,x:(r5)+               ; line 6
        move    y:(r6)+n6,a
        move    a,x:(r5)+               ; line 7

; ---- wet output: eight lines summed per channel -------------------------
; L = l0 - l1 + l2 + l3/2 + l4 - l5 + l6 + bloom/8; R = l0 + l1 - l2 + l4 +
; l5 - l6 + l7/2 + bloom/8 (l3/l7, the driven lines, split L/R keep the
; image wide; the bloom at 0.5x). 56-bit sums, so the order is free.
        lua     (r7+$16),r4
        lua     (r7+$3a),r5
        move    x:(r7+$08),b            ; the bloom, pre-filter
        asr     #$3,b,b
        move    x:(r4)+,a               ; line 0
        add     b,a
        move    x:(r4)+,x0              ; line 1
        sub     x0,a
        move    x:(r4)+,x0              ; line 2
        add     x0,a
        move    x:(r4)+,b               ; line 3 (driven)
        asr     #$1,b,b
        add     b,a
        move    x:(r5)+,x0              ; line 4
        add     x0,a
        move    x:(r5)+,x0              ; line 5
        sub     x0,a
        move    x:(r5)+,x0              ; line 6
        add     x0,a
        move    a,x:(r7+$2d)            ; wet L
        lua     (r7+$16),r4
        lua     (r7+$3a),r5
        move    x:(r7+$08),b            ; the bloom again
        asr     #$3,b,b
        move    x:(r4)+,a               ; line 0
        add     b,a
        move    x:(r4)+,x0              ; line 1
        add     x0,a
        move    x:(r4)+,x0              ; line 2
        sub     x0,a
        move    x:(r5)+,x0              ; line 4
        add     x0,a
        move    x:(r5)+,x0              ; line 5
        add     x0,a
        move    x:(r5)+,x0              ; line 6
        sub     x0,a
        move    x:(r5)+,b               ; line 7 (driven), R side
        asr     #$1,b,b
        add     b,a
        move    a,x:(r7+$2e)            ; wet R

; ---- 8x8 Fast Walsh-Hadamard Transform, in place ---------------------------
; Stage 1 pairs neighbours (r4 reads, r5 writes one pair behind); stage 2
; pairs (0,2)/(1,3) with the four values in registers; stage 3 pairs the
; groups (r4/r6 on $16.., r5 on $3a..). A register park limits exactly as
; the stores it replaces.
        lua     (r7+$16),r4
        lua     (r7+$16),r5
        move    x:(r4)+,a               ; d0
        move    x:(r4)+,x0              ; d1
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r5)+               ; u0 = d0+d1
        move    b,x:(r5)+               ; u1 = d0-d1
        move    x:(r4)+,a               ; d2
        move    x:(r4)+,x0              ; d3
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r5)+               ; u2 = d2+d3
        move    b,x:(r5)+               ; u3 = d2-d3

        lua     (r7+$3a),r4
        lua     (r7+$3a),r5
        move    x:(r4)+,a               ; d4
        move    x:(r4)+,x0              ; d5
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r5)+               ; u4 = d4+d5
        move    b,x:(r5)+               ; u5 = d4-d5
        move    x:(r4)+,a               ; d6
        move    x:(r4)+,x0              ; d7
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r5)+               ; u6 = d6+d7
        move    b,x:(r5)+               ; u7 = d6-d7

        lua     (r7+$16),r4
        lua     (r7+$16),r5
        move    x:(r4)+,x0              ; u0
        move    x:(r4)+,x1              ; u1
        move    x:(r4)+,a               ; u2
        move    a,b
        add     x0,a                    ; u0+u2
        neg     b
        add     x0,b                    ; u0-u2
        move    a,x:(r5)+               ; u0' = u0+u2
        move    b,y0                    ; u2' = u0-u2, parked
        move    x:(r4)+,a               ; u3
        move    a,b
        add     x1,a                    ; u1+u3
        neg     b
        add     x1,b                    ; u1-u3
        move    a,x:(r5)+               ; u1' = u1+u3
        move    y0,x:(r5)+              ; u2'
        move    b,x:(r5)+               ; u3' = u1-u3

        lua     (r7+$3a),r4
        lua     (r7+$3a),r5
        move    x:(r4)+,x0              ; u4
        move    x:(r4)+,x1              ; u5
        move    x:(r4)+,a               ; u6
        move    a,b
        add     x0,a
        neg     b
        add     x0,b
        move    a,x:(r5)+               ; u4' = u4+u6
        move    b,y0                    ; u6' = u4-u6, parked
        move    x:(r4)+,a               ; u7
        move    a,b
        add     x1,a
        neg     b
        add     x1,b
        move    a,x:(r5)+               ; u5' = u5+u7
        move    y0,x:(r5)+              ; u6'
        move    b,x:(r5)+               ; u7' = u5-u7

        lua     (r7+$16),r4
        lua     (r7+$3a),r5
        lua     (r7+$16),r6
        move    x:(r4)+,a               ; u0
        move    x:(r5),x0               ; u4
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r6)+               ; u0' = u0+u4
        move    b,x:(r5)+               ; u4' = u0-u4
        move    x:(r4)+,a               ; u1
        move    x:(r5),x0               ; u5
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r6)+               ; u1' = u1+u5
        move    b,x:(r5)+               ; u5' = u1-u5
        move    x:(r4)+,a               ; u2
        move    x:(r5),x0               ; u6
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r6)+               ; u2' = u2+u6
        move    b,x:(r5)+               ; u6' = u2-u6
        move    x:(r4)+,a               ; u3
        move    x:(r5),x0               ; u7
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r6)+               ; u3' = u3+u7
        move    b,x:(r5)+               ; u7' = u3-u7

; ⚠️ The marker below said "excised unless SHIMMER=1" until 30 Aug 2026.
; Both halves were wrong: the shimmer is IN by default, build_bus.py
; excises it only when NOSHIM=1, and there is no SHIMMER flag. That exact
; belief polluted every measured voicing round up to Round 12.
; ⚠️ Do not add lines between SHIMMER_BEGIN and SHIMMER_END without
; expecting the NOSHIM build report to change -- it prints the line count.
; SHIMMER_BEGIN
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
; TRAP (AGENTS.md): `cmp a,b` has silently encoded as `max a,b`, which updates
; only C while bge tests N^V. No cmp here at all -- the two comparisons are
; done as `sub` + branch, which sets N and V properly. Every mpy is x0,y1 or
; x1,x0 (signed) except head 1's frac multiply, an audited mpysu (y0 >= 0).
;
; STATE: r7+$0e SHMR (glided per block), r7+$0f phase mod 4096, r7+$4e
; one-pole, y:$0905 read phase, y:$0906 HP state.
; BUFFER: shared+0x0800, 2048 words, 2048-aligned so the AGU wraps it free.

        move    x:(r7+$5e),a            ; in-loop allpass A base = shared+0x4000,
        sub     #>$3800,a                  ; the shimmer buffer at shared+0x0800,
        move    a,r5                    ; 2048-ALIGNED, as the AGU wrap requires
                                        ; (m5 = $7ff). Derived from
                                        ; $5e because the r7 block has no slot
                                        ; to cache it, and still the only reason
                                        ; the two are placed 0x3800 apart.

        move    x:(r7+$0f),a            ; phase, mod 4096 = 2N. May be GARBAGE
        add     #>$1,a                  ; it, which is why no init is needed ; on the first call -- the mask cleans
        and     #>$fff,a                  ; from the phase rather than kept as a ; and why every address here is DERIVED
        move    a1,x1                   ; walking pointer (AND cleans A1 only;
        move    x1,x:(r7+$0f)           ; x1 is 24-bit so this IS the value)

; ---- one-pole, then the decimated write ---------------------------------
; c = 0.35 -> corner ~2.7 kHz. It sits BEFORE the shift, so it lands ~5.4 kHz
; on the way out, and below the SR/4 the decimation folds about: this is the
; anti-alias filter and the shimmer path's HF rolloff doing one job twice.
        move    x:(r7+$08),a            ; BLOOM BRANCH (R18): single-octave feed.
        asr     #$2,a,a                 ; -12 dB: $08 is raw chain scale, 4x
                                        ; hotter than $15 (see the bloom-sum
                                        ; >>3), so SHMR's range is unchanged
        move    y:>$0906,x0             ; HP state s
        sub     x0,a                    ; x - s
        move    a,x0                    ; the HP output, held in x0 across
                                        ; the state update (no $14 park)
        move    #$05,y1                 ; c ~0.039 -> corner ~280 Hz (Sam,
        mpy     x0,y1,a                 ; c*(x - s)   [audited-signed x0,y1]
        move    y:>$0906,b
        add     b,a                     ; s' = s + c*(x - s)
        move    a,y:>$0906
        move    x0,a                    ; HP output feeds the LP below
        move    x:(r7+$4e),b            ; previous filter output
        sub     b,a
        move    a,x0
        move    #>$399999,y1            ; c = 0.45 (R18; was 0.35). Corner ~4.2k
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

; ---- READ PHASE: the heads' own fractional phase, stepped by SHFT ---------
        move    y:>$0905,a              ; read phase
        move    x:(r7+$2c),x0           ; STEP
        add     x0,a
        and     #>$7fffff,a             ; wrap (2048 words)
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,y:>$0905
        move    a,x1                    ; parked for the int/frac splits below
; frac_total = wobble frac + read-phase frac, carry out:
        move    x:(r7+$21),a           ; line-0 LFO offset (x MOD depth)
        and     #>$3,a                  ; sub-word bits of the sample offset
        asl     #$15,a,a               ; ($21 & 3) << 21 = x0.25 in Q23
        move    x:(r7+$22),b           ; the paired interpolation fraction
        asr     #$2,b,b                ; samples -> words
        add     b,a                    ; wobble frac (<= $7fffff, no carry)
        move    a,b                    ; park it (< 1: the move cannot limit)
        move    x1,a                   ; read phase (a2 = 0: wrapped above)
        and     #>$fff,a               ; its frac field
        asl     #$b,a,a                ; -> Q23
        add     b,a                    ; frac sum; a1 bit 23 = the carry
        move    a1,x0                  ; raw sum, unlimited
        and     #>$7fffff,a            ; frac_total (a2 still 0)
        move    a,x:(r7+$38)           ; frac for both heads' lerped reads
; integer read position = read words + wobble words + carry:
        move    x0,a                   ; raw sum, sign-extended
        asr     #$17,a,a               ; carry -> 0 or -1 (sign-extended)
        neg     a                      ; -> 0 or +1
        move    x:(r7+$21),b
        asr     #$2,b,b                ; wobble integer words, 0..31
        add     b,a
        move    a1,x0
        move    x1,a                   ; read phase again
        asr     #$c,a,a                ; integer words, 0..2047
        add     x0,a
        move    a1,x1                  ; read position for both head reads
                                       ; (heads mask $7ff, exactly as before)

; ---- head 0: pos = phase & $7ff, age = (write - pos) & $7ff -------------
        move    x1,a
        and     #>$7ff,a                
        move    a1,n5                   ; n5 = pos0, held across the gain
        move    a1,x0
        move    y0,a                    ; write index
        sub     x0,a                    ; write - pos0, may go negative
        and     #>$7ff,a                  ; age0 (AND of the two's complement low
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
        asl     #$f,a,a                 ; g = t/256 in Q23 (linear ramp)
        move    a,x0                    ; g
        move    a,y1                    ; g
        mpy     x0,y1,a                 ; g^2  (mpy x0,y1 = signed)
        move    a,b                     ; park g^2 (x1 is the read position)
        move    #>$7fffff,a
        sub     x0,a                    ; 1 - g
        move    a,y1                    ; 1 - g
        move    b,x0                    ; g^2
        mpy     x0,y1,a                 ; g^2*(1-g)
        asl     #$1,a,a                 ; 2*g^2*(1-g)
        add     x0,a                    ; s = g^2 + 2*g^2*(1-g)
shd0:
        move    a1,b                    ; park g0
        move    y:(r5+n5),a             ; t0
        move    a,x:(r7+$14)
        move    n5,a
        move    #>1,x0
        add     x0,a
        and     #>$7ff,a                  ; pos0 + 1, wrapped
        move    a1,n5
        move    y:(r5+n5),a             ; t1
        move    x:(r7+$14),x0
        sub     x0,a                    ; t1 - t0
        move    a1,x0
        move    x:(r7+$38),y1           ; frac
        mpy     x0,y1,a                 ; frac*(t1-t0)  (signed x frac)
        move    x:(r7+$14),x0
        add     x0,a                    ; interpolated tap 0
        move    a1,x0
        move    b,y1                    ; g0 back
        mpy     x0,y1,a
        move    a,b                     ; b = head 0's contribution

; ---- head 1: half a buffer on, so its age runs 1024 behind head 0's -----
        move    x1,a
        move    #>1024,x0
        add     x0,a
        and     #>$7ff,a                  ; MASKED -- a modulo offset larger than
        move    a1,n5                   ; the buffer is undefined (REVERB.md)
        move    a1,x0
        move    y0,a
        sub     x0,a
        and     #>$7ff,a                  ; age1
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
        asl     #$f,a,a                 ; g = t/256 in Q23 (linear ramp)
; SMOOTHSTEP, same as head 0
        move    a,x0                    ; g
        move    a,y1                    ; g
        mpy     x0,y1,a                 ; g^2
        move    a,x1                    ; save g^2
        move    #>$7fffff,a
        sub     x0,a                    ; 1 - g
        move    a,y1                    ; 1 - g
        move    x1,x0                   ; g^2
        mpy     x0,y1,a                 ; g^2*(1-g)
        asl     #$1,a,a                 ; 2*g^2*(1-g)
        add     x1,a                    ; s = g^2 + 2*g^2*(1-g)
shd1:
        move    y:(r5+n5),a             ; t0
        move    a,x1                    ; parked (x1 is free from here on)
        move    n5,a
        move    #>1,x0
        add     x0,a
        and     #>$7ff,a                  ; pos1 + 1, wrapped
        move    a1,n5
        move    y:(r5+n5),a             ; t1
        sub     x1,a                    ; t1 - t0
        move    a1,x0
        move    x:(r7+$38),y0           ; frac (write index in y0 is dead now)
        mpy     x0,y0,a                 ; frac*(t1-t0) -- mpysu, y0 >= 0: safe
        add     x1,a                    ; interpolated tap 1
        move    a1,x0
        mpy     x0,y1,a                 ; g1 * tap
        add     b,a                     ; the octave-up signal, g0+g1 ~= 1

; ---- back into the tank input -------------------------------------------
        move    a1,x1
        move    x:(r7+$0e),x0           ; SHMR (glided per block; r6 walks the
        mpy     x1,x0,a                 ; state table in this loop, so the knob
        move    x:(r7+$15),x0           ; is never read here)
        add     x0,a
        move    a,x:(r7+$15)            ; tank input, with the octave folded in
; SHIMMER_END

; ---- feedback and write back (ROLLED, 8-line) ----------------------------

        move    x:(r7+$0d),a            ; table B base
        move    a,r6

; -- Step 1a: rolled feedback, group A (u[0..3] at $16..$19) --------------
; r4 walks u[0..3] (post-increment), r5 walks scratch[0..3] ($1a..$1d).
; r6 already walks table B (weight + gain, 2 words per line). The tank input
; sits in y1 across both groups: nothing in either body writes y1.
        lua     (r7+$16),r4             ; r4 -> u0
        lua     (r7+$1a),r5             ; r5 -> scratch0
        move    x:(r7+$15),y1           ; input, also spaces the r5 write
        nop
        do      #4,>fbA
        move    y:(r6)+,x0             ; weight[k]
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
        lua     (r7+$3a),r4             ; r4 -> u4
        nop                             ; spaces the r4 write
        lua     (r4+$7),r5              ; r5 -> scratch4 = r7+$41, past
                                        ; lua's 7-bit displacement
        nop                             ; r5 is first read ten
                                        ; instructions into the loop
        do      #4,>fbB
        move    y:(r6)+,x0             ; weight[k]
        mpy     x0,y1,b                ; input * weight[k] (y1 from group A)
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
        move    n0,a                    ; phase (masked to $7ff above)
        and     #>$1ff,a                ; ...but these buffers are 512. A2 is
                                        ; already 0 (the phase loads positive),
                                        ; so no A2-clean dance is needed here.
        move    x:(r7+$5e),x0
        add     x0,a
        move    a,r5                    ; = write address
        move    x:(r7+$6d),y0           ; g, held in y0 across both lines
        move    y:(r5+n5),b             ; d0
; Interpolate against the PREVIOUS sample's d0.
        move    x:(r7+$5c),a            ; d1 = last sample's d0
        move    b,x:(r7+$5c)            ; carry forward
        sub     b,a                     ; d1 - d0
        move    a,x0
        move    x:(r7+$53),y1           ; fraction
        mpy     x0,y1,a                 ; f*(d1-d0)
        add     b,a                     ; + d0 -> interpolated tap
        move    a,b
        move    b,x0
        mpy     y0,x0,a                 ; g*d, signed (y0,x0)
        move    x1,x0
        add     x0,a                    ; v = x + g*d
        move    a,x0                    ; x0 = v, limited as the store was
        mpy     y0,x0,a                 ; g*v
        sub     a,b                     ; out = d - g*v
        move    x0,y:(r5)               ; store v
        move    b,a                     ; out -> the line
        move    a,y:(r1)             ; write at the line's own modulo pointer

; -- Step 3: in-loop allpass, line 1 --
        move    x:(r7+$1b),a            ; fb1 from scratch
        move    a,x1                    ; x = the value bound for the line
        move    x:(r7+$61),a
        move    x:(r7+$54),x0           ; LFO integer offset -- the allpass is
        sub     x0,a                    ; MODULATED now, not static
        move    a,n5                    ; (512 - tap) - offset
        move    n0,a                    ; phase (masked to $7ff above)
        and     #>$1ff,a                ; ...but these buffers are 512
        move    x:(r7+$5f),x0
        add     x0,a
        move    a,r5                    ; = write address
        move    y:(r5+n5),b             ; d0
        move    x:(r7+$5d),a            ; d1 = last sample's d0
        move    b,x:(r7+$5d)            ; carry forward
        sub     b,a                     ; d1 - d0
        move    a,x0
        move    x:(r7+$55),y1           ; fraction
        mpy     x0,y1,a                 ; f*(d1-d0)
        add     b,a                     ; + d0 -> interpolated tap
        move    a,b
        move    b,x0
        mpy     y0,x0,a                 ; g*d (y0 = g from line 0)
        move    x1,x0
        add     x0,a                    ; v = x + g*d
        move    a,x0                    ; x0 = v, limited as the store was
        mpy     y0,x0,a                 ; g*v
        sub     a,b                     ; out = d - g*v
        move    x0,y:(r5)               ; store v
        move    #>$7ff,m5               ; back to the input diffusers' 2048
        move    b,a                     ; out -> the line
        move    a,y:(r2)             ; write at the line's own modulo pointer

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

; ---- WIDTH: mid/side, then the wet high-cut, WET, then onto the dry ------
; M = (L+R)/2, S = (L-R)/2, out = M +/- w*S. The width w is pinned at 0.75
; (the knob is SHFT; $2c carries its step). M, w*S and their high-cut
; values live in y1/x1 (a register move limits exactly as the parked store
; did); the wet gain sits in b and is moved into y0 per channel.
        move    x:(r7+$2d),a
        move    x:(r7+$2e),x0
        add     x0,a
        asr     #$1,a,a
        move    a,y1                    ; M
        move    x:(r7+$2d),a
        sub     x0,a
        asr     #$1,a,a
        move    a,x0
        move    #$60,y0                 ; w = 0.75
        mpy     x0,y0,a
        move    a,x1                    ; w*S

; ---- wet high-cut --------------------------------------------
        move    y1,a                    ; M
        move    x:(r7+$78),b            ; high-cut state, M channel
        sub     b,a
        move    a,x0
        move    x:(r7+$7a),y0           ; per-mode wet high-cut coefficient
        mpy     x0,y0,a                 ; c*(x - y)
        add     b,a                     ; y += c*(x - y)
        move    a,x:(r7+$78)
        move    a,y1                    ; M, high-cut
        move    x1,a                    ; w*S
        move    x:(r7+$79),b            ; state, S channel
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$79)
        move    a,x1                    ; w*S, high-cut
        move    x:(r7+$20),b            ; wet gain (wgain/2)

; ---- L = M + w*S, R = M - w*S, each * wgain * GLVL * WET * 2, + dry -----
        move    y1,a
        add     x1,a
        move    a,x0
        move    b,y0
        mpy     y0,x0,a                 ; * (wgain/2), signed (y0,x0)
        asl     #$1,a,a                 ; wet makeup: doubled in full precision
        move    a,x0                    ; GATE: scale the wet by the gate level
        move    x:(r7+$62),y0           ; GLVL (0..1)
        mpy     y0,x0,a                 ; signed (y0,x0): wet * gate
        move    a,x0                    ; gated wet L
; THE HOST PRINT: dry + wet*WET, in place. The chain input (the aux, or
; the delay's output while it is live) feeds the tank only; the dry the
; host hears is its own.
        move    x:(r7+$71),a            ; WET, ramped per sample: + this
        move    x:(r7+$7c),y0           ; block's step
        add     y0,a
        move    a,x:(r7+$71)
        move    a,y0
        mpy     y0,x0,a                 ; wet * WET
        asl     #$1,a,a                 ; x2: WET 127 = +6 dB (the stores
                                        ; below limit)
        move    x:(r0),x0               ; dry L, still in place
        add     x0,a                    ; + dry at unity
        move    a,x:(r0)+               ; L in place -- dry + wet; r0 on to R
        move    y1,a
        sub     x1,a
        move    a,x0
        move    b,y0
        mpy     y0,x0,a                 ; * (wgain/2)
        asl     #$1,a,a                 ; wet makeup, right channel
        move    a,x0                    ; GATE: same gate level on the right
        move    x:(r7+$62),y0           ; GLVL
        mpy     y0,x0,a                 ; wet * gate
        move    a,x0                    ; gated wet R
        move    x:(r7+$71),y0           ; WET, this sample's
        mpy     y0,x0,a                 ; wet * WET
        asl     #$1,a,a                 ; x2, as on L
        move    x:(r0),x0               ; dry R, still in place
        add     x0,a                    ; + dry at unity
        move    a,x:(r0)+               ; R in place -- dry + wet; r0 on to
                                        ; the next frame (n0 is not used)
        move    (r1)+                   ; the three line pointers advance
        move    (r2)+                   ; together and each wraps inside its
        move    (r3)+                   ; own line under m1..m3 = $fff (r4 is
                                        ; the feedback walker now, rebuilt by
                                        ; lua every sample)
rvend:

noloop:

; ---- save the phase, restore the M registers ---------------------------
        move    r1,a
        and     #>$fff,a                ; 4096-word lines (increment 2), so
                                        ; the phase is 0..4095 -- which is what
                                        ; m1 = $fff wraps it to anyway
        move    a,x:(r7+$83)
dry:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts

; ---- apbody: one input-diffuser allpass ------------------------------------
; In: r5 = write address, n5 = this allpass's tap (m5 = $7ff modulo held by
; the caller), y0 = g (held across all four calls), y1 = chain in.
; Out: y1 = chain out, v written at y:(r5). Clobbers a/b/x0/x1.
; The mpy x0,y0 encodes as mpysu: safe because the SECOND operand y0 = g is
; always positive.
apbody:
        nop                             ; spaces the caller's r5 write
        move    y:(r5+n5),b             ; d, at (phase - tap) mod 2048
        move    b,x0
        mpy     x0,y0,a
        add     y1,a                    ; v = x + g*d
        move    a,x1                    ; x1 = v (a register move limits
                                        ; exactly as a store does)
        mpy     x1,y0,a
        sub     a,b                     ; out = d - g*v
        move    x1,y:(r5)               ; write v at base + phase
        move    b,y1                    ; chain out
        rts

; ---- stampgr: a clear-on-read liveness stamp with 3 blocks of grace -------
; In: b = the grace counter as stored (masked here: core-private and r7
; words start as boot garbage), r5 -> the stamp word (m5 is irrelevant for a
; plain access). Out: b = the new counter -- 3 if the stamp was set this
; block, else the old one minus 1 floored at 0; the stamp is cleared. Used
; for the delay's chain-liveness stamp (and for RETV, the T8 return's,
; until 20 Sep 2026). Clobbers a and x0. Every select is a
; Tcc off the ONE flag-setting op above it, moves between.
stampgr:
        and     #>$3,b                  ; boot garbage masked ...
        move    b1,x0
        move    x0,b                    ; ... and B2 clean again (a logical op
                                        ; leaves it stale; AGENTS.md)
        move    #>$1,x0
        sub     x0,b
        move    #0,x0
        tmi     x0,b                    ; floored at 0
        move    y:(r5),a                ; the stamp
        move    x0,y:(r5)               ; clear-on-read (x0 is still 0)
        move    #>$3,x0
        tst     a
        tne     x0,b                    ; stamped this block: 3 blocks of grace
        rts
