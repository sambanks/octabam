| <Module name> -- one linked unit. GNU as, ColdFire ISA A+ (m68k-elf-as).
|
| Symbols you `.global` here are what the manifest's Detours name. Absolute
| references to stock code are fine (`jsr (0x40001e50).l`); references to
| your own labels are resolved by the link wherever the build places this,
| so write `lea SYM:l,%a0` for a same-unit address you need as a pointer
| (a bare `lea SYM,%a0` assembles pc-relative -- correct, but four bytes
| shorter than a hand-assembled original if you are matching one).
        .text
        .global my_hook

| A "jsr" detour lands here and expects an rts. A "jmp" detour's target
| must first REPLAY the instructions the six-byte jmp displaced, then jump
| back to site+6 (or wherever those instructions would have continued).
my_hook:
        nop
        rts
