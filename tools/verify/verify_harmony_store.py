#!/usr/bin/env python3
"""STORE checked callbacks: clobber-safe arguments, veto ordering and errors."""
import json
import struct
import subprocess
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import *
from verify_harmony_degree_files import Files, ROOT


def main():
    m=Files();u=m.uc
    nm=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    m.sym.update({f[2]:int(f[0],16) for f in (line.split() for line in nm.splitlines()) if len(f)==3})
    table=m.scratch+0x800; callbacks=[m.scratch+0x900+i*16 for i in range(3)]
    seen=[]; returns=[]
    def callback(u,pc,size,data):
        if pc not in callbacks:return
        i=callbacks.index(pc);sp=u.reg_read(UC_M68K_REG_A7)
        ret=int.from_bytes(u.mem_read(sp,4),'big')
        seen.append((i,tuple(u.reg_read(r) for r in (UC_M68K_REG_D0,UC_M68K_REG_D1,UC_M68K_REG_D2))))
        # The contract permits every register except SP to be clobbered.
        for r in (*range(UC_M68K_REG_D0,UC_M68K_REG_D7+1),*range(UC_M68K_REG_A0,UC_M68K_REG_A6+1)):
            u.reg_write(r,0x1234abcd)
        u.reg_write(UC_M68K_REG_D0,returns[i]&0xffffffff)
        u.reg_write(UC_M68K_REG_A7,sp+4);u.reg_write(UC_M68K_REG_PC,ret)
    u.hook_add(UC_HOOK_CODE,callback)
    cases=0
    for returns in ([],[0],[3,0,9],[-7,0,0],[0,-12,0],[0,0,-19]):
        seen.clear();u.mem_write(table,struct.pack('>'+str(len(returns)+1)+'I',*callbacks[:len(returns)],0))
        result=m.call('fire_checked',91,52,a0=table,regs={UC_M68K_REG_D2:77})
        end=next((i+1 for i,r in enumerate(returns) if r<0),len(returns))
        assert seen==[(i,(91,52,77)) for i in range(end)],seen
        expected=returns[end-1] if end and returns[end-1]<0 else 0
        assert result==expected&0xffffffff,(returns,result)
        assert u.reg_read(UC_M68K_REG_A7)==m.stack+4
        cases+=1
    # Actual native-copy failure must reach the caller and never copy HDP4.
    dst,src=m.scratch+0x300,m.scratch+0x400
    u.mem_write(dst,b'/SET/PROJECT/bank01.strd\0');u.mem_write(src,b'/SET/PROJECT/bank01.work\0')
    m.files['/SET/PROJECT/hdeg01.work']=b'companion that must not be copied'
    m.files['/SET/PROJECT/hdeg01.strd']=b'last stored companion'
    m.files['/SET/PROJECT/p2lk01.strd']=b'last stored P2 backup'
    before=dict(m.files)
    assert m.c('store_fcopy',dst,src,0)==0xfffffff4
    assert m.files==before
    # After native success, a missing companion must erase a stale destination
    # with HDP0. A companion write failure must be returned to the caller.
    m.files.clear();m.files['/SET/PROJECT/bank01.work']=b'native'
    m.files['/SET/PROJECT/hdeg01.strd']=b'stale'
    assert m.c('store_fcopy',dst,src,0)==0
    assert m.files['/SET/PROJECT/hdeg01.strd']==b'HDP0'+bytes(28)
    m.files['/SET/PROJECT/hdeg01.strd']=b'last good';m.failure='open'
    assert m.c('store_fcopy',dst,src,0)==0xfffffff9
    assert m.files['/SET/PROJECT/hdeg01.strd']==b'last good'
    # The missing-source marker must report open, write AND close failures.
    # A failed close may mean buffered data never reached the card.
    for failure in ('open','write1','close'):
        m.files.clear();m.files['/SET/PROJECT/bank01.work']=b'native'
        m.failure=failure;m.writes_count=0
        assert m.c('store_fcopy',dst,src,0)==0xfffffff9,failure
    # No Harmony persistence replacement may compete with STORE's detours.
    from remix.registry import _load_one
    harmony=_load_one(ROOT/'modules/midi-harmony/manifest.py')
    store=_load_one(ROOT/'modules/store/manifest.py')
    assert not ({d.site for d in harmony.detours}&{d.site for d in store.detours})
    assert not any(o.module=="STORE" for o in harmony.overrides)
    result={'checked_dispatch_cases':cases,'native_copy_failure_preserved':True,'native_failure_preserves_all_companions':True,
            'missing_companion_clears_stale_backup':True,'companion_failure_propagates':True,
            'empty_marker_io_failures':3,'no_harmony_store_overrides':True,'hardware_tested':False}
    (ROOT/'out/harmony-degrees').mkdir(parents=True, exist_ok=True)
    (ROOT/'out/harmony-degrees/store-client.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
