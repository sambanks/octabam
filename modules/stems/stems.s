| STEM REC -- the enabled tracks to the card while the sequencer plays. The
| build records all eight by default (stems_tracks = 0xFF).
|
| Design: docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md
| (streaming), over docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md.
| Every stock address below, with its evidence: docs/firmware/STEM_REC.md.
|
| Three parts share the state words below:
|   stems_action      MAIN MENU > STEMS > REC, in the UI task; stems_track_action T1-T8
|   stems_frame_hook  the per-frame tap, in the audio interrupt at IPL 5
|   stems_task        our own RTOS task: the ring to the card, while recording
| The state is one aligned long, so every read and write of it is one
| instruction. The action and the hook write it; the task writes IDLE, and
| FINISHING when a card write fails.

| ---- stock facts (docs/firmware/STEM_REC.md) ----------------------------
        .equ    TRANSPORT,     0x800065b8   | long; 1 = running, 0 or 2 = stopped (Task 2)
        .equ    TRANSPORT_RUNNING, 1        | the ONLY value that means playing   (Task 2)
        .equ    CARD_MOUNTED,  0x460d1cb8   | long; 0 = no card                   (Task 8)
        .equ    FRAME_ROUTINE, 0x400031a0   | the displaced call
        .equ    MODE_W,        0x400b328b   | "w": opens without truncating
        .equ    PING,          0x800000e0   | the read-back half selector  (Task 3)
        .equ    PING_XOR,      0            | half = (PING ^ PING_XOR) & 1  (Task 3)
        .equ    READBACK,      0x80003190   | track k's block at READBACK + half*0x400 + k*0x80 (9.2)
        .equ    K_CREATE,      0x400005fc   | (tcb, entry, prio, stack, size) -> 1   (Task 4)
        .equ    K_START,       0x4000063c   | (tcb)                                  (Task 4)
        .equ    TCB_SIZE,      84           |                                        (Task 4)
        .equ    K_DELAY,       0x40020c7c   | (us, wait) -> 0; -1 = timer busy, wait 0 (Task 5)
        .equ    K_DELAY_TRY,   0            | wait = 0: never block on the shared timer (Task 5)
        .equ    TASK_SLEEP_US, 10000        | one pass; MICROSECONDS, not ticks       (Task 5)
        .equ    FS_EXISTS_PTR, 0x46c823fa   | -> exists(path): 0 no, 1 file, 2 folder (6.11, 8.0)
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
        .equ    RAW_OPEN_PTR,  0x46c8242a   | -> open(path, mode) -> handle 1..511, <0 error (12.1)
        .equ    RAW_WRITE_PTR, 0x46c82402   | -> write(handle, buf, sectors) <0 error      (12.1)
        .equ    RAW_SEEK_PTR,  0x46c8243e   | -> seek(handle, offset)                       (12.1)
        .equ    RAW_SETLEN_PTR,0x46c82436   | -> setlen(handle, length)                     (12.1)
        .equ    RAW_CLOSE_PTR, 0x46c82422   | -> close(handle)                              (12.1)
        .equ    UNCACHED,      0x08000000   | the same RAM, data cache bypassed (PLAN.md, "The RAM")

| ---- constants -----------------------------------------------------------
        .equ    ST_IDLE,       0
        .equ    ST_ARMED,      1
        .equ    ST_RECORDING,  2
        .equ    ST_FINISHING,  3
        .equ    RING_SIZE,     0x400000     | = DramRegion stems_ring
        .equ    TRACK_BYTES,   64           | one track's frame: 16 stereo 16-bit samples
        .equ    MAX_FRAMES,    9922500      | 60 minutes
        .equ    CHUNK_FRAMES,  512          | frames per write while recording
        .equ    SBUF_SIZE,     CHUNK_FRAMES*64+512   | one track's stream buffer: a chunk plus a carry
        .equ    SEC0_BASE,     8*SBUF_SIZE  | the sector-0 copies follow the eight stream buffers
        .equ    STACK_SIZE,    0x2000       | = DramRegion stems_stack
        .equ    TASK_PRIO,     1
        .equ    PATH_MAX,      256
        .equ    ERR_OVERFLOW,  1
        .equ    ERR_PATH,      2
        .equ    ERR_OPEN,      3
        .equ    ERR_EXISTS,    4
        .equ    ERR_WRITE,     5
        .equ    ERR_SEEK,      6            | the seek in the header fix
        .equ    ERR_CLOSE,     7
        .equ    ERR_TASK,      8
        .equ    STACK_FILL,    0x5354454d   | "STEM": the untouched stack
        .equ    HDR_SIZE,      44

| ColdFire byterev is ISA_A+ and -mcpu=5407 does not accept it, so it is
| encoded by hand: opcode 0x02C0 | reg (SAMPLE_SAVE.md section 3).
        .macro  BYTEREV reg          | reg = 0..7, a data register number
        .short  0x02c0 + \reg
        .endm
        .macro  RAWCALL ptr
        movea.l \ptr,%a0
        jsr     (%a0)
        .endm

        .text

| ---- state -----------------------------------------------------------------
| The first six words are read as one 24-byte dump by verify_stems.py.
        .balign 4
        .global stems_state, stems_status, stems_task_made, stems_wr, stems_rd, stems_frames, stems_peak
stems_state:     .long   ST_IDLE
stems_status:    .long   0          | the last error, 0 = none
stems_task_made: .long   0
stems_wr:        .long   0          | frames the hook has put in the ring
stems_rd:        .long   0          | frames the task has taken out
stems_frames:    .long   0          | frames recorded (= stems_wr)
stems_peak:      .long   0          | the take's largest ring fill, frames; reset at the arm
        .global stems_tracks, stems_hold, stems_wr_off, stems_rd_off, stems_probe, stems_probe_res
