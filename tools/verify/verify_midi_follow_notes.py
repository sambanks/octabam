#!/usr/bin/env python3
"""Execute the linked Follow note handoff with and without Harmony selected."""
from midi_machine import Machine
from unicorn.m68k_const import UC_M68K_REG_A2, UC_M68K_REG_A5, UC_M68K_REG_A6
from unicorn.m68k_const import UC_M68K_REG_D4, UC_M68K_REG_D7


def notes(machine, source_harm, follower_harm, root=60, offsets=(4, 7, 12), tran=0):
    u, symbols = machine.uc, machine.sym
    source_lane, follower_lane, frame = 0x47002000, 0x47003000, 0x47004000
    source, follower = 0, 1
    machine.follow_write('source', bytes((source + 1,)), follower)
    u.mem_write(machine.part_address(source, 5), bytes((source_harm,)))
    u.mem_write(machine.part_address(follower, 5), bytes((follower_harm,)))
    u.mem_write(symbols['bf_pitches'] + source, bytes((root,)))
    u.mem_write(symbols['bf_roots'] + source, bytes((36 + root % 12,)))
    u.mem_write(source_lane + 0x220, bytes((root, 90, 6, *(64 + n for n in offsets))))
    u.mem_write(source_lane + 0x22c, b'\x40')
    u.mem_write(follower_lane + 0x22c, bytes((64 + tran,)))
    machine.call('bf_latch_extra', regs={UC_M68K_REG_D7: source, UC_M68K_REG_A5: source_lane})
    intervals = bytes(u.mem_read(symbols['bf_intervals'] + source * 3, 3))
    if source_harm:
        assert intervals == bytes((128,)) * 3, intervals
    else:
        assert intervals == bytes(n & 255 for n in offsets), intervals
    u.mem_write(frame - 4, bytes((48, 255, 255, 255)))
    machine.call('bf_seed_extras', regs={UC_M68K_REG_D7: follower,
                                        UC_M68K_REG_A6: frame})
    assert bytes(u.mem_read(frame - 3, 3)) == (
        bytes((255,)) * 3 if source_harm or follower_harm else bytes((48,)) * 3)
    if follower_harm:
        assert machine.call('mh_generate', follower, tran, a0=frame - 4) == 1
    result = []
    for slot in range(4):
        address = frame - 4 + slot
        want_continue = follower_harm or slot == 0 or not source_harm
        machine.call('bf_note', stop=0x4009fb86 if want_continue else 0x4009fd2a,
                     regs={UC_M68K_REG_D7: follower, UC_M68K_REG_D4: slot,
                           UC_M68K_REG_A2: address, UC_M68K_REG_A5: follower_lane,
                           UC_M68K_REG_A6: frame})
        result.append(u.mem_read(address, 1)[0])
    return result


def main():
    m = Machine()
    has_harmony = 'mh_active' in m.sym
    # Native source N1-4, receiver HARM OFF. Default FIXED octave 3.
    assert notes(m, 0, 0) == [36, 40, 43, 48]
    assert notes(m, 0, 0, root=65, offsets=(-5, 3, 7), tran=7) == [48, 43, 51, 55]
    print('[ok] HARM OFF -> OFF: all four effective source notes follow in receiver register')
    if has_harmony:
        # A Harmony source publishes its resolved degree:oct root only.
        assert notes(m, 1, 0, root=62) == [38, 255, 255, 255]
        assert notes(m, 2, 0, root=62) == [38, 255, 255, 255]
        print('[ok] HARM NOTE/CHORD source -> HARM OFF receiver: Note1 only')
        for source_mode in (0, 1, 2):
            for follower_mode in (1, 2):
                result = notes(m, source_mode, follower_mode, root=62)
                assert result[0] == 38, (source_mode, follower_mode, result)
                assert all(p == 38 for p in result) if follower_mode == 1 else len(set(result)) > 1, result
                print('[ok] source HARM', source_mode, '-> follower HARM', follower_mode, result)


if __name__ == '__main__':
    main()
