#!/usr/bin/env python3
"""Check the built MIDI FOLLOW detour; optionally play a copied MIDI project.

Usage: .venv/bin/python3 tools/verify/verify_midi_follow.py midi-follow --project DIR
The local template is only read. Fixtures, UART bytes and logs stay in out/.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402,F401
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE  # noqa: E402
from unicorn.m68k_const import *  # noqa: E402,F403

OUT = ROOT / 'out/midi-follow'
CAPTURE, CAPTURE_END = 0x4009FB00, 0x4009FB08
SITE, CONTINUE, SKIP = 0x4009FB80, 0x4009FB86, 0x4009FD2A
REGS = [UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3,
        UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
        UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3,
        UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6, UC_M68K_REG_A7]


def symbols():
    nm = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {name: int(addr, 16) for addr, name in re.findall(r'^([0-9a-f]+) [TtBb] (bf_\w+)$', nm, re.M)}


def machine_gate(image):
    """Execute the actual build's detour and DRAM bytes, not a Python model."""
    layout = json.loads((ROOT / 'out/platform/layout.json').read_text())
    base = layout['base']
    sym = symbols()
    root = sym['bf_roots']
    entry, capture_entry = sym['bf_note'], sym['bf_capture']
    binary = image.read_bytes()
    assert binary[SITE - 0x40000400:SITE - 0x40000400 + 6] == b'\x4e\xf9' + entry.to_bytes(4, 'big')
    assert binary[CAPTURE - 0x40000400:CAPTURE - 0x40000400 + 6] == b'\x4e\xf9' + capture_entry.to_bytes(4, 'big')
    from midi_machine import Machine
    m = Machine(symbols)
    uc = m.uc
    m.stops = set()  # This gate observes native detour continuation addresses.
    pitch, stack = 0x47001000, 0x47008000
    # Measured deepest call is pre-capture -> register sync -> native Part
    # reader, 224 bytes including return addresses (previous graph: 192).
    stack_budget = 224
    arrivals = []
    unexpected_writes = []
    written_addresses = set()

    def guard_write(u, access, address, size, value, user):
        written_addresses.add(address)
        # Only module state, scratch output, the displaced stock write and
        # a bounded stack frame may change during these machine-code calls.
        allowed = tuple((sym[name],sym[name]+size) for name,size in (('bf_history',128),('bf_response_context',64),('bf_response_anchor',32),('bf_response_seen',32),('bf_response_pool',32),('bf_intervals',24))) + ((root, root + 8), (sym["bf_pitches"], sym["bf_pitches"] + 8), *tuple((m.part_address(t,3),m.part_address(t,3)+1) for t in range(8)),
                   *tuple((0x100a4ece+0x4e2+t*36+3,0x100a4ece+0x4e2+t*36+4) for t in range(8)),
                   (0x400e21e0+0x95048,0x400e21e0+0x95049),
                   (0x400e21e0+0x9b332,0x400e21e0+0x9b336),
                   (0x100b145e,0x100b145f),(0x100f8598,0x100f859c),
                   (pitch, pitch + 4), (stack - stack_budget, stack),
                   (0x47004000 - 43, 0x47004000 - 42))
        if not any(lo <= address and address + size <= hi for lo, hi in allowed):
            unexpected_writes.append((hex(address), size, hex(value)))

    uc.hook_add(UC_HOOK_MEM_WRITE, guard_write)

    done = 0x4700fff0

    def stop(u, address, size, user):
        if address in (CAPTURE_END, CONTINUE, SKIP, 0x4009f98c, 0x4003667a, done):
            arrivals.append(address)
            u.emu_stop()
    uc.hook_add(UC_HOOK_CODE, stop, begin=1, end=0)

    def note(track, slot, value, transpose=64):
        before = [0x12340000 + i for i in range(16)]
        before[4], before[7], before[10], before[15] = slot, track, pitch, stack
        before[13], before[14] = 0x47002000, 0x47004000
        uc.reg_write(UC_M68K_REG_SR, 0x2700)
        for reg, val in zip(REGS, before):
            uc.reg_write(reg, val)
        uc.mem_write(pitch - 1, bytes((0xa5, value, 0x5a)))
        uc.mem_write(before[14] - 4, b'\x30')
        uc.mem_write(before[13] + 0x22c, bytes((transpose,)))
        arrivals.clear()
        uc.emu_start(SITE, 0, count=3000)
        result = uc.mem_read(pitch, 1)[0]
        assert arrivals == [SKIP if result >= 128 else CONTINUE]
        after = [uc.reg_read(reg) for reg in REGS]
        before[1] = (before[1] & ~255) | result  # displaced move.b
        assert after == before, (track, slot, value, before, after)
        assert uc.mem_read(pitch - 1, 3) == bytes((0xa5, result, 0x5a))
        return result

    def capture(track, value, transpose=64, extra=0, scale=0):
        before = [0x12340000 + i for i in range(16)]
        frame, lane = 0x47004000, 0x47002000
        before[7], before[13], before[14], before[15] = track, lane, frame, stack
        uc.reg_write(UC_M68K_REG_SR, 0x2700)
        for reg, val in zip(REGS, before):
            uc.reg_write(reg, val)
        uc.mem_write(lane + 0x220, bytes((value,)))
        uc.mem_write(lane + 0x22c, bytes((transpose,)))
        uc.mem_write(0x46c7a124 + track, bytes((extra & 255,)))
        uc.mem_write(frame - 64, scale.to_bytes(4, 'big'))
        arrivals.clear()
        uc.emu_start(CAPTURE, 0, count=1000)
        assert arrivals == [CAPTURE_END]
        before[4] = track * 4  # displaced stock bookkeeping
        assert [uc.reg_read(reg) for reg in REGS] == before
        assert uc.mem_read(frame - 43, 1)[0] == track * 4
        assert uc.mem_read(lane + 0x220, 1)[0] == value
        return uc.mem_read(root + track, 1)[0]

    def select(track, delta):
        uc.reg_write(UC_M68K_REG_A7, stack)
        uc.reg_write(UC_M68K_REG_D0, track)
        uc.reg_write(UC_M68K_REG_D1, delta & 0xffffffff)
        uc.mem_write(stack, done.to_bytes(4, 'big'))
        arrivals.clear()
        uc.emu_start(sym['bf_select'], 0, count=4000)
        assert arrivals == [done]
        assert uc.reg_read(UC_M68K_REG_A7) == stack + 4
        return m.follow_read('source')

    assert uc.mem_read(root, 8) == b'\xff' * 8
    assert m.follow_read('source') == bytes(8)
    assert capture(0, 60) == 36
    assert note(1, 0, 48) == 48  # OFF is the default
    uc.mem_write(root, b'\xff' * 8)
    assert select(1, 1) == bytes((0, 1, 0, 0, 0, 0, 0, 0))
    assert note(1, 0, 48) == 48  # follower before first leader
    for n in range(128):
        expected = 36 + n % 12
        assert capture(0, n) == expected
        assert note(0, 0, n) == n
        assert uc.mem_read(root, 1)[0] == expected
        assert note(1, 0, 72) == expected
        for slot in (1, 2, 3):
            assert note(0, slot, 76) == 76  # leader chord cannot replace root
            assert note(1, slot, 76) == 255  # bass is monophonic
        for track in range(2, 8):
            assert capture(track, n) == expected
            assert note(track, 0, n) == n
        for track in range(8):
            assert note(track, 0, 255) == 255  # absent/out-of-range note
        assert uc.mem_read(root, 1)[0] == expected
    assert capture(0, 60) == 36
    for arp_note in (60, 64, 67, 64):
        assert note(0, 0, arp_note) == arp_note
        assert note(1, 0, 48) == 36
    assert capture(0, 65) == 41
    for arp_note in (65, 69, 72, 69):
        assert note(0, 0, arp_note) == arp_note
        assert note(1, 0, 48) == 41
    assert capture(0, 60, transpose=66, extra=3) == 41
    assert capture(0, 60, transpose=62, extra=-3) == 43
    assert capture(0, 255) == 43
    assert capture(0, 0, transpose=63) == 43
    assert capture(0, 127, transpose=65) == 43
    assert capture(0, 61, scale=12) == 36  # C# -> C in C major
    assert capture(0, 66, scale=12) == 41  # F# -> F in C major
    assert capture(0, 61, scale=10) == 37  # C# belongs to D major
    assert capture(0, 61, transpose=66, scale=12) == 38  # transpose THEN scale
    # Followers retain signed TRAN, including octave shifts rather than mod 12.
    # Exhaust the normal byte range and reject corrupt/out-of-MIDI results.
    for n in range(12):
        capture(0, 60 + n)
        for offset in range(-64, 64):
            expected = 36 + n + offset
            assert note(1, 0, 72, transpose=64+offset) == (expected if 0 <= expected <= 127 else 255)
        assert note(1, 0, 72, transpose=255) == 255
        assert note(1, 1, 76, transpose=71) == 255
        assert note(1, 0, 255, transpose=71) == 255
        assert note(0, 0, 72, transpose=71) == 72  # RFOL OFF: stock result preserved
    # All 56 source/follower pairs, independent of output MIDI channels.
    for follower in range(8):
        for leader in range(8):
            if follower == leader:
                continue
            m.follow_write('source', bytes(8))
            # Selection skips the follower itself.
            select(follower, leader + 1 - (leader > follower))
            assert m.follow_read('source',1,follower)[0] == leader + 1
            capture(leader, 65)
            assert note(follower, 0, 60) == 41
            select(follower, -8)
            assert note(follower, 0, 60) == 60
    m.follow_write('source', bytes(8))
    select(1, 1)                 # T2 -> T1
    select(2, 2)                 # T3 -> T2 -> T1
    assert select(0, 1)[0] == 4  # T1 cannot choose itself, T2 or T3
    select(0, -1)                # OFF, skipping those same cycles
    capture(0, 67)
    assert note(2, 0, 48) == 43
    assert note(2, 0, 48, transpose=76) == 55  # chain uses destination's offset
    assert select(7, 1000)[7] == 7  # clamps at T7, skips itself
    assert select(7, -1000)[7] == 0
    assert select(99, 1)[7] == 0

    # Real pre-loop hook: T8's root arrives before T2's same-tick note.
    m.follow_write('source', bytes((0, 8, 0, 0, 0, 0, 0, 0)))
    frame = 0x47004000
    def pre_capture(mask=128, mute=0, channel=8, velocity=90, note_value=65, disabled=False, track=7):
        uc.mem_write(frame - 42, mask.to_bytes(4, 'big'))
        uc.mem_write(frame - 37, bytes((mute,)))
        enabled = bytearray(8)
        enabled[track] = 255 if disabled else 0
        uc.mem_write(0x80006676, bytes(enabled))
        uc.mem_write(0x8000666e, bytes(8))
        setup = 0x46c76dc0 + track * 68
        lane = 0x46c76dc0 + track * 32
        uc.mem_write(setup + 32, bytes((channel,)))
        uc.mem_write(setup + 49, bytes((0,)))
        uc.mem_write(lane + 0x220, bytes((note_value, velocity)))
        uc.mem_write(lane + 0x22c, bytes((64,)))
        uc.mem_write(0x46c7a124 + track, bytes((0,)))
        uc.reg_write(UC_M68K_REG_A6, frame)
        uc.reg_write(UC_M68K_REG_A7, stack)
        arrivals.clear()
        before = [uc.reg_read(r) for r in REGS]
        # The composed Harmony path reaches 4,350 instructions in this
        # eight-track fixture; keep a bounded allowance above that path.
        uc.emu_start(0x4009f986, 0, count=5000)
        assert arrivals == [0x4009f98c], ('pre-capture did not finish',hex(uc.reg_read(UC_M68K_REG_PC)))
        before[8] = 0x80006676  # displaced lea
        assert [uc.reg_read(r) for r in REGS] == before
        assert arrivals == [0x4009f98c]
        return uc.mem_read(root + track, 1)[0]
    uc.mem_write(root + 7, b'\xff')
    assert pre_capture(disabled=True) == 255
    assert pre_capture(mask=0) == 255
    assert pre_capture(mute=128, mask=0) == 255
    assert pre_capture(mute=128, disabled=True) == 255
    assert pre_capture(channel=0) == 255
    assert pre_capture(velocity=0) == 255
    assert pre_capture(note_value=255) == 255
    assert pre_capture(mute=128) == 41  # even the first source trig may be muted
    assert note(1, 0, 48) == 41
    assert pre_capture(mute=128, note_value=67) == 43
    assert note(1, 0, 48) == 43
    assert pre_capture(mute=128, mask=0, note_value=60) == 43  # rests still latch
    assert pre_capture(note_value=60) == 36  # unmute does not reset the source
    assert note(1, 0, 48) == 36
    # Every source position uses the same mute-independent root path.
    for track in range(8):
        uc.mem_write(root + track, b'\xff')
        assert pre_capture(track=track, mask=1 << track, mute=255, note_value=65) == 41
        assert pre_capture(track=track, mask=1 << track, mute=255, velocity=0) == 41

    m.follow_write('source', bytes((2, 1, 0, 0, 0, 0, 0, 0)))
    assert note(1, 0, 48) == 48  # bounded even for corrupt cyclic RAM
    m.follow_write('source', b'\xff',1)
    assert note(1, 0, 48) == 48

    for value in range(10):
        uc.reg_write(UC_M68K_REG_A7, stack)
        uc.mem_write(stack, b''.join(v.to_bytes(4, 'big') for v in (done, pitch, value)))
        uc.mem_write(pitch, b'xxxxxxxx')
        arrivals.clear()
        uc.emu_start(sym['bf_format'], 0, count=100)
        assert arrivals == [done]
        expected = f'T{value}' if 1 <= value <= 8 else 'OFF'
        assert bytes(uc.mem_read(pitch, len(expected)+1)) == expected.encode()+b'\0'
    assert {root, m.part_address(1,3), pitch} <= written_addresses, 'memory-write hook did not observe known writes'
    assert not unexpected_writes, ('out-of-contract memory writes', unexpected_writes[:10])
    print('  [ok] machine code: 56 routes, OFF, chains/cycles, 128 roots, all follower TRAN offsets, arp isolation, same-tick muted T8 source, all eight muted sources, gates, note-offs path, formatters, registers, bounded memory writes')


