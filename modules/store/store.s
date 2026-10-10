| STORE -- the stock sites where a project's side files are written, read,
| copied and cleared, and where a Part is saved or cleared, owned once.
|
| Each wrapper below replays the instructions its detour displaced and calls
| the clients' handlers (the tables in remix.inc, from manifest.store_inc)
| before or after stock's routine. A handler is entered with every register
| free to clobber; d0, d1, d2 carry:
|
|   loadall_pre/post     none
|   loadmask_pre/post    d1 = the bank mask, d2 = the caller's return address
|   newproj              none
|   bankw_pre            d1 = the mask of banks the writer is about to write
|   bankw_post           none
|   pstore_pre/post      none
|   preload_post         none
|   bankcopy             d0 = the destination path, d1 = the source path,
|                        after stock's copy
|   tocs1, fromcs1       d0 = the bank, before (tocs1) or after (fromcs1)
|                        stock's CS1 copy
|   partsaved            d0 = the part (0..3), the current bank
|   partclear            d0 = the part
|
| The wrappers keep one return slot each; none re-enters.

        .include "remix.inc"

        .set    F_COPY,     0x40016388      | (dst path, src path, 0) -> <0 error
        .set    F_OPEN,     0x40016864      | (fo, path, mode, buffer, size) -> <0 error
        .set    F_READ,     0x40016564      | (fo, dst, n) -> 1
        .set    F_WRITE,    0x400166b8      | (fo, src, n) -> 1
        .set    F_CLOSE,    0x4001677c      | (fo)
        .set    PROJDIR,    0x40025230      | (0, 0) -> the project directory
        .set    SPRINTF,    0x40013a08
        .set    IOB_LEN,    0x1000

        .macro  SAVE
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        .endm
        .macro  REST
        movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        .endm

        .text
        .globl  store_loadall, store_loadmask, store_newproj, store_bankw
        .globl  store_bankw_mid, store_pstore, store_preload, store_fcopy
        .globl  store_d5_ef9a, store_d5_f02e, store_d5_f2a6, store_d5_f33a
        .globl  store_tocs1, store_fromcs1, store_partsaved, store_partclear
        .globl  store_path, store_fopen, store_fread, store_fwrite, store_fclose, store_crc32

| fire: a0 = a table, d0-d2 = the arguments. Calls each handler with them.
fire:
        movel   %d0,FA0
        movel   %d1,FA1
        movel   %d2,FA2
        moveal  %a0,%a2
1:      movel   %a2@+,%d0
        beq.s   2f
        moveal  %d0,%a1
        movel   %a2,%sp@-
        movel   FA0,%d0
        movel   FA1,%d1
        movel   FA2,%d2
        jsr     %a1@
        movel   %sp@+,%a2
        bra.s   1b
2:      rts

| 0x40090504: the project load's bank load.
store_loadall:
        clrl    store_npend             | a new project: nothing refused yet
        clrl    store_shown
        SAVE
        moveq   #0,%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_loadall_pre,%a0
        bsr.w   fire
        REST
        movel   %sp@+,SL_RET
        pea     sl_after
        lea     %sp@(-328),%sp          | displaced
        moveml  %d2-%d7/%a2-%fp,%sp@
        jmp     0x4009050c
sl_after:
        movel   SL_RET,%sp@-
        SAVE
        moveq   #0,%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_loadall_post,%a0
        bsr.w   fire
        REST
        rts

| 0x400905d4 (?, mask, ...): a masked bank load.
store_loadmask:
        clrl    store_shown
        SAVE
        moveq   #0,%d0
        moveq   #0,%d1
        movew   %sp@(60+10),%d1
        movel   %d1,SM_MASK
        movel   %sp@(60),%d2
        movel   %d2,SM_RET
        lea     ev_loadmask_pre,%a0
        bsr.w   fire
        REST
        movel   %sp@+,SM_RET
        pea     sm_after
        lea     %sp@(-328),%sp          | displaced
        moveml  %d2-%d7/%a2-%fp,%sp@
        jmp     0x400905dc
sm_after:
        movel   SM_RET,%sp@-
        SAVE
        moveq   #0,%d0
        movel   SM_MASK,%d1
        movel   SM_RET,%d2
        lea     ev_loadmask_post,%a0
        bsr.w   fire
        REST
        rts

