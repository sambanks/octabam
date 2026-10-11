| RECORDER LOOP FIX hold, crossfade copy, second fetch -- hooked at 0x4000854e
| (move.l d0,d7 / lea (16,sp),sp / tst.l d4), after the fetch of +0x4c.
| Scratch: a0, a1 (loaded before use below the hook).
| Assemble: m68k-elf-as -mcpu=5475 -o hold_xfade_b.o hold_xfade_b.s (from the repo root)
        .text
        .globl  rlf_hold_xfade_b
rlf_hold_xfade_b:
stub:   movea.l (%sp)+,%a1              | return address
        movea.l (4,%sp),%a0             | the fetched index
        bsr     fix
        move.l  %d0,%d7                 | displaced
        lea     (16,%sp),%sp            | displaced
        tst.l   %d4                     | displaced
        jmp     (%a1)
        .include "modules/recorder-loop-fix/fix.inc"
