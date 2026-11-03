#!/usr/bin/env python3
"""Execute linked Harmony firmware; optionally exercise full firmware on a virtual card."""
import argparse
import itertools
import json
import pathlib
import re
import subprocess
import sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.m68k_const import *

from harmony_midi_machine import MODES, raw_scale, Machine as LinkedMidiMachine

def symbols():
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [TtBbAa] ((?:ha|hd|ch|mh|bf|ms)_\w+)$',raw,re.M)}

class Machine(LinkedMidiMachine):
    def __init__(self):
        super().__init__(symbols)
        self.instruction_budget = 30_000_000
    def setting(self,t,kind=0,key=0,scale=0):
        # Historical test cases 2/3 denote TRI/7TH; both now use HARM CHORD.
        # These exhaustive pitch/voicing fixtures configure the generator,
        # not project-bank transitions. The degree integration gate exercises
        # the interactive setter with real banks and retention separately.
        self.call('mh_set_native' if 'hd_set' in self.sym else 'mh_set',t,min(kind,2))
        for name in ('ch_current','ch_live','ch_sequence_quality'):
            self.uc.mem_write(self.sym[name]+t, bytes((1 if kind==3 else 0,)))
        self.call('ch_base_set',t,int(kind==3))
        self.set_key(t,raw_scale(key,scale))
    def chord(self,t,n,offset=0,direct=False):
        self.uc.mem_write(self.scratch,bytes((n,11,12,13)))
        self.call('mh_direct' if direct else 'mh_generate',t,offset & 0xffffffff,a0=self.scratch)
        return list(self.uc.mem_read(self.scratch,4))
    def sequence_root(self,pitch):
        """Give the degree candidate an explicit C-major default root.

        Its sequence hook reads degree state; the existing generator API
        still accepts real pitches and retains its exhaustive checks.
        """
        if 'hd_encode' not in self.sym:return
        code=self.call('hd_encode',pitch,0)
        self.uc.mem_write(self.stack+4,b''.join(n.to_bytes(4,'big') for n in (0,0,0,code)))
        self.call('hd_edit_base_c')

def machine_gate():
    m=Machine();u=m.uc
    assert m.harmony_state()==bytes(16)
    # Per-track TYPE writes leave the other tracks and adjacent Quantizer alone.
    values=[t%3 for t in range(8)]
    for t,v in enumerate(values):m.call('mh_set',t,v)
    assert [m.call('mh_get',t) for t in range(8)]==values
    for t in range(8):
        for kind in range(3):
            m.call('mh_set',t,kind)
            assert m.call('mh_get',t)==kind
            assert all(m.call('mh_get',j)==values[j] for j in range(8) if j!=t)
        m.call('mh_set',t,values[t])
    m.call('mh_defaults',stop=0x40025ace)
    for mode,degrees in enumerate(MODES):
        if "ms_decode" not in m.sym and mode not in (0,5):continue
        for key in range(12):
            valid=[n for n in range(128) if (n-key)%12 in degrees]
            for kind in (1,2,3):
                m.setting(0,kind,key,mode)
                for note in range(128):
                    root=min(valid,key=lambda n:(abs(n-note),n))
                    assert m.call('mh_quant',note,0)==root,(mode,key,note)
                    scale_notes=[n for n in range(root,160) if (n-key)%12 in degrees]
                    expected=[root]*4
                    if kind>1:
                        for slot in range(1,kind+1):
                            candidate=scale_notes[slot*2]
                            if candidate<=127:expected[slot]=candidate
                    actual=m.chord(0,note)
                    assert actual==expected,(mode,key,kind,note,actual,expected)
                    # Only scratch and bounded call stack may be written.
                    assert all(m.scratch<=a and a+n<=m.scratch+4 or m.stack-192<=a and a+n<=m.stack+4 for a,n in m.writes)
    print('  [ok] linked code: all keys and available modes x 128 pitches x NOTE/TRIAD/7TH; bounds and write guards')
    m.setting(0,0,4,5)
    assert m.chord(0,61)==[61,11,12,13]
    assert m.call('mh_quant',61,0)==61
    # Corrupt native HARM is bypassed; boot does not rewrite stored Parts.
    u.mem_write(m.part_address(0,5),b'\xff')
    assert m.call('mh_get',0)==0
    before=m.harmony_state()
    m.call('mh_boot',stop=0x4001022a)
    assert m.harmony_state()==before
    if 'bf_source_get' in m.sym:
        m.follow_write('source',bytes((0,1,2,0,0,0,0,0)),0)
        u.mem_write(m.sym['bf_roots'],bytes((38,255,255,255,255,255,255,255)))
        m.setting(0,0,0,0);m.setting(2,2,1,5)
        assert m.call('mh_source',2)==0
        assert m.chord(2,72)==[38,41,45,38] # D minor in inherited C major
        u.mem_write(m.sym['bf_roots'],bytes([255]*8))
        assert m.chord(2,61)==[60,64,67,60] # unknown source: own note, inherited scale
        u.mem_write(m.sym['bf_roots'],bytes((37,255,255,255,255,255,255,255)))
        assert m.chord(2,72)==[36,40,43,36] # followed chromatic root snaps before stacking thirds
        m.setting(0,1,0,1 if 'ms_decode' in m.sym else 0)
        u.mem_write(m.sym['bf_roots'],bytes((41,255,255,255,255,255,255,255)))
        assert m.chord(2,72)==[41,45,48,41] # F major in C dorian
        m.follow_write('source',bytes((2,1,0,0,0,0,0,0)),0)
        assert m.call('mh_source',0)==0
        print('  [ok] optional Follow inheritance, chains, cycle fallback and independent TYPE')
    m.setting(0,2)
    m.set_key(0,0)
    assert m.chord(0,61)==[61,65,68,61], 'KEY OFF builds major on the unsnapped root'
    for kind in (1,2,3):
        m.setting(0,kind);m.set_key(0,0)
        for pitch in range(128):
            assert m.call('mh_quant',pitch,0)==pitch
            for offset in (-12,0,12):
                root=(pitch+offset)&255
                want=[root]*4 if root<128 else [0]*4
                if kind>1 and root<128:
                    for slot,interval in enumerate((4,7,11)[:kind],1):
                        if root+interval<128:want[slot]=root+interval
                assert m.chord(0,pitch,offset)==want,(kind,pitch,offset)
    print('  [ok] KEY OFF: unsnapped roots, major triads/sevenths, NOTE identity, TRAN and MIDI bounds')
    print('  [ok] Part TYPE storage, TYPE OFF identity, KEY OFF fallback and corrupt-value bypass')


