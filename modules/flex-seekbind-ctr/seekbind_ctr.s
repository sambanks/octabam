| FLEX seek-bind B (second cave, paired with A) -- hooked on the bind's
| per-voice counter bump (0x4000f834: addql #1,(144,a2) / movel a0,(152,a2),
| 8 bytes). On a same-sample re-bind leave the counter alone so the frame
| builder does not re-send the voice as new; always replay the store.
        .text
seekB:  tstb    (59,%sp)
        bnes    same
        addql   #1,(144,%a2)
same:   movel   %a0,(152,%a2)
        rts
