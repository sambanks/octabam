| DSP RESET PROBE -- can the ColdFire reset the DSP?
|
| OS SWITCH needs each DSP core to be in its HI08 boot ROM when the OS it
| switches into runs its upload (0x40001e50). The soft reset restarts the
| ColdFire and NOT the DSP (measured on the unit, BOOT TRACE build 4), so
| every image that can switch AWAY carries 40 words of park code in both
| payloads -- and payload A has no room for them in a full remix, which is
| why the stage-B builds are boot-only targets.
|
| If the ColdFire can reset the DSP in hardware there is no park at all, no
| DSP words, and every image can switch. This probe asks the one candidate
| left after the register map was read: RSTOUT, the reset controller's
| output to the rest of the board (RCR bit 6, FRCRSTOUT, 0xfc0a0000).
| The other candidate is retracted: the pin the bootstrap drives once at
| 0x400e0dce is 0xfc0a4024, the DATA DIRECTION register of the port whose
| output register 0xfc0a400c is the DSP core select -- it makes the select
| pin an output, it is not a reset line (docs/firmware/ARCHITECTURE.md).
|
| WHAT IT MEASURES, and why it can see both answers. The instrument is the
| boot ROM's own protocol (micro.asm): seven words that answer with a magic
| if, and only if, a ROM is listening. Each pass runs it three times:
|
|   the control   no pulse, core 0. The payload is running, so nothing may
|                 answer. An answer here means the instrument is broken --
|                 a stale word, an echo -- and the probe stops and says so
|                 rather than reporting a reset that did not happen.
|   the test      after the pulse, core 0 and core 1.
|
| Two passes: a bare write/clear pair (RSTOUT asserted for the few bus
| cycles between them), then a ~1 ms hold. A DSP reset pin that needs
| longer than a pulse would show up in the second pass only.
|
| WHERE IT RUNS: 0x40000518, the instruction after the boot's DSP upload
| returned (and after 0x4000f938). Chosen because everything that could
| care is either finished or not started: the payloads are up, so there is
| something to reset; the panel link (0x4001f834), the card and the RTOS
| come later, so if RSTOUT does reach the panel controller the OS
| initialises it afterwards anyway. Nothing is written to the flash and
| nothing to the card: a power-cycle is always the way out.
|
| EVERY STEP REPORTS BEFORE IT ACTS. If a pulse takes the unit down, the
| last note received names the step that did it (BOOT TRACE's lesson).
| Note On, channel 1, MIDI OUT (UART0, polled, at most POLL polls a byte,
| so a dead port costs time and never a hang):
|
|   40  the probe is in                              velocity 1
|   41  the control pass                             velocity = a code below
|   42  about to pulse                               velocity = the pass (1, 2)
|   43  the test, core 0                             velocity = a code below
|   44  the test, core 1 (not in a PARK build: core 1 is the positive
|       control's, and parked)                       velocity = a code below
|   45  a core answered: re-pulsing, then re-uploading both payloads
|   46  the stock upload returned -- audio should be back
|   47  done                                         velocity = the bitmap below
|   48  the control pass answered: the instrument is not trustworthy, so no
|       conclusion is drawn                          velocity = its code
|   50  (PARK only, FIRST) core 1 sent OS SWITCH's park command: velocity 1
|       if the core took it, 0 if it never did
|   51  (PARK only, FIRST) the POSITIVE CONTROL: the parked core's answer,
|       same codes. 1 is the one that matters -- see below
|   49  the word an unexpected answer carried, three notes: bits 6..0,
|       13..7, 20..14
|
| result codes (notes 41, 43, 44, 48)
|   0  no answer: the core is not in a boot ROM (what a running payload does)
|   1  the magic for that core came back: the core IS in its boot ROM
|   2  a word came back, but not that core's magic (note 49 carries it)
|   3  the host port would not take a word (the send timed out)
| the bitmap (note 47): bit 0 core 0 answered, bit 1 core 1, bits 3..2 the
| pass it answered in, bit 4 the stock upload was re-run, bit 5 the control
| pass answered, bit 6 the POSITIVE CONTROL answered.
|
| THE CELL (`dr_cell`, seven longs in this unit's own bytes, so it exists
| in any remix and needs no claim on DRAM) carries the same results for a
| reader with no MIDI monitor; tools/verify/verify_dspreset.py reads it
| under the port, by symbol.
|   +0   "DRP1"                      +16  core 1's word
|   +4   the control pass's word     +20  the bitmap
|   +8   the pass a core answered    +24  that pass's RSTOUT hold
|   +12  core 0's word
|
| THE POSITIVE CONTROL (PARK, i.e. a remix with OS SWITCH). Everything
| above is a NEGATIVE result: no core answered. A negative from an
| instrument that has never been seen to say yes ON THIS MACHINE is worth
| little -- the port's model is not the machine (AGENTS.md). So when
| nothing answered, the probe finishes by making a listening ROM itself:
| OS SWITCH's park command turns core 0's running payload into a boot-ROM
| loader (dsp_park.asm), and the same seven words are sent to it again.
| That core MUST answer. If it does, "no answer" earlier means there was
| no ROM; if it does not, the probe cannot see a ROM on hardware at all
| and every no above is void. It runs last because a parked core cannot be
| given back its payload -- there is no way into a boot ROM from a park,
| which is the whole reason this module exists.
|
| THE RISK, stated: the control pass sends nine words into a RUNNING
| payload's host port, and a payload that is handed a partial frame never
| gets back in step. That is the price of the control, and without the
| control an answer means nothing -- so the probe ends by uploading both
| payloads again in EVERY case (the restore, below), and the boot goes on
| with a DSP in the state the boot left it in. What is not repaired that
| way is a pulse that takes the unit down: a power-cycle, and the flash is
| never written.

| PARK: 1 when the remix carries OS SWITCH, whose DSP park (host command
| $12 on vector P:$24) is what the positive control needs. manifest.py
| writes it (schema.Linked.include).
        .include "remix.inc"

        .set    DSP_SELECT,  0xfc0a400c | which core's host port the window shows
        .set    HI08_ICR,    0x20000000 | host side: 0x81 = INIT|RREQ
        .set    HI08_CVR,    0x20000004 | the host command register
        .set    HI08_ISR,    0x20000008 | bit 0 RXDF, bits 1|2 TXDE|TRDY
        .set    HI08_H,      0x20000014 | TXH on a write, RXH on a read
        .set    HI08_M,      0x20000018
        .set    HI08_L,      0x2000001c | the low byte starts the transfer
        .set    RCR,         0xfc0a0000 | the reset controller (MCF54455 RM)
        .set    FRCRSTOUT,   0x40       | bit 6: force RSTOUT
        .set    DSP_UPLOAD,  0x40001e50 | the stock DSP boot sequence, re-run
        .set    PARK_HC,     0x0092     | HC | $12: OS SWITCH's park (switch.s
                                        | parkcore sends the same word)
        .set    UART0_USR,   0xfc060004 | MIDI OUT (tools/emu/README.md)
        .set    UART0_UTB,   0xfc06000c
        .set    POLL,        200000     | polls before a MIDI byte gives up
        .set    HPOLL,       4000       | ... and before a host-port wait does.
                                        | Short on purpose: a core in its ROM
                                        | answers in a handful of polls, and a
                                        | RUNNING payload leaves a word unread
                                        | in its receive register, which holds
                                        | TXDE low for good -- the stock sender
                                        | waits there forever and this must not
                                        | (under the port a long spin is a
                                        | FAULT, on the unit it is a dead boot)
        .set    HOLD,        0x00033000 | pass 2's RSTOUT hold, ~1 ms at 264
                                        | MHz (cycle count INFERRED)
        .set    MICRO_N,     7          | words in the micro program
        .set    MICRO_AT,    0x31000    | where the ROM is asked to put it:
                                        | the shared window, where the stock
                                        | upload puts bootstrap A
        .set    MAGIC,       0x5a3c60   | the magic the micro program answers
                                        | with, | the core number: the one
                                        | word of the table that is not an
                                        | instruction, so the sender finds it
                                        | by value
        .set    CELL_MAGIC,  0x44525031 | "DRP1"
        .set    C_CTRL,      4          | the cell's fields
        .set    C_PASS,      8
        .set    C_C0,        12
        .set    C_C1,        16
        .set    C_BITS,      20
        .set    C_HOLD,      24
        .set    C_PC,        28         | the positive control's word

        .text

| ---- the boot detour ---------------------------------------------------------
| 0x40000518, `movea.l #0x46025de0,%a0`: replayed, then the boot goes on.
        .global dr_entry
dr_entry:
        lea     (-48,%sp),%sp
        movem.l %d0-%d7/%a0-%a2,(%sp)
        bsr.w   dr_run
        movem.l (%sp),%d0-%d7/%a0-%a2
        lea     (48,%sp),%sp
        movea.l #0x46025de0,%a0
        jmp     (0x4000051e).l

| ---- the probe ---------------------------------------------------------------
| a2 = the cell, d7 = the result bitmap, d6 = the pass, d4/d5 = the codes.
| The pass's RSTOUT hold lives in the cell (C_HOLD), not in a register: the
| test pass between the pulse and the restore needs d3 for the core number.
dr_run:
        lea     (dr_cell).l,%a2
        move.l  #CELL_MAGIC,%d0
        move.l  %d0,(%a2)
        moveq   #0,%d0
        move.l  %d0,(C_CTRL,%a2)
        move.l  %d0,(C_PASS,%a2)
        move.l  %d0,(C_C0,%a2)
        move.l  %d0,(C_C1,%a2)
        move.l  %d0,(C_BITS,%a2)
        move.l  %d0,(C_HOLD,%a2)
        move.l  %d0,(C_PC,%a2)
        moveq   #0,%d7
        moveq   #40,%d0
        moveq   #1,%d1
        bsr.w   dr_note

        .if     PARK
| ---- the positive control, FIRST and on CORE 1 ------------------------------
| Everything below this is a negative result, and a negative from an
| instrument never seen to say yes ON THIS MACHINE is worth little (the
| port's model is not the machine). So before anything else, make a
| listening boot ROM and ask it: OS SWITCH's park command turns core 1's
| running payload into a boot-ROM loader (dsp_park.asm), and the same seven
| words go to it. It MUST answer.
|
| FIRST, and on the other core, for a measured reason: a probe leaves its
| words unread in the host port of a core that has no ROM, and a loader
| parked afterwards reads THOSE as its count and address (under the port,
| 29 Sep 2026: the parked core loaded [7, $31000, ...] over itself and
| jumped into it, answering nothing). So the positive control gets a clean
| port, and core 1 -- which is then parked for good -- is not probed again.
        moveq   #1,%d3
        bsr.w   dr_parkcore             | -> d0 = 1 taken, 0 timed out
        move.l  %d0,%d1
        moveq   #50,%d0
        bsr.w   dr_note
        moveq   #1,%d3
        bsr.w   dr_romprobe             | -> d0 = the code, d1 = the word
        move.l  %d1,(C_PC,%a2)
        move.l  %d0,%d4
        moveq   #51,%d0
        move.l  %d4,%d1
        bsr.w   dr_note
        cmpi.l  #1,%d4
        bne.s   1f
        bset    #6,%d7
1:
| dr_parkcore: OS SWITCH's park command to the core in d3, the switcher's
| own sequence (switch.s parkcore). out: d0 = 1 taken, 0 not.
        bra.s   2f
dr_parkcore:
        move.b  %d3,(DSP_SELECT).l
        nop
        move.l  #PARK_HC,%d0
        move.w  %d0,(HI08_CVR).l
        move.l  #HPOLL,%d2
3:      move.w  (HI08_CVR).l,%d0
        tst.b   %d0
        bpl.s   4f
        subq.l  #1,%d2
        bne.s   3b
        moveq   #0,%d0
        rts
4:      moveq   #1,%d0
        rts
2:
        .endif

| the control pass: core 0, no pulse. Nothing may answer.
        moveq   #0,%d3
        bsr.w   dr_romprobe             | -> d0 = the code, d1 = the word
        move.l  %d1,(C_CTRL,%a2)
        move.l  %d0,%d4
        moveq   #41,%d0
        move.l  %d4,%d1
        bsr.w   dr_note
        cmpi.l  #1,%d4
        bne.s   dr_pass1
| An answer with no pulse: the instrument cannot tell a reset from its own
| noise. Say so and leave the DSP alone.
        bset    #5,%d7
        moveq   #48,%d0
        move.l  %d4,%d1
        bsr.w   dr_note
        bra.w   dr_done

| pass 1: the bare write/clear pair.
dr_pass1:
        moveq   #42,%d0
        moveq   #1,%d1
        bsr.w   dr_note
        moveq   #1,%d6
        moveq   #0,%d3                  | no hold
        move.l  %d3,(C_HOLD,%a2)
        bsr.w   dr_pulse
        bsr.w   dr_test
        bsr.w   dr_answered             | the CORE bits alone, not the whole bitmap
        bne.w   dr_restore

| pass 2: RSTOUT held ~1 ms.
        moveq   #42,%d0
        moveq   #2,%d1
        bsr.w   dr_note
        moveq   #2,%d6
        move.l  #HOLD,%d3
        move.l  %d3,(C_HOLD,%a2)
        bsr.w   dr_pulse
        bsr.w   dr_test
        bsr.w   dr_answered
        beq.w   dr_done

| ---- the restore --------------------------------------------------------
| A core answered, so it is parked in the micro program and its payload is
| gone: this pass's own pulse puts it back in its boot ROM, and the stock
| sequence uploads both payloads again, exactly as it did at 0x4000050c.
|
| The no-answer case is NOT repaired, and that is deliberate. Those cores
| are still running their payloads with the probe's first words unread in
| the receive register, which is enough to put a payload out of step for
| good -- but the only way to get a running core back into a boot ROM is OS
| SWITCH's park command, and a park that does not take (or that reads the
| leftover words as its own count) leaves the stock uploader waiting on a
| core that will never answer -- a boot that never finishes, which is worse
| than the wedged payload it was meant to repair. Measured under the port,
| 29 Sep 2026: the rescue hung the boot on exactly that path. A probe image
| is not a playing image; the way out is the power-cycle.
dr_restore:
        move.l  %d6,(C_PASS,%a2)
        lsl.l   #2,%d6
        or.l    %d6,%d7
        moveq   #45,%d0
        moveq   #1,%d1
        bsr.w   dr_note
        move.l  (C_HOLD,%a2),%d3
        bsr.w   dr_pulse
        | the stock routine keeps none of our registers: the bitmap and the
        | cell pointer go on the stack across it
        move.l  %d7,-(%sp)
        jsr     (DSP_UPLOAD).l
        move.l  (%sp)+,%d7
        lea     (dr_cell).l,%a2
        bset    #4,%d7
        moveq   #46,%d0
        moveq   #1,%d1
        bsr.w   dr_note

dr_done:
        move.l  %d7,(C_BITS,%a2)
        moveq   #47,%d0
        move.l  %d7,%d1
        andi.l  #0x7f,%d1
        bsr.w   dr_note
        rts

| dr_answered: Z clear when a CORE answered (bits 0, 1). The bitmap also
| carries the positive control (bit 6), the control pass (bit 5) and the
| pass number, so a plain `tst` on it reads "a core answered" from the
| positive control alone -- which it did under the port on 29 Sep 2026, and
| sent the boot into an upload to cores still running their payloads.
| clobbers d0.
dr_answered:
        move.l  %d7,%d0
        andi.l  #3,%d0
        rts

| ---- one test pass: both cores ----------------------------------------------
| out: d7 |= bit 0 / bit 1 for a core that answered with its own magic
dr_test:
        moveq   #0,%d3
        bsr.w   dr_romprobe
        move.l  %d1,(C_C0,%a2)
        move.l  %d0,%d4
        moveq   #43,%d0
        move.l  %d4,%d1
        bsr.w   dr_note
        cmpi.l  #1,%d4
        bne.s   1f
        bset    #0,%d7
1:
        .if     PARK == 0
        moveq   #1,%d3
        bsr.w   dr_romprobe
        move.l  %d1,(C_C1,%a2)
        move.l  %d0,%d5
        moveq   #44,%d0
        move.l  %d5,%d1
        bsr.w   dr_note
        cmpi.l  #1,%d5
        bne.s   2f
        bset    #1,%d7
2:
        .endif
        rts

| ---- the candidate ----------------------------------------------------------
| RSTOUT asserted through the reset controller, held for d3 loop iterations
| (0 = the bare pair). RCR is a byte register and the write goes through a
| data register, the form the switcher's own soft reset uses. d3 preserved.
dr_pulse:
        move.l  %d3,%d1
        moveq   #FRCRSTOUT,%d0
        move.b  %d0,(RCR).l
        tst.l   %d1
        beq.s   2f
1:      subq.l  #1,%d1
        bne.s   1b
2:      clr.b   %d0
        move.b  %d0,(RCR).l
        rts

| ---- the instrument --------------------------------------------------------
| dr_romprobe: ask the core in d3 whether a boot ROM is listening.
| out: d0 = the code (0 none, 1 the magic, 2 another word, 3 send timed out)
|      d1 = the word that came back, or 0
| clobbers d0-d2, a0, a1. d3 and the cell are untouched.
dr_romprobe:
        move.l  %d3,-(%sp)
        move.b  %d3,(DSP_SELECT).l
        | the interface as the stock upload opens it: CVR cleared
        | (0x40001d4c's first act), then ICR = INIT|RREQ (0x40001e50's)
        clr.w   %d0
        move.w  %d0,(HI08_CVR).l
        move.w  #0x81,%d0
        move.w  %d0,(HI08_ICR).l
        | anything the running payload left for the host, taken and dropped:
        | a stale word must not be read as an answer (OS SWITCH's park
        | drains the same register for the same reason)
        moveq   #4,%d2
1:      move.w  (HI08_ISR).l,%d0
        btst    #0,%d0
        beq.s   2f
        bsr.w   dr_take
        subq.l  #1,%d2
        bne.s   1b
2:
        | the ROM's protocol: the word count, the load address, the words
        moveq   #MICRO_N,%d1
        bsr.w   dr_send
        tst.l   %d0
        bmi.w   dr_sendto
        move.l  #MICRO_AT,%d1
        bsr.w   dr_send
        tst.l   %d0
        bmi.w   dr_sendto
        | The words, by cursor: a1 to a0. NOT an index in a data register --
        | dr_send's poll counter is d2 and an index there came back as
        | whatever was left of the poll, so the loop walked off the end of
        | the table and sent zeros until a send timed out (29 Sep 2026,
        | found under the port: nine words on the wire, then code 3).
        | The magic is recognised by its VALUE: it is the one word of the
        | table that is not an instruction, and it appears exactly once
        | (verify_dspreset checks that).
        lea     (dr_micro).l,%a1
        lea     (dr_micro_end).l,%a0
3:      move.l  (%a1)+,%d1
        cmpi.l  #MAGIC,%d1
        bne.s   4f
        or.l    (%sp),%d1               | the core number, into the magic
4:      bsr.w   dr_send
        tst.l   %d0
        bmi.w   dr_sendto
        cmp.l   %a0,%a1
        bne.s   3b
        | the answer
        bsr.w   dr_recv
        tst.l   %d0
        bmi.s   5f
        move.l  %d0,%d1                 | a word came back
        move.l  (%sp),%d0
        ori.l   #MAGIC,%d0              | this core's magic (its low bit is the core)
        cmp.l   %d1,%d0
        beq.s   6f
        | not the magic: report the word itself, three notes
        bsr.w   dr_word
        moveq   #2,%d0
        bra.s   7f
6:      moveq   #1,%d0
        bra.s   7f
5:      moveq   #0,%d0                  | nothing came
        moveq   #0,%d1
7:      addq.l  #4,%sp
        rts
dr_sendto:
        moveq   #3,%d0
        moveq   #0,%d1
        addq.l  #4,%sp
        rts

| dr_send: the 24-bit word in d1 to the selected core, the stock sender's
| own sequence (0x40001d4c: poll the ISR for TXDE|TRDY, then TXH, TXM, TXL;
| the low byte of each 16-bit bus cycle carries the datum).
| out: d0 = 0, or -1 if the port never took it. clobbers d0, d2. d1 kept.
dr_send:
        move.l  #HPOLL,%d2
1:      move.w  (HI08_ISR).l,%d0
        andi.l  #6,%d0
        bne.s   2f
        subq.l  #1,%d2
        bne.s   1b
        moveq   #-1,%d0
        rts
2:      move.l  %d1,%d0
        swap    %d0
        ext.l   %d0
        move.w  %d0,(HI08_H).l
        move.l  %d1,%d0
        asr.l   #8,%d0
        move.w  %d0,(HI08_M).l
        move.w  %d1,(HI08_L).l
        clr.l   %d0
        rts

| dr_recv: a word from the selected core, at most POLL polls of RXDF.
| out: d0 = the word, or -1. clobbers d0, d1, d2.
dr_recv:
        move.l  #HPOLL,%d2
1:      move.w  (HI08_ISR).l,%d0
        btst    #0,%d0
        bne.s   dr_take
        subq.l  #1,%d2
        bne.s   1b
        moveq   #-1,%d0
        rts

| dr_take: read the word that is waiting, the stock reader's own sequence
| (0x40001b8e: the low byte of each read carries the datum).
| out: d0 = the word. clobbers d0, d1.
dr_take:
        move.w  (HI08_H).l,%d0
        andi.l  #0xff,%d0
        swap    %d0
        move.w  (HI08_M).l,%d1
        andi.l  #0xff,%d1
        lsl.l   #8,%d1
        or.l    %d1,%d0
        move.w  (HI08_L).l,%d1
        andi.l  #0xff,%d1
        or.l    %d1,%d0
        rts

| dr_word: the 24-bit word in d1 as three notes (bits 6..0, 13..7, 20..14),
| note 49. clobbers d0, d2. d1 kept.
dr_word:
        move.l  %d1,-(%sp)
        move.l  %d1,%d2
        moveq   #3,%d0
1:      move.l  %d0,-(%sp)
        move.l  %d2,%d1
        andi.l  #0x7f,%d1
        moveq   #49,%d0
        bsr.w   dr_note
        move.l  (%sp)+,%d0
        lsr.l   #7,%d2
        subq.l  #1,%d0
        bne.s   1b
        move.l  (%sp)+,%d1
        rts

| ---- MIDI OUT --------------------------------------------------------------
| dr_note: Note On, channel 1, note d0.b, velocity d1.b. Everything
| preserved (BOOT TRACE's tracev, kept separate so the two are independent
| and the probe can run in a remix without it).
        .global dr_note
dr_note:
        lea     (-16,%sp),%sp
        movem.l %d0-%d3,(%sp)
        move.l  %d1,%d3
        move.l  #0x90,%d1
        bsr.s   1f
        move.l  (%sp),%d1
        bsr.s   1f
        move.l  %d3,%d1
        andi.l  #0x7f,%d1
        bsr.s   1f
        movem.l (%sp),%d0-%d3
        lea     (16,%sp),%sp
        rts
1:      move.l  #POLL,%d2
2:      move.b  (UART0_USR).l,%d0
        btst    #2,%d0
        bne.s   3f
        subq.l  #1,%d2
        bne.s   2b
3:      move.b  %d1,(UART0_UTB).l
        rts

| ---- the micro program -----------------------------------------------------
| micro.asm, assembled by dsp_asm at P:0x31000. verify_dspreset.py assembles
| that file on every run and refuses these seven longs if they differ, and
| round-trips them through the disassembler (AGENTS.md: disassemble what you
| assemble).
| the result record (the header says what each long is)
        .align  4
        .global dr_cell
dr_cell:
        .long   0, 0, 0, 0, 0, 0, 0, 0

        .align  4
        .global dr_micro
dr_micro:
        .long   0x0cc301, 0x000000      | brclr #1,x:<<$ffffc3,0   (HTDE)
        .long   0x44f400, 0x5a3c60      | move #>$5a3c60,x0        (| the core)
        .long   0x08c407                | movep x0,x:<<$ffffc7     (HOTX)
        .long   0x0cc300, 0x000000      | brclr #0,x:<<$ffffc3,0   (park)
dr_micro_end:
