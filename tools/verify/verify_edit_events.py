#!/usr/bin/env python3
"""Execute EVENTS editing with zero, one and three unrelated clients.

Assembles the production sources with synthetic registrations, then substitutes
only client callbacks and native continuation/copy boundaries. Separate module
and image gates verify real clients and native data behavior.
"""
from pathlib import Path
import tempfile
import verify_system_events as fixture
from verify_system_events import Fixture, read_sr, DONE, STACK


def native_copy_cases(work):
    """Compare the tail call against stock memcpy, including its clobbers.

    Load native code from the operator's own image. Only the clients are
    substituted; all native copy instructions execute in this pass.
    """
    class RealCopy(Fixture):
        def hook(self, u, pc, size, data):
            if pc == 0x40020898:
                self.native_count += 1
                assert [u.reg_read(r) for r in fixture.REGS] == self.before
                assert u.reg_read(fixture.UC_M68K_REG_A7) == STACK
                return
            super().hook(u, pc, size, data)

    raw = (fixture.ROOT / 'out/raw/section_3_MAIN_OS.bin').read_bytes()
    fixtures = []
    for count in (0, 1, 3):
        f = RealCopy('edit', count, work)
        f.uc.mem_write(0x40020898, raw[0x40020898 - 0x40000400:0x40022000 - 0x40000400])
        fixtures.append(f)
    cases = 0
    for size in (0, 1, 2, 3, 4, 7, 15, 16, 31, 64, 512):
        for offset in range(4):
            states = []
            for f in fixtures:
                u = f.uc
                payload = bytes(i % 256 for i in range(512))
                dst, src = 0x47005000 + offset, 0x47006000 + offset
                u.mem_write(0x47005000, b'old!' + bytes(1020))
                u.mem_write(src, payload)
                f.call('ed_copy', args=(dst, src, size))
                assert bytes(u.mem_read(dst, size)) == payload[:size]
                assert f.native_count == 1
                states.append(([u.reg_read(r) for r in fixture.REGS],
                               u.reg_read(fixture.UC_M68K_REG_A7), read_sr(u, DONE - 16),
                               bytes(u.mem_read(0x47005000, 1024))))
            assert states[0] == states[1] == states[2], (size, offset)
            cases += 1
    print(f'[ok] {cases} native memcpy comparisons: 0/1/3 clients, 11 lengths x 4 alignments; entry frame, copy bytes, return registers, stack and CCR match stock')

def main():
    cases=0;costs={}
    with tempfile.TemporaryDirectory(prefix='octabam-edit-events-') as td:
        work=Path(td)
        for count in (0,1,3):
            f=Fixture('edit',count,work);u=f.uc
            u.mem_write(0x47005000,b'old!');u.mem_write(0x47005100,b'new!')
            f.call('ed_copy',args=(0x47005000,0x47005100,4))
            assert [(i,e,a[:3]) for i,e,a in f.log]==[(i,e,(0x47005000,0x47005100,4)) for e in ('copy_pre',) for i in range(count)]
            assert f.native_count==1
            assert bytes(u.mem_read(0x47005000,4))==b'new!'
            f.preserved({0:0x47005000},STACK+4)
            assert read_sr(u,DONE-16)==0x2705, 'native copy condition codes'
            costs[count]={'copy':f.instructions}
            cases+=1
            for claims in [set(),*({i} for i in range(count)),set(range(count))]:
                f.claims=claims
                stop=DONE if claims else 0x400508ec
                f.call('ed_held',stop,args=(4,7))
                owner=min(claims) if claims else None
                assert [(i,e) for i,e,a in f.log]==([(i,'claim') for i in range(owner+1)]+[(owner,'handle')] if claims else [(i,'claim') for i in range(count)])
                assert all(a[:2]==(4,7) for i,e,a in f.log if e=='claim')
                if claims:f.preserved({0:91},STACK+4)
                else:
                    f.preserved(sp=STACK-80)
                    assert read_sr(u,DONE-16)==0x2700, 'native held fallthrough flags'
                    costs[count]['held_fallthrough']=f.instructions
                cases+=1
    assert costs == {
        0: {'copy': 0, 'held_fallthrough': 2},
        1: {'copy': 13, 'held_fallthrough': 16},
        3: {'copy': 21, 'held_fallthrough': 26},
    }, costs
    print('Dispatcher instruction counts (excluding native bodies and synthetic callbacks):', costs)
    print(f'[ok] {cases} assembled cases for EVENTS editing: 0/1/3 unrelated clients, register preservation, ordering and native boundaries')
    with tempfile.TemporaryDirectory(prefix='octabam-events-native-copy-') as td:
        native_copy_cases(Path(td))

if __name__=='__main__':main()
