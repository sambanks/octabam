#!/usr/bin/env python3
"""STORE copy notifications follow native success; failures leave clients alone."""
import json
import struct
import subprocess
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import *
from midi_machine import Machine, ROOT


def symbols():
    raw=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    return {f[2]:int(f[0],16) for f in (line.split() for line in raw.splitlines()) if len(f)==3}


def lifecycle():
    """Execute the selected wrappers, replacing only clients/native I/O."""
    m=Machine(symbol_loader=symbols);u=m.uc
    guards={a:n for n,a in m.sym.items() if n.endswith('_st_bankw_guard')}
    pre={a:n for n,a in m.sym.items() if n.endswith('_st_bankw_pre')}
    new={a:n for n,a in m.sym.items() if n.endswith(('_st_newproj','_st_newproj_post'))}
    seen=[];refuse=0
    def intercept(u,pc,size,data):
        sp=u.reg_read(UC_M68K_REG_A7)
        if pc==0x4000fd34:
            # Displaced PUSH A2 / PUSH 0 / JSR has run. Substitute the native
            # body and unwind its actual frame, returning through np_after
            # when selected. The native result must survive post callbacks.
            seen.append('native-new-project')
            u.reg_write(UC_M68K_REG_A2,int.from_bytes(u.mem_read(sp+8,4),'big'))
            u.reg_write(UC_M68K_REG_D0,37)
            u.reg_write(UC_M68K_REG_PC,int.from_bytes(u.mem_read(sp+12,4),'big'))
            u.reg_write(UC_M68K_REG_A7,sp+16)
            return
        if pc not in guards and pc not in pre and pc not in new:return
        name=(guards|pre|new)[pc]
        seen.append(name)
        if pc in guards or pc in pre:
            assert u.reg_read(UC_M68K_REG_D1)==0x8005
        ret=int.from_bytes(u.mem_read(sp,4),'big')
        for r in (*range(UC_M68K_REG_D0,UC_M68K_REG_D7+1),*range(UC_M68K_REG_A0,UC_M68K_REG_A6+1)):
            u.reg_write(r,0xaabbccdd)
        u.reg_write(UC_M68K_REG_D0,(refuse if pc in guards else 0)&0xffffffff)
        u.reg_write(UC_M68K_REG_PC,ret);u.reg_write(UC_M68K_REG_A7,sp+4)
    u.hook_add(UC_HOOK_CODE,intercept)
    results=[]
    for refuse in ((0,-7) if guards else (0,)):
        seen.clear()
        stop=0x400919d6 if refuse else 0x400918b0
        regs={UC_M68K_REG_D2:0x12345678,UC_M68K_REG_D6:0xface8005,UC_M68K_REG_A2:0x23456789}
        m.call('store_bankw_mid',stop=stop,regs=regs)
        assert u.reg_read(UC_M68K_REG_A7)==m.stack
        assert u.reg_read(UC_M68K_REG_D6)==regs[UC_M68K_REG_D6]
        assert u.reg_read(UC_M68K_REG_D2)==(refuse&0xffffffff if refuse else regs[UC_M68K_REG_D2])
        assert u.reg_read(UC_M68K_REG_A2)==(regs[UC_M68K_REG_A2] if refuse else 0x400e21e0)
        assert len(seen)==(1 if refuse else len(guards)+len(pre)),seen
        assert not refuse or all(n.endswith('_guard') for n in seen),seen
        results.append(refuse)
    seen.clear();refuse=0
    assert m.call('store_newproj',regs={UC_M68K_REG_A2:0x23456789})==37
    assert u.reg_read(UC_M68K_REG_A7)==m.stack+4
    assert u.reg_read(UC_M68K_REG_A2)==0x23456789
    assert seen.count('native-new-project')==1 and len(seen)==len(new)+1,seen
    native=seen.index('native-new-project')
    assert all(n.endswith('_st_newproj') for n in seen[:native]),seen
    assert all(n.endswith('_st_newproj_post') for n in seen[native+1:]),seen
    return dict(bank_write_results=results,bank_write_refusal_skips_pre=('passed' if guards else 'not selected'),
                new_project_native_once=True,new_project_phase_order=True,
                new_project_post_clients=sum(n.endswith('_post') for n in new.values()),
                native_result_survives_post_callbacks=True)


def main():
    m=Machine(symbol_loader=symbols);u=m.uc
    handlers={address:name for name,address in m.sym.items()
              if name.endswith(('_st_bankcopy','_st_bankcopy_guard','_st_bankcopy_done'))}
    native=[];clients=[];result=0;dst=m.scratch;src=m.scratch+260
    u.mem_write(dst,b'/SET/PROJECT/bank01.strd\0');u.mem_write(src,b'/SET/PROJECT/bank01.work\0')
    def io(u,pc,size,data):
        if pc!=0x40016388 and pc not in handlers:return
        sp=u.reg_read(UC_M68K_REG_A7);ret=int.from_bytes(u.mem_read(sp,4),'big')
        if pc==0x40016388:
            native.append(struct.unpack('>3I',u.mem_read(sp+4,12)));value=result
        else:
            name=handlers[pc]
            clients.append((name,u.reg_read(UC_M68K_REG_D0),u.reg_read(UC_M68K_REG_D1)))
            value=0
            for r in (*range(UC_M68K_REG_D0,UC_M68K_REG_D7+1),*range(UC_M68K_REG_A0,UC_M68K_REG_A6+1)):
                u.reg_write(r,0xabcddcba)
        u.reg_write(UC_M68K_REG_D0,value&0xffffffff)
        u.reg_write(UC_M68K_REG_A7,sp+4);u.reg_write(UC_M68K_REG_PC,ret)
    u.hook_add(UC_HOOK_CODE,io)
    for result in (-12,0,1):
        native.clear();clients.clear()
        u.mem_write(m.stack+4,struct.pack('>3I',dst,src,0))
        actual=m.call('store_fcopy')
        assert actual==result&0xffffffff,(result,actual)
        assert native==[(dst,src,0)],native
        expected={name for name in handlers.values() if result>=0 or name.endswith('_guard')}
        assert {name for name,_,_ in clients}==expected,(result,clients,expected)
        assert len(clients)==len(expected)
        assert all((d,s)==(dst,src) for _,d,s in clients)
        assert u.reg_read(UC_M68K_REG_A7)==m.stack+4
    report={'native_copy_results':[-12,0,1],'native_copy_once':True,
            'failure_skips_all_companion_notifications':True,'callback_arguments_preserved':True}
    report.update(lifecycle())
    path=ROOT/'out/store-copy.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
