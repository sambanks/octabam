#!/usr/bin/env python3
"""DRUMMER under the port, on the panel: T1 (a plain FLEX track) -> FUNC+SRC -> the last machine row
(DRUMMER) -> YES, then NO, SRC (the LIVE page), FUNC+SRC (the CONFIG page). Each run ends on one screen
(PNG beside it, lcd_view.py) and dumps the Part (T1 signed DR,1 and the twelve defaults).
Paths are this worktree's; the card is probe_slices.py's (out/drummer/slices/card.img), the image
out/drummer/drummer_4b.bin."""
import subprocess, sys, pathlib, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'out/drummer/ui'
OUT.mkdir(parents=True, exist_ok=True)
def key(code, gap=.6, hold=.3): return [(gap, f"key {code:#x} down"), (hold, f"key {code:#x} up")]
base = key(0x10) + [(.6, 'key 0x2d down'), (.3, 'key 0x22 down'), (.3, 'key 0x22 up'), (.3, 'key 0x2d up')]
for _ in range(6): base += key(0x20, .25, .25)
scripts = {
    '1_list': base + [(1.0, 'quit')],
    '2_config': base + key(0x31) + [(1.5, 'quit')],
    '3_live': base + key(0x31) + key(0x32) + key(0x22) + [(1.5, 'quit')],
    '4_config_again': base + key(0x31) + key(0x32) + key(0x22) + [(.6, 'key 0x2d down'), (.3, 'key 0x22 down'), (.3, 'key 0x22 up'), (.3, 'key 0x2d up'), (1.5, 'quit')],
}
def run(name):
    t, lines = 0.0, []
    for d, ev in scripts[name]:
        t += d; lines.append(f"{int(t*1000)} {ev}")
    sf = OUT / f'{name}.script'; sf.write_text("\n".join(lines) + "\n")
    lcd = OUT / f'{name}.lcd'
    cmd = [str(ROOT/'out/emu/ot_emu'), '--image', str(ROOT/'out/drummer/drummer_4b.bin'), '--card', str(ROOT/'out/drummer/slices/card.img'),
           '--set', 'OCTABAM', '--project', 'RIG', '--load-ms', '20000', '--lcd', str(lcd), '--live-script', str(sf),
           '--mem-dump', f'0x40170f60,6322={OUT}/{name}_part.bin']
    with open(OUT/f'{name}.log', 'w') as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=1500)
    subprocess.run([str(ROOT/'.venv/bin/python3'), str(ROOT/'tools/emu/lcd_view.py'), str(lcd), '--png', str(OUT/f'{name}.png')], cwd=ROOT)
    return name, r.returncode
with cf.ThreadPoolExecutor(4) as ex:
    for name, rc in ex.map(run, scripts): print(name, rc)
