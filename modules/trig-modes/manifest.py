"""TRIG MODES: compose registered MIDI playing modes at shared stock sites."""
from collections import namedtuple
import re

from remix.schema import Gate, Category, Detour, Kind, Linked, Module, Poke, Proof, SymbolRef


# An immutable record, independent of the manifest loader's module lifetime.
Mode = namedtuple('Mode', 'module number title order key leds release guide overlay octave icon',
                  defaults=(None, None, False, 1))


# Clients supply musical behavior. The dispatcher has no client-specific branches.
CLIENTS = (
    Mode('CHORDS FACTORY', 2, 'CHORDS', 20,
         'ch_trig_key', 'ch_leds', 'ch_trig_release', overlay='ch_trig_overlay', icon=2),
    Mode('MIDI HARMONY', 6, 'CHORD PLAY', 30,
         'mhc_play_key', 'mhc_play_leds', 'mh_trig_release', guide='mhc_play_guide', octave=True),
)
STOCK_ROWS = ((0, 0), (1, 10), (4, 100))
STOCK_NAMES = (0x400b5f4b, 0x400b5366, 0x400b5370, 0x400b6cb9, 0x400b5376, 0x400b5381)
STOCK_ICONS = (0x400beaaa, 0x400beae6, 0x400bea82, 0x400bea96, 0x400beabe, 0x400bead2)


def registrations(modules):
    """Validate all declarations, including absent clients; return selected modes."""
    numbers, owners, callbacks = set(), set(), set()
    for m in CLIENTS:
        if (not m.module or m.module in owners or type(m.number) is not int
                or m.number in (0, 1, 4) or not 0 <= m.number <= 31 or m.number in numbers
                or type(m.order) is not int or not 10 < m.order < 100
                or not re.fullmatch(r'[A-Z0-9][A-Z0-9 -]{0,15}', m.title)
                or type(m.octave) is not bool
                or type(m.icon) is not int or not 0 <= m.icon < len(STOCK_ICONS)):
            raise ValueError(f'invalid TRIG MODES registration: {m!r}')
        for symbol in (m.key, m.leds, m.release, m.guide, m.overlay):
            if symbol is None:
                continue
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', symbol) or symbol in callbacks:
                raise ValueError(f'duplicate or invalid TRIG MODES callback: {symbol!r}')
            callbacks.add(symbol)
        if not all((m.key, m.leds, m.release)):
            raise ValueError('TRIG MODES clients require key, LED and release callbacks')
        owners.add(m.module)
        numbers.add(m.number)
    selected = tuple(sorted((m for m in CLIENTS if m.module in modules), key=lambda m: (m.order, m.number)))
    if len(selected) + len(STOCK_ROWS) > 6:
        raise ValueError('TRIG MODES: the measured stock menu supports at most six rows')
    return selected


def rows(modules):
    return tuple(n for n, _ in sorted((*STOCK_ROWS, *((m.number, m.order) for m in registrations(modules))),
                                      key=lambda row: (row[1], row[0])))


