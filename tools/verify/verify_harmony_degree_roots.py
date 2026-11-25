#!/usr/bin/env python3
"""Execute pattern representation and boundary policy as real ColdFire code.

Independent musical oracles and byte comparisons cover context replacement,
mixed Parts, invalid publication, native edits and every scale/tonic. This is
a component gate; it does not claim native-hook, file or hardware acceptance.
"""
from harmony_midi_machine import HARMONY_SOURCE
import json
import pathlib
import re
import subprocess
import tempfile

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import *
from verify_harmony_degree_codec import MODES

ROOT = pathlib.Path(__file__).resolve().parents[2]
SIZE = 131
NONE = 255


def encode(note, scale):
    if note == NONE:
        return NONE
    mode, key = scale >> 6, (scale >> 2) & 15
    valid = [n for n in range(128) if (n-key) % 12 in MODES[mode]]
    pitch = min(valid, key=lambda n: (abs(note-n), n))
    octave, semitone = divmod(pitch-key, 12)
    return (octave+1)*7 + MODES[mode].index(semitone)


def decode(code, scale):
    mode, key = scale >> 6, (scale >> 2) & 15
    octave, degree = divmod(code, 7)
    return max(0, min(127, 12*(octave-1)+key+MODES[mode][degree]))


def main():
    subprocess.run(['python3', str(HARMONY_SOURCE/'generate.py'), '--check'], check=True)
    with tempfile.TemporaryDirectory(prefix='harmony-degree-roots-') as tmp:
        out = pathlib.Path(tmp)
        objects = []
        for unit in ('codec', 'roots'):
            obj = out/f'{unit}.o'
            subprocess.run(['m68k-elf-as', '-mcpu=54455', '-o', str(obj),
                            str(HARMONY_SOURCE/f'{unit}.s')], check=True)
            objects.append(str(obj))
        subprocess.run(['m68k-elf-ld', '-Ttext=0x47000000', '-e', 'hd_roots_reset_c',
                        '-o', str(out/'roots.elf'), *objects], check=True)
        subprocess.run(['m68k-elf-objcopy', '-O', 'binary', str(out/'roots.elf'), str(out/'roots.bin')], check=True)
        nm = subprocess.check_output(['m68k-elf-nm', str(out/'roots.elf')], text=True)
        sym = {n: int(a, 16) for a, n in re.findall(r'^([0-9a-f]+) [Tt] (hd_\w+)$', nm, re.M)}
        u = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        u.mem_map(0x47000000, 0x100000)
        u.mem_write(0x47000000, (out/'roots.bin').read_bytes())
        stack, done = 0x470f0000, 0x470ffff0
        reached = []
        def stop(u, pc, size, data):
            if pc == done:
                reached.append(True)
                u.emu_stop()
        u.hook_add(UC_HOOK_CODE, stop)
        def call(name, *args):
            reached.clear()
            u.reg_write(UC_M68K_REG_SR, 0x2000)
            u.reg_write(UC_M68K_REG_A7, stack)
            u.mem_write(stack, b''.join((v & 0xffffffff).to_bytes(4, 'big') for v in (done, *args)))
            saved = (UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4,
                     UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7,
                     UC_M68K_REG_A2, UC_M68K_REG_A3, UC_M68K_REG_A4,
                     UC_M68K_REG_A5, UC_M68K_REG_A6)
            for reg in saved:
                u.reg_write(reg, 0x12345678)
            u.emu_start(sym[name], 0, count=200000)
            assert reached, (name, args, hex(u.reg_read(UC_M68K_REG_PC)))
            for reg in saved:
                assert u.reg_read(reg) == 0x12345678, (name, reg)
            assert u.reg_read(UC_M68K_REG_A7) == stack+4, name
            assert u.reg_read(UC_M68K_REG_SR) & 0xff00 == 0x2000, name
            result = u.reg_read(UC_M68K_REG_D0)
            return result if result < 0x80000000 else result-0x100000000
        root, native, output = 0x47020000, 0x47030000, 0x47030100
        def read(address, n=SIZE):
            return bytes(u.mem_read(address, n))
        def reset(address=root):
            u.mem_write(address-4, b'\xa5'*(SIZE+8))
            call('hd_roots_reset_c', address)
            assert read(address-4, 4) == read(address+SIZE, 4) == b'\xa5'*4
            assert call('hd_roots_valid_c', address) == 1
        def sync(notes, harm, scale, context=0, address=root):
            u.mem_write(native, bytes(notes))
            u.mem_write(output, b'\xa5'*64)
            changed = call('hd_roots_sync_c', address, native, output, harm, scale, context)
            assert changed >= 0
            assert read(native, 64) == bytes(notes), 'input modified'
            assert call('hd_roots_valid_c', address) == 1
            return read(output, 64), changed

        cmin, dmin, emin = 320, 328, 336
        notes = bytes([48, 50, 53, NONE]*16)
        reset()
        assert sync(notes, 2, cmin)[0] == notes
        assert read(root, 4) == bytes([35, 36, 38, NONE])
        # HARM->HARM changes key, retaining every lock and unlocked sentinel.
        roots = read(root, 64)
        assert sync(notes, 1, dmin, 1)[0] == notes
        assert read(root, 64) == roots
        # Same-slot replacement: detach C-minor provenance before D-minor OFF
        # overwrites the physical Part. Incoming key must not turn C3 into D3.
        reset()
        sync(notes, 2, cmin, 3)
        assert call('hd_roots_detach_c', root, 3, cmin) == 1
        outgoing = read(root)
        assert outgoing[130] == NONE
        assert call('hd_roots_detach_c', root, 3, dmin) == 0
        assert read(root) == outgoing, 'reusing a detached slot corrupted its old scale'
        result, changed = sync(notes, 0, dmin, 3)
        assert result == notes and changed == 0
        assert result[0] == 48 and result[3] == NONE
        # Last outgoing KEY edit counts even if no trig occurred afterward.
        reset()
        sync(notes, 2, cmin, 0)
        call('hd_roots_detach_c', root, 0, emin)
        result, changed = sync(notes, 0, dmin, 1)
        assert result == bytes([52, 54, 57, NONE]*16) and changed == 48
        # OFF is pitch-absolute. Enabling HARM under a new KEY re-encodes;
        # there is no retained playable degree to resurrect in stock mode.
        off_notes = bytes([50, NONE]*32)
        reset()
        sync(off_notes, 0, cmin)
        assert sync(off_notes, 0, emin)[0] == off_notes
        sync(off_notes, 1, emin)
        assert read(root, 2) == bytes([34, NONE])  # D3 is E-minor degree 7:2
        assert sync(off_notes, 0, cmin)[0] == off_notes
        # Native editing, clearing and replacing an identical pitch must not
        # retain a removed root's earlier degree identity.
        reset()
        sync(notes, 2, cmin)
        edited = bytearray(notes)
        edited[0] = 55
        sync(edited, 2, cmin)
        assert read(root, 1) == b'\x27'  # degree 5:3
        edited[0] = NONE
        sync(edited, 2, dmin)
        assert read(root, 1) == b'\xff'
        edited[0] = 48
        sync(edited, 2, dmin)
        assert read(root, 1)[0] == 34
        # Each pattern/track retains independent state, even when inactive
        # patterns name the same recyclable physical Part slot.
        lanes = 16*8
        for lane in range(lanes):
            address = root+lane*256
            reset(address)
            sync(notes, lane % 3, cmin, lane % 64, address)
        before = read(root, lanes*256)
        call('hd_roots_detach_c', root+7*256, 7, emin)
        after = read(root, lanes*256)
        assert before[:7*256] == after[:7*256]
        assert before[7*256+SIZE:] == after[7*256+SIZE:]
        # All 84 musical scales: independently derived entry degrees and
        # outgoing root pitches, including both MIDI bounds and tie-down.
        scale_cases = 0
        scale_notes = bytes([0, 1, 12, 47, 48, 49, 60, 126, 127, NONE]*6+[48, NONE, 127, 0])
        for mode in range(7):
            for tonic in range(12):
                scale = mode*64+tonic*4
                reset()
                mirrored, _ = sync(scale_notes, 2, scale, 63)
                expected_degrees = bytes(encode(n, scale) for n in scale_notes)
                assert read(root, 64) == expected_degrees
                outgoing_scale = mode*64+((tonic+7) % 12)*4
                call('hd_roots_detach_c', root, 63, outgoing_scale)
                result, changed = sync(mirrored, 0, (mode*64+((tonic+2) % 12)*4), 1)
                expected = bytes(NONE if d == NONE else decode(d, outgoing_scale) for d in expected_degrees)
                assert result == expected, (mode, tonic, result, expected)
                assert changed == sum(a != b for a, b in zip(mirrored, expected))
                scale_cases += 1
        # Explicit degrees can lie outside MIDI even when their native edit
        # snapshot is a valid pitch. Every degree must clamp only at OFF;
        # HARM->HARM must preserve even currently silent out-of-range roots.
        explicit_cases = 0
        for mode in range(7):
            for tonic in range(12):
                scale = mode*64+tonic*4
                for first in (0, 64):
                    codes = list(range(first, min(first+64, 84)))
                    count = len(codes)
                    encoded = bytes(codes+[NONE]*(64-count))
                    snapshots = bytes([48]*count+[NONE]*(64-count))
                    state = encoded+snapshots+bytes([2, mode*12+tonic, 0])
                    u.mem_write(root, state)
                    mirrored, _ = sync(snapshots, 1, scale, 0)
                    assert read(root, 64) == encoded
                    result, _ = sync(mirrored, 0, 0, 1)
                    assert result == bytes([decode(code, scale) for code in codes]+[NONE]*(64-count))
                    explicit_cases += count
        # Every physical NOTE under every KEY becomes a canonical mirror,
        # while its musical degree and subsequent outgoing pitch are exact.
        native_cases = 0
        for mode in range(7):
            for tonic in range(12):
                scale = mode*64+tonic*4
                for first in (0, 64):
                    reset()
                    notes_in = bytes(range(first,first+64))
                    canonical, _ = sync(notes_in, 2, scale)
                    degrees = bytes(encode(n,scale) for n in notes_in)
                    assert read(root,64) == degrees
                    assert canonical == bytes(decode(d,0) for d in degrees)
                    assert read(root+64,64) == canonical
                    assert sync(canonical,0,scale)[0] == bytes(decode(d,scale) for d in degrees)
                    native_cases += 64
        # Corrupt companions and invalid inputs fail before any publication.
        reset()
        sync(notes, 2, cmin)
        valid = read(root)
        invalid_cases = 0
        for offset, value in ((0, 84), (0, NONE), (64, 128), (64, NONE),
                              (128, 3), (128, 1), (129, 84), (130, 64)):
            broken = bytearray(valid)
            broken[offset] = value
            u.mem_write(root, bytes(broken))
            assert call('hd_roots_valid_c', root) == 0
            u.mem_write(output, b'\xa5'*64)
            assert call('hd_roots_sync_c', root, native, output, 2, cmin, 0) == -1
            assert read(root) == bytes(broken) and read(output, 64) == b'\xa5'*64
            invalid_cases += 1
        u.mem_write(root, valid)
        for harm, scale, context in ((3, cmin, 0), (2, 1, 0), (2, 48, 0), (2, 448, 0), (2, cmin, 64)):
            assert call('hd_roots_sync_c', root, native, output, harm, scale, context) == -1
            assert read(root) == valid and read(output, 64) == b'\xa5'*64
            invalid_cases += 1
        for value in (128, 254):
            u.mem_write(native+63, bytes([value]))
            assert call('hd_roots_sync_c', root, native, output, 2, cmin, 0) == -1
            assert read(root) == valid and read(output, 64) == b'\xa5'*64
            invalid_cases += 1
        print(json.dumps({'scale_cases': scale_cases, 'explicit_degree_boundaries': explicit_cases,
                          'physical_note_key_combinations': native_cases,
                          'independent_pattern_tracks': lanes,
                          'roots_per_case': 64, 'invalid_publications_rejected': invalid_cases,
                          'same_slot_c3_boundary': 'passed', 'abi_registers_and_stack': 'passed',
                          'evidence': 'ColdFire component', 'hardware_tested': False}))


if __name__ == '__main__':
    main()
