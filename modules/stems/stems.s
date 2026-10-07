| STEM REC -- the enabled tracks to the card while the sequencer plays. The
| build records all eight by default (stems_tracks = 0xFF).
|
| Design: git show 4d2d6456:docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md
| (streaming), over git show 4d2d6456:docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md.
| Every stock address below, with its evidence: docs/firmware/STEM_REC.md.
|
| Three parts share the state words below:
|   stems_action      MAIN MENU > STEMS > REC, in the UI task; stems_source_action
|                     T1-T8, MAIN, CUE, AB, CD; stems_switch_action the format
|   stems_frame_hook  the per-frame tap, in the audio interrupt at IPL 5
|   stems_task        our own RTOS task: the ring to the card, while recording
| The state is one aligned long, so every read and write of it is one
| instruction. The action and the hook write it; the task writes IDLE, and
| FINISHING when a card write fails.

| ---- stock facts (docs/firmware/STEM_REC.md) ----------------------------
        .equ    TRANSPORT,     0x800065b8   | long; 1 = running, 0 or 2 = stopped (Task 2)
        .equ    TRANSPORT_RUNNING, 1        | the ONLY value that means playing   (Task 2)
        .equ    MASTER_TRK,    0x80000034   | byte; non-zero = MASTER TRACK on: MAIN is T8 alone (18.8)
        .equ    CARD_MOUNTED,  0x460d1cb8   | long; 0 = no card                   (Task 8)
        .equ    FRAME_ROUTINE, 0x400031a0   | the displaced call
        .equ    MODE_W,        0x400b328b   | "w": opens without truncating
        .equ    PING,          0x800000e0   | the read-back half selector  (Task 3)
        .equ    PING_XOR,      0            | half = (PING ^ PING_XOR) & 1  (Task 3)
        .equ    READBACK,      0x80003190   | track k's block at READBACK + half*0x400 + k*0x80 (9.2)
        .equ    LV_PAGES,      0x80005460   | the level pages, 0x80 bytes each (STEM_REC.md 18.1)
        .equ    LV_NPAGES,     4            | four of them; the sent index passes 4 inside one routine (18.1)
        .equ    LV_SENT,       0x80004804   | long: the page channel 0 sends this frame (18.1)
        .equ    IN_RING,       0x80005660   | the inputs, eight 0x100-byte pages: C D longs, then A B at +0x80 (18.7)
        .equ    IN_IDX,        0x46104d00   | long: the page eDMA channel 7 was last pointed at (18.7)
        .equ    BUS,           0x80005e60   | channel 6's buffer: MAIN +0x00, CUE +0x80 (18.6)
        .equ    IN_AB_OFF,     0x80         | inputs A and B within a ring page (18.7)
        .equ    IN_CD_OFF,     0x00         | inputs C and D within a ring page (18.7)
        .equ    IN_A_IS_LEFT,  1            | A (and C) in the pair's first long (18.7)
        .equ    IN_A_OFF,      4-4*IN_A_IS_LEFT
        .equ    IN_B_OFF,      4*IN_A_IS_LEFT
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
        .equ    DTCN3,         0xfc07c00c   | DMA timer 3: free-running at the bus clock (modules/cfmeter)
        .equ    BUS_MHZ,       132          | its counts a microsecond: 7.58 ns a count
        .equ    CARD_UDMA,     0x46c85c8c   | byte: the card's Ultra DMA mode, if any (STEM_REC.md 11.7)
        .equ    CARD_MWDMA,    0x46c85c8b   | byte: its multiword DMA mode, if any
        .equ    CARD_SPC,      0x46107990   | byte: the mounted volume's sectors a cluster: the raw
                                            | write returns it << 9 (0x40018e28; 2,048 on FAT16 and
                                            | 512 on FAT32 in STEM_REC.md 12.1). The file layer sends
                                            | the card one command a cluster (perf probe, 7 Oct 2026)

| ---- constants -----------------------------------------------------------
        .equ    ST_IDLE,       0
        .equ    ST_ARMED,      1
        .equ    ST_RECORDING,  2
        .equ    ST_FINISHING,  3
        .equ    RING_SIZE,     0x800000     | = DramRegion stems_ring (piece 5: 8 MiB)
        .equ    MAX_FILES,     14
        .equ    FB_MAX,        96           | one file's frame at most: 16 stereo 24-bit samples
        .equ    K_MAIN,        8            | the kinds after the tracks: MAIN, CUE, AB, CD, then A B C D
        .equ    K_AB,          10
        .equ    K_A,           12
        .equ    SRC_BITS,      0xfff        | the sources a take may latch: T1-T8, MAIN, CUE, AB, CD
        .equ    MAX_FRAMES,    9922500      | 60 minutes
        .equ    CHUNK_FRAMES,  512          | frames per write while recording
        .equ    SBUF_SIZE,     CHUNK_FRAMES*FB_MAX+512  | one file's stream buffer: a chunk plus a carry
        .equ    SEC0_BASE,     MAX_FILES*SBUF_SIZE      | the sector-0 copies follow the stream buffers
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
| MAIN at hook frame f is core 0's mix of the half PING doesn't name as
| that half read at frame f-1, times the gains of the page sent at f-2
| (18.5). Both are known at f-1, so the hook stages each track's share of
| ring frame f+1 at frame f: from the half PING doesn't name now, with the
| gains of the page before the newest (the perf design, 1.1).
        .equ    GAIN_LAG,      1            | frames before the newest mirrored page, when the tracks are staged
        .equ    TRACK_HALF,    1            | the samples core 0 mixes: the half PING doesn't name (18.5)
        .equ    GQ_N,          4            | frames of per-sample gains kept; GAIN_LAG < GQ_N
        .equ    GQ_SLOT,       0x80         | one slot's gains: their bound (stems_mirror), 16 gains, padding
        .equ    GQ_FRAME,      8*GQ_SLOT    | one frame of gains: 8 slots, at k * 0x80 like the samples
        .equ    LIM_FREE,      0x200000     | 0 <= g <= this: lim(floor(g*x / 2^21)) never limits (design 1.3)
        .if     GQ_FRAME != 1024            | stems_stage multiplies by a shift
        .error  "GQ_FRAME is not 1024"
        .endif
        .equ    MACSR_FRAC,    0x20         | fractional, truncating: the frame interrupt's own mode
        .equ    TRACE_N,       64           | test seam: frames stems_trace records
        .equ    TRACE_B,       64           | bytes a traced frame

| ColdFire byterev is ISA_A+ and -mcpu=5407 does not accept it, so it is
| encoded by hand: opcode 0x02C0 | reg (SAMPLE_SAVE.md section 3).
        .macro  BYTEREV reg          | reg = 0..7, a data register number
        .short  0x02c0 + \reg
        .endm
        .macro  RAWCALL ptr
        movea.l \ptr,%a0
        jsr     (%a0)
        .endm
| The mirror's EMAC, entered at its first multiply in a page: a page whose
| targets are all cached multiplies nothing and leaves the EMAC alone (the
| perf round). Clobbers the condition codes only.
        .macro  EMAC_ON
        tst.l   stems_gemac
        bne.s   .Le\@
        bsr.w   stems_emac_in
        addq.l  #1,stems_gemac
.Le\@:
        .endm

| A value limited to 16 bits: one compare on the common path. Uses d0.
        .macro  LIM16 reg
        move.l  \reg,%d0
        addi.l  #0x8000,%d0
        cmpi.l  #0xffff,%d0
        bls.s   .Ll16\@
        tst.l   \reg
        smi     \reg
        extb.l  \reg                        | -1 below the range, 0 above
        eori.l  #0x7fff,\reg                | 0x7fff above, -0x8000 below
.Ll16\@:
        .endm

| A value limited to 24 bits. Uses d0.
        .macro  LIM24 reg
        move.l  \reg,%d0
        addi.l  #0x800000,%d0
        cmpi.l  #0xffffff,%d0
        bls.s   .Ll24\@
        tst.l   \reg
        smi     \reg
        extb.l  \reg
        eori.l  #0x7fffff,\reg              | 0x7fffff above, -0x800000 below
.Ll24\@:
        .endm

| Two 24-bit values (right-justified) as six bytes, big-endian, at (a1)+:
| three word stores, so every store stays word-aligned. Uses d0; changes a.
        .macro  PACK6 a, b
        move.l  \a,%d0
        asr.l   #8,%d0
        move.w  %d0,(%a1)+                  | a's top 16
        lsl.l   #8,\a
        move.l  \b,%d0
        swap    %d0                         | b's top byte, in the low byte
        move.b  %d0,\a
        move.w  \a,(%a1)+                   | a's low 8 : b's top 8
        move.w  \b,(%a1)+                   | b's low 16
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
        .global stems_fmt, stems_nf, stems_ftab, stems_fbytes
stems_tracks:    .long   0xFF       | the sources: bits 0-7 T1-T8, 8 MAIN, 9 CUE, 10 AB, 11 CD
stems_fmt:       .long   6          | bit 0 24 BIT, bit 1 AB STEREO, bit 2 CD STEREO
stems_hold:      .long   0          | test seam: non-zero pauses the writer while RECORDING
        .global stems_trace, stems_trace_buf
stems_trace:     .long   0          | test seam: 1..TRACE_N records that frame into stems_trace_buf, then counts on
stems_trace_buf: .space  TRACE_N*TRACE_B
        .global stems_gstate, stems_gq, stems_gqn, stems_gqok, stems_lvskip, stems_staged
stems_lvlast:    .long   -1         | the last page index mirrored
stems_lvskip:    .long   0          | test seam: page-index steps other than +1 or a wrap to 0
stems_gw29:      .long   -1         | the MAIN level the cached targets were computed with
stems_gm2:       .long   0          | its square
stems_gcache:    .space  8*8        | per slot: w1 << 16 | w2, then its target
        .global stems_gsel