stems_tracks:    .long   0xFF       | the track mask, bit k = track k+1; latched at the start
stems_hold:      .long   0          | test seam: non-zero pauses the writer while RECORDING
stems_mask:      .long   0          | the latched mask
stems_nt:        .long   0          | its bit count
stems_fbytes:    .long   0          | a ring frame: 64 x stems_nt
stems_rframes:   .long   0          | the ring's capacity in frames
stems_rlimit:    .long   0          | stems_rframes x stems_fbytes: offsets wrap here
stems_wr_off:    .long   0          | the hook's next frame, a byte offset into the ring
stems_rd_off:    .long   0          | the task's next frame
stems_nopen:     .long   0          | files open
stems_wfail:     .long   0          | a card write failed: finish without writing more
stems_handle:    .space  32         | one per open file, in track order
stems_slen:      .space  32         | bytes waiting in each stream buffer
stems_fpos:      .space  32         | bytes of each file on the card
stems_tcb:       .space  TCB_SIZE   | zero until the one create (STEM_REC.md 3.8)
stems_probe:     .long   0          | test seam: non-zero runs stems_probe_run once
stems_probe_res: .space  28
        .global stems_took, stems_ui_bufs
stems_took:      .long   0          | a take ended since the last arm: IDLE shows its result
ui_key:          .long   -1         | what the labels last showed, packed (stems_ui)
stems_ui_bufs:                      | two buffers for each formatted line
stat_buf0:       .space  16
stat_buf1:       .space  16
peak_buf0:       .space  16
peak_buf1:       .space  16
stems_name:      .space  16         | YYMMDD-HHMM
stems_path:      .space  PATH_MAX   | <set>/AUDIO/<name>
stems_fpath:     .space  PATH_MAX   | <set>/AUDIO/<name>/T<n>.wav
| The ring's capacity and wrap point for 1 to 8 tracks: whole frames only.
rframes_tab:
        .long   RING_SIZE/64, RING_SIZE/128, RING_SIZE/192, RING_SIZE/256
        .long   RING_SIZE/320, RING_SIZE/384, RING_SIZE/448, RING_SIZE/512
rlimit_tab:
        .long   (RING_SIZE/64)*64, (RING_SIZE/128)*128, (RING_SIZE/192)*192, (RING_SIZE/256)*256
        .long   (RING_SIZE/320)*320, (RING_SIZE/384)*384, (RING_SIZE/448)*448, (RING_SIZE/512)*512
| The 44-byte header, little-endian as RIFF wants, sizes 0: the placeholder
| every file starts with. The real sizes go into the sector-0 copy at the end.
stems_hdr:
        .ascii  "RIFF"
        .long   0
        .ascii  "WAVEfmt "
        .byte   16,0,0,0            | fmt chunk size
        .byte   1,0                 | PCM
        .byte   2,0                 | stereo
        .byte   0x44,0xac,0,0       | 44,100
        .byte   0x10,0xb1,0x02,0    | 176,400 bytes per second
        .byte   4,0                 | block align
        .byte   16,0                | bits
        .ascii  "data"
        .long   0
fmt_dir:   .asciz  "/AUDIO/%s"
fmt_file:  .asciz  "/T%d.wav"
probe_name: .asciz "/PROBE.BIN"
        .balign 2

| ---- the STEMS category (docs/superpowers/specs/2026-09-28-stem-rec-menu-design.md)
| A fifth MAIN MENU category. The manifest's TableGrow gives the root a row
| pointing at stems_cat_label, stems_icon and stems_list. The list and its
| rows live here, in DRAM: the menu engine writes the list's cursor
| fields, and STEM REC rewrites the rows' labels. A label changes by one
| aligned long write to the row's +0x00, so a redraw reads a whole old
| label or a whole new one. The menu redraws on keys only (STEM_REC.md
| 16.1): a label the task changes shows at the next key.
        .equ    ROW_LEN,       24           | a menu row (MAINMENU.md 1)
        .equ    MENU_ROWS,     11
        .equ    MENU_VISIBLE,  7            | a submenu pane's rows
        .equ    ROW_TRK0,      2            | T1's row
        .equ    ROW_PEAK,      10           | PEAK: the last row
| Rows with action 0 are headings. The engine skips ONE such row, not two
| in a row, and never moves onto a last one (STEM_REC.md 16.1), so the
| status row sits alone between REC and T1, and PEAK is the last row.
        .equ    LIST_SEL,      0x0c         | a list's absolute selection: the row under the cursor
        .global stems_cat_label, stems_icon, stems_icon_p0, stems_icon_p1, stems_list, stems_rows, stems_zero
        .equ    stems_zero, 0               | the root row's action, getter and id
stems_cat_label:
        .asciz  "STEMS"
        .balign 4
stems_icon:                                 | 19 x 9, two planes (MAINMENU.md 1)
        .long   0x13, 0x09, 0x01, stems_icon_p0, stems_icon_p1
stems_icon_p0:                              | a record dot: one long a column, the column in its top byte
        .long   0, 0, 0, 0, 0, 0
        .long   0x1c000000, 0x3e000000, 0x7f000000, 0x7f000000, 0x7f000000, 0x3e000000, 0x1c000000
        .long   0, 0, 0, 0, 0, 0
stems_icon_p1:                              | the stock icons' second plane, every column
        .rept   19
        .long   0xff800000
        .endr
stems_list:                                 | shipped filled in: the boot's set-up covers only stock lists
        .long   MENU_ROWS, 0, 0, 0, MENU_VISIBLE, MENU_ROWS, stems_rows
stems_rows:                                 | label, window, action, getter, child, page id
        .long   lbl_rec,   0, stems_action, 0, 0, 0
        .long   lbl_ready, 0, 0, 0, 0, 0    | the status: action 0, a heading the cursor skips
        .long   trk1_on, 0, stems_track_action, 0, 0, 0
        .long   trk2_on, 0, stems_track_action, 0, 0, 0
        .long   trk3_on, 0, stems_track_action, 0, 0, 0
        .long   trk4_on, 0, stems_track_action, 0, 0, 0
        .long   trk5_on, 0, stems_track_action, 0, 0, 0
        .long   trk6_on, 0, stems_track_action, 0, 0, 0
        .long   trk7_on, 0, stems_track_action, 0, 0, 0
        .long   trk8_on, 0, stems_track_action, 0, 0, 0
        .long   lbl_peak0, 0, 0, 0, 0, 0    | PEAK: a heading, the last row, which the cursor never reaches
