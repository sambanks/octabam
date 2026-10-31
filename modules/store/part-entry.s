/* Early-ROM gates. Stock memcpy is used before the platform loader runs.
 * Only the native post-loader call publishes the two DRAM entry pointers.
 * C ABI volatile a0 is assigned by both native bodies before it is consumed.
 */
    .text
    .global store_part_copy_entry,store_part_init_entry,store_part_copy_target,store_part_init_target
store_part_copy_entry:
    move.l store_part_copy_target,%a0
    cmpa.l #0,%a0
    beq.s .copy_stock
    jmp (%a0)
.copy_stock:
    move.l %d2,-(%sp)
    move.l 8(%sp),%a1
    jmp 0x4002089e
store_part_init_entry:
    move.l store_part_init_target,%a0
    cmpa.l #0,%a0
    beq.s .init_stock
    jmp (%a0)
.init_stock:
    lea -88(%sp),%sp
    movem.l %d2-%d7/%a2-%a6,(%sp)
    jmp 0x40005640
    .balign 4
store_part_copy_target: .long 0
store_part_init_target: .long 0

/* Boot activation stays in the OS entry unit. Callback symbols are resolved
 * from the final runtime link; the native continuation and stores are unchanged.
 * Keep the unused original runtime body for now to preserve runtime layout.
 */
.global store_part_resident_activate
store_part_resident_activate:
    move.l %d0,-(%sp)
    move.l #store_part_native_copy,%d0
    move.l %d0,store_part_copy_target
    move.l #store_part_native_init,%d0
    move.l %d0,store_part_init_target
    move.l (%sp)+,%d0
    jmp 0x4000f938