stems_gsel:      .long   0          | 0 or 96: stems_gstate + stems_gsel is the current state
stems_gstate:    .space  2*8*12     | two states, used in turn: per slot split, increment, gain
                                    | (core 0's X:0x3dd+5k words 0, 2, 4); the other is the frame before
stems_gqn:       .long   0          | frames written to stems_gq
stems_gqok:      .long   0          | frames written to stems_gq since IDLE: the start edge needs 2
stems_gq:        .space  GQ_N*GQ_FRAME
stems_emac_save: .space  16         | the caller's MACSR, ACC0, ACC1, ACCEXT01
stems_gemac:     .long   0          | 1 while the mirror holds the EMAC (EMAC_ON)
stems_staged:    .long   0          | 1: the ring frame at stems_wr_off holds the next frame's tracks
        .include "remix.inc"        | stems_gtab: core 0's gain table, from the user's image (18.4)
        .balign 4
stems_lsrc:      .long   0          | the sources latched at the start
stems_lfmt:      .long   0          | the format latched at the start
stems_nf:        .long   0          | files in the take
stems_ftab:      .space  4*MAX_FILES  | per file: kind << 24 | channels << 16 | bytes per frame
        .global stems_ffn, stems_farg, stems_ntrk, stems_tbytes
stems_ffn:       .space  4*MAX_FILES  | per file: the routine that writes its frame
stems_farg:      .space  4*MAX_FILES  | per file: its d5, k * 0x80 for a track, the kind for a bus
stems_ntrk:      .long   0          | the track files, first in the table
stems_tbytes:    .long   0          | their bytes in a ring frame: the buses' part starts there
        .equ    STEMS_FN_OFF,  stems_ffn-stems_ftab-4   | from just past an ftab entry to its ffn
        .equ    STEMS_ARG_OFF, stems_farg-stems_ftab-4  | ... and to its farg
stems_fbytes:    .long   0          | a ring frame: the sum of the files' frames
stems_rframes:   .long   0          | the ring's capacity in frames
stems_rlimit:    .long   0          | stems_rframes x stems_fbytes: offsets wrap here
stems_wr_off:    .long   0          | the hook's next frame, a byte offset into the ring
stems_rd_off:    .long   0          | the task's next frame
stems_nopen:     .long   0          | files open
stems_wfail:     .long   0          | a card write failed: finish without writing more
stems_handle:    .space  4*MAX_FILES  | one per open file, in file order
stems_slen:      .space  4*MAX_FILES  | bytes waiting in each stream buffer
stems_fpos:      .space  4*MAX_FILES  | bytes of each file on the card
stems_tcb:       .space  TCB_SIZE   | zero until the one create (STEM_REC.md 3.8)
stems_probe:     .long   0          | test seam: non-zero runs stems_probe_run once
stems_probe_res: .space  28
        .global stems_took, stems_ui_bufs
stems_took:      .long   0          | a take ended since the last arm: IDLE shows its result
        .global stems_m8last
stems_m8last:    .long   0          | the MASTER TRACK byte T8's row was last drawn for

| ---- the readout, STATS.TXT (perf design 3): cleared at each arm ----------
| Times in DTCN3 counts unless named; sums of counts are 64 bits, hi:lo.
        .global stems_st, stems_st_n, stems_st_wn
stems_st:
stems_st_on:     .long   0          | 1 while this frame records: the hook times it
stems_st_t0:     .long   0          | DTCN3 at the hook's entry
stems_st_hmax:   .long   0          | the hook's longest frame
stems_st_hsum:   .long   0, 0       | the hook's frames, summed
stems_st_fmax:   .long   0          | the hook and the stock frame routine after it, longest
stems_st_fsum:   .long   0, 0       | ... summed
stems_st_n:      .long   0          | frames timed
stems_st_wn:     .long   0          | card writes, the raw write calls
stems_st_wsum:   .long   0          | their time, microseconds
stems_st_wmax:   .long   0          | the longest
stems_st_csum:   .long   0          | the writer's copy, microseconds
stems_st_cmax:   .long   0          | its longest batch
stems_st_smax:   .long   0          | the writer's longest sleep while recording (it asks TASK_SLEEP_US)
stems_st_end:
        .equ    ST_LONGS,      (stems_st_end-stems_st)/4
ui_key:          .long   -1         | what the labels last showed, packed (stems_ui)
stems_ui_bufs:                      | two buffers for each formatted line
stat_buf0:       .space  16
stat_buf1:       .space  16
peak_buf0:       .space  16
peak_buf1:       .space  16
stems_name:      .space  16         | YYMMDD-HHMM
stems_path:      .space  PATH_MAX   | <set>/AUDIO/<name>
stems_fpath:     .space  PATH_MAX   | <set>/AUDIO/<name>/<file>.wav
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
        .balign 4
bus_names:  .long   nm_main, nm_cue, nm_ab, nm_cd, nm_a, nm_b, nm_c, nm_d
nm_main:    .asciz  "/MAIN.wav"
nm_cue:     .asciz  "/CUE.wav"
nm_ab:      .asciz  "/AB.wav"
nm_cd:      .asciz  "/CD.wav"
nm_a:       .asciz  "/A.wav"
nm_b:       .asciz  "/B.wav"
nm_c:       .asciz  "/C.wav"
nm_d:       .asciz  "/D.wav"
        .balign 4
| Where each bus kind's first long is: MAIN and CUE absolute; an input, its
| offset within the ring page channel 7 filled this frame.
bus_src:    .long   BUS, BUS+0x80, IN_AB_OFF, IN_CD_OFF
            .long   IN_AB_OFF+IN_A_OFF, IN_AB_OFF+IN_B_OFF, IN_CD_OFF+IN_A_OFF, IN_CD_OFF+IN_B_OFF
        .balign 2

| ---- the STEMS category (git show 4d2d6456:docs/superpowers/specs/2026-09-28-stem-rec-menu-design.md)
| A fifth MAIN MENU category. The manifest's TableGrow gives the root a row
| pointing at stems_cat_label, stems_icon and stems_list. The list and its
| rows live here, in DRAM: the menu engine writes the list's cursor
| fields, and STEM REC rewrites the rows' labels. A label changes by one
| aligned long write to the row's +0x00, so a redraw reads a whole old
| label or a whole new one. The menu redraws on keys only (STEM_REC.md
| 16.1): a label the task changes shows at the next key.
        .equ    ROW_LEN,       24           | a menu row (MAINMENU.md 1)
        .equ    MENU_ROWS,     18
        .equ    MENU_VISIBLE,  7            | a submenu pane's rows
        .equ    ROW_SRC0,      2            | T1's row; the sources T1-T8, MAIN, CUE, AB, CD follow
        .equ    NSRC,          12
        .equ    ROW_SW0,       14           | AB STEREO; CD STEREO and 24 BIT follow
        .equ    ROW_PEAK,      17           | PEAK: the last row
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
        .long   trk1_on, 0, stems_source_action, 0, 0, 0
        .long   trk2_on, 0, stems_source_action, 0, 0, 0
        .long   trk3_on, 0, stems_source_action, 0, 0, 0
        .long   trk4_on, 0, stems_source_action, 0, 0, 0
        .long   trk5_on, 0, stems_source_action, 0, 0, 0
        .long   trk6_on, 0, stems_source_action, 0, 0, 0
        .long   trk7_on, 0, stems_source_action, 0, 0, 0
        .long   trk8_on, 0, stems_source_action, 0, 0, 0
        .long   main_off, 0, stems_source_action, 0, 0, 0
        .long   cue_off, 0, stems_source_action, 0, 0, 0
        .long   ab_off, 0, stems_source_action, 0, 0, 0
        .long   cd_off, 0, stems_source_action, 0, 0, 0
        .long   abst_on, 0, stems_switch_action, 0, 0, 0
        .long   cdst_on, 0, stems_switch_action, 0, 0, 0
        .long   b24_off, 0, stems_switch_action, 0, 0, 0
        .long   lbl_peak0, 0, 0, 0, 0, 0    | PEAK: a heading, the last row, which the cursor never reaches
rec_by_state:   .long   lbl_rec, lbl_cancel, lbl_stop, lbl_saving       | row 1, by state
st_by_state:    .long   lbl_ready, lbl_armed, 0, lbl_saving             | the status; RECORDING is the task's
err_names:      .long   0, err_ring, err_path, err_open, err_exists, err_write, err_seek, err_close, err_task
src_on:         .long   trk1_on, trk2_on, trk3_on, trk4_on, trk5_on, trk6_on, trk7_on, trk8_on
                .long   main_on, cue_on, ab_on, cd_on
src_off:        .long   trk1_off, trk2_off, trk3_off, trk4_off, trk5_off, trk6_off, trk7_off, trk8_off
                .long   main_off, cue_off, ab_off, cd_off
sw_bit:         .long   1, 2, 0     | rows 14-16: AB STEREO, CD STEREO, 24 BIT in stems_fmt
sw_on:          .long   abst_on, cdst_on, b24_on
sw_off:         .long   abst_off, cdst_off, b24_off
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
trk8_master: .asciz "T8 MASTER"         | MASTER TRACK on: T8 is MAIN, not a source
main_on:  .asciz "MAIN [X]"
main_off: .asciz "MAIN [ ]"
cue_on:   .asciz "CUE [X]"
cue_off:  .asciz "CUE [ ]"
ab_on:    .asciz "AB [X]"
ab_off:   .asciz "AB [ ]"
cd_on:    .asciz "CD [X]"
cd_off:   .asciz "CD [ ]"
abst_on:  .asciz "AB STEREO [X]"
abst_off: .asciz "AB STEREO [ ]"
cdst_on:  .asciz "CD STEREO [X]"
cdst_off: .asciz "CD STEREO [ ]"
b24_on:   .asciz "24 BIT [X]"
b24_off:  .asciz "24 BIT [ ]"
fmt_rec:        .asciz  "REC %02d:%02d"
fmt_done:       .asciz  "DONE %02d:%02d"
fmt_peak:       .asciz  "PEAK %d%s"         | "%" as an argument: %% is untested in the stock sprintf
| STATS.TXT (perf design 3), a line each
nm_stats:       .asciz  "/STATS.TXT"
lbl_ok:         .asciz  "OK"
st_f_take:      .asciz  "STEM REC STATS %s\r\n"
st_f_status:    .asciz  "status %s\r\n"
st_f_take2:     .asciz  "%d frames, %d s, %d files, %d bits\r\n"
st_f_ring:      .asciz  "ring peak %d of %d frames\r\n"
st_f_writes:    .asciz  "card writes %d, %d ms in all, longest %d us\r\n"
st_f_copy:      .asciz  "writer copy %d ms in all, longest batch %d us\r\n"
st_f_sleep:     .asciz  "writer longest sleep %d us, asks %d\r\n"
st_f_hook:      .asciz  "hook mean %d us, longest %d us\r\n"
st_f_frame:     .asciz  "hook and frame routine mean %d us, longest %d us, %d frames\r\n"
st_f_card:      .asciz  "card udma %d mwdma %d, cluster %d sectors\r\n"
        .even
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
        lea     stems_st,%a0        | the readout starts over
        moveq   #ST_LONGS,%d1
.La_st:
        clr.l   (%a0)+
        subq.l  #1,%d1
        bne.s   .La_st
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

| ---- a source row's action (T1-T8, MAIN, CUE, AB, CD): action(0), in the
| UI task. The row under the cursor names the source (the list's absolute
| selection, less T1's row, as octalab's checkbox rows do). Locked while a
| take records or saves: the take keeps the sources it latched at its
| start, and the rows show what records. The last source that's on stays
| on, so a take always has a file the rows show. The test and the flip run
| with interrupts masked, so the hook can't latch between them. With
| MASTER TRACK on, T8's row reads T8 MASTER (stems_m8check) and does
| nothing: T8 is MAIN then, and a take doesn't record it (stems_layout).
        .global stems_source_action
stems_source_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  stems_list+LIST_SEL,%d3
        subq.l  #ROW_SRC0,%d3               | source k, 0..11
        moveq   #NSRC,%d0
        cmp.l   %d0,%d3
        bcc.s   .Lk_out                     | not a source row (unsigned: below T1 too)
        move.w  %sr,%d2
        move.w  #0x2700,%sr
        move.l  stems_state,%d1
        moveq   #ST_RECORDING,%d0
        cmp.l   %d0,%d1
        bcc.s   .Lk_keep                    | RECORDING or FINISHING: locked
        moveq   #7,%d0
        cmp.l   %d0,%d3
        bne.s   .Lk_flip
        tst.b   MASTER_TRK
        bne.s   .Lk_keep                    | T8 with MASTER TRACK on: MAIN, not a source
.Lk_flip:
        moveq   #1,%d0
        lsl.l   %d3,%d0                     | the source's bit
        move.l  stems_tracks,%d1
        eor.l   %d0,%d1
        movea.l %d1,%a0                     | the new word
        andi.l  #0xfff,%d1
        beq.s   .Lk_keep                    | the last source on: it stays on
        move.l  %a0,stems_tracks
        move.w  %d2,%sr
        lea     src_off,%a1
        move.l  %a0,%d1
        and.l   %d0,%d1
        beq.s   .Lk_label
        lea     src_on,%a1
.Lk_label:
        movea.l (%a1,%d3.l*4),%a0           | the label
        move.l  %d3,%d1
        addq.l  #ROW_SRC0,%d1
        moveq   #ROW_LEN,%d0
        mulu.l  %d0,%d1
        movea.l %d1,%a1
        adda.l  #stems_rows,%a1
        move.l  %a0,(%a1)                   | the row's label pointer
        bra.s   .Lk_out
.Lk_keep:
        move.w  %d2,%sr
.Lk_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| ---- a switch row's action (AB STEREO, CD STEREO, 24 BIT): action(0) -------
| Flips its bit of stems_fmt; locked while a take records or saves, as the
| source rows are.
        .global stems_switch_action
stems_switch_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  stems_list+LIST_SEL,%d3
        subi.l  #ROW_SW0,%d3                | switch k, 0..2
        moveq   #3,%d0
        cmp.l   %d0,%d3
        bcc.s   .Lw_out
        move.w  %sr,%d2
        move.w  #0x2700,%sr
        move.l  stems_state,%d1
        moveq   #ST_RECORDING,%d0
        cmp.l   %d0,%d1
        bcc.s   .Lw_keep                    | locked while a take records or saves
        lea     sw_bit,%a0
        move.l  (%a0,%d3.l*4),%d1
        moveq   #1,%d0
        lsl.l   %d1,%d0                     | the format's bit
        move.l  stems_fmt,%d1
        eor.l   %d0,%d1
        move.l  %d1,stems_fmt
        move.w  %d2,%sr
        lea     sw_off,%a1
        and.l   %d0,%d1
        beq.s   .Lw_label
        lea     sw_on,%a1
.Lw_label:
        movea.l (%a1,%d3.l*4),%a0
        move.l  %d3,%d1
        addi.l  #ROW_SW0,%d1
        moveq   #ROW_LEN,%d0
        mulu.l  %d0,%d1
        movea.l %d1,%a1
        adda.l  #stems_rows,%a1
        move.l  %a0,(%a1)
        bra.s   .Lw_out
.Lw_keep:
        move.w  %d2,%sr
.Lw_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| ---- the frame hook: in the audio interrupt, IPL 5 ---------------------
| Reached by `jsr` from 0x40004b12. Calls nothing but the routine it
| displaced; uses no RTOS service; loops are bounded (8 tracks). Every
| frame it mirrors core 0's gains (stems_mirror); in IDLE that and two
| tests are its whole cost. The copy runs BEFORE the stock routine, which
| reads the same block.
|
| While recording, frame f finishes ring frame f, which frame f-1 staged
| with the tracks' shares: MAIN, CUE and the inputs of frame f go into its
| buses' part, and it is published. Then the tracks of frame f+1 are
| staged into the next ring frame (GAIN_LAG). Staging reserves that
| frame, so the room test comes before it: a take stops when the next
| frame doesn't fit, at the last whole frame. A staged frame of a take
| that stops is never published.
|
| A recording frame is timed on DTCN3 for the readout: the hook from its
| entry, and the hook with the stock frame routine after it (stems_st_on).
        .global stems_frame_hook
stems_frame_hook:
        tst.l   stems_state
        beq.w   .Lh_idle            | IDLE: the mirror only, and stock
        move.l  %d0,-(%sp)
        move.l  DTCN3,%d0
        move.l  %d0,stems_st_t0
        move.l  (%sp)+,%d0
        clr.l   stems_st_on
        bsr.w   stems_mirror
        tst.l   stems_trace
        beq.s   .Lh_notrace
        bsr.w   stems_trace_frame
.Lh_notrace:
        bsr.w   stems_m8check
        lea     -56(%sp),%sp
        movem.l %d0-%d7/%a0-%a5,(%sp)
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
        bsr.w   stems_layout        | latch the layout
        moveq   #ST_RECORDING,%d0
        move.l  %d0,stems_state
        clr.l   stems_staged
        moveq   #2,%d0
        cmp.l   stems_gqok,%d0
        bhi.w   .Lh_out             | the page before this one has no gains (REC while
                                    | playing): stage on the next frame, one frame later
        bra.w   .Lh_stage           | the take's first frame is the next one, as before
.Lh_rec:                            | RECORDING
        tst.l   %d2
        beq.s   .Lh_play
        moveq   #ST_FINISHING,%d0   | the sequencer stopped: 0 (end, rewind) or 2 (STOP key)
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_play:
        moveq   #1,%d0
        move.l  %d0,stems_st_on     | a recording frame: time it
        tst.l   stems_staged
        beq.s   .Lh_stage           | nothing staged yet: the take starts at the next frame
        movea.l stems_wr_off,%a1
        adda.l  stems_tbytes,%a1
        adda.l  #stems_ring,%a1     | this ring frame's buses
        bsr.w   stems_bus_frame
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
        move.l  %d0,%d1
        sub.l   stems_rd,%d0        | frames in the ring, this one included
        cmp.l   stems_peak,%d0
        bls.s   .Lh_nopeak
        move.l  %d0,stems_peak      | the take's largest fill (the menu's PEAK row)