rec_by_state:   .long   lbl_rec, lbl_cancel, lbl_stop, lbl_saving       | row 1, by state
st_by_state:    .long   lbl_ready, lbl_armed, 0, lbl_saving             | the status; RECORDING is the task's
err_names:      .long   0, err_ring, err_path, err_open, err_exists, err_write, err_seek, err_close, err_task
trk_on:         .long   trk1_on, trk2_on, trk3_on, trk4_on, trk5_on, trk6_on, trk7_on, trk8_on
trk_off:        .long   trk1_off, trk2_off, trk3_off, trk4_off, trk5_off, trk6_off, trk7_off, trk8_off
lbl_rec:        .asciz  "REC"
lbl_cancel:     .asciz  "CANCEL"
lbl_stop:       .asciz  "STOP"
lbl_saving:     .asciz  "SAVING"
lbl_ready:      .asciz  "READY"
lbl_armed:      .asciz  "ARMED"
lbl_nocard:     .asciz  "NO CARD"
lbl_peak0:      .asciz  "PEAK 0%"
err_ring:       .asciz  "RING FULL"         | ERR_OVERFLOW
err_path:       .asciz  "PATH FAILED"       | ERR_PATH
err_open:       .asciz  "OPEN FAILED"       | ERR_OPEN
err_exists:     .asciz  "SAME MINUTE"       | ERR_EXISTS
err_write:      .asciz  "WRITE FAILED"      | ERR_WRITE
err_seek:       .asciz  "SEEK FAILED"       | ERR_SEEK
err_close:      .asciz  "CLOSE FAILED"      | ERR_CLOSE
err_task:       .asciz  "TASK FAILED"       | ERR_TASK
trk1_on:  .asciz "T1 [X]"
trk1_off: .asciz "T1 [ ]"
trk2_on:  .asciz "T2 [X]"
trk2_off: .asciz "T2 [ ]"
trk3_on:  .asciz "T3 [X]"
trk3_off: .asciz "T3 [ ]"
trk4_on:  .asciz "T4 [X]"
trk4_off: .asciz "T4 [ ]"
trk5_on:  .asciz "T5 [X]"
trk5_off: .asciz "T5 [ ]"
trk6_on:  .asciz "T6 [X]"
trk6_off: .asciz "T6 [ ]"
trk7_on:  .asciz "T7 [X]"
trk7_off: .asciz "T7 [ ]"
trk8_on:  .asciz "T8 [X]"
trk8_off: .asciz "T8 [ ]"
fmt_rec:        .asciz  "REC %02d:%02d"
fmt_done:       .asciz  "DONE %02d:%02d"
fmt_peak:       .asciz  "PEAK %d%s"         | "%" as an argument: %% is untested in the stock sprintf
pct_sign:       .asciz  "%"
        .balign 2

| ---- the menu action: action(0), in the UI task ------------------------
| IDLE arms: the hook starts the take at the first playing frame, which is
| the next frame if the sequencer already plays. ARMED cancels. RECORDING
| stops. FINISHING is ignored. Arming resets the counters and the ring's
| offsets; a test may poke them afterwards (the port's pokes land after
| this call).
        .global stems_action
stems_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        tst.l   CARD_MOUNTED        | no card: say so, and change nothing else
        beq.w   .La_nocard
        tst.l   stems_task_made     | the writer task, created once (STEM_REC.md 3.8)
        bne.s   .La_made
        bsr.w   stems_task_create   | d0 = 1 when the task exists
        tst.l   %d0
        beq.w   .La_notask          | could not create it: stay IDLE, say so
        moveq   #1,%d0
        move.l  %d0,stems_task_made
.La_made:
        move.w  %sr,%d2
        move.w  #0x2700,%sr         | no frame hook between read and write
        move.l  stems_state,%d0
        tst.l   %d0
        bne.s   .La_busy
        clr.l   stems_wr            | IDLE: a fresh take
        clr.l   stems_rd
        clr.l   stems_frames
        clr.l   stems_peak
        clr.l   stems_status
        clr.l   stems_took          | the new take's result replaces the last one's
        clr.l   stems_wr_off
        clr.l   stems_rd_off
        moveq   #ST_ARMED,%d1
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
        bsr.w   stems_ui_state      | row 1 and the status, at once
.La_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts
.La_nocard:                         | no card: say so, and change nothing else
        lea     lbl_nocard,%a0
        move.l  %a0,stems_rows+ROW_LEN
        bra.s   .La_out
.La_notask:                         | the task couldn't be made: stay IDLE, say so
        lea     err_task,%a0
        move.l  %a0,stems_rows+ROW_LEN
        bra.s   .La_out

| ---- row 1 and the status from the state, at once (the actions) ---------
| Fixed strings only, in the UI task. The action never leaves the state
| RECORDING (the hook makes it), so st_by_state's RECORDING entry is 0: the
| task's line, left alone. Arming also shows a new take's PEAK 0%.
stems_ui_state:
        move.l  stems_state,%d0
        lea     rec_by_state,%a0
        move.l  (%a0,%d0.l*4),%d1
        move.l  %d1,stems_rows
        lea     st_by_state,%a0
        move.l  (%a0,%d0.l*4),%d1
        beq.s   .Lv_peak
        move.l  %d1,stems_rows+ROW_LEN
.Lv_peak:
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .Lv_out
        lea     lbl_peak0,%a0
        move.l  %a0,stems_rows+ROW_PEAK*ROW_LEN
.Lv_out:
        rts

| ---- a track row's action: action(0), in the UI task --------------------
| The row under the cursor names the track (the list's absolute selection,
| less T1's row, as octalab's checkbox rows do). Locked while a take
| records or saves: the take keeps the mask it latched at its start, and
| the rows show what records. The last track that's on stays on, so a take
| always has a track the rows show. The test and the flip run with
| interrupts masked, so the hook can't latch between them.
        .global stems_track_action
