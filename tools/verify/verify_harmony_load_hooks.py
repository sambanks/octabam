#!/usr/bin/env python3
"""Execute STORE load dispatch from native callers, substituting native I/O.

Pin caller identity, mask selection, stack/register preservation and native
result branches. Full port gates cover the real bank and companion files.
"""
import struct
import subprocess
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import *
import verify_midi_harmony as h


def check():
    cases = 0
    sites = (
        (0x400852c8, 0x40090504, 16, None),
        (0x40084d60, 0x400905d4, 16, 0xfffb),
        (0x400853d8, 0x400905d4, 28, 0xffff),
        (0x40085452, 0x400905d4, 20, 0x8005),
    )
    for site, native, cleanup, mask in sites:
        for result in (0, 1, 0xfffffff9):
            m = h.Machine(); u = m.uc
            nm = subprocess.check_output(['m68k-elf-nm', str(h.ROOT/'out/platform/runtime/runtime.elf')], text=True)
            sym = {f[2]:int(f[0],16) for f in (line.split() for line in nm.splitlines()) if len(f)==3}
            assert bytes(u.mem_read(site, 6)) == b'\x4e\xb9' + struct.pack('>I', native)
            # STORE owns the entry. The caller's cleanup/TST stays stock.
            assert bytes(u.mem_read(site+6,6)) == bytes.fromhex('4fef')+struct.pack('>H',cleanup)+bytes.fromhex('4a80')
            wrapper = sym['store_loadall' if mask is None else 'store_loadmask']
            assert bytes(u.mem_read(native,6)) == b'\x4e\xf9'+struct.pack('>I',wrapper)
            calls = []; banks = []; clients = []
            other = {sym[name]:name for name in sym if name.startswith(('plk_st_load','kits_st_load','scn_st_load'))
                     and ('loadall' if mask is None else 'loadmask') in name}
            def observe(u, address, size, data):
                sp = u.reg_read(UC_M68K_REG_A7)
                if address == native:
                    calls.append(struct.unpack('>I',u.mem_read(sp,4))[0])
                elif address == native+8:
                    # Native load's exact epilogue: restore its saved callee
                    # registers and return to STORE's post-load dispatcher.
                    regs = (*range(UC_M68K_REG_D2,UC_M68K_REG_D7+1),
                            *range(UC_M68K_REG_A2,UC_M68K_REG_A6+1))
                    for reg,value in zip(regs,struct.unpack('>11I',u.mem_read(sp,44))):u.reg_write(reg,value)
                    u.reg_write(UC_M68K_REG_D0,result)
                    u.reg_write(UC_M68K_REG_PC,int.from_bytes(u.mem_read(sp+328,4),'big'))
                    u.reg_write(UC_M68K_REG_A7,sp+332)
                elif address == sym['ch_file_read']:
                    banks.append(u.reg_read(UC_M68K_REG_D0))
                    u.reg_write(UC_M68K_REG_D0,0xdeadbeef)
                elif address in other:
                    clients.append((other[address],u.reg_read(UC_M68K_REG_D1),u.reg_read(UC_M68K_REG_D2)))
            u.hook_add(UC_HOOK_CODE,observe)
            # Only I/O/helpers are substituted; STORE and Harmony's loops run.
            for address in (*other, sym['ch_lock_init'],sym['ch_file_read'],sym['ch_nv_save']):
                u.mem_write(address,b'\x4e\x75')
            args=struct.pack('>8I',0x100b14f0,mask or 0,3,4,5,6,7,8)
            u.reg_write(UC_M68K_REG_SR,0x2700);u.reg_write(UC_M68K_REG_A7,m.stack)
            u.mem_write(m.stack,args)
            u.reg_write(UC_M68K_REG_D0,result)
            u.reg_write(UC_M68K_REG_D2,0x23456789);u.reg_write(UC_M68K_REG_D3,0x3456789a)
            continuation=site+12;m.stops={continuation};m.arrival=None
            u.emu_start(site,0,count=10000)
            assert m.arrival==continuation,(hex(site),hex(u.reg_read(UC_M68K_REG_PC)))
            assert calls==[site+6],calls
            assert banks==[b for b in range(16) if mask is None or mask&(1<<b)],banks
            for name,seen_mask,caller in clients:
                if mask is not None: assert (seen_mask,caller)==(mask,site+6),(name,seen_mask,caller)
            expected={name for name in other.values() if ('loadall' if mask is None else 'loadmask') in name}
            assert {name for name,_,_ in clients}==expected,(clients,expected)
            assert len(clients)==len(expected),clients
            assert u.reg_read(UC_M68K_REG_A7)==m.stack+cleanup
            assert bytes(u.mem_read(m.stack,len(args)))==args
            assert u.reg_read(UC_M68K_REG_D0)==result
            assert u.reg_read(UC_M68K_REG_D2)==0x23456789
            assert u.reg_read(UC_M68K_REG_D3)==0x3456789a
            # Execute real branches rather than reading Unicorn's lazy flags.
            if site in (0x400852c8,0x400853d8):success,failure=continuation+8,continuation+2
            else:success,failure=continuation+2,continuation+4
            m.stops={success,failure};m.arrival=None;u.emu_start(continuation,0,count=10)
            assert m.arrival==(failure if result&0x80000000 else success)
            cases+=1
    print(f'[ok] {cases} STORE load dispatch/caller/continuation cases, including error results',flush=True)
    return cases


if __name__=='__main__':check()
