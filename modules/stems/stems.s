| STEM REC -- T1 to the card while the sequencer plays (proof of concept).
|
| Design: docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md.
| Every stock address below, with its evidence: docs/firmware/STEM_REC.md.
|
| Three parts share the state words below:
|   stems_action      MAIN MENU > CONTROL > STEM REC, in the UI task
|   stems_frame_hook  the per-frame tap, in the audio interrupt at IPL 5
|   stems_task        our own RTOS task: the ring to the card, once the take stops
| The state is one aligned long, so every read and write of it is one
| instruction. The action and the hook write it; the task writes only IDLE.

| ---- stock facts (docs/firmware/STEM_REC.md) ----------------------------
        .equ    TRANSPORT,     0x800065b8   | long; 1 = running, 0 or 2 = stopped (Task 2)
        .equ    TRANSPORT_RUNNING, 1        | the ONLY value that means playing   (Task 2)
        .equ    CARD_MOUNTED,  0x460d1cb8   | long; 0 = no card                   (Task 8)
        .equ    FRAME_ROUTINE, 0x400031a0   | the displaced call
        .equ    MODE_W,        0x400b328b   | "w": opens without truncating
        .equ    PING,          0x800000e0   | the read-back half selector  (Task 3)
        .equ    PING_XOR,      0            | half = (PING ^ PING_XOR) & 1  (Task 3)
        .equ    READBACK,      0x80003190   | core 1's read-back, tracks 1-4
        .equ    T1_OFFSET,     0x100        | T1's block in a half: the THIRD 0x80 slot (Task 11)
        .equ    K_CREATE,      0x400005fc   | (tcb, entry, prio, stack, size) -> 1   (Task 4)
        .equ    K_START,       0x4000063c   | (tcb)                                  (Task 4)
        .equ    TCB_SIZE,      84           |                                        (Task 4)
        .equ    K_DELAY,       0x40020c7c   | (us, wait) -> 0; -1 = timer busy, wait 0 (Task 5)
        .equ    K_DELAY_TRY,   0            | wait = 0: never block on the shared timer (Task 5)
        .equ    TASK_SLEEP_US, 10000        | one pass; MICROSECONDS, not ticks       (Task 5)
        .equ    F_OPEN,        0x40016864   | (obj, path, mode, buf, size) <0 = error
        .equ    F_WRITE,       0x400166b8   | (obj, src, len) 1 = success
        .equ    F_CLOSE,       0x4001677c   | (obj) <0 = error; sets the file length to obj+16
        .equ    FS_EXISTS_PTR, 0x46c823fa   | -> exists(path): non-zero if it exists; call THROUGH it (Task 7)
        .equ    SET_PATH,      0x100f8480   | the current set's path, a C string in place (Task 6)
        .equ    CLK_READ,      0x4001c4d8   | (field) -> one BCD byte in d0; BLOCKS   (Task 6)
        .equ    BCD2BIN,       0x4001c31c   | (bcd) -> binary                          (Task 6)
        .equ    NAME_FMT,      0x400b77bb   | "%02d%02d%02d-%02d%02d"                  (Task 6)
        .equ    SPRINTF,       0x40013a08   | (buf, fmt, ...)
        .equ    FS_MKDIR_PTR,  0x46c8240a   | -> mkdir(path): 0 ok, <0 failed; call THROUGH it (Task 7)
        .equ    ATA_DATA,      0x900000a0   | the card's data register, 16 bits       (11.7)
        .equ    ATA_PTR,       0x46c8c594   | long; the PIO handler's next sector      (11.7)
        .equ    ATA_LEFT,      0x46c8c592   | byte; the sectors the handler still sends (11.7)
        .equ    ATA_RET,       0x40014d58   | the PIO write routine's return           (11.7)

