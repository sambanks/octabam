"""Settings resolved for a remix, the refusals, and the lock file.

git show 76fd8466:docs/proposals/BRAIN.md sections 2 and 4 are the rules. Layers 1 and 2
(the manifest's default and the remix's value or Pin) are resolved here, at
build. Layers 3 and 4 (card and project) exist only when the remix carries
the BRAIN module.

    python3 tools/remix/brain.py resolve <remix>      the value of every setting and its layer
    python3 tools/remix/brain.py check                every module's lock, every remix's settings
    python3 tools/remix/brain.py image-name <remix> <build>   the name REMIX SWITCH shows, and its .RMX file's
    python3 tools/remix/brain.py lock <module> [--retire KEY ...] [--retire-param KEY ...]
"""
from __future__ import annotations

import dataclasses
import json
import re
import pathlib
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from remix.schema import (BRAIN_KEY, Apply, Binary, Blob, ModeView, Number, Option,  # noqa: E402
                          Pin, Trigger)

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCK = "brain.lock"

# CS1 (battery SRAM) that stock references nothing in: its whole-CS1
# initialise writes it, nothing reads it (docs/firmware/STEP_LOCKS.md
# section 6). The early block takes the largest run left after every
# selected module's Claims.sram.
CS1_FREE = (0x100F859C, 0x100FFF00)
EARLY_HEADER = 4                 # magic, version, 16-bit sum (BRAIN.md section 6.4)


# ---- resolution -----------------------------------------------------------

@dataclass(frozen=True)
class Resolved:
    store_id: str
    module: str                  # module key
    key: int
    name: str
    value: object                # an Option is its index
    layer: str                   # "manifest", "remix" or "pin"
    runtime: bool                # card and project layers apply on the unit

    def shown(self, setting) -> str:
        k = setting.kind
        if isinstance(k, Option):
            return k.labels[self.value]
        if isinstance(k, Blob):
            return f"{len(self.value)} bytes"
        if isinstance(k, Number) and k.unit:
            return f"{self.value} {k.unit}"
        return str(self.value)


IMAGE_NAME_MAX = 15        # REMIX SWITCH's mailbox keeps the flashed image's name in 16 bytes


def image_name(remix=None, build=None) -> str:
    """The name an image calls itself: REMIX SWITCH's
    FLASHED row, the boot picker, and its .RMX file on the card. `RMXNAME` in the
    environment overrides it (`make rmx RMX=NAME`); else the remix's
    `image_name` (schema.Remix) or its last path part, then the build tag:
    `BRAIN B2`. Upper case, A-Z 0-9 space . _ -, at most IMAGE_NAME_MAX
    characters. A declared image_name is at most IMAGE_NAME_MAX - 3 characters
    so the tag (up to two characters) is never cut."""
    import os
    raw = os.environ.get("RMXNAME")
    if not raw:
        rname = pathlib.PurePath(remix or os.environ.get("REMIX", "?")).name
        from remix import registry
        base = registry.declared_image_name(rname) or rname
        raw = f"{base} {build if build is not None else os.environ.get('BUILD', '79')}"
    return re.sub(r"[^A-Z0-9 ._-]", "", raw.upper()).strip()[:IMAGE_NAME_MAX].strip() or "OCTABAM"


def remix_label(remix=None) -> str:
    """The remix's last path part, upper case, as the IMAGE tab of ABOUT shows it (at most 14 characters)."""
    import os
    raw = pathlib.PurePath(remix or os.environ.get("REMIX", "?")).name
    return re.sub(r"[^A-Z0-9 ._-]", "", raw.upper())[:14] or "?"


def has_brain(remix) -> bool:
    return BRAIN_KEY in remix.modules


def _selected(remix, mods):
    return [mods[k] for k in remix.modules if k in mods]


def _owners(remix, mods) -> dict[str, object]:
    return {m.store.id: m for m in _selected(remix, mods) if m.store is not None}


