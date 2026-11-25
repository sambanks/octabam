"""STORE's optional retained byte pool: explicit, stable client reservations.

Offsets address the logical 16 KB pool, not contiguous hardware memory.
Registrations never move implicitly when a composition changes. Clients own
their format and publication; STORE owns bounds and native copy protection.
"""
from remix.schema import Gate, Linked, Poke

CAPACITY = 16384
# key: (stable client ID, logical offset, length). Harmony's existing HMT2
# layout uses the entire pool and direct aligned words; do not relocate it.
RETAINED_CLIENTS = {'MIDI HARMONY': (0, 0, CAPACITY)}

LOOPS = (
    (0x4002adc8, '7020', '701e', 'MIDI page paste'),
    (0x4002c766, '7020', '701e', 'MIDI trig paste'),
    (0x400387e6, '7020', '701e', 'MIDI masked clear'),
    (0x400397d0, '7020', '701e', 'MIDI page clear'),
    (0x40039b9e, '7020', '701e', 'MIDI track clear'),
    (0x40040dd4, '7020', '701e', 'MIDI held-lock clear'),
    (0x4005fe08, '3c3c0020', '3c3c001e', 'MIDI trig toggle'),
    (0x4009ceaa, '7220', '721e', 'MIDI step duplication'),
)


def layout(modules, clients=None):
    clients = RETAINED_CLIENTS if clients is None else clients
    active, ids = [], set()
    for key, reservation in clients.items():
        if (not isinstance(key, str) or not key or not isinstance(reservation, (tuple, list))
                or len(reservation) != 3):
            raise ValueError(f'invalid STORE retained client {key!r}')
        client, offset, size = reservation
        if (any(type(v) is not int for v in reservation) or not 0 <= client <= 0xffffffff
                or client in ids or offset < 0 or size <= 0 or offset + size > CAPACITY):
            raise ValueError(f'invalid STORE retained reservation for {key}')
        ids.add(client)
        if key in modules:
            for other, _, start, length in active:
                if offset < start + length and start < offset + size:
                    raise ValueError(f'STORE retained overlap: {key} and {other}')
            active.append((key, client, offset, size))
    return tuple(sorted(active, key=lambda row: row[1]))


def retained_inc(modules, remix=None):
    active = layout(modules)
    out = ['.macro STORE_RETAINED_TABLE', '.global store_retained_count,store_retained_clients',
           f'store_retained_count: .long {len(active)}', 'store_retained_clients:']
    out += [f'    .long {client},{offset},{size}' for _, client, offset, size in active]
    return '\n'.join(out + ['.endm']) + '\n'


def additions(modules):
    if not layout(modules):
        return dict(linked=(), pokes=(), gates=(), sram=())
    return dict(
        linked=(Linked('storeretained', 'modules/store/retained.s', dram=True),
                Linked('storeretainedcopy', 'modules/store/retained-copy.s', dram=True),
                Linked('storeretainedclients', 'modules/store/retained-clients.s',
                       dram=True, include=retained_inc)),
        pokes=tuple(Poke(at, bytes.fromhex(old), bytes.fromhex(new),
                         label + ': preserve STORE retained storage') for at, old, new, label in LOOPS),
        gates=(Gate('tools/verify/verify_store_retained.py', stage='image', venv=True),),
        # Claim only the actual padding bytes, never the intervening stock data.
        sram=tuple((0x1001614e+p*0x8ed8+0x4900+t*0x8b0+s*32+30, 2,
                    'STORE retained pool') for p in range(16) for t in range(8) for s in range(64)),
    )
