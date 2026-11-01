/* Publish native Part replacement coherently without masking interrupts
 * throughout a native copy/clear. While a bank is being replaced, shared
 * readers see its complete outgoing registered-field snapshot. The single UI
 * writer publishes the incoming bytes by clearing the snapshot pointer.
 * No KITS dependency. Nested stock calls retain the outer transaction.
 */
    .include "remix.inc"
    .text
    .global store_part_native_copy,store_part_native_init,store_part_snapshot_bank,store_part_snapshot,store_part_activate,store_part_snapshot_parts,store_part_epochs
/* The platform's verified loader has returned before this native boot call.
 * Tail-call preserves the original stock return address at 0x40000518.
 */
store_part_activate:
    move.l %d0,-(%sp)
    move.l #store_part_native_copy,%d0
    move.l %d0,store_part_copy_target
    move.l #store_part_native_init,%d0
    move.l %d0,store_part_init_target
    move.l (%sp)+,%d0
    jmp 0x4000f938
store_part_native_copy:
    lea -24(%sp),%sp
    movem.l %d0-%d1/%a0-%a1,(%sp)
    move.l 28(%sp),%d0
    move.l 36(%sp),%d1
    bsr.w .begin
    move.l %d0,16(%sp)
    movem.l (%sp),%d0-%d1/%a0-%a1
    move.l 36(%sp),-(%sp)
    move.l 36(%sp),-(%sp)
    move.l 36(%sp),-(%sp)
    bsr.w .copy_stock
    lea 12(%sp),%sp
    bra.s .finish
store_part_native_init:
    lea -24(%sp),%sp
    movem.l %d0-%d1/%a0-%a1,(%sp)
    move.l 28(%sp),%d0
    move.l #0x18b2,%d1
    bsr.w .begin
    move.l %d0,16(%sp)
    movem.l (%sp),%d0-%d1/%a0-%a1
    move.l 28(%sp),-(%sp)
    bsr.w .init_stock
    addq.l #4,%sp
.finish:
    tst.l 16(%sp)
    beq.s .finished
    /* Epoch and settings publication are one short critical section.
     * No native copying, initialization or degree callback runs masked. */
    lea -20(%sp),%sp
    movem.l %d0-%d3/%a0,(%sp)
    move.w %sr,%d3
    move.w #0x2700,%sr
    move.l store_part_snapshot_bank,%d0
    subi.l #0x400e21e0,%d0
    move.l #0x9b340,%d1
    divu.l %d1,%d0
    lsl.l #4,%d0
    lea store_part_epochs,%a0
    adda.l %d0,%a0
    move.l store_part_snapshot_parts,%d1
    moveq #0,%d2
.epoch_part:
    btst %d2,%d1
    beq.s .epoch_next
    addq.l #1,(%a0)
.epoch_next:
    addq.l #4,%a0
    addq.l #1,%d2
    cmpi.l #4,%d2
    bne.s .epoch_part
    clr.l store_part_snapshot_bank
    clr.l store_part_snapshot_parts
    move.w %d3,%sr
    movem.l (%sp),%d0-%d3/%a0
    lea 20(%sp),%sp
.finished:
    lea 24(%sp),%sp
    rts
.copy_stock:
    STORE_PART_COPY_OVERRIDE
    move.l %d2,-(%sp)
    move.l 8(%sp),%a1
    jmp 0x4002089e
.init_stock:
    lea -88(%sp),%sp
    movem.l %d2-%d7/%a2-%a6,(%sp)
    jmp 0x40005640

/* d0 destination,d1 length. Only resident bank writes intersecting working
 * Parts need a snapshot. Native copies spanning multiple banks are not a
 * live Part operation. Snapshot preparation only reads unchanged bytes:
 * interrupts remain enabled, including throughout native initialization.
 */
.begin:
    lea -32(%sp),%sp
    movem.l %d1-%d5/%a0-%a2,(%sp)
    tst.l store_part_snapshot_bank
    bne.w .no_begin
    tst.l %d1
    beq.w .no_begin
    move.l %d0,%d2
    subi.l #0x400e21e0,%d2
    cmpi.l #16*0x9b340,%d2
    bcc.w .no_begin
    move.l %d2,%d3
    move.l #0x9b340,%d4
    divu.l %d4,%d3
    mulu.l %d3,%d4
    sub.l %d4,%d2
    add.l %d2,%d1
    bcs.w .no_begin
    cmpi.l #0x9b340,%d1
    bhi.w .no_begin
    cmpi.l #0x8ed80,%d1
    bls.w .no_begin
    cmpi.l #0x95048,%d2
    bcc.w .no_begin
    addi.l #0x400e21e0,%d4
    move.l %d4,%d5
    /* Publish the exact overlapped Parts, including partial SETUP copies. */
    moveq #0,%d0
    moveq #0,%d3
    move.l #0x8ed80,%d4
.mask_part:
    cmp.l %d4,%d1
    bls.s .mask_next
    move.l %d4,%a0
    adda.l #0x18b2,%a0
    cmpa.l %d2,%a0
    bls.s .mask_next
    bset %d3,%d0
.mask_next:
    addi.l #0x18b2,%d4
    addq.l #1,%d3
    cmpi.l #4,%d3
    bne.s .mask_part
    move.l %d0,store_part_snapshot_parts
    move.l %d5,%a0
    adda.l #0x8ed80,%a0
    lea store_part_snapshot,%a1
    moveq #4,%d3
.snapshot_part:
    STORE_PART_SNAPSHOT_COPY
    adda.l #0x18b2,%a0
    subq.l #1,%d3
    bne.s .snapshot_part
    .if STORE_PART_HAS_SNAPSHOT_PRE
    move.l %d5,%d0
    STORE_PART_SNAPSHOT_PRE
    .endif
    move.l %d5,store_part_snapshot_bank
    .if STORE_PART_HAS_REPLACE_PRE
    moveq #0,%d3
    move.l store_part_snapshot_parts,%d2
.before_part:
    btst %d3,%d2
    beq.s .before_next
    move.l #0x18b2,%d0
    mulu.l %d3,%d0
    add.l %d5,%d0
    addi.l #0x8ed80,%d0
    STORE_PART_REPLACE_PRE
.before_next:
    addq.l #1,%d3
    cmpi.l #4,%d3
    bne.s .before_part
    .endif
    moveq #1,%d0
    bra.s .begin_done
.no_begin:
    moveq #0,%d0
.begin_done:
    movem.l (%sp),%d1-%d5/%a0-%a2
    lea 32(%sp),%sp
    rts
    .balign 4
store_part_snapshot_bank: .long 0
store_part_snapshot_parts: .long 0
store_part_snapshot: .space 4*STORE_PART_STRIDE
store_part_epochs: .space 64*4
