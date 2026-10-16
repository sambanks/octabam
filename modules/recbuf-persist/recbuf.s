| RECBUF PERSIST -- project-folder recorder buffers (REC1.wav..REC8.wav).
|
| On pstore_pre: mkdir BUFFERS/, sync-write each non-empty recorder
| (wav_write) to BUFFERS/RECn.wav, PATH it there, then stock slot load +
| post-load so the control record / UI show the assignment.
| On load*_post / preload_post: same PATH + slot load when the file exists.
| Folder name has no '!': SLOT_LOAD treats '!BUFFERS/…' as INVALID FILENAME
| (PATH landed in project.work on R4/R5; UI stayed unassigned).
|
| Empty test: control record length at 0x46c922c4 + slot*44 + 16.

        .text
        .globl  rbp_st_pstore_pre, rbp_st_loadall_post, rbp_st_loadmask_post
        .globl  rbp_st_preload_post, rbp_st_answer
        .extern store_path

        .set    F_OPEN,     0x40016864
        .set    F_CLOSE,    0x4001677c
        .set    SLOT_LOAD,  0x40093980      | (slot, keep_trim) STORAGE.md §2
        .set    POST_LOAD,  0x40099148      | (0, slot)
        .set    REARM,      0x40093468      | (-1) re-arm voices
        .set    REFRESH,    0x4009da20      | (-1) refresh
        .set    SPRINTF,    0x40013a08
        .set    WAV_WRITE,  0x40020f04
        .set    MODE_R,     0x400b3289
        .set    MODE_W,     0x400b328b
        .set    SETTINGS,   0x100b14f0
        .set    SET_STRIDE, 0x448
        .set    CTL_BASE,   0x46c922c4
        .set    CTL_STRIDE, 44
        .set    CTL_LEN,    16
        .set    WAV_GUARD,  0x46105408
        .set    FS_MKDIR,   0x46c8240a      | -> mkdir(path); call through
        .set    MIN_FRAMES, 64
        .set    MAX_FRAMES, 5292000
        .set    IOB_LEN,    0x10000

rbp_st_answer:
        rts

| ------------------------------------------------------------------ save
rbp_st_pstore_pre:
        lea     %sp@(-40),%sp
        movem.l %d2-%d7/%a2-%a5,%sp@
        | Ensure <project>/BUFFERS exists (idempotent if already there).
        moveq   #0,%d0
        lea     FMT_DIR,%a0
        lea     PATH,%a1
        jsr     store_path
        moveal  FS_MKDIR,%a0
        pea     PATH
        jsr     %a0@
        addql   #4,%sp
        clrl    IDX
sv_loop:
        movel   #128,%d3
        addl    IDX,%d3
        movel   %d3,SLOT
        bsr.w   slot_ctl
        movel   %a3@(CTL_LEN),%d5
        cmpl    #MIN_FRAMES,%d5
        bls.w   sv_next
        cmpl    #MAX_FRAMES,%d5
        bhi.w   sv_next
        movel   %d5,FRAMES
        moveq   #1,%d0
        addl    IDX,%d0
        lea     FMT_ABS,%a0
        lea     PATH,%a1
        jsr     store_path
        moveq   #1,%d0
        movel   %d0,WAV_GUARD
        pea     IOB_LEN
        pea     IOB
        pea     MODE_W:l
        pea     PATH
        pea     FO
        jsr     F_OPEN
        lea     %sp@(20),%sp
        tstl    %d0
        bmi.w   sv_next
        movel   SLOT,%sp@-
        movel   FRAMES,%sp@-
        clrl    %sp@-
        pea     FO
        jsr     WAV_WRITE
        lea     %sp@(16),%sp
        pea     FO
        jsr     F_CLOSE
        addql   #4,%sp
        bsr.w   assign_slot
sv_next:
        addql   #1,IDX
        moveq   #7,%d0
        cmpl    IDX,%d0
        bcc.w   sv_loop
        | One re-arm / refresh after the batch (STORAGE.md §2).
        pea     -1
        jsr     REARM
        addql   #4,%sp
        pea     -1
        jsr     REFRESH
        addql   #4,%sp
        movem.l %sp@,%d2-%d7/%a2-%a5
        lea     %sp@(40),%sp
        rts

| ------------------------------------------------------------------ load
rbp_st_loadall_post:
rbp_st_loadmask_post:
rbp_st_preload_post:
        lea     %sp@(-40),%sp
        movem.l %d2-%d7/%a2-%a5,%sp@
        clrl    IDX
ld_loop:
        moveq   #1,%d0
        addl    IDX,%d0
        lea     FMT_ABS,%a0
        lea     PATH,%a1
        jsr     store_path
        pea     IOB_LEN
        pea     IOB
        pea     MODE_R:l
        pea     PATH
        pea     FO
        jsr     F_OPEN
        lea     %sp@(20),%sp
        tstl    %d0
        bmi.w   ld_next
        pea     FO
        jsr     F_CLOSE
        addql   #4,%sp
        movel   #128,%d3
        addl    IDX,%d3
        movel   %d3,SLOT
        bsr.w   assign_slot
ld_next:
        addql   #1,IDX
        moveq   #7,%d0
        cmpl    IDX,%d0
        bcc.w   ld_loop
        pea     -1
        jsr     REARM
        addql   #4,%sp
        pea     -1
        jsr     REFRESH
        addql   #4,%sp
        movem.l %sp@,%d2-%d7/%a2-%a5
        lea     %sp@(40),%sp
        rts

| PATH = RECn.wav, then stock slot load + post-load (binds ctl name / state).
assign_slot:
        movel   SLOT,%d3
        bsr.w   slot_settings
        moveq   #1,%d0
        addl    IDX,%d0
        lea     FMT_REL,%a0
        moveal  %a2,%a1
        movel   %d0,%sp@-
        movel   %a0,%sp@-
        movel   %a1,%sp@-
        jsr     SPRINTF
        lea     %sp@(12),%sp
        clrl    %sp@-                   | keep_trim = 0
        movel   SLOT,%sp@-
        jsr     SLOT_LOAD
        addql   #8,%sp
        movel   SLOT,%sp@-
        clrl    %sp@-
        jsr     POST_LOAD
        addql   #8,%sp
        rts

slot_settings:
        movel   %d3,%d0
        movel   #SET_STRIDE,%d1
        mulsl   %d1,%d0
        addil   #SETTINGS,%d0
        moveal  %d0,%a2
        rts

slot_ctl:
        movel   %d3,%d0
        movel   #CTL_STRIDE,%d1
        mulsl   %d1,%d0
        addil   #CTL_BASE,%d0
        moveal  %d0,%a3
        rts

        .data
        .align  4
FMT_DIR:  .asciz  "%s/BUFFERS"
FMT_ABS:  .asciz  "%s/BUFFERS/REC%d.wav"
FMT_REL:  .asciz  "BUFFERS/REC%d.wav"
        .align  4

        .section .bss
        .align  4
IDX:    .space  4
SLOT:   .space  4
FRAMES: .space  4
PATH:   .space  260
FO:     .space  32
IOB:    .space  0x10000
