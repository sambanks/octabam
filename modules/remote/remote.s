| REMOTE -- event records for a host driving a unit (tools/hw/ot_events.py).
|
| A record is 8 bytes: seq (16 bits, the low half of the count of records
| written), kind (8), arg (8), then DMA timer 3's count (32 bits, 132 MHz).
| RMT_RING is a 32-byte header {magic "RMT1", head, screen count, screen
| stamp, the address of RMT_TRACE, three zero longs} and 256 records:
| head counts every record written, record n is at index n & 255, so a host
| that last saw head H reads records H..head-1 and has lost head-H-256 of
| them when that is positive. The screen's redraws are a count and the last
| one's stamp, not records: a playing unit redraws about 70 times a second
| (224 in 9,000 frames under the port), which would turn the ring over in
| under 4 s. The USB module answers the vendor request 0xc0/0x5a with the
| block's bytes from byte offset wValue (modules/usb/usbaudio.s).
|
| Sources:
|   STORE's events (modules/store), each a record when its handler runs;
|   the frame interrupt's entry (0x4000aad0, vector 0x41, about 2,756 a
|   second): five state bytes compared with their values at the previous
|   entry, one record per change, and the LCD's front-buffer pointer, a
|   count and a stamp per change.
|   RMT_TRACE: at every frame interrupt's entry the interrupted PC (from
|   the exception frame) and DMA timer 3's count, the last 512 kept (186 ms):
|   {count, 0, 512 x {pc, stamp}}. A host reads it with PEEK (0xc0/0x58).
| The watched cells, measured under the port on the stock image (13 Nov
| 2026, --watch-mem): 0x800065b8 is written at 0x400a1050 and by the
| transport (docs/specs/EVENTS.md); 0x800065bd..c2 are written together at
| 0x400a05f6..0x400a0614 with the bank in bd, bf, c2 and the pattern in be,
| c0, c1 (docs/firmware/PARTS.md section 3: bf and c0 are the queued pair);
| 0x400b970c is written at 0x40013d6c by the LCD flush (0x40013abc) when it
| swaps the buffers.
| SPDX-License-Identifier: MIT

        .equ    DTCN3,   0xfc07c00c             | DMA timer 3's count, 132 MHz
        .equ    BODY,    0x4000aad8             | the handler after its displaced prologue
        .equ    LCDFRONT, 0x400b970c            | the frame the panel was last sent
        .equ    NREC,    256
        .equ    NTRACE,  512
        .equ    LOGF,    0x4001ffe4             | stock's log printf (level, format, ...)
        .equ    LOG_WARNING, 2                  | its level table 0x400abf28: CRITICAL, ERROR, WARNING
        .include "remix.inc"                    | HK_FRAME_ENTRY (modules/hooks)

| kinds
        .equ    K_LOADALL,  1                   | STORE loadall_post
        .equ    K_LOADMASK, 2                   | STORE loadmask_post, arg = the mask's low byte
        .equ    K_NEWPROJ,  3                   | STORE newproj
        .equ    K_BANKW,    4                   | STORE bankw_post
        .equ    K_PSTORE,   5                   | STORE pstore_post
        .equ    K_PRELOAD,  6                   | STORE preload_post
        .equ    K_WATCH,    16                  | 16 + the row of rmt_wtab, arg = the byte's new value

        .text
        .globl  rmt_in
rmt_in:
        .if     HK_FRAME_ENTRY == 0             | bridged by HOOKS: it replays the prologue
        lea     %sp@(-252),%sp                  | displaced: lea %sp@(-252),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@            | displaced: moveml %d0-%fp,%sp@
        .endif
        .if     HK_FRAME_ENTRY                  | every register is saved
        move.l  %sp@(260),%d0                   | the interrupted PC: HOOKS's return address, the 252-byte
        .else                                   | frame, the exception frame's format/SR long
        move.l  %sp@(256),%d0
        .endif
        lea     RMT_TRACE,%a0
        move.l  %a0@,%d1
        move.l  %d1,%d2
        and.l   #NTRACE-1,%d2
        lsl.l   #3,%d2
        lea     %a0@(8,%d2:l),%a1
        move.l  %d0,%a1@
        move.l  DTCN3,%d0
        move.l  %d0,%a1@(4)
        addq.l  #1,%d1
        move.l  %d1,%a0@
        lea     rmt_wtab,%a3
        lea     rmt_shadow,%a2
        moveq   #K_WATCH,%d4
1:      move.l  %a3@+,%d0
        beq.s   3f
        move.l  %d0,%a0
        mvz.b   %a0@,%d1
        mvz.b   %a2@,%d0
        cmp.l   %d0,%d1
        beq.s   2f
        move.b  %d1,%a2@
        move.l  %d4,%d0
        bsr.s   rmt_put
2:      addq.l  #1,%a2
        addq.l  #1,%d4
        bra.s   1b
3:      move.l  LCDFRONT,%d0
        cmp.l   rmt_lcd,%d0
        beq.s   4f
        move.l  %d0,rmt_lcd
        lea     RMT_RING,%a0
        addq.l  #1,%a0@(8)                      | the screen count
        move.l  DTCN3,%d0
        move.l  %d0,%a0@(12)
        .if     HK_FRAME_ENTRY
4:      rts                                     | HOOKS goes on to the next participant
        .else
4:      jmp     BODY
        .endif

