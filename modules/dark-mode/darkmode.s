| darkmode.s -- Full Octa Dark Mode (system-wide display inversion)
|
| Author: 8thmyth & Octahacks Multi-Agent Fleet
|
| Hooks the display compositor flush routine at 0x40013cae:
| Right after the page plane and all window layers (Mixer, Audio Editor,
| Arranger, Menus, Popups, Step View) have finished compositing into the
| 1,024-byte backbuffer [0x400b9710], and immediately before the diff-and-send
| loop transmits changed blocks to the LCD controller over UART1.
|
| When Dark Mode is enabled (dm_enabled != 0), inverts all 256 longwords
| (1,024 bytes) of the backbuffer. This turns every screen into crisp,
| high-contrast OLED-style dark mode (white graphics/text on deep black).

        .include "remix.inc"

        .text
        .balign 2
        .global dm_flush_hook

        .equ    BACK_BUF,   0x400b9710
        .equ    RET_SITE,   0x40013cb4

dm_flush_hook:
        moveal  BACK_BUF,%a5                | replay displaced instruction: a5 = backbuffer
        get_dark_mode %d0                   | read BRAIN setting (or dm_enabled fallback)
        tstl    %d0                         | check if Dark Mode is enabled
        beqs    .Ldm_done                   | if 0, pass through unchanged

        | Invert all 1,024 bytes (256 longwords = 64 loops of 4 longwords)
        moveal  %a5,%a0
        moveq   #64-1,%d0
.Ldm_loop:
        movel   %a0@,%d1
        notl    %d1
        movel   %d1,%a0@+
        movel   %a0@,%d1
        notl    %d1
        movel   %d1,%a0@+
        movel   %a0@,%d1
        notl    %d1
        movel   %d1,%a0@+
        movel   %a0@,%d1
        notl    %d1
        movel   %d1,%a0@+
        subql   #1,%d0
        bpls    .Ldm_loop

.Ldm_done:
        jmp     RET_SITE:l                  | return to stock diff loop (0x40013cb4)