def final_note_gate():
    m=Machine();u=m.uc
    for mode,degrees in enumerate(MODES):
        if 'ms_decode' not in m.sym and mode not in (0,5):continue
        for tonic in range(12):
            for kind in (1,2,3):
                m.setting(0,kind,tonic,mode)
                valid=[n for n in range(128) if (n-tonic)%12 in degrees]
                for pitch in range(128):
                    want=min(valid,key=lambda n:(abs(n-pitch),n))
                    # No degree bank is loaded in this arithmetic fixture.
                    assert m.call('mh_prepare',pitch,0)==(0xffffffff if 'hd_prepare' in m.sym else pitch)
                    assert m.call('mh_final',pitch,0)==want
    for kind in (1,2,3):
        m.setting(0,kind)
        for note in range(128):
            for offset in (-64,-1,1,2,7,63):
                pitch=(note+offset)&255
                actual=m.chord(0,note,offset)
                if pitch>127:
                    assert actual==[0]*4
                    assert u.reg_read(UC_M68K_REG_D0)==0xffffffff
                    continue
                valid=[n for n in range(128) if n%12 in MODES[0]]
                root=min(valid,key=lambda n:(abs(n-pitch),n))
                degrees=[n for n in range(root,160) if n%12 in MODES[0]]
                want=[root]*4
                if kind>1:
                    for slot in range(1,kind+1):
                        if degrees[slot*2]<=127:want[slot]=degrees[slot*2]
                assert actual==want,(kind,note,offset,actual,want)
        # Actual sequence hook receives current TRAN/P-lock and arranger offset.
        lane=m.scratch+0x1000
        m.sequence_root(62) # degree 2:4; +1 snaps back to D in C major
        u.mem_write(m.scratch,bytes((61,0,0,0)))
        u.mem_write(lane+0x22c,bytes((65,)))
        m.call('mh_sequence',stop=0x4009fa30,regs={UC_M68K_REG_A5:lane,UC_M68K_REG_A6:m.scratch+4,UC_M68K_REG_D7:0})
        assert list(u.mem_read(m.scratch,4))==([62]*4 if kind==1 else [62,65,69,62 if kind==2 else 72])
        # The native output must not add either offset twice.
        u.mem_write(0x46c7a124,bytes((2,)))
        m.sequence_root(60)
        u.mem_write(m.scratch,bytes((60,0,0,0)))
        m.call('mh_sequence',stop=0x4009fa30,regs={UC_M68K_REG_A5:lane,UC_M68K_REG_A6:m.scratch+4,UC_M68K_REG_D7:0})
        assert list(u.mem_read(m.scratch,4))==([62]*4 if kind==1 else [62,65,69,62 if kind==2 else 72])
        u.mem_write(0x46c7a124,b'\0')
        for live in (0,1):
            u.mem_write(0x46c77b1e,bytes((live,)))
            m.call('mh_transpose',stop=0x4009fb40 if live else 0x4009fb58,regs={UC_M68K_REG_A5:lane,UC_M68K_REG_D7:0})
        # Out-of-range sequenced root is muted, then a valid trig recovers.
        u.mem_write(0x46c77b1e,b'\0')
        u.mem_write(lane+0x22c,b'\0')
        m.sequence_root(0)
        u.mem_write(m.scratch,bytes((0,0,0,0)))
        m.call('mh_sequence',stop=0x4009fa30,regs={UC_M68K_REG_A5:lane,UC_M68K_REG_A6:m.scratch+4,UC_M68K_REG_D7:0})
        assert u.mem_read(m.sym['mh_muted'],1)==b'\x01'
        m.call('mh_transpose',stop=0x4009fd2a,regs={UC_M68K_REG_A5:lane,UC_M68K_REG_D7:0})
        u.mem_write(0x46c77b1e,b'\x01')
        m.call('mh_transpose',stop=0x4009fb40,regs={UC_M68K_REG_A5:lane,UC_M68K_REG_D7:0})
        u.mem_write(lane+0x22c,b'\x40');u.mem_write(m.scratch,bytes((60,0,0,0)))
        m.sequence_root(60)
        m.call('mh_sequence',stop=0x4009fa30,regs={UC_M68K_REG_A5:lane,UC_M68K_REG_A6:m.scratch+4,UC_M68K_REG_D7:0})
        assert u.mem_read(m.sym['mh_muted'],1)==b'\0'
        # Final arp F# becomes F in all modes, before note ownership.
        u.mem_write(m.scratch,b'\x42')
        m.call('mh_output',stop=0x4009fb8c,regs={UC_M68K_REG_A2:m.scratch,UC_M68K_REG_D7:0,UC_M68K_REG_D6:128})
        assert u.mem_read(m.scratch,1)==b'\x41'
        assert u.reg_read(UC_M68K_REG_D0)==193
        for invalid in (128,255,0xffffffff):assert m.call('mh_final',invalid,0)==invalid
        if 'bf_source_get' in m.sym:
            m.follow_write('source',bytes((0,1,0,0,0,0,0,0)),0)
            m.setting(1,kind,1,5)
            assert m.call('mh_final',42,1)==41
            u.mem_write(lane+0x220,bytes((71,)))
            m.sequence_root(71)
            u.mem_write(lane+0x22c,bytes((71,)))
            m.call('bf_latch',regs={UC_M68K_REG_A5:lane,UC_M68K_REG_D7:0})
            assert u.mem_read(m.sym['bf_roots'],1)==bytes((41,))
    for kind in (0,1,2,3):
        m.setting(0,kind)
        if kind:m.set_key(0,0)
        assert m.call('mh_final',66,0)==66
        u.mem_write(lane+0x22c,b'\x47')
        u.mem_write(0x46c77b1e,b'\0') # sequenced pool has already received TRAN
        m.call('mh_transpose',stop=0x4009fb40 if kind==0 else 0x4009fb58,regs={UC_M68K_REG_A5:lane,UC_M68K_REG_D7:0,UC_M68K_REG_D1:50})
        if kind==0:
            assert u.reg_read(UC_M68K_REG_D0)&255==71
            assert u.reg_read(UC_M68K_REG_A1)==50
    print('  [ok] every HARM mode: TRAN before root snap/chord, final arp snap, bounds, OFF identity and source latch')