| ---- constants -----------------------------------------------------------
        .equ    ST_IDLE,       0
        .equ    ST_ARMED,      1
        .equ    ST_RECORDING,  2
        .equ    ST_FINISHING,  3
        .equ    RING_SIZE,     0x400000     | = DramRegion stems_ring
        .equ    FRAME_BYTES,   64           | 16 stereo 16-bit samples
        .equ    MAX_FRAMES,    41344        | 15.0 s
        .equ    ERR_OVERFLOW,  1
        .equ    CHUNK,         0x10000      | 64 KB per write
        .equ    STACK_SIZE,    0x2000       | = DramRegion stems_stack
        .equ    TASK_PRIO,     1
        .equ    FBUF_SIZE,     512
        .equ    PATH_MAX,      256
        .equ    ERR_PATH,      2
        .equ    ERR_OPEN,      3
        .equ    ERR_EXISTS,    4
        .equ    ERR_WRITE,     5
|       6 is retired: it was ERR_SEEK, and the unit no longer seeks
        .equ    ERR_CLOSE,     7
        .equ    ERR_TASK,      8
        .equ    STACK_FILL,    0x5354454d   | "STEM": the untouched stack

| ColdFire byterev is ISA_A+ and -mcpu=5407 does not accept it, so it is
| encoded by hand: opcode 0x02C0 | reg (SAMPLE_SAVE.md section 3).
        .macro  BYTEREV reg          | reg = 0..7, a data register number
        .short  0x02c0 + \reg
        .endm

        .text

| ---- state -----------------------------------------------------------------
        .balign 4
        .global stems_state, stems_status, stems_task_made
stems_state:     .long   ST_IDLE
stems_status:    .long   0          | the last error, 0 = none
stems_task_made: .long   0
stems_wr:        .long   0          | bytes the hook has put in the ring
stems_rd:        .long   0          | bytes the task has taken out
stems_frames:    .long   0          | frames recorded
stems_file_open: .long   0
stems_file:      .space  24         | the stock buffered file object: +0 handle, +4 buffer,
                                    | +8 buffer size, +12 fill, +16 write position, +20 mode
                                    | byte; nothing touches +21 or above (STEM_REC.md 7.10)
stems_tcb:       .space  TCB_SIZE   | zero until the one create (STEM_REC.md 3.8)
stems_name:      .space  16         | YYMMDD-HHMM
stems_path:      .space  PATH_MAX
stems_fbuf:      .space  FBUF_SIZE
| The 44-byte header, little-endian as RIFF wants. The two sizes are
| filled in here, in memory, once the take has stopped, and the header is
| then written FIRST, with its final values: the file layer cannot patch a
| header after the data (STEM_REC.md 7.10).
stems_hdr:
        .ascii  "RIFF"
        .long   0                   | 36 + data, at stop
        .ascii  "WAVEfmt "
        .byte   16,0,0,0            | fmt chunk size
        .byte   1,0                 | PCM
        .byte   2,0                 | stereo
        .byte   0x44,0xac,0,0       | 44,100
        .byte   0x10,0xb1,0x02,0    | 176,400 bytes per second
        .byte   4,0                 | block align
        .byte   16,0                | bits
        .ascii  "data"
        .long   0                   | data, at stop
        .equ    HDR_SIZE, 44
fmt_dir:   .asciz  "/AUDIO/%s"
fmt_file:  .asciz  "/T1.wav"
        .balign 2

| ---- the menu row -------------------------------------------------------
        .global stems_label, stems_zero
        .equ    stems_zero, 0       | the row's window, pad, child and id
stems_label:
        .asciz  "STEM REC"
        .balign 2

| ---- the menu action: action(0), in the UI task ------------------------
| d0-d1/a0-a1 are scratch; everything else is preserved.
        .global stems_action
stems_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        tst.l   CARD_MOUNTED        | no card: do nothing at all
        beq.s   .La_out
        tst.l   stems_task_made     | the writer task, created once (STEM_REC.md 3.8)
        bne.s   .La_made
        bsr.w   stems_task_create   | d0 = 1 when the task exists
        tst.l   %d0
        beq.w   .La_out             | could not create it: stay IDLE
        moveq   #1,%d0
        move.l  %d0,stems_task_made
