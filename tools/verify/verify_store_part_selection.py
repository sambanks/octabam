#!/usr/bin/env python3
"""STORE selection, registration guards and non-MIDI native Part publication."""
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath
from remix import registry
from midi_machine import Machine
from verify_store_part_copy import symbols
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import UC_M68K_REG_PC, UC_M68K_REG_A7, UC_M68K_REG_A1, UC_M68K_REG_D3


def registrations():
    ns=runpy.run_path(str(ROOT/'modules/store/parts.py'))
    active,windows,writes=ns['layout']({'MIDI FOLLOW','MIDI LOOPBACK'})
    assert windows==((0x4e2,288),)
    assert set(writes)=={0x4e2+36*t+f for t in range(8) for f in (3,12,13,15)}
    base=registry.modules()['STORE']
    # Real registry binding must omit *all* optional code, hooks and claims.
    for remix in ('octabam','octabam-bus','events-clients'):
        chosen=registry.bound(registry.remix(remix))['STORE']
        assert chosen.linked==base.linked and chosen.detours==base.detours
        assert chosen.pokes==base.pokes and chosen.claims==base.claims
    for remix,setup in (('midi-loopback',False),('midi-follow',True),('midi-follow-events',True)):
        r=registry.remix(remix);m=registry.bound(r)['STORE']
        assert len(m.detours)==len(base.detours)+3+int(setup)
        assert len({d.site for d in m.detours})==len(m.detours)
        assert ('storepartsetup' in {u.label for u in m.linked})==setup
        assert len(m.pokes)==1 and len(m.claims.part_window)==8
        assert all('MIDI PART STATE' not in x.requires for x in registry.selected(r))
    malformed=[{'X': (((0,0),),())}, {'X': (((-1,2),),())},
               {'X': (((0x18b1,2),),())}, {'X': (((0,1),),(1,))},
               {'X': (((0,1),),(0,0))}]
    for clients in malformed:
        try:ns['layout'](set(),clients)
        except ValueError:pass
        else:raise AssertionError(clients)
    assert ns['layout']({'X'},{'X': (((12,2),(10,3),(30,1)),(10,30))})[1]==((10,4),(30,1))
    print('[ok] absent/single/combined STORE bindings, unique hooks, merged windows and invalid registrations')
    return ns


