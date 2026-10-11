| RECORDER LOOP FIX hold, crossfade copy, first fetch -- hooked at 0x4000853e
| (movea.l d0,a3 / move.l d1,d4 / move.l (76,a2),-(sp)), after the fetch of
| +0x48. The fetch's arguments stay on the stack (0x40008550 drops both pairs).
| Scratch: a0, a1 (loaded before use below the hook).
| Assemble: m68k-elf-as -mcpu=5475 -o hold_xfade_a.o hold_xfade_a.s (from the repo root)
        .text
        .globl  rlf_hold_xfade_a
rlf_hold_xfade_a:
stub:   movea.l (%sp)+,%a1              | return address
        movea.l (4,%sp),%a0             | the fetched index
        bsr     fix
        movea.l %d0,%a3                 | displaced
        move.l  %d1,%d4                 | displaced
        move.l  (76,%a2),-(%sp)         | displaced
        jmp     (%a1)
        .include "modules/recorder-loop-fix/fix.inc"