def resolve(remix, mods) -> list[tuple[Resolved, object]]:
    """(Resolved, Setting) for every setting of every selected module, in
    remix order then key order. Assumes check_remix found nothing."""
    core = has_brain(remix)
    out = []
    for m in _selected(remix, mods):
        for s in sorted(m.settings, key=lambda s: s.key):
            given = remix.settings.get((m.store.id, s.name), _ABSENT)
            if given is _ABSENT:
                value, layer = s.default, "manifest"
            elif isinstance(given, Pin):
                value, layer = given.value, "pin"
            else:
                value, layer = given, "remix"
            if isinstance(s.kind, Option):
                value = s.kind.index(value)
            runtime = (core and layer != "pin" and s.apply is not Apply.BUILD
                       and not isinstance(s.kind, Trigger))
            out.append((Resolved(m.store.id, m.key, s.key, s.name, value, layer, runtime), s))
    return out


_ABSENT = object()


# ---- the run-time value table (BRAIN.md section 5) ------------------------

def value_symbol(store_id: str, key: int) -> str:
    """The BRAIN unit's global for one setting's run-time value (a long)."""
    return "brain_v_" + re.sub(r"[^a-z0-9]", "_", store_id) + f"_{key}"


def live_table(remix, mods) -> list[tuple[Resolved, object, object]]:
    """(Resolved, Setting, module) for each setting the unit holds at run
    time: the remix carries BRAIN, the value is not pinned, it is not
    Apply.BUILD, and it is a Binary, an Option or a Number (a long in the
    value table; Blobs and Triggers have no row yet). By module key, then
    setting name: the SETTINGS list's order (BRAIN.md section 9)."""
    if not has_brain(remix):
        return []
    rows = [(r, s, mods[r.module]) for r, s in resolve(remix, mods)
            if r.runtime and isinstance(s.kind, (Binary, Option, Number))]
    return sorted(rows, key=lambda row: (row[0].module, row[1].name))


def read_macro(remix, mods, store_id: str, name: str, macro: str) -> str:
    """A gas macro `<macro> reg` a ColdFire unit reads one of its settings
    with: one absolute load from BRAIN's value table when the value is held
    at run time, else the resolved value as a constant (no BRAIN, a pin, or
    Apply.BUILD). The source is the same either way (BRAIN.md section 5)."""
    for r, s in resolve(remix, mods):
        if r.store_id == store_id and r.name == name:
            if r.runtime and isinstance(s.kind, (Binary, Option, Number)):
                body = f"        move.l  {value_symbol(store_id, r.key)},\\reg"
            else:
                body = f"        move.l  #{int(r.value)},\\reg"
            return f"        .macro  {macro} reg\n{body}\n        .endm\n"
    raise KeyError(f"{store_id}: no setting {name!r} in this remix")


def build_values(remix, mods) -> dict[str, dict[str, object]]:
    """{module key: {setting name: value}} of every Apply.BUILD setting of
    the selected modules; an Option as its label."""
    out: dict[str, dict[str, object]] = {}
    for r, s in resolve(remix, mods):
        if s.apply is Apply.BUILD:
            v = s.kind.labels[r.value] if isinstance(s.kind, Option) else r.value
            out.setdefault(r.module, {})[r.name] = v
    return out


def value(remix, mods, store_id: str, name: str):
    """One setting's resolved value for the remix (an Option as its label),
    or None when no selected module files it."""
    for r, s in resolve(remix, mods):
        if r.store_id == store_id and r.name == name:
            return s.kind.labels[r.value] if isinstance(s.kind, Option) else r.value
    return None


# ---- knob defaults (Remix.defaults) ---------------------------------------

def _knob_slot(m, mode, knob: str) -> int | None:
    """The slot `knob` names on module m: its Param name, or the name the
    mode's view gives the slot."""
    for i, p in enumerate(m.params):
        if p.name is not None and p.name.decode("ascii", "replace") == knob:
            return i
    if mode is not None:
        v = next((v for v in m.mode_views if v.mode == mode), None)
        for i, nm in (v.names.items() if v else ()):
            if nm.decode("ascii", "replace") == knob:
                return i
    return None


def _mode_value(m, mode):
    """A mode label or value -> the MODE select's value, or None when it
    names nothing."""
    if m.mode_slot is None:
        return None
    p = m.params[m.mode_slot]
    if isinstance(mode, str):
        return p.labels.index(mode) if p.labels and mode in p.labels else None
    if isinstance(mode, int) and not isinstance(mode, bool) and 0 <= mode < (p.count or 0):
        return mode
    return None