stems_track_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  stems_list+LIST_SEL,%d3
        subq.l  #ROW_TRK0,%d3               | track k, 0..7
        moveq   #8,%d0
        cmp.l   %d0,%d3
        bcc.s   .Lk_out                     | not a track row (unsigned: below T1 too)
        move.w  %sr,%d2
        move.w  #0x2700,%sr
        move.l  stems_state,%d1
        moveq   #ST_RECORDING,%d0
        cmp.l   %d0,%d1
        bcc.s   .Lk_keep                    | RECORDING or FINISHING: locked
        moveq   #1,%d0
        lsl.l   %d3,%d0                     | the track's bit
        move.l  stems_tracks,%d1
        eor.l   %d0,%d1
        tst.b   %d1
        beq.s   .Lk_keep                    | the last track on: it stays on
        move.l  %d1,stems_tracks
        move.w  %d2,%sr
        lea     trk_off,%a0
        and.l   %d0,%d1
        beq.s   .Lk_label
        lea     trk_on,%a0
.Lk_label:
        move.l  (%a0,%d3.l*4),%d0           | the label
        move.l  %d3,%d1
        addq.l  #ROW_TRK0,%d1
        lsl.l   #3,%d1                      | row * 8
        movea.l %d1,%a1
        adda.l  %d1,%a1
        adda.l  %d1,%a1                     | row * 24
        adda.l  #stems_rows,%a1
        move.l  %d0,(%a1)                   | the row's label pointer
        bra.s   .Lk_out
.Lk_keep:
        move.w  %d2,%sr
.Lk_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| ---- the frame hook: in the audio interrupt, IPL 5 ---------------------
| Reached by `jsr` from 0x40004b12. Calls nothing but the routine it
| displaced; uses no RTOS service; loops are bounded (8 tracks). In IDLE its
| whole cost is one test and one branch. The copy runs BEFORE the stock
| routine, which reads the same block.
        .global stems_frame_hook
stems_frame_hook:
        tst.l   stems_state
        beq.w   .Lh_stock           | IDLE
        lea     -36(%sp),%sp
        movem.l %d0-%d5/%a0-%a2,(%sp)
        move.l  stems_state,%d0
        moveq   #ST_FINISHING,%d1
        cmp.l   %d1,%d0
        beq.w   .Lh_out             | FINISHING: the hook adds nothing
        move.l  TRANSPORT,%d2       | running iff exactly 1 (Task 2)
        subq.l  #TRANSPORT_RUNNING,%d2   | Z set while the sequencer plays
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .Lh_rec
        tst.l   %d2                 | ARMED
        bne.w   .Lh_out             | still stopped (0 or 2)
        bsr.w   stems_layout        | latch the mask and the ring's geometry
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
        move.l  stems_wr,%d0
        sub.l   stems_rd,%d0        | frames in the ring
        cmp.l   stems_rframes,%d0
        bcs.s   .Lh_room            | fewer than capacity: one more fits
        moveq   #ERR_OVERFLOW,%d0   | the card fell behind: stop at the last whole frame
        move.l  %d0,stems_status
        moveq   #ST_FINISHING,%d0
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_room:
        addq.l  #1,%d0              | frames in the ring with this one
        cmp.l   stems_peak,%d0
        bls.s   .Lh_nopeak
        move.l  %d0,stems_peak      | the take's largest fill (the menu's status row)
.Lh_nopeak:
        move.l  PING,%d4            | the half holding this frame (Task 3)
        eori.l  #PING_XOR,%d4
        moveq   #1,%d5
        and.l   %d5,%d4
        moveq   #10,%d5
        lsl.l   %d5,%d4             | * 0x400
        addi.l  #READBACK,%d4       | this half's T1 block
        movea.l stems_wr_off,%a1
        adda.l  #stems_ring,%a1
        move.l  stems_mask,%d3
        moveq   #0,%d5              | track k's offset, k * 0x80
.Lh_trk:
        lsr.l   #1,%d3              | C = track k's bit
        bcc.w   .Lh_next
        movea.l %d4,%a0
        adda.l  %d5,%a0
| Each sample is one long on the host port: its top 16 bits, then its low
| 8 bits shifted up. Keep the top halves of L and R as one long.
        .rept   16
        move.l  (%a0)+,%d0          | L
        move.l  (%a0)+,%d1          | R
        swap    %d1
        move.w  %d1,%d0             | L top 16 : R top 16
        move.l  %d0,(%a1)+
        .endr
.Lh_next:
        addi.l  #0x80,%d5
        tst.l   %d3
        bne.w   .Lh_trk
        move.l  stems_wr_off,%d0
        add.l   stems_fbytes,%d0
        cmp.l   stems_rlimit,%d0
        bcs.s   .Lh_nowrap
        moveq   #0,%d0
.Lh_nowrap:
        move.l  %d0,stems_wr_off
        move.l  stems_wr,%d0
        addq.l  #1,%d0
        move.l  %d0,stems_wr        | publish after the data
        move.l  %d0,stems_frames
        cmpi.l  #MAX_FRAMES,%d0
        bcs.s   .Lh_out
        moveq   #ST_FINISHING,%d0   | the 60-minute cap
        move.l  %d0,stems_state
.Lh_out:
        movem.l (%sp),%d0-%d5/%a0-%a2
        lea     36(%sp),%sp
.Lh_stock:
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        rts

| ---- the layout, latched at the start edge (in the hook) ---------------
| Uses d0, d1 and a0 only. Offsets poked past this layout's wrap go to 0.
stems_layout:
        move.l  stems_tracks,%d0
        andi.l  #0xff,%d0
        bne.s   .Ll_some
        moveq   #1,%d0              | no track: T1
.Ll_some:
        move.l  %d0,stems_mask
        moveq   #0,%d1
.Ll_pop:
        lsr.l   #1,%d0
        bcc.s   .Ll_zero
        addq.l  #1,%d1