| 0x400909d8: a new, empty project.
store_newproj:
        SAVE
        moveq   #0,%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_newproj,%a0
        bsr.w   fire
        REST
        movel   %a2,%sp@-               | displaced
        clrl    %sp@-
        jsr     0x4000fd34
        jmp     0x400909e2

| 0x400917c8: the bank writer (background save, save-as, new project,
| SAVE PROJECT). After it: bankw_post.
store_bankw:
        movel   %sp@+,BW_RET
        pea     bw_after
        linkw   %fp,#-324               | displaced
        moveml  %d2-%d7/%a2-%a5,%sp@
        jmp     0x400917d0
bw_after:
        movel   BW_RET,%sp@-
        SAVE
        moveq   #0,%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_bankw_post,%a0
        bsr.w   fire
        REST
        rts

| 0x400918aa, inside the bank writer, after the project directory is made
| and before the first bankNN.work: d6 (low word) = the banks it writes.
store_bankw_mid:
        lea     0x400e21e0,%a2          | displaced
        SAVE
        moveq   #0,%d0
        moveq   #0,%d1
        movew   %d6,%d1
        moveq   #0,%d2
        lea     ev_bankw_pre,%a0
        bsr.w   fire
        REST
        jmp     0x400918b0

| 0x4008ee74: the project store. pstore_pre, stock's store, pstore_post.
store_pstore:
        SAVE
        moveq   #0,%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_pstore_pre,%a0
        bsr.w   fire
        REST
        movel   %sp@+,PS_RET
        pea     ps_after
        linkw   %fp,#-560               | displaced
        moveml  %d2-%d7/%a2-%a5,%sp@
        jmp     0x4008ee7c
ps_after:
        movel   PS_RET,%sp@-
        SAVE
        moveq   #0,%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_pstore_post,%a0
        bsr.w   fire
        REST
        rts

| 0x4008f180: the project reload. preload_post.
store_preload:
        movel   %sp@+,PR_RET
        pea     pr_after
        linkw   %fp,#-560               | displaced
        moveml  %d2-%d7/%a2-%a5,%sp@
        jmp     0x4008f188
pr_after:
        movel   PR_RET,%sp@-
        SAVE
        moveq   #0,%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_preload_post,%a0
        bsr.w   fire
        REST
        rts

| The stock file copy (dst, src, 0) at the bank store and bank reload sites,
| and the project store and reload (which call it through d5): stock copies,
| then bankcopy.
store_fcopy:
        movel   %sp@(12),%sp@-
        movel   %sp@(12),%sp@-
        movel   %sp@(12),%sp@-
        jsr     F_COPY
        lea     %sp@(12),%sp
        SAVE                            | d0 = stock's result, kept
        movel   %sp@(60+4),%d0
        movel   %sp@(60+8),%d1
        moveq   #0,%d2
        lea     ev_bankcopy,%a0
        bsr.w   fire
        REST
        rts

store_d5_ef9a:
        movel   #store_fcopy,%d5
        jmp     0x4008efa0
store_d5_f02e:
        movel   #store_fcopy,%d5
        jmp     0x4008f034
store_d5_f2a6:
        movel   #store_fcopy,%d5
        jmp     0x4008f2ac
store_d5_f33a:
        movel   #store_fcopy,%d5
        jmp     0x4008f340

| 0x4000faf0(bank): stock copies the bank into CS1.
store_tocs1:
        SAVE
        movel   %sp@(60+4),%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_tocs1,%a0
        bsr.w   fire
        REST
        movel   %a2,%sp@-               | displaced
        movel   %d2,%sp@-
        movel   #0x8ed80,%sp@-
        jmp     0x4000fafa

| the power-up's 0x4000fbb4(bank) call at 0x40025808: the bank from CS1.
store_fromcs1:
        movel   %sp@(4),%sp@-
        jsr     0x4000fbb4
        addql   #4,%sp
        SAVE
        movel   %sp@(60+4),%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_fromcs1,%a0
        bsr.w   fire
        REST
        rts

| 0x4004a9c4: the stock Part Save's tail, d4 = the part.
store_partsaved:
        SAVE
        movel   %d4,%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_partsaved,%a0
        bsr.w   fire
        REST
        moveml  %sp@,%d2-%d4/%a2-%a3    | displaced
        lea     %sp@(20),%sp
        rts