from midi_fixture import fixture, notes


def port_case(image, project, arp=False, leader=0, enabled=True, live_change=None, held_boundary=False, offsets=None):
    name = "off" if not enabled else "reverse-arp" if leader and arp else "reverse" if leader else "arp" if arp else "chords"
    if live_change:
        name = f'live-{live_change}'
    if held_boundary:
        name = 'held-boundary'
    if offsets is not None:
        name = 'offsets-' + name
    work = OUT / name
    work.mkdir(parents=True, exist_ok=True)
    import emu_card
    fixture(project, work / 'project', arp=arp, leader=leader, offsets=offsets)
    card, _ = emu_card.stage_project(work / 'project', 'OCTABAM', 'BASS', tree=work / 'tree')
    (work / 'card.img').write_bytes(card)
    results, hashes = {}, {}
    for label, firmware in [('stock', ROOT / 'out/raw/section_3_MAIN_OS.bin'), ('patched', image)]:
        hashes[label] = hashlib.sha256(firmware.read_bytes()).hexdigest()
        capture = work / f'{label}.midi'
        log = work / f'{label}.log'
        cmd = [str(ROOT / 'out/emu/ot_emu'), '--image', str(firmware),
               '--card', str(work/'card.img'), '--set', 'OCTABAM', '--project', 'BASS',
               '--sequencer', '--internal-clock', '--frames', '1500' if held_boundary else '7000', '--load-ms', '90000',
               '--midi-out', str(capture), '--card-out', str(work/f'{label}-card.img')]
        if label == 'patched' and enabled:
            cmd += ['--step', '-:poke:0x100b14cc=1',
                    '--step', f'-:call:{symbols()["bf_encoder"]:#x},3,4'] * (leader + 1 - (leader > 1))
            if live_change:
                # Use the real encoder callback while the sequencer is playing.
                # +1 skips T2 itself and selects T3; -1 switches RFOL OFF.
                delta = -1 if live_change == 'off' else 1
                cmd += ['--step', f'1500:call:{symbols()["bf_encoder"]:#x},3,{4*delta}',
                        '--step', f'1500:dump:0x100a4ece,25288={work / "sources.bin"}']
        with log.open('w') as f:
            proc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        text = log.read_text()
        assert proc.returncode == 0 and 'run ended REACHED' in text, log
        assert 'load run ended: LOAD PROJECT handled' in text, log
        if label == 'patched' and live_change:
            raw=(work/'sources.bin').read_bytes()
            assert raw[0x4e2+36+3] == (0 if live_change == 'off' else 3)
        events = notes(capture.read_bytes())
        results[label] = events
        (work/f'{label}-notes.json').write_text(json.dumps(events, indent=2)+'\n')
        # Firmware must not write the transformed pitches back to the bank.
        files = emu_card.extract_image((work/f'{label}-card.img').read_bytes())
        for path in (work/'project').glob('bank*.*'):
            key = f'OCTABAM/BASS/{path.name}'
            assert files[key] == path.read_bytes(), key
        held = set()
        for kind, ch, pitch, velocity in events:
            key = ch, pitch
            if kind == 'on':
                assert key not in held, ('duplicate note-on', label, key)
                held.add(key)
            else:
                assert key in held, ('unmatched note-off', label, key)
                held.remove(key)
        if held_boundary:
            # This deliberately truncated run proves the live-change instant
            # falls inside an active bass note, rather than between notes.
            native_first = next(e[2] for e in results['stock'] if e[:2] == ('on', 2)) if label == 'patched' else next(e[2] for e in events if e[:2] == ('on', 2))
            assert (2, 36 if label == 'patched' else native_first) in held, (label, held)
        else:
            assert not held, ('hanging notes', label, held)
    stock, patched = results['stock'], results['patched']
    if held_boundary:
        native_first = next(e[2] for e in stock if e[:2] == ('on', 2))
        assert [e[2] for e in patched if e[:2] == ('on', 2)] == [native_first, 36, 36]
        print('  [ok] port UART: bass C is still held at frame 1500, the live RFOL change boundary')
        return dict(status='pass', intentionally_truncated=True, image_sha256=hashes)
    if not enabled:
        assert stock == patched
        print('  [ok] port UART (OFF): all MIDI events identical to stock')
        return dict(status='pass', image_sha256=hashes)
    leader_ch = 13 if leader == 7 else leader + 1
    bass_ch = 5 if leader == 7 else 2
    for ch in (leader_ch, 3):
        assert [e for e in stock if e[1] == ch] == [e for e in patched if e[1] == ch]
    leader_notes = [e[2] for e in stock if e[:2] == ('on', leader_ch)]
    if arp:
        assert {60, 64, 67, 65, 69, 72, 71, 74} <= set(leader_notes), leader_notes
        # Regression: an E arp note must not turn the next C bass into E.
        e = patched.index(('on', leader_ch, 64, 90+leader))
        next_bass = next(event for event in patched[e+1:] if event[:2] == ('on', bass_ch))
        assert next_bass == ('on', bass_ch, 36, 91), next_bass
    else:
        assert leader_notes == [60, 65, 69, 67]
    assert [e[2] for e in stock if e[:2] == ('on', 3)] == [72, 74, 76]
    bass = [e for e in patched if e[:2] == ('on', bass_ch)]
    first_native = next(e[2] for e in stock if e[:2] == ('on', bass_ch))
    expected = ([first_native, 36, 36, first_native, first_native,
                 first_native + 7, first_native] if live_change == 'off' else
                [first_native, 36, 36, 38, 38, 40] if live_change == 'source' else
                [first_native, 36, 40, 43, 36, 40, 43, 41, 45, 48,
                 43, 47, 50, 43, 47, 50] if arp else
                [first_native, 36, 36, 41, 45, 43, 43])
    if offsets is not None:
        assert not live_change and not arp and not held_boundary
        expected = [first_native, 36 + offsets.get(2, 7),
                    36 + offsets.get(3, 7), 41 + offsets.get(6, 7),
                    45 + offsets.get(6, 7), 43 + offsets.get(8, 7),
                    43 + offsets.get(10, 7)]
        # Prove the fixture's base setting and P-locks are active in stock too.
        stock_expected = []
        for step in (0, 2, 3, 6, 8, 10):
            pitch = 47 + offsets.get(step, 7)
            stock_expected.append(pitch)
            if step == 8:
                stock_expected.append(pitch + 7)
        assert [e[2] for e in stock if e[:2] == ('on', bass_ch)] == stock_expected
    assert [e[2] for e in bass] == expected, bass
    assert all(e[3] == 91 for e in bass)
    # F starts while the old C bass is still held; its release stays C.
    f = patched.index(('on', leader_ch, 65, 90+leader))
    held_pitch = 36 + offsets.get(3, 7) if offsets is not None else 36
    first_follower_f = (first_native if live_change == 'off' else
                        38 if live_change == 'source' else
                        41 + (offsets.get(6, 7) if offsets is not None else 0))
    assert patched.index(('off', bass_ch, held_pitch, 0), f) < patched.index(('on', bass_ch, first_follower_f, 91), f)
    print(f'  [ok] port UART ({work.name}): independent rhythm, C/F/G, same-step order, held-note release, other tracks and stored banks')
    return dict(status='pass', leader_notes=leader_notes, bass_notes=[e[2] for e in bass], image_sha256=hashes)