.Ll_zero:
        tst.l   %d0
        bne.s   .Ll_pop
        move.l  %d1,stems_nt
        move.l  %d1,%d0
        lsl.l   #6,%d0
        move.l  %d0,stems_fbytes
        lea     rframes_tab,%a0
        move.l  -4(%a0,%d1.l*4),%d0
        move.l  %d0,stems_rframes
        lea     rlimit_tab,%a0
        move.l  -4(%a0,%d1.l*4),%d0
        move.l  %d0,stems_rlimit
        cmp.l   stems_wr_off,%d0
        bhi.s   .Ll_wr
        clr.l   stems_wr_off
.Ll_wr:
        cmp.l   stems_rd_off,%d0
        bhi.s   .Ll_rd
        clr.l   stems_rd_off
.Ll_rd:
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

| ---- buffers: d1 = slot j in; a2 (stream buffer) or a0 (sector-0 copy) out
| Both uncached: the card may read them by DMA (STEM_REC.md 11.8).
stems_sbuf:                         | clobbers d0
        move.l  #SBUF_SIZE,%d0
        mulu.l  %d1,%d0
        movea.l %d0,%a2
        adda.l  #stems_buf+UNCACHED,%a2
        rts
stems_sec0:                         | clobbers d0
        move.l  %d1,%d0
        lsl.l   #8,%d0
        add.l   %d0,%d0             | j * 512
        movea.l %d0,%a0
        adda.l  #stems_buf+UNCACHED+SEC0_BASE,%a0
        rts

| ---- the task ------------------------------------------------------------
| Wakes every TASK_SLEEP_US. Owns the files. While RECORDING it makes the
| files at the first wake, then writes whole chunks as they fill. At
| FINISHING it writes the rest, fixes each header, and goes IDLE.
| K_DELAY(us, wait): C order, so wait is pushed first (STEM_REC.md 4.4).
stems_task:
.Lt_loop:
        pea     K_DELAY_TRY
        pea     TASK_SLEEP_US
        jsr     K_DELAY             | d0 = -1 when the timer was busy: just loop
        addq.l  #8,%sp
        bsr.w   stems_ui            | the menu's labels, every pass
        tst.l   stems_probe
        beq.s   .Lt_noprobe
        bsr.w   stems_probe_run
        clr.l   stems_probe
        bra.s   .Lt_loop
.Lt_noprobe:
        move.l  stems_state,%d0
        moveq   #ST_RECORDING,%d1
        cmp.l   %d1,%d0
        beq.s   .Lt_rec
        moveq   #ST_FINISHING,%d1
        cmp.l   %d1,%d0
        bne.s   .Lt_loop            | IDLE or ARMED
        tst.l   stems_nopen
        bne.s   .Lt_fin
        move.l  stems_wr,%d0
        cmp.l   stems_rd,%d0
        beq.s   .Lt_idle            | stopped before a frame: no files
        bsr.w   stems_start
        tst.l   %d0
        bmi.s   .Lt_drop
.Lt_fin:
        bsr.w   stems_finish
.Lt_idle:
        moveq   #1,%d0
        move.l  %d0,stems_took      | the take ended: IDLE shows its result
        clr.l   stems_state
        bra.w   .Lt_loop
.Lt_rec:
        tst.l   stems_hold
        bne.s   .Lt_loop            | test seam: hold the writer
        tst.l   stems_nopen
        bne.s   .Lt_drain
        bsr.w   stems_start
        tst.l   %d0
        bmi.s   .Lt_drop
.Lt_drain:
        move.l  #CHUNK_FRAMES,%d1
        bsr.w   stems_drain         | whole chunks only while recording
        tst.l   %d0
        bpl.w   .Lt_loop
        moveq   #ST_FINISHING,%d0   | a write failed: stop, keep what reached the card
        move.l  %d0,stems_state
        bra.w   .Lt_loop
.Lt_drop:                           | no files could be made: drop the take
        moveq   #1,%d0
        move.l  %d0,stems_took      | the take ended: IDLE shows its error
        clr.l   stems_state         | the next arm resets wr and rd; writing rd here
        bra.w   .Lt_loop            | could land after a new arm and corrupt that take

| ---- the labels, from the task (every pass) -----------------------------
| Row 1, the status and PEAK from the state. A line is rewritten only when
| what it shows changes: the state, whether a take has ended, the error,
| the take's whole seconds and the PEAK percent, packed into ui_key. A
| number is formatted into the buffer its row isn't showing, and the row's
| label pointer then switches. NO CARD and TASK FAILED change nothing in
| the key, so they stay until the next change. The screen shows a change
| at the next key (STEM_REC.md 16.1).
stems_ui:
        lea     -28(%sp),%sp
        movem.l %d2-%d6/%a2-%a3,(%sp)
        move.l  stems_state,%d2             | d2: the state
        move.l  stems_frames,%d3
        lsl.l   #4,%d3                      | 16 samples a frame
        move.l  #44100,%d0
        divu.l  %d0,%d3                     | d3: whole seconds
        moveq   #0,%d4                      | d4: PEAK percent, 0 before any take
        move.l  stems_rframes,%d0
        beq.s   .Lu_pct
        move.l  stems_peak,%d4
        moveq   #100,%d1
        mulu.l  %d1,%d4
        divu.l  %d0,%d4
.Lu_pct:
        move.l  %d3,%d5                     | d5: secs<<16 | pct<<8 | status<<3 | took<<2 | state
        moveq   #16,%d0
        lsl.l   %d0,%d5
        move.l  %d4,%d0
        lsl.l   #8,%d0
        or.l    %d0,%d5
        move.l  stems_status,%d0
        lsl.l   #3,%d0
        or.l    %d0,%d5
        move.l  stems_took,%d0
        lsl.l   #2,%d0
        or.l    %d0,%d5
        or.l    %d2,%d5
        cmp.l   ui_key,%d5
        beq.w   .Lu_out
        move.l  %d5,ui_key
        lea     rec_by_state,%a0            | row 1
        move.l  (%a0,%d2.l*4),%d0
        move.l  %d0,stems_rows
        moveq   #ST_RECORDING,%d0           | the status
        cmp.l   %d0,%d2
        beq.s   .Lu_rec
        tst.l   %d2
        bne.s   .Lu_fixed                   | ARMED, SAVING
        tst.l   stems_took
        beq.s   .Lu_fixed                   | IDLE, no take since the arm: READY
        move.l  stems_status,%d0
        beq.s   .Lu_done
        lea     err_names,%a0               | IDLE after a take that failed: its error
        move.l  (%a0,%d0.l*4),%d0
        bra.s   .Lu_stat
