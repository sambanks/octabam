#!/usr/bin/env python3
"""Full-firmware MIDI capture for a native four-note source and empty receiver slots."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from midi_fixture import fixture, notes
from verify_midi_follow import ROOT, OUT
import emu_card


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    args = parser.parse_args()
    work = OUT / 'native-voices'
    work.mkdir(parents=True, exist_ok=True)
    fixture(args.project, work / 'project', voices=True)
    card, _ = emu_card.stage_project(work / 'project', 'OCTABAM', 'BASS', tree=work / 'tree')
    (work / 'card.img').write_bytes(card)
    image = ROOT / 'out/mainos_bus.bin'
    captures = {}
    for label, firmware in (('stock', ROOT / 'out/raw/section_3_MAIN_OS.bin'), ('patched', image)):
        midi = work / f'{label}.midi'
        cmd = [str(ROOT / 'out/emu/ot_emu'), '--image', str(firmware),
               '--card', str(work / 'card.img'), '--set', 'OCTABAM', '--project', 'BASS',
               '--sequencer', '--internal-clock', '--frames', '7000', '--load-ms', '90000',
               '--midi-out', str(midi)]
        if label == 'patched':
            from verify_midi_follow import symbols
            cmd += ['--step', '-:poke:0x100b14cc=1',
                    '--step', f'-:call:{symbols()["bf_encoder"]:#x},3,4']
        log = work / f'{label}.log'
        with log.open('w') as output:
            run = subprocess.run(cmd, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
        assert run.returncode == 0 and 'run ended REACHED' in log.read_text(), log
        events = notes(midi.read_bytes())
        held = set()
        for kind, channel, pitch, _ in events:
            key = (channel, pitch)
            if kind == 'on':
                assert key not in held, (label, key)
                held.add(key)
            else:
                assert key in held, (label, key)
                held.remove(key)
        assert not held, (label, held)
        captures[label] = [event[2] for event in events if event[:2] == ('on', 2)]
        (work / f'{label}-notes.json').write_text(json.dumps(events, indent=2) + '\n')
    native = captures['stock']
    expected = [native[0], 36, 40, 43, 48, 36, 40, 43, 48,
                41, 45, 48, 53, 43, 47, 50, 55, 43, 47, 50, 55]
    assert len(native) == 6, native
    assert captures['patched'] == expected, captures['patched']
    print('[ok] full firmware: source N1-4 follows into receiver with absent own N2-4; releases balanced')
    print('image_sha256=' + hashlib.sha256(image.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
