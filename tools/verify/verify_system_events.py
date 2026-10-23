#!/usr/bin/env python3
"""Execute available platform dispatchers with zero, one and three unrelated clients.

Assembles the production sources with synthetic registrations, then substitutes
client callbacks and native continuation/copy boundaries. A second pass runs
the native MIDI arbitration and packet construction with only the sender stubbed.
Separate module and image gates verify real clients and installed hooks.
"""
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import *
def read_sr(uc, probe):
    # Unicorn's host SR accessor changes deferred flags; execute MOVE.W SR,D7
    # in a saved context so observing CCR cannot change the resumed test.
    saved = uc.context_save()
    try:
        uc.emu_start(probe, probe + 2, count=1)
        assert uc.reg_read(UC_M68K_REG_PC) == probe + 2
        return uc.reg_read(UC_M68K_REG_D7) & 0xffff
    finally:
        uc.context_restore(saved)

REGS = [UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3,
        UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
        UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3,
        UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6]
BASE, STACK, DONE = 0x48000000, 0x47008000, 0x4700fff0


class Fixture:
    def __init__(self, slug, count, work, handled=None):
        declaration = runpy.run_path(str(ROOT / 'modules' / slug / 'manifest.py'))
        fn = declaration['event_inc' if slug == 'sequencer-events' else 'edit_inc']
        keys = tuple(f'CLIENT {i}' for i in range(count))
        events = declaration['EVENTS']
        fn.__globals__['CLIENTS'] = tuple((k, f'test{i}', events if handled is None else handled) for i, k in enumerate(keys))
        include = fn(keys)
        assert not any(f'test{i}_' in fn(()) for i in range(count)), 'absent clients must be omitted'
        self.callbacks = {}
        suffixes = events if slug == 'sequencer-events' else ('claim','handle','copy_pre')
        for i in range(count):
            for suffix in suffixes:
                address = 0x47002000 + len(self.callbacks)*16
                self.callbacks[address] = (i,suffix)
                include += f'.set test{i}_{suffix},0x{address:x}\n'
        (work/'remix.inc').write_text(include)
        subprocess.run(['m68k-elf-as','-mcpu=54455','-I',str(work),'-o',str(work/'events.o'),
                        str(ROOT/'modules'/slug/'events.s')],check=True,capture_output=True)
        subprocess.run(['m68k-elf-ld','-Ttext=0x48000000','-o',str(work/'events.elf'),str(work/'events.o')],check=True,capture_output=True)
        subprocess.run(['m68k-elf-objcopy','-O','binary',str(work/'events.elf'),str(work/'events.bin')],check=True)
        nm=subprocess.check_output(['m68k-elf-nm',str(work/'events.elf')],text=True)
        self.sym={f[2]:int(f[0],16) for line in nm.splitlines() if len(f:=line.split())==3}
        self.uc=u=Uc(UC_ARCH_M68K,UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        for address,size in ((0x40000000,0x100000),(0x46c70000,0x20000),(0x47000000,0x10000),(BASE,0x10000),(0x80000000,0x10000)):
            u.mem_map(address,size)
        u.mem_write(BASE,(work/'events.bin').read_bytes())
        u.mem_write(DONE-16,bytes.fromhex('40c7'))
        self.log=[];self.claims=set();self.arrived=None;self.stop=DONE
        self.native_count=0
        self.sent=None
        self.instructions=0
        u.hook_add(UC_HOOK_CODE,self.hook)

    def ret(self,result=None):
        u=self.uc;sp=u.reg_read(UC_M68K_REG_A7)
        if result is not None:u.reg_write(UC_M68K_REG_D0,result)
        u.reg_write(UC_M68K_REG_PC,int.from_bytes(u.mem_read(sp,4),'big'))
        u.reg_write(UC_M68K_REG_A7,sp+4)

    def hook(self,u,pc,size,data):
        if pc==self.stop:
            self.arrived=pc;u.emu_stop();return
        self.instructions+=1
        if pc in self.callbacks:
            client,event=self.callbacks[pc]
            args=tuple(u.reg_read(r) for r in REGS[:4])
            self.log.append((client,event,args))
            if event=='midi_note_accepted' and self.sent is not None:
                assert self.sent, 'notification must follow native send'
                assert args[2:] == (self.sent[-1][2],self.sent[-1][1])
            if event=='handle':
                assert [u.reg_read(r) for r in REGS]==self.before, 'handler native registers'
                assert u.reg_read(UC_M68K_REG_A7)==STACK, 'handler native stack'
                assert bytes(u.mem_read(STACK+4,8))==struct.pack('>II',4,7)
                self.ret(91);return
            if event=='copy_pre':
                assert bytes(u.mem_read(0x47005000,4))==b'old!'
            for i,r in enumerate(REGS):u.reg_write(r,0xdead0000+i)
            self.ret(int(client in self.claims) if event=='claim' else 0xabcdef01)
        elif pc==0x40010bc8 and self.sent is not None:
            sp=u.reg_read(UC_M68K_REG_A7)
            length,address=struct.unpack('>II',u.mem_read(sp+4,8))
            assert length==3
            self.sent.append(bytes(u.mem_read(address,length)))
            self.ret()
        elif pc==0x40020898:
            self.native_count+=1
            sp=u.reg_read(UC_M68K_REG_A7)
            dst,src,n=struct.unpack('>III',u.mem_read(sp+4,12))
            u.mem_write(dst,bytes(u.mem_read(src,n)))
            self.ret(dst)

    def call(self,name,stop=DONE,values=None,args=()):
        u=self.uc;self.log=[];self.arrived=None;self.stop=stop;self.native_count=0
        self.instructions=0
        self.before=[0x12340000+i for i in range(len(REGS))]
        for i,v in (values or {}).items():self.before[i]=v
        u.reg_write(UC_M68K_REG_SR,0x2700)
        u.reg_write(UC_M68K_REG_A7,STACK)
        for r,v in zip(REGS,self.before):u.reg_write(r,v)
        u.mem_write(STACK,struct.pack('>I',DONE)+b''.join(struct.pack('>I',v) for v in args))
        u.emu_start(self.sym[name],0,count=10000)
        assert self.arrived==stop,(name,hex(u.reg_read(UC_M68K_REG_PC)))

    def preserved(self,changes=None,sp=STACK):
        want=self.before.copy()
        for i,v in (changes or {}).items():want[i]=v
        assert [self.uc.reg_read(r) for r in REGS]==want, (want,[self.uc.reg_read(r) for r in REGS])
        assert self.uc.reg_read(UC_M68K_REG_A7)==sp



def native_midi_cases(work, count):
    """Run stock packet construction/arbitration, not a model of its decisions.

    Enter after native track/mute/channel selection with a prepared note pool;
    stop after the first voice. The sender records packets instead of using UART.
    No proprietary bytes are embedded here: load the user's reconstructed image.
    """
    f=Fixture('sequencer-events',count,work);u=f.uc
    raw=(ROOT/'out/raw/section_3_MAIN_OS.bin').read_bytes()
    start,end=0x4009faba,0x4009fd6e
    u.mem_write(start,raw[start-0x40000400:end-0x40000400])
    declaration=runpy.run_path(str(ROOT/'modules/sequencer-events/manifest.py'))
    for detour in declaration['MODULE'].detours:
        if start <= detour.site < end:
            offset=detour.site-0x40000400
            assert raw[offset:offset+len(detour.expect)]==detour.expect
            u.mem_write(detour.site,b'\x4e\xf9'+f.sym[detour.symbol].to_bytes(4,'big'))
    f.sym['native_note']=start
    frame,lane,config,active=0x47006000,0x47004000,0x47005000,0x47005500
    cases=0
    for track in (0,3,7):
        for channel,pitch in ((0,0),(6,61),(15,127)):
            for pool in (0,1):
                for mode in ('free','replace','live_replace','reserved','lower_priority','zero_velocity','invalid_note'):
                    if mode=='replace' and track==7: continue
                    if mode=='lower_priority' and track==0: continue
                    u.mem_write(0x46c70000,bytes(0x20000))
                    u.mem_write(lane,bytes(0x300))
                    u.mem_write(config,bytes(0x100))
                    u.mem_write(frame-80,bytes(80))
                    u.mem_write(active,b'\0')
                    velocity=0 if mode=='zero_velocity' else 93
                    note=255 if mode=='invalid_note' else pitch
                    u.mem_write(lane+0x221,bytes((velocity,)))
                    u.mem_write(lane+0x22c,b'\x40')  # neutral native transpose
                    u.mem_write(frame-4,bytes((note,255,255,255)))
                    u.mem_write(frame-12,struct.pack('>I',active))
                    u.mem_write(0x46c77b1e+10*track,bytes((pool,)))
                    owner=255
                    if mode=='replace': owner=4*(track+1)
                    if mode=='live_replace': owner=4
                    if mode=='reserved': owner=32
                    if mode=='lower_priority': owner=0
                    owner_address=0x46c78152+128*channel+pitch
                    u.mem_write(owner_address,bytes((owner,)))
                    if mode in ('replace','live_replace'):
                        previous=(0x46c7a1a0 if mode=='live_replace' else 0x46c77a16)+8*owner
                        u.mem_write(previous,struct.pack('>II',0xffffff90|channel,pitch))
                    if mode=='live_replace':
                        mask_address=0x46c79eba+4*(4*channel+(pitch>>5))
                        u.mem_write(mask_address,struct.pack('>I',1<<(pitch&31)))
                    # Poison the old packet: native code must construct all three bytes.
                    u.mem_write(0x400d807c,bytes((0xc2,17,9,0,0,0)))
                    f.sent=[]
                    stop=end if velocity==0 else 0x4009fd2a
                    f.call('native_note',stop,values={5:channel,7:track,8:config,13:lane,14:frame})
                    accepted=mode in ('free','replace','live_replace')
                    want=[(i,'midi_note_accepted',(track,pool,velocity,pitch)) for i in range(count)] if accepted else []
                    assert f.log==want,(mode,track,channel,pool,f.log,want)
                    assert len(f.sent)==(2 if mode in ('replace','live_replace') else int(accepted)), (mode,f.sent)
                    if accepted:
                        assert f.sent[-1]==bytes((0x90|channel,pitch,velocity))
                        assert bytes(u.mem_read(owner_address,1))==bytes((4*track,))
                        assert bytes(u.mem_read(0x46c77a16+32*track,8))==struct.pack('>II',0xffffff90|channel,pitch)
                        assert bytes(u.mem_read(active,1))==b'\x01'
                    assert u.reg_read(UC_M68K_REG_A7)==STACK, 'native stack cleanup'
                    cases+=1
    return cases


def empty_midi_cost(work, transport_clients):
    """Count executed instructions from the installed detour to its continuation.

    Include the entry JMP and displaced work; exclude the continuation itself.
    Compare with the stock instruction at that same site in a separate emulator
    (never rewrite already translated code). This is not a CPU-cycle benchmark.
    """
    declaration=runpy.run_path(str(ROOT/'modules/sequencer-events/manifest.py'))
    for detour in declaration['MODULE'].detours:
        if detour.symbol not in ('seq_sent_a','seq_sent_b'):continue
        # Match EUCLID's registration: transport clients must not enable MIDI work.
        patched=Fixture('sequencer-events',transport_clients,work,handled=('start','resume'))
        stock=Fixture('sequencer-events',0,work)
        patched.uc.mem_write(detour.site,b'\x4e\xf9'+patched.sym[detour.symbol].to_bytes(4,'big'))
        stock.uc.mem_write(detour.site,detour.expect)
        stop=detour.site+len(detour.expect)
        counts=set()
        for track in range(8):
            for pool in (0,1):
                for f in (patched,stock):
                    f.sym['note_site']=detour.site
                    f.uc.mem_write(0x46c77b1e+10*track,bytes((pool,)))
                    f.uc.mem_write(0x400d807c,bytes((0x90,61,93)))
                    f.call('note_site',stop,values={7:track})
                    assert not f.log
                    changed=1 if detour.symbol=='seq_sent_a' else 0
                    f.preserved({changed:0xffffff90})
                counts.add((patched.instructions,stock.instructions))
                assert read_sr(patched.uc,DONE-16)==read_sr(stock.uc,DONE-16), 'native condition codes'
        assert counts=={(4,1)}, (detour.symbol,counts)
        print(f'[ok] empty MIDI dispatcher at {detour.site:#x}: 4 instructions including entry JMP and displaced work; stock 1; added 3 ({transport_clients} transport clients, 8 tracks x 2 pool kinds; not cycles)')


def transport_registration_cases(work):
    """Exercise independent event selection against stock transport boundaries."""
    declaration=runpy.run_path(str(ROOT/'modules/sequencer-events/manifest.py'))
    events=declaration['EVENTS']
    cases=0
    for mask in range(1 << len(events)):
        handled=tuple(event for i,event in enumerate(events) if mask & (1 << i))
        for detour in declaration['MODULE'].detours:
            if detour.symbol not in ('seq_start','seq_resume'):continue
            event=detour.symbol.removeprefix('seq_')
            patched=Fixture('sequencer-events',int(bool(handled)),work,handled=handled)
            stock=Fixture('sequencer-events',0,work)
            patched.uc.mem_write(detour.site,b'\x4e\xf9'+patched.sym[detour.symbol].to_bytes(4,'big'))
            stock.uc.mem_write(detour.site,detour.expect)
            stop=detour.site+len(detour.expect)
            for playing in (0,1,0x80000000,0xffffffff):
                for f in (patched,stock):
                    f.sym['transport_site']=detour.site
                    f.call('transport_site',stop,values={0:playing})
                    f.preserved()
                    assert bytes(f.uc.mem_read(0x800065b8,4))==struct.pack('>I',playing)
                want=[(0,event)] if event in handled else []
                assert [(i,e) for i,e,a in patched.log]==want,(handled,event,patched.log)
                assert all(a[0]==playing for i,e,a in patched.log)
                if event not in handled:
                    assert (patched.instructions,stock.instructions)==(3,1), (event,handled,patched.instructions,stock.instructions)
                assert read_sr(patched.uc,DONE-16)==read_sr(stock.uc,DONE-16), 'native condition codes'
                cases+=1
    print(f'[ok] {cases} transport cases across every event-registration subset: native PLAYING write, callbacks, registers, stack and condition codes; empty start/resume 3 instructions vs stock 1, added 2 (not cycles)')


def main():
    cases=0
    with tempfile.TemporaryDirectory(prefix='octabam-system-events-') as td:
        work=Path(td)
        for count in (0,1,3):
            if (ROOT/'modules/sequencer-events/manifest.py').exists():
                f=Fixture('sequencer-events',count,work);u=f.uc
                for name,event,stop in (('seq_start','start',0x4009c3da),('seq_resume','resume',0x4009c4da)):
                    f.call(name,stop,values={0:1})
                    assert [(i,e) for i,e,a in f.log]==[(i,event) for i in range(count)]
                    assert all(a[0]==1 for i,e,a in f.log)
                    assert bytes(u.mem_read(0x800065b8,4))==struct.pack('>I',1)
                    f.preserved();assert read_sr(u,DONE-16)==0x2700
                    cases+=1
                for track in range(9):
                    for pool in (0,1):
                        for velocity in (0,100):
                            u.mem_write(0x46c77b1e+10*track,bytes((pool,)))
                            # Status and note must differ: the callback exposes the note,
                            # while the displaced native instruction still reads status.
                            pitch = (track * 17 + pool * 11 + velocity) % 128
                            status = 0x90 | (track % 16)
                            u.mem_write(0x400d807c,bytes((status,pitch,velocity)))
                            for name,stop,changed in (('seq_sent_a',0x4009fbb8,1),('seq_sent_b',0x4009fd00,0)):
                                f.call(name,stop,values={7:track})
                                want=[(i,'midi_note_accepted',(track,pool,velocity,pitch)) for i in range(count)] if track<8 else []
                                assert f.log==want,(f.log,want)
                                f.preserved({changed:0xffffff00 | status});cases+=1
            if (ROOT/'modules/edit-events/manifest.py').exists():
                f=Fixture('edit-events',count,work);u=f.uc
                u.mem_write(0x47005000,b'old!');u.mem_write(0x47005100,b'new!')
                f.call('ed_copy',args=(0x47005000,0x47005100,4))
                assert [(i,e,a[:3]) for i,e,a in f.log]==[(i,e,(0x47005000,0x47005100,4)) for e in ('copy_pre',) for i in range(count)]
                assert f.native_count==1
                f.preserved({0:0x47005000},STACK+4);cases+=1
                for claims in [set(),*({i} for i in range(count)),set(range(count))]:
                    f.claims=claims
                    stop=DONE if claims else 0x400508ec
                    f.call('ed_held',stop,args=(4,7))
                    owner=min(claims) if claims else None
                    assert [(i,e) for i,e,a in f.log]==([(i,'claim') for i in range(owner+1)]+[(owner,'handle')] if claims else [(i,'claim') for i in range(count)])
                    assert all(a[:2]==(4,7) for i,e,a in f.log if e=='claim')
                    if claims:f.preserved({0:91},STACK+4)
                    else:f.preserved(sp=STACK-80)
                    cases+=1
    native_cases=0
    if (ROOT/'modules/sequencer-events/manifest.py').exists():
        with tempfile.TemporaryDirectory(prefix='octabam-native-events-') as td:
            transport_registration_cases(Path(td))
            for transport_clients in (0,1):
                empty_midi_cost(Path(td),transport_clients)
            for count in (0,1,3):
                native_cases+=native_midi_cases(Path(td),count)
        print(f'[ok] {native_cases} native MIDI cases: packet payloads, free/replacement ownership, rejected notes, zero velocity and native continuation')
    print(f'[ok] {cases} assembled cases for available dispatchers: 0/1/3 unrelated clients, register preservation, ordering and native boundaries')

if __name__=='__main__':main()
