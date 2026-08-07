; ---- BURN PROBE 2 of 2: neutralise p3's audio effect --------------------
; p3 is the burn knob now, so its filter must stop moving -- otherwise every
; step of the sweep changes the timbre and "did it break" becomes a judgement
; about sound rather than about breakage. The comment above the coefficient
; block is what makes this exact rather than approximate: HP=0 gives
; coefficient 0, "the state never moves, nothing is subtracted, and the filter
; is bypassed exactly." So forcing the coefficient to 0 is the documented
; bypass, not an attenuation, and the probe's audio path is the shipping
; engine with LO off.
;
; THIS MUST LAND *AFTER* THE ENGINE'S OWN WRITE TO r7+$40, NOT BEFORE IT.
; dsp/burn_probe.asm (the fork this replaced) worked by REPLACING that write;
; an injection that lands before it is silently undone by the real coefficient
; on the very next line, and the burn knob goes on filtering. That is exactly
; what happened on the first cut of this splice, and tools/verify_burn.py's
; "inert at BURN=127" check is what caught it.
        clr     a
        move    a,x:(r7+$40)            ; LO coefficient forced to 0 (bypass)
