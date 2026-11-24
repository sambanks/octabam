"""MACHINES -- the track's machine list, SRC SETUP and the Part validator, held
once for every added machine (docs/specs/MACHINES.md).

An added machine is a client: an entry in CLIENTS below, `requires=("MACHINES",)`,
and the routines that make it different from its base machine
(`<prefix>_mc_<hook>`). MACHINES gives each client present a row (5, 6, ...
in CLIENTS order), signs a track that chooses it, and answers every stock site
that shows or stores a track's machine. A client claims none of those sites.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Evidence, Level

H = bytes.fromhex

FLEX = 1
# (module key, symbol prefix, signature, name, base machine, plays the base's slot, hooks).
# The signature is two ASCII bytes and a version byte. A client exports
# `<prefix>_mc_defaults`, the 12 knob bytes a track gets when first signed (page 1, then
# page 2), and its hooks: `page` is required (<prefix>_mc_page(type_ptr) -> the PLAYBACK
# descriptor), `tick` and `keep` are optional.
CLIENTS = (
    ("DRUMMER", "dr", b"DR\x01", "DRUMMER", FLEX, True, ("page", "tick", "keep")),
    ("ANALOG BD", "ab", b"AB\x01", "ANALOG BD", FLEX, False, ("page",)),
)
HOOKS = ("page", "tick", "keep")
# PB_TABLE (0x400d5f38) has slots 0..6 and a spare zero word at 0x400d5f54; the FX1 table
# starts at 0x400d5f58: three client rows at most until the table is moved.
MAX = 3
STOCK_NAMES = (0x400B3EAC, 0x400B3E98, 0x400B7C67, 0x400B5413, 0x400B7A63)


# The longest machine name the list draws today (BLKPYRAMD, ANALOG BD): a longer one is not measured.
NAME_MAX = 9


def check_clients(clients):
    """CLIENTS is the contract every machine author edits: refuse an entry the tables cannot serve."""
    seen_sig, seen_prefix = {}, {}
    for key, prefix, sig, name, base, slot, hooks in clients:
        where = f"MACHINES CLIENTS {key!r}"
        if base != FLEX:
            raise ValueError(f"{where}: base {base} -- the validator masks a client's knobs with FLEX's "
                             f"defaults (machines.c mc_validate), so FLEX is the only base for now")
        if len(sig) != 3 or not all(0x20 < b < 0x7F for b in sig[:2]) or sig[2] == 0:
            raise ValueError(f"{where}: signature {sig!r} -- two printable ASCII bytes and a version byte, not 0")
        if sig in seen_sig:
            raise ValueError(f"{where}: signature {sig!r} is {seen_sig[sig]!r}'s -- the second row would be unreachable")
        if prefix in seen_prefix or not prefix.isidentifier():
            raise ValueError(f"{where}: prefix {prefix!r} -- an identifier no other client uses")
        if not 0 < len(name) <= NAME_MAX or any(c in name for c in '"\\') or not name.isascii() or not name.isprintable():
            raise ValueError(f"{where}: name {name!r} -- 1 to {NAME_MAX} printable ASCII characters, no quote "
                             f"or backslash (it is written into an .asciz)")
        if "page" not in hooks or not set(hooks) <= set(HOOKS):
            raise ValueError(f"{where}: hooks {hooks!r} -- 'page' and any of {HOOKS}")
        seen_sig[sig], seen_prefix[prefix] = key, key


def present(modules):
    """The clients in a selection, in row order."""
    on = tuple(c for c in CLIENTS if c[0] in modules)
    if len(on) > MAX:
        raise ValueError(f"MACHINES: {', '.join(c[0] for c in on)} need {len(on)} rows after the "
                         f"stock five; PB_TABLE has room for {MAX}")
    return on


def machines_inc(modules, remix=None):
    """remix.inc for machines.s: the clients' tables, and each client's row word."""
    on = present(modules)
    n = len(on)
    hook = lambda c, h: f"{c[1]}_mc_{h}" if h in c[6] else "0"            # noqa: E731
    out = [f".set MC_END, {5 + n}", "        .balign 4",
           "        .global mc_count, mc_sigs, mc_defaults, mc_flags, mc_pages, mc_ticks, mc_keeps",
           "        .global mc_src_names",
           f"mc_count: .long {n}"]
    out.append("mc_sigs:")
    out += [f"        .long 0x{int.from_bytes(c[2] + bytes(1), 'big'):08x}" for c in on]
    out.append("mc_defaults:")
    out += [f"        .long {c[1]}_mc_defaults" for c in on]
    out.append("mc_flags:")
    out += [f"        .long 0x{c[4] | (0x100 if c[5] else 0):x}" for c in on]
    for h in HOOKS:
        out.append(f"mc_{h}s:")
        out += [f"        .long {hook(c, h)}" for c in on]
    out.append("mc_src_names:")
    out += [f"        .long 0x{a:08x}" for a in STOCK_NAMES]
    out += [f"        .long mc_name_{i}" for i in range(n)]
    for i, c in enumerate(on):
        out += [f"        .global {c[1]}_mc_row", f"{c[1]}_mc_row: .long {5 + i}"]
    for i, c in enumerate(on):
        out.append(f'mc_name_{i}: .asciz "{c[3]}"')
    out.append("        .balign 2")
    return "\n".join(out) + "\n"


DETOURS = (
    Detour(0x400334D8, H("2f02222f0008"), "machines", "mc_machine_name", "a row's name on the machine list"),
    Detour(0x4003C928, H("4bf9400a78c8"), "machines", "mc_src_names", "SRC SETUP's machine names, the clients' after "
           "stock's five", kind="lea"),
    Detour(0x4003D718, H("41f9400a78c8"), "machines", "mc_name_a", "the main page's name of a track's machine"),
    Detour(0x4004C36A, H("41f9400a78c8"), "machines", "mc_name_b", "the second name lookup"),
    Detour(0x4003C980, H("71104fef0018"), "machines", "mc_setup_row", "SRC SETUP highlights the track's row"),
    Detour(0x40078678, H("7004b0826d24"), "machines", "mc_chooser_name",
           "the machine list scrolls: row top + d2's name on screen row d2"),
    Detour(0x400786C8, H("7110b480662e7004b0826d28"), "machines", "mc_chooser_box",
           "the machine list's box on the track's row", pad_to=12),
    Detour(0x400585DC, H("161079034879400bb704"), "machines", "mc_setup_open", "SRC SETUP opens on the track's row",
           pad_to=10),
    Detour(0x40078886, H("71102f004879460e7386"), "machines", "mc_chooser_open",
           "the machine list opens on the track's row", pad_to=10),
    Detour(0x4003A52E, H("2002e788d4829082"), "machines", "mc_setup_edit6",
           "SETUP's editor: a client's row edits its base's bytes", pad_to=8),
    Detour(0x4003CD98, H("2e06e78fdc869e86"), "machines", "mc_setup_draw6",
           "SETUP's drawer: a client's row draws its base's bytes", pad_to=8),
    Detour(0x4007981C, H("77101084d081"), "machines", "mc_main_commit", "the list's commit signs a client's track"),
    Detour(0x4005A616, H("2239460d5c30"), "machines", "mc_src_commit", "SRC SETUP's commit signs a client's track"),
    Detour(0x4005A850, H("2239460d5c30"), "machines", "mc_src_commit2", "SRC SETUP's second commit path"),
    Detour(0x40002318, H("4fefffa048d77cfc"), "machines", "mc_validate_entry",
           "the Part validator keeps a client track's knob bytes", pad_to=8),
    Detour(0x4005221E, H("4ebaff1c4eb94007e940"), "machines", "mc_tick",
           "the UI tick: each client's page as its row's, each client's tick", pad_to=10),
    Detour(0x40031E74, H("710541f9400d5f386050"), "machines", "mc_resolve_pb",
           "a client's track shows its client's PLAYBACK page", pad_to=10),
    Detour(0x4003BFF0, H("711041f9400d5f38605a"), "machines", "mc_lfo_pb",
           "LFO SETUP names a client's knobs on its track", pad_to=10),
    Detour(0x4003D1C0, H("2f02202f00082239460d1a48"), "machines", "mc_setup_key",
           "SRC SETUP: RIGHT on a client's row opens its base's slot list"),
)
# The list's five key handlers (UP, DOWN, their FUNC pages, the encoder) clamp the cursor to
# 0..5 after moving (`moveq #5,%d1 ; cmp.l %d0,%d1 ; bge.s ; moveq #5,%d0`).
CLAMPS = (0x40078C22, 0x40078CB0, 0x40078D2E, 0x40078DEE, 0x40078E7C)


def pokes(n):
    """The lists' counts and bounds for 5 + n rows; none without a client, so stock's five rows stand."""
    if n == 0:
        return ()
    rows, last = 5 + n, 4 + n
    out = (
        Poke(0x40079248, H("48780005"), H(f"487800{rows:02x}"), f"the machine list has {rows} rows"),
        Poke(0x400585FA, H("48780005"), H(f"487800{rows:02x}"), f"SRC SETUP's selector has {rows} rows"),
        Poke(0x4003C950, H("7204"), H(f"72{last:02x}"), f"SRC SETUP's name lookup admits rows 5..{last}"),
        Poke(0x40079904, H("7604"), H(f"76{last:02x}"), f"the machine list's commit persists rows 5..{last}"),
    )
    if last > 5:      # one past stock's last row fits the clamp already
        out += tuple(Poke(at + off, H(f"{op}05"), H(f"{op}{last:02x}"), f"the list's cursor reaches row {last}")
                     for at in CLAMPS for off, op in ((0, "72"), (6, "70")))
    return out


check_clients(CLIENTS)
UNIT = Linked("machines", "modules/machines/machines_unit.s", cpu="5475", dram=True, include=machines_inc)


def select(modules):
    """The rows this selection's clients need."""
    return {"pokes": pokes(len(present(modules)))}


