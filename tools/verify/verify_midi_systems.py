#!/usr/bin/env python3
"""Exercise actual combined mode/scale clients, including unsupported music.

Uses the linked image and the unchanged 20,000-instruction call ceiling.
The stock toast is the only mocked UI boundary; no hardware claim is made.
"""
import json
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import UC_M68K_REG_A7
from harmony_midi_machine import Machine
from verify_midi_scale_provider import symbols, field, MASKS, U32
from verify_scales import CATALOGUE, encode, mask


def main():
    m = Machine(symbols)
    m.instruction_budget = 20_000
    u, s = m.uc, m.sym
    notices = []
    def toast(uc, pc, size, data):
        if pc == 0x4005a2b8:
            sp = uc.reg_read(UC_M68K_REG_A7)
            pointer = int.from_bytes(uc.mem_read(sp+4, 4), 'big')
            notices.append(bytes(uc.mem_read(pointer, 80)).split(b'\0')[0].decode())
    u.mem_write(0x4005a2b8, bytes.fromhex('4e75'))
    u.hook_add(UC_HOOK_CODE, toast)
    def c(name, *args):
        u.mem_write(m.stack+4, b''.join((a & U32).to_bytes(4, 'big') for a in args))
        return m.call(name)
    def select(ident, tonic=0, context=0, track=0):
        u.mem_write(field(context, track), bytes((encode(tonic, ident),)))
        u.mem_write(s['sc_lib'] + (context%64)*8+track, bytes((ident if ident > 7 else 0,)))

    if 'msp_scales_read' in s:
        # UI/live context deliberately differs from the requested one. Extra
        # catalogue IDs have SCALES' destination-Part semantics on saved KEY.
        for context in (0, 7, 64, 127):
            for ident, row in CATALOGUE.items():
                for tonic in range(12):
                    select(ident, tonic, context, 3)
                    want = mask(row[4]) | tonic<<12 | (0x10000 if ident in (1, 6) else 0)
                    assert m.call('msp_scales_read', 3, context) == want, (context, ident, tonic)
        # Every catalogue choice still works on an ordinary Follow track.
        for ident, row in CATALOGUE.items():
            select(ident, 0, 0, 0)
            desc = m.call('msp_scales_read', 0, 0)
            if 'bf_quant' in s:
                for pitch in (0, 61, 66, 127):
                    assert m.call('bf_quant', pitch, 0) == m.call('msp_quant', pitch, desc)
        before = bytes(u.mem_read(s['hd_banks'], 128*131))
        for ident in range(8, 53):
            select(ident)
            assert mask(CATALOGUE[ident][4]) not in MASKS
            assert m.call('mh_scale_record_at', 0, 0) == U32-1
            assert m.call('mh_scale_supported_ui', 0) == 0
            m.call('mh_set_native', 0, 0)
            assert m.call('mh_set', 0, 2) == 0
            assert m.call('mh_get', 0) == 0
            assert notices[-1] == 'HARM NEEDS DIATONIC SCALE'
            m.call('mh_set_native', 0, 2)
            for entry in ('mh_direct', 'mh_generate'):
                u.mem_write(m.scratch, bytes((60, 64, 67, 60)))
                assert m.call(entry, 0, 0, a0=m.scratch) == U32, (entry, ident)
                assert bytes(u.mem_read(m.scratch, 4)) == bytes(4)
            assert bytes(u.mem_read(s['hd_banks'], 128*131)) == before
        # A followed source can become unsupported after Harmony was enabled.
        # The consumer refuses it without editing the source or its own intent.
        if 'bf_source_resolve_at' in s:
            select(1, track=1)
            m.follow_write('source', bytes((1,)), track=1)
            select(36, track=0)
            m.call('mh_set_native', 1, 2)
            assert m.call('mh_scale_supported_ui', 1) == 0
            assert m.call('sc_track', 1) == 36<<4
            u.mem_write(0x100b14cc, b'\x01')
            assert m.call('sc_can_edit') == 0
            assert m.call('mh_set', 1, 0) == 0
            assert m.call('mh_get', 1) == 2
            select(2, track=0)
            assert m.call('mh_scale_supported_ui', 1) == 1
            u.mem_write(0x100b14cc, b'\0')
            m.follow_write('source', b'\0', track=1)
        select(1)
        print('[ok] all 52 catalogue IDs, working/saved contexts; unsupported direct/followed Harmony preserves degree intent')

    if 'ch_accepts_absolute' in s:
        m.call('mh_set_native', 0, 0)
        assert c('ch_accepts_absolute', 0) == 1
        m.call('mh_set_native', 0, 2)
        assert c('ch_accepts_absolute', 0) == 0
        u.mem_write(s['ch_ready'], b'\x01')
        u.mem_write(s['ch_bank'], bytes((4,50,53,57,60)))
        assert c('ch_trig_key', 0, 1) == 1
        assert u.mem_read(s['ch_held_n'], 1) == b'\0'
        assert notices[-1] == 'CHORDS NEEDS HARM OFF'
        assert s['ch_current'] != s['mhc_current']
        assert s['ch_st_newproj'] != s['mhc_st_newproj']
        for mode, row in ((0,0),(1,1),(2,2),(6,3),(4,4)):
            assert m.call('tm_row', mode) == row
        print('[ok] independent Factory/Harmony storage and menus; Factory refuses degree-owned tracks with an explicit message')
    print(json.dumps({'instruction_limit': m.instruction_budget, 'hardware_tested': False}))


if __name__ == '__main__':
    main()
