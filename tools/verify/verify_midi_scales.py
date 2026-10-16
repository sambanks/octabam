#!/usr/bin/env python3
"""Check actual linked MIDI Scales code, native IDs, rounding and formatter bounds."""
import argparse
import midi_scales_machine as h
from unicorn.m68k_const import *

def machine_gate():
    m=h.Machine();u=m.uc
    # Check the installed hooks, not just calls to the linked helpers.
    for site, name, opcode in ((0x4007a3e2, 'ms_encoder', b'\x4e\xf9'),
                              (0x4009fb58, 'ms_output', b'\x4e\xf9')):
        assert bytes(u.mem_read(site, 6)) == opcode + m.sym[name].to_bytes(4, 'big')
    assert int.from_bytes(u.mem_read(0x400d40c6, 4), 'big') == m.sym['ms_format']
    assert int.from_bytes(u.mem_read(0x400d4096, 4), 'big') == 85
    m.sym['installed_output'] = 0x4009fb58
    m.sym['installed_encoder'] = 0x4007a3e2
    for key in range(12):
        for mode,degrees in enumerate(h.MODES):
            raw=h.raw_scale(key,mode)
            assert m.call('ms_decode',raw)==(key<<2)+(mode<<6)
            valid=[n for n in range(128) if (n-key)%12 in degrees]
            for n in range(128):
                want=min(valid,key=lambda v:(abs(v-n),v))
                assert m.call('ms_snap',n,raw)==want,(raw,n,want)
            m.set_key(0,raw)
            u.mem_write(0x100b14cc,b'\0')
            u.mem_write(m.scratch-1,b'\xa5'+b'?'*10+b'\xa5')
            # Formatter takes normal stack arguments.
            u.mem_write(m.stack+4,m.scratch.to_bytes(4,'big')+raw.to_bytes(4,'big'))
            m.call('ms_format')
            result=bytes(u.mem_read(m.scratch,10))
            assert result[:5].split(b'\0')[0].decode()==['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][key]
            assert result[5:].split(b'\0')[0].decode()==['MAJ','DOR','PHR','LYD','MIX','MIN','LOC'][mode]
            assert bytes(u.mem_read(m.scratch-1,1))==bytes(u.mem_read(m.scratch+10,1))==b'\xa5'
    for raw in [0,85,127,255]:
        assert m.call('ms_decode',raw)==0xffffffff
        assert m.call('ms_snap',61,raw)==61
    # Execute the actual output detour on every track. Legacy KEY values
    # must return unchanged to stock quantization; added modes quantize here.
    frame = m.scratch + 128
    for track in range(8):
        for raw in range(85):
            m.set_key(track, raw)
            decoded = m.call('ms_decode', raw)
            for note in range(128):
                u.mem_write(m.scratch - 1, bytes((0xa5, note, 0xa5)))
                u.mem_write(frame - 64, (1 if raw else 0).to_bytes(4, 'big'))
                dest = 0x4009fb5e if 1 <= raw <= 24 else 0x4009fb80
                regs = {UC_M68K_REG_D7: track, UC_M68K_REG_A2: m.scratch,
                        UC_M68K_REG_A6: frame, UC_M68K_REG_A0: m.scratch + 32}
                m.call('installed_output', 0x12345678, 0xabcdef01, stop=dest, regs=regs)
                want = note
                if raw > 24:
                    key, mode = (decoded >> 2) & 15, decoded >> 6
                    valid = [n for n in range(128) if (n-key) % 12 in h.MODES[mode]]
                    want = min(valid, key=lambda n: (abs(n-note), n))
                assert bytes(u.mem_read(m.scratch - 1, 3)) == bytes((0xa5, want, 0xa5)), (track, raw, note)
                assert u.reg_read(UC_M68K_REG_D0) == 0x12345678
                assert u.reg_read(UC_M68K_REG_D1) == 0xabcdef01
                assert all(u.reg_read(reg) == value for reg, value in regs.items())
                assert u.reg_read(UC_M68K_REG_A7) == m.stack
    u.mem_write(0x100b14cc, b'\0')
    # Native setter receives the raw-ID delta for a musical-order movement.
    ordered=[0]+[h.raw_scale(key,mode) for key in range(12) for mode in range(7)]
    for ordinal,raw in enumerate(ordered):
        m.set_key(0,raw)
        for delta in (-100000,-4,-1,0,1,4,100000):
            u.mem_write(0x46c7d244+5*20,bytes(4))
            m.call('installed_encoder',5,stop=0x4007a3ea,regs={UC_M68K_REG_D5:delta & 0xffffffff})
            actual=u.reg_read(UC_M68K_REG_D5)
            target=ordered[max(0,min(84,ordinal+(1 if delta>=4 else -1 if delta<=-4 else 0)))]
            assert actual==(target-raw)&0xffffffff,(raw,delta,actual,target)
    for slot in range(5):m.call('ms_encoder',slot,stop=0x4007a4cc)
    print('  [ok] scale encoder order, both end clamps, stock-control pass-through')
    print('  [ok] installed output: 8 tracks x 85 KEY choices x 128 notes; legacy stock paths, guards and registers')
    print('  [ok] linked MIDI Scales: 84 combinations x 128 pitches, native IDs preserved, OFF/invalid, formatter guards')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('remix',nargs='?');ap.parse_args();machine_gate()