.Lu_fixed:
        lea     st_by_state,%a0
        move.l  (%a0,%d2.l*4),%d0
        bra.s   .Lu_stat
.Lu_rec:
        lea     fmt_rec,%a3
        bra.s   .Lu_time
.Lu_done:
        lea     fmt_done,%a3
.Lu_time:
        lea     stat_buf0,%a2               | the buffer the row isn't showing
        cmpa.l  stems_rows+ROW_LEN,%a2
        bne.s   .Lu_sbuf
        lea     stat_buf1,%a2
.Lu_sbuf:
        move.l  %d3,%d6
        moveq   #60,%d1
        divu.l  %d1,%d6                     | minutes
        move.l  %d6,%d0
        mulu.l  %d1,%d0
        move.l  %d3,%d1
        sub.l   %d0,%d1                     | seconds
        move.l  %d1,-(%sp)
        move.l  %d6,-(%sp)
        move.l  %a3,-(%sp)
        move.l  %a2,-(%sp)
        jsr     SPRINTF
        lea     16(%sp),%sp
        move.l  %a2,%d0
.Lu_stat:
        move.l  %d0,stems_rows+ROW_LEN
        lea     peak_buf0,%a2               | PEAK, formatted with every change
        cmpa.l  stems_rows+ROW_PEAK*ROW_LEN,%a2
        bne.s   .Lu_pbuf
        lea     peak_buf1,%a2
.Lu_pbuf:
        pea     pct_sign
        move.l  %d4,-(%sp)
        pea     fmt_peak
        move.l  %a2,-(%sp)
        jsr     SPRINTF
        lea     16(%sp),%sp
        move.l  %a2,stems_rows+ROW_PEAK*ROW_LEN
.Lu_out:
        movem.l (%sp),%d2-%d6/%a2-%a3
        lea     28(%sp),%sp
        rts

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

| ---- the folder path: <set>/AUDIO/<name> ------------------------------
| set = the C string at SET_PATH, used exactly as the stock save uses it
| (STEM_REC.md 5.8). d0 = 0, or -1 (empty, or too long).
stems_make_folder:
        lea     SET_PATH,%a0
        lea     stems_path,%a1
        move.l  #PATH_MAX-40,%d1    | room for /AUDIO/name/T8.wav
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
        pea     stems_name
        pea     fmt_dir
        move.l  %a1,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        moveq   #0,%d0
        rts
.Lp_fail:
        moveq   #-1,%d0
        rts

| ---- a file path: stems_path + /T<k+1>.wav, k in d3 ---------------------
stems_make_file:
        lea     stems_path,%a0
        lea     stems_fpath,%a1
.Lm_copy:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lm_copy
        subq.l  #1,%a1
        move.l  %d3,%d0
        addq.l  #1,%d0
        move.l  %d0,-(%sp)
        pea     fmt_file
        move.l  %a1,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        rts

| ---- start: name, folder, one file per latched track ---------------------
| d0 = 0 with every file open, or -1 with stems_status set and none open.
stems_start:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        clr.l   stems_nopen
        clr.l   stems_wfail
        bsr.w   stems_make_name
        bsr.w   stems_make_folder
        tst.l   %d0
        bmi.w   .Ls_path
        movea.l FS_EXISTS_PTR,%a0   | same minute as an earlier take: refuse
        pea     stems_path
        jsr     (%a0)
        addq.l  #4,%sp
        tst.l   %d0
        bne.w   .Ls_exists
        movea.l FS_MKDIR_PTR,%a0    | an error is left to the opens
        pea     stems_path
        jsr     (%a0)
        addq.l  #4,%sp
        move.l  stems_mask,%d2
        moveq   #0,%d3              | track k
.Ls_trk:
        lsr.l   #1,%d2
        bcc.w   .Ls_next
        bsr.w   stems_make_file
        pea     MODE_W
        pea     stems_fpath
        RAWCALL RAW_OPEN_PTR
        addq.l  #8,%sp
        tst.l   %d0
        ble.w   .Ls_open
        move.l  stems_nopen,%d1     | slot j
        lea     stems_handle,%a0
        move.l  %d0,(%a0,%d1.l*4)
        lea     stems_fpos,%a0
        clr.l   (%a0,%d1.l*4)
        lea     stems_slen,%a0
        moveq   #HDR_SIZE,%d0
        move.l  %d0,(%a0,%d1.l*4)   | the stream starts with the placeholder header
        bsr.w   stems_sbuf
        lea     stems_hdr,%a0
        moveq   #HDR_SIZE/4,%d0
.Ls_hdr:
        move.l  (%a0)+,(%a2)+
        subq.l  #1,%d0
        bne.s   .Ls_hdr
        addq.l  #1,stems_nopen
.Ls_next:
        addq.l  #1,%d3
        tst.l   %d2
        bne.w   .Ls_trk
        moveq   #0,%d0
        bra.s   .Ls_out
.Ls_open:
        moveq   #ERR_OPEN,%d0
        move.l  %d0,stems_status
        bsr.w   stems_close_all
        moveq   #-1,%d0
        bra.s   .Ls_out
.Ls_path:
        moveq   #ERR_PATH,%d0
        move.l  %d0,stems_status
        moveq   #-1,%d0
        bra.s   .Ls_out
.Ls_exists:
        moveq   #ERR_EXISTS,%d0
        move.l  %d0,stems_status
        moveq   #-1,%d0
.Ls_out:
        movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        rts

| ---- close every open file, as they are -----------------------------------
stems_close_all:
        move.l  %d2,-(%sp)
        moveq   #0,%d2