.La_made:
        move.w  %sr,%d2
        move.w  #0x2700,%sr         | no frame hook between read and write
        move.l  stems_state,%d0
        tst.l   %d0
        bne.s   .La_busy
        clr.l   stems_wr            | IDLE: a fresh recording
        clr.l   stems_rd
        clr.l   stems_frames
        clr.l   stems_status
        moveq   #ST_ARMED,%d1
        move.l  TRANSPORT,%d0       | running iff exactly 1 (Task 2)
        subq.l  #TRANSPORT_RUNNING,%d0
        bne.s   .La_set             | 0 or 2: stopped
        moveq   #ST_RECORDING,%d1   | already playing: start at the next frame
        bra.s   .La_set
.La_busy:
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .La_notarmed
        moveq   #ST_IDLE,%d1        | ARMED: cancel
        bra.s   .La_set
.La_notarmed:
        moveq   #ST_RECORDING,%d1
        cmp.l   %d1,%d0
        bne.s   .La_unmask          | FINISHING: ignored
        moveq   #ST_FINISHING,%d1   | RECORDING: stop
.La_set:
        move.l  %d1,stems_state
.La_unmask:
        move.w  %d2,%sr
.La_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| ---- the frame hook: in the audio interrupt, IPL 5 ---------------------
| Reached by `jsr` from 0x40004b12. Calls nothing but the routine it
| displaced; uses no RTOS service; loops are bounded. In IDLE its whole
| cost is one test and one branch. The copy runs BEFORE the stock routine,
| which reads the same block (spec section 4).
        .global stems_frame_hook
stems_frame_hook:
        tst.l   stems_state
        beq.w   .Lh_stock           | IDLE
        lea     -32(%sp),%sp
        movem.l %d0-%d5/%a0-%a1,(%sp)
        move.l  stems_state,%d0
        moveq   #ST_FINISHING,%d1
        cmp.l   %d1,%d0
        beq.w   .Lh_out             | FINISHING: the task owns the ring now
        move.l  TRANSPORT,%d2       | running iff exactly 1 (Task 2)
        subq.l  #TRANSPORT_RUNNING,%d2   | Z set while the sequencer plays
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .Lh_rec
        tst.l   %d2                 | ARMED
        bne.w   .Lh_out             | still stopped (0 or 2)
        moveq   #ST_RECORDING,%d0   | the first playing frame is recorded
        move.l  %d0,stems_state
        bra.s   .Lh_copy
.Lh_rec:                            | RECORDING
        tst.l   %d2
        beq.s   .Lh_copy
        moveq   #ST_FINISHING,%d0   | the sequencer stopped: 0 (end, rewind) or 2 (STOP key)
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_copy:
        move.l  stems_wr,%d3
        move.l  %d3,%d0
        sub.l   stems_rd,%d0        | bytes in the ring
        cmpi.l  #RING_SIZE-FRAME_BYTES,%d0
        bls.s   .Lh_room
        moveq   #ERR_OVERFLOW,%d0   | would overwrite unwritten audio: stop
        move.l  %d0,stems_status
        moveq   #ST_FINISHING,%d0
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_room:
        move.l  PING,%d4            | the half holding this frame (Task 3)
        eori.l  #PING_XOR,%d4
        moveq   #1,%d5
        and.l   %d5,%d4
        moveq   #10,%d5
        lsl.l   %d5,%d4             | * 0x400
        movea.l %d4,%a0
        adda.l  #READBACK+T1_OFFSET,%a0
        move.l  %d3,%d0
        andi.l  #RING_SIZE-1,%d0
        movea.l %d0,%a1
        adda.l  #stems_ring,%a1
| Each sample is one long on the host port: its top 16 bits, then its low
| 8 bits shifted up. Keep the top halves of L and R as one long.
        .rept   16
        move.l  (%a0)+,%d0          | L
        move.l  (%a0)+,%d1          | R
        swap    %d1
        move.w  %d1,%d0             | L top 16 : R top 16
        move.l  %d0,(%a1)+
        .endr
        moveq   #FRAME_BYTES,%d0
        add.l   %d0,%d3
        move.l  %d3,stems_wr        | publish after the data
        move.l  stems_frames,%d0
        addq.l  #1,%d0
        move.l  %d0,stems_frames
        cmpi.l  #MAX_FRAMES,%d0
        bcs.s   .Lh_out
        moveq   #ST_FINISHING,%d0   | 15 seconds
        move.l  %d0,stems_state
