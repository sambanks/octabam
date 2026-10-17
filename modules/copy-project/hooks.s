| COPY PROJECT hooks -- PROJECT menu TableGrow symbols.

| PROJECT menu row = label, 0, action, 0, 0, 0 (docs/firmware/MAINMENU.md).
        .global cp_zero, cp_lbl
        .equ    cp_zero, 0
        .section .rodata
        .balign 4
cp_lbl:
        .asciz  "COPY PROJECT"