def panel_gate(image):
    """Use UART1 key/encoder reports, not direct writes to module settings."""
    work = OUT/'ui'
    work.mkdir(exist_ok=True)
    card = OUT/'chords/card.img'
    sym = symbols()
    def script(actions):
        lines, time = [], 100
        for kind, value in actions:
            if kind == 'key':
                lines += [f'{time} key {value} down', f'{time+50} key {value} up']
                time += 250
            elif kind == 'setup':
                lines += [f'{time} key 0x2d down', f'{time+50} key 0x22 down',
                          f'{time+100} key 0x22 up', f'{time+150} key 0x2d up']
                time += 400
            else:
                lines += [f'{time} enc 3 {4*value}']
                time += 250
        return '\n'.join(lines + [f'{time+300} quit'])+'\n'
    open_t2 = [('key', '0x35'), ('key', '0x11'), ('setup', None)]
    # Set two followers, then return to T2 and confirm the displayed selection.
    linked = open_t2 + [('enc', 1), ('key', '0x32'), ('key', '0x12'),
                        ('setup', None), ('enc', 1), ('key', '0x32'),
                        ('key', '0x11'), ('setup', None)]
    # T1 skips self/T2/T3 (cycles), reaches T4, then can return to OFF.
    disabled = linked + [('key', '0x32'), ('key', '0x10'), ('setup', None),
                         ('enc', 1), ('enc', -1), ('key', '0x32'),
                         ('key', '0x11'), ('setup', None), ('enc', -1)]
    baseline = None
    for name, actions, expected in [
            ('baseline', open_t2, bytes(8)),
            ('t2-t1', linked, bytes((0, 1, 1, 0, 0, 0, 0, 0))),
            ('t2-off', disabled, bytes((0, 0, 1, 0, 0, 0, 0, 0))),
            ('fresh-part', open_t2, bytes(8))]:
        events, log = work/f'{name}.txt', work/f'{name}.log'
        events.write_text(script(actions))
        after = work/f'{name}-after.bin'
        state = work/f'{name}-state.bin'
        # Stock working-Part mirror (four Parts, stride 0x18b2), not live lanes.
        cmd = [str(ROOT/'out/emu/ot_emu'), '--image', str(image), '--card', str(card),
               '--set', 'OCTABAM', '--project', 'BASS', '--load-ms', '90000', '--mkii',
               '--live-script', str(events), '--lcd', str(work/f'{name}.lcd'),
               '--mem-dump', f'0x100b14cf,1={state};0x100a4ece,25288={after}']
        with log.open('w') as f:
            proc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        assert proc.returncode == 0 and 'ended on quit' in log.read_text(), log
        part=state.read_bytes()[0]
        raw=after.read_bytes()
        actual=bytes(raw[part*0x18b2+0x4e2+t*36+3] for t in range(8))
        assert actual == expected, (name,actual)
        if baseline is None:baseline=raw
        allowed={part*0x18b2+0x4e2+t*36+3 for t in range(8)}
        assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(baseline,raw))), (name,'unrelated native Part byte changed')
        subprocess.run([sys.executable, str(ROOT/'tools/emu/lcd_view.py'),
                        str(work/f'{name}.lcd'), '--png', str(work/f'{name}.png')], check=True)
    print('  [ok] UART panel: RFOL selection, shared source, track reopening, OFF, fresh-project defaults; only native RFOL bytes change')


