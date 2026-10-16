#!/usr/bin/env python3
"""Measure stock 1.40C project-load compatibility on a disposable virtual card.

Requires the user's firmware and a local project. Publishes no firmware/project
bytes. Exercises the firmware's own load and SAVE PROJECT, not a Python clamp.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402
import ab_fixture  # noqa: E402
import emu_card  # noqa: E402
from hw import ot_project as otp  # noqa: E402

FIELD = 17
LIMIT = 84
STOCK_LIMIT = 24
NAME = 'midi-scales'
BANK = 0x400e21e0
STRIDE = 0x9b340
PART = 0x18b2


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', type=Path, required=True)
    args = ap.parse_args()
    out = ROOT / 'out' / (NAME + '-stock')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'receipt.json').unlink(missing_ok=True)
    project = out / 'project'
    ab_fixture.prepare(args.project, project)
    for f in project.glob('project.*'):
        data = re.sub(rb'\[SAMPLE\].*?\[/SAMPLE\]\r?\n', b'', f.read_bytes(), flags=re.S)
        f.write_bytes(data)
    banks = sorted(int(p.stem[4:]) for p in project.glob('bank*.work'))
    assert banks == list(range(1, 17)), 'a complete 16-bank fixture is required'
    def value(bank, part, track):
        if bank == 1:
            return (0, 1, 24, 25, 26, 35, 84, 255)[track]
        return ((bank - 2) * 32 + (part % 4) * 8 + track) % 256
    for bank in banks:
        def seed(data):
            for part in range(8):
                for track in range(8):
                    at = otp.PART_BASE + part * otp.PART_STRIDE + 9 + 0x4e2 + track * 36
                    data[at + FIELD] = value(bank, part, track)
        otp._bank_write(project, bank, seed, guard=False)
    card, _ = emu_card.stage_project(project, 'OCTABAM', 'CHECK', tree=out / 'tree')
    (out / 'seed.img').write_bytes(card)
    # Dismiss a date prompt, open PROJECT, choose SAVE PROJECT and confirm.
    script = ''
    for at, code in [(100, 0x32), (1500, 0x1c), (2500, 0x21),
                     (3200, 0x20), (3900, 0x31), (4600, 0x31)]:
        script += f'{at} key {code:#x} down\n{at + 80} key {code:#x} up\n'
    script += '40000 quit\n'
    (out / 'save.txt').write_text(script)
    candidate = out / 'candidate.bin'
    candidate.write_bytes((ROOT / 'out/mainos_bus.bin').read_bytes())
    stock = ROOT / 'out/raw/section_3_MAIN_OS.bin'
    runs = []
    for label, image, source, limit in [
        ('candidate', candidate, out / 'seed.img', LIMIT),
        ('stock', stock, out / 'candidate-card.img', STOCK_LIMIT),
        ('return', candidate, out / 'stock-card.img', LIMIT),
    ]:
        dump = out / (label + '-banks.bin')
        input_files = emu_card.extract_image(source.read_bytes())
        cmd = [str(ROOT / 'out/emu/ot_emu'), '--image', str(image),
               '--card', str(source), '--set', 'OCTABAM', '--project', 'CHECK',
               '--load-ms', '90000', '--mkii', '--live-script', str(out / 'save.txt'),
               '--mem-dump', f'{BANK:#x},{16 * STRIDE}={dump}',
               '--card-out', str(out / (label + '-card.img'))]
        with (out / (label + '.log')).open('w') as log:
            result = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        assert result.returncode == 0, (label, result.returncode)
        assert 'ended on quit' in (out / (label + '.log')).read_text(), label
        memory = dump.read_bytes()
        files = emu_card.extract_image((out / (label + '-card.img')).read_bytes())
        checks = 0
        for bank in banks:
            for part in range(4):
                for track in range(8):
                    pos = otp.PART_BASE + part * otp.PART_STRIDE + 9 + 0x4e2 + track * 36 + FIELD
                    previous = input_files[f'OCTABAM/CHECK/bank{bank:02d}.work'][pos]
                    expected = min(previous, limit)
                    at = (bank - 1) * STRIDE + 0x8ed80 + part * PART + 0x4e2 + track * 36 + FIELD
                    assert memory[at] == expected, (label, 'RAM', bank, part, track, memory[at], expected)
                    for suffix in ('work', 'strd'):
                        data = files[f'OCTABAM/CHECK/bank{bank:02d}.{suffix}']
                        pos = otp.PART_BASE + part * otp.PART_STRIDE + 9 + 0x4e2 + track * 36 + FIELD
                        # SAVE PROJECT writes the current bank. Loading a different
                        # bank's values does not by itself dirty its disk file.
                        disk_expected = expected if bank == 1 else input_files.get(f'OCTABAM/CHECK/bank{bank:02d}.{suffix}', input_files[f'OCTABAM/CHECK/bank{bank:02d}.work'])[pos]
                        assert data[pos] == disk_expected, (label, suffix, bank, part, track, data[pos], disk_expected)
                    checks += 1
        runs.append({'stage': label, 'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                     'working_part_fields_checked': checks, 'load_clamp_maximum': limit, 'saved_bank': 1})
        print(f'[ok] {label}: 16 banks x 4 Parts x 8 tracks, RAM, current-bank work/strd save and unchanged other bank files', flush=True)
    receipt = {'status': 'pass', 'field': FIELD, 'input_values': 'all bytes 0..255',
               'candidate_max': LIMIT, 'stock_max': STOCK_LIMIT, 'runs': runs,
               'hardware_tested': False,
               'scope': 'SAVE PROJECT writes the current bank; unvisited bank files are unchanged. Cold disk load and native save; retained-memory startup and physical hardware not qualified.'}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
