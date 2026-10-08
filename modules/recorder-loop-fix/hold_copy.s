| RECORDER LOOP FIX hold, plain copy -- hooked at 0x400086c2 (move.l d0,d3 /
| addq.l #8,sp / tst.l d1), after the forward copy loop's fetch of +0x48.
| Scratch: a0, a1 (loaded before use below the hook).
| Assemble: m68k-elf-as -mcpu=5475 -o hold_copy.o hold_copy.s (from the repo root)
        .text
        .globl  rlf_hold_copy
rlf_hold_copy:
stub:   movea.l (%sp)+,%a1              | return address
        movea.l (4,%sp),%a0             | the fetched index
        addq.l  #8,%sp                  | displaced: the fetch's two arguments
        bsr     fix
        move.l  %d0,%d3                 | displaced
        tst.l   %d1                     | displaced
        jmp     (%a1)
        .include "modules/recorder-loop-fix/fix.inc"