.Lx_trk:
        cmp.l   stems_nopen,%d2
        bcc.s   .Lx_done
        lea     stems_handle,%a0
        move.l  (%a0,%d2.l*4),-(%sp)
        RAWCALL RAW_CLOSE_PTR
        addq.l  #4,%sp
        addq.l  #1,%d2
        bra.s   .Lx_trk
.Lx_done:
        clr.l   stems_nopen
        move.l  (%sp)+,%d2
        rts

| ---- drain: frames from the ring into the stream buffers, then sectors -----
| d1 = CHUNK_FRAMES: whole chunks only (recording). d1 = 1: everything.
| d0 = 0, or -1 with ERR_WRITE set and stems_wfail = 1.
stems_drain:
        lea     -24(%sp),%sp
        movem.l %d2-%d5/%a2-%a3,(%sp)
        move.l  %d1,%d5             | the smallest batch worth taking
.Ld_more:
        cmpi.l  #CHUNK_FRAMES,%d5   | recording: the test seam holds the writer
        bne.s   .Ld_go              | between batches too, not only between passes
        tst.l   stems_hold
        bne.w   .Ld_done
.Ld_go:
        move.l  stems_wr,%d2
        sub.l   stems_rd,%d2        | frames waiting
        cmp.l   %d5,%d2
        bcs.w   .Ld_done
        cmpi.l  #CHUNK_FRAMES,%d2
        bls.s   .Ld_batch
        move.l  #CHUNK_FRAMES,%d2
.Ld_batch:
        moveq   #0,%d3              | frame within the batch
.Ld_frame:
        movea.l stems_rd_off,%a3
        adda.l  #stems_ring,%a3
        moveq   #0,%d4              | slot j
.Ld_trk:
        move.l  %d4,%d1
        bsr.w   stems_sbuf          | a2 = stream buffer j
        lea     stems_slen,%a0
        move.l  (%a0,%d4.l*4),%d0
        adda.l  %d0,%a2
        addi.l  #TRACK_BYTES,%d0
        move.l  %d0,(%a0,%d4.l*4)
        moveq   #16,%d1
.Ld_s:                              | [L1 L0 R1 R0] -> [L0 L1 R0 R1]
        move.l  (%a3)+,%d0
        BYTEREV 0
        swap    %d0
        move.l  %d0,(%a2)+
        subq.l  #1,%d1
        bne.s   .Ld_s
        addq.l  #1,%d4
        cmp.l   stems_nt,%d4
        bcs.s   .Ld_trk
        move.l  stems_rd_off,%d0
        add.l   stems_fbytes,%d0
        cmp.l   stems_rlimit,%d0
        bcs.s   .Ld_nowrap
        moveq   #0,%d0
.Ld_nowrap:
        move.l  %d0,stems_rd_off
        addq.l  #1,%d3
        cmp.l   %d2,%d3
        bcs.s   .Ld_frame
        add.l   %d2,stems_rd        | the hook may reuse these frames now
        moveq   #0,%d4
.Ld_flush:
        move.l  %d4,%d1
        moveq   #0,%d0              | whole sectors only
        bsr.w   stems_flush
        tst.l   %d0
        bmi.s   .Ld_err
        addq.l  #1,%d4
        cmp.l   stems_nt,%d4
        bcs.s   .Ld_flush
        bra.w   .Ld_more
.Ld_done:
        moveq   #0,%d0
        bra.s   .Ld_out
.Ld_err:
        moveq   #-1,%d0
.Ld_out:
        movem.l (%sp),%d2-%d5/%a2-%a3
        lea     24(%sp),%sp
        rts

| ---- flush slot d1's whole sectors; with d0 != 0, pad the tail first ------
| The file's first sector is kept in the sector-0 copy. d0 = 0, or -1.
stems_flush:
        lea     -20(%sp),%sp
        movem.l %d2-%d4/%a2-%a3,(%sp)
        move.l  %d1,%d4             | slot j
        move.l  %d0,%d3             | pad?
        bsr.w   stems_sbuf          | a2 = stream buffer j
        lea     stems_slen,%a3
        move.l  (%a3,%d4.l*4),%d2   | bytes waiting
        tst.l   %d3
        beq.s   .Lf_whole
        move.l  %d2,%d0
        andi.l  #511,%d0
        beq.s   .Lf_whole
        neg.l   %d0
        addi.l  #512,%d0            | zeros to the sector's end
        lea     (%a2,%d2.l),%a0
        add.l   %d0,%d2
.Lf_zero:
        clr.b   (%a0)+
        subq.l  #1,%d0
        bne.s   .Lf_zero
.Lf_whole:
        move.l  %d2,%d3
        lsr.l   #8,%d3
        lsr.l   #1,%d3              | whole sectors
        beq.w   .Lf_ok
        move.l  %d3,-(%sp)
        move.l  %a2,-(%sp)
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        tst.l   %d0
        bmi.s   .Lf_err
        lea     stems_fpos,%a3
        tst.l   (%a3,%d4.l*4)
        bne.s   .Lf_moved
        move.l  %d4,%d1             | the file's first sector: keep a copy
        bsr.w   stems_sec0
        movea.l %a2,%a1
        move.l  #128,%d1
.Lf_c0:
        move.l  (%a1)+,(%a0)+
        subq.l  #1,%d1
        bne.s   .Lf_c0
.Lf_moved:
        move.l  %d3,%d1
        lsl.l   #8,%d1
        add.l   %d1,%d1             | bytes written
        add.l   %d1,(%a3,%d4.l*4)
        sub.l   %d1,%d2             | the carry: 0 to 511 bytes
        lea     (%a2,%d1.l),%a0
        movea.l %a2,%a1
        move.l  %d2,%d0
        beq.s   .Lf_set
.Lf_mv:
        move.b  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.s   .Lf_mv
.Lf_set:
        lea     stems_slen,%a3
        move.l  %d2,(%a3,%d4.l*4)
.Lf_ok:
        moveq   #0,%d0
        bra.s   .Lf_out
.Lf_err:
        moveq   #ERR_WRITE,%d0
        move.l  %d0,stems_status
        moveq   #1,%d0
        move.l  %d0,stems_wfail
        moveq   #-1,%d0
