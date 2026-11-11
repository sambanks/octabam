"""PAGES -- the extra pages a page key cycles through, for several modules.

A page key pressed again on its own page (stock's mode 1: no setup window,
no FUNC) opens nothing in stock. PAGES owns that press and the display
loop's tick, and steps through the pages its clients register on that key:
the stock page, the first client's, the next one's ... then the stock page
again. Each client keeps its own window, layer and drawing; PAGES only asks
it whether its page is shown, and opens, closes and ticks it.

A client registers (module key, prefix) on a page; it exports
<prefix>_page_shown (d0 nonzero while its page is open), <prefix>_page_open,
<prefix>_page_close and <prefix>_page_tick (C convention, d0-d1/a0-a1
clobbered). Registration is build-time: the cycle is direct calls, no table.

Measured so far: SRC in MIDI mode (README "Measured": mode 1 = a single
press again, mode 3 = the double press, NOTE SETUP) and in audio mode (mode 1
leaves the track's PLAYBACK page as it was, mode 3 opens SRC SETUP). The opener 0x400322f0
is every page key's (code, mode); the other keys and audio mode are declared
when a client needs them and a gate has measured them.
"""
import re
import runpy
from pathlib import Path

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex

# The page keys PAGES may own: (mode, key) -> the key code at the opener.
KEYS = {('midi', 'src'): 0x22, ('audio', 'src'): 0x22}
CLIENTS = {
    ('midi', 'src'): (('CHORDS FACTORY', 'ch'),),
    ('audio', 'src'): (('DRUMMER', 'dr'),),
}

# LOCKS: the pages whose parameters take step locks and scene locks (locks.c).
# (module key, prefix, page id, page name, hold). The page id (1..7) is the
# page's in every lock entry, fixed once given (a saved lock names it); hold is
# how long a step's locks play: 'trig' (stock's: until the track's next trig)
# or 'step' (that step only). The client exports, C convention:
#   <prefix>_lk_ctx()                          0, or 0x8000 | page << 8 | track while
#                                              its lockable page is in front
#   <prefix>_lk_turn(page, slot, value, delta) the value a turn gives, -1 when the
#                                              slot takes no lock (delta 0: pure)
#   <prefix>_lk_part(page, track, slot)        the edited Part's value of the slot
#   <prefix>_lk_redraw(page)                   draw the page again
# With a trig (GRID RECORDING) or a scene held, a knob on ANY PAGES page is
# PAGES': a page that takes no lock (or none on that knob) drops the turn,
# rather than stock locking the page under it (reported on image 87: NEXT).
# and calls pg_lk_step / pg_lk_value / pg_lk_shown / pg_lk_where (locks.c).
# The locks enter a remix with PAGES, EVENTS (edit.held, edit.scene_held) and
# a client of them; without EVENTS the pages work without locks.
LOCKS = (
    ('DRUMMER', 'dr', 1, 'KIT BALANCE', 'trig'),
)
HOLDS = {'trig': 0, 'step': 1}

# The page key's setup opener: movel %sp@(4),%d0 ; moveq #3,%d1
OPENER = 0x400322F0
OPENER_STOCK = H("202f00047203")
# The display loop (UI task), the double-press tick load: movel 0x460d5de0,%d0
TICK = 0x40052208
TICK_STOCK = H("2039460d5de0")


def registrations(modules):
    """Validate every registration, present or not; the present clients per page, in order."""
    if set(CLIENTS) - set(KEYS):
        raise ValueError('PAGES registrations must name declared page keys')
    out, prefixes = {}, set()
    for page in KEYS:
        seen = set()
        out[page] = []
        for key, prefix in CLIENTS.get(page, ()):
            if not key or key in seen or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', prefix) \
                    or prefix in prefixes:
                raise ValueError(f'invalid PAGES {page} registration: {key!r}')
            seen.add(key)
            prefixes.add(prefix)
            if key in modules:
                out[page].append(prefix)
    return out


def pages_inc(modules, remix=None):
    """The cycle and the tick as direct calls, per page with a client."""
    regs = registrations(modules)
    out = []
    for (mode, name), prefixes in regs.items():
        tag = f'{mode}_{name}'
        out += [f'.set pg_{tag}, {len(prefixes)}', f'.set pg_{tag}_code, {KEYS[mode, name]:#x}',
                f'.macro pg_cycle_{tag}']
        # the page shown closes and the next one opens; none shown, the first opens
        for i, p in enumerate(prefixes):
            out += [f'    jsr {p}_page_shown', '    tst.l %d0', f'    beq.s .Lpg_{tag}_not_{i}',
                    f'    jsr {p}_page_close']
            out += [f'    jmp {prefixes[i + 1]}_page_open' if i + 1 < len(prefixes) else '    rts']
            out += [f'.Lpg_{tag}_not_{i}:']
        if prefixes:
            out += [f'    jmp {prefixes[0]}_page_open']
        out += ['.endm']
    every = [p for prefixes in regs.values() for p in prefixes]
    out += ['.macro pg_ticks'] + [f'    jsr {p}_page_tick' for p in every] + ['.endm']
    return '\n'.join(out) + '\n'


