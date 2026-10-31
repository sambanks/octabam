#!/usr/bin/env python3
"""Native Part copy/clear ABI and interrupt-point settings publication gate."""
import json
import re
import subprocess
from midi_machine import Machine, ROOT
B, BS, PS = 0x400e21e0, 0x9b340, 0x18b2

def symbols():
    raw = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {n:int(a,16) for a,n in re.findall(r'^([0-9a-f]+) [TtBbAa] (store_part_\w+)$',raw,re.M)}
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import *

COPY, INIT = 0x40020898, 0x40005638
FIELDS = (3,5,12,13,15,16,17,18,19)
REGS = tuple(range(UC_M68K_REG_D0, UC_M68K_REG_D7+1)) + tuple(range(UC_M68K_REG_A0, UC_M68K_REG_A6+1))

def main():
    m=Machine(symbols);u=m.uc
    stock=(ROOT/'out/raw/section_3_MAIN_OS.bin').read_bytes()
    originals={a:stock[a-0x40000400:a-0x40000400+n] for a,n in ((COPY,6),(INIT,8))}
    patched_entries={a:bytes(u.mem_read(a,n)) for a,n in ((COPY,6),(INIT,8))}
    for entry in (COPY,INIT):
        assert patched_entries[entry][:2]==bytes.fromhex('4ef9'), 'native boundary not installed'
        assert 0x40000400<=int.from_bytes(patched_entries[entry][2:6],'big')<0x400e0000, 'entry must be available before DRAM loading'
    source=0x47002000
    wrapped=True
    active=False
    cold=True
    runtime_end=m.base+len((ROOT/'out/platform/runtime/runtime.bin').read_bytes())
    interrupted=False
    target=0
    def observe(u,pc,size,data):
        nonlocal interrupted
        if cold:
            assert not m.base<=pc<runtime_end, f'early entry executed DRAM at {pc:#x}'
        if active and not interrupted and int.from_bytes(u.mem_read(m.sym['store_part_snapshot_bank'],4),'big'):
            if (pc==0x400208ae and u.reg_read(UC_M68K_REG_A1)>=target+0x4e2+144) or (pc==0x400058da and u.reg_read(UC_M68K_REG_D3)==3):
                interrupted=True;u.emu_stop()
    u.hook_add(UC_HOOK_CODE,observe)
    def install(on):
        nonlocal wrapped
        wrapped=on
        for entry,name in ((COPY,'store_part_native_copy'),(INIT,'store_part_native_init')):
            data=patched_entries[entry] if on else originals[entry]
            u.mem_write(entry,data);u.ctl_remove_cache(entry,entry+len(data))
    def run(entry,args,sr=0x2000,pause=False):
        nonlocal active,interrupted,target
        active=pause;interrupted=False;target=args[0]
        # Derive expected state from the operation's input memory, independent
        # of the wrapper's snapshot/epoch implementation.
        epochs = bytes(u.mem_read(m.sym['store_part_epochs'], 64*4))
        expected_epochs = bytearray(epochs)
        expected_snapshot = bytes(u.mem_read(m.sym['store_part_snapshot'], 4*288))
        length = args[2] if entry == COPY else PS
        bank = (target-B)//BS
        if wrapped and not cold and length > 0 and 0 <= bank < 16:
            bank_base = B + bank*BS
            affected = [p for p in range(4)
                        if target < bank_base+0x8ed80+(p+1)*PS
                        and target+length > bank_base+0x8ed80+p*PS]
            if target+length <= bank_base+BS and affected:
                expected_snapshot = b''.join(bytes(u.mem_read(
                    bank_base+0x8ed80+p*PS+0x4e2, 288)) for p in range(4))
                for part in affected:
                    at = (bank*4+part)*4
                    value = (int.from_bytes(epochs[at:at+4], 'big')+1) & 0xffffffff
                    expected_epochs[at:at+4] = value.to_bytes(4, 'big')
        m.arrival=None;m.stops={m.done}
        for i,reg in enumerate(REGS):u.reg_write(reg,0x12340000+i)
        u.reg_write(UC_M68K_REG_SR,sr);u.reg_write(UC_M68K_REG_A7,m.stack)
        u.mem_write(m.stack,b''.join(x.to_bytes(4,'big') for x in (m.done,*args)))
        u.emu_start(entry,0,count=1000000)
        if pause:
            assert interrupted and m.arrival is None
            assert m.read_sr()&0xff00==sr, 'native operation masked interrupts'
            assert bytes(u.mem_read(m.sym['store_part_snapshot'], 4*288)) == expected_snapshot, 'outgoing snapshot mismatch'
            assert bytes(u.mem_read(m.sym['store_part_epochs'], 64*4)) == epochs
            saved=u.context_save();oldstack=m.stack;m.stack-=0x1000
            bank=(target-B)//BS
            part=(target-B-bank*BS-0x8ed80)//PS
            length=args[2] if entry==COPY else PS
            affected=sum(1<<p for p in range(4) if target<B+bank*BS+0x8ed80+(p+1)*PS and target+length>B+bank*BS+0x8ed80+p*PS)
            assert int.from_bytes(u.mem_read(m.sym['store_part_snapshot_parts'],4),'big')==affected
            # This is the state a playback interruption sees after native bytes
            # have already begun changing, including KEY and other Parts.
            for part in range(4):
                for track in range(8):
                    for field in FIELDS:
                        if field==17:got=m.call('store_part_midi_key',track,bank*4+part)
                        else:got=m.call('store_part_midi_read',track,bank*4+part,regs={UC_M68K_REG_D2:field})
                        assert got==old_settings[part,track,field],(part,track,field,got)
            m.stack=oldstack;u.context_restore(saved);m.arrival=None;m.stops={m.done}
            active=False
            u.emu_start(u.reg_read(UC_M68K_REG_PC),0,count=1000000)
        assert m.arrival==m.done,(hex(entry),hex(u.reg_read(UC_M68K_REG_PC)))
        assert u.reg_read(UC_M68K_REG_A7)==m.stack+4
        assert bytes(u.mem_read(m.stack+4,4*len(args)))==b''.join(x.to_bytes(4,'big') for x in args)
        assert bytes(u.mem_read(m.sym['store_part_snapshot'], 4*288)) == expected_snapshot, 'outgoing snapshot mismatch'
        assert bytes(u.mem_read(m.sym['store_part_epochs'], 64*4)) == bytes(expected_epochs), 'Part epoch publication mismatch'
        assert bytes(u.mem_read(m.sym['store_part_snapshot_bank'],4))==bytes(4)
        assert bytes(u.mem_read(m.sym['store_part_snapshot_parts'],4))==bytes(4)
        return tuple(u.reg_read(r) for r in REGS),m.read_sr()&0xff00
    # Cold entries must use stock before the platform runtime is available.
    # Poisoning its first instruction makes any premature DRAM dispatch fail.
    first=bytes(u.mem_read(m.base,2));u.mem_write(m.base,b'\x4a\xfc')
    # RIG HOSTS and BRAIN customize Part defaults in DRAM after boot.
    # Isolate the cold dispatch contract from those independent downstream
    # hooks, then restore them for all warm copy/clear comparisons below.
    init_hooks={a:bytes(u.mem_read(a,n)) for a,n in
                ((0x4000567e,24),(0x40005830,10),(0x40005840,10),(0x40005a38,8))}
    for a,data in init_hooks.items():
        u.mem_write(a,stock[a-0x40000400:a-0x40000400+len(data)])
        u.ctl_remove_cache(a,a+len(data))
    # Before activation, compare against stock, including CCR, every general
    # register, stack contents and write addresses/order. Dirty stack bytes and
    # all incoming CCR values exercise more than a zero-filled happy path.
    # No physical cache, bus timing or power-off state is modeled here.
    def compare_cold(entry, length, sr, fill):
        dest=0x47004000
        u.mem_write(source,bytes((i*7+11)&255 for i in range(length)))
        results=[]
        for patched in (False,True):
            install(patched)
            u.mem_write(dest-4,bytes((fill,))*(length+8))
            u.mem_write(m.stack-256,bytes((fill,))*288)
            m.writes=[]
            regs=run(entry,(dest,source,length) if entry==COPY else (dest,),sr=sr)
            results.append((regs,m.read_sr(),
                            bytes(u.mem_read(dest-4,length+8)),
                            bytes(u.mem_read(m.stack-256,288)),tuple(m.writes)))
        assert results[0]==results[1],('cold ABI',hex(entry),length,hex(sr),fill)
        if entry==COPY:
            assert results[1][2]==bytes((fill,))*4+bytes(u.mem_read(source,length))+bytes((fill,))*4
    cold_cases=0
    for ccr in range(32):
        for length in (0,1,3,4,15,16,17,150,174):
            compare_cold(COPY,length,0x2700|ccr,0xa5 if ccr&1 else 0x5a)
            cold_cases+=1
        compare_cold(INIT,PS,0x2700|ccr,0xa5 if ccr&1 else 0x5a)
        cold_cases+=1
    # Prove the comparison detects an ABI violation while the native copy
    # still completes: save D7 where the stock fallback saves/restores D2.
    # Corrupting the gate's initial MOVEA instead would jump via an unset A0
    # and test an unmapped fetch rather than the register comparison.
    entry=int.from_bytes(patched_entries[COPY][2:6],'big')
    gate=entry+bytes(u.mem_read(entry,32)).index(bytes.fromhex('2f02226f0008'))
    saved=bytes(u.mem_read(gate,2))
    u.mem_write(gate,bytes.fromhex('2f07'));u.ctl_remove_cache(gate,gate+2)
    try:
        compare_cold(COPY,17,0x271f,0xa5)
    except AssertionError as error:
        assert error.args[0][0]=='cold ABI',error
    else:
        raise AssertionError('cold register corruption accepted')
    finally:
        u.mem_write(gate,saved);u.ctl_remove_cache(gate,gate+2)
    install(True)
    for a,data in init_hooks.items():
        u.mem_write(a,data);u.ctl_remove_cache(a,a+len(data))
    u.mem_write(m.base,first)
    cold=False
    # Exercise the installed boot call, including resident activation builds.
    boot=bytes(u.mem_read(0x40000512,6));assert boot[:2]==bytes.fromhex('4eb9')
    m.sym['store_part_boot_activate']=int.from_bytes(boot[2:],'big')
    hk=re.search(r'^([0-9a-f]+) [Tt] hk_boot$',subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True),re.M)
    if hk and int(hk.group(1),16)==m.sym['store_part_boot_activate']:
        # HOOKS's boot bridge (modules/hooks, boot): BOOT TRACE's note, then a jmp to the
        # resident activation (verify_hooks checks the chain); exercise the activation itself.
        res=re.search(r'^([0-9a-f]+) [Tt] store_part_resident_activate$',subprocess.check_output(
            ['m68k-elf-nm',str(ROOT/'out/linked/store/storepartentry/u.elf')],text=True),re.M)
        act=int(res.group(1),16)
        assert bytes.fromhex('4ef9')+act.to_bytes(4,'big') in bytes(u.mem_read(int(hk.group(1),16),64))
        m.sym['store_part_boot_activate']=act
    m.call('store_part_boot_activate',stop=0x4000f938)
    for target,entry in (('store_part_copy_target','store_part_native_copy'),('store_part_init_target','store_part_native_init')):
        assert int.from_bytes(u.mem_read(m.sym[target],4),'big')==m.sym[entry]
    # Copy ABI/canaries at working, saved and unrelated destinations, including
    # partial SETUP writes and copies touching neither settings nor native Parts.
    cases=0
    for bank,part in ((0,0),(0,3),(15,2)):
        base=B+bank*BS+0x8ed80+part*PS
        for offset,length in ((0,PS),(0,2*PS),(0x4e2,288),(0x4e2+12,1),(0,0),(PS,17)):
            dest=base+offset
            data=bytes((i*7+11)&255 for i in range(length+8));u.mem_write(source,data)
            results=[]
            for patched in (False,True):
                install(patched);u.mem_write(dest-4,b'\xa5'*(length+8))
                result=run(COPY,(dest,source,length))
                assert bytes(u.mem_read(dest-4,length+8))==b'\xa5'*4+data[:length]+b'\xa5'*4
                results.append(result)
            assert results[0]==results[1],(bank,part,offset,length,results)
            cases+=1
    # Native initialization has many direct writes; compare the entire Part.
    for dest in (B+0x8ed80,B+0x9504a,source):
        results=[]
        for patched in (False,True):
            install(patched);u.mem_write(dest-4,b'\xa5'*(PS+8))
            result=run(INIT,(dest,))
            results.append((result,bytes(u.mem_read(dest-4,PS+8))))
        assert results[0]==results[1],('init',hex(dest))
        cases+=1
    install(True)
    for bank,part in ((0,0),(7,3),(15,2)):
        dest=B+bank*BS+0x8ed80+part*PS
        for entry,length in ((COPY,PS),(COPY,2*PS),(INIT,PS)):
            old_settings={}
            for p in range(4):
                for t in range(8):
                    for field in FIELDS:
                        value=(13+p*19+t*11+field)%128
                        old_settings[p,t,field]=value
                        u.mem_write(B+bank*BS+0x8ed80+p*PS+0x4e2+t*36+field,bytes((value,)))
            u.mem_write(source,bytes((i*3+1)&127 for i in range(length)))
            run(entry,(dest,source,length) if entry==COPY else (dest,),pause=True)
            for t in range(8):
                for field in FIELDS:
                    native=u.mem_read(dest+0x4e2+t*36+field,1)[0]
                    got=m.call('store_part_midi_key',t,bank*4+part) if field==17 else m.call('store_part_midi_read',t,bank*4+part,regs={UC_M68K_REG_D2:field})
                    assert got==native,(entry,bank,part,t,field)
    # Negative control: execute the real wrapper with its epoch increment
    # disabled. The state assertions must reject it even though copy succeeds.
    start, end = m.sym['store_part_native_init'], m.sym['store_part_snapshot_bank']
    code = bytes(u.mem_read(start, end-start))
    needle = bytes.fromhex('5290')  # ADDQ.L #1,(A0)
    sites = [i for i in range(0, len(code)-1, 2) if code[i:i+2] == needle]
    assert len(sites) == 1
    address = start + sites[0]
    u.mem_write(address, bytes.fromhex('4e71'))
    u.ctl_remove_cache(address, address+2)
    try:
        try:
            run(COPY, (B+0x8ed80, source, PS))
        except AssertionError as error:
            assert str(error) == 'Part epoch publication mismatch', error
        else:
            raise AssertionError('missing epoch publication was accepted')
    finally:
        u.mem_write(address, needle)
        u.ctl_remove_cache(address, address+2)
    print(json.dumps({'cold_stock_vs_wrapped_operations':cold_cases,
                      'cold_register_corruption_rejected':True,
                      'stock_vs_wrapped_operations':cases,'interrupted_copy_clear_publications':9,
                      'outgoing_reads_per_interruption':4*8*len(FIELDS),'interrupts_remain_enabled':True,
                      'missing_epoch_publication_rejected':True,'full_snapshot_and_all_epochs_checked':True,'production_hooks_installed':True,'hardware_tested':False}))

if __name__=='__main__':main()