.Lh_nopeak:
        cmpi.l  #MAX_FRAMES,%d1
        bcc.s   .Lh_fin             | the 60-minute cap
        cmp.l   stems_rframes,%d0
        bcs.s   .Lh_stage           | fewer than capacity: the next frame fits
        moveq   #ERR_OVERFLOW,%d0   | the card fell behind: stop at the last whole frame
        move.l  %d0,stems_status
.Lh_fin:
        moveq   #ST_FINISHING,%d0
        move.l  %d0,stems_state
        bra.s   .Lh_out
.Lh_stage:
        movea.l stems_wr_off,%a1
        adda.l  #stems_ring,%a1
        bsr.w   stems_stage         | the tracks of the next ring frame
        moveq   #1,%d0
        move.l  %d0,stems_staged
.Lh_out:
        tst.l   stems_st_on
        beq.s   .Lh_rest
        move.l  DTCN3,%d0
        sub.l   stems_st_t0,%d0     | the hook's own time this frame
        cmp.l   stems_st_hmax,%d0
        bls.s   .Lh_hm
        move.l  %d0,stems_st_hmax
.Lh_hm:
        add.l   %d0,stems_st_hsum+4
        bcc.s   .Lh_rest
        addq.l  #1,stems_st_hsum
.Lh_rest:
        movem.l (%sp),%d0-%d7/%a0-%a5
        lea     56(%sp),%sp
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        tst.l   stems_st_on
        beq.s   .Lh_ret
        move.l  %d0,-(%sp)
        move.l  DTCN3,%d0
        sub.l   stems_st_t0,%d0     | with the stock frame routine
        cmp.l   stems_st_fmax,%d0
        bls.s   .Lh_fm
        move.l  %d0,stems_st_fmax
.Lh_fm:
        add.l   %d0,stems_st_fsum+4
        bcc.s   .Lh_fc
        addq.l  #1,stems_st_fsum
.Lh_fc:
        addq.l  #1,stems_st_n
        move.l  (%sp)+,%d0
.Lh_ret:
        rts
.Lh_idle:
        bsr.w   stems_mirror
        tst.l   stems_trace
        beq.s   .Lh_m8
        bsr.w   stems_trace_frame
.Lh_m8:
        bsr.w   stems_m8check
.Lh_stock:
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        rts

