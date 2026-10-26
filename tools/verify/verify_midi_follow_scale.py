#!/usr/bin/env python3
"""Compare Follow's final KEY correction with executable stock 1.40C."""
import argparse
from midi_machine import Machine, ROOT
from unicorn.m68k_const import *


def main():
    m = Machine()
    stock = Machine()
    stock.uc.mem_write(0x40000400, (ROOT / 'out/raw/section_3_MAIN_OS.bin').read_bytes())
    stock.sym['stock_quant'] = 0x4009fb58
    frame = 0x47004000
    lane = 0x47003000
    m.follow_write('source', bytes((0, 1, 2)), 0)

    def native(pitch, key):
        rotation = (12 if key & 1 else 21) - ((key - 1) // 2) if key else 0
        stock.uc.mem_write(frame - 64, rotation.to_bytes(4, 'big'))
        stock.uc.mem_write(stock.scratch, bytes((pitch,)))
        stock.call('stock_quant', stop=0x4009fb80,
                   regs={UC_M68K_REG_A2: stock.scratch, UC_M68K_REG_A6: frame})
        return stock.uc.mem_read(stock.scratch, 1)[0]

    # Independent oracle: execute unmodified stock instructions, including
    # its table, division and low-byte behavior. Do not mirror the algorithm.
    cases = 0
    for key in range(25):
        m.set_key(0, key)
        m.set_key(1, 24 if key != 24 else 1)  # own KEY must not win
        for pitch in range(128):
            expected = native(pitch, key)
            for receiver in (1, 2):
                regs = {UC_M68K_REG_D2: 0x12345678, UC_M68K_REG_D3: 0x76543210,
                        UC_M68K_REG_A0: lane, UC_M68K_REG_A1: frame}
                result = m.call('bf_quant', pitch, receiver, regs=regs)
                assert result & 255 == expected, (key, pitch, receiver, result, expected)
                assert all(m.uc.reg_read(r) == v for r, v in regs.items())
                assert m.uc.reg_read(UC_M68K_REG_D1) == receiver
                cases += 1
            # Actual note handoff, signed TRAN before KEY, all native scales.
            m.uc.mem_write(m.sym['bf_pitches'], bytes((pitch,)))
            m.follow_write('mode', b'\x02', 1)
            for tran in (-64, -13, -1, 0, 1, 7, 63):
                raw = pitch + tran
                want = native(raw, key) if 0 <= raw <= 127 else 255
                m.uc.mem_write(lane + 0x22c, bytes((64 + tran,)))
                m.uc.mem_write(m.scratch, b'\x3c')
                m.call('bf_note', stop=0x4009fb86 if want < 128 else 0x4009fd2a,
                       regs={UC_M68K_REG_D7: 1, UC_M68K_REG_D4: 0,
                             UC_M68K_REG_A2: m.scratch, UC_M68K_REG_A5: lane,
                             UC_M68K_REG_A6: frame})
                assert m.uc.mem_read(m.scratch, 1)[0] == want, (key, pitch, tran, want)
                cases += 1
    print(f'[ok] {cases} stock-oracle cases: OFF, all 24 native keys, direct/chained inheritance, TRAN and bounds')

    if 'ms_snap' in m.sym:
        for key in range(25, 85):
            m.set_key(0, key)
            for pitch in range(128):
                expected = m.call('ms_snap', pitch, key)
                assert m.call('bf_quant', pitch, 2) == expected
        print('[ok] 60 additional MIDI Scales choices use the extension after TRAN')
    else:
        # Native-only UI retains the original formatter/setter. The installed
        # hooks supply inherited KEY and reject edits only on followers.
        assert bytes(m.uc.mem_read(0x4007a3e2, 6)) == b'\x4e\xf9' + m.sym['bf_key_encoder'].to_bytes(4, 'big')
        assert bytes(m.uc.mem_read(0x4003b79c, 6)) == b'\x4e\xf9' + m.sym['bf_key_format'].to_bytes(4, 'big')
        m.set_key(0, 7)
        for track in (0, 1, 2):
            m.uc.mem_write(0x100b14cc, bytes((track,)))
            m.call('bf_key_encoder', 5, stop=0x4007a6ba if track else 0x4007a3ea)
            for control in range(5):
                m.call('bf_key_encoder', control, stop=0x4007a4cc)
            m.uc.mem_write(frame + 12, (19).to_bytes(4, 'big'))
            m.call('bf_key_format', stop=0x4003b7a4, regs={UC_M68K_REG_A6: frame})
            assert m.uc.reg_read(UC_M68K_REG_D2) == (7 if track else 19)
        print('[ok] native-only inherited KEY display and lock; unfollowed controls retain stock paths')

    # LIVE must shift pre-quantized voices, then correct each voice anew.
    # Recovering only the snapped output would accumulate rounding errors.
    from verify_midi_follow_response import fixture
    m = fixture(pitches=(36, 41, 43))
    m.set_key(0, 1)
    m.uc.mem_write(0x46c76fe0 + 32 + 12, b'\x41')  # TRAN +1
    for slot, raw in enumerate((37, 41, 44)):
        assert m.call('bf_quant_note', raw, 1, regs={UC_M68K_REG_D4: slot}) == (36, 41, 43)[slot]
    m.call('bf_response_tick', 2, 0)
    m.call('bf_response_observe', regs={UC_M68K_REG_D7: 1, UC_M68K_REG_D4: 0,
                                      UC_M68K_REG_A2: m.scratch})
    for _ in range(8):
        m.events.clear()
        assert m.change(65) == [(0x91, n, 0) for n in (36, 41, 43)] + [(0x91, n, 91) for n in (41, 45, 48)]
        m.events.clear()
        assert m.change(60) == [(0x91, n, 0) for n in (41, 45, 48)] + [(0x91, n, 91) for n in (36, 41, 43)]
    print('[ok] LIVE chord scale correction, repeated C/F/C changes without pitch drift, native releases')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('remix', nargs='?')
    parser.parse_args()
    main()
