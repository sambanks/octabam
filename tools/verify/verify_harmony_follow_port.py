#!/usr/bin/env python3
"""Capture the source/follower HARM matrix through the real sequencer and UART."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import verify_midi_harmony_port as port
import emu_card
from hw import ot_project as otp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('remix', nargs='?')
    parser.add_argument('--project', type=Path, default=os.environ.get('OT_PROJECT') or None)
    args = parser.parse_args()
    if args.project is None:
        print('[SKIP] Harmony/Follow UART matrix: supply --project DIR or OT_PROJECT')
        return
    symbols = port.harmony.symbols()
    if 'bf_encoder' not in symbols:
        print('[SKIP] Follow composition: select MIDI FOLLOW')
        return
    assert 'bf_encoder' in symbols, 'select MIDI FOLLOW'
    has_harmony = 'mh_generate' in symbols
    port.OUT = port.ROOT / 'out' / ('harmony-follow-port' if has_harmony else 'follow-no-harmony-port')
    port.OUT.mkdir(parents=True, exist_ok=True)
    image = port.freeze_candidate(port.OUT)
    modes = (0, 1, 2) if has_harmony else (0,)
    results = {}
    for reverse in (False, True):
        leader = 7 if reverse else 0
        for source_mode in modes:
            for follower_mode in modes:
                name = f'source-{leader + 1}-harm-{source_mode}-follower-{follower_mode}'
                work = port.fixture(args.project, name,
                                    {leader: source_mode, 1: follower_mode},
                                    reverse=reverse, first_note=60,
                                    voicings={leader: 2} if source_mode == 2 else {})
                for path in (work / 'project').glob('bank*.work'):
                    def mutate(data):
                        for part in range(8):
                            base = otp.PART_BASE + part * otp.PART_STRIDE + 9
                            data[base + 0x4e2 + 36 + 17] = 1  # C major before first source trig
                        for pattern in range(16):
                            for track in (leader, 1):
                                at = 0x492e + pattern * 0x8eec + track * 0x8b9
                                for step in range(64):
                                    lock = at + 0x39 + step * 32
                                    data[lock + 3:lock + 6] = bytes((68, 71, 76) if track == leader else (255, 255, 255))
                    otp._bank_write(work / 'project', int(path.stem[4:]), mutate, guard=False)
                card, _ = emu_card.stage_project(work / 'project', 'OCTABAM', 'BASS', tree=work / 'tree')
                (work / 'card.img').write_bytes(card)
                extra = ['--sequencer', '--internal-clock', '--frames', '7000',
                         '--step', '-:poke:0x100b14cc=1']
                for _ in range(leader + 1):
                    extra += ['--step', f'-:call:{symbols["bf_encoder"]:#x},3,4']
                events = port.run(work, 'matrix', extra)
                port.balanced(events)
                lead_ch, follower_ch = (13, 5) if reverse else (1, 2)
                lead = [e[2] for e in events if e[:2] == ('on', lead_ch)]
                follower = [e[2] for e in events if e[:2] == ('on', follower_ch)]
                source_intervals = {0: (0, 4, 7, 12), 1: (0,), 2: (4, 7, 12)}[source_mode]
                expected_source = [root + n for root in (60, 65, 67) for n in source_intervals]
                assert lead == expected_source, (name, 'source', lead, expected_source)
                intervals = (0, 4, 7) if follower_mode == 2 else ((0, 4, 7, 12) if source_mode == follower_mode == 0 else (0,))
                expected = ([48, 52, 55] if follower_mode == 2 else [48])
                expected += [root + n for root in (36, 36, 41, 43, 43) for n in intervals]
                assert follower == expected, (name, 'follower', follower, expected)
                results[name] = dict(source=lead, follower=follower, balanced_releases=True)
                print('[ok]', name, 'source progression and complete follower pitches', flush=True)
    (port.OUT / 'result.json').write_text(json.dumps(dict(
        cases=results, harmony_selected=has_harmony,
        image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        hardware_tested=False), indent=2) + '\n')


if __name__ == '__main__':
    main()
