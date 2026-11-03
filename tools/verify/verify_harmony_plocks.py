#!/usr/bin/env python3
"""Execute shared editing/copy events with Harmony and P2, including both stores in each case.

Native memcpy executes unmodified. File and CS1 boundaries are substituted
to isolate ownership, ordering and ABI; full firmware gates cover real I/O.
"""
import json
import sys
import struct
import subprocess
from collections import Counter
from unicorn.m68k_const import *
from verify_harmony_degree_files import Files, ROOT, BANK, STRIDE, PATTERN
from harmony_retained import raw_p2 as raw
from verify_midi_sram import OFFSETS
import harmony_retained as retained

P2NV, P2SIZE = 0x100f8600, 15464


class Combined(Files):
    def __init__(self):
        self.calls = Counter()
        self.copy_paths = []
        super().__init__()
        nm = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
        self.sym.update({f[2]: int(f[0], 16) for f in (line.split() for line in nm.splitlines()) if len(f) == 3})
        assert 'ed_copy' in self.sym, 'build a remix selecting EDIT EVENTS and PLOCKS P2'
        self.call('plk_init')
        self.call('ch_lock_init')

    def io(self, u, pc, size, user):
        for name in ('plk_st_newproj', 'kits_st_newproj', 'scn_st_newproj',
                     'ch_st_newproj', 'ch_st_newproj_post'):
            if pc == self.sym.get(name):
                self.calls[name] += 1
        if pc in (0x40020898, 0x400909d8, 0x4000fbb4, 0x40016388):
            self.calls[pc] += 1
        sp = u.reg_read(UC_M68K_REG_A7)
        if (pc == 0x4000fd34 and 'store_newproj' in self.sym
                and bytes(u.mem_read(int.from_bytes(u.mem_read(sp, 4), 'big'), 6))
                == bytes.fromhex('4ef9400909e2')):
            # STORE has executed every new-project client, then replayed
            # native's push A2 / push 0 / JSR prologue. Substitute the same
            # native body as the old 0x400909d8 stub, preserving that stack.
            self.calls[0x400909d8] += 1
            u.reg_write(UC_M68K_REG_A2, int.from_bytes(u.mem_read(sp+8, 4), 'big'))
            u.reg_write(UC_M68K_REG_D0, 0)
            u.reg_write(UC_M68K_REG_PC, int.from_bytes(u.mem_read(sp+12, 4), 'big'))
            u.reg_write(UC_M68K_REG_A7, sp+16)
            return
        if pc == 0x40016388:
            dst, src = struct.unpack('>2I', u.mem_read(sp+4, 8))
            self.copy_paths.append((self.string(dst), self.string(src)))
        if pc in (0x400909d8, 0x4000fbb4):
            if pc == 0x4000fbb4:
                bank = int.from_bytes(u.mem_read(sp+4, 4), 'big')
                data=bytearray(u.mem_read(0x1001614e, STRIDE))
                if 'rp_native_copy' in self.sym:
                    for offset in OFFSETS:data[offset]=255
                u.mem_write(BANK+bank*STRIDE, bytes(data))
            u.reg_write(UC_M68K_REG_D0, 0)
            u.reg_write(UC_M68K_REG_PC, int.from_bytes(u.mem_read(sp, 4), 'big'))
            u.reg_write(UC_M68K_REG_A7, sp+4)
            return
        super().io(u, pc, size, user)

    def seed(self):
        roots, qualities = super().seed()
        u, s = self.uc, self.sym
        p2 = bytearray(b'\xff'*98304)
        records = [(i*9, i%128) for i in range(4768 if 'plk_nv_encode' not in s and 'plk_pool_encode' not in s else 10234)]
        for i, value in records: p2[i] = value
        u.mem_write(s['STORE'], bytes(p2))
        return bytes(roots), bytes(qualities), bytes(p2), records

    def c(self, name, *args):
        result = super().c(name, *args)
        assert self.uc.reg_read(UC_M68K_REG_A7) == self.stack+4, name
        return result