def check_defaults(remix, mods) -> list[str]:
    bad, sel = [], set(remix.modules)
    for entry, v in remix.defaults.items():
        if not (isinstance(entry, tuple) and len(entry) == 3):
            bad.append(f"defaults entry {entry!r}: (module key, mode or None, knob name)")
            continue
        key, mode, knob = entry
        m = mods.get(key) if key in sel else None
        if m is None:
            bad.append(f"defaults {entry!r}: {key!r} is not in the remix")
            continue
        if not m.params:
            bad.append(f"defaults {entry!r}: {m.name} has no knobs")
            continue
        mv = None
        if mode is not None:
            mv = _mode_value(m, mode)
            if mv is None:
                bad.append(f"defaults {entry!r}: {m.name} has no MODE value {mode!r}")
                continue
        slot = _knob_slot(m, mv, knob)
        if slot is None:
            bad.append(f"defaults {entry!r}: {m.name} has no knob {knob!r}")
            continue
        if mv is not None and slot == m.mode_slot:
            bad.append(f"defaults {entry!r}: a mode's view does not re-default MODE itself")
            continue
        count = m.params[slot].count or 128
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < count:
            bad.append(f"defaults {entry!r}: {v!r} is outside the knob's {count} values")
    return bad


def apply_defaults(m, entries) -> dict:
    """{field: value} that put a remix's knob defaults for module m into
    its params and mode views; entries are (mode value or None, slot, byte)."""
    params, views = list(m.params), {v.mode: v for v in m.mode_views}
    for mode, slot, v in entries:
        if mode is None:
            params[slot] = dataclasses.replace(params[slot], default=v)
        else:
            old = views.get(mode) or ModeView(mode)
            views[mode] = dataclasses.replace(old, defaults={**old.defaults, slot: v})
    return {"params": tuple(params),
            "mode_views": tuple(views[k] for k in sorted(views))}


def defaults_by_module(remix, mods) -> dict[str, list[tuple]]:
    out: dict[str, list[tuple]] = {}
    for (key, mode, knob), v in remix.defaults.items():
        m = mods[key]
        mv = None if mode is None else _mode_value(m, mode)
        out.setdefault(key, []).append((mv, _knob_slot(m, mv, knob), v))
    return out


# ---- FX pages as targets (BRAIN.md sections 3 and 7.6) -------------------

def fx_store_id(m) -> str:
    """The store id an effect's FX page defaults are filed under: its own
    Store, else octabam.<module directory>, or stock.<name> for a stock
    effect (spaces and punctuation to '-')."""
    if m.store is not None:
        return m.store.id
    if m.is_stock:
        return "stock." + "".join(c if c.isalnum() else "-" for c in m.key.lower()).strip("-")
    return f"octabam.{m.name}"


def fx_keys(m) -> list[int]:
    """Twelve stored keys, 0 for a slot that is not drawn. An unkeyed
    module's drawn slots are keyed by position (slot + 1), as stock's are."""
    keyed = any(p.key is not None for p in m.params)
    return [0 if p.active is not True else (p.key if keyed else i + 1)
            for i, p in enumerate(m.params)]


def fx_layout(m) -> int:
    """The layout hash of an effect's page (brainfile.layout_hash): (key, the
    declared count or 0) per slot, then the MODE slot."""
    from remix import brainfile
    keys = fx_keys(m)
    return brainfile.layout_hash([(k, (p.count or 0) if k else 0) for k, p in zip(keys, m.params)],
                            m.mode_slot)


