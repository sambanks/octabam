#!/usr/bin/env python3
"""Execute linked companion I/O with byte-accurate files and injected failures.

Only the native filesystem boundary is substituted. Header construction,
validation, checksums, publication and save/copy guards execute firmware code.
Full buffered I/O and FAT are separately exercised by the port verifier.
"""
import json
import struct
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import *
from verify_harmony_degree_integration import DegreeMachine, ROOT


BANK, STRIDE, PATTERN = 0x400e21e0, 0x9b340, 0x8ed8


class Files(DegreeMachine):
    def __init__(self):
        super().__init__()
        self.files={};self.opened=None;self.position=0;self.failure=None;self.writes_count=0
        self.exists=self.scratch+0x100
        self.uc.mem_write(0x46c823fa,self.exists.to_bytes(4,'big'))
        self.uc.mem_write(self.scratch,b'/SET/PROJECT\0')
        self.uc.hook_add(UC_HOOK_CODE,self.io)
    def seed(self):
        u, s = self.uc, self.sym
        u.mem_write(BANK, b'\xff'*STRIDE)
        for p in range(16):
            u.mem_write(BANK+p*PATTERN+0x8e57, b'\0')
        for part in range(8):
            base = BANK+(0x8ed80+part*0x18b2 if part<4 else 0x9504a+(part-4)*0x18b2)
            for t in range(8):
                u.mem_write(base+0x3e2+t*32, b'\x30')
                for field, value in ((3,0),(5,2),(16,0),(17,1),(18,0),(19,35)):
                    u.mem_write(base+0x4e2+t*36+field, bytes((value,)))
        self.call('hd_bank_loaded', 0)
        roots = bytearray()
        qualities = bytearray()
        for lane in range(128):
            ds = [(lane+step)%84 for step in range(64)]
            notes = [max(0, min(127, 12*(d//7-1)+(0,2,4,5,7,9,11)[d%7])) for d in ds]
            roots.extend(bytes(ds+notes+[2,0,255]))
            qualities.extend(bytes((lane+step)%8 for step in range(64)))
            for step, note in enumerate(notes):
                u.mem_write(BANK+(lane//8)*PATTERN+0x4900+(lane%8)*0x8b0+step*32, bytes((note,)))
        u.mem_write(s['hd_banks'], bytes(roots))
        u.mem_write(s['ch_lock_table'], bytes(qualities))
        return bytes(roots), bytes(qualities)

    def string(self,address):return bytes(self.uc.mem_read(address,260)).split(b'\0')[0].decode()
    def io(self,u,pc,size,user):
        if pc not in (self.exists,0x40025230,0x40013a08,0x40016864,0x40016564,
                      0x400166b8,0x4001677c,0x400148d4,0x40016388):return
        sp=u.reg_read(UC_M68K_REG_A7)
        a=struct.unpack('>5I',u.mem_read(sp+4,20));result=0
        if pc==self.exists:result=int(self.string(a[0]) in self.files)
        elif pc==0x40025230:result=self.scratch
        elif pc==0x40013a08:
            fmt=self.string(a[1])
            text=fmt%((self.string(a[2]),a[3]) if '%02d' in fmt else self.string(a[2]))
            u.mem_write(a[0],text.encode()+b'\0');result=len(text)
        elif pc==0x40016864:
            name,mode=self.string(a[1]),self.string(a[2])
            if self.failure=='open' or mode=='r' and name not in self.files:result=-7
            else:
                self.opened=name;self.position=0;self.writes_count=0
                if mode=='w':self.files[name]=b''
                result=1
        elif pc==0x40016564:
            data=self.files[self.opened][self.position:self.position+a[2]]
            if self.failure=='read':data=data[:-1]
            if data:u.mem_write(a[1],data)
            self.position+=len(data);result=int(len(data)==a[2])
        elif pc==0x400166b8:
            self.writes_count+=1;data=bytes(u.mem_read(a[1],a[2]))
            failed=self.failure==f'write{self.writes_count}'
            if failed:data=data[:len(data)//2]
            self.files[self.opened]+=data;result=0 if failed else 1
        elif pc==0x4001677c:result=-7 if self.failure=='close' else 0
        elif pc==0x400148d4:result=len(self.files[self.opened])
        elif pc==0x40016388:
            dst,src=self.string(a[0]),self.string(a[1])
            if src not in self.files:result=-12
            else:self.files[dst]=self.files[src]
        u.reg_write(UC_M68K_REG_D0,result&0xffffffff)
        u.reg_write(UC_M68K_REG_PC,int.from_bytes(u.mem_read(sp,4),'big'))
        u.reg_write(UC_M68K_REG_A7,sp+4)


def fnv(data):
    h=0x811c9dc5
    for byte in data:h=((h^byte)*0x1000193)&0xffffffff
    return h


def main():
    m=Files();u=m.uc;s=m.sym;b=0x400e21e0
    m.call('ch_lock_init');u.mem_write(b,b'\xff'*0x9b340)
    for p in range(16):u.mem_write(b+p*0x8ed8+0x8e57,b'\0')
    for part in range(8):
        base=b+(0x8ed80+part*0x18b2 if part<4 else 0x9504a+(part-4)*0x18b2)
        for t in range(8):
            u.mem_write(base+0x3e2+t*32,b'\x30')
            for slot,value in ((3,0),(5,0),(16,0),(17,2),(18,0),(19,35)):
                u.mem_write(base+0x4e2+t*36+slot,bytes((value,)))
    u.mem_write(0x46c82456,b.to_bytes(4,'big'))
    m.call('mh_set_native',0,2);m.call('hd_bank_loaded',0)
    m.c('hd_edit_base_c',0,0,0,39) # Native default belongs to the Part, never the companion.
    m.c('hd_edit_step_c',0,0,0,3,38)
    u.mem_write(s['ch_lock_table']+3,b'\x04')
    assert m.call('ch_file_write',0)==1
    path='/SET/PROJECT/hdeg01.work';original=m.files[path]
    version=4
    assert len(original)==15136
    assert original[:8]==f'HDP{version}'.encode()+version.to_bytes(4,'big')
    assert int.from_bytes(original[16:20],'big')==fnv(original[32:])
    # The validation helper may tail-call and rewrite its argument; the hash
    # wrapper must still hash the COMPLETE payload from its original pointer.
    payload=0x48000000;u.mem_map(payload,0x10000);u.mem_write(payload,original[32:])
    assert m.call('hd_payload_hash',a0=payload)==fnv(original[32:])
    m.call('hd_bank_reset',0);u.mem_write(s['ch_lock_table'],b'\xff'*8192)
    m.c('hd_edit_base_c',0,0,0,41)
    m.call('ch_file_read',0)
    assert bytes(u.mem_read(s['ch_lock_status'],1))==b'\x01'
    assert m.c('hd_base_c',0,0,0)==41
    assert bytes(u.mem_read(s['ch_lock_table']+3,1))==b'\x04'
    invalid=[('short',original[:-1],2),('long',original+b'\0',2),
             ('checksum',original[:100]+bytes((original[100]^1,))+original[101:],2),
             ('identity',original[:20]+bytes((original[20]^1,))+original[21:],3)]
    invalid.append(('old_format',b'HDP2'+(2).to_bytes(4,'big')+original[8:],2))
    # A valid checksum never admits a reserved metadata value or token.
    for name,offset,value in (('metadata',32,252),('token',33,255)):
        broken=bytearray(original);broken[offset]=value
        broken[16:20]=fnv(broken[32:]).to_bytes(4,'big')
        invalid.append((name,bytes(broken),2))
    for name,data,status in invalid:
        m.files[path]=data;m.call('ch_file_read',0)
        assert bytes(u.mem_read(s['ch_lock_status'],1))==bytes((status,)),name
        assert bytes(u.mem_read(s['ch_lock_table'],8192))==b'\xff'*8192,name
        assert m.c('hd_base_c',0,0,0)==41,name
        assert m.call('ch_file_write',0)==0xfffffff9,name
        assert m.files[path]==data,name
    backup='/SET/PROJECT/hdeg01.strd'
    for failure in ('open','write1','write2','close'):
        m.files[path]=original;m.files[backup]=original
        u.mem_write(s['ch_lock_status'],b'\x01');m.failure=failure
        assert m.call('ch_file_write',0)==0xfffffff9,failure
        assert bytes(u.mem_read(s['ch_lock_status'],1))==b'\x04'
        u.mem_write(m.scratch+0x200,b'/SET/PROJECT/bank01.work\0')
        assert m.call('ch_copy_guard',a0=m.scratch+0x200)==0xfffffff9
        assert m.files[backup]==original
    result={'round_trip':'passed','incoming_part_default_preserved':'passed','full_payload_checksum':'passed','malformed_files':len(invalid),
            'injected_write_failures':4,'stored_backup_guard':'passed','hardware_tested':False}
    print(json.dumps(result))
    out=ROOT/'out/harmony-degrees';out.mkdir(parents=True,exist_ok=True)
    (out/'files.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
