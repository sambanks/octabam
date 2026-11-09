; ---------------------------------------------------------------------------
; KEYBUS -- every track's key level, published each block for any reader on
; either core (CHARACTER's KEY T1..T8).
;
; One hook, at the dispatcher's per-track site `move x:>$208,r6` (payload A
; P:$4a7, payload B P:$29c), which every track on the core passes once a
; block with its input block in X:$00..$1f (16 frames, L then R) and its
; index in x:$420 (0..7: core A runs tracks 4-7, core B 0-3). The hook takes
; the peak of |(L + R) / 2| over the 16 frames and stores it, one word, at
; X:$37F60 + track, in the shared window: both cores see all eight words.
; Each word is wholly rewritten every block, so there is nothing to clear,
; no generation and no election; a reader on the other core sees the last
; block that core finished (or the one before, within one block).
;
; SIDECHAIN_COMPRESSOR's sctap hooks the same site. Where SC is loaded on
; demand, SC KEYBUS BRIDGE stands in for this hook there (schema.DspOverride):
; SC's resident stub runs sctap while SC is loaded, then jumps here.
;
; Registers: a, b, x0, r0, r1 and r6, the set stock reloads after this site
; (SIDECHAIN_COMPRESSOR's sctap audit); r6 is the displaced instruction's
; own. Forms: `max a,b` is stock's (payload A P:$1e8, encoding 20001d); the
; long-displacement store `move b,x:(r1+xxx)` is BusVerb's class (0a7_8e/8f).
; One copy serves both cores (no per-payload text): the window's P is shared.
; ---------------------------------------------------------------------------
kbus_tap:
        move    #0,r0                   ; the input block, X:$00
        clr     b                       ; the peak so far
        do      #<$10,>kbus_l1
        move    x:(r0)+,a               ; L
        move    x:(r0)+,x0              ; R
        add     x0,a
        asr     a                       ; (L + R) / 2
        abs     a
        max     a,b                     ; b = the larger
kbus_l1:
        move    x:>$420,r1              ; the track, 0..7
        move    b,x:(r1+$37f60)         ; the limiting store: this track's key word
        move    x:>$208,r6              ; --- displaced ---
        rts