# The stock targets of templates (brain.c st_ent): store id and layout word.
# AMP: keys 1-6 page 1, 7-12 page 2. LFO: 1-6 page 1, 7-9 PMTR, 10-12
# WAVE, 13-15 MULT, 16-18 TRIG. MIDI track: 1 + setup-record offset (0x24
# bytes, MIDI_TRACKS.md section 1), 64 + flat for page 1 (flats 0-29, 94
# and 95 the CTRL1/CTRL2 enable bitmaps). A slot whose descriptor enable
# nibble has bit 0 clear is not stored (PARAM_PAGES.md section 3b).
STOCK_TARGETS = {
    "amp": ("stock.amp", 0x414d5031),
    "lfo": ("stock.lfo", 0x4c464f31),
    "midi": ("stock.midi", 0x4d494431),
    # the SRC page, one target per machine type: keys 1-6 page 1, 7-12 page 2
    "static": ("stock.static", 0x53544131),
    "flex": ("stock.flex", 0x464c5831),
    "thru": ("stock.thru", 0x54485231),
    "neighbor": ("stock.neighbor", 0x4e425231),
    "pickup": ("stock.pickup", 0x50434b31),
}
MACHINES = ("static", "flex", "thru", "neighbor", "pickup")   # the machine byte's values


def fx_targets(remix, mods) -> list:
    """The selected effects with knobs, as the brain's table lists them."""
    return [m for m in _selected(remix, mods) if m.menu is not None and len(m.params) == 12]


# ---- the stock pages' slots (BRAIN.md section 4.2) -------------------------

STOCK_IMAGE = ROOT / "out/raw/section_3_MAIN_OS.bin"

# The stock page descriptors' entry starts (PARAM_PAGES.md section 3).
_D = dict(playback=0x400d2fe4, lfo=0x400d37be, amp=0x400d3950, note=0x400d3e06, arp=0x400d3f98, mlfo=0x400d412a,
          ctl1=0x400d42bc, ctl2=0x400d444e)
_MIDI_PAGES = (("NOTE", "note"), ("LFO", "mlfo"), ("ARP", "arp"), ("CTL1", "ctl1"), ("CTL2", "ctl2"))


def _desc(img: bytes, E: int, s: int) -> tuple[str, int, int, bool]:
    """Slot s of the stock descriptor at entry E: name, minimum, count, and
    whether its enable nibble has bit 0 set."""
    o = E - 0x40000400
    name = img[o + 0x4e + 6 * s:o + 0x54 + 6 * s].split(b"\0", 1)[0].decode("latin1")
    lo = int.from_bytes(img[o + 0xa2 + 4 * s:o + 0xa6 + 4 * s], "big", signed=True)
    cnt = int.from_bytes(img[o + 0xd2 + 4 * s:o + 0xd6 + 4 * s], "big", signed=True)
    en = int.from_bytes(img[o + 0x1c2:o + 0x1ca], "big") >> (4 * s) & 1
    return name, lo, cnt, bool(en)


