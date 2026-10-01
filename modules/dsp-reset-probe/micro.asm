; DSP RESET PROBE, the DSP side -- seven words the ColdFire sends through the
; host port to ask "are you in your boot ROM?".
;
; This is NOT part of either payload. It is sent at run time, as the stock
; upload sends the bootstraps (FUN_40001d4c: a word count, a load address,
; that many words, then the ROM jumps to the address), and it only ever runs
; if the core is sitting in its HI08 boot ROM waiting for a program -- which
; is exactly what the probe is asking. A core running a payload has no boot
; ROM listening: the words go into its host receive register and nothing
; here executes, so no answer comes back. That asymmetry IS the measurement.
;
; The answer is a magic the host chose, with the core's number in its low
; bit (probe.s ORs it into the immediate before sending): a crossed core
; select cannot pass core 1's answer off as core 0's, and a stale word left
; in the receive register cannot pass as an answer at all.
;
; Every form has a stock site: the HTDE and HRDF waits are the stock
; bootstrap's own word pair (`brclr #n,x:<<$ffffc3,0` = 0cc30n 000000,
; P:$31004/$31007 of bootstrap A, read from the user's image with
; tools/build/dsp_disasm_all.py), `movep x0,x:<<$ffffc7` is HOTX the way
; bootstrap A echoes a record type (`movep a,x:<<M_HOTX`, 08ce07), and a
; register into x:qq is the payloads' form (dsp_park.asm). x0, not an
; accumulator: a store from `a` would run through the limiter with A2 stale
; (AGENTS.md), and a magic with bit 23 set would come back as $7fffff.
;
; The park at the end is the HRDF wait: the core waits for a word the host
; never sends. The probe puts the core back in its ROM by pulsing the
; candidate again before it re-runs the stock upload, so nothing here has
; to find its way home.
;
; tools/verify/verify_dspreset.py assembles this file and refuses the build
; if probe.s's seven longs are not what dsp_asm emits for it.
        brclr   #1,x:<<$ffffc3,0        ; wait for HTDE: the host transmit register is free
        move    #>$5a3c60,x0            ; the magic; the host ORs the core number in
        movep   x0,x:<<$ffffc7          ; HOTX: the answer
        brclr   #0,x:<<$ffffc3,0        ; park: wait for a word that never comes
