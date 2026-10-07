; OS SWITCH, DSP side: park the core in a boot-ROM loader, so the OS the
; unit resets into can upload its program without the chip being reset.
;
; MEASURED on the unit (BOOT TRACE, build 4, 29 Sep 2026): after the soft
; reset the staged OS runs, starts the DSP upload (0x40001e50) and never
; returns from it -- the soft reset restarts the ColdFire but not the DSP,
; whose HI08 bootstrap ROM only listens after a chip reset, and nothing in
; the OS or the bootstrap resets it.
;
; So before the switcher resets, it sends each core host command $12
; (vector P:$24, stock's unused `reserved24`: `jmp *`, turned into
; `jsr >osw_dsp` by schema.DspHook in both payloads). This handler stops
; everything that could touch memory or the host port behind the loader's
; back and then IS the boot ROM, as dsp56kEmu's DspBoot describes it and
; the firmware's upload (FUN_40001d4c) drives it: a word count, a load
; address, that many words into P, then r0 = address + count, r1 =
; address, CCR clear, jump to the address. The stock bootstraps it loads
; (P:$31000 on core 0, P:$32000 on core 1) mask interrupts and reset the
; stack themselves, then load the payload over everything, this included.
;
; Every instruction form here has a stock site, except `bclr #7` on HPCR
; (the payload's `bset #7` and `bclr #5`/`#6` there are): the HRDF wait,
; movep from HORX into a / r0 / x:(r0)+ and jmp (rN) are the stock
; bootstraps' own (P:$31000..); movep from a register into a peripheral,
; is the payloads' (`movep r3,x:<<pp`, `movep a,x:<<qq`), movep #>imm into
; y:qq too (ESAI_1, P:$30067);
; move #>$300,sr is the payload's start (P:$30000); move ssh / rti are the
; frame handler's. The registers are the DSP56300 map the payloads address:
; DCR0-5 x:$ffffec/e8/e4/e0/dc/d8, ESAI TCR/RCR x:$ffffb5/b7, ESAI_1
; TCR/RCR y:$ffff95/97, HSR x:$ffffc3 (bit 0 HRDF), HORX x:$ffffc6.

; COMPACT (29 Sep 2026, build 15): 40 words, because bottleservice-ret's
; payload A had 42 to spare. Build 14's hardware-proven sequence, minus what
; the unit showed was only diagnosis (HF2/HF3 in HCR), minus the paths the
; stock upload never takes (a zero count; a bootstrap outside the shared
; window: 1.40C's load at P:$31000 and P:$32000), minus the two bsets
; bootstrap A makes itself; the ten peripheral stores through one cleared
; register where the stock payloads have that form (`movep r3,x:<<M_HOTX`
; 08d307 for the DMA registers; `movep a,x:<<M_TX0` 04cec0 for ESAI's in
; x:qq), ESAI_1's in y:qq as immediates still.
osw_dsp:
        move    #0,r3
        movep   r3,x:<<$ffffec          ; DMA0 off: the host-port receive DMA
        movep   r3,x:<<$ffffe8          ; DMA1 off: the host-port transmit DMA
        movep   r3,x:<<$ffffe4          ; DMA2 off: the ESAI feed
        movep   r3,x:<<$ffffe0          ; DMA3 off
; DMA4 and DMA5 are NOT stopped: ✅ measured from the user's own image (29
; Sep 2026, tools/build/dsp_disasm_all.py), neither payload writes M_DCR4 or
; M_DCR5 anywhere, so 1.40C never enables them and the two stores were two
; words spent on nothing. verify_dspvectors' peripheral allowlist refuses a
; payload that starts writing either, which is what keeps this true.
        movep   r3,x:<<$ffffb5          ; ESAI transmitter off
        movep   r3,x:<<$ffffb7          ; ESAI receiver off
        movep   #>$0,y:<<$ffff95        ; ESAI_1 transmitter off (the immediate: a
        movep   #>$0,y:<<$ffff97        ; register into y:qq has no stock site; build 14's form)
; The host port back into the mode the boot ROM leaves it in. The payload's
; start (P:$30016..$30018, both payloads) disables it, sets HPCR bit 7 and
; enables it again; the stock upload's reads assume the ROM's mode. MEASURED
; on the unit (build 12, BOOT TRACE notes 17/19): after a switch the first
; record's echo read back $010101 on both cores where a power-on boot reads
; $000001 -- the low byte right, repeated in every lane -- and the record
; sender abandoned both uploads; with this, build 14's switch completed both
; (final echo 3 on each core). That bit 7 is the lane mode is INFERRED
; (bit 5, cleared at P:$3001b, is left as the payload has it).
        bclr    #6,x:<<$ffffc4          ; HPCR: HEN off
        bclr    #7,x:<<$ffffc4
        bset    #6,x:<<$ffffc4          ; HEN on
; Leave the interrupt before loading: the host command made this a LONG
; interrupt (the vector's jsr), and the vendored emulator runs no
; peripheral until that interrupt's rti -- its HI08 then never raised HTDE
; for the stock bootstrap's first echo, and the upload stalled there under
; the port (29 Sep 2026). The chip has no such state (the DSP56300 nests by
; the IPL in SR alone), but a clean exit costs a few words: pop the return
; address the interrupt stacked, push the loader's in its place -- the
; slot's SSL still holds the interrupted SR -- and rti into the loader.
; move ssh,x0 / move x0,ssh are the stock frame handler's (P:$5c8, $5c1).
        move    ssh,x0                  ; drop the interrupted PC
        move    #>osw_ldr,x0
        move    x0,ssh                  ; the loader, as the return address
        nop
        rti
; The whole SR, not only the interrupt mask: rti restored the payload's mode
; bits (it sets SR bit $14 at P:$77f), and under them `movep x:HORX,a`
; landed the word count shifted left by 8 under the port (29 Sep 2026).
; $300 is the payload's own start (P:$30000): IPL 3, every mode off.
osw_ldr:
        move    #>$300,sr
; The ROM's protocol, as the firmware's upload (FUN_40001d4c) drives it: a
; word count, a load address, that many words, then the jump. The HRDF
; waits are `brclr #0,x:<<$ffffc3,0`: a displacement of 0, a branch to
; itself -- the stock bootstraps' exact word pair (0cc300 000000); dsp_asm
; encodes a LABEL there as an absolute address, and the build refuses every
; other bit-test branch. The copy is a DO loop (dsp_asm encodes no backward
; Bcc). The bootstrap lands in the shared window, written through X: the
; window is one memory in P, X and Y (CHIP.md), and movep HORX,x:(r0)+ is
; the stock bootstrap's own form (P:$31024).
        brclr   #0,x:<<$ffffc3,0        ; wait: the word count
        movep   x:<<$ffffc6,a
        brclr   #0,x:<<$ffffc3,0        ; wait: the load address
        movep   x:<<$ffffc6,r0
        move    r0,r1
        move    a1,x0
; ---- the bridge -------------------------------------------------------------
; The park lives in stock's dead interrupt vectors, and they come in runs
; that are not long enough for it whole: the rest of this loader runs in the
; second run. A ONE-word short jump ($0c00xx) is the only jmp form dsp_asm
; encodes, which is lucky -- the bridge costs a word, not two -- and the
; build rewrites its placeholder target to wherever it put the second piece
; (schema.DspSection.pins, build_bus.PIN_BRIDGE -- do not spell that literal
; here, the census counts it in comments too). The cut is HERE, before the
; `do`: a hardware DO
; loop cannot be entered or left by a jump, so the whole loop stays in one
; piece.
        jmp     $fab
osw_tail:
        do      x0,osw_xend
        brclr   #0,x:<<$ffffc3,0        ; wait: a word
        movep   x:<<$ffffc6,x:(r0)+
osw_xend:
; The payload's start (P:$30019/$3001a) sets bit 14 of y:$fffffd and
; y:$fffffe, which a power-on leaves clear; bootstrap A's own first
; instructions set the rest it needs. Then the ROM's exit: jump to the
; address the bootstrap was loaded at, with r1 = that address (bootstrap A
; then loads the payload over everything, this included).
        bclr    #$e,y:<<$fffffd
        bclr    #$e,y:<<$fffffe
        jmp     (r1)
