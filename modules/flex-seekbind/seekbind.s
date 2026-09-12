| FLEX seek-bind A -- hooked on the bind tail's same-sample test (0x4000f8cc:
| tstb (55,sp) / beqs 0x4000f8ea, 6 bytes). Same slot/type/generation ->
| take the SAME-SAMPLE continuation with result 1, skipping the position
| compare that turns a recorder-buffer re-bind into a new note. Otherwise
| the stock "different" path. Entry: (sp) = return, bind's sp@55 = (59,sp).
        .text
seekA:  tstb    (59,%sp)
        beqs    diff
        moveq   #1,%d0
        addql   #4,%sp
        jmp     0x4000f8ec
diff:   addql   #4,%sp
        jmp     0x4000f8ea
