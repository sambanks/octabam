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
; Every instruction form here has a stock site that has run on the chip:
; the HRDF wait, movep from HORX into a / r0 / p:(r0)+ and
; jmp (rN) are the stock bootstraps' own (P:$31000..); movep #>imm into the
; DMA and ESAI registers is the payloads' (P:$99, P:$30026, P:$30067);
; move #>$300,sr is the payload's start (P:$30000); sub #<n,a / cmp as
; there. The registers are the DSP56300 map the payloads address:
; DCR0-5 x:$ffffec/e8/e4/e0/dc/d8, ESAI TCR/RCR x:$ffffb5/b7, ESAI_1
; TCR/RCR y:$ffff95/97, HSR x:$ffffc3 (bit 0 HRDF), HORX x:$ffffc6.

; The whole SR first, not only the interrupt mask: the handler inherits
; the payload's mode bits (it sets SR bit $14 at P:$77f, and runs its
; arithmetic in the modes it chose), and under them `movep x:HORX,a`
; landed the word count shifted left by 8 -- the loader read a count of 2
; as $200 under the port (29 Sep 2026) and took the payload stream for
; program words. The stock bootstraps run from a chip reset with those bits
; clear; $300 is the payload's own start (P:$30000): IPL 3, every mode off.
osw_dsp:
        move    #>$300,sr               ; nothing interrupts the loader; no mode bits
        movep   #>$0,x:<<$ffffec        ; DMA0 off: the host-port receive DMA
        movep   #>$0,x:<<$ffffe8        ; DMA1 off: the host-port transmit DMA
        movep   #>$0,x:<<$ffffe4        ; DMA2 off: the ESAI feed
        movep   #>$0,x:<<$ffffe0        ; DMA3 off
        movep   #>$0,x:<<$ffffdc        ; DMA4 off
        movep   #>$0,x:<<$ffffd8        ; DMA5 off
        movep   #>$0,x:<<$ffffb5        ; ESAI transmitter off
        movep   #>$0,x:<<$ffffb7        ; ESAI receiver off
        movep   #>$0,y:<<$ffff95        ; ESAI_1 transmitter off
        movep   #>$0,y:<<$ffff97        ; ESAI_1 receiver off
; Leave the interrupt before loading: the host command made this a LONG
; interrupt (the vector's jsr), and the vendored emulator runs no
; peripheral until that interrupt's rti -- its HI08 then never raised HTDE
; for the stock bootstrap's first echo, and the upload stalled there under
; the port (29 Sep 2026). The chip has no such state (the DSP56300 nests by
; the IPL in SR alone), but a clean exit costs three words: pop the return
; address the interrupt stacked, push the loader's in its place -- the
; slot's SSL still holds the interrupted SR -- and rti into the loader.
; move ssh,x0 / move x0,ssh are the stock frame handler's (P:$5c8, $5c1).
        move    ssh,x0                  ; drop the interrupted PC
        move    #>osw_ldr,x0
        move    x0,ssh                  ; the loader, as the return address
        nop
        rti
osw_ldr:
        move    #>$300,sr               ; IPL 3, no mode bits, outside any interrupt
        movep   #>$8,x:<<$ffffc2        ; HCR: HF2 -- the host sees "the loader runs" in its ISR (bit 3)
; The HRDF waits are written `brclr #0,x:<<$ffffc3,0`: a displacement of 0,
; a branch to itself -- the stock bootstraps' exact word pair (0cc300
; 000000). dsp_asm encodes a LABEL there as an absolute address in the
; displacement word (0cc300 001015 for a loop at P:$1015, which would
; branch $1015 words away), and it cannot encode a backward Bcc at all; the
; copy is a DO loop for the same reason (do x0 as the modules' pad loops).
        brclr   #0,x:<<$ffffc3,0        ; wait: the word count
        movep   x:<<$ffffc6,a
        brclr   #0,x:<<$ffffc3,0        ; wait: the load address
        movep   x:<<$ffffc6,r0
        move    r0,r1
        tst     a
        beq     osw_jmp
        move    a1,x0
        do      x0,osw_end
        brclr   #0,x:<<$ffffc3,0        ; wait: a word, into P
        movep   x:<<$ffffc6,p:(r0)+
osw_end:
osw_jmp:
        movep   #>$18,x:<<$ffffc2       ; HCR: HF2|HF3 -- "the loader jumps" (the payload's start rewrites HCR)
        move    #>$300,sr               ; CCR clear, as the ROM leaves it
        jmp     (r1)