def port_gate(image, project):
    (OUT/'result.json').unlink(missing_ok=True)
    cases = {name: port_case(image, project, arp=arp)
             for name, arp in [('chords', False), ('arp', True)]}
    cases['reverse'] = port_case(image, project, leader=7)
    cases['reverse-arp'] = port_case(image, project, arp=True, leader=7)
    cases['off'] = port_case(image, project, enabled=False)
    cases['held-boundary'] = port_case(image, project, held_boundary=True)
    cases['live-off'] = port_case(image, project, live_change='off')
    cases['live-source'] = port_case(image, project, live_change='source')
    # +7 on the whole track, with 0/+12/-12 P-locks and a held +12 note
    # spanning the leader's C -> F change. Step 10 proves return to base +7.
    offsets = {2: 0, 3: 12, 6: -12, 8: 12}
    cases['offsets'] = port_case(image, project, offsets=offsets)
    cases['offsets-reverse'] = port_case(image, project, leader=7, offsets=offsets)
    cases['offsets-off'] = port_case(image, project, enabled=False, offsets=offsets)
    panel_gate(image)
    from verify_midi_follow_mute import port_gate as mute_gate
    cases['mute'] = mute_gate(image, project, OUT/'mute')
    (OUT/'result.json').write_text(json.dumps(dict(status='pass', cases=cases,
                                                  hardware_tested=False), indent=2)+'\n')


def main():
    global OUT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix', nargs='?', default='midi-follow')
    ap.add_argument('--mute-only', action='store_true', help='run only linked checks and mute UART regressions')
    ap.add_argument('--project', default=os.environ.get('OT_PROJECT') or None)
    a = ap.parse_args()
    if a.remix != 'midi-follow':
        OUT = ROOT/'out'/f'{a.remix}-midi-follow'
    OUT.mkdir(parents=True, exist_ok=True)
    image = ROOT/'out/mainos_bus.bin'
    machine_gate(image)
    if a.project:
        if a.mute_only:
            from verify_midi_follow_mute import port_gate as mute_gate
            mute_gate(image, pathlib.Path(a.project).expanduser(), OUT/'mute')
        else:
            port_gate(image, pathlib.Path(a.project).expanduser())
    else:
        print('  [SKIP] port project test: supply --project DIR or OT_PROJECT (source is only read)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
