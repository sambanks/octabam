| octabam's early loader -- appended after the OS image, runs once at boot.
|
| Derived from Em's Octakit loader (emuyia/ems-octakit, runtime/loader.S),
| whose design this is: a stub past the end of the OS that the boot path
| detours into, which copies a packed payload to a persistent stage,
| hash-gates it, depacks it with the firmware's OWN aPLib routine into a
| DRAM window, hash-gates the result and keeps a backup copy. Generalised
| here to a TABLE of payloads so that her Kit runtime and every other
| module's DRAM code are equal payloads of one loader.
|
| Fixed facts (all measured, docs/remixer/PLACEMENT.md):
|   0x4010fdf0  this stub: the byte after the stock OS image (her BOOTSTRAP_LOAD)
|   0x40001e50  the stock boot-continue call the boot site used to make;
|               replayed first, exactly as her loader does
|   0x400e0aca  the stock aPLib depacker: pea dst ; pea src(GKA3 header) ; jsr
|   +0x08000000 the uncached SDRAM alias every copy and depack writes through
|
| Table entry (eight longs; built by tools/remix/platform_build.py):
|   src       address of the staged blob's SOURCE in this append (4-byte
|             signature, then the "GKA3"+size+packed stream)
|   len       total staged length, signature included
|   phash     rolling x33 hash of the packed stream (len-4 bytes from src+4)
|   stage     uncached address the blob is copied to and depacked FROM --
|             persistent: Octakit's post-clear relocation re-depacks from
|             her stage (0x4ffc7414) after stock zero-fills her window
|   dst       uncached address the payload is depacked to
|   rawlen    depacked size (must equal the GKA3 header's)
|   rhash     rolling x33 hash of the depacked payload
|   backup    uncached address of a backup copy, or 0 for none
| A `bra fatal` hang on any mismatch, as hers: a half-loaded runtime is
| worse than a visibly stuck boot.
|
| Registers inside the loop: a2 table cursor, d7 payloads left, d6 stage,
| d5 len then rawlen, d4 dst, d3 expected hash; d0/d1/d2/a0/a1 scratch.

        .set    BOOT_CONTINUE, 0x40001e50
        .set    APLIB_DEPACK,  0x400e0aca

        .text
        .global octabam_bootstrap
octabam_bootstrap:
        jsr     (BOOT_CONTINUE).l
        lea     (-48,%sp),%sp
        movem.l %d0-%d7/%a0-%a2,(%sp)
        lea     table(%pc),%a2
        move.l  (%a2)+,%d7              | payload count
        beq.w   done
next:
        move.l  (%a2)+,%a0              | src
        move.l  (%a2)+,%d5              | len (signature + GKA3 stream)
        move.l  (%a2)+,%d3              | phash
        move.l  (%a2)+,%d6              | stage (uncached)
        move.l  %d6,%a1
        move.l  %d5,%d0
        bsr.w   copy                    | stage <- src, len bytes
        move.l  %d6,%a0
        addq.l  #4,%a0                  | the GKA3 stream, past the signature
        move.l  %d5,%d0
        subq.l  #4,%d0
        bsr.w   hash
        cmp.l   %d3,%d1
        bne.w   fatal
        move.l  %d6,%a0
        addq.l  #4,%a0
        move.l  (%a0)+,%d1              | GKA3 header: magic
        cmpi.l  #0x474b4133,%d1
        bne.w   fatal
        move.l  (%a2)+,%d4              | dst (uncached)
        move.l  (%a2)+,%d5              | rawlen
        move.l  (%a0),%d1               | header: depacked size
        cmp.l   %d5,%d1
        bne.w   fatal
        move.l  %d4,-(%sp)              | pea dst
        move.l  %d6,%d1
        addq.l  #4,%d1
        move.l  %d1,-(%sp)              | pea GKA3 stream (stage + 4)
        jsr     (APLIB_DEPACK).l
        lea     (8,%sp),%sp
        tst.l   %d0
        bne.w   fatal
        move.l  %d4,%a0
        move.l  %d5,%d0
        bsr.w   hash
        move.l  (%a2)+,%d3              | rhash
        cmp.l   %d3,%d1
        bne.w   fatal
        move.l  (%a2)+,%d1              | backup (uncached) or 0
        beq.w   nobackup
        move.l  %d4,%a0
        move.l  %d1,%a1
        move.l  %d5,%d0
        bsr.w   copy
nobackup:
        subq.l  #1,%d7
        bne.w   next
done:
        movem.l (%sp),%d0-%d7/%a0-%a2
        lea     (48,%sp),%sp
        rts
fatal:
        bra.w   fatal

| copy: (a1) <- (a0), d0 bytes (d0 > 0). Clobbers a0, a1, d0.
copy:
        move.b  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.w   copy
        rts

| hash: d1 = rolling x33 over d0 bytes at (a0) -- the function her
| OS-resident helper computes, so her packed/raw hashes are ours.
| Clobbers a0, d0, d1, d2.
hash:
        moveq   #0,%d1
hashloop:
        move.l  %d1,%d2
        lsl.l   #5,%d1
        add.l   %d2,%d1
        moveq   #0,%d2
        move.b  (%a0)+,%d2
        add.l   %d2,%d1
        subq.l  #1,%d0
        bne.w   hashloop
        rts

        .align  4
table:
        .include "table.inc"