| 0x4004a9d0 (part): the stock Part Clear's entry; it ends in Part Save.
store_partclear:
        SAVE
        movel   %sp@(60+4),%d0
        moveq   #0,%d1
        moveq   #0,%d2
        lea     ev_partclear,%a0
        bsr.w   fire
        REST
        lea     %sp@(-16),%sp           | displaced
        moveml  %d2-%d3/%a2-%a3,%sp@
        jmp     0x4004a9d8


| ============================================================= refusals ====
| A client that finds a file it cannot use (an unknown version, a length or a
| CRC that does not hold) calls store_refuse and leaves the file alone: it
| plays without it and never writes over it. STORE keeps the list; the prompt
| (store_answer) then offers IGNORE (nothing), OVERWRITE (start empty, write at
| the next save) or BACKUP (copy the file to a .bak name, then OVERWRITE). The
| answer goes to the client's <prefix>_st_answer through ans_tab.
        .set    ANS_IGNORE,     0
        .set    ANS_OVERWRITE,  1
        .set    ANS_BACKUP,     2
        .globl  store_refuse, store_answer, store_answer_cb, store_pend, store_npend

| store_refuse: d0 = the client's id (CLIENT_IDS), d1 = its argument (a bank,
| or 0). Entered again for the same file it adds nothing. Clobbers d0, d1, a0.
store_refuse:
        movel   %d2,%sp@-
        movel   %d3,%sp@-
        lea     store_pend,%a0
        movel   store_npend,%d3
        beq.s   2f
1:      moveq   #0,%d2
        moveb   %a0@+,%d2
        cmpl    %d2,%d0
        bne.s   3f
        moveb   %a0@,%d2
        cmpl    %d2,%d1
        beq.s   9f
3:      addql   #1,%a0
        subql   #1,%d3
        bne.s   1b
2:      movel   store_npend,%d3
        cmpil   #16,%d3
        bcc.s   9f
        lea     store_pend,%a0
        lsll    #1,%d3
        addal   %d3,%a0
        moveb   %d0,%a0@+
        moveb   %d1,%a0@
        addql   #1,store_npend
9:      movel   %sp@+,%d3
        movel   %sp@+,%d2
        rts

| store_answer: d0 = ANS_*, d1 = the entry's number in store_pend. The entry
| leaves the list and its client is called with d0 = the answer, d1 = its
| argument. Clobbers everything the handler does.
store_answer:
        movel   %d0,%sp@-
        movel   store_npend,%d0
        cmpl    %d0,%d1
        bcc.s   8f
        lea     store_pend,%a0
        movel   %d1,%d2
        lsll    #1,%d2
        addal   %d2,%a0                 | a0 = the entry
        moveq   #0,%d2
        moveb   %a0@,%d2                | d2 = client
        moveq   #0,%d3
        moveb   %a0@(1),%d3             | d3 = argument
        subql   #1,%d0
        movel   %d0,store_npend         | one fewer
        subl    %d1,%d0                 | entries behind it
        beq.s   2f
1:      moveb   %a0@(2),%a0@
        moveb   %a0@(3),%a0@(1)
        addql   #2,%a0
        subql   #1,%d0
        bne.s   1b
2:      lea     ans_tab,%a0
        movel   %a0@(0,%d2:l:4),%d0
        beq.s   8f
        moveal  %d0,%a1
        movel   %d3,%d1
        movel   %sp@,%d0
        jsr     %a1@
8:      addql   #4,%sp
        rts

| store_answer_cb(choice, entry): store_answer with the C calling convention,
| for the prompt's callbacks and the port's --call.
store_answer_cb:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %sp@(44+4),%d0
        movel   %sp@(44+8),%d1
        bsr.w   store_answer
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| =============================================================== prompt ====
| A refused file is offered three rows in the firmware's list window (the one
| KITS opens for LOAD KIT): IGNORE, OVERWRITE, BACKUP, each naming the file.
| The list opens at the first encoder turn after the load, the only UI-task
| site STORE holds (a window cannot be opened from the engine task), and
| LEVEL scrolls it. A row's callback answers the first listed file; the next
| asks at the next turn. Closing the list with NO leaves the entries listed
| and asks no more until the next project load.
        .set    M_OPEN,     0x4006d94c      | (count, sel, &sel, labels, callbacks)
        .set    M_OBJ,      0x460e5e30      | long: the open list
        .set    M_CBS,      0x460e5e28      | long: its callbacks, stored by M_OPEN
        .set    M_STATE,    0x460e5e38      | its scroll state
        .set    M_DOWN,     0x4007eca4      | (&state): one row down
        .set    M_UP,       0x4007ec7c      | (&state): one row up
        .set    M_REDRAW,   0x4006d784
        .set    T_OBJ,      0x460e7612      | nonzero: a text editor is open
        .set    CTL_DISP,   0x40031944      | (control, delta): the encoders' dispatch
        .globl  store_ctl

