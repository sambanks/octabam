"""Shared editor ownership and native pattern/track data movement."""
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

EVENTS = ('held', 'copy_pre')
# Explicit order: held predicates select the FIRST matching owner. Predicates
# must be read-only. Copy notifications reach ALL registered clients.
CLIENTS = (
    ('PLOCKS P2', 'plk_ed', ('held', 'copy_pre')),
)

def edit_inc(modules, remix=None):
    seen = set()
    for key, prefix, handled in CLIENTS:
        if key in seen or len(set(handled)) != len(handled) or set(handled) - set(EVENTS):
            raise ValueError(f'invalid EDIT EVENTS registration: {key}')
        seen.add(key)
    out = []
    for event in EVENTS:
        out.append(f'ed_ev_{event}:')
        for key, prefix, handled in CLIENTS:
            if key in modules and event in handled:
                if event == 'held':
                    out.append(f'    .long {prefix}_claim, {prefix}_handle')
                else:
                    out.append(f'    .long {prefix}_{event}')
        out.append('    .long 0')
    return '\n'.join(out) + '\n'

MODULE = Module(
    name='edit-events', key='EDIT EVENTS', kind=Kind.CF_PATCH,
    category=Category.PARTS, author='radiohagen',
    author_url='https://github.com/radiohagen', proof=Proof.CHECK, proof_note='Assembled dispatcher tests (0/1/3 clients); 21 installed hooks and three PLOCKS callbacks checked; held-edit/copy paths on radiohagen’s MKII, Core PLK858 (22 Oct 2026)',
    doc='Platform: held-step editor routing and pattern/track copy notifications.',
    linked=(Linked('editevents', 'modules/edit-events/events.s', dram=True, include=edit_inc),),
    gates=(Gate('tools/verify/verify_edit_events.py', once=True, venv=True),
           Gate('tools/verify/verify_edit_event_clients.py', stage='image', venv=True)),
    detours=(
        Detour(0x400508e4, bytes.fromhex('4fefffb048d77cfc'), 'editevents', 'ed_held', 'held-step editor ownership', pad_to=8),
        Detour(0x400267e8, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40026884, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40026ece, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40026f5e, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40027764, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40027834, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x4002924c, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029280, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029316, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029352, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029980, bytes.fromhex('4eb940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='jsr'),
        Detour(0x40029652, bytes.fromhex('49f940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002978e, bytes.fromhex('49f940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b370, bytes.fromhex('45f940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b42e, bytes.fromhex('45f940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b4b2, bytes.fromhex('49f940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b692, bytes.fromhex('49f940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4002b9da, bytes.fromhex('45f940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4003de14, bytes.fromhex('47f940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
        Detour(0x4003e036, bytes.fromhex('47f940020898'), 'editevents', 'ed_copy', 'pattern/track data movement, including clipboard and undo', kind='lea'),
    ),
)
