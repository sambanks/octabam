#!/usr/bin/env python3
"""Count executed routing instructions, not CPU cycles or hardware latency.

Read a built midi-loopback image and runtime. --build-root can point to a
separate baseline build; the receipt identifies the exact image/runtime bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path

import verify_midi_loopback as lb


class MeasuredMachine(lb.Machine):
    measuring = False

    def stop(self, u, pc, size, data):
        if self.measuring and pc not in self.stops:
            self.counts['instructions'] += 1
            if self.tracked_sr & 0x700 == 0x700:
                self.counts['masked_instructions'] += 1
                self.span += 1
                self.counts['longest_masked_span'] = max(
                    self.counts['longest_masked_span'], self.span)
            else:
                self.span = 0
            # Reading SR from this Unicorn build's hook disturbs lazy flags.
            # Track move-to-SR forms instead; compare state to an unmetered run.
            op = int.from_bytes(u.mem_read(pc, 2), 'big')
            if op & 0xfff8 == 0x46c0:
                self.tracked_sr = u.reg_read(lb.REGS[op & 7]) & 0xffff
            elif op == 0x46fc:
                self.tracked_sr = int.from_bytes(u.mem_read(pc + 2, 2), 'big')
            elif op & 0xffc0 == 0x46c0 or op in (0x007c, 0x027c, 0x0a7c, 0x4e73):
                raise AssertionError(f'unhandled SR write at {pc:08x}: {op:04x}')
        super().stop(u, pc, size, data)


def measure(name, setup, action):
    m = MeasuredMachine()
    setup(m)
    counts = dict(instructions=0, masked_instructions=0, longest_masked_span=0)
    m.counts, m.span, m.measuring, m.tracked_sr = counts, 0, True, 0x2000
    observed = action(m)
    m.measuring = False
    control = lb.Machine()
    setup(control)
    assert observed == action(control), (name, 'return value changed under measurement')
    layout = json.loads((lb.ROOT/'out/platform/layout.json').read_text())
    size = len((lb.ROOT/'out/platform/runtime/runtime.bin').read_bytes())
    for address, length in ((layout['base'], size), (lb.Q, 32), (0x47002000, 4096)):
        assert m.u.mem_read(address, length) == control.u.mem_read(address, length), (
            name, 'state changed under measurement', hex(address))
    return dict(case=name, **counts, instrumented_state_matches_control=True)


def internal(m):
    m.put('lb_routes', 1, 1)


def queued(m):
    internal(m)
    m.capture((0x90, 60, 100))


def channels_changed(m):
    for t in range(8):
        m.put(m.sym['lb_channels'] + t, 0, 1)
        m.put(0x46c76de0 + 68*t, t+1, 1)


def held(m):
    internal(m)
    for n in range(128):
        m.capture((0x90, n, 100))
        assert m.next() == bytes((0x90, n, 100))
    assert m.get('lb_internal_held') == 128


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build-root', type=Path, default=lb.ROOT)
    ap.add_argument('--out', type=Path, default=lb.ROOT/'out/loopback-cost.json')
    args = ap.parse_args()
    lb.ROOT = args.build_root.resolve()
    cases = [
        ('capture_internal_note_empty_queue', internal, lambda m: m.capture((0x90, 60, 100))),
        ('capture_external_note', lambda m: None, lambda m: m.capture((0x90, 60, 100))),
        ('release_internal_note', queued, lambda m: m.capture((0x80, 60, 0), 0x4009f8c2)),
        ('internal_cc', internal, lambda m: m.capture((0xb0, 34, 99), 0x4009fef2)),
        ('sync_no_changes', lambda m: m.u.mem_write(m.sym['lb_channels'], bytes(8)),
         lambda m: m.call('lb_sync')),
        ('dequeue_internal_note', queued, lambda m: m.next()),
        ('flush_empty_track', lambda m: None, lambda m: m.call('lb_flush', (0,))),
        ('change_route_empty_track', lambda m: None, lambda m: m.call('lb_set_route', (0, 1))),
        ('sync_eight_changed_channels_empty_tracks', channels_changed, lambda m: m.call('lb_sync')),
        ('flush_128_internal_held_notes', held, lambda m: m.call('lb_flush', (0,))),
    ]
    report = dict(
        scope='Executed ColdFire instructions including stock queue calls; no RTOS scheduling, '
              'physical UART timing, CPU cycle or audio latency claim.',
        image_sha256=hashlib.sha256((lb.ROOT/'out/mainos_bus.bin').read_bytes()).hexdigest(),
        runtime_sha256=hashlib.sha256((lb.ROOT/'out/platform/runtime/runtime.bin').read_bytes()).hexdigest(),
        cases=[measure(*case) for case in cases],
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