MODULE = Module(
    name="machines",
    key="MACHINES",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES, author="djib", author_url="https://github.com/Djibdjib",
    evidence=(Evidence(Level.EMULATOR, ref="modules/machines/verify.py",
        note="verify.py: the list, SRC SETUP, the commits and the validator under Unicorn, for one and two clients"),),
    doc="Platform: the machine list and SRC SETUP, held once for every added machine.",
    linked=(UNIT,),
    detours=DETOURS,
    pokes=pokes(len(CLIENTS)),
    select=select,
    # The machines still on HOOKS' machine_rows chain, and the ports outside it, until each is a client.
    conflicts=(
        ("OCTA303", "both own the machine list's sites (HOOKS machine_rows) until OCTA303 is a MACHINES client"),
        ("CX OSC", "both own the machine list's sites (HOOKS machine_rows) until CX OSC is a MACHINES client"),
        ("WAVE CF", "both own the machine list's sites (HOOKS machine_rows) until WAVE CF is a MACHINES client"),
        ("BLACKPYRAMIDS_303", "both own the machine list's sites; the port is not a MACHINES client"),
        ("SYNTH MACHINE", "both own SRC SETUP's sites; the port is not a MACHINES client"),
    ),
    gates=(Gate("modules/machines/verify.py", remix_arg=False, venv=True),),
)
