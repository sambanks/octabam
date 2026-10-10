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
