#!/usr/bin/env python3
"""Harmony-owned LIVE pitch movement, cached arp tones and release records."""
import json
from harmony_midi_machine import Machine, MODES, raw_scale, ROOT
from verify_midi_follow_response import fixture
from unicorn.m68k_const import *


def main():
    m = Machine()
    if 'mh_follow_shift' not in m.sym or 'bf_source_get' not in m.sym:
        print('[SKIP] Harmony LIVE composition: select Harmony and Follow')
        return
    m.follow_write('source', b'\x01', 1)
    m.uc.mem_write(m.part_address(1, 5), b'\x02')
    cases = 0
    scales = [(0, 0, 0)] + [(raw_scale(t, mode), t, mode)
                           for t in range(12) for mode in range(7)
                           if ({'ms_snap', 'sc_track_at'} & m.sym.keys()) or mode in (0, 5)]
    for key, tonic, mode in scales:
        m.set_key(0, key)
        m.set_key(1, 24 if key != 24 else 1)
        members = [n for n in range(-24, 161) if (n-tonic) % 12 in MODES[mode]]
        valid = [n for n in members if 0 <= n <= 127]
        roots = [n for n in valid if 36 <= n <= 60][:4]
        for quality in (0, 5, 6, 7):
            m.uc.mem_write(m.sym['mhc_sequence_quality'] + 1, bytes((quality,)))
            for old, new in ((roots[0], roots[1]), (roots[1], roots[3]), (roots[3], roots[0])):
                for voice in range(128):
                    if not key or quality >= 5:
                        expected = voice + new - old
                    else:
                        snapped = min(valid, key=lambda n: (abs(n-voice), n))
                        index = members.index(snapped) + members.index(new) - members.index(old)
                        expected = members[index]
                    if not 0 <= expected <= 127:
                        expected = 0xffffffff
                    regs = {UC_M68K_REG_D2: new, UC_M68K_REG_D3: 0x12345678,
                            UC_M68K_REG_D4: 0x23456789, UC_M68K_REG_D5: 0x3456789a,
                            UC_M68K_REG_D6: 0x456789ab, UC_M68K_REG_D7: 1,
                            UC_M68K_REG_A0: m.scratch}
                    actual = m.call('mh_follow_shift', voice, old, regs=regs)
                    assert actual == expected, (key, quality, old, new, voice, actual, expected)
                    assert m.uc.reg_read(UC_M68K_REG_D1) == old
                    assert all(m.uc.reg_read(r) == v for r, v in regs.items())
                    assert all(m.stack-256 <= a and a+n <= m.stack+4 for a,n in m.writes)
                    cases += 1
    print(f'[ok] {cases} Harmony LIVE scale-degree/chromatic cases; all MIDI pitches, bounds and preserved registers', flush=True)

    # The regression crosses minor/major thirds in both directions, repeatedly.
    # Execute actual Follow ownership/release code, with only MIDI queue I/O
    # substituted by the established fixture. The native deadline stays 37.
    transitions = []
    for source_mode in range(3):
        for follower_mode in (1, 2):
            tones = (36,) if follower_mode == 1 else (36, 40, 43)
            m = fixture(pitches=tones)
            u = m.uc
            for track, mode in ((0, source_mode), (1, follower_mode)):
                u.mem_write(m.part_address(track, 5), bytes((mode,)))
            m.set_key(0, 1)
            m.call('bf_response_tick', 2, 0)
            m.call('bf_response_observe', regs={UC_M68K_REG_D7: 1, UC_M68K_REG_D4: 0,
                                              UC_M68K_REG_A2: m.scratch})
            previous = list(tones)
            for _ in range(4):
                for pitch, chord in ((62, [38,41,45]), (65,[41,45,48]), (60,[36,40,43])):
                    want = chord[:1] if follower_mode == 1 else chord
                    m.events.clear()
                    events = m.change(pitch)
                    assert events == [(0x91,n,0) for n in previous] + [(0x91,n,91) for n in want], (source_mode, follower_mode, events, want)
                    previous = want
                    # Cached original arp tones follow the same harmonic motion;
                    # only outgoing scratch moves. Original pool anchor stays C.
                    for original, target in zip(tones, want):
                        u.mem_write(m.scratch, bytes((original,)))
                        m.call('bf_response_adjust', regs={UC_M68K_REG_D7: 1, UC_M68K_REG_A2: m.scratch})
                        assert u.mem_read(m.scratch, 1)[0] == target
                    transitions.append((source_mode, follower_mode, pitch, want))
    print('[ok] 72 repeated C/D/F/C held-note transitions and cached arp tones, all source HARM modes, NOTE/CHORD followers, release pitches/deadlines', flush=True)
    (ROOT/'out/harmony-follow-live.json').write_text(json.dumps(dict(
        arithmetic_cases=cases, transitions=transitions, hardware_tested=False), indent=2)+'\n')


if __name__ == '__main__':
    main()
