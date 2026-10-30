"""Full-firmware mute regressions, called by the MIDI Follow project gate.

Only virtual copies of the supplied project are used. No emulator code patches:
mute and scale events write native control state, and RFOL uses its encoder.
"""
import hashlib
import json
import re
import subprocess

import verify_midi_follow as follow
import emu_card
from hw import ot_project as otp


def balanced(events):
    held = set()
    for kind, channel, note, _ in events:
        key = channel, note
        if kind == 'on':
            assert key not in held, ('duplicate on', key)
            held.add(key)
        else:
            assert key in held, ('unmatched off', key)
            held.remove(key)
    assert not held, ('stuck notes', held)


def port_gate(image, project, out):
    out.mkdir(parents=True, exist_ok=True)
    receipt = out/'result.json'
    receipt.unlink(missing_ok=True)
    candidate = out/'candidate.bin'
    candidate.write_bytes(image.read_bytes())
    raw = subprocess.check_output(['m68k-elf-nm', str(follow.ROOT/'out/platform/runtime/runtime.elf')], text=True)
    sym = {name: int(addr, 16) for addr, name in
           re.findall(r'^([0-9a-f]+) [TtBb] ((?:bf|mh|ms|ch)_\w+)$', raw, re.M)}
    (out/'symbols.json').write_text(json.dumps(sym, indent=2)+'\n')
    modes = [('plain', 0, False), ('reverse', 7, False), ('arp', 0, True)]
    if 'ms_decode' in sym:
        modes.append(('scales', 0, False))
    if 'mh_sequence' in sym:
        modes.extend([('harmony', 0, False), ('harmony-arp', 0, True)])
    if 'ch_lock_table' in sym:
        modes.insert(0, ('chord-locks', 0, False))
    cases = {}
    for mode, leader, arp in modes:
        work = out/mode
        work.mkdir(exist_ok=True)
        follow.fixture(project, work/'project', arp=arp, leader=leader)
        harmony = mode.startswith('harmony') or mode == 'chord-locks'
        for path in (work/'project').glob('project.*'):
            data = re.sub(rb'^#MIDI_HARMONY[^\r\n]*\r?\n', b'', path.read_bytes(), flags=re.M)
            path.write_bytes(data)
        for path in (work/'project').glob('bank*.work'):
            def setup(data):
                for part in range(8):
                    base = otp.PART_BASE + part*otp.PART_STRIDE + 9
                    for track in range(8):
                        data[base+0x4e2+36*track+17] = 1 if harmony else 0
                        data[base+0x4e2+36*track+5] = (2 if track==leader or (track==1 and mode!='chord-locks') else 0) if harmony else 0
                    if mode == 'scales':
                        data[base+0x4e2+36*leader+17] = 25
                    if harmony and arp:
                        data[base+0x3e2+32+14] = 1
                        data[base+0x3e2+32+15] = 3
                if mode in ('scales', 'chord-locks'):
                    # Out-of-scale roots exercise snapping, not just the UI value.
                    at = 0x492e + leader*0x8b9 + 0x39
                    data[at+2*32] = 64
                    data[at+4*32] = 66
                    data[at+8*32] = 69
            otp._bank_write(work/'project', int(path.stem[4:]), setup, guard=False)
        card, _ = emu_card.stage_project(work/'project', 'OCTABAM', 'BASS', tree=work/'tree')
        (work/'card.img').write_bytes(card)
        source_ch, follower_ch = (13, 5) if leader == 7 else (1, 2)
        control = None
        for state in ('audible', 'source-muted', 'follower-muted', 'mute-unmute'):
            args = ['--step', '-:poke:0x100b14cc=1', '--step',
                    f'-:call:{sym["bf_encoder"]:#x},3,4'] * (leader+1-(leader>1))
            mask = (1 << leader) if state == 'source-muted' else 2 if state == 'follower-muted' else 0
            args += ['--step', f'-:poke:0x8000000e={mask}']
            if state == 'mute-unmute':
                args += ['--step', f'1300:poke:0x8000000e={1 << leader}',
                         '--step', '2500:poke:0x8000000e=0']
            if mode in ('scales', 'chord-locks'):
                # Change source KEY during the mute interval in all controls.
                args += ['--step', f'1600:poke:{0x46c76df1+68*leader:#x}=2;{0x400e21e0+0x8ed80+0x4e2+36*leader+17:#x}=2;{0x100a4ece+0x4e2+36*leader+17:#x}=2']
            if mode == 'chord-locks':
                table = sym['ch_lock_table'] + leader*64
                args += ['--step', f'-:poke:{table+2:#x}=1;{table+4:#x}=5;{table+8:#x}=7']
            capture, log = work/f'{state}.midi', work/f'{state}.log'
            command = [str(follow.ROOT/'out/emu/ot_emu'), '--image', str(candidate),
                       '--card', str(work/'card.img'), '--set', 'OCTABAM', '--project', 'BASS',
                       '--load-ms', '90000', '--mkii', '--sequencer', '--internal-clock',
                       '--frames', '7000', '--midi-out', str(capture), *args]
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=follow.ROOT, stdout=stream, stderr=subprocess.STDOUT)
            assert result.returncode == 0 and 'run ended REACHED' in log.read_text(), log
            events = follow.notes(capture.read_bytes())
            balanced(events)
            channels = {ch: [event for event in events if event[1] == ch]
                        for ch in (source_ch, follower_ch, 3)}
            if control is None:
                control = channels
                assert all(channels.values()), (mode, channels)
            elif state == 'follower-muted':
                assert not channels[follower_ch], (mode, state, channels)
                assert channels[source_ch] == control[source_ch], (mode, state, channels)
            else:
                assert channels[follower_ch] == control[follower_ch], (mode, state, channels, control)
                if state == 'source-muted':
                    assert not channels[source_ch], (mode, state, channels)
                else:
                    assert channels[source_ch] and channels[source_ch] != control[source_ch], (mode, state, channels)
            assert channels[3] == control[3], (mode, state, channels)
            cases[f'{mode}/{state}'] = events
            print(f'  [ok] mute UART {mode}/{state}: output isolation, root progression, balanced releases', flush=True)
    result = dict(status='pass', image_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
                  hardware_tested=False, cases=cases)
    receipt.write_text(json.dumps(result, indent=2)+'\n')
    return result
