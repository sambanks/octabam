/* Native Part access owned by STORE. Read windows and writable bytes are
 * registered by clients at build time; field meaning remains with clients.
 * Context = bank * 4 + Part, 0..63; -1 means unavailable. Read/write take
 * explicit context so queued events never consult the current UI selection.
 * All public entries preserve every register except d0 and condition codes.
 */
    .include "remix.inc"
    .text
    .global store_part_ui_context,store_part_audio_context,store_part_midi_context,store_part_midi_read,store_part_midi_write,store_part_midi_key,store_part_epoch
store_part_ui_context:
    lea -12(%sp),%sp
    movem.l %d1-%d2/%a0,(%sp)
    move.l 0x46c82456,%d0
    subi.l #0x400e21e0,%d0
    cmpi.l #0x9b340*16,%d0
    bcc.s .ui_bad
    move.l %d0,%d2
    move.l #0x9b340,%d1
    divu.l %d1,%d0
    mulu.l %d0,%d1
    cmp.l %d1,%d2
    bne.s .ui_bad
    lsl.l #2,%d0
    moveq #0,%d1
    move.b 0x100b14cf,%d1
    cmpi.l #3,%d1
    bhi.s .ui_bad
    add.l %d1,%d0
    bra.s .ui_done
.ui_bad:
    moveq #-1,%d0
.ui_done:
    movem.l (%sp),%d1-%d2/%a0
    lea 12(%sp),%sp
    rts

/* d0 context -> replacement epoch, or -1. Runtime-only history invalidation;
 * ordinary single-field UI edits do not replace a Part or change its epoch. */
store_part_epoch:
    cmpi.l #63,%d0
    bhi.s .epoch_bad
    move.l %a0,-(%sp)
    lea store_part_epochs,%a0
    move.l (%a0,%d0.l*4),%d0
    move.l (%sp)+,%a0
    rts
.epoch_bad:
    moveq #-1,%d0
    rts

/* d0 track. Audio and MIDI engines have distinct per-track latches.
 * Both fall back to the applied engine context while unlatched. */
store_part_audio_context:
    lea -8(%sp),%sp
    movem.l %d1/%a0,(%sp)
    lea 0x8000182a,%a0
    bra.s .play_read
store_part_midi_context:
    lea -8(%sp),%sp
    movem.l %d1/%a0,(%sp)
    lea 0x8000666e,%a0
.play_read:
    cmpi.l #7,%d0
    bhi.s .play_bad
    moveq #0,%d1
    move.b (%a0,%d0.l),%d1
    addq.l #8,%a0
    move.b (%a0,%d0.l),%d0
    andi.l #255,%d0
    cmpi.l #15,%d1
    bhi.s .play_applied
    cmpi.l #3,%d0
    bls.s .play_pack
.play_applied:
    moveq #0,%d1
    move.b 0x80001828,%d1
    moveq #0,%d0
    move.b 0x80001829,%d0
    cmpi.l #15,%d1
    bhi.s .play_bad
    cmpi.l #3,%d0
    bhi.s .play_bad
.play_pack:
    lsl.l #2,%d1
    add.l %d1,%d0
    bra.s .play_done
.play_bad:
    moveq #-1,%d0
.play_done:
    movem.l (%sp),%d1/%a0
    addq.l #8,%sp
    rts

/* d0 Part-relative offset,d1 context -> a0 working byte,a1 bank,
 * d0 working-array offset,d4 Part; invalid input -> d0=-1. */
.address:
    cmpi.l #0x18b2,%d0
    bcc.w .address_bad
.address_in_part:
    cmpi.l #63,%d1
    bhi.w .address_bad
    STORE_PART_READ_GUARD .address_bad
    move.l %d1,%d4
    andi.l #3,%d4
    move.l #0x18b2,%d5
    mulu.l %d4,%d5
    add.l %d5,%d0
    move.l %d1,%d5
    lsr.l #2,%d5
    move.l #0x9b340,%d6
    mulu.l %d6,%d5
    lea 0x400e21e0,%a1
    adda.l %d5,%a1
    move.l %a1,%a0
    adda.l #0x8ed80,%a0
    adda.l %d0,%a0
    rts
.address_bad:
    moveq #-1,%d0
    rts

/* d0 Part offset,d1 context -> byte or -1. */
.global store_part_read
store_part_read:
    lea -20(%sp),%sp
    movem.l %d4-%d6/%a0-%a1,(%sp)
    bsr.w .address