.Lf_out:
        movem.l (%sp),%d2-%d4/%a2-%a3
        lea     20(%sp),%sp
        rts

| ---- finish: the rest, then per file the header, the length, close -------
stems_finish:
        lea     -16(%sp),%sp
        movem.l %d2-%d4/%a2,(%sp)
        tst.l   stems_wfail
        bne.s   .Lz_files
        moveq   #1,%d1
        bsr.w   stems_drain         | everything left
.Lz_files:
        moveq   #0,%d4
.Lz_trk:
        cmp.l   stems_nopen,%d4
        bcc.w   .Lz_done
        lea     stems_fpos,%a0
        move.l  (%a0,%d4.l*4),%d2   | on the card
        tst.l   stems_wfail
        bne.s   .Lz_len
        lea     stems_slen,%a0
        add.l   (%a0,%d4.l*4),%d2   | + the carry: the exact length
        move.l  %d4,%d1
        moveq   #1,%d0
        bsr.w   stems_flush         | the carry, padded
        tst.l   %d0
        bpl.s   .Lz_len
        lea     stems_fpos,%a0
        move.l  (%a0,%d4.l*4),%d2   | the carry failed: what is on the card
.Lz_len:
        move.l  %d2,%d3
        subi.l  #HDR_SIZE,%d3       | data bytes
        bpl.s   .Lz_pos
        moveq   #0,%d3
.Lz_pos:
        andi.l  #-4,%d3
        moveq   #HDR_SIZE,%d2
        add.l   %d3,%d2             | the length: 44 + data
        lea     stems_fpos,%a0
        tst.l   (%a0,%d4.l*4)
        beq.w   .Lz_close           | nothing on the card: no header to fix
        move.l  %d4,%d1
        bsr.w   stems_sec0
        movea.l %a0,%a2
        move.l  %d3,%d0
        BYTEREV 0
        move.l  %d0,40(%a2)         | data size, little-endian
        moveq   #36,%d0
        add.l   %d3,%d0
        BYTEREV 0
        move.l  %d0,4(%a2)          | RIFF size = 36 + data
        clr.l   -(%sp)
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_SEEK_PTR
        addq.l  #8,%sp
        tst.l   %d0
        bmi.s   .Lz_seekerr
        pea     1
        move.l  %a2,-(%sp)
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        tst.l   %d0
        bmi.s   .Lz_werr
.Lz_setlen:
        move.l  %d2,-(%sp)
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_SETLEN_PTR
        addq.l  #8,%sp
        tst.l   %d0
        bmi.s   .Lz_cerr
.Lz_close:
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_CLOSE_PTR
        addq.l  #4,%sp
        tst.l   %d0
        bpl.s   .Lz_next
        moveq   #ERR_CLOSE,%d0
        move.l  %d0,stems_status
.Lz_next:
        addq.l  #1,%d4
        bra.w   .Lz_trk
.Lz_seekerr:
        moveq   #ERR_SEEK,%d0
        move.l  %d0,stems_status
        bra.s   .Lz_setlen
.Lz_werr:
        moveq   #ERR_WRITE,%d0
        move.l  %d0,stems_status
        bra.s   .Lz_setlen
.Lz_cerr:
        moveq   #ERR_CLOSE,%d0
        move.l  %d0,stems_status
        bra.s   .Lz_close
.Lz_done:
        clr.l   stems_nopen
        clr.l   stems_wfail
        movem.l (%sp),%d2-%d4/%a2
        lea     16(%sp),%sp
        rts

| ---- the raw file routines, measured (a test seam; STEM_REC.md 12.1) -----
| Runs in the task when stems_probe is non-zero. Writes <set>/PROBE.BIN:
| three 0xAA sectors in one write, one 0xBB sector in a second write, a
| seek to 0, one 0xCC sector over sector 0, length 1000, close. Each
| routine's d0 goes to stems_probe_res, in that order.
stems_probe_run:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        lea     stems_probe_res,%a0
        moveq   #7,%d0
.Lq_clr:
        clr.l   (%a0)+
        subq.l  #1,%d0
        bne.s   .Lq_clr
        lea     SET_PATH,%a0        | <set>/PROBE.BIN
        lea     stems_fpath,%a1
.Lq_set:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lq_set
        subq.l  #1,%a1
        lea     probe_name,%a0
.Lq_name:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lq_name
        moveq   #0,%d1              | stream buffer 0: AA AA AA BB CC
        bsr.w   stems_sbuf
        movea.l %a2,%a0
        move.l  #0xaaaaaaaa,%d0
        move.l  #384,%d1
.Lq_a:  move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bne.s   .Lq_a
        move.l  #0xbbbbbbbb,%d0
        move.l  #128,%d1
.Lq_b:  move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bne.s   .Lq_b
        move.l  #0xcccccccc,%d0
        move.l  #128,%d1
.Lq_c:  move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bne.s   .Lq_c
        pea     MODE_W
        pea     stems_fpath
        RAWCALL RAW_OPEN_PTR
        addq.l  #8,%sp
        move.l  %d0,stems_probe_res
        move.l  %d0,%d2             | the handle
        ble.w   .Lq_out
        pea     3
        move.l  %a2,-(%sp)
        move.l  %d2,-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        move.l  %d0,stems_probe_res+4
        pea     1
        pea     1536(%a2)
        move.l  %d2,-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        move.l  %d0,stems_probe_res+8
        clr.l   -(%sp)
        move.l  %d2,-(%sp)
        RAWCALL RAW_SEEK_PTR
        addq.l  #8,%sp
        move.l  %d0,stems_probe_res+12
        pea     1
        pea     2048(%a2)
        move.l  %d2,-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        move.l  %d0,stems_probe_res+16
        pea     1000
        move.l  %d2,-(%sp)
        RAWCALL RAW_SETLEN_PTR
        addq.l  #8,%sp
        move.l  %d0,stems_probe_res+20
        move.l  %d2,-(%sp)
        RAWCALL RAW_CLOSE_PTR
        addq.l  #4,%sp
        move.l  %d0,stems_probe_res+24
.Lq_out:
        movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        rts