.Lh_out:
        movem.l (%sp),%d0-%d5/%a0-%a1
        lea     32(%sp),%sp
.Lh_stock:
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        rts

| ---- the stock PIO write's first sector (docs/firmware/STEM_REC.md 11.7) --
| Reached by `jmp` from 0x40014cfe, in the task that issued a WRITE SECTORS,
| once the card has asked for data. Stock streams the first sector, then
| advances the interrupt handler's data pointer and sector count, with
| interrupts enabled: a card interrupt taken between the two runs the
| handler on the stale pair, which either sends a sector twice or leaves
| the handler waiting, masked, for a sector the card never asks for. This
| does the same work in the safe order. The card cannot interrupt for this
| command until the whole sector is in, so the handler always finds the
| pair already advanced. Registers as stock: d0, d1 and a0.
        .global stems_ata_first
stems_ata_first:
        movea.l ATA_PTR,%a0         | this sector (the displaced instruction)
        move.l  %a0,%d1
        addi.l  #512,%d1
        move.l  %d1,ATA_PTR         | the handler's next sector
        move.b  ATA_LEFT,%d0
        subq.l  #1,%d0
        move.b  %d0,ATA_LEFT        | the sectors the handler still sends
.Lw_word:
        move.w  (%a0)+,%d0
        move.w  %d0,ATA_DATA
        cmp.l   %a0,%d1
        bne.s   .Lw_word
        jmp     ATA_RET             | stock: return the count

| ---- creating the task (from the action, in the UI task) ---------------
| The sequence is stock's own (docs/firmware/STEM_REC.md section 3).
stems_task_create:
        lea     stems_stack,%a0     | fill the stack so its peak can be read
        move.l  #STACK_SIZE/4,%d0
        move.l  #STACK_FILL,%d1
.Lc_fill:
        move.l  %d1,(%a0)+
        subq.l  #1,%d0
        bne.s   .Lc_fill
        move.l  #STACK_SIZE,-(%sp)
        pea     stems_stack
        pea     TASK_PRIO
        pea     stems_task
        pea     stems_tcb
        jsr     K_CREATE
        lea     20(%sp),%sp
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bne.s   .Lc_fail
        pea     stems_tcb
        jsr     K_START
        addq.l  #4,%sp
        moveq   #1,%d0
        rts
.Lc_fail:
        moveq   #ERR_TASK,%d0
        move.l  %d0,stems_status
        moveq   #0,%d0
        rts

| ---- the task ------------------------------------------------------------
| Wakes every TASK_SLEEP_US. Owns the file. Writes stems_state only to IDLE.
| Writes nothing while the take runs: once the hook has moved the state to
| FINISHING, stems_wr is final and the whole take is written in one pass,
| header first (STEM_REC.md 7.10). The ring holds a whole 15 s take.
| K_DELAY(us, wait): C order, so wait is pushed first (STEM_REC.md 4.4:
| us at sp@(8), wait at sp@(12) inside the routine).
stems_task:
.Lt_loop:
        pea     K_DELAY_TRY
        pea     TASK_SLEEP_US
        jsr     K_DELAY             | d0 = -1 when the timer was busy: just loop
        addq.l  #8,%sp
        moveq   #ST_FINISHING,%d1
        cmp.l   stems_state,%d1
        bne.s   .Lt_loop            | IDLE, ARMED or RECORDING: nothing to write
        tst.l   stems_frames
        beq.s   .Lt_idle            | stopped before a frame: no file
        bsr.w   stems_write_take    | stems_status says why if it failed
.Lt_idle:
        clr.l   stems_state
        bra.s   .Lt_loop

| ---- the name: YYMMDD-HHMM, from the clock -----------------------------
        .macro  CLOCK field
        pea     \field
        jsr     CLK_READ
        addq.l  #4,%sp
        move.l  %d0,-(%sp)
        jsr     BCD2BIN
        addq.l  #4,%sp
        .endm