def stock_slots(target: str, img: bytes) -> list[tuple[int, str, int, int]]:
    """(key, name, minimum, count) of every stored slot of a stock target, in
    brain.c view_fill's order, from the user's stock image. Names: AMP and
    LFO as the page draws them, LFO's per-LFO slots numbered (PMTR1..TRIG3);
    a repeated name takes a '2' (the SRC page's LEN2 and RATE2, THRU's
    VOL2); a MIDI track's as PAGE.NAME (NOTE, LFO, ARP, CTL1, CTL2), a setup slot
    that repeats a page-1 name with '#' (CTL1.CC1#: the CC number), the
    enable bitmaps CTL1.ON and CTL2.ON (raw bytes)."""
    out = []
    def add(key, name, E, s):
        n, lo, cnt, en = _desc(img, E, s)
        name = name or n
        if name in {x[1] for x in out}:     # a page-2 slot named as a page-1 one (LEN, RATE, VOL)
            name += "2"
        if en and cnt > 0:
            out.append((key, name, lo, cnt))
    if target in MACHINES:
        for s in range(12):
            add(1 + s, None, _D["playback"] + 0x192 * MACHINES.index(target), s)
    elif target == "amp":
        for s in range(12):
            add(1 + s, None, _D["amp"], s)
    elif target == "lfo":
        for s in range(6):
            add(1 + s, None, _D["lfo"], s)
        for i, nm in enumerate(("PMTR", "WAVE", "MULT", "TRIG")):
            for k in range(3):
                add(7 + 3 * i + k, f"{nm}{k + 1}", _D["lfo"], 6 + i)
    elif target == "midi":
        for f in range(30):
            pg, d = _MIDI_PAGES[f // 6]
            add(64 + f, f"{pg}.{_desc(img, _D[d], f % 6)[0]}", _D[d], f % 6)
        out += [(94, "CTL1.ON", 0, 256), (95, "CTL2.ON", 0, 256)]
        taken = {n for _k, n, _l, _c in out}
        for o in range(30):
            pg, d = _MIDI_PAGES[o // 6]
            if pg == "LFO":                 # PMTR x3, WAVE x3: one descriptor slot per kind
                add(1 + o, f"LFO.{('PMTR', 'WAVE')[(o - 6) // 3]}{(o - 6) % 3 + 1}", _D[d], 6 + (o - 6) // 3)
                continue
            nm = f"{pg}.{_desc(img, _D[d], 6 + o % 6)[0]}"
            add(1 + o, nm + "#" if nm in taken else nm, _D[d], 6 + o % 6)
        for i, nm in enumerate(("MULT", "TRIG")):
            for k in range(3):
                add(31 + 3 * i + k, f"LFO.{nm}{k + 1}", _D["mlfo"], 8 + i)
    return out


# ---- refusals -------------------------------------------------------------

def check_modules(mods) -> list[str]:
    """Registry-wide: two modules with one store id."""
    seen, bad = {}, []
    for m in mods.values():
        st = getattr(m, "store", None)
        if st is None:
            continue
        if st.id in seen:
            bad.append(f"store id {st.id!r}: {seen[st.id]} and {m.name}")
        seen[st.id] = m.name
    return bad


def _free_run(remix, mods) -> tuple[int, int]:
    """(start, length) of CS1_FREE's largest run after the selected
    modules' Claims.sram; the CS1 block's home (BRAIN.md section 6.4)."""
    lo, hi = CS1_FREE
    taken = sorted((b, b + n) for m in _selected(remix, mods) if m.claims
                   for b, n, _w in m.claims.sram if b < hi and b + n > lo)
    best, at, start = 0, lo, lo
    for b, e in taken:
        if b - at > best:
            best, start = b - at, at
        at = max(at, e)
    if hi - at > best:
        best, start = hi - at, at
    return start, best


def early_budget(remix, mods) -> int:
    """Bytes of early values the remix's CS1 block can hold: the largest free
    run of CS1_FREE after every selected module's Claims.sram, less the
    block header."""
    return max(0, _free_run(remix, mods)[1] - EARLY_HEADER)


def early_settings(remix, mods) -> list[tuple[object, object]]:
    """(module, Setting) of every early setting the CS1 block carries: the
    remix has the brain, and the value is neither pinned nor build-time."""
    if not has_brain(remix):
        return []
    return [(m, s) for r, s in resolve(remix, mods) for m in [mods[r.module]]
            if s.early and r.runtime]


def early_layout(remix, mods) -> tuple[int, dict[tuple[str, int], int]]:
    """(base, {(store id, key): CS1 offset}) of the early block: the values
    at `base` + EARLY_HEADER in early_settings order, one s.size bytes each.
    settings_inc emits each entry's offset into its brain_set[] row, so
    brain.c's writer needs only the base (defsym CS1_EARLY_BASE)."""
    base, _run = _free_run(remix, mods)
    offs, at = {}, base + EARLY_HEADER
    for m, s in early_settings(remix, mods):
        offs[(m.store.id, s.key)] = at
        at += s.size
    return base, offs


def check_remix(remix, mods) -> list[str]:
    """Every refusal of BRAIN.md section 4.3 that needs the remix."""
    bad = []
    sel = _selected(remix, mods)
    if not has_brain(remix):
        for m in sel:
            if m.requires_brain:
                bad.append(f"{m.name}: its function is stored state and the remix "
                           f"does not carry {BRAIN_KEY}")
    owners = _owners(remix, mods)
    for entry, given in remix.settings.items():
        if not (isinstance(entry, tuple) and len(entry) == 2):
            bad.append(f"settings entry {entry!r}: (store id, setting name)")
            continue
        sid, name = entry
        m = owners.get(sid)
        if m is None:
            bad.append(f"settings {entry!r}: no selected module files settings under {sid!r}")
            continue
        s = next((s for s in m.settings if s.name == name), None)
        if s is None:
            bad.append(f"settings {entry!r}: {m.name} has no setting {name!r} "
                       f"(has {', '.join(x.name for x in m.settings) or 'none'})")
            continue
        value = given.value if isinstance(given, Pin) else given
        if isinstance(s.kind, Trigger):
            bad.append(f"settings {entry!r}: a Trigger holds no value")
            continue
        why = s.kind.check(value)
        if why:
            bad.append(f"settings {entry!r}: {why}")
    bad += check_defaults(remix, mods)
    if has_brain(remix) and not bad:
        need = sum(s.size for _m, s in early_settings(remix, mods))
        room = early_budget(remix, mods)
        if need > room:
            bad.append(f"early settings take {need} bytes; the free CS1 run of this "
                       f"remix holds {room} after the {EARLY_HEADER}-byte header")
    return bad


def report(remix, mods) -> list[str]:
    """The build report's settings section: every setting and remix knob
    default with its value and layer. Empty when there is neither."""
    rows = resolve(remix, mods)
    if not rows and not remix.defaults:
        return []
    # The report text is API (trap-report-api): the cited file is removed, the text stays.
    out = ["=== Settings: resolved at build (docs/proposals/" "BRAIN.md) ==="]
    for r, s in rows:
        where = "card/project at run time" if r.runtime else "fixed in the image"
        out.append(f"  {r.store_id} {r.name} = {r.shown(s)}  ({r.layer}; {where})")
    for (key, mode, knob), v in remix.defaults.items():
        out.append(f"  {key} {knob}{'' if mode is None else ' in ' + str(mode)} default = {v}  (remix)")
    return out


# ---- the lock file (BRAIN.md section 4.4) ---------------------------------

def needs_lock(m) -> bool:
    return m.store is not None or any(p.key is not None for p in m.params)


def _kind_lock(k) -> dict:
    if isinstance(k, Binary):
        return {"type": "binary"}
    if isinstance(k, Option):
        return {"type": "option", "labels": list(k.labels)}
    if isinstance(k, Number):
        return {"type": "number", "min": k.min, "max": k.max, "step": k.step}
    if isinstance(k, Trigger):
        return {"type": "trigger"}
    return {"type": "blob", "max_bytes": k.max_bytes}


def lock_of(m, retired=None) -> dict:
    """The lock file's content for a module as declared now."""
    retired = retired or {"settings": [], "params": []}
    return {
        "store": None if m.store is None else {"id": m.store.id, "major": m.store.major},
        "settings": {str(s.key): {"name": s.name, **_kind_lock(s.kind)}
                     for s in sorted(m.settings, key=lambda s: s.key)},
        "params": {str(p.key): {"slot": i, "count": p.count}
                   for i, p in enumerate(m.params) if p.key is not None},
        "retired": {"settings": sorted(retired["settings"]),
                    "params": sorted(retired["params"])},
    }


def lock_path(m) -> pathlib.Path:
    return ROOT / "modules" / m.name / LOCK


def read_lock(m) -> dict | None:
    p = lock_path(m)
    return json.loads(p.read_text()) if p.exists() else None


def breaks(old: dict, new: dict) -> list[str]:
    """What `new` does to released keys that the lock refuses."""
    bad = []
    major_up = (new["store"] or {}).get("major", 1) > (old["store"] or {}).get("major", 1)
    if old["store"] and new["store"] and old["store"]["id"] != new["store"]["id"]:
        bad.append(f"store id {old['store']['id']!r} became {new['store']['id']!r}")
    for part in ("settings", "params"):
        retired = set(old["retired"][part])
        kept_retired = set(new["retired"][part])
        for k in retired - kept_retired:
            bad.append(f"{part} key {k} was retired and is no longer listed as retired")
        for k in sorted({int(x) for x in new[part]} & (retired | kept_retired)):
            bad.append(f"{part} key {k} was retired and is in use again")
        for k, was in old[part].items():
            now = new[part].get(k)
            if now is None:
                if int(k) not in kept_retired:
                    bad.append(f"{part} key {k} ({was.get('name', 'slot ' + str(was.get('slot')))}) "
                               f"was removed: retire it (brain.py lock <module> "
                               f"--retire{'' if part == 'settings' else '-param'} {k})")
                continue
            if part == "params":
                continue
            if now["type"] != was["type"] and not major_up:
                bad.append(f"setting {k} {was['name']!r} changed type {was['type']} -> "
                           f"{now['type']}: a new key, or a new store major")
            if was["type"] == "option" and now["type"] == "option":
                old_l, new_l = was["labels"], now["labels"]
                if new_l[:len(old_l)] != old_l:
                    bad.append(f"setting {k} {was['name']!r}: labels {old_l} became "
                               f"{new_l}; append only")
    return bad


def check_lock(m) -> list[str]:
    """A module that needs a lock has one, it matches the manifest, and the
    manifest breaks nothing it released."""
    if not needs_lock(m):
        return [f"{m.name}: {LOCK} without a store or a keyed param"] \
            if lock_path(m).exists() else []
    old = read_lock(m)
    if old is None:
        return [f"{m.name}: no {LOCK}: python3 tools/remix/brain.py lock {m.name}"]
    new = lock_of(m, old["retired"])
    bad = [f"{m.name}: {b}" for b in breaks(old, new)]
    if not bad and new != old:
        bad.append(f"{m.name}: {LOCK} is stale: python3 tools/remix/brain.py lock {m.name}")
    return bad


def write_lock(m, retire=(), retire_param=()) -> list[str]:
    old = read_lock(m) or {"store": None, "settings": {}, "params": {},
                           "retired": {"settings": [], "params": []}}
    retired = {"settings": sorted(set(old["retired"]["settings"]) | set(retire)),
               "params": sorted(set(old["retired"]["params"]) | set(retire_param))}
    new = lock_of(m, retired)
    bad = breaks(old, new)
    if bad:
        return bad
    lock_path(m).write_text(json.dumps(new, indent=1, sort_keys=True) + "\n")
    return []


# ---- CLI ------------------------------------------------------------------

def main(argv):
    from remix import registry
    if len(argv) < 2 or argv[1] not in ("resolve", "check", "lock", "image-name"):
        print(__doc__.strip())
        return 2
    if argv[1] == "image-name":      # the Makefile's IMAGE_NAME: image-name <remix> <build>
        print(image_name(argv[2], argv[3]))
        return 0
    mods = registry.modules()
    if argv[1] == "resolve":
        r = registry.remix(argv[2] if len(argv) > 2 else None)
        bad = check_remix(r, mods)
        if bad:
            print("\n".join(bad))
            return 1
        rows = resolve(r, mods)
        print(f"{r.name}: {len(rows)} settings, core {'in' if has_brain(r) else 'absent'}")
        for res, s in rows:
            where = "run time" if res.runtime else "build"
            print(f"  {res.store_id:28s} {res.key:5d} {res.name:16s} "
                  f"{res.shown(s):12s} {res.layer:8s} {where}")
        return 0
    if argv[1] == "check":
        bad = check_modules(mods)
        for m in mods.values():
            bad += check_lock(m)
        for name in registry.remix_names():
            bad += [f"remix {name}: {b}" for b in check_remix(registry.remix(name), mods)]
        print("\n".join(bad) if bad else
              f"brain: {sum(needs_lock(m) for m in mods.values())} locked modules, "
              f"{len(registry.remix_names())} remixes, 0 problems")
        return 1 if bad else 0
    # lock
    args = argv[2:]
    if not args:
        print("brain.py lock <module> [--retire KEY ...] [--retire-param KEY ...]")
        return 2
    m = registry.by_name(args[0])
    retire, retire_param, cur = [], [], None
    for a in args[1:]:
        if a in ("--retire", "--retire-param"):
            cur = retire if a == "--retire" else retire_param
        elif cur is not None:
            cur.append(int(a))
        else:
            print(f"unexpected argument {a!r}")
            return 2
    if not needs_lock(m):
        print(f"{m.name}: no store and no keyed param, so no lock")
        return 1
    bad = write_lock(m, retire, retire_param)
    print("\n".join(f"{m.name}: {b}" for b in bad) if bad else f"wrote {lock_path(m).relative_to(ROOT)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