| 0x40061e00 (jsr CTL_DISP, control, delta): an encoder turn.
store_ctl:
        tstl    store_mown
        beq.s   sc_closed
        tstl    M_OBJ
        bne.s   sc_open
        clrl    store_mown              | closed without an answer
sc_closed:
        tstl    store_npend
        beq.s   sc_pass
        tstl    store_shown
        bne.s   sc_pass
        tstl    M_OBJ
        bne.s   sc_pass
        tstl    T_OBJ
        bne.s   sc_pass
        bra.w   prompt_open             | the turn that opens it is spent
sc_open:
        movel   M_CBS,%d0
        cmpil   #store_cbtab,%d0
        bne.s   sc_pass
        moveq   #6,%d0
        cmpl    %sp@(4),%d0
        bne.s   sc_pass
        movel   %d2,%sp@-
        movel   %sp@(12),%d2            | the delta, signed detents
        beq.s   8f
        bpl.s   2f
        negl    %d2
1:      pea     M_STATE
        jsr     M_UP
        addql   #4,%sp
        subql   #1,%d2
        bne.s   1b
        bra.s   3f
2:      pea     M_STATE
        jsr     M_DOWN
        addql   #4,%sp
        subql   #1,%d2
        bne.s   2b
3:      jsr     M_REDRAW
8:      movel   %sp@+,%d2
        rts
sc_pass:
        movel   ev_ctl,%d0              | KITS' list scroll, else stock's dispatch
        beq.s   1f
        moveal  %d0,%a0
        jmp     %a0@
1:      jmp     CTL_DISP

| prompt_open: the first listed file's three rows. A C routine: keeps d2-d7/a2-a6.
prompt_open:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        lea     store_pend,%a0
        moveq   #0,%d2
        moveb   %a0@,%d2                | the client
        moveq   #0,%d3
        moveb   %a0@(1),%d3             | its argument
        addql   #1,%d3
        lea     name_tab,%a1
        movel   %a1@(0,%d2:l:4),%d0
        movel   %d3,%sp@-
        movel   %d0,%sp@-
        pea     store_name
        jsr     SPRINTF
        lea     %sp@(12),%sp
        pea     store_name
        pea     fmt_ignore
        pea     store_row0
        jsr     SPRINTF
        lea     %sp@(12),%sp
        pea     store_name
        pea     fmt_over
        pea     store_row1
        jsr     SPRINTF
        lea     %sp@(12),%sp
        pea     store_name
        pea     fmt_back
        pea     store_row2
        jsr     SPRINTF
        lea     %sp@(12),%sp
        clrl    store_msel
        pea     store_cbtab
        pea     store_lbtab
        pea     store_msel
        clrl    %sp@-
        pea     3
        jsr     M_OPEN
        lea     %sp@(20),%sp
        moveq   #1,%d0
        movel   %d0,store_mown
        movel   %d0,store_shown
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

store_cb0:
        moveq   #ANS_IGNORE,%d0
        bra.s   cb_go
store_cb1:
        moveq   #ANS_OVERWRITE,%d0
        bra.s   cb_go
store_cb2:
        moveq   #ANS_BACKUP,%d0
cb_go:  lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveq   #0,%d1
        bsr.w   store_answer
        clrl    store_mown
        clrl    store_shown             | the next listed file asks at the next turn
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| =============================================================== files ====
| The file calls a client uses. A client owns a context of STORE_CTX = 4,120
| bytes (.space 4120, 4-byte aligned): the stock file object (24 B) and its
| 4 KB buffer. Handlers of different events never share a context, so one
| client's open file is not disturbed by another's. Each call clobbers d0,
| d1, a0, a1 and keeps everything else; a2 = the context.