stems_make_name:
        lea     -20(%sp),%sp
        movem.l %d2-%d6,(%sp)
        CLOCK   2
        move.l  %d0,%d2             | minute
        CLOCK   3
        move.l  %d0,%d3             | hour
        CLOCK   5
        move.l  %d0,%d4             | day
        CLOCK   6
        move.l  %d0,%d5             | month
        CLOCK   7
        move.l  %d0,%d6             | year, two digits
        move.l  %d2,-(%sp)
        move.l  %d3,-(%sp)
        move.l  %d4,-(%sp)
        move.l  %d5,-(%sp)
        move.l  %d6,-(%sp)
        pea     NAME_FMT
        pea     stems_name
        jsr     SPRINTF
        lea     28(%sp),%sp
        movem.l (%sp),%d2-%d6
        lea     20(%sp),%sp
        rts

| ---- the path: <set>/AUDIO/<name>/T1.wav ---------------------------------
| set = the C string at SET_PATH, used exactly as the stock save uses it
| (STEM_REC.md 5.8): copied, never trimmed, and PROJ_DIR is never called.
| Uses d0, d1, a0, a1 only. d0 = 0, or -1 (empty, or too long).
stems_make_path:
        lea     SET_PATH,%a0
        lea     stems_path,%a1
        move.l  #PATH_MAX-40,%d1    | room left for /AUDIO/name/T1.wav
.Lp_copy:
        move.b  (%a0)+,%d0
        beq.s   .Lp_end
        move.b  %d0,(%a1)+
        subq.l  #1,%d1
        bne.s   .Lp_copy
        bra.s   .Lp_fail            | the set path is too long
.Lp_end:
        clr.b   (%a1)
        move.l  %a1,%d0
        sub.l   #stems_path,%d0
        beq.s   .Lp_fail            | an empty set path: no set mounted
        pea     stems_name          | <set>/AUDIO/<name>, written at the end
        pea     fmt_dir
        move.l  %a1,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        movea.l FS_MKDIR_PTR,%a0    | the take's folder (STEM_REC.md 6.11). It
        pea     stems_path          | takes FS_LOCK and reads the clock, so task
        jsr     (%a0)               | context only. An error is left to the
        addq.l  #4,%sp              | open, which fails if the folder is absent.
        lea     fmt_file,%a0
        lea     stems_path,%a1      | append the file part
.Lp_find:
        tst.b   (%a1)+
        bne.s   .Lp_find
        subq.l  #1,%a1
.Lp_app:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lp_app
        moveq   #0,%d0
        rts
.Lp_fail:
        moveq   #-1,%d0
        rts

| ---- name, folder, refuse an existing file, open ------------------------
| d0 = 0 with the file open, or -1 with stems_status set and nothing open.
stems_open:
        bsr.w   stems_make_name
        bsr.w   stems_make_path
        tst.l   %d0
        bmi.s   .Lo_path
        movea.l FS_EXISTS_PTR,%a0   | same minute as an earlier take: refuse.
        pea     stems_path          | (The object's +16 cannot say: open
        jsr     (%a0)               | clears it. STEM_REC.md 7.10.)
        addq.l  #4,%sp
        tst.l   %d0
        bne.s   .Lo_exists          | non-zero: it exists (or no card: -1)
        pea     FBUF_SIZE
        pea     stems_fbuf
        pea     MODE_W
        pea     stems_path
        pea     stems_file
        jsr     F_OPEN
        lea     20(%sp),%sp
        tst.l   %d0
        bmi.s   .Lo_open
        moveq   #1,%d0
        move.l  %d0,stems_file_open
        moveq   #0,%d0
        rts
.Lo_path:   moveq   #ERR_PATH,%d0
        bra.s   .Lo_err
.Lo_open:   moveq   #ERR_OPEN,%d0
        bra.s   .Lo_err
.Lo_exists: moveq   #ERR_EXISTS,%d0
.Lo_err:
        move.l  %d0,stems_status
        moveq   #-1,%d0
        rts

