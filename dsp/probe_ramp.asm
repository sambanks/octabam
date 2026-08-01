; Does our state word at X:0xb000 persist between proc calls?
;
; The echo test works perfectly in the emulator (echoes at exactly 1789, 3578,
; 5367...) and produces nothing on hardware. The delay logic is therefore right,
; and the most likely reason it fails is that the write phase does not survive
; between calls -- r1 would land somewhere different every frame and reads would
; never line up with writes. X:0x9000 was proven to persist; X:0xb000 never was.
;
; This makes persistence audible. A counter is advanced once per sample and
; written straight to the output as a sawtooth:
;
;   LOW tone (~86 Hz)   -> the counter carries across calls: state persists
;   HIGH buzz (~5.5 kHz) -> it restarts every block: state does NOT persist,
;                           and the ramp only ever climbs n7 steps
;
; The two are unmistakably different, which is the point.
init:
        move    #>$ffffff,m0
        move    #>$ffffff,m5
        rts

proc:
        move    x:>$b000,a              ; counter carried from last call
        move    r0,r5
        move    #>$ffffff,m5
        move    #>$8000,x0              ; wraps every 512 samples -> ~86 Hz
        do      n7,>rend
        add     x0,a
        move    a,x:(r5)+
        move    a,x:(r5)+
rend:
        move    a,x:>$b000              ; carry it to the next call
        move    #>$ffffff,m0
        move    #>$ffffff,m5
        rts