| store_path: a0 = format ("%s/name.ext", or one more %d), a1 = a 260-byte
| buffer, d0 = the number a second %d takes (0 when the format has none).
store_path:
        movel   %a2,%sp@-
        movel   %a3,%sp@-
        moveal  %a0,%a2
        moveal  %a1,%a3
        movel   %d0,%sp@-
        clrl    %sp@-
        clrl    %sp@-
        jsr     PROJDIR
        addql   #8,%sp
        movel   %d0,%sp@-
        movel   %a2,%sp@-
        movel   %a3,%sp@-
        jsr     SPRINTF
        lea     %sp@(16),%sp
        movel   %sp@+,%a3
        movel   %sp@+,%a2
        rts

| store_fopen: a0 = path, a1 = mode, a2 = ctx -> d0 (< 0: failed).
store_fopen:
        pea     IOB_LEN
        pea     %a2@(24)
        movel   %a1,%sp@-
        movel   %a0,%sp@-
        pea     %a2@
        jsr     F_OPEN
        lea     %sp@(20),%sp
        rts

| store_fread / store_fwrite: a0 = buffer, d0 = length, a2 = ctx -> d0 (1: done).
store_fread:
        movel   %d0,%sp@-
        movel   %a0,%sp@-
        pea     %a2@
        jsr     F_READ
        lea     %sp@(12),%sp
        rts
store_fwrite:
        movel   %d0,%sp@-
        movel   %a0,%sp@-
        pea     %a2@
        jsr     F_WRITE
        lea     %sp@(12),%sp
        rts

store_fclose:
        pea     %a2@
        jsr     F_CLOSE
        addql   #4,%sp
        rts

| store_crc32: a0 = data, d0 = length, d1 = the CRC of what came before (0
| to start) -> d0 = the CRC-32 (zlib's); the table is built on the first call. Keeps d2-d7/a2-a6; clobbers d1, a0.
store_crc32:
        movel   %d2,%sp@-
        movel   %a2,%sp@-
        movel   %d0,%d2
        movel   %d1,%sp@-
        bsr.s   crc_init
        movel   %sp@+,%d1
        lea     CRCTAB,%a2
        movel   %d1,%d0                 | the running value, 0 to start
        notl    %d0
        tstl    %d2
        beq.s   2f
1:      moveq   #0,%d1
        moveb   %a0@+,%d1
        eorl    %d0,%d1
        andil   #0xff,%d1
        lsrl    #8,%d0
        movel   %a2@(0,%d1:l:4),%d1
        eorl    %d1,%d0
        subql   #1,%d2
        bne.s   1b
2:      notl    %d0
        movel   %sp@+,%a2
        movel   %sp@+,%d2
        rts

crc_init:
        tstl    CRCREADY
        bne.s   9f
        movel   %d2,%sp@-
        movel   %a0,%sp@-
        lea     CRCTAB,%a0
        moveq   #0,%d0
1:      movel   %d0,%d1
        moveq   #7,%d2
2:      lsrl    #1,%d1
        bcc.s   3f
        eoril   #0xedb88320,%d1
3:      subql   #1,%d2
        bpl.s   2b
        movel   %d1,%a0@+
        addql   #1,%d0
        cmpil   #256,%d0
        bne.s   1b
        moveq   #1,%d0
        movel   %d0,CRCREADY
        movel   %sp@+,%a0
        movel   %sp@+,%d2
9:      rts

        .section .data
        .align  4
SL_RET: .long   0
SM_RET: .long   0
SM_MASK: .long  0
BW_RET: .long   0
PS_RET: .long   0
PR_RET: .long   0
FA0:    .long   0
FA1:    .long   0
FA2:    .long   0
store_mown:  .long 0            | the prompt's list is open
store_shown: .long 0            | the prompt has been shown since the last project load
store_msel:  .long 0
store_cbtab: .long store_cb0, store_cb1, store_cb2
store_lbtab: .long store_row0, store_row1, store_row2
fmt_ignore:  .asciz "IGNORE %s"
fmt_over:    .asciz "OVERWRITE %s"
fmt_back:    .asciz "BACKUP %s"
        .align  4
CRCREADY: .long 0
store_npend: .long 0

        .section .bss
        .align  4
CRCTAB: .space  256*4
store_pend: .space 32
store_name: .space 32
store_row0: .space 40
store_row1: .space 40
store_row2: .space 40