| ---- write d1 bytes from the ring's read index, little-endian ----------
| d1: a multiple of 4 that does not cross the ring's end. d0 = 0 or -1.
stems_write_run:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  %d1,%d3
        beq.s   .Lw_done
        move.l  stems_rd,%d0
        andi.l  #RING_SIZE-1,%d0
        movea.l %d0,%a0
        adda.l  #stems_ring,%a0
        movea.l %a0,%a1
        move.l  %d3,%d2
        lsr.l   #2,%d2              | longs
.Lw_swap:                           | [L1 L0 R1 R0] -> [L0 L1 R0 R1]
        move.l  (%a1),%d0
        BYTEREV 0
        swap    %d0
        move.l  %d0,(%a1)+
        subq.l  #1,%d2
        bne.s   .Lw_swap
        move.l  %d3,-(%sp)
        move.l  %a0,-(%sp)
        pea     stems_file
        jsr     F_WRITE
        lea     12(%sp),%sp
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bne.s   .Lw_err
        add.l   %d3,stems_rd
.Lw_done:
        moveq   #0,%d0
        bra.s   .Lw_out
.Lw_err:
        moveq   #ERR_WRITE,%d0
        move.l  %d0,stems_status
        moveq   #-1,%d0
.Lw_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| ---- the take: its final header, then the ring, then close --------------
| Runs once the hook has stopped (FINISHING), so stems_wr is final. One
| sequential pass and NO SEEK, the way the stock sample save writes: the
| buffered layer's seek does not flush and moves the write position, and
| close sets the file's length to that position, so a header patched after
| the data would cut the file to 44 bytes (STEM_REC.md 7.10).
| d0 = 0, or -1 with stems_status set; the file is closed either way.
stems_write_take:
        bsr.w   stems_open          | name, folder, refuse an existing file, open
        tst.l   %d0
        bmi.w   .Lk_ret             | nothing is open
        move.l  stems_wr,%d1
        sub.l   stems_rd,%d1        | data bytes: exactly what will be written
        move.l  %d1,%d0
        BYTEREV 0
        move.l  %d0,stems_hdr+40    | data size, little-endian
        moveq   #36,%d0
        add.l   %d1,%d0             | RIFF size = 36 + data
        BYTEREV 0
        move.l  %d0,stems_hdr+4
        pea     HDR_SIZE
        pea     stems_hdr
        pea     stems_file
        jsr     F_WRITE
        lea     12(%sp),%sp
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bne.s   .Lk_werr
.Lk_chunk:                          | at most CHUNK, never across the ring's end
        move.l  stems_wr,%d1
        sub.l   stems_rd,%d1        | bytes left
        beq.s   .Lk_close
        cmpi.l  #CHUNK,%d1
        bls.s   .Lk_fit
        move.l  #CHUNK,%d1
.Lk_fit:
        move.l  stems_rd,%d0
        andi.l  #RING_SIZE-1,%d0
        neg.l   %d0
        addi.l  #RING_SIZE,%d0      | bytes from the read index to the ring's end
        cmp.l   %d0,%d1
        bls.s   .Lk_run             | d1 <= room: keep d1
        move.l  %d0,%d1
.Lk_run:
        bsr.w   stems_write_run     | swaps in place, writes, advances stems_rd
        tst.l   %d0
        bpl.s   .Lk_chunk
        bra.s   .Lk_fail            | stems_write_run set ERR_WRITE
.Lk_close:
        pea     stems_file
        jsr     F_CLOSE             | flushes the tail; length = write position
        addq.l  #4,%sp
        clr.l   stems_file_open     | before the check: never close twice
        tst.l   %d0
        bmi.s   .Lk_cerr
        moveq   #0,%d0
.Lk_ret:
        rts
.Lk_werr:
        moveq   #ERR_WRITE,%d0
        move.l  %d0,stems_status
.Lk_fail:
        pea     stems_file
        jsr     F_CLOSE
        addq.l  #4,%sp
        clr.l   stems_file_open
        moveq   #-1,%d0
        rts
.Lk_cerr:
        moveq   #ERR_CLOSE,%d0
        move.l  %d0,stems_status
        moveq   #-1,%d0
        rts
