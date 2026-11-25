#!/usr/bin/env python3
"""Pinned MIDI Scenes producers obey Loopback without changing Scenes or USB."""
import hashlib
import json
import subprocess
from verify_midi_loopback import ROOT, MSG, REGS
from verify_midi_loopback_producers import prepare, outputs
from unicorn.m68k_const import UC_M68K_REG_D7


def main():
    raw=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    syms={f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    assert syms['scn_pbi']-syms['scn_state']==288
    assert syms['scn_pp']-syms['scn_state']==292
    m=prepare(0,0)
    def caller(first,last,target):
        lo,hi=syms[first],syms[last]
        code=bytes(m.u.mem_read(lo,hi-lo));pattern=b'\x4e\xb9'+target.to_bytes(4,'big')
        sites=[lo+i+6 for i in range(len(code)-5) if code[i:i+6]==pattern]
        assert len(sites)==1,(first,sites)
        return sites[0]
    cc_pc=caller('scn_ccnote','scn_clear',0x40010bc8)
    mix_pc=caller('scn_morph','scn_invalidate',0x4009eec8)
    for track in range(8):
        for route in range(3):
            for kind in ('sequence','mix-cached','mix-tail'):
                # UI and cached routes disagree: the Scene mixer really owns
                # bank 2 / Part 3, whose native flags decide this emission.
                m=prepare(track,(route+1)%3)
                m.put(syms['scn_pbi'],1);m.put(syms['scn_pp'],2)
                m.put(0x40171442+0x9b340+2*0x18b2+track*36+12,route*4+3,1)
                if kind=='sequence':
                    msg=(0xb0,34,70);m.u.mem_write(MSG,bytes(msg))
                    before={reg:0x10203040+i for i,reg in enumerate(REGS)}
                    before[UC_M68K_REG_D7]=track
                    m.call(0x40010bc8,(3,MSG),regs=before,stop=cc_pc,return_pc=cc_pc)
                    assert all(m.u.reg_read(reg)==value for reg,value in before.items())
                else:
                    msg=(0xb0,34,80)
                    for t in range(8):
                        m.put(0x40171360+32*t,4,1)
                        m.put(0x46c76dc0+68*t+30,4,1)
                        m.put(0x46c76dc0+68*t+52,34,1)
                    active=(track+1)%8 if kind=='mix-tail' else track
                    m.put(0x8000000c,(255 ^ (1 << active)) << 8)
                    m.call(0x4009eec8,(track,20,80,0),stop=mix_pc,return_pc=mix_pc)
                outputs(m,[msg],route)
    # Ordinary global senders bypass Loopback, including external INT-track
    # traffic. Invalid Scene contexts default EXT and never read a bogus Part.
    for parent,bank,part in ((0x40012340,1,2),(cc_pc,255,0),(cc_pc,0,4)):
        m=prepare(0,1);m.put(syms['scn_pbi'],bank);m.put(syms['scn_pp'],part)
        m.u.mem_write(MSG,bytes((0xb0,34,70)))
        m.call(0x40010bc8,(3,MSG),regs={UC_M68K_REG_D7:0},stop=parent,return_pc=parent)
        outputs(m,[(0xb0,34,70)],0)
    out=ROOT/'out/midi-loopback-scenes';out.mkdir(exist_ok=True)
    (out/'result.json').write_text(json.dumps(dict(
        image_sha256=hashlib.sha256((ROOT/'out/mainos_bus.bin').read_bytes()).hexdigest(),
        tracks=8, routes=['EXT','INT','BOTH'], producers=['sequence','mix-cached','mix-tail'],
        ordinary_sender_bypass=True, invalid_context_defaults_ext=True,
        scope='Installed machine-code producer checks; RTOS project routing is tested separately.'),indent=2)+'\n')
    print('[ok] Scenes sequence and mixer: eight tracks, EXT/INT/BOTH, actual mix Part, DIN/USB, registers, ordinary sender bypass and invalid-context guards')


if __name__=='__main__':main()