.read_value:
    tst.l %d0
    bmi.s .read_done
    bsr.w .snapshot_address
    moveq #0,%d0
    move.b (%a0),%d0
.read_done:
    movem.l (%sp),%d4-%d6/%a0-%a1
    lea 20(%sp),%sp
    rts

.snapshot_address:
    cmpa.l store_part_snapshot_bank,%a1
    bne.s .snapshot_done
    move.l store_part_snapshot_parts,%d5
    btst %d4,%d5
    beq.s .snapshot_done
    move.l #0x18b2,%d5
    mulu.l %d4,%d5
    neg.l %d5
    add.l %d0,%d5
    STORE_PART_SNAPSHOT_INDEX
    move.l #STORE_PART_STRIDE,%d6
    mulu.l %d4,%d6
    add.l %d6,%d5
    lea store_part_snapshot,%a0
    adda.l %d5,%a0
.snapshot_done:
    rts

/* d0 Part offset,d1 context,d3 byte -> 1 accepted,0 invalid/busy.
 * Registered byte writes are atomic with the native mirror/dirty updates.
 * Refuse writes into a replacement transaction rather than lose an edit. */
.global store_part_write
store_part_write:
    lea -24(%sp),%sp
    movem.l %d4-%d7/%a0-%a1,(%sp)
    cmpi.l #255,%d3
    bhi.w .write_bad
    cmpi.l #0x18b2,%d0
    bcc.w .write_bad
    STORE_PART_WRITE_GUARD .write_bad
    bsr.w .address
    tst.l %d0
    bmi.w .write_bad
    move.w %sr,%d7
    move.w #0x2700,%sr
    cmpa.l store_part_snapshot_bank,%a1
    bne.s .write_ready
    move.l store_part_snapshot_parts,%d5
    btst %d4,%d5
    bne.s .write_busy
.write_ready:
    cmp.b (%a0),%d3
    beq.s .write_restore
    move.b %d3,(%a0)
    move.l %a1,%a0
    adda.l #0x95048,%a0
    bset %d4,(%a0)
    moveq #1,%d6
    move.l %a1,%a0
    adda.l #0x9b332,%a0
    move.l %d6,(%a0)
    cmpa.l 0x46c82456,%a1
    bne.s .write_restore
    lea 0x100a4ece,%a0
    move.b %d3,(%a0,%d0.l)
    bset %d4,0x100b145e
    move.l %d6,0x100f8598
.write_restore:
    move.w %d7,%sr
    moveq #1,%d0
    bra.s .write_done
.write_busy:
    move.w %d7,%sr
.write_bad:
    moveq #0,%d0
.write_done:
    movem.l (%sp),%d4-%d7/%a0-%a1
    lea 24(%sp),%sp
    rts

/* MIDI layout adapters: d0 track,d1 context,d2 SETUP field,d3 value.
 * Valid track/field pairs are necessarily inside the Part. Keep the general
 * context/window and snapshot checks, sharing the reader's register frame. */
store_part_midi_read:
    cmpi.l #7,%d0
    bhi.s .midi_read_bad
    cmpi.l #35,%d2
    bhi.s .midi_read_bad
    lea -20(%sp),%sp
    movem.l %d4-%d6/%a0-%a1,(%sp)
    moveq #36,%d4
    mulu.l %d4,%d0
    add.l %d2,%d0
    addi.l #0x4e2,%d0
.midi_read_address:
    bsr.w .address_in_part
    bra.w .read_value
.midi_read_bad:
    moveq #-1,%d0
    rts
store_part_midi_key:
    cmpi.l #7,%d0
    bhi.s .midi_read_bad
    lea -20(%sp),%sp
    movem.l %d4-%d6/%a0-%a1,(%sp)
    moveq #36,%d4
    mulu.l %d4,%d0
    addi.l #0x4e2+17,%d0
    bra.s .midi_read_address
store_part_midi_write:
    cmpi.l #7,%d0
    bhi.s .midi_write_bad
    cmpi.l #35,%d2
    bhi.s .midi_write_bad
    cmpi.l #127,%d3
    bhi.s .midi_write_bad
    move.l %d4,-(%sp)
    moveq #36,%d4
    mulu.l %d4,%d0
    move.l (%sp)+,%d4
    add.l %d2,%d0
    addi.l #0x4e2,%d0
    bra.w store_part_write
.midi_write_bad:
    moveq #0,%d0
    rts
    STORE_PART_WRITE_TABLE
