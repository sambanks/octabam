"""octabam's platform runtime: every DRAM unit in the remix, linked as one
image, packed, and appended after the OS behind the loader (loader.S)
together with any other payload as equals.

One link for all DRAM units means cross-unit symbols resolve without any
--defsym; other payloads' symbols and the units' resolved
Linked.defsyms are offered as defsyms, and each unit's own Linked.defsyms also go to its assembly. The
loader itself is assembled here with the payload table and blobs
`.incbin`'d after it, so every address in the append is the assembler's,
not arithmetic in Python.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

from remix import pack

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOADER_AT = 0x4010FDF0          # the byte after the stock OS image
UNCACHED = 0x08000000
STAGE_ALIGN = 0x1000            # the stage follows the runtime image, page-aligned
LAYOUT = "layout.json"          # written beside the append: base, runtime, stage, ceiling
SIGNATURE = b"OCTA"
MAX_CANDIDATES = 4096


def roll(b: bytes) -> int:
    h = 0
    for x in b:
        h = (h * 33 + x) & 0xFFFFFFFF
    return h


def _run(args, cwd):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"platform build: {args[0]} failed\n{r.stderr[-3000:]}")
    return r.stdout


def _nm(elf, cwd):
    rows = [l.split() for l in _run(["m68k-elf-nm", elf], cwd).splitlines()]
    return {f[2]: int(f[0], 16) for f in rows if len(f) == 3 and not f[2].startswith(".L")}


def as_defsyms(defs) -> list[str]:
    """`m68k-elf-as` arguments defining each (name, value)."""
    return [x for n, v in defs for x in ("--defsym", f"{n}=0x{v:x}")]


def redefined(obj, defs) -> list[str]:
    """Names in `defs` that the object's own source defines: the assembler
    lets a label or `.equ` silently override `--defsym`, so a declared
    name that comes back as a section symbol, or as an absolute with
    another value, is the source's own."""
    want = dict(defs)
    rows = [l.split() for l in _run(["m68k-elf-nm", obj], ROOT).splitlines()]
    return sorted(f[2] for f in rows if len(f) == 3 and f[2] in want
                  and (f[1] not in ("a", "A") or int(f[0], 16) != want[f[2]] & 0xFFFFFFFF))


def _globals_defined(units, work, includes, unit_defs) -> dict:
    """{unit label: global names the OTHER units define, None: every unit's},
    from a first assembly of each unit with its declared defsyms."""
    probe = work / "globals"
    probe.mkdir(parents=True, exist_ok=True)
    own = {}
    for i, (_key, u) in enumerate(units):
        obj = probe / f"{i:02d}_{u.label}.o"
        inc = []
        if includes and u.label in includes:
            d = probe / f"{i:02d}_{u.label}.inc"
            d.mkdir(exist_ok=True)
            (d / "remix.inc").write_text(includes[u.label])
            inc = ["-I", str(d)]
        mine = tuple((unit_defs or {}).get(u.label, ()))
        _run(["m68k-elf-as", "-mcpu=54455", *inc, "-I", ROOT, *as_defsyms(mine), "-o", obj, ROOT / u.source], probe)
        rows = [l.split() for l in _run(["m68k-elf-nm", "-g", "--defined-only", obj], ROOT).splitlines()]
        own[u.label] = {f[2] for f in rows if len(f) == 3 and f[1] not in ("A",)}
    every = set().union(*own.values()) if own else set()
    out = {label: set().union(*(s for k, s in own.items() if k != label)) if len(own) > 1 else set()
           for label in own}
    out[None] = every
    return out


