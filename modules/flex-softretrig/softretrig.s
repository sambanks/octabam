| FLEX soft retrigger -- hooked on the three position stores of the FLEX bind
| (0x4000f820..0x4000f82b: movel a0,(64,a2) / (68,a2) / (72,a2)).
| Entry (after the planted jsr): a2 = voice, a0 = new start position,
| (4+55,sp) = the bind's own "same slot, type, generation" byte (sp@55).
| d0 is dead at the hook (reloaded at 0x4000f83c) but is saved anyway.
        .text
        .globl softretrig
softretrig:
        movel   %d0,-(%sp)
        tstb    (63,%sp)            | same sample as the running voice?
        beqs    do
        tstb    (%a2)               | voice active?
        beqs    do
        tstb    (21,%a2)            | recorder buffer (slot bit 7)?
        bpls    do
        mvsb    (20,%a2),%d0        | FLEX (type 1)?
        cmpil   #1,%d0
        bnes    do
        movel   (72,%a2),%d0        | read position - new start, unsigned
        subl    %a0,%d0
        cmpil   #64,%d0
        blss    skip                | just wrapped: leave it running
        movel   (52,%a2),%d0        | window end - read position
        subl    (72,%a2),%d0
        cmpil   #64,%d0
        blss    skip                | about to wrap on its own: leave it
do:     movel   %a0,(64,%a2)
        movel   %a0,(68,%a2)
        movel   %a0,(72,%a2)
skip:   movel   (%sp)+,%d0
        rts