| ---- T8's row against MASTER TRACK, from the hook every frame -----------
| On a change of the MASTER TRACK byte, T8's label becomes T8 MASTER, or
| T8 [X] / T8 [ ] by its bit, which the row keeps underneath. The hook
| runs from boot, so the row is right before the writer task exists.
| Every register is kept.
stems_m8check:
        move.l  %d0,-(%sp)
        moveq   #0,%d0
        move.b  MASTER_TRK,%d0
        cmp.l   stems_m8last,%d0
        beq.s   .Lm8_out            | no change
        move.l  %d0,stems_m8last
        move.l  %a0,-(%sp)
        lea     trk8_master,%a0
        tst.l   %d0
        bne.s   .Lm8_set
        lea     trk8_off,%a0
        move.l  stems_tracks,%d0
        btst    #7,%d0
        beq.s   .Lm8_set
        lea     trk8_on,%a0
.Lm8_set:
        move.l  %a0,stems_rows+(ROW_SRC0+7)*ROW_LEN
        movea.l (%sp)+,%a0
.Lm8_out:
        move.l  (%sp)+,%d0
        rts

| ---- the layout, latched at the start edge (in the hook) ---------------
| The sources (with MASTER TRACK on, T8 left out, or MAIN for T8 alone)
| and the format, then the file table in file order (T1..T8,
| MAIN, CUE, AB or A B, CD or C D), the ring frame and the ring's capacity;
| then each file's routine and argument (stems_ffn, stems_farg), the track
| files' count and their part of a ring frame. Uses d0-d4 and a0-a2.
| Offsets past this layout's wrap go to 0.
stems_layout:
        move.l  stems_tracks,%d0
        andi.l  #SRC_BITS,%d0
        tst.b   MASTER_TRK
        beq.s   .Ll_any
        andi.l  #SRC_BITS-0x80,%d0  | MASTER TRACK on: T8 is MAIN (T8.wav would equal MAIN.wav)
        bne.s   .Ll_some
        move.l  #0x100,%d0          | T8 alone: MAIN, the same audio
        bra.s   .Ll_some
.Ll_any:
        tst.l   %d0
        bne.s   .Ll_some
        moveq   #1,%d0              | no source: T1
.Ll_some:
        move.l  %d0,stems_lsrc
        move.l  stems_fmt,%d2
        andi.l  #7,%d2
        move.l  %d2,stems_lfmt
        moveq   #32,%d3             | one channel's frame: 16 samples of 2 bytes,
        btst    #0,%d2
        beq.s   .Ll_w
        moveq   #48,%d3             | or of 3 with 24 BIT
.Ll_w:
        lea     stems_ftab,%a0
        moveq   #0,%d1              | the kind
.Ll_src:
        btst    %d1,%d0
        beq.s   .Ll_next
        cmpi.l  #K_AB,%d1
        bcs.s   .Ll_stereo          | a track, MAIN or CUE: stereo
        move.l  %d1,%d2
        subi.l  #K_AB-1,%d2         | the format bit: 1 for AB, 2 for CD
        btst    %d2,stems_lfmt+3
        bne.s   .Ll_stereo          | the pair as one stereo file
        move.l  %d1,%d2             | two mono files: A B (or C D)
        subi.l  #K_AB,%d2
        add.l   %d2,%d2
        addi.l  #K_A,%d2
        swap    %d2
        lsl.l   #8,%d2
        ori.l   #0x10000,%d2
        add.l   %d3,%d2
        move.l  %d2,(%a0)+
        addi.l  #0x01000000,%d2     | the pair's second input
        move.l  %d2,(%a0)+
        bra.s   .Ll_next
.Ll_stereo:
        move.l  %d1,%d2
        swap    %d2
        lsl.l   #8,%d2              | kind << 24
        ori.l   #0x20000,%d2        | two channels
        add.l   %d3,%d2
        add.l   %d3,%d2
        move.l  %d2,(%a0)+
.Ll_next:
        addq.l  #1,%d1
        cmpi.l  #K_AB+2,%d1
        bne.s   .Ll_src
        move.l  %a0,%d0
        subi.l  #stems_ftab,%d0
        lsr.l   #2,%d0
        move.l  %d0,stems_nf
        moveq   #0,%d2              | the ring frame
        lea     stems_ftab,%a0
.Ll_sum:
        moveq   #0,%d1
        move.w  2(%a0),%d1
        add.l   %d1,%d2
        addq.l  #4,%a0
        subq.l  #1,%d0
        bne.s   .Ll_sum
        move.l  %d2,stems_fbytes
        move.l  #RING_SIZE,%d0
        divu.l  %d2,%d0
        move.l  %d0,stems_rframes
        mulu.l  %d2,%d0
        move.l  %d0,stems_rlimit
        cmp.l   stems_wr_off,%d0
        bhi.s   .Ll_wr
        clr.l   stems_wr_off
.Ll_wr:
        cmp.l   stems_rd_off,%d0
        bhi.s   .Ll_rd
        clr.l   stems_rd_off
.Ll_rd:                             | each file's routine and argument; the tracks' part
        movea.l #stems_track16,%a1
        movea.l #stems_bus16,%a2
        move.l  stems_lfmt,%d0
        btst    #0,%d0
        beq.s   .Ll_16
        movea.l #stems_track24,%a1
        movea.l #stems_bus24,%a2
.Ll_16:
        lea     stems_ftab,%a0
        moveq   #0,%d0              | track files
        moveq   #0,%d3              | their bytes in a ring frame
        move.l  stems_nf,%d2
.Ll_fn:
        move.l  (%a0)+,%d1          | kind << 24 | channels << 16 | bytes
        moveq   #0,%d4
        move.w  %d1,%d4             | the file's bytes in a ring frame
        swap    %d1
        andi.l  #0xff00,%d1
        lsr.l   #8,%d1              | the kind
        cmpi.l  #K_MAIN,%d1
        bcc.s   .Ll_bus
        addq.l  #1,%d0
        add.l   %d4,%d3
        lsl.l   #7,%d1              | k * 0x80: the track's block, and its gains' slot
        move.l  %a1,(STEMS_FN_OFF,%a0)
        bra.s   .Ll_arg
.Ll_bus:
        move.l  %a2,(STEMS_FN_OFF,%a0)
.Ll_arg:
        move.l  %d1,(STEMS_ARG_OFF,%a0)
        subq.l  #1,%d2
        bne.s   .Ll_fn
        move.l  %d0,stems_ntrk
        move.l  %d3,stems_tbytes
        rts

| ---- the caller's EMAC state, saved and put back ---------------------------
| The moves run in integer mode, as the frame interrupt's own save does
| (0x4000ac96, 0x4000d968); the work runs in MACSR_FRAC. The hook runs
| before that save, inside whatever code the interrupt stopped, so ACC0
| and ACC1 hold that code's sums: they are cleared after the save, or
| the first mac.l into each adds into them. MACSR is read into an address register: stock never
| reads it into a data register (0x400031ac, 0x4000ac98). d0 and a0 are
| preserved.
stems_emac_in:
        move.l  %d0,-(%sp)
        move.l  %a0,-(%sp)
        move.l  %macsr,%a0
        move.l  %a0,stems_emac_save
        movea.l (%sp)+,%a0
        moveq   #0,%d0
        move.l  %d0,%macsr
        move.l  %acc0,%d0
        move.l  %d0,stems_emac_save+4
        move.l  %acc1,%d0
        move.l  %d0,stems_emac_save+8
        move.l  %accext01,%d0
        move.l  %d0,stems_emac_save+12
        moveq   #0,%d0
        move.l  %d0,%acc0
        move.l  %d0,%acc1
        move.l  %d0,%accext01
        moveq   #MACSR_FRAC,%d0
        move.l  %d0,%macsr
        move.l  (%sp)+,%d0
        rts
stems_emac_out:
        move.l  %d0,-(%sp)
        moveq   #0,%d0
        move.l  %d0,%macsr
        move.l  stems_emac_save+4,%d0
        move.l  %d0,%acc0
        move.l  stems_emac_save+8,%d0
        move.l  %d0,%acc1
        move.l  stems_emac_save+12,%d0
        move.l  %d0,%accext01
        move.l  stems_emac_save,%d0
        move.l  %d0,%macsr
        move.l  (%sp)+,%d0
        rts

| ---- the gain mirror: core 0's MAIN gains from the level pages -----------
| Every frame: the page channel 0 sends (LV_SENT), through core 0's
| arithmetic (docs/firmware/STEM_REC.md 18.2-18.3), so the current state
| (stems_gstate + stems_gsel) equals core 0's MAIN ramp state; each page
| reads one of the two states and writes the other. While a take is armed,
| recording or saving, and while the sequencer is stopped (so the frame
| before a take's first playing frame always has them, however late it was
| armed: the take starts as it did before the perf round), also each track
| slot's 16 gains into stems_gq, after
| their bound: the largest end of the three parts that write them, unsigned.
| Each part is linear, so the bound is at most LIM_FREE only when every gain
| is in 0..LIM_FREE (an end below 0 reads as large). stems_gqok counts
| those frames; IDLE while playing sets it to 0. An index above 3 is the
| increment before its wrap (18.1), not a page. In the audio interrupt;
| every register is preserved.
stems_mirror:
        move.l  %d0,-(%sp)
        move.l  LV_SENT,%d0
        cmpi.l  #LV_NPAGES-1,%d0
        bhi.s   .Lg_none                    | 4: the wrap's transient
        cmp.l   stems_lvlast,%d0
        bne.s   .Lg_new
.Lg_none:
        move.l  (%sp)+,%d0
        rts                                 | no new page this frame
.Lg_new:
        lea     -56(%sp),%sp
        movem.l %d1-%d7/%a0-%a6,(%sp)
        move.l  stems_lvlast,%d1
        move.l  %d0,stems_lvlast
        tst.l   %d1
        bmi.s   .Lg_seq                     | the first page
        addq.l  #1,%d1
        cmp.l   %d1,%d0
        beq.s   .Lg_seq
        tst.l   %d0
        beq.s   .Lg_seq                     | the ring wrapped to page 0
        addq.l  #1,stems_lvskip
