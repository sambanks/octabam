; ---------------------------------------------------------------------------
; TEMPO PROBE (TPROBE=1) -- stream stock's per-frame parameter staging block
; out as audio, so a hardware capture can tell us whether the ColdFire
; publishes anything TEMPO-shaped where the DSP can read it. (23 Aug 2026;
; Sam wants tempo sync, mostly for the delay -- the sequencer clock is
; ColdFire-side and nothing mapped so far carries BPM.)
;
; WHAT IT STREAMS. X:0x30000-0x30047: the 72 words stock's frame setup copies
; to y:0x1b8 and writes parameter values back into, EVERY FRAME (DSP.md
; section "Stock uses X:0x30000 as per-frame parameter staging"; disassembled
; do #<$48 loops at P:0x0a4/P:0x366). If the panel publishes tempo to the
; DSP at all, this staging block is the first place to look.
;
; FORMAT -- self-synchronizing, no frame markers, branch-free:
;   LEFT  = staging[idx], the raw 24-bit word as a sample
;   RIGHT = idx << 16, a 0..71 staircase that labels every left sample
; The decode aligns on the staircase, so block boundaries and capture trims
; are irrelevant. One full block streams every 72 samples (~613 Hz), far
; faster than any tempo change.
;
; PROCEDURE (one flash, needs the unit):
;   1. TPROBE=1 python3 tools/build_bus.py     (PLAIN build -- no XBUS: the
;      probe has no bus scratch and the XBUS relocation refuses a source
;      without any, and a probe needs no bus anyway)
;      make -o bus image BUILD=T1        (-o skips the bus rebuild: `make
;      bus` forces SPEC=1, which refuses probe builds)
;      The probe replaces BusVerb; flash as usual (docs/FLASHING.md).
;   2. Assign the probe to an FX2 slot on a track 5-8, capture its outputs
;      (MicroBook ch3/4 direct, docs/CAPTURE.md) for ~5 s at BPM 60.000.
;   3. Change ONLY the project tempo to 180.000, capture ~5 s again.
;   4. tools/decode_tempo_probe.py <60.wav> <180.wav>: aligns both on the
;      staircase, averages each of the 72 words, prints the ones that
;      CHANGED, with 60/180 values and the 180/60 ratio. A word whose ratio
;      is ~3.0 (or ~1/3) is a rate or period; decode from there.
;   5. Repeat at a third tempo if a candidate needs disambiguating.
; NOTHING LOCAL CAN ANSWER THIS: dsp_host never runs stock's frame setup, so
; the staging block is all zeros in the emulator (the decode script will say
; so -- that is the expected local result, not a probe failure).
;
; The $30000 below is payload A's staging base and this probe is only ever
; placed on payload A (the build wiring guards it); the blanket payload-B
; substitution would rewrite it to $38000, which is why the literal must be
; spelled exactly once, here.
; ---------------------------------------------------------------------------

init:
        move    #>0,x0
        move    x0,a
        move    a,x:(r7+$10)            ; idx = 0 (boot garbage here would
                                        ; read wild addresses)
        rts

proc:
        move    #>$1,n0
        do      n7,>tpend               ; n7 = frames, pre-set by the
                                        ; dispatcher (x:$20d,n7 before the
                                        ; jsr -- the same protocol every
                                        ; probe and server relies on)

        move    x:(r7+$10),a            ; idx, 0..71
        move    #>$30000,x0             ; staging base (payload A)
        add     x0,a
        move    a,r1
        move    x:(r1),a
        move    a,x:(r0)                ; LEFT = staging[idx]
        move    x:(r7+$10),a
        asl     #$10,a,a                ; idx << 16
        move    a,x:(r0+n0)             ; RIGHT = the index staircase
; idx = (idx + 1) mod 72, branch-free (branches in a do loop can hang the
; DSP): compute idx+1, subtract 72 to set Z on wrap, then Tcc-select --
; the moves between the sub and the teq do not disturb the condition codes.
        move    x:(r7+$10),a
        move    #>1,x0
        add     x0,a                    ; idx+1
        move    a,x1                    ; candidate, held through the test
        move    #>72,x0
        sub     x0,a                    ; Z set exactly at idx+1 == 72
        move    #>0,x0
        move    x1,a                    ; idx+1 back (flags untouched)
        teq     x0,a                    ; wrap -> 0
        move    a,x:(r7+$10)

        move    #>$2,n0
        move    (r0)+n0                 ; advance one stereo frame
        move    #>$1,n0
tpend:
        rts
