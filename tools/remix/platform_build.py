"""octabam's platform runtime: every DRAM unit in the remix, linked as one
image, packed, and appended after the OS behind the loader (loader.S)
together with any other payload -- Em's Kit runtime -- as equals.

Placement (docs/remixer/PLACEMENT.md): the runtime and its stage live in
a RESERVE carved off the bottom of stock's audio page arena
(tools/remix/arena.py) -- the one DRAM placement with a hardware record
(Octakit's top 528 pages, octamax's bottom 64), 1,707 pages = 10 MiB by
default. The build hands `build()` the reserve; the runtime is linked at
its base and the stage (signature + packed stream) sits after the
runtime image, page-aligned. Two earlier homes are RETRACTED: "8.8 MB
free at 0x47700000" (the delay rings, cleared through the uncached alias
~38 M instructions after the boot detour returns) and the ~101 KB above
the rings (stock's engine task keeps its sector bounce buffers there and
fills 0x47fc8fe4.. at project load when static samples are present).
Octakit's stage stays at HER address (0x47fc7410) because her post-clear
relocation re-depacks from exactly there -- her call. The uncached alias
(+0x08000000) is what the loader writes through, as hers does.

One link for all DRAM units means cross-unit symbols resolve without any
--defsym; other payloads' symbols (her gk_*) are offered as defsyms so a
unit may call into them. The loader itself is assembled here with the
payload table and blobs `.incbin`'d after it, so every address in the
append is the assembler's, not arithmetic in Python.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

from remix import runtime_build

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


def link_runtime(units, work: pathlib.Path, defsyms: dict, base: int) -> tuple[bytes, dict]:
    """Assemble every (module key, Linked) unit and link them together at
    `base`. Returns (raw image, symbols)."""
    work.mkdir(parents=True, exist_ok=True)
    objs = []
    for i, (key, u) in enumerate(units):
        obj = work / f"{i:02d}_{u.label}.o"
        _run(["m68k-elf-as", f"-mcpu={u.cpu}", "-o", obj, ROOT / u.source], work)
        objs.append(obj)
    elf, raw = work / "runtime.elf", work / "runtime.bin"
    _run(["m68k-elf-ld", f"-Ttext=0x{base:x}",
          *[f"--defsym={n}=0x{v:x}" for n, v in defsyms.items()], "-o", elf, *objs], work)
    _run(["m68k-elf-objcopy", "-O", "binary", elf, raw], work)
    return raw.read_bytes(), _nm(elf, work)


def build(units, payloads, work: pathlib.Path, reserve=None):
    """units: [(module key, Linked)] with dram=True, in link order.
    payloads: [dict(name, blob, stage, dst, rawlen, rhash, backup)] for
    payloads built elsewhere (Octakit): `blob` = signature + GKA3 stream.
    reserve: (base, size) of the arena reserve the runtime lives in;
    required when there are units. Returns (append bytes, symbols of the
    octabam runtime, boot poke, payload names) and writes LAYOUT."""
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
        raw, symbols = link_runtime(units, work / "runtime", defs, base)
        packed = runtime_build.PACKED_MAGIC + len(raw).to_bytes(4, "big") + \
            runtime_build.pack(raw, MAX_CANDIDATES)
        stage = (base + len(raw) + STAGE_ALIGN - 1) & ~(STAGE_ALIGN - 1)
        stage_end = stage + 4 + len(packed)
        if stage_end > ceiling:
            sys.exit(f"platform build: the runtime does not fit its arena reserve -- raw "
                     f"{len(raw):,} B at 0x{base:08x}, stage 0x{stage:08x}..0x{stage_end:08x}, "
                     f"ceiling 0x{ceiling:08x} ({size:,} B). Reserve more pages "
                     f"(tools/remix/arena.py PLATFORM_PAGES).")
        entries.append(dict(name="octabam", blob=SIGNATURE + packed,
                            stage=stage + UNCACHED, dst=base + UNCACHED,
                            rawlen=len(raw), rhash=roll(raw), backup=0))
        (work / "runtime.raw").write_bytes(raw)
        layout.update(base=base, runtime_end=base + len(raw), stage=stage,
                      stage_end=stage_end, ceiling=ceiling, size=size)
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
    o, e, b = work / "loader.o", work / "loader.elf", work / "append.bin"
    _run(["m68k-elf-as", "-mcpu=5475", "-I", work, "-o", o, ROOT / "tools/remix/loader.S"], work)
    _run(["m68k-elf-ld", f"-Ttext=0x{LOADER_AT:x}", "-o", e, o], work)
    _run(["m68k-elf-objcopy", "-O", "binary", e, b], work)
    append = b.read_bytes()
    # the boot site's stock `jsr 0x40001e50`, redirected to the loader; only
    # needed when no other payload's own writes already route boot here
    boot_poke = (0x4000050C, bytes.fromhex("4eb940001e50"),
                 b"\x4e\xb9" + LOADER_AT.to_bytes(4, "big"), "boot -> octabam loader")
    return append, symbols, boot_poke, [e["name"] for e in entries]
