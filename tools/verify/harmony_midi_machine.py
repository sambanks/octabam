"""Explicit Harmony fixture layered on the native MIDI machine."""
import pathlib
import re
import subprocess
from midi_machine import Machine as NativeMachine, read_sr, dram_map_size
from unicorn.m68k_const import *

ROOT = pathlib.Path(__file__).resolve().parents[2]
HARMONY_SOURCE = ROOT / 'modules/midi-harmony/upstream/modules/midi-harmony'

def raw_scale(key,mode):
    return 1+key*2+(mode==5) if mode in (0,5) else 25+key*5+(1,2,3,4,6).index(mode)

MODES = [(0,2,4,5,7,9,11),(0,2,3,5,7,9,10),(0,1,3,5,7,8,10),
         (0,2,4,6,7,9,11),(0,2,4,5,7,9,10),(0,2,3,5,7,8,10),(0,1,3,5,6,8,10)]


class InterruptMaskTrace:
    """Observe IPL without materializing Unicorn's lazy comparison flags.

    Reading SR on every instruction can change a ColdFire CMP/BNE result in
    Unicorn. Decode the actual SR writers instead; refuse an unknown writer
    so a new instruction cannot silently invalidate the measurement.
    """
    def __init__(self, uc, ipl=0):
        self.uc=uc;self.ipl=ipl
    def before(self, pc):
        u=self.uc;old=self.ipl
        op=int.from_bytes(u.mem_read(pc,2),'big')
        if op==0x46fc:
            self.ipl=(int.from_bytes(u.mem_read(pc+2,2),'big')>>8)&7
        elif op&0xfff8==0x46c0:
            self.ipl=(u.reg_read(UC_M68K_REG_D0+(op&7))>>8)&7
        elif op&0xffc0==0x46c0 or op in (0x007c,0x027c,0x0a7c,0x4e73):
            raise AssertionError(('unhandled SR writer',hex(pc),hex(op)))
        return old

def symbols():
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [TtBbDdAa] ((?:hd|mh|bf|ms|sc|mhc|store_part|ha)_\w+)$',raw,re.M)}

class Machine(NativeMachine):
    def __init__(self, symbol_loader=None, artifact_root=None):
        super().__init__(symbol_loader or symbols, artifact_root,
                         profile='native', instruction_budget=10_000_000)
        self.call('mh_defaults', stop=0x40025ace)

    def harmony_state(self):
        return b''.join(bytes(self.uc.mem_read(self.part_address(t, f), 1))
                        for t in range(8) for f in (5, 16))