def mode_inc(modules, remix=None):
    modes = registrations(modules)
    ordered = rows(modules)
    names = {m.number: f'tm_title_{m.number}' for m in modes}
    icons = {m.number: STOCK_ICONS[m.icon] for m in modes}
    top = max((*range(len(STOCK_NAMES)), *names))
    out = [f'.set TM_ROWS, {len(ordered)}', '.macro tm_tables', '.balign 4',
           '.global tm_modes, tm_names, tm_icons', 'tm_modes:',
           '    .long ' + ','.join(map(str, ordered)), 'tm_names:']
    for n in range(top + 1):
        out.append(f'    .long {names.get(n, hex(STOCK_NAMES[n]) if n < len(STOCK_NAMES) else hex(STOCK_NAMES[0]))}')
    out.append('tm_icons:')
    for n in range(top + 1):
        out.append(f'    .long {hex(icons.get(n, STOCK_ICONS[n] if n < len(STOCK_ICONS) else STOCK_ICONS[0]))}')
    for m in modes:
        out += [f'tm_title_{m.number}: .asciz "{m.title}"']
    out += ['.balign 2', '.endm']
    for event in ('key', 'leds', 'guide'):
        out.append(f'.macro tm_dispatch_{event}')
        for m in modes:
            symbol = getattr(m, event)
            if symbol:
                out += [f'    cmpi.l #{m.number},%d0', f'    bne.s .Ltm_{event}_{m.number}']
                if event == 'key':
                    out += ['    move.l 8(%sp),-(%sp)', '    move.l 8(%sp),-(%sp)',
                            f'    jsr {symbol}', '    lea 8(%sp),%sp', '    bra.w .key_refresh']
                else:
                    out += [f'    jmp {symbol}']
                out += [f'.Ltm_{event}_{m.number}:']
        out.append('.endm')
    out.append('.macro tm_overlays')
    for m in modes:
        if m.overlay:
            out += [f'    jsr {m.overlay}', '    tst.l %d0', f'    beq.s .Ltm_overlay_{m.number}',
                    '    rts', f'.Ltm_overlay_{m.number}:']
    out += ['.endm', '.macro tm_releases']
    for m in modes:
        out += ['    move.l 68(%sp),-(%sp)', f'    jsr {m.release}', '    addq.l #4,%sp']
    out += ['.endm', '.macro tm_octaves']
    for m in modes:
        if m.octave:
            out += [f'    cmpi.l #{m.number},%d1', f'    bne.s .Ltm_octave_{m.number}',
                    '    moveq #1,%d1', f'.Ltm_octave_{m.number}:']
    out += ['.endm', '.macro tm_registered']
    for m in modes:
        out += [f'    cmpi.l #{m.number},%d0', '    beq.w .grid_release']
    out += ['.endm']
    return '\n'.join(out) + '\n'


H = bytes.fromhex
UNIT = Linked('trigmodes', 'modules/trig-modes/modes.s', dram=True, include=mode_inc)
DETOURS = (
    Detour(0x400359fa, H('2c3c400beb72'), 'trigmodes', 'tm_list_names', 'MIDI mode names'),
    Detour(0x40036046, H('41f9400beb72'), 'trigmodes', 'tm_bar_names', 'MIDI mode title'),
    Detour(0x40058742, H('2f39460d16f0'), 'trigmodes', 'tm_cursor', 'mode ID to menu row'),
    Detour(0x400501d8, H('2f02206f0008'), 'trigmodes', 'tm_key', 'registered playing-mode keys'),
    Detour(0x40043fdc, H('4fefffbc48d73c7c'), 'trigmodes', 'tm_leds', 'registered playing-mode LEDs', pad_to=8),
    Detour(0x40044920, H('4fefffd448d77cfc'), 'trigmodes', 'tm_guide', 'registered mode guide', pad_to=8),
    Detour(0x40043728, H('4feffff048d70c0c'), 'trigmodes', 'tm_release', 'client note cleanup before native cleanup', pad_to=8),
    Detour(0x4004878a, H('41f94007e998'), 'trigmodes', 'tm_grid', 'release playing-mode ownership on grid entry'),
    *(Detour(a, H('b0b9460d16f0'), 'trigmodes', 'tm_octave', 'registered native octave controls', kind='jsr')
      for a in (0x400458b2, 0x400458e6)),
)


def select(modules):
    active = registrations(modules)
    if not active:
        return dict(linked=(), detours=(), pokes=(), symbol_refs=())
    return dict(linked=(UNIT,), detours=DETOURS,
                pokes=(Poke(0x4005872e, H('7003'), bytes((0x70, len(rows(modules)))),
                            'MIDI mode row count'),),
                symbol_refs=(
                    *(SymbolRef(a, 0x400a74c0, 'trigmodes', 'tm_modes', 'registered MIDI mode list')
                      for a in (0x40035a24, 0x40051efc, 0x40051f6c)),
                    *(SymbolRef(a, 0x400beb8a, 'trigmodes', 'tm_icons', 'mode icon table')
                      for a in (0x40035856, 0x40035a46))))


MODULE = Module(name='trig-modes', key='TRIG MODES', kind=Kind.CF_PATCH,
                category=Category.SETTINGS, author='radiohagen',
                author_url='https://github.com/radiohagen', proof=Proof.CHECK,
                proof_note='Independent-client machine checks and combined Factory/Harmony panel checks; not tested on hardware',
                doc='System: compose MIDI playing modes, menu navigation and mode callbacks.',
                gates=(Gate('tools/verify/verify_trig_modes.py', venv=True, once=True),),
                select=select)
