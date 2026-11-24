| COPY PROJECT hooks -- CHANGE→FUNC+BANK LISTPOP label.

| Short "COPY" matches stock RENAME/DELETE tails (docs/firmware/PANEL.md).
        .global cp_zero, cp_lbl
        .equ    cp_zero, 0
        .section .rodata
        .balign 4
cp_lbl:
        .asciz  "COPY"

| SAVE TO NEW's sidecars (copyproj.c cp_sa_capture / cp_sa_copy).
        .text
        .balign 4
        .global cp_sa_cap_stub, cp_sa_copy_stub

| 0x40085012, the jsr that overwrites the project name (strcpy 0x40013f40).
cp_sa_cap_stub:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     cp_sa_capture
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        jmp     0x40013f40

| 0x400850ee, after the last stock write. The result in d2 is stock's and is not
| consulted: an error in an earlier step leaves it negative with the new folder written.
cp_sa_copy_stub:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     cp_sa_copy
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        move.l  %d2,-(%sp)              | displaced
        move.l  -530(%fp),%a0           | displaced
        jmp     0x400850f4