def keyboard_gate():
    """Execute wrapper with stock sender intercepted to inspect ownership arguments.
    Full-port UART tests separately exercise the real sender and MIDI parser.
    """
    m=Machine();u=m.uc;m.setting(0,2)
    u.mem_write(0x46c76fec,bytes((64,0,0)))
    from unicorn.m68k_const import UC_M68K_REG_D2,UC_M68K_REG_D3,UC_M68K_REG_D4,UC_M68K_REG_D5,UC_M68K_REG_D6,UC_M68K_REG_D7,UC_M68K_REG_A2
    regs=[UC_M68K_REG_D2,UC_M68K_REG_D3,UC_M68K_REG_D4,UC_M68K_REG_D5,UC_M68K_REG_D6,UC_M68K_REG_D7,UC_M68K_REG_A2]
    recorded=[];forwarded=[]
    def key(note,velocity):
        args=[0,note,velocity,1]
        u.mem_write(m.stack,m.done.to_bytes(4,'big')+b''.join(v.to_bytes(4,'big') for v in args))
        u.reg_write(UC_M68K_REG_A7,m.stack);u.reg_write(UC_M68K_REG_SR,0x2700)
        m.stops={m.done,0x4009e9b0,m.sym['mh_record_key'],m.sym['mh_owned_key']};pc=m.sym['mh_keyboard'];events=[]
        for _ in range(20):
            m.arrival=None;u.emu_start(pc,0,count=50000)
            assert m.arrival in m.stops
            if m.arrival==m.done:return events
            sp=u.reg_read(UC_M68K_REG_A7)
            if m.arrival in (m.sym['mh_record_key'],m.sym['mh_owned_key']):
                args=[int.from_bytes(u.mem_read(sp+4+4*i,4),'big') for i in range(4)]
                if m.arrival==m.sym['mh_record_key']:recorded.append(tuple(args))
                else:events.append((args[1],args[2]));forwarded.append(tuple(args))
                pc=int.from_bytes(u.mem_read(sp,4),'big');u.reg_write(UC_M68K_REG_A7,sp+4)
                continue
            args=[int.from_bytes(u.mem_read(sp+32+4*i,4),'big') for i in range(4)]
            events.append((args[1],args[2]));forwarded.append(tuple(args))
            for i,r in enumerate(regs):u.reg_write(r,int.from_bytes(u.mem_read(sp+4*i,4),'big'))
            pc=int.from_bytes(u.mem_read(sp+28,4),'big');u.reg_write(UC_M68K_REG_A7,sp+32)
        raise AssertionError('unbounded keyboard loop')
    assert key(48,100)==[(48,100),(52,100),(55,100)]
    assert key(52,100)==[(59,100)]
    assert recorded==[(0,48,100,1),(0,52,100,1)] # shared E still records its root
    assert all(event[3]==0 for event in forwarded) # generated tones never record
    m.setting(0,3,5,5) # held notes release their original pitches after edits
    assert key(48,0)==[(48,0)]
    assert key(52,0)==[(52,0),(55,0),(59,0)]
    assert recorded[-2:]==[(0,48,0,1),(0,52,0,1)]
    assert all(event[3]==0 for event in forwarded)
    m.setting(0,2);u.mem_write(0x46c76fec,b'\x00') # -64 must not alter absolute keyboard pitches
    assert key(60,100)==[(60,100),(64,100),(67,100)]
    assert key(60,0)==[(60,0),(64,0),(67,0)]
    u.mem_write(0x46c76fec,b'\x40')
    m.setting(0,0)
    assert key(61,100)==[(61,100)]
    if 'bf_roots' in m.sym:assert u.mem_read(m.sym['bf_roots'],1)==bytes((37,)), 'HARM OFF keyboard must publish C# root'
    assert key(61,100)==[(61,100)] # bypass repeats retain the stock call path
    if 'bf_roots' in m.sym:
        assert forwarded[-1]==(0,61,100,1) # native recorder still owns bypass notes
        assert key(65,100)==[(65,100)]
        assert u.mem_read(m.sym['bf_roots'],1)==bytes((41,))
        assert key(65,0)==[(65,0)]
        assert u.mem_read(m.sym['bf_roots'],1)==bytes((41,)) # release retains latest root
        # An arp tick using a live pool must not relatch unrelated stored C.
        u.mem_write(0x46c77b1e,b'\x01')
        lane=0x46c76dc0;frame=m.scratch+0x200
        u.mem_write(lane+0x220,bytes((60,)))
        u.mem_write(lane+0x22c,bytes((64,)))
        u.mem_write(frame-64,bytes(4))
        m.call('bf_capture',stop=0x4009fb08,regs={UC_M68K_REG_D7:0,UC_M68K_REG_A5:lane,UC_M68K_REG_A6:frame})
        assert u.mem_read(m.sym['bf_roots'],1)==bytes((41,))
        u.mem_write(0x46c77b1e,b'\x00')
    m.setting(0,2)
    assert key(61,0)==[(61,0)] # enabling Harmony must still release stock press
    assert key(48,100)==[(48,100),(52,100),(55,100)]
    m.setting(0,0)
    assert key(48,0)==[(48,0),(52,0),(55,0)]
    m.setting(0,2);m.set_key(0,0)
    assert key(61,100)==[(61,100),(65,100),(68,100)]
    if 'bf_roots' in m.sym:assert u.mem_read(m.sym['bf_roots'],1)==bytes((37,)), 'KEY OFF must still publish live root'
    m.setting(0,2)
    assert key(61,0)==[(61,0),(65,0),(68,0)] # Release captured no-scale voices after selecting a key
    m.setting(0,1)
    u.mem_write(0x46c76fec,b'\x47') # TRAN +7 must not shift chromatic input
    if 'bf_source_get' in m.sym:
        m.follow_write('source',bytes((2,0,0,0,0,0,0,0)),0)
        u.mem_write(m.sym['bf_roots']+1,bytes((41,))) # followed F root
        m.setting(1,0) # source KEY C major
        m.setting(0,1,1,5) # own C# minor must be ignored
    assert key(50,100)==[(50,100)] # D, not followed F, F+2, or D+7
    assert key(50,0)==[(50,0)]
    assert key(49,100)==[(48,100)] # C# -> C in effective C major
    assert recorded[-1]==(0,49,100,1) # NOTE stores physical C#, not snapped C
    u.mem_write(0x46c76fec,b'\x4c')
    assert key(49,0)==[(48,0)] # changing TRAN must not lose ownership
    assert recorded[-1]==(0,49,0,1)
    for kind,want in [(2,[50,53,57]),(3,[50,53,57,60])]:
        m.setting(0,kind,1 if 'bf_source_get' in m.sym else 0,5 if 'bf_source_get' in m.sym else 0)
        assert key(50,100)==[(n,100) for n in want]
        assert key(50,0)==[(n,0) for n in want]
    if 'bf_source_get' in m.sym:m.follow_write('source',bytes(8),0)
    m.setting(0,2);m.call('mh_voic_set',0,1)
    assert key(48,100)==[(48,100),(52,100),(55,100)]
    assert key(53,100)==[(53,100),(57,100)] # common C remains held
    assert recorded[-1]==(0,53,100,1) # physical F, not inversion bass C
    if 'bf_roots' in m.sym:assert u.mem_read(m.sym['bf_roots'],1)==bytes((41,))
    assert key(48,0)==[(52,0),(55,0)]
    m.call('mh_voic_set',0,0) # an edit cannot alter held-note ownership
    assert key(53,0)==[(48,0),(53,0),(57,0)]
    for spread,want in ((1,[48,55,64]),(2,[48,64,67])):
        m.call('mh_sprd_set',0,spread)
        assert key(48,100)==[(n,100) for n in want]
        assert recorded[-1]==(0,48,100,1)
        m.call('mh_sprd_set',0,0)
        assert key(48,0)==[(n,0) for n in want]
    m.setting(0,2);m.call('mh_voic_set',0,2);m.call('mh_sprd_set',0,0);m.call('mh_omit_set',0,1)
    assert key(48,100)==[(52,100),(55,100)]
    m.call('mh_omit_set',0,0)
    assert key(48,0)==[(52,0),(55,0)]
    m.call('mh_omit_set',0,1)
    assert key(127,100)==[]
    assert key(127,0)==[]
    assert recorded[-2:]==[(0,127,100,1),(0,127,0,1)]
    assert u.mem_read(m.sym['mh_held']+127*4,4)==b'\xff'*4
    print('  [ok] linked keyboard ownership: overlapping chord tones, setting changes while held, absolute roots and pre-arp pools independent of TRAN')