def generic_window(ns):
    # Two disjoint non-MIDI regions, with an odd stride and the last Part byte.
    # This is a synthetic reader, never a selectable production module.
    clients={'PROBE': (((0x10,5),(0x18b0,2)),(0x11,0x18b1))}
    ns['part_inc'].__globals__['PART_CLIENTS']=clients
    ns['part_inc'].__globals__['PART_CALLBACKS']={
        'snapshot_pre': (('PROBE','store_part_probe_pre'),),
        'replace_pre': (('PROBE','store_part_probe_replace'),),
    }
    with tempfile.TemporaryDirectory(prefix='octabam-store-part-') as tmp:
        d=Path(tmp);(d/'remix.inc').write_text(ns['part_inc']({'PROBE'}))
        callback=['.text']
        for label in ('pre','replace'):
            prefix='store_part_probe_'+label
            callback += [f'.global {prefix}',f'{prefix}:',f'move.l %d0,{prefix}_arg',
                         'move.l store_part_snapshot_bank,%d0',f'move.l %d0,{prefix}_bank',
                         f'addq.l #1,{prefix}_calls']
            callback += [f'move.l #0x12345678,%{reg}' for reg in
                         [*(f'd{i}' for i in range(8)),*(f'a{i}' for i in range(7))]]
            callback += ['rts']
        callback += ['.data','.balign 4']
        for label in ('pre','replace'):
            for field in ('arg','bank','calls'):
                name=f'store_part_probe_{label}_{field}'
                callback += [f'.global {name}',f'{name}: .long 0']
        (d/'callbacks.s').write_text('\n'.join(callback)+'\n')
        objs=[]
        for slug in ('part','part-copy','callbacks'):
            obj=d/(slug+'.o');objs.append(obj)
            subprocess.run(['m68k-elf-as','-mcpu=54455','-I',str(d),'-o',str(obj),str(d/'callbacks.s' if slug=='callbacks' else ROOT/f'modules/store/{slug}.s')],check=True)
        elf=d/'part.elf';binary=d/'part.bin'
        subprocess.run(['m68k-elf-ld','-Ttext=0x48000000','-e','store_part_read','--defsym=store_part_copy_target=0x400d6bb8',
                        '--defsym=store_part_init_target=0x400d6bbc','-o',str(elf),*map(str,objs)],check=True)
        subprocess.run(['m68k-elf-objcopy','-O','binary',str(elf),str(binary)],check=True)
        rows=subprocess.check_output(['m68k-elf-nm',str(elf)],text=True)
        syms={n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [TtBbDdAa] (store_part_\w+)$',rows,re.M)}
        m=Machine(symbols);u=m.uc;u.mem_map(0x48000000,0x10000);u.mem_write(0x48000000,binary.read_bytes());m.sym.update(syms)
        bank=0x400e21e0;part=bank+0x8ed80+3*0x18b2;context=3
        old=bytes((i*7+11)&255 for i in range(0x18b2));new=bytes((i*3+17)&255 for i in range(0x18b2))
        u.mem_write(part,old);u.mem_write(0x47002000,new)
        for offset in (0x10,0x11,0x12,0x13,0x14,0x18b0,0x18b1):assert m.call('store_part_read',offset,context)==old[offset]
        for offset in (0,0x15,0x18af,0x18b2):assert m.call('store_part_read',offset,context)==0xffffffff
        # MIDI adapter bounds do not grant access to an unregistered window.
        assert m.call('store_part_midi_read',0,context)==0xffffffff
        assert m.call('store_part_midi_key',0,context)==0xffffffff
        assert m.call('store_part_write',0x10,context,regs={UC_M68K_REG_D3:4})==0
        assert m.call('store_part_write',0x11,context,regs={UC_M68K_REG_D3:255})==1
        assert u.mem_read(part+0x11,1)==b'\xff'
        u.mem_write(part,old)
        paused=False
        def interrupt(uc,pc,size,data):
            nonlocal paused
            if not paused and pc==0x400208ae and uc.reg_read(UC_M68K_REG_A1)>=part+100:
                paused=True;uc.emu_stop()
        hook=u.hook_add(UC_HOOK_CODE,interrupt)
        u.reg_write(UC_M68K_REG_A7,m.stack);u.mem_write(m.stack,b''.join(v.to_bytes(4,'big') for v in (m.done,part,0x47002000,0x18b2)))
        m.arrival=None;u.emu_start(syms['store_part_native_copy'],0,count=1000000)
        assert paused and m.arrival is None
        saved=u.context_save();m.stack-=0x1000
        for offset in (0x10,0x11,0x12,0x13,0x14,0x18b0,0x18b1):assert m.call('store_part_read',offset,context)==old[offset]
        assert m.call('store_part_epoch',context)==0
        assert m.call('store_part_write',0x11,context,regs={UC_M68K_REG_D3:33})==0
        m.stack+=0x1000;u.context_restore(saved);m.arrival=None
        u.emu_start(u.reg_read(UC_M68K_REG_PC),0,count=1000000)
        assert m.arrival==m.done and bytes(u.mem_read(part,0x18b2))==new
        assert m.call('store_part_epoch',context)==1
        for label,arg,published in (('pre',bank,0),('replace',part,bank)):
            for field,expected in (('calls',1),('arg',arg),('bank',published)):
                address=syms[f'store_part_probe_{label}_{field}']
                assert int.from_bytes(u.mem_read(address,4),'big')==expected,(label,field)
        for offset in (0x10,0x11,0x12,0x13,0x14,0x18b0,0x18b1):assert m.call('store_part_read',offset,context)==new[offset]
        u.hook_del(hook)
    print('[ok] non-MIDI disjoint windows, odd snapshot stride, last-byte bounds, read-only fields, clobbering companion callbacks and interrupted copy publication')


if __name__=='__main__':
    ns=registrations()
    generic_window(ns)