.Lg_seq:
        lsl.l   #7,%d0
        movea.l %d0,%a0
        adda.l  #LV_PAGES,%a0               | a0: the page
        moveq   #0,%d0
        move.w  0x52(%a0),%d0               | the MAIN level, halfword 0x29
        cmp.l   stems_gw29,%d0
        beq.s   .Lg_m2
        move.l  %d0,stems_gw29
        EMAC_ON
        andi.l  #0xff,%d0
        moveq   #24,%d1
        lsl.l   %d1,%d0                     | m << 8: (W29 & 0xff) << 24
        cmpi.l  #0x80000000,%d0
        beq.s   .Lg_m2one                   | -1.0: its square overflows the EMAC's read-out
        mac.l   %d0,%d0,%acc0
        movclr.l %acc0,%d0
        asr.l   #8,%d0                      | M2 = floor(m*m / 2^23)
        bra.s   .Lg_m2ok
.Lg_m2one:
        move.l  #0x7fffff,%d0               | core 0's limited 1.0
.Lg_m2ok:
        move.l  %d0,stems_gm2
        lea     stems_gcache,%a1            | every target is stale
        moveq   #-1,%d2
        moveq   #8,%d1
.Lg_inval:
        move.l  %d2,(%a1)
        addq.l  #8,%a1
        subq.l  #1,%d1
        bne.s   .Lg_inval
.Lg_m2:
        suba.l  %a4,%a4                     | a4: where the gains go, 0 = nowhere
        tst.l   stems_state
        bne.s   .Lg_q                       | armed, recording or saving: the gains
        moveq   #TRANSPORT_RUNNING,%d0
        cmp.l   TRANSPORT,%d0
        beq.s   .Lg_noq                     | IDLE while the sequencer plays: the state only