| rmt_put: one record. d0 = kind, d1 = arg. Changes d0, d1, a0, a1. The
| head is read and written with interrupts masked: the frame interrupt and
| the tasks both write records.
        .globl  rmt_put
rmt_put:
        lea     %sp@(-8),%sp
        movem.l %d2-%d3,%sp@
        move.w  %sr,%d3
        move.w  #0x2700,%sr
        and.l   #0xff,%d0
        and.l   #0xff,%d1
        lsl.l   #8,%d0
        or.l    %d1,%d0                         | kind, arg
        lea     RMT_RING,%a0
        move.l  %a0@(4),%d2                     | head
        move.l  %d2,%d1
        swap    %d1
        clr.w   %d1
        or.l    %d1,%d0                         | seq in the high word
        move.l  %d2,%d1
        and.l   #NREC-1,%d1
        lsl.l   #3,%d1
        lea     %a0@(32,%d1:l),%a1
        move.l  %d0,%a1@
        move.l  DTCN3,%d1
        move.l  %d1,%a1@(4)
        addq.l  #1,%d2
        move.l  %d2,%a0@(4)
        move.w  %d3,%sr
        movem.l %sp@,%d2-%d3
        lea     %sp@(8),%sp
        rts

| STORE's handlers (docs/specs/STORE.md): a handler may change every register.
| Each writes its record, then rmt_flush.
        .globl  rmt_st_loadall_post, rmt_st_loadmask_post, rmt_st_newproj
        .globl  rmt_st_bankw_post, rmt_st_pstore_post, rmt_st_preload_post
rmt_st_loadall_post:
        moveq   #K_LOADALL,%d0
        bra.s   5f
rmt_st_loadmask_post:                           | d1 = the mask
        moveq   #K_LOADMASK,%d0
        bra.s   6f
rmt_st_newproj:
        moveq   #K_NEWPROJ,%d0
        bra.s   5f
rmt_st_bankw_post:
        moveq   #K_BANKW,%d0
        bra.s   5f
rmt_st_pstore_post:
        moveq   #K_PSTORE,%d0
        bra.s   5f
rmt_st_preload_post:
        moveq   #K_PRELOAD,%d0
5:      moveq   #0,%d1
6:      bsr.w   rmt_put

| rmt_flush: every record since the last flush as a
| line of stock's card log (/LOG <date>.txt): "RMT seq kind arg stamp",
| decimal. LOGF is stock's log printf (level, format, ...): it formats
| "<date> <LEVEL> <text>" and appends the line to the file, opening and
| closing it (read from 0x4001ffe4 and 0x4001ff2c; the load calls it once
| per sample it cannot open). Called only from STORE's handlers, which run
| in the task and at the points where stock itself reads or writes the card.
rmt_flush:
        lea     %sp@(-16),%sp
        movem.l %d2-%d3/%a2-%a3,%sp@
        lea     RMT_RING,%a2
1:      move.l  rmt_flushed,%d2
        move.l  %a2@(4),%d0                     | head
        cmp.l   %d0,%d2
        bcc.s   9f                              | nothing newer
        sub.l   %d2,%d0
        cmp.l   #NREC,%d0
        bls.s   2f
        move.l  %a2@(4),%d2                     | more than a ring behind: from the oldest kept
        sub.l   #NREC,%d2
2:      move.l  %d2,%d0
        addq.l  #1,%d0
        move.l  %d0,rmt_flushed
        and.l   #NREC-1,%d2
        lsl.l   #3,%d2
        lea     %a2@(32,%d2:l),%a3
        mvz.b   %a3@(2),%d0
        move.l  %a3@(4),%sp@-                   | stamp
        mvz.b   %a3@(3),%d1
        move.l  %d1,%sp@-                       | arg
        move.l  %d0,%sp@-                       | kind
        mvz.w   %a3@,%d1
        move.l  %d1,%sp@-                       | seq
        pea     rmt_fmt
        moveq   #LOG_WARNING,%d0
        move.l  %d0,%sp@-
        jsr     LOGF
        lea     %sp@(24),%sp
        bra.s   1b
9:      movem.l %sp@,%d2-%d3/%a2-%a3
        lea     %sp@(16),%sp
        rts

rmt_fmt: .asciz "RMT %d %d %d %d"
        .balign 2

        .data
        .balign 4
| The watched bytes, in kind order from K_WATCH; a zero ends the table.
rmt_wtab:
        .long   0x800065bb                      | 16 PLAYING (the long's low byte)
        .long   0x800065bd                      | 17 the current bank
        .long   0x800065be                      | 18 the current pattern
        .long   0x800065bf                      | 19 the queued bank
        .long   0x800065c0                      | 20 the queued pattern
        .long   0
rmt_shadow:
        .space  8                               | each watched byte at the previous entry
rmt_lcd: .long  0                               | LCDFRONT at the previous entry
rmt_flushed: .long 0                            | the count of records rmt_flush has passed
        .globl  RMT_RING
RMT_RING:
        .long   0x524d5431                      | "RMT1"
        .long   0                               | head
        .long   0                               | LCD front-buffer changes
        .long   0                               | the last one's stamp
        .long   RMT_TRACE
        .long   0, 0, 0
        .space  NREC*8
        .globl  RMT_TRACE
RMT_TRACE:
        .long   0                               | frame interrupts entered
        .long   0
        .space  NTRACE*8