def link_runtime(units, work: pathlib.Path, defsyms: dict, base: int, includes=None,
                 unit_defs=None) -> tuple[bytes, dict]:
    """Assemble every (module key, Linked) unit and link them together at
    `base`. Returns (raw image, symbols). `includes` = {unit label: text}
    for units with `Linked.include`: the text is written as `remix.inc`
    beside the unit's object and the assembler searches there.
    `unit_defs` = {unit label: ((name, value), ...)}, that unit's resolved
    Linked.defsyms, passed to its assembly."""
    work.mkdir(parents=True, exist_ok=True)
    # A declared default for a name another unit of this link defines (CC
    # MAP's CC_MODEDEF1 beside MODE DEFAULTS' label) gives way to that
    # definition: an assembly-time --defsym would bind the reference before
    # the link sees the label.
    provided = _globals_defined(units, work, includes, unit_defs)
    unit_defs = {k: tuple((n, v) for n, v in d if n not in provided.get(k, set()))
                 for k, d in (unit_defs or {}).items()}
    defsyms = {n: v for n, v in defsyms.items() if n not in provided[None]}
    objs = []
    for i, (key, u) in enumerate(units):
        obj = work / f"{i:02d}_{u.label}.o"
        inc = []
        if includes and u.label in includes:
            d = work / f"{i:02d}_{u.label}.inc"
            d.mkdir(exist_ok=True)
            (d / "remix.inc").write_text(includes[u.label])
            inc = ["-I", str(d)]
        # Every DRAM unit is assembled for the chip itself (MCF54455, ISA C).
        # GNU ld refuses to link an ISA-C object beside ISA-B ones, so one
        # unit that needs `byterev` (octemu's USB-audio producer) would force
        # the whole link, and an ISA-C assembly of ISA-A/B text is the same
        # bytes (refhash: every runtime bit-identical, 25 Sep 2026).
        # `Linked.cpu` still governs the ROM-cave form.
        mine = tuple((unit_defs or {}).get(u.label, ()))
        _run(["m68k-elf-as", "-mcpu=54455", *inc, "-I", ROOT, *as_defsyms(mine), "-o", obj, ROOT / u.source], work)
        own = redefined(obj, mine) if mine else []
        if own:
            sys.exit(f"platform build: {u.source} defines {', '.join(own)}, which its "
                     f"Linked.defsyms also declares")
        objs.append(obj)
    elf, raw = work / "runtime.elf", work / "runtime.bin"
    _run(["m68k-elf-ld", f"-Ttext=0x{base:x}",
          *[f"--defsym={n}=0x{v:x}" for n, v in defsyms.items()], "-o", elf, *objs], work)
    _run(["m68k-elf-objcopy", "-O", "binary", elf, raw], work)
    return raw.read_bytes(), _nm(elf, work)


def preboot_layout(layout, entries):
    """Declare cached-address extents and reject overlap with the runtime/stage."""
    if not entries:
        return []
    if not all(k in layout for k in ('base', 'runtime_end', 'stage', 'stage_end', 'ceiling')):
        raise ValueError('pre-boot payloads require a declared platform arena layout')
    occupied = [('runtime', layout['base'], layout['runtime_end']),
                ('runtime stage', layout['stage'], layout['stage_end'])]
    if 'bss_end' in layout:
        occupied.append(('runtime .bss', layout['runtime_end'], layout['bss_end']))
    # A module's DRAM regions (schema.DramRegion, STEM REC's ring and stack)
    # are claims on the same arena: a pre-boot payload may not land on them.
    occupied += [(f'DRAM region {sym}', a, a + n)
                 for sym, (a, n) in layout.get('regions', {}).items()]
    result = []
    for entry in entries:
        for role, length in (('dst', entry['rawlen']), ('stage', len(entry['blob']))):
            start = entry[role]
            if 0x48000000 <= start < 0x50000000:
                start -= UNCACHED
            end = start + length
            name = entry['name'] + ' ' + role
            if length <= 0 or not layout['base'] <= start < end <= layout['ceiling']:
                raise ValueError(f'pre-boot {name} lies outside the platform arena')
            for other, lo, hi in occupied:
                if start < hi and lo < end:
                    raise ValueError(f'pre-boot {name} overlaps {other}: {start:#x}..{end:#x}')
            occupied.append((name, start, end))
            result.append(dict(name=name, start=start, end=end))
    return result


