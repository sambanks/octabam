#!/usr/bin/env python3
"""Pin event selection before claims/linking, and reject ambiguous registrations."""
from dataclasses import replace
from itertools import combinations
from pathlib import Path
import os
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath
from remix import registry
from verify_system_events import Fixture
import tempfile


def main():
    ns = runpy.run_path(str(ROOT / 'modules/events/manifest.py'))
    select = ns['select']
    original = ns['CLIENTS']
    events = tuple(ns['HOOKS'])
    cases = 0
    # Every subset independently controls both declared claims and generated
    # entry points, including edit-only, MIDI-only and mixed subscriptions.
    with tempfile.TemporaryDirectory(prefix='octabam-events-selection-') as td:
        for n in range(len(events) + 1):
            for subset in combinations(events, n):
                clients = {family: [] for family in ns['FAMILIES']}
                for family in clients:
                    handled = tuple(event for fam, event in subset if fam == family)
                    if handled:
                        clients[family] = [('SYNTHETIC', f'probe_{family}', handled)]
                select.__globals__['CLIENTS'] = clients
                selected = select({'SYNTHETIC'})
                expected = tuple(d for event in events if event in subset for d in ns['HOOKS'][event])
                assert selected['detours'] == expected
                assert {u.label for u in selected['linked']} == {d.unit for d in expected}
                assert select(set()) == {'linked': (), 'detours': ()}
                for slug in ('sequencer', 'edit'):
                    handled = tuple('midi_' + e if fam == 'midi' else e for fam, e in subset
                                    if (fam == 'edit') == (slug == 'edit'))
                    f = Fixture(slug, 1, Path(td), handled=handled)
                    for event, hooks in ns['HOOKS'].items():
                        if (event[0] == 'edit') != (slug == 'edit'):
                            continue
                        for d in hooks:
                            assert (d.symbol in f.production_symbols) == (event in subset), (subset, d.symbol)
                cases += 1
    # A larger fanout catches short-branch range assumptions and stack growth.
    with tempfile.TemporaryDirectory(prefix='octabam-events-fanout-') as td:
        f = Fixture('sequencer', 16, Path(td), handled=('midi_note_accepted',))
        f.uc.mem_write(0x46c77b1e, b'\x01')
        f.uc.mem_write(0x400d807c, bytes((0x90, 61, 93)))
        f.call('seq_sent_a', 0x4009fbb8, values={7: 0})
        assert f.log == [(i, 'midi_note_accepted', (0, 1, 93, 61)) for i in range(16)]
        f.preserved({1: 0xffffff90})
    # Malformed registrations fail even if that module is not selected.
    invalid = [
        {'transport': [('X', 'x', ('typo',))], 'midi': (), 'edit': ()},
        {'transport': [('X', 'x', ('start', 'start'))], 'midi': (), 'edit': ()},
        {'transport': [('X', 'x', ('start',)), ('X', 'y', ('resume',))], 'midi': (), 'edit': ()},
        {'transport': [('X', 'bad prefix', ('start',))], 'midi': (), 'edit': ()},
        {'transport': [('X', 'x', ())], 'midi': (), 'edit': ()},
        {'transport': [('X', 'x', ('start',)), ('Y', 'x', ('start',))], 'midi': (), 'edit': ()},
        {'transport': (), 'edit': ()},
    ]
    for clients in invalid:
        select.__globals__['CLIENTS'] = clients
        try:
            select(set())
        except ValueError:
            pass
        else:
            raise AssertionError(clients)
    select.__globals__['CLIENTS'] = original
    # Exercise the registry's actual bound selection, not only the helper.
    for remix, count in (('events-empty', 0), ('euclid', 2), ('plocks-p2', 23), ('octabam', 23), ('events-clients', 25), ('midi-follow', 4), ('midi-follow-events', 27)):
        selected = {m.key: m for m in registry.selected(registry.remix(remix))}
        assert len(selected['EVENTS'].detours) == count, remix
        assert selected['EVENTS'].select is not None
    # The official octabam remix does not carry EUCLID. Keep the combined-client binding
    # assertion independent of that production remix's effect selection.
    euclid = registry.remix('euclid')
    combined = replace(euclid, modules=euclid.modules + ('SCENES P2', 'STORE', 'PLOCKS P2'))
    selected = {m.key: m for m in registry.selected(combined)}
    assert len(selected['EVENTS'].detours) == 25, 'EUCLID + PLOCKS P2'
    r = registry.remix('events-empty')
    old = registry.modules()['EVENTS']
    try:
        registry.modules()['EVENTS'] = replace(old, select=lambda keys: {'key': 'WRONG'})
        try:
            registry.bound(r)
        except ValueError:
            pass
        else:
            raise AssertionError('selection changed module identity')
    finally:
        registry.modules()['EVENTS'] = old
    # The boot verifier must use the bound units, even when out/platform still
    # contains a previous remix's runtime. Empty EVENTS has nothing to load.
    boot = subprocess.run([sys.executable, str(ROOT / 'tools/verify/verify_dram_boot.py')],
                          env=dict(os.environ, REMIX='events-empty'),
                          capture_output=True, text=True, check=True)
    assert 'carries no DRAM payload' in boot.stdout, boot.stdout
    print(f'[ok] {cases} event subsets: exact hooks and assembled entries, empty/real selections; {len(invalid)} invalid registrations refused')


if __name__ == '__main__':
    main()