def register_reference(previous,old_root,new_root):
    # Preserve deliberate register jumps, with sub-octave moves voice-led.
    delta=new_root-old_root
    shift=(abs(delta)//12)*12*(1 if delta>=0 else -1)
    return [n+shift for n in previous]


def octave_gate():
    m=Machine();u=m.uc
    def voice(root):
        raw=m.chord(0,root)
        u.mem_write(m.scratch,bytes(raw));m.call('mh_voice',0,a0=m.scratch)
        return list(u.mem_read(m.scratch,4))
    for kind in (2,3):
        for mode in (0,5):
            for spread in range(3):
                for omit in (0,1):
                    m.setting(0,kind,0,mode);m.call('mh_voic_set',0,1)
                    m.call('mh_sprd_set',0,spread);m.call('mh_omit_set',0,omit)
                    original=voice(48)
                    assert voice(60)==[n+12 for n in original]
                    assert voice(84)==[n+36 for n in original]
                    assert voice(48)==original
                    inverted=voice(53) # retains nearby C -> F voice leading
                    assert voice(65)==[n+12 for n in inverted]
                    assert voice(41)==[n-12 for n in inverted]
                    assert voice(53)==inverted
    # Crossing C within a small interval must not force an octave shift.
    m.setting(0,2);m.call('mh_voic_set',0,1);m.call('mh_sprd_set',0,0);m.call('mh_omit_set',0,0)
    assert voice(59)==[59,62,65,59]
    assert voice(60)==[60,64,67,60]
    print('  [ok] AUTO register: octave and multi-octave jumps, prior inversions, spread/omit and adjacent B-C')


def voicing_gate():
    """Compare linked search against all compact MIDI voicings, not its loops."""
    m=Machine();u=m.uc
    history=m.sym['mh_voice_history']
    regs=[UC_M68K_REG_D0,UC_M68K_REG_D1,UC_M68K_REG_D2,UC_M68K_REG_D3,
          UC_M68K_REG_D4,UC_M68K_REG_D5,UC_M68K_REG_D6,UC_M68K_REG_D7,
          UC_M68K_REG_A1,UC_M68K_REG_A2,UC_M68K_REG_A3,UC_M68K_REG_A4,UC_M68K_REG_A5,UC_M68K_REG_A6]
    def voice(t,raw):
        u.mem_write(m.scratch,bytes(raw))
        sentinels={r:0x12340000+i for i,r in enumerate(regs) if r!=UC_M68K_REG_D0}
        m.call('mh_voice',t,a0=m.scratch,regs=sentinels)
        assert u.reg_read(UC_M68K_REG_D0)==t
        assert all(u.reg_read(r)==v for r,v in sentinels.items())
        assert u.reg_read(UC_M68K_REG_A0)==m.scratch
        assert all(m.scratch<=a and a+n<=m.scratch+4 or
                   m.stack-192<=a and a+n<=m.stack+4 or
                   history+8*t<=a and a+n<=history+8*t+8 or
                   m.sym['mh_voice_context']+4*t<=a and a+n<=m.sym['mh_voice_context']+4*t+4 or
                   m.sym['mh_voice_epoch']+4*t<=a and a+n<=m.sym['mh_voice_epoch']+4*t+4 for a,n in m.writes)
        return list(u.mem_read(m.scratch,4))
    def cost(notes,prev):return (sum(abs(a-b) for a,b in zip(notes,prev)),sum(a!=b for a,b in zip(notes,prev)))
    for kind in (2,3):
        for mode,degrees in enumerate(MODES):
            if 'ms_decode' not in m.sym and mode not in (0,5):continue
            for tonic in range(12):
                m.setting(0,kind,tonic,mode);m.call('mh_voic_set',0,1)
                previous=None
                # Covers every MIDI input, upward and downward register jumps.
                for note in range(0,128):
                    note=(note*37)%128
                    raw=m.chord(0,note);actual=voice(0,raw);count=kind+1
                    full=raw[:count]==sorted(set(raw[:count]))
                    if not full:
                        assert actual==raw
                        previous=None
                        continue
                    pitches=actual[:count];pcs={n%12 for n in raw[:count]}
                    assert len(set(pitches))==count and pitches==sorted(pitches)
                    assert {n%12 for n in pitches}==pcs
                    assert pitches[-1]-pitches[0]<12
                    assert abs(pitches[0]-raw[0])<=12
                    if previous is None:assert actual==raw
                    else:
                        all_notes=[n for n in range(128) if n%12 in pcs]
                        candidates=[all_notes[i:i+count] for i in range(len(all_notes)-count+1)
                                    if all_notes[i+count-1]-all_notes[i]<12 and abs(all_notes[i]-raw[0])<=12 and raw[0] in all_notes[i:i+count]]
                        target=register_reference(previous,previous_root,raw[0])
                        assert cost(pitches,target)==min(cost(c,target) for c in candidates)
                    previous=pitches;previous_root=raw[0]
    m.setting(0,2);m.call('mh_voic_set',0,1)
    assert voice(0,m.chord(0,48))==[48,52,55,48]
    assert voice(0,m.chord(0,53))==[48,53,57,48]
    for t in range(1,8):
        m.setting(t,2);m.call('mh_voic_set',t,1)
        assert voice(t,m.chord(t,53))==[53,57,60,53] # independent history
    assert voice(0,m.chord(0,53))==[48,53,57,48] # repeated root is stable
    m.call('mh_voic_set',0,0)
    assert voice(0,m.chord(0,53))==[53,57,60,53]
    before=m.harmony_state()+bytes(u.mem_read(history,64))
    for t,v in ((8,1),(0xffffffff,1),(0,5),(0,0xffffffff)):
        m.call('mh_voic_set',t,v)
        assert m.harmony_state()+bytes(u.mem_read(history,64))==before
    m.call('mh_voic_set',0,1)
    assert voice(0,m.chord(0,53))==[53,57,60,53]
    # Type/scale changes reseed, regardless of the prior inversion.
    m.setting(0,3)
    assert voice(0,m.chord(0,48))==[48,52,55,59]
    m.setting(0,3,0,5)
    assert voice(0,m.chord(0,53))==[53,56,60,63]
    if 'bf_source_get' in m.sym:
        m.setting(1,2);m.follow_write('source',bytes((2,0,0,0,0,0,0,0)),0)
        # Same effective scale, different source must still reset context.
        m.setting(0,2);m.call('mh_voic_set',0,1)
        voice(0,m.chord(0,48,direct=True));voice(0,m.chord(0,53,direct=True))
        m.follow_write('source',bytes(8),0)
        assert voice(0,m.chord(0,53))==[53,57,60,53]
    print('  [ok] AUTO: global minimum compact voice movement across MIDI range/scales, register/write guards, per-track history, resets and root identity')


def spread_notes(notes,spread):
    if spread==0:return list(notes)
    raised=[n+(12 if (i==1 if spread==1 else i>0) else 0) for i,n in enumerate(notes)]
    return sorted(raised) if max(raised)<=127 else None


def spread_gate():
    m=Machine();u=m.uc;history=m.sym['mh_voice_history']
    regs=[UC_M68K_REG_D1,UC_M68K_REG_D2,UC_M68K_REG_D3,UC_M68K_REG_D4,
          UC_M68K_REG_D5,UC_M68K_REG_D6,UC_M68K_REG_D7,UC_M68K_REG_A1,
          UC_M68K_REG_A2,UC_M68K_REG_A3,UC_M68K_REG_A4,UC_M68K_REG_A5,UC_M68K_REG_A6]
    def voice(t,raw):
        u.mem_write(m.scratch,bytes(raw))
        sentinels={r:0x12340000+i for i,r in enumerate(regs)}
        m.call('mh_voice',t,a0=m.scratch,regs=sentinels)
        assert u.reg_read(UC_M68K_REG_D0)==t and u.reg_read(UC_M68K_REG_A0)==m.scratch
        assert all(u.reg_read(r)==v for r,v in sentinels.items())
        assert all(m.scratch<=a and a+n<=m.scratch+4 or
                   m.stack-192<=a and a+n<=m.stack+4 or
                   history+8*t<=a and a+n<=history+8*t+8 or
                   m.sym['mh_voice_context']+4*t<=a and a+n<=m.sym['mh_voice_context']+4*t+4 or
                   m.sym['mh_voice_epoch']+4*t<=a and a+n<=m.sym['mh_voice_epoch']+4*t+4 for a,n in m.writes)
        return list(u.mem_read(m.scratch,4))
    def cost(a,b):return (sum(abs(x-y) for x,y in zip(a,b)),sum(x!=y for x,y in zip(a,b)))
    for spread in (1,2):
        for auto in (0,1):
            for kind in (2,3):
                count=kind+1
                for mode in range(7):
                    if 'ms_decode' not in m.sym and mode not in (0,5):continue
                    for tonic in range(12):
                        m.setting(0,kind,tonic,mode)
                        m.call('mh_voic_set',0,auto);m.call('mh_sprd_set',0,spread)
                        previous=None
                        for n in range(128):
                            raw=m.chord(0,(n*37)%128);actual=voice(0,raw)
                            if raw[:count]!=sorted(set(raw[:count])):
                                assert actual==raw
                                previous=None
                                continue
                            seed=spread_notes(raw[:count],spread) or raw[:count]
                            pcs={p%12 for p in raw[:count]}
                            all_notes=[p for p in range(128) if p%12 in pcs]
                            candidates=[]
                            for i in range(len(all_notes)-count+1):
                                close=all_notes[i:i+count]
                                if close[-1]-close[0]<12 and abs(close[0]-raw[0])<=12:
                                    spaced=spread_notes(close,spread)
                                    if spaced is not None and raw[0] in spaced:candidates.append(spaced)
                            if not auto or previous is None or not candidates:assert actual[:count]==seed
                            else:
                                target=register_reference(previous,previous_root,raw[0])
                                assert cost(actual[:count],target)==min(cost(c,target) for c in candidates)
                            assert actual[:count]==sorted(set(actual[:count]))
                            assert {p%12 for p in actual[:count]}==pcs
                            if count==3:assert actual[3]==actual[0]
                            previous=actual[:count];previous_root=raw[0]
    # Per-track packed settings preserve one another and reject invalid writes.
    for t in range(8):
        for kind in range(3):
            for spread in range(3):
                m.call('mh_sprd_set',t,spread);m.call('mh_set',t,kind)
                assert m.call('mh_get',t)==kind and m.call('mh_sprd_get',t)==spread
    before=m.harmony_state()+bytes(u.mem_read(history,64))
    for t,v in ((8,1),(0xffffffff,1),(0,3),(0,0xffffffff)):
        m.call('mh_sprd_set',t,v)
        assert m.harmony_state()+bytes(u.mem_read(history,64))==before
    # OFF/NOTE ignore spread; toggling spacing reseeds AUTO.
    for kind in (0,1):
        m.setting(0,kind);m.call('mh_sprd_set',0,2)
        raw=m.chord(0,48);assert voice(0,raw)==raw
    m.setting(0,2);m.set_key(0,0)
    m.call('mh_voic_set',0,0);m.call('mh_sprd_set',0,1)
    raw=m.chord(0,49);assert voice(0,raw)==[49,56,65,49]
    m.setting(0,2);m.call('mh_voic_set',0,1);m.call('mh_sprd_set',0,0)
    voice(0,m.chord(0,48));voice(0,m.chord(0,53))
    m.call('mh_sprd_set',0,1)
    assert voice(0,m.chord(0,53))==[53,60,69,53]
    print('  [ok] SPRD: ROOT/AUTO x TRI/7TH x scales/keys/MIDI range, sounded-voice cost, bounds, register/write guards, packed Part state')


def inversion_gate():
    m=Machine();u=m.uc;history=m.sym['mh_voice_history']
    for kind in (2,3):
        count=kind+1
        for mode in range(7):
            if 'ms_decode' not in m.sym and mode not in (0,5):continue
            for key in range(12):
                m.setting(0,kind,key,mode)
                for choice in (2,3,4):
                    m.call('mh_voic_set',0,choice)
                    for spread in range(3):
                        m.call('mh_sprd_set',0,spread)
                        for note in range(128):
                            raw=m.chord(0,note)
                            expected=raw[:]
                            if raw[:count]==sorted(set(raw[:count])):
                                # Select the requested bass chord tone, then take the
                                # next occurrence of every other tone above that bass.
                                bass=raw[min(choice-1,count-1)]
                                pcs={n%12 for n in raw[:count]}
                                close=[n for n in range(bass,bass+12) if n%12 in pcs]
                                if close[-1]>127:close=raw[:count]
                                expected=spread_notes(close,spread) or close
                                if count==3:expected=expected+[expected[0]]
                            u.mem_write(m.scratch,bytes(raw))
                            m.call('mh_voice',0,a0=m.scratch,regs={UC_M68K_REG_D2:0x12345678,UC_M68K_REG_A4:0x23456789})
                            assert list(u.mem_read(m.scratch,4))==expected,(kind,mode,key,choice,spread,note)
                            assert u.reg_read(UC_M68K_REG_D2)==0x12345678 and u.reg_read(UC_M68K_REG_A4)==0x23456789
                            assert u.mem_read(history+4,4)==bytes(4)
                            assert all(m.scratch<=a and a+n<=m.scratch+4 or
                                       m.stack-192<=a and a+n<=m.stack+4 or
                                       history<=a and a+n<=history+8 or m.sym['mh_voice_context']<=a and a+n<=m.sym['mh_voice_context']+4 or m.sym['mh_voice_epoch']<=a and a+n<=m.sym['mh_voice_epoch']+4 for a,n in m.writes)
    # Every setting combination coexists, across all eight tracks.
    for t in range(8):
        for choice in range(5):
            m.call('mh_voic_set',t,choice)
            for kind in range(3):
                m.call('mh_set',t,kind)
                for spread in range(3):
                    m.call('mh_sprd_set',t,spread)
                    assert [m.call(g,t) for g in ('mh_get','mh_voic_get','mh_sprd_get')]==[kind,choice,spread]
        m.call('mh_voic_set',t,t%5)
    before=m.harmony_state();m.call('mh_boot',stop=0x4001022a)
    assert m.harmony_state()==before
    for t in range(8):assert m.call('mh_voic_get',t)==t%5
    print('  [ok] manual inversions: all MIDI pitches/keys/scales/spreads, triad 3RD clamp, atomic range fallback, register/write guards and per-track resume')


def omit_gate():
    m=Machine();u=m.uc
    for kind in (0,1,2,3):
        for choice in range(5):
            for spread in range(3):
                m.setting(0,kind);m.call('mh_voic_set',0,choice);m.call('mh_sprd_set',0,spread)
                for note in range(128):
                    raw=m.chord(0,note)
                    m.call('mh_omit_set',0,0);u.mem_write(m.scratch,bytes(raw))
                    m.call('mh_voice',0,a0=m.scratch)
                    full=list(u.mem_read(m.scratch,4))
                    m.call('mh_omit_set',0,1);u.mem_write(m.scratch,bytes(raw))
                    m.call('mh_voice',0,a0=m.scratch)
                    actual=list(u.mem_read(m.scratch,4))
                    if kind<2:assert actual==full
                    else:
                        want={n for n in full if n%12!=raw[0]%12}
                        assert {n for n in actual if n<=127}==want,(kind,choice,spread,note,full,actual)
                        if not want:assert actual==[255]*4
    for t in range(8):
        m.call('mh_omit_set',t,t%2)
        for choice in range(5):
            m.call('mh_voic_set',t,choice)
            m.call('mh_set',t,3);m.call('mh_sprd_set',t,2)
            assert m.call('mh_omit_get',t)==t%2
            assert m.call('mh_voic_get',t)==choice
    before=m.harmony_state();m.call('mh_boot',stop=0x4001022a)
    assert m.harmony_state()==before
    for t,v in ((8,1),(0xffffffff,1),(0,2),(0,0xffffffff)):
        m.call('mh_omit_set',t,v)
        assert m.harmony_state()==before
    print('  [ok] OMIT: harmonic-root removal across voicings/spreads/MIDI range, silent empty pools, OFF/NOTE identity, packed Part settings')


def root_placement_gate():
    m=Machine();u=m.uc;history=m.sym['mh_voice_history']
    for kind in range(4):
        for choice in range(5):
            for spread in range(3):
                m.setting(0,kind);m.call('mh_voic_set',0,choice);m.call('mh_sprd_set',0,spread)
                for note in range(128):
                    raw=m.chord(0,note)
                    m.call('mh_root_set',0,0);u.mem_write(m.scratch,bytes(raw))
                    m.call('mh_voice',0,a0=m.scratch)
                    full=set(u.mem_read(m.scratch,4))-{255}
                    for mode,drop in ((2,12),(3,24)):
                        m.call('mh_root_set',0,mode);u.mem_write(m.scratch,bytes(raw))
                        regs={r:0x12340000+i for i,r in enumerate((UC_M68K_REG_D1,UC_M68K_REG_D2,UC_M68K_REG_D3,UC_M68K_REG_D4,UC_M68K_REG_D5,UC_M68K_REG_D6,UC_M68K_REG_D7,UC_M68K_REG_A1,UC_M68K_REG_A2,UC_M68K_REG_A3,UC_M68K_REG_A4))}
                        m.call('mh_voice',0,a0=m.scratch,regs=regs)
                        got=list(u.mem_read(m.scratch,4));actual=set(got)-{255}
                        want=full if kind<2 else {n for n in full if n%12!=raw[0]%12} | ({raw[0]-drop} if raw[0]>=drop else set())
                        assert actual==want,(kind,choice,spread,note,mode,full,got,want)
                        assert len(actual)<=len(full) and all(0<=n<=127 for n in actual)
                        assert all(u.reg_read(r)==v for r,v in regs.items())
                        assert all(m.scratch<=a and a+n<=m.scratch+4 or m.stack-256<=a and a+n<=m.stack+4 or history<=a and a+n<=history+8 or m.sym['mh_voice_context']<=a and a+n<=m.sym['mh_voice_context']+4 or m.sym['mh_voice_epoch']<=a and a+n<=m.sym['mh_voice_epoch']+4 for a,n in m.writes)
    # AUTO history must still describe the upper chord, independent of ROOT.
    for mode in (2,3):
        m.setting(0,3);m.call('mh_voic_set',0,1);m.call('mh_sprd_set',0,0);m.call('mh_root_set',0,mode)
        for root,want in ((48,[48-(12 if mode==2 else 24),52,55,59]),(53,[53-(12 if mode==2 else 24),48,52,57])):
            raw=m.chord(0,root);u.mem_write(m.scratch,bytes(raw));m.call('mh_voice',0,a0=m.scratch)
            assert list(u.mem_read(m.scratch,4))==want,(mode,root,list(u.mem_read(m.scratch,4)),want)
    for t in range(8):
        for mode in range(4):
            m.call('mh_root_set',t,mode)
            for voic in range(5):
                m.call('mh_voic_set',t,voic);m.call('mh_sprd_set',t,2);m.call('mh_set',t,2)
                assert m.call('mh_root_get',t)==mode and m.call('mh_voic_get',t)==voic
    before=m.harmony_state();m.call('mh_boot',stop=0x4001022a)
    assert m.harmony_state()==before
    for t,v in ((8,2),(0xffffffff,1),(0,4),(0,0xffffffff)):
        m.call('mh_root_set',t,v);assert m.harmony_state()==before
    print('  [ok] ROOT: both octave drops across HARM/voicings/spreads/MIDI range, AUTO history, four-voice limit, underflow, register/write guards and native Part settings')


def recorder_gate():
    m=Machine();u=m.uc;bank=0x400e21e0
    u.mem_write(0x46c82456,bank.to_bytes(4,'big'))
    for part in range(8):
        u.mem_write(0x100b14cf,bytes((part,)))
        for track in range(8):
            channel=1+(part+track)%16
            at=bank+part*0x18b2+track*36+0x8f262
            u.mem_write(at,bytes((channel,)))
            for velocity in (0,100):
                args=(track,50,velocity,1)
                u.mem_write(m.stack+4,b''.join(n.to_bytes(4,'big') for n in args))
                m.call('mh_record_key',stop=0x4009eb7a)
                assert [u.reg_read(r) for r in (UC_M68K_REG_D3,UC_M68K_REG_D4,UC_M68K_REG_D5,UC_M68K_REG_D6,UC_M68K_REG_D7)]==[50,channel-1,track,velocity,1]
                assert u.reg_read(UC_M68K_REG_A7)==m.stack-28
            u.mem_write(at,b'\0')
            m.call('mh_record_key',stop=0x4009eb7a) # stock records even with CHAN OFF
            assert u.reg_read(UC_M68K_REG_D4)==0
    u.mem_write(at,b'\x01')
    u.mem_write(m.stack+16,bytes(4))
    m.call('mh_record_key') # record flag OFF also bypasses
    print('  [ok] recorder handoff: chosen root once, independent shared tones, native Part channels, CHAN OFF recording and record-flag guard')


def live_transpose_gate():
    """Compare live Harmony's output hook with the original stock instructions."""
    patched=Machine();stock=Machine()
    entry,end=0x4009fb3a,0x4009fb58
    raw=(ROOT/'out/raw/section_3_MAIN_OS.bin').read_bytes()
    stock.uc.mem_write(entry,raw[entry-0x40000400:end-0x40000400])
    stock.sym['stock_transpose']=entry
    cases=0
    for track in (0,7):
        for kind in (1,2):
            patched.setting(track,kind)
            patched.uc.mem_write(0x46c77b1e+10*track,b'\x01')
            # A muted sequencer pool must not silence an independent live arp.
            patched.uc.mem_write(patched.sym['mh_muted']+track,b'\x01')
            for arranger in (0,12):
                for delta in (-64,-12,-7,-1,0,1,7,12,63):
                    for pitch in range(128):
                        outputs=[]
                        for m,name in ((patched,'mh_transpose'),(stock,'stock_transpose')):
                            lane=m.scratch+0x1000
                            m.uc.mem_write(lane+0x22c,bytes((64+delta,)))
                            m.uc.mem_write(0x46c7a124+track,bytes((arranger,)))
                            m.uc.mem_write(m.scratch,bytes((pitch,)))
                            m.call(name,d1=pitch,stop=end,regs={UC_M68K_REG_A5:lane,UC_M68K_REG_A2:m.scratch,UC_M68K_REG_D7:track})
                            outputs.append((bytes(m.uc.mem_read(m.scratch,1)),tuple(m.uc.reg_read(r) for r in (UC_M68K_REG_D0,UC_M68K_REG_D1,UC_M68K_REG_A0,UC_M68K_REG_A1,UC_M68K_REG_A7))))
                        assert outputs[0]==outputs[1],(track,kind,arranger,delta,pitch,outputs)
                        cases+=1
    print(f'  [ok] live arp TRAN: {cases} exact stock comparisons, both Harmony modes, track isolation, arranger offsets and MIDI bounds')


def controls_gate():
    """Check the shared NOTE callback and inherited KEY control boundaries."""
    m=Machine();u=m.uc
    def args(slot,delta):
        u.mem_write(m.stack+4,slot.to_bytes(4,'big')+(delta & 0xffffffff).to_bytes(4,'big'))
    entry='bf_encoder' if 'bf_encoder' in m.sym else 'mh_note_encoder'
    # Original CHAN, BANK, PROG and SBNK must reach the untouched stock body.
    for slot in (0,1,2,4):
        args(slot,1);m.call(entry,stop=0x4003a8f0)
        assert u.reg_read(UC_M68K_REG_A7)==m.stack-16
        assert int.from_bytes(u.mem_read(m.stack+4,4),'big')==slot
    u.mem_write(0x100b14cc,b'\x01')
    for delta,want in [(1,0),(1,0),(1,0),(1,1),(100000,2),(-4,1),(-4,0),(-100000,0)]:
        args(5,delta);m.call(entry,stop=0x40036548)
        assert m.call('mh_get',1)==want
        assert m.call('mh_get',0)==0
    u.mem_write(m.sym['mh_page_track'],(1).to_bytes(4,'big'))
    for slot,getter,values in ((0,'mh_voic_get',[0,2,3,4,1]),
                              (1,'mh_sprd_get',[0,1,2]),
                              (2,'mh_root_get',[0,1,2,3]),
                              (3,'mh_size_get',[0,1,2,3])):
        for want in values[1:]:
            for tick in range(4):
                args(slot,1);m.call('mh_page_encoder',stop=m.sym['mh_page_draw'])
            assert m.call(getter,1)==want,(slot,want)
        args(slot,0x7fffffff);m.call('mh_page_encoder',stop=m.sym['mh_page_draw'])
        assert m.call(getter,1)==values[-1]
        for want in reversed(values[:-1]):
            args(slot,-0x80000000);m.call('mh_page_encoder',stop=m.sym['mh_page_draw'])
            assert m.call(getter,1)==want
    for slot in range(4,7):
        before=m.harmony_state()
        args(slot,100);m.call('mh_page_encoder')
        assert m.harmony_state()==before
    if 'bf_source_get' in m.sym:
        m.follow_write('source',bytes((0,1,0,0,0,0,0,0)),0)
        args(5,1);m.call('mh_arp_encoder',stop=0x40079d48)
        assert u.reg_read(UC_M68K_REG_A7)==m.stack
        args(0,1);m.call('mh_arp_encoder',stop=0x4007a2f4)
        u.mem_write(0x100b14cc,b'\0')
        args(5,1);m.call('mh_arp_encoder',stop=0x4007a2f4)
    print('  [ok] NOTE controls pass through, HARM clamps per track, inherited KEY is read-only')


def voicing_sort_gate():
    """All orderings/ties of up to four ranked pitches; independent oracle."""
    m=Machine(); u=m.uc; count=0
    registers=[UC_M68K_REG_D0+i for i in range(8)]+[UC_M68K_REG_A0+i for i in range(7)]
    for voices in (3,4):
        for pitches in itertools.product((0,12,64,127),repeat=voices):
            data=bytes(pitches)+(b'\xd3' if voices==3 else b'')
            u.mem_write(m.scratch,data)
            before={r:0x12340000+i for i,r in enumerate(registers)}
            before[UC_M68K_REG_D6]=voices;before[UC_M68K_REG_A0]=m.scratch
            m.call('mh_sort_chord',regs=before)
            assert bytes(u.mem_read(m.scratch,4))==bytes(sorted(pitches))+data[voices:]
            assert all(u.reg_read(r)==v for r,v in before.items())
            assert u.reg_read(UC_M68K_REG_A7)==m.stack+4
            count+=1
    print(f'  [ok] voicing sort: {count} pitch order/tie cases, padding and all registers preserved')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix',nargs='?',default='midi-harmony')
    a=ap.parse_args()
    machine_gate()
    final_note_gate()
    keyboard_gate()
    octave_gate()
    voicing_sort_gate()
    voicing_gate()
    inversion_gate()
    omit_gate()
    root_placement_gate()
    spread_gate()
    recorder_gate()
    live_transpose_gate()
    controls_gate()
if __name__=='__main__':main()
