| HELLO DRAM -- the smallest thing the DRAM platform can carry.
|
| One unit, no detours, no pokes. The build links it into octabam's platform
| runtime, packs it, appends it behind the loader and depacks it at boot into
| the never-cleared window (docs/remixer/PLACEMENT.md). Nothing in the OS
| ever calls it; `tools/verify/verify_dram_boot.py` proves it LANDED, byte for
| byte, at the address the link gave it. A real module puts code here and
| reaches it with `Detour`s; this one exists to be read, and to stay
| buildable as a canary for the loader path.
        .text
        .global hello_dram_tag, hello_dram_probe
hello_dram_tag:
        .ascii  "octabam hello-dram"
        .byte   0
        .balign 2
| A callable that returns. A Detour(kind="jsr") at a stock site would reach
| it as `jsr hello_dram_probe`; none does.
hello_dram_probe:
        nop
        rts
