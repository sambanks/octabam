"""Stereo block peak limiter shared by SHATTER and RESONATOR.

The effect writes its mixed block first. A second pass applies one linked
attenuation, computed from that same block, so the first transient is covered.
No makeup gain: signals below the ceiling retain unity gain.
"""


def source(prefix, threshold, level, gain, left, right, peak, start, knob):
    def cell(offset):
        return f"x:(r7+${offset:02x})"
    t, e, g, l, r, p, s = map(cell, (threshold, level, gain, left, right, peak, start))
    threshold_code = f"""        move    x:(r6+${knob:x}),a
        and     #>$7f00,a
        beq     {prefix}off
        asl     #$8,a,a
        move    a,x0
        move    #>$200000,y1            ; ceiling 1 - LIM*0.25/128
        mpy     x0,y1,a
        move    #>$7fffff,b
        sub     a,b
        move    b,{t}
        bra     {prefix}ready
{prefix}off:
        clr     a
        move    a,{t}
        move    a,{e}                 ; clear release while bypassed
{prefix}ready:
"""
    prepare = f"""        move    r0,{s}
        clr     a
        move    a,{p}
"""
    collect = f"""        move    {l},a
        abs     a
        move    a,x1
        move    {r},a
        abs     a
        cmp     x1,a
        tlt     x1,a
        move    {p},b
        cmp     b,a
        tlt     b,a
        move    a,{p}
"""
    finish = f"""        move    {t},a
        tst     a
        beq     {prefix}done
; Block envelope: immediate attack, approximately 63 ms release at 15 frames.
        move    {e},x0
        move    #>$7f4f10,y1
        mpy     x0,y1,a
        move    {p},b
        cmp     b,a
        tlt     b,a
        move    a,{e}
        move    {t},b
        cmp     b,a
        ble     {prefix}done
; g = ceiling / max(current block peak, released envelope), always < 1.
        move    a,x0
        move    b,y1
        move    y1,a
        andi    #$fe,ccr
        do      #$18,>{prefix}quot
        div     x0,a
{prefix}quot:
        move    a0,{g}
        move    {s},r0
        move    {g},y1
        do      n7,>{prefix}scale
        move    x:(r0),x0
        mpy     x0,y1,a
        move    a,x:(r0)+
        move    x:(r0),x0
        mpy     x0,y1,a
        move    a,x:(r0)+
{prefix}scale:
        nop
{prefix}done:
"""
    return {"; LIMIT_THRESHOLD": threshold_code,
            "; LIMIT_PREPARE": prepare, "; LIMIT_COLLECT": collect,
            "; LIMIT_FINISH": finish}