def lock_clients(modules):
    """Validate every LOCKS entry, present or not; the present ones (EVENTS in the remix)."""
    ids, prefixes = set(), set()
    for key, prefix, page, name, hold in LOCKS:
        if (not key or not 1 <= page <= 7 or page in ids or prefix in prefixes or hold not in HOLDS
                or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', prefix) or not name):
            raise ValueError(f'invalid PAGES LOCKS registration: {key!r}')
        if not any(key == k for regs in CLIENTS.values() for k, _p in regs):
            raise ValueError(f'PAGES LOCKS {key!r}: not a PAGES client')
        ids.add(page)
        prefixes.add(prefix)
    if not {'PAGES', 'EVENTS', 'STORE'} <= set(modules):   # STORE: PGLOCKS.WORK (client 10)
        return []
    return [entry for entry in LOCKS if entry[0] in modules]


def locks_inc(modules, remix=None):
    """The clients' callbacks by page id, their pages' hold."""
    present = lock_clients(modules)
    out = ['.macro pg_lk_ctx_calls']
    for _key, prefix, _page, _name, _hold in present:
        out += [f'    jsr {prefix}_lk_ctx', '    tst.l %d0', '    bne.s 9f']
    out += ['    bra.s 8f', '9:  rts', '8:', '.endm', '.macro pg_lk_by_page name']
    for _key, prefix, page, _name, _hold in present:
        out += ['    moveq #%d,%%d0' % page, '    cmp.l 4(%sp),%d0', '    bne.s 1f',
                f'    jmp {prefix}_lk_\\name', '1:']
    out += ['.endm', '.macro pg_lk_shown_calls']      # every PAGES page of the remix, locks or not
    for prefix in dict.fromkeys(p for prefixes in registrations(modules).values() for p in prefixes):
        out += [f'    jsr {prefix}_page_shown', '    tst.l %d0', '    bne.s 9f']
    out += ['    bra.s 8f', '9:  moveq #1,%d0', '    rts', '8:']
    ids = runpy.run_path(str(Path(__file__).parents[1] / 'store/manifest.py'))['CLIENT_IDS']
    out += ['.endm', f".set PG_CLIENT, {ids[('PAGES', 'EVENTS', 'DRUMMER')]}", '.macro pg_lk_holds']
    holds = [0] * 8
    for _key, _prefix, page, _name, hold in present:
        holds[page] = HOLDS[hold]
    out += ['    .byte ' + ', '.join(map(str, holds)), '.endm']
    return '\n'.join(out) + '\n'


def select(modules):
    """PAGES enters a remix only with a client in it; its locks with EVENTS and a LOCKS client."""
    if not any(registrations(modules).values()):
        return {'linked': (), 'detours': ()}
    return {'linked': (UNIT, LOCKS_UNIT) if lock_clients(modules) else (UNIT,), 'detours': DETOURS}


UNIT = Linked('pages', 'modules/pages/pages.s', dram=True, include=pages_inc)
LOCKS_UNIT = Linked('pagelocks', 'modules/pages/locks_unit.s', cpu='5475', dram=True, include=locks_inc)
DETOURS = (
    Detour(OPENER, OPENER_STOCK, 'pages', 'pg_opener',
           "a page key pressed again on its page (mode 1): the next registered page"),
    Detour(TICK, TICK_STOCK, 'pages', 'pg_tick_stub',
           "the display loop: every registered page's tick (follow the track, close off its page)"),
)

MODULE = Module(
    name='pages', key='PAGES', kind=Kind.CF_PATCH,
    category=Category.SETTINGS, author='djib', author_url='https://github.com/Djibdjib',
    proof=Proof.HARDWARE, proof_note="the owner's MKII (live-djib, Oct-Nov 2026): SRC again on MIDI NOTE; "
                                     "verify_chords (the port): SRC 1/2/3 through PAGES",
    doc='System: the extra pages a page key cycles through (SRC again on MIDI NOTE: CHORDS FACTORY ...).',
    linked=(UNIT,), detours=DETOURS,
    select=select,
    gates=(Gate('tools/verify/verify_chords.py', venv=True, stage='image'),),
)
