; ---------------------------------------------------------------------------
; The minimum possible effect in DARK REV's slot.
;
; Every hypothesis for the two-track hang so far has been about what our code
; DOES -- cycles, buffer bounds, the base stash, r7 slots, init fields. Two of
; those were real bugs and fixing them changed nothing, which means the guesses
; are not converging. This partitions the problem instead of guessing again.
;
; init writes nothing at all. proc reads no parameter, touches no Y memory, uses
; no r7 slot, reads X:$213 never, and just copies input to output -- the same
; five instructions as the stock null stub at P:0x7c8, which is known good.
;
;   two tracks HANG   -> nothing our DSP code does is responsible. The trigger
;                        is instantiating this module twice, and the fault is on
;                        the host side or in the module/descriptor, not in the
;                        algorithm. Everything measured so far is irrelevant.
;   two tracks RUN    -> the algorithm is implicated after all, and we add it
;                        back a stage at a time from a known-good floor.
;
; M registers are restored anyway: the stock stub does not, but it also never
; sets them, and we do not want a difference we cannot account for.
; ---------------------------------------------------------------------------

init:
        rts

proc:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    r0,r1
        do      n7,>pend
        move    x:(r0)+,a
        move    x:(r0)+,b
        move    a,x:(r1)+
        move    b,x:(r1)+
pend:
        rts
