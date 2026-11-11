"""One system dependency, separately selected native event contracts."""
import re

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

# Explicit families prevent a notification from being confused with an owner.
# Each tuple is (module key, callback prefix, events). Order is dispatch order;
# a key may be a tuple of module keys, present when every one of them is (PAGES'
# locks: PAGES with a client that declares LOCKS, pages/manifest.py).
# edit.held and edit.scene_held use first-owner precedence. Registration is entirely build-time.
FAMILIES = {
    'transport': ('start', 'resume'),
    'midi': ('note_accepted',),
    'edit': ('held', 'copy_pre', 'scene_held', 'steps'),
}
CLIENTS = {
    'transport': (('EUCLID', 'eu_seq', ('start', 'resume')),
                  ('MIDI FOLLOW', 'bf_seq', ('start', 'resume'))),
    'midi': (('MIDI FOLLOW', 'bf_seq', ('note_accepted',)),),
    'edit': (('PLOCKS P2', 'plk_ed', ('held', 'copy_pre')),),
}


def present(key, modules):
    """A registration's module key, or every key of a tuple, in the remix."""
    return all(k in modules for k in (key if isinstance(key, tuple) else (key,)))


def registrations(modules):
    """Validate even absent clients; return ordered symbols per event."""
    if set(CLIENTS) != set(FAMILIES):
        raise ValueError('EVENTS registrations must name exactly the declared families')
    out = {}
    symbols = set()
    for family, events in FAMILIES.items():
        seen = set()
        for event in events:
            out[family, event] = []
        for key, prefix, handled in CLIENTS[family]:
            if (not key or key in seen or not handled
                    or len(set(handled)) != len(handled)
                    or set(handled) - set(events)
                    or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', prefix)):
                raise ValueError(f'invalid EVENTS {family} registration: {key!r}')
            seen.add(key)
            for event in handled:
                suffixes = (('claim', 'handle') if (family, event) == ('edit', 'held')
                            else ('scene_claim', 'scene_handle') if (family, event) == ('edit', 'scene_held')
                            else (event,))
                names = tuple(f'{prefix}_{suffix}' for suffix in suffixes)
                if symbols.intersection(names):
                    raise ValueError(f'duplicate EVENTS callback: {names}')
                symbols.update(names)
                if present(key, modules):
                    out[family, event].append(names)
    return out


def event_inc(modules, remix=None):
    """Generate direct calls, with no pointer table or runtime event switch."""
    out = []
    for (family, event), handlers in registrations(modules).items():
        name = f'ev_{family}_{event}'
        out += [f'.set {name}_count, {len(handlers)}', f'.macro {name}']
        for i, names in enumerate(handlers):
            if family == 'transport':
                out += ['    move.l (%sp),%d0', f'    jsr {names[0]}']
            elif family == 'midi':
                out += ['    movem.l (%sp),%d0-%d3', f'    jsr {names[0]}']
            elif event == 'steps':           # the site's record: op, then up to five arguments
                out += ['    movem.l (%sp),%d0-%d5', f'    jsr {names[0]}']
            elif event == 'copy_pre':
                out += ['    move.l 68(%sp),%d0', '    move.l 72(%sp),%d1',
                        '    move.l 76(%sp),%d2', f'    jsr {names[0]}']
            else:
                out += ['    move.l 68(%sp),%d0', '    move.l 72(%sp),%d1',
                        f'    jsr {names[0]}', '    tst.l %d0',
                        f'    beq.w .Lev_{event}_next_{i}_\\@', '    EV_RESTORE',
                        f'    jmp {names[1]}', f'.Lev_{event}_next_{i}_\\@:']   # \\@: one per expansion
        out += ['.endm']
    return '\n'.join(out) + '\n'


def select(modules):
    """Only claimed boundaries/code enter the bound module and claims ledger."""
    active = {event for event, handlers in registrations(modules).items() if handlers}
    detours = tuple(d for event, hooks in HOOKS.items() if event in active for d in hooks)
    units = tuple(u for u in UNITS if any(d.unit == u.label for d in detours))
    return {'linked': units, 'detours': detours}


UNITS = (
    Linked('eventsseq', 'modules/events/sequencer.s', dram=True, include=event_inc),
    Linked('eventsedit', 'modules/events/edit.s', dram=True, include=event_inc),
)

# Each event's native boundary is independently optional. Empty events leave
# the stock instructions intact, rather than detouring through an empty stub.
HOOKS = {
    ('transport', 'start'): (
        Detour(0x4009c3d4, bytes.fromhex('23c0800065b8'), 'eventsseq', 'seq_start', 'transport start'),),
    ('transport', 'resume'): (
        Detour(0x4009c4d4, bytes.fromhex('23c0800065b8'), 'eventsseq', 'seq_resume', 'transport resume'),),
    ('midi', 'note_accepted'): (
        Detour(0x4009fbb2, bytes.fromhex('7339400d807c'), 'eventsseq', 'seq_sent_a', 'accepted MIDI output'),
        Detour(0x4009fcfa, bytes.fromhex('7139400d807c'), 'eventsseq', 'seq_sent_b', 'accepted MIDI ownership replacement'),),
}

_EDIT_HOOKS = (
        Detour(0x400508e4, bytes.fromhex('4fefffb048d77cfc'), 'eventsedit', 'ed_held', 'held-step editor ownership', pad_to=8),
        Detour(0x40053498, bytes.fromhex('4fefffdc48d71cfc'), 'eventsedit', 'ed_scene_held', 'held-scene knob ownership (SCENE A)', pad_to=8),
        Detour(0x40052e98, bytes.fromhex('4fefffe048d70cfc'), 'eventsedit', 'ed_scene_held_b', 'held-scene knob ownership (SCENE B)', pad_to=8),
        Detour(0x400267e8, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40026884, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40026ece, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40026f5e, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40027764, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40027834, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x4002924c, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029280, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029316, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029352, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029550, bytes.fromhex('49f940020898'), 'eventsedit', 'ed_copy', 'track-lock snapshot before trig paste or clear', kind='lea'),
        Detour(0x4002a426, bytes.fromhex('49f940020898'), 'eventsedit', 'ed_copy', 'restore track-lock snapshot on trig undo', kind='lea'),
        Detour(0x40029980, bytes.fromhex('4eb940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029652, bytes.fromhex('49f940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002978e, bytes.fromhex('49f940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b370, bytes.fromhex('45f940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b42e, bytes.fromhex('45f940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b4b2, bytes.fromhex('49f940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b692, bytes.fromhex('49f940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b9da, bytes.fromhex('45f940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4003de14, bytes.fromhex('47f940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4003e036, bytes.fromhex('47f940020898'), 'eventsedit', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
    )
# edit.steps: a step's locks move or go, at the stock routines that move or
# clear page-1 locks (docs/firmware/STEP_LOCKS.md section 4); d0 = op:
#   0 TRIG_CLEAR   d1 step (the UI's bank, pattern, track): a trig taken off clears its locks
#   1 LOCKS_CLEAR  d1 pattern, d2 track, d3 page, d4 mask: hold trigs + PLAY
#   2 TRACK_CLEAR  d1 pattern, d2 track, d3 flags (bit 0: the steps and locks)
#   3 TRIG_COPY    d1 clip, d2 pattern, d3 track, d4 page, d5 mask: record b = bit b
#   4 TRIG_PASTE   d1 clip, d2 pattern, d3 track, d4 source record, d5 destination step
# Notify all, before the stock routine goes on (TRIG_PASTE: before the step's lock copy).
_STEPS_HOOKS = (
    Detour(0x4006036E, bytes.fromhex('e98e260dd686'), 'eventsedit', 'ed_steps_trig', 'a trig taken off: its locks', pad_to=6),
    Detour(0x40040E14, bytes.fromhex('4fefffd448d77cfc'), 'eventsedit', 'ed_steps_locks', 'clear the held steps\' locks', pad_to=8),
    Detour(0x40039DF4, bytes.fromhex('4fefffc448d77cfc'), 'eventsedit', 'ed_steps_track', 'clear a track (and, per track, a pattern)', pad_to=8),
    Detour(0x4002BF38, bytes.fromhex('4fefffc048d77cfc'), 'eventsedit', 'ed_steps_copy', 'trig copy into the clipboard or the undo buffer', pad_to=8),
    Detour(0x4002CB52, bytes.fromhex('d1fc1001614f'), 'eventsedit', 'ed_steps_paste', 'trig paste, before the step\'s lock copy', pad_to=6),
)
HOOKS['edit', 'steps'] = _STEPS_HOOKS
HOOKS['edit', 'held'] = _EDIT_HOOKS[:1]
HOOKS['edit', 'scene_held'] = _EDIT_HOOKS[1:3]
HOOKS['edit', 'copy_pre'] = _EDIT_HOOKS[3:]

MODULE = Module(
    name='events', key='EVENTS', kind=Kind.CF_PATCH,
    category=Category.PARTS, author='radiohagen', author_url='https://github.com/radiohagen',
    proof=Proof.CHECK, proof_note="Tested on radiohagen's MKII (25 Oct 2026): transport and trig-paste undo.",
    doc='System: transport and MIDI notifications, held-step ownership and copy notifications.',
    linked=UNITS, detours=tuple(d for hooks in HOOKS.values() for d in hooks),
    select=select,
    gates=(Gate('tools/verify/verify_system_events.py', once=True, venv=True),
           Gate('tools/verify/verify_edit_events.py', once=True, venv=True),
           Gate('tools/verify/verify_events_selection.py', once=True, venv=True),
           Gate('tools/verify/verify_event_clients.py', stage='image', venv=True)),
)