def build(units, payloads, work: pathlib.Path, reserve=None, defsyms=None, preboot=(), includes=None,
          unit_defs=None, regions=(), patch=None, early=()):
    """units: [(module key, Linked)] with dram=True, in link order.
    payloads: [dict(name, blob, stage, dst, rawlen, rhash, backup)] for
    payloads built elsewhere: `blob` = signature + GKA3 stream.
    reserve: (base, size) of the arena reserve the runtime lives in;
    required when there are units. defsyms: extra {name: value} for the
    link (a bridge's continuation targets, schema.Override). preboot:
    [dict(name, blob, stage, dst, rawlen, rhash)] depacked BEFORE the
    boot-continue call (Analog BD's DSP uploads); the loader
    carries that section only when there is one. Returns
    (append bytes, symbols of the octabam runtime, boot poke, payload
    names) and writes LAYOUT. unit_defs: {unit label: resolved
    Linked.defsyms} for each unit's assembly (link_runtime). regions:
    [(symbol, size, align)] of uninitialised DRAM (schema.DramRegion),
    stacked down from the reserve's ceiling and handed to the link as
    --defsym symbol=address. patch: {address: bytes} written over the
    linked runtime before it is packed, each over bytes the link left zero
    (the build's descriptor clones, filled after every pass that writes
    them)."""
    import json
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    entries = list(payloads)
    symbols = {}
    layout = {"loader": LOADER_AT}
    if units:
        if reserve is None:
            sys.exit("platform build: DRAM units need an arena reserve (tools/remix/arena.py)")
        base, size = reserve
        ceiling = base + size
        defs = {}
        for p in payloads:
            defs.update(p.get("symbols", {}))
        defs.update(defsyms or {})
        # DramRegions: stacked down from the ceiling, named to the link.
        placed = {}
        top = ceiling
        for r_sym, r_size, r_align in regions:
            top = (top - r_size) & ~(r_align - 1)
            placed[r_sym] = (top, r_size)
        defs.update({s: a for s, (a, _) in placed.items()})
        raw, symbols = link_runtime(units, work / "runtime", defs, base, includes, unit_defs)
        if patch:
            raw = bytearray(raw)
            for p_at, p_bytes in sorted(patch.items()):
                o = p_at - base
                if not 0 <= o <= len(raw) - len(p_bytes) or any(raw[o:o + len(p_bytes)]):
                    sys.exit(f"platform build: patch at 0x{p_at:08x} ({len(p_bytes)} B) is "
                             f"not over zero bytes of the linked runtime")
                raw[o:o + len(p_bytes)] = p_bytes
            raw = bytes(raw)
            (work / "runtime" / "runtime.bin").write_bytes(raw)
        packed = pack.PACKED_MAGIC + len(raw).to_bytes(4, "big") + \
            pack.pack(raw, MAX_CANDIDATES)
        stage = (base + len(raw) + STAGE_ALIGN - 1) & ~(STAGE_ALIGN - 1)
        stage_end = stage + 4 + len(packed)
        if stage_end > ceiling:
            sys.exit(f"platform build: the runtime does not fit its arena reserve -- raw "
                     f"{len(raw):,} B at 0x{base:08x}, stage 0x{stage:08x}..0x{stage_end:08x}, "
                     f"ceiling 0x{ceiling:08x} ({size:,} B). Reserve more pages "
                     f"(tools/remix/arena.py PLATFORM_PAGES).")
        # A unit's .bss follows the image, is never loaded and holds whatever
        # the boot left (the stage sits inside it until the depack is done):
        # the unit initialises it. It has to end below the ceiling.
        bss_end = symbols.get("_end", base + len(raw))
        if bss_end > ceiling:
            sys.exit(f"platform build: the runtime's .bss ends at 0x{bss_end:08x}, past the "
                     f"reserve's ceiling 0x{ceiling:08x} ({size:,} B). Reserve more pages "
                     f"(tools/remix/arena.py PLATFORM_PAGES).")
        if placed:
            floor_sym, (floor, _) = min(placed.items(), key=lambda kv: kv[1][0])
            if max(stage_end, bss_end) > floor:
                sys.exit(f"platform build: the runtime, its stage and its .bss end at "
                         f"0x{max(stage_end, bss_end):08x}, above DRAM region {floor_sym} at "
                         f"0x{floor:08x} -- shrink the regions or reserve more pages "
                         f"(tools/remix/arena.py PLATFORM_PAGES).")
        entries.append(dict(name="octabam", blob=SIGNATURE + packed,
                            stage=stage + UNCACHED, dst=base + UNCACHED,
                            rawlen=len(raw), rhash=roll(raw), backup=0))
        (work / "runtime.raw").write_bytes(raw)
        layout.update(base=base, runtime_end=base + len(raw), stage=stage,
                      stage_end=stage_end, ceiling=ceiling, size=size)
        if bss_end > symbols.get("__bss_start", bss_end):
            layout.update(bss_end=bss_end)
        if placed:
            layout["regions"] = {s: [a, n] for s, (a, n) in placed.items()}
    if preboot:
        try:
            layout['preboot'] = preboot_layout(layout, preboot)
        except ValueError as exc:
            sys.exit(f'platform build: {exc}')
    (work / LAYOUT).write_text(json.dumps(layout, indent=2) + "\n")
    # the table and the blobs, as assembler input
    inc = [f"        .long {len(entries)}"]
    for i, e in enumerate(entries):
        (work / f"blob{i}.bin").write_bytes(e["blob"])
        inc += [f"        .long blob{i}, {len(e['blob'])}, 0x{roll(e['blob'][4:]):08x}, "
                f"0x{e['stage']:08x}, 0x{e['dst']:08x}, {e['rawlen']}, 0x{e['rhash']:08x}, "
                f"0x{e['backup']:08x}"]
    for i in range(len(entries)):
        inc += [f"        .align 4", f"blob{i}:", f"        .incbin \"blob{i}.bin\""]
    (work / "table.inc").write_text("\n".join(inc) + "\n")
    pre = [f"        .long {len(preboot)}"]
    for i, e in enumerate(preboot):
        (work / f"preblob{i}.bin").write_bytes(e["blob"])
        pre += [f"        .long preblob{i}, {len(e['blob'])}, 0x{roll(e['blob'][4:]):08x}, "
                f"0x{e['stage']:08x}, 0x{e['dst']:08x}, {e['rawlen']}, 0x{e['rhash']:08x}, 0"]
    for i in range(len(preboot)):
        pre += [f"        .align 4", f"preblob{i}:", f"        .incbin \"preblob{i}.bin\""]
    if preboot:
        (work / "pretable.inc").write_text("\n".join(pre) + "\n")
    # LOADER UNITS (schema.Linked.loader): their source, after their include
    # text, inline in the loader's one assembly -- `.include "remix.inc"`
    # is the include text itself here. Empty for every remix without one,
    # so the loader's bytes do not move for them.
    ear = []
    for u in early:
        src = (ROOT / u.source).read_text().replace('.include "remix.inc"', "")
        ear += [f"| ---- {u.label} ({u.source})", (includes or {}).get(u.label, ""), src,
                "        .text", "        .align  2"]
    (work / "early.inc").write_text("\n".join(ear) + "\n")
    o, e, b = work / "loader.o", work / "loader.elf", work / "append.bin"
    _run(["m68k-elf-as", "-mcpu=5475", "-I", work, *(["--defsym", "PREBOOT=1"] if preboot else []),
          "-o", o, ROOT / "tools/remix/loader.S"], work)
    _run(["m68k-elf-ld", f"-Ttext=0x{LOADER_AT:x}", "-o", e, o], work)
    _run(["m68k-elf-objcopy", "-O", "binary", e, b], work)
    append = b.read_bytes()
    if early:
        # the loader units' globals, for the detours that name them
        nm = subprocess.run(["m68k-elf-nm", e], capture_output=True, text=True, check=True).stdout
        for line in nm.splitlines():
            f = line.split()
            if len(f) == 3 and f[1] == "T":
                symbols.setdefault(f[2], int(f[0], 16))
    # the boot site's stock `jsr 0x40001e50`, redirected to the loader; only
    # needed when no other payload's own writes already route boot here
    boot_poke = (0x4000050C, bytes.fromhex("4eb940001e50"),
                 b"\x4e\xb9" + LOADER_AT.to_bytes(4, "big"), "boot -> octabam loader")
    return append, symbols, boot_poke, [e["name"] for e in list(preboot) + entries]
