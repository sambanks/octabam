#!/usr/bin/env python3
"""MIDI SEQ panel edits, confirmation and destination isolation under the port."""
from verify_seq_scenarios import (
    ROOT, IMAGE, CARD, MenuPort, SeqPort, ensure_card, local_sym,
    DBPTR_ADDR, UI_PTN, PTN_STR, DIALOG_OPEN, u8,
)


def main():
    ensure_card()
    failures = []

    def check(name, ok, detail=''):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f': {detail}' if detail else ''), flush=True)
        if not ok:
            failures.append(name)

    with MenuPort(IMAGE, CARD, 'OCTABAM', 'A', mkii=True) as p:
        p.settle()
        if not p.long(0x80000012):
            p.press('midi', settle=300)
        track = 1  # T2 catches accidentally using track zero or the wrong stride.
        pattern = p.long(DBPTR_ADDR) + u8(p, UI_PTN) * PTN_STR
        mirror = 0x1001614e + u8(p, UI_PTN) * PTN_STR
        size = PTN_STR * 2
        assert u8(p, UI_PTN) < 15
        for t in range(8):
            record = pattern + 0x48d0 + t * 0x8b0
            p.poke(record, (0x100001111).to_bytes(8, 'big'))
            p.poke(record + 0x28, b'\x10')
            locks = bytearray(p.peek(record + 0x30, 2048))
            for step in range(64):
                for flat in range(30):
                    locks[step * 32 + flat] = 20 + (t * 7 + flat * 3 + step * 5) % 90
            p.poke(record + 0x30, locks)
        p.poke(mirror, p.peek(pattern, size))
        s = SeqPort(p)
        s.open_seq('t2')
        record_offset = 0x48d0 + track * 0x8b0
        record = pattern + record_offset

        def knob(encoder, delta):
            p.proc.command(f'knob {0x30 + encoder:#x} {delta}', 'ok')
            p.run(300)

        def field(name):
            return p.long(local_sym(name))

        def snapshots():
            return p.peek(pattern, size), p.peek(mirror, size)

        def unchanged(name, before):
            after = snapshots()
            check(name, before == after)

        def isolated(name, before, flat, trig):
            after = snapshots()
            allowed = {record_offset + 0x30 + step * 32 + flat for step in range(16)}
            if trig:
                allowed.update(range(record_offset, record_offset + 8))
            for tag, old, new in zip(('RAM', 'CS1'), before, after):
                bad = [i for i, (a, b) in enumerate(zip(old, new)) if a != b and i not in allowed]
                check(f'{name}: {tag} preserves all 29 other destinations, other tracks and next pattern',
                      not bad, f'unexpected offsets={bad[:12]}' if bad else '')
            check(f'{name}: selected destination actually changes',
                  any(before[0][i] != after[0][i] for i in allowed if i >= record_offset + 0x30))
            check(f'{name}: pattern and mirror agree', after[0] == after[1])

        knob(2, -1)  # TRIG
        knob(3, -127)  # NOTE
        knob(4, -127)
        knob(4, 4)
        before = snapshots()
        pulses = field('ef_pulses')
        knob(0, 1)
        check('MIDI PULS edit with existing trigs opens confirmation', field('ef_ask') == 1)
        unchanged('opening confirmation leaves every pattern byte unchanged', before)
        s.yes()
        check('confirmation YES releases the stock dialog', p.long(DIALOG_OPEN) == 0)
        check('confirmation YES leaves editing unlocked', field('ef_unlocked') == 1 and field('ef_ask') == 0)
        check('confirmation YES applies the pending PULS delta', field('ef_pulses') == pulses + 1)
        unchanged('confirmation YES does not regenerate any destination', before)
        knob(1, 1)
        p.press('cue', settle=400)
        check('ROT and CUE remain editable after confirmation', field('ef_ask') == 0 and field('ef_free') == 1)
        unchanged('preview edits leave all existing locks untouched', before)
        s.yes()
        isolated('NOTE TRIG CUE fill', before, 0, True)
        check('explicit fill relocks rhythm editing', field('ef_unlocked') == 0,
              f"ef_unlocked={field('ef_unlocked')}")

        # Select CC1 through D, then confirm a CUE gesture. It must only
        # change the preview until the separate fill YES.
        knob(3, 20)
        knob(4, -127)
        knob(4, 5)
        before = snapshots()
        p.press('cue', settle=400)
        check('CUE on a baked MIDI track opens confirmation', field('ef_ask') == 1)
        s.yes()
        check('confirmation resumes pending CUE and keeps controls unlocked',
              field('ef_unlocked') == 1 and field('ef_free') == 1 and field('ef_from_cue') == 1)
        unchanged('CUE confirmation preserves NOTE, VEL, CC and all other locks', before)
        s.yes()
        isolated('CC1 TRIG CUE fill', before, 20, True)

        before = snapshots()
        p.press('cue', settle=400)
        p.press('no', settle=400)
        check('confirmation NO cancels and stays locked', field('ef_ask') == 0 and field('ef_unlocked') == 0)
        unchanged('confirmation NO preserves every pattern and mirror byte', before)

        knob(3, -19)  # VEL
        knob(4, -127)
        before = snapshots()
        knob(0, -1)
        s.yes()
        check('second PULS confirmation also unlocks', field('ef_unlocked') == 1)
        unchanged('DPTH zero confirmation preserves all existing locks', before)
        s.yes()
        isolated('VEL TRIG depth-zero fill', before, 1, True)
        check('DPTH zero clears only the selected VEL locks',
              all(u8(p, record + 0x30 + step * 32 + 1) == 255 for step in range(16)))

        knob(3, 19)  # CC1
        knob(4, 5)
        knob(2, 1)  # PLCK
        knob(0, 3)
        before = snapshots()
        p.press('cue', settle=400)
        check('PLOCK CUE needs no note-trig confirmation', field('ef_ask') == 0)
        s.yes()
        isolated('CC1 PLOCK fill', before, 20, False)
        # Exercise destination boundaries and each MIDI page family through D.
        selected = 20
        for flat in (3, 4, 5, 18, 19, 29):
            knob(3, flat - selected)
            selected = flat
            knob(4, -127)
            knob(4, 5)
            knob(0, -64)
            knob(0, 3)
            before = snapshots()
            p.press('cue', settle=400)
            s.yes()
            isolated(f'MIDI flat {flat} PLOCK fill', before, flat, False)

        def clear_menu():
            p.chord('func', 'bank', settle=500)
            check('MIDI FUNC+BANK opens all three clear rows',
                  s.clear_labels() == ['CLEAR DEST', 'CLEAR ALL DEST', 'CLEAR ALL+TRIGS'])

        def clear_row(index):
            clear_menu()
            for _ in range(index):
                p.press('down', settle=150)
            p.press('yes', settle=700)
            check(f'MIDI clear row {index} restores SEQ', p.long(s.ef) != 0)

        def settings():
            return (p.peek(local_sym('ef_midi_dep_mem'), 8 * 36),
                    p.peek(local_sym('ef_midi_plk_mem'), 8 * 30 * 12))

        def settings_others(before, flat=None):
            after = settings()
            ranges = ((track * 36, 36), (track * 30 * 12, 30 * 12))
            for tag, old, new, (start, length) in zip(('depth', 'PLOCK'), before, after, ranges):
                if flat is None:
                    allowed = set(range(start, start + length))
                else:
                    at = start + flat * (1 if tag == 'depth' else 12)
                    allowed = set(range(at, at + (1 if tag == 'depth' else 12)))
                check(f'MIDI clear preserves other {tag} recipes',
                      all(a == b for i, (a, b) in enumerate(zip(old, new)) if i not in allowed))

        def all_clear_isolated(name, before, trigs):
            after = snapshots()
            allowed = {record_offset + 0x30 + step * 32 + flat
                       for step in range(16) for flat in range(30)}
            if trigs:
                allowed.update(range(record_offset, record_offset + 8))
            for tag, old, new in zip(('RAM', 'CS1'), before, after):
                bad = [i for i, (a, b) in enumerate(zip(old, new)) if a != b and i not in allowed]
                check(f'{name}: {tag} preserves audio, other MIDI tracks and steps outside LEN', not bad,
                      f'unexpected offsets={bad[:12]}' if bad else '')
            check(f'{name}: all focused MIDI destinations clear',
                  all(u8(p, record + 0x30 + step * 32 + flat) == 255
                      for step in range(16) for flat in range(30)))
            check(f'{name}: bank and battery mirror agree', after[0] == after[1])

        audio_settings = (p.peek(local_sym('ef_dep_mem'), 8 * 36),
                          p.peek(local_sym('ef_plk_mem'), 8 * 36 * 12))
        before = snapshots()
        clear_menu()
        p.press('no', settle=500)
        check('MIDI clear NO restores SEQ', p.long(s.ef) != 0)
        unchanged('MIDI clear NO preserves the pattern and battery mirror', before)
        clear_menu()
        p.chord('func', 'bank', settle=500)
        check('MIDI FUNC+BANK toggles the menu closed and restores SEQ', p.long(s.ef) != 0 and not s.clear_labels())
        unchanged('MIDI clear toggle preserves all pattern data', before)

        before = snapshots()
        recipe_before = settings()
        check('MIDI CLEAR DEST starts with locks to clear',
              any(u8(p, record + 0x30 + step * 32 + 29) != 255 for step in range(16)))
        clear_row(0)  # current destination is CC10 / flat 29
        isolated('MIDI CLEAR DEST', before, 29, False)
        check('MIDI CLEAR DEST immediately resets focused knobs',
              field('ef_depth') == field('ef_ppulses') == field('ef_prot') == 0)
        settings_others(recipe_before, 29)

        before = snapshots()
        recipe_before = settings()
        clear_row(1)
        all_clear_isolated('MIDI CLEAR ALL DEST', before, False)
        settings_others(recipe_before)
        check('MIDI CLEAR ALL DEST preserves the note-trig mask', p.peek(record, 8) == before[0][record_offset:record_offset + 8])
        dep, plk = settings()
        check('MIDI CLEAR ALL DEST resets all focused recipes',
              not any(dep[track * 36:(track + 1) * 36])
              and not any(plk[track * 360:(track + 1) * 360]))

        # Refill through the actual panel before the final menu row.
        knob(4, 5)
        knob(0, 4)
        p.press('cue', settle=400)
        s.yes()
        before = snapshots()
        clear_row(2)
        all_clear_isolated('MIDI CLEAR ALL+TRIGS', before, True)
        mask_before = int.from_bytes(before[0][record_offset:record_offset + 8], 'big')
        check('MIDI CLEAR ALL+TRIGS clears only note trigs within LEN',
              int.from_bytes(p.peek(record, 8), 'big') == mask_before & ~0xffff)
        check('MIDI CLEAR ALL+TRIGS restores TRIG defaults',
              field('ef_pulses') == 5 and field('ef_rot') == field('ef_free') == 0)
        check('all MIDI clear rows preserve audio SEQ settings', audio_settings ==
              (p.peek(local_sym('ef_dep_mem'), 8 * 36),
               p.peek(local_sym('ef_plk_mem'), 8 * 36 * 12)))
    print(f'SEQ MIDI edits: {len(failures)} failed checks', flush=True)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