.Lg_q:                                      | (stopped, the frame before a take's first has them)
        move.l  stems_gqn,%d0
        moveq   #GQ_N-1,%d1
        and.l   %d1,%d0
        moveq   #10,%d1
        lsl.l   %d1,%d0                     | * GQ_FRAME
        movea.l %d0,%a4
        adda.l  #stems_gq,%a4
.Lg_noq:
        move.l  stems_gsel,%d0              | a2: the state now, a1: the one this page makes
        lea     stems_gstate,%a2
        adda.l  %d0,%a2
        eori.l  #96,%d0
        lea     stems_gstate,%a1
        adda.l  %d0,%a1
        lea     stems_gcache,%a3
        lea     2(%a0),%a5                  | slot 0's w1
        moveq   #0,%d6                      | slot k
.Lg_slot:
        moveq   #0,%d1
        move.w  (%a5),%d1                   | w1: the track level
        moveq   #0,%d2
        move.w  2(%a5),%d2                  | w2: the MAIN table index
        moveq   #0,%d3
        move.w  4(%a5),%d3
        moveq   #15,%d7
        and.l   %d7,%d3                     | s: the split sample
        move.l  %d1,%d4
        swap    %d4
        or.l    %d2,%d4                     | the cache key: w1 << 16 | w2
        cmp.l   (%a3),%d4
        bne.s   .Lg_miss
        moveq   #-1,%d7
        cmp.l   %d7,%d4
        bne.w   .Lg_cached                  | a hit, unless the key is the stale mark itself
.Lg_miss:
        EMAC_ON
        move.l  %d4,(%a3)
        move.l  %d1,%d0
        swap    %d0                         | x << 8 = w1 << 16, signed
        cmpi.l  #0x80000000,%d0
        beq.s   .Lg_sqone                   | -1.0: its square overflows the EMAC's read-out
        mac.l   %d0,%d0,%acc0
        movclr.l %acc0,%d0
        asr.l   #8,%d0                      | w1sq = floor(x*x / 2^23)
        bra.s   .Lg_sqok
.Lg_sqone:
        move.l  #0x7fffff,%d0               | core 0's limited 1.0
.Lg_sqok:
        move.l  %d2,%d5
        swap    %d5
        moveq   #23,%d4
        asr.l   %d4,%d5                     | idx = sext24(w2 << 8) >> 15
        moveq   #0,%d4                      | T = 0 below the table (a w2 of 0x8000 or more)
        tst.l   %d5
        bmi.s   .Lg_t
        movea.l %d5,%a6
        adda.l  %d5,%a6
        adda.l  %d5,%a6                     | 3 * idx
        adda.l  #stems_gtab,%a6
        move.b  2(%a6),%d4
        lsl.l   #8,%d4
        move.b  1(%a6),%d4
        lsl.l   #8,%d4
        move.b  (%a6),%d4                   | T: 24 bits, little-endian as in the image
.Lg_t:
        move.l  stems_gm2,%d5
        lsl.l   #8,%d5
        lsl.l   #8,%d4
        mac.l   %d5,%d4,%acc0
        movclr.l %acc0,%d4
        asr.l   #8,%d4                      | tM = floor(M2 * T / 2^23)
        lsl.l   #8,%d0
        lsl.l   #8,%d4
        mac.l   %d0,%d4,%acc0
        movclr.l %acc0,%d0
        asr.l   #8,%d0                      | the target = floor(w1sq * tM / 2^23)
        move.l  %d0,4(%a3)
.Lg_cached:
        move.l  4(%a3),%d0                  | d0: the target
        movem.l (%a2),%d1/%d4-%d5           | d1: last split, d4: increment, d5: gain
        cmp.l   %d1,%d3
        bcc.s   .Lg_m                       | s >= last split: m = last split
        move.l  %d3,%d1                     | m = s
.Lg_m:
        move.l  %a4,%d2
        beq.s   .Lg_fast
        addq.l  #4,%a4                      | the slot's first long: the gains' bound, below
        move.l  %d5,%d7                     | d7: the largest end so far, unsigned. Each part is
                                            | linear, so its ends bound it: the old ramp and the
                                            | hold lie between d5 now and d5 after them, the new
                                            | ramp between that and d5 after it
        move.l  %d1,%d2                     | the old ramp: m samples
        beq.s   .Lg_h0
.Lg_old:
        move.l  %d5,(%a4)+
        add.l   %d4,%d5
        subq.l  #1,%d2
        bne.s   .Lg_old
.Lg_h0:
        move.l  %d3,%d2
        sub.l   %d1,%d2                     | the hold: s - m samples
        beq.s   .Lg_new2
.Lg_hold:
        move.l  %d5,(%a4)+
        subq.l  #1,%d2
        bne.s   .Lg_hold
.Lg_new2:
        cmp.l   %d5,%d7
        bcc.s   .Lg_mx1
        move.l  %d5,%d7
.Lg_mx1:
        move.l  %d0,%d4
        sub.l   %d5,%d4
        asr.l   #4,%d4                      | the new increment
        moveq   #16,%d2
        sub.l   %d3,%d2                     | the new ramp: 16 - s samples, 1..16
.Lg_ramp:
        move.l  %d5,(%a4)+
        add.l   %d4,%d5
        subq.l  #1,%d2
        bne.s   .Lg_ramp
        cmp.l   %d5,%d7
        bcc.s   .Lg_mx2
        move.l  %d5,%d7
.Lg_mx2:
        move.l  %d7,-68(%a4)                | the slot's bound
        lea     GQ_SLOT-68(%a4),%a4         | the next slot
        bra.s   .Lg_store
.Lg_fast:                                   | the state only: the same sums, multiplied
        move.l  %d4,%d2
        muls.l  %d1,%d2
        add.l   %d2,%d5                     | gain += m * increment
        move.l  %d0,%d4
        sub.l   %d5,%d4
        asr.l   #4,%d4
        moveq   #16,%d2
        sub.l   %d3,%d2
        muls.l  %d4,%d2
        add.l   %d2,%d5                     | gain += (16 - s) * the new increment
.Lg_store:
        movem.l %d3-%d5,(%a1)               | split, increment, gain
        lea     12(%a1),%a1
        lea     12(%a2),%a2
        addq.l  #8,%a3
        addq.l  #8,%a5
        addq.l  #1,%d6
        moveq   #8,%d0
        cmp.l   %d0,%d6
        bne.w   .Lg_slot
        move.l  stems_gsel,%d0
        eori.l  #96,%d0
        move.l  %d0,stems_gsel              | the state this page made is the current one
        move.l  %a4,%d0
        beq.s   .Lg_idle
        addq.l  #1,stems_gqn
        addq.l  #1,stems_gqok
        bra.s   .Lg_done
.Lg_idle:
        clr.l   stems_gqok
.Lg_done:
        tst.l   stems_gemac
        beq.s   .Lg_noemac                  | no multiply this page: the EMAC was never touched
        clr.l   stems_gemac
        bsr.w   stems_emac_out
.Lg_noemac:
        movem.l (%sp),%d1-%d7/%a0-%a6
        lea     56(%sp),%sp
        move.l  (%sp)+,%d0
        rts

| ---- d4 = T1's block in the read-back half PING names (Task 3 of piece 1) --
stems_half:
        move.l  PING,%d4
        eori.l  #PING_XOR,%d4
        andi.l  #1,%d4
        moveq   #10,%d0
        lsl.l   %d0,%d4
        addi.l  #READBACK,%d4
        rts

| ---- a track's inputs: d4 = stems_half's, d5 = k * 0x80, d7 = the gains'
| frame in stems_gq. a2 = the 16 samples core 0 mixes for track k (the half
| PING doesn't name, TRACK_HALF), a0 = their end, a3 = the slot's 16 gains,
| d0 = their bound (stems_mirror writes it first): at most LIM_FREE only
| when every gain is in 0..LIM_FREE.
        .macro  TRACK_IN
        move.l  %d4,%d0
        .if     TRACK_HALF
        eori.l  #0x400,%d0
        .endif
        add.l   %d5,%d0
        movea.l %d0,%a2
        lea     0x80(%a2),%a0
        movea.l %d7,%a3
        adda.l  %d5,%a3
        move.l  (%a3)+,%d0
        .endm

| ---- one track's ring frame after the fader, 16-bit (d4, d5, d7 as
| TRACK_IN takes them; a1 = the ring). Each sample: floor(g*x / 2^15) on the
| EMAC (MACSR_FRAC, set by the caller), its top 16 bits as floor(g*x / 2^29),
| limited to 16 bits as core 0 limits MAIN to 24 (STEM_REC.md 18.2). With
| every gain in 0..LIM_FREE the limit can't act, so that loop has none, two
| samples a pass. Uses d0-d3, a0, a2, a3.
        .global stems_track16
stems_track16:
        TRACK_IN
        cmpi.l  #LIM_FREE,%d0
        bhi.s   .Lp_lim                     | a gain above a quarter, or below 0
        moveq   #14,%d3
.Lp_f:
        move.l  (%a3)+,%d0
        lsl.l   #8,%d0                      | g << 8
        move.l  (%a2)+,%d1                  | L, left-justified 24 bits
        move.l  (%a2)+,%d2                  | R
        clr.b   %d1                         | the top 24 bits only (18.5)
        clr.b   %d2
        mac.l   %d0,%d1,%acc0
        mac.l   %d0,%d2,%acc1
        movclr.l %acc0,%d1                  | floor(g*x / 2^15)
        movclr.l %acc1,%d2
        asr.l   %d3,%d1                     | floor(g*x / 2^29)
        asr.l   %d3,%d2
        swap    %d1
        move.w  %d2,%d1                     | L : R, big-endian halves
        move.l  %d1,(%a1)+
        move.l  (%a3)+,%d0                  | the next sample, the same
        lsl.l   #8,%d0
        move.l  (%a2)+,%d1
        move.l  (%a2)+,%d2
        clr.b   %d1
        clr.b   %d2
        mac.l   %d0,%d1,%acc0
        mac.l   %d0,%d2,%acc1
        movclr.l %acc0,%d1
        movclr.l %acc1,%d2
        asr.l   %d3,%d1
        asr.l   %d3,%d2
        swap    %d1
        move.w  %d2,%d1
        move.l  %d1,(%a1)+
        cmpa.l  %a0,%a2
        bcs.s   .Lp_f
        rts
.Lp_lim:
        moveq   #16,%d3
.Lp_s:
        move.l  (%a3)+,%d0
        lsl.l   #8,%d0                      | g << 8
        move.l  (%a2)+,%d1                  | L, left-justified 24 bits
        move.l  (%a2)+,%d2                  | R
        clr.b   %d1                         | the DSP takes the top 24 bits; the half core 0
        clr.b   %d2                         | mixes has 0xff here on positive samples (18.5)
        mac.l   %d0,%d1,%acc0
        mac.l   %d0,%d2,%acc1
        movclr.l %acc0,%d1                  | floor(g*x / 2^15)
        movclr.l %acc1,%d2
        moveq   #14,%d0
        asr.l   %d0,%d1                     | floor(g*x / 2^29)
        asr.l   %d0,%d2
        LIM16   %d1
        LIM16   %d2
        swap    %d1
        move.w  %d2,%d1                     | L : R, big-endian halves, as before
        move.l  %d1,(%a1)+
        subq.l  #1,%d3
        bne.s   .Lp_s
        rts

| ---- MAIN, CUE or an input, 16-bit: d5 = the kind (8-15), a1 = the ring.
| MAIN and CUE from channel 6's buffer (STEM_REC.md 18.6); the inputs from
| the page of channel 7's ring that IN_IDX names this frame, complete at
| hook time (18.7). 16 samples of left-justified 24-bit longs, L then R (A
| then B, C then D). Uses d0-d3, a0, a2.
| ---- a2 = the first long of bus kind d5 this frame. Uses d0, d1, a0. -----
stems_bus_src:
        move.l  %d5,%d0
        subq.l  #K_MAIN,%d0
        lsl.l   #2,%d0
        lea     bus_src,%a0
        movea.l (%a0,%d0.l),%a2             | MAIN, CUE: the long; an input: its offset in the page
        cmpi.l  #K_AB,%d5
        bcs.s   .Lbs_out
        move.l  IN_IDX,%d0                  | this frame's page
        moveq   #7,%d1
        and.l   %d1,%d0
        lsl.l   #8,%d0
        adda.l  %d0,%a2
        adda.l  #IN_RING,%a2
.Lbs_out:
        rts

        .global stems_bus16
stems_bus16:
        bsr.w   stems_bus_src
        moveq   #16,%d3
        cmpi.l  #K_A,%d5
        bcc.s   .Lb_mono
.Lb_st:
        move.l  (%a2)+,%d1                  | L
        move.l  (%a2)+,%d2                  | R
        swap    %d2
        move.w  %d2,%d1                     | L's top 16 : R's top 16
        move.l  %d1,(%a1)+
        subq.l  #1,%d3
        bne.s   .Lb_st
        rts
.Lb_mono:
        move.l  (%a2),%d1
        swap    %d1
        move.w  %d1,(%a1)+                  | the channel's top 16
        addq.l  #8,%a2
        subq.l  #1,%d3
        bne.s   .Lb_mono
        rts

| ---- one track's ring frame after the fader, 24-bit: as stems_track16, but
| the whole 24-bit share, floor(g*x / 2^21), limited as MAIN is.
        .global stems_track24
stems_track24:
        TRACK_IN
        cmpi.l  #LIM_FREE,%d0
        bhi.s   .Lq_lim                     | a gain above a quarter, or below 0
.Lq_f:
        move.l  (%a3)+,%d0
        lsl.l   #8,%d0
        move.l  (%a2)+,%d1
        move.l  (%a2)+,%d2
        clr.b   %d1                         | the top 24 bits, as the DSP takes them (18.5)
        clr.b   %d2
        mac.l   %d0,%d1,%acc0
        mac.l   %d0,%d2,%acc1
        movclr.l %acc0,%d1
        movclr.l %acc1,%d2
        asr.l   #6,%d1                      | floor(g*x / 2^21)
        asr.l   #6,%d2
        PACK6   %d1,%d2
        move.l  (%a3)+,%d0                  | the next sample, the same
        lsl.l   #8,%d0
        move.l  (%a2)+,%d1
        move.l  (%a2)+,%d2
        clr.b   %d1
        clr.b   %d2
        mac.l   %d0,%d1,%acc0
        mac.l   %d0,%d2,%acc1
        movclr.l %acc0,%d1
        movclr.l %acc1,%d2
        asr.l   #6,%d1
        asr.l   #6,%d2
        PACK6   %d1,%d2
        cmpa.l  %a0,%a2
        bcs.s   .Lq_f
        rts
.Lq_lim:
        moveq   #16,%d3
.Lq_s:
        move.l  (%a3)+,%d0
        lsl.l   #8,%d0
        move.l  (%a2)+,%d1
        move.l  (%a2)+,%d2
        clr.b   %d1                         | the top 24 bits, as the DSP takes them (18.5)
        clr.b   %d2
        mac.l   %d0,%d1,%acc0
        mac.l   %d0,%d2,%acc1
        movclr.l %acc0,%d1
        movclr.l %acc1,%d2
        asr.l   #6,%d1                      | floor(g*x / 2^21)
        asr.l   #6,%d2
        LIM24   %d1
        LIM24   %d2
        PACK6   %d1,%d2
        subq.l  #1,%d3
        bne.s   .Lq_s
        rts

| ---- MAIN, CUE or an input, 24-bit (d5 = the kind, a1 = the ring) ------
| Uses d0-d3, a0, a2.
        .global stems_bus24
stems_bus24:
        bsr.w   stems_bus_src
        cmpi.l  #K_A,%d5
        bcc.s   .Lu_mono
        moveq   #16,%d3
.Lu_st:
        move.l  (%a2)+,%d1
        move.l  (%a2)+,%d2
        asr.l   #8,%d1                      | 24 bits, right-justified
        asr.l   #8,%d2
        PACK6   %d1,%d2
        subq.l  #1,%d3
        bne.s   .Lu_st
        rts
.Lu_mono:
        moveq   #8,%d3                      | two samples to six bytes
.Lu_mo:
        move.l  (%a2),%d1
        move.l  8(%a2),%d2
        asr.l   #8,%d1
        asr.l   #8,%d2
        PACK6   %d1,%d2
        lea     16(%a2),%a2
        subq.l  #1,%d3
        bne.s   .Lu_mo
        rts

| ---- stage: the tracks' part of the next ring frame (a1 = its first byte) --
| From the half PING doesn't name now and the gains of the page GAIN_LAG
| before the newest (design 1.1); each track file's routine and argument
| from the table the layout latched. Sets the EMAC around the work. Uses
| d0-d7, a0-a5.
stems_stage:
        bsr.w   stems_emac_in
        bsr.w   stems_half                  | d4
        move.l  stems_gqn,%d7
        subq.l  #1+GAIN_LAG,%d7
        moveq   #GQ_N-1,%d0
        and.l   %d0,%d7
        moveq   #10,%d0
        lsl.l   %d0,%d7                     | * GQ_FRAME
        addi.l  #stems_gq,%d7               | d7: the gains' frame
        lea     stems_ffn,%a4
        lea     stems_farg,%a5
        move.l  stems_ntrk,%d6
        beq.s   .Lc_done
.Lc_file:
        movea.l (%a4)+,%a0
        move.l  (%a5)+,%d5
        jsr     (%a0)
        subq.l  #1,%d6
        bne.s   .Lc_file
.Lc_done:
        bsr.w   stems_emac_out
        rts

| ---- the buses' part of this ring frame (a1 = its first byte): MAIN, CUE and
| the inputs of this frame, in the table's order. Uses d0-d6, a0-a5.
stems_bus_frame:
        move.l  stems_ntrk,%d0
        move.l  stems_nf,%d6
        sub.l   %d0,%d6
        beq.s   .Lb_done
        lsl.l   #2,%d0
        lea     stems_ffn,%a4
        adda.l  %d0,%a4
        lea     stems_farg,%a5
        adda.l  %d0,%a5
.Lb_file:
        movea.l (%a4)+,%a0
        move.l  (%a5)+,%d5
        jsr     (%a0)
        subq.l  #1,%d6
        bne.s   .Lb_file
.Lb_done:
        rts

| ---- test seam: one frame of what the hook sees (STEM_REC.md 18.5) -----
| TRACE_B bytes a frame: PING, the written and sent page indexes, T1's
| first read-back long in the half PING names and in the other half,
| MAIN's first L and R, MAIN's last L; the input ring's index, and in
| its page A's, B's, C's and D's first longs and A's last; in the page
| before it A's first; T1's last long in the other half.
stems_trace_frame:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        move.l  stems_trace,%d0
        subq.l  #1,%d0
        cmpi.l  #TRACE_N,%d0
        bcc.w   .Lr_out
        lsl.l   #6,%d0              | * TRACE_B
        movea.l %d0,%a1
        adda.l  #stems_trace_buf,%a1
        move.l  PING,%d1
        move.l  %d1,(%a1)+
        move.l  0x80004800,(%a1)+
        move.l  0x80004804,(%a1)+
        eori.l  #PING_XOR,%d1
        andi.l  #1,%d1
        moveq   #10,%d0
        lsl.l   %d0,%d1
        movea.l %d1,%a0
        adda.l  #READBACK,%a0
        move.l  (%a0),(%a1)+
        move.l  %a0,%d1
        eori.l  #0x400,%d1
        movea.l %d1,%a0
        move.l  (%a0),(%a1)+
        move.l  0x80005e60,(%a1)+
        move.l  0x80005e64,(%a1)+
        move.l  0x80005ed8,(%a1)+
        move.l  IN_IDX,%d1
        move.l  %d1,(%a1)+
        moveq   #7,%d0
        and.l   %d0,%d1
        lsl.l   #8,%d1
        movea.l %d1,%a0
        adda.l  #IN_RING,%a0
        move.l  0x80(%a0),(%a1)+
        move.l  0x84(%a0),(%a1)+
        move.l  (%a0),(%a1)+
        move.l  4(%a0),(%a1)+
        move.l  0xf8(%a0),(%a1)+
        move.l  IN_IDX,%d1
        subq.l  #1,%d1
        and.l   %d0,%d1
        lsl.l   #8,%d1
        movea.l %d1,%a0
        adda.l  #IN_RING,%a0
        move.l  0x80(%a0),(%a1)+
        move.l  PING,%d1
        eori.l  #PING_XOR^1,%d1
        andi.l  #1,%d1
        moveq   #10,%d0
        lsl.l   %d0,%d1
        movea.l %d1,%a0
        adda.l  #READBACK,%a0
        move.l  0x78(%a0),(%a1)+
        addq.l  #1,stems_trace
.Lr_out:
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
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
        move.l  DTCN3,-(%sp)        | the sleep's start, for the readout
        pea     K_DELAY_TRY
        pea     TASK_SLEEP_US
        jsr     K_DELAY             | d0 = -1 when the timer was busy: just loop
        addq.l  #8,%sp
        move.l  DTCN3,%d1
        sub.l   (%sp)+,%d1          | how long the sleep took
        moveq   #ST_RECORDING,%d0
        cmp.l   stems_state,%d0
        bne.s   .Lt_slept           | only a recording's sleeps count
        cmp.l   stems_st_smax,%d1
        bls.s   .Lt_slept
        move.l  %d1,stems_st_smax
.Lt_slept:
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
        bne.w   .Lt_loop            | test seam: hold the writer
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

| ---- a file path: stems_path + the name of file d3 ----------------------
stems_make_file:
        lea     stems_path,%a0
        lea     stems_fpath,%a1
.Lm_copy:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lm_copy
        subq.l  #1,%a1
        move.l  %d3,%d0
        lsl.l   #2,%d0
        lea     stems_ftab,%a0
        move.l  (%a0,%d0.l),%d0
        moveq   #24,%d1
        lsr.l   %d1,%d0                     | the kind
        cmpi.l  #K_MAIN,%d0
        bcc.s   .Lm_named
        addq.l  #1,%d0                      | T<k+1>
        move.l  %d0,-(%sp)
        pea     fmt_file
        move.l  %a1,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        rts
.Lm_named:
        subq.l  #K_MAIN,%d0
        lsl.l   #2,%d0
        lea     bus_names,%a0
        movea.l (%a0,%d0.l),%a0
.Lm_name:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lm_name
        rts

| ---- file d3's header into a2: the template with its channels, its bytes a
| second, its block align and its bits, little-endian as RIFF wants -------
stems_hdr_fill:
        lea     stems_hdr,%a0
        movea.l %a2,%a1
        moveq   #HDR_SIZE/4,%d0
.Lhf_cp:
        move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.s   .Lhf_cp
        move.l  %d3,%d0
        lsl.l   #2,%d0
        lea     stems_ftab,%a0
        move.l  (%a0,%d0.l),%d1
        swap    %d1
        andi.l  #0xff,%d1                   | channels
        move.l  stems_lfmt,%d2
        andi.l  #1,%d2
        addq.l  #2,%d2                      | bytes a sample: 2, or 3 with 24 BIT
        move.b  %d1,22(%a2)                 | channels
        move.l  %d1,%d0
        mulu.l  %d2,%d0                     | block align
        move.b  %d0,32(%a2)
        lsl.l   #3,%d2
        move.b  %d2,34(%a2)                 | bits
        move.l  #44100,%d1
        mulu.l  %d1,%d0                     | bytes a second
        BYTEREV 0
        move.l  %d0,28(%a2)
        rts

| ---- start: name, folder, one file per entry of the file table ----------
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
        moveq   #0,%d3              | file j
.Ls_file:
        cmp.l   stems_nf,%d3
        bcc.s   .Ls_all
        bsr.w   stems_make_file
        pea     MODE_W
        pea     stems_fpath
        RAWCALL RAW_OPEN_PTR
        addq.l  #8,%sp
        tst.l   %d0
        ble.w   .Ls_open
        lea     stems_handle,%a0
        move.l  %d0,(%a0,%d3.l*4)
        lea     stems_fpos,%a0
        clr.l   (%a0,%d3.l*4)
        lea     stems_slen,%a0
        moveq   #HDR_SIZE,%d0
        move.l  %d0,(%a0,%d3.l*4)   | the stream starts with the placeholder header
        move.l  %d3,%d1
        bsr.w   stems_sbuf          | a2: stream buffer j
        bsr.w   stems_hdr_fill
        addq.l  #1,stems_nopen
        addq.l  #1,%d3
        bra.s   .Ls_file
.Ls_all:
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
        lea     -40(%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)
        move.l  %d1,%d5             | the smallest batch worth taking
.Ld_more:
        cmpi.l  #CHUNK_FRAMES,%d5   | recording: the test seam holds the writer
        bne.s   .Ld_go              | between batches too, not only between passes
        bsr.w   stems_ui            | and the labels follow the take between chunks: a writer
                                    | behind the hook stays here, and the menu froze (3 Oct 2026)
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
.Ld_batch:                          | per file, over the batch's frames (perf design 2.1)
        move.l  DTCN3,-(%sp)        | the copy's start, for the readout
        moveq   #0,%d4              | file j
        moveq   #0,%d7              | its part's offset in a ring frame
        lea     stems_ftab,%a4
        lea     stems_slen,%a5
.Ld_file:
        move.l  %d4,%d1
        bsr.w   stems_sbuf          | a2 = stream buffer j
        adda.l  (%a5),%a2           | past the bytes already waiting in it
        move.l  (%a4)+,%d1
        andi.l  #0xffff,%d1         | d1: this file's bytes in a frame
        move.l  %d1,%d0
        mulu.l  %d2,%d0
        add.l   %d0,(%a5)+          | the buffer's fill after the batch
        move.l  stems_rd_off,%d6    | d6: the frame's offset in the ring
        move.l  %d2,%d3             | d3: frames left
        move.l  stems_lfmt,%d0
        btst    #0,%d0
        bne.s   .Ld_24
.Ld_f16:                            | 16 bits: a frame's part is 2 or 4 groups of 16 bytes
        movea.l %d6,%a3
        adda.l  %d7,%a3
        adda.l  #stems_ring,%a3
        lea     (%a3,%d1.l),%a1     | its end
.Ld_s:                              | [L1 L0 R1 R0] -> [L0 L1 R0 R1], four longs a pass
        move.l  (%a3)+,%d0
        BYTEREV 0
        swap    %d0
        move.l  %d0,(%a2)+
        move.l  (%a3)+,%d0
        BYTEREV 0
        swap    %d0
        move.l  %d0,(%a2)+
        move.l  (%a3)+,%d0
        BYTEREV 0
        swap    %d0
        move.l  %d0,(%a2)+
        move.l  (%a3)+,%d0
        BYTEREV 0
        swap    %d0
        move.l  %d0,(%a2)+
        cmpa.l  %a1,%a3
        bcs.s   .Ld_s
        add.l   stems_fbytes,%d6
        cmp.l   stems_rlimit,%d6
        bcs.s   .Ld_w16
        moveq   #0,%d6              | the ring's wrap
.Ld_w16:
        subq.l  #1,%d3
        bne.s   .Ld_f16
        bra.s   .Ld_fnext
.Ld_24:                             | 24 bits: a frame's part is 4 or 8 groups of 12 bytes
        movea.l %d6,%a3
        adda.l  %d7,%a3
        adda.l  #stems_ring,%a3
        lea     (%a3,%d1.l),%a1
.Ld_g:                              | [a2 a1 a0 b2 b1 b0] -> [a0 a1 a2 b0 b1 b2], twice a pass
        move.b  2(%a3),(%a2)+
        move.b  1(%a3),(%a2)+
        move.b  (%a3),(%a2)+
        move.b  5(%a3),(%a2)+
        move.b  4(%a3),(%a2)+
        move.b  3(%a3),(%a2)+
        move.b  8(%a3),(%a2)+
        move.b  7(%a3),(%a2)+
        move.b  6(%a3),(%a2)+
        move.b  11(%a3),(%a2)+
        move.b  10(%a3),(%a2)+
        move.b  9(%a3),(%a2)+
        lea     12(%a3),%a3
        cmpa.l  %a1,%a3
        bcs.s   .Ld_g
        add.l   stems_fbytes,%d6
        cmp.l   stems_rlimit,%d6
        bcs.s   .Ld_w24
        moveq   #0,%d6
.Ld_w24:
        subq.l  #1,%d3
        bne.s   .Ld_24
.Ld_fnext:
        add.l   %d1,%d7             | the next file's part
        addq.l  #1,%d4
        cmp.l   stems_nf,%d4
        bcs.w   .Ld_file
        move.l  %d6,stems_rd_off    | every file's loop ends one batch on
        add.l   %d2,stems_rd        | the hook may reuse these frames now
        move.l  DTCN3,%d1
        sub.l   (%sp)+,%d1
        bsr.w   stems_st_copy
        moveq   #0,%d4
.Ld_flush:
        move.l  %d4,%d1
        moveq   #0,%d0              | whole sectors only
        bsr.w   stems_flush
        tst.l   %d0
        bmi.s   .Ld_err
        addq.l  #1,%d4
        cmp.l   stems_nf,%d4
        bcs.s   .Ld_flush
        bra.w   .Ld_more
.Ld_done:
        moveq   #0,%d0
        bra.s   .Ld_out
.Ld_err:
        moveq   #-1,%d0
.Ld_out:
        movem.l (%sp),%d2-%d7/%a2-%a5
        lea     40(%sp),%sp
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
        move.l  DTCN3,-(%sp)        | the write's start, for the readout
        move.l  %d3,-(%sp)
        move.l  %a2,-(%sp)
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        move.l  DTCN3,%d1
        sub.l   (%sp)+,%d1
        bsr.w   stems_st_write
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
        move.l  %d4,%d0
        lsl.l   #2,%d0
        lea     stems_ftab,%a0
        move.l  (%a0,%d0.l),%d1
        swap    %d1
        andi.l  #0xff,%d1                   | channels
        move.l  stems_lfmt,%d0
        andi.l  #1,%d0
        addq.l  #2,%d0                      | bytes a sample: 2, or 3 with 24 BIT
        mulu.l  %d0,%d1                     | block align
        move.l  %d3,%d0
        divu.l  %d1,%d0
        mulu.l  %d1,%d0
        move.l  %d0,%d3                     | whole frames of this file only
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
        bsr.w   stems_stats         | the readout, beside the closed files
        clr.l   stems_nopen
        clr.l   stems_wfail
        movem.l (%sp),%d2-%d4/%a2
        lea     16(%sp),%sp
        rts

| ---- the readout's writer counters: d1 = DTCN3 counts; d0 is kept --------
stems_st_write:                     | one card write
        addq.l  #1,stems_st_wn
        cmp.l   stems_st_wmax,%d1
        bls.s   .Lsw_us
        move.l  %d1,stems_st_wmax
.Lsw_us:
        move.l  %d0,-(%sp)
        move.l  #BUS_MHZ,%d0
        divu.l  %d0,%d1
        add.l   %d1,stems_st_wsum
        move.l  (%sp)+,%d0
        rts
stems_st_copy:                      | one batch of the writer's copy
        cmp.l   stems_st_cmax,%d1
        bls.s   .Lsc_us
        move.l  %d1,stems_st_cmax
.Lsc_us:
        move.l  %d0,-(%sp)
        move.l  #BUS_MHZ,%d0
        divu.l  %d0,%d1
        add.l   %d1,stems_st_csum
        move.l  (%sp)+,%d0
        rts

| ---- d1 = (d0:d1) / d2, unsigned, d0 < d2 (a 64-bit sum over its count);
| d0 = the remainder. Uses d3.
stems_div64:
        moveq   #32,%d3
.Ldv_bit:
        add.l   %d1,%d1             | d0:d1 one bit left
        addx.l  %d0,%d0
        bcs.s   .Ldv_sub            | a 33-bit d0 is above d2
        cmp.l   %d2,%d0
        bcs.s   .Ldv_next
.Ldv_sub:
        sub.l   %d2,%d0
        addq.l  #1,%d1              | the quotient's next bit
.Ldv_next:
        subq.l  #1,%d3
        bne.s   .Ldv_bit
        rts

| ---- d1 = the mean of a 64-bit sum at a0 over stems_st_n, in microseconds
stems_st_mean:
        moveq   #0,%d1
        move.l  stems_st_n,%d2
        beq.s   .Lsm_out
        move.l  (%a0),%d0
        move.l  4(%a0),%d1
        bsr.w   stems_div64         | counts a frame
        move.l  #BUS_MHZ,%d0
        divu.l  %d0,%d1
.Lsm_out:
        rts

| ---- d1 = d1 DTCN3 counts in microseconds ---------------------------------
stems_st_us:
        move.l  %d0,-(%sp)
        move.l  #BUS_MHZ,%d0
        divu.l  %d0,%d1
        move.l  (%sp)+,%d0
        rts

| ---- a3 = the end of the text at a3 (its NUL) -----------------------------
stems_st_tail:
        tst.b   (%a3)
        beq.s   .Lst_out
        addq.l  #1,%a3
        bra.s   stems_st_tail
.Lst_out:
        rts

| ---- STATS.TXT: the readout, one sector of text in the take's folder -----
| After the take's files are closed (stems_finish), unless a card write
| failed: the card may refuse this one too. Built in sector-0 copy 0, free
| by then. An error here changes nothing: the take is whole without it.
stems_stats:
        lea     -32(%sp),%sp
        movem.l %d2-%d7/%a2-%a3,(%sp)
        tst.l   stems_wfail
        bne.w   .Lo_out
        moveq   #0,%d1
        bsr.w   stems_sec0
        movea.l %a0,%a2             | a2: the text
        movea.l %a0,%a3             | a3: its end
        moveq   #127,%d0
.Lo_clr:
        clr.l   (%a0)+              | 512 bytes of NUL: the sector past the text
        subq.l  #1,%d0
        bpl.s   .Lo_clr
        pea     stems_name                          | STEM REC STATS <take>
        pea     st_f_take
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        bsr.w   stems_st_tail
        move.l  stems_status,%d0                    | status <name>
        lea     lbl_ok,%a0
        beq.s   .Lo_st
        lea     err_names,%a0
        movea.l (%a0,%d0.l*4),%a0
.Lo_st:
        move.l  %a0,-(%sp)
        pea     st_f_status
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        bsr.w   stems_st_tail
        moveq   #16,%d2                             | frames, seconds, files, bits
        move.l  stems_lfmt,%d0
        btst    #0,%d0
        beq.s   .Lo_bits
        moveq   #24,%d2
.Lo_bits:
        move.l  %d2,-(%sp)
        move.l  stems_nf,-(%sp)
        move.l  stems_frames,%d0
        lsl.l   #4,%d0
        move.l  #44100,%d1
        divu.l  %d1,%d0
        move.l  %d0,-(%sp)
        move.l  stems_frames,-(%sp)
        pea     st_f_take2
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     24(%sp),%sp
        bsr.w   stems_st_tail
        move.l  stems_rframes,-(%sp)                | ring peak
        move.l  stems_peak,-(%sp)
        pea     st_f_ring
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     16(%sp),%sp
        bsr.w   stems_st_tail
        move.l  stems_st_wmax,%d1                   | card writes
        bsr.w   stems_st_us
        move.l  %d1,-(%sp)
        move.l  stems_st_wsum,%d0
        move.l  #1000,%d1
        divu.l  %d1,%d0
        move.l  %d0,-(%sp)
        move.l  stems_st_wn,-(%sp)
        pea     st_f_writes
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     20(%sp),%sp
        bsr.w   stems_st_tail
        move.l  stems_st_cmax,%d1                   | the writer's copy
        bsr.w   stems_st_us
        move.l  %d1,-(%sp)
        move.l  stems_st_csum,%d0
        move.l  #1000,%d1
        divu.l  %d1,%d0
        move.l  %d0,-(%sp)
        pea     st_f_copy
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     16(%sp),%sp
        bsr.w   stems_st_tail
        pea     TASK_SLEEP_US                       | the writer's longest sleep
        move.l  stems_st_smax,%d1
        bsr.w   stems_st_us
        move.l  %d1,-(%sp)
        pea     st_f_sleep
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     16(%sp),%sp
        bsr.w   stems_st_tail
        move.l  stems_st_hmax,%d1                   | the hook
        bsr.w   stems_st_us
        move.l  %d1,-(%sp)
        lea     stems_st_hsum,%a0
        bsr.w   stems_st_mean
        move.l  %d1,-(%sp)
        pea     st_f_hook
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     16(%sp),%sp
        bsr.w   stems_st_tail
        move.l  stems_st_n,-(%sp)                   | the hook and the stock frame routine
        move.l  stems_st_fmax,%d1
        bsr.w   stems_st_us
        move.l  %d1,-(%sp)
        lea     stems_st_fsum,%a0
        bsr.w   stems_st_mean
        move.l  %d1,-(%sp)
        pea     st_f_frame
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     20(%sp),%sp
        bsr.w   stems_st_tail
        moveq   #0,%d0                              | the card's DMA modes and its cluster
        move.b  CARD_SPC,%d0
        move.l  %d0,-(%sp)
        moveq   #0,%d0
        move.b  CARD_MWDMA,%d0
        move.l  %d0,-(%sp)
        moveq   #0,%d0
        move.b  CARD_UDMA,%d0
        move.l  %d0,-(%sp)
        pea     st_f_card
        move.l  %a3,-(%sp)
        jsr     SPRINTF
        lea     20(%sp),%sp
        bsr.w   stems_st_tail
        move.l  %a3,%d7
        sub.l   %a2,%d7                             | d7: the text's length
        lea     stems_path,%a0                      | <set>/AUDIO/<take>/STATS.TXT
        lea     stems_fpath,%a1
.Lo_p1:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lo_p1
        subq.l  #1,%a1
        lea     nm_stats,%a0
.Lo_p2:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lo_p2
        pea     MODE_W
        pea     stems_fpath
        RAWCALL RAW_OPEN_PTR
        addq.l  #8,%sp
        move.l  %d0,%d6                             | d6: the handle
        ble.s   .Lo_out
        pea     1
        move.l  %a2,-(%sp)
        move.l  %d6,-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        move.l  %d7,-(%sp)
        move.l  %d6,-(%sp)
        RAWCALL RAW_SETLEN_PTR
        addq.l  #8,%sp
        move.l  %d6,-(%sp)
        RAWCALL RAW_CLOSE_PTR
        addq.l  #4,%sp
.Lo_out:
        movem.l (%sp),%d2-%d7/%a2-%a3
        lea     32(%sp),%sp
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