def main():
    if len(sys.argv)>1:
        from remix import registry
        selected=registry.remix(sys.argv[1]).modules
        if not {'MIDI HARMONY','PLOCKS P2'} <= set(selected):
            print('[SKIP] Harmony/PLOCKS composition: select both clients')
            return
    m = Combined(); u, s = m.uc, m.sym
    global P2SIZE
    pooled='plk_pool_encode' in s
    upstream_p2='plk_nv_encode' not in s and not pooled
    P2SIZE=14320 if upstream_p2 else 20 if pooled else 15464
    magic=b'P2NV' if upstream_p2 else b'P2S1' if pooled else b'P2R1'
    roots, qualities, p2, records = m.seed()
    guards=((P2NV-16,16),)  # MIDI Scenes owns the immediately following range
    for address, length in guards: u.mem_write(address, b'\xa5'*length)
    # Both full-capacity stores are checkpointed through the real shared entry.
    u.mem_write(m.stack+4, struct.pack('>I', 0))
    m.call('store_tocs1', stop=0x4000fafa)
    assert u.reg_read(UC_M68K_REG_A7) == m.stack-12
    assert bytes(u.mem_read(P2NV,4)) == magic
    assert retained.committed(m)
    assert int.from_bytes(u.mem_read(P2NV+(12 if pooled else 8),4),'big') == len(records)
    for address, length in guards: assert u.mem_read(address,length) == b'\xa5'*length
    m.sym['native_copy']=0x40020898
    m.c('native_copy',0x1001614e,BANK,STRIDE)
    u.mem_write(s['STORE'], b'\xcc'*98304)
    u.mem_write(s['hd_banks'], b'\xcc'*16768)
    u.mem_write(s['ch_lock_table'], b'\xcc'*8192)
    m.c('store_fromcs1', 0)
    assert m.calls[0x4000fbb4] == 1
    assert bytes(u.mem_read(s['STORE'],98304)) == p2
    assert bytes(u.mem_read(s['hd_banks'],16768)) == roots
    assert bytes(u.mem_read(s['ch_lock_table'],8192)) == qualities
    if not upstream_p2:
        # The old full-length P2NV occupies the new Harmony range. Decode and
        # migrate it before Harmony touches that range; all 10,234 locks survive.
        u.mem_write(P2NV, raw(records, bank=0))
        u.mem_write(s['STORE'], b'\xcc'*98304)
        m.c('store_fromcs1', 0)
        assert bytes(u.mem_read(s['STORE'],98304)) == p2
        assert bytes(u.mem_read(P2NV,4)) == magic
        for address, length in guards:
            if address < P2NV or address >= 0x100ffe00:
                assert u.mem_read(address,length) == b'\xa5'*length
        print('[ok] full 10,234 P2 locks plus 8,192 CHRD/DEG steps: retention and legacy migration', flush=True)

    roots, qualities, p2, _ = m.seed()
    # Whole-pattern clipboard and undo moves carry both independent mirrors.
    expected_native = bytes(u.mem_read(BANK,PATTERN))
    for dst, src in ((0x460c8122,BANK),(0x460bf218,0x460c8122),
                     (BANK+PATTERN,0x460bf218)):
        before = m.calls[0x40020898]
        m.c('ed_copy',dst,src,PATTERN)
        assert m.calls[0x40020898] == before+1
        assert bytes(u.mem_read(dst,PATTERN)) == expected_native
    assert bytes(u.mem_read(s['STORE']+6144,6144)) == p2[:6144]
    assert bytes(u.mem_read(s['hd_banks']+1048,1048)) == bytes(u.mem_read(s['hd_banks'],1048))
    assert bytes(u.mem_read(s['ch_lock_table']+512,512)) == qualities[:512]
    # Audio track copy must move P2, MIDI track copy must move CHRD and DEG.
    for dst, src, length in ((BANK+2*PATTERN,BANK,0x91a),
                             (BANK+2*PATTERN+0x48d0,BANK+0x48d0,0x8b0)):
        before = m.calls[0x40020898]
        m.c('ed_copy',dst,src,length)
        assert m.calls[0x40020898] == before+1
    assert bytes(u.mem_read(s['STORE']+12288,768)) == p2[:768]
    assert bytes(u.mem_read(s['ch_lock_table']+1024,64)) == qualities[:64]
    assert bytes(u.mem_read(s['hd_banks']+2096,130)) == bytes(u.mem_read(s['hd_banks'],130))
    print('[ok] pattern/track/clipboard/undo copies preserve both mirrors; native memcpy once', flush=True)

    roots, qualities, p2, _ = m.seed()
    m.call('store_bankw_mid',stop=0x400918b0,regs={UC_M68K_REG_D6:1})
    assert u.reg_read(UC_M68K_REG_A7) == m.stack
    assert m.files['/SET/PROJECT/p2lk01.work'][16:] == p2
    assert m.files['/SET/PROJECT/hdeg01.work'][:4] == b'HDP4'
    m.files['/SET/PROJECT/bank01.work'] = bytes(u.mem_read(BANK,STRIDE))
    dst, src = m.scratch+0x300, m.scratch+0x400
    u.mem_write(dst,b'/SET/PROJECT/bank01.strd\0')
    u.mem_write(src,b'/SET/PROJECT/bank01.work\0')
    before = len(m.copy_paths)
    assert m.c('store_fcopy',dst,src,0) == 0
    assert [d.split('/')[-1] for d,_ in m.copy_paths[before:]] == ['bank01.strd','p2lk01.strd','hdeg01.strd']
    for prefix in ('bank','p2lk','hdeg'):
        assert m.files[f'/SET/PROJECT/{prefix}01.strd'] == m.files[f'/SET/PROJECT/{prefix}01.work']
    saved = dict(m.files)
    m.failure = 'open'
    m.call('store_bankw_mid',stop=0x400919d6,regs={UC_M68K_REG_D6:1})
    assert m.files == saved
    before = len(m.copy_paths)
    assert m.c('store_fcopy',dst,src,0) == 0xfffffff9
    assert len(m.copy_paths) == before and m.files == saved
    m.failure = None
    print('[ok] all three companion/native saves and backups; Harmony failure blocks every backup write', flush=True)

    # Enter the installed editor hook. Context chooses a handler, not just
    # track type; ordinary audio/MIDI pages must still reach native editing.
    s['installed_editor'] = 0x400508e4
    for midi, page, window, modal, target in (
            (0,3,1,0,s['plk_edit']), (1,0,0,m.scratch,s['ch_step_encoder']),
            (0,0,0,0,0x400508ec), (1,1,0,0,0x400508ec)):
        for addr,value in ((0x80000012,midi),(0x460d1684,page),
                           (0x460d175c,window),(s['mh_page_win'],modal)):
            u.mem_write(addr,struct.pack('>I',value))
        u.mem_write(0x460d174a,b'\0\1')
        u.mem_write(m.stack+4,struct.pack('>II',0,1))
        m.call('installed_editor',stop=target)
        assert u.reg_read(UC_M68K_REG_A7) == m.stack-(80 if target==0x400508ec else 0)
    before = m.calls[0x400909d8]
    m.c('store_newproj')
    assert m.calls[0x400909d8] == before+1
    for name in ('plk_st_newproj', 'kits_st_newproj', 'scn_st_newproj',
                     'ch_st_newproj', 'ch_st_newproj_post'):
        if name in s: assert m.calls[name] == 1, name
    assert u.mem_read(s['STORE'],1572864) == b'\xff'*1572864
    assert u.mem_read(s['ch_lock_table'],131072) == b'\xff'*131072
    if 'scn_lib' in s: assert u.mem_read(s['scn_lib'],64*4096) == b'\xff'*(64*4096)
    assert not retained.committed(m)
    report = dict(p2_retained_locks=len(records),harmony_steps=8192,legacy_migration=not upstream_p2,
                  shared_native_memcpy_once=True,copy_and_undo=True,
                  paired_companion_saves=True,save_failure_guard=True,
                  editor_dispatch=True,new_project=True,store_client=True,hardware_tested=False)
    out = ROOT/'out/harmony-plocks'; out.mkdir(exist_ok=True)
    (out/'bridge.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__ == '__main__': main()
