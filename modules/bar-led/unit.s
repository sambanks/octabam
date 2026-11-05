| BAR LED -- the tempo LED flashes green on the pattern's 1 while the
| sequencer plays; every other flash stays stock red.
|
| Stock flashes the tempo LED from its clock-message loop: message 7 (a
| clock tick, 24 a beat) calls set_led(38, 3) (0x40013784: LED id 38, the
| tempo LED's red half, lit for three 120 Hz ticks) when the tick counter
| 0x460d1e10 is 0, then counts it 0..23. Message 2 clears the counter, so
| the first tick after a start flashes. LED ids pair red (even) with green
| (odd, the next bit up), as the trig and track LEDs do, so 39 is green.
|
| The detour is that call (0x40056f24, `jsr set_led`): bl_flash gets the
| caller's two arguments on the stack (4(sp) the id, 8(sp) the count), turns
| id 38 into 39 on the pattern's 1 and tail-jumps to set_led, which returns
| to stock. d0-d1 are free there (set_led is a C function; stock reloads d0
| after it).
|
| The pattern's 1 is read from the sequencer, not counted: the master step
| 0x800065b4 (u16, the step now playing; 0x400a422c writes it each step,
| before that step's beat flash) runs 0.. and wraps at the pattern's length.
| A flash that sees a lower step than the flash before is the first since
| the wrap: green. So it follows pattern length, scale, pattern changes,
| tempo and external MIDI clock. Stopped, every flash is stock's and the
| last step is rearmed (-1), so the first flash after PLAY is green.
        .text
        .global bl_flash

        .equ    SET_LED, 0x40013784
        .equ    TRANSPORT, 0x800065b8   | 1 while the sequencer plays (Euclid's EU_TRANSPORT)
        .equ    MASTER_STEP, 0x800065b4 | u16: the master step now playing
        .equ    LED_GREEN, 39           | the tempo LED's green half (stock flashes 38, red)

bl_flash:
        move.l  (TRANSPORT).l,%d0
        subq.l  #1,%d0
        beq.s   .Lplaying
        moveq   #-1,%d0                 | stopped: the next PLAY's first flash is the 1
        move.l  %d0,(bl_last).l
        jmp     (SET_LED).l
.Lplaying:
        mvz.w   (MASTER_STEP).l,%d0
        move.l  (bl_last).l,%d1
        move.l  %d0,(bl_last).l
        cmp.l   %d1,%d0
        bcc.s   .Lred                   | step >= the last flash's (unsigned): no wrap
        moveq   #LED_GREEN,%d0
        move.l  %d0,4(%sp)              | the caller's id argument: 38 -> 39
.Lred:
        jmp     (SET_LED).l

| In .text: a DRAM unit's text is RAM (as Apply Scene keeps its state).
        .balign 4
bl_last:
        .long   -1
