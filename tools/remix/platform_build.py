"""octabam's platform runtime: every DRAM unit in the remix, linked as one
image, packed, and appended after the OS behind the loader (loader.S)
together with any other payload -- Em's Kit runtime -- as equals.

Placement (measured 9 Sep 2026 with the ColdFire port; docs/remixer/
PLACEMENT.md): the DRAM stock never writes is the ~101 KB between the end
of its boot-time delay-ring clear (0x47fc7410) and the 128 KiB it keeps
below the reset stack pointer (0x47fe0000) -- the constants below. An
earlier "8.8 MB free at 0x47700000" was a measurement blind to writes
made through the uncached alias and is RETRACTED; that run is the delay
ring, cleared ~38 M instructions after the boot detour returns. Octakit's
stage stays at HER address (0x47fc7410, signature + stream) because her
post-clear relocation re-depacks from exactly there; ours sits above it.
The uncached alias (+0x08000000) is what the loader writes through, as
hers does.

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
# THE WINDOW, measured 9 Sep 2026 under the ColdFire port: stock clears
# 0x47502c10..0x47fc7410 (its delay ring, 10.8 MB, through the uncached
# alias) at instruction ~42 M of boot -- some 38 M instructions AFTER the
# boot detour has returned -- and zero-fills 0x42000000..0x45ffffff (64 MB)
# at boot and again at project load. Anything depacked into either at boot
# is gone by the time the OS is up. The DRAM that is never written is the
# run between the end of that clear and the 128 KiB Em keeps below the
# reset stack pointer: 0x47fc7410..0x47fe0000, ~101 KB, of which her stage
# takes the first 72,959 bytes when Octakit is in the image. octabam's
# stage and runtime sit above hers, at fixed addresses whatever the remix:
STAGE_BASE = 0x47FD9200         # our persistent stage (signature + GKA3 stream)
RUNTIME_BASE = 0x47FDB000       # our window; ceiling 0x47fe0000 (~20 KB)
CEILING = 0x47FE0000
UNCACHED = 0x08000000
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


def link_runtime(units, work: pathlib.Path, defsyms: dict) -> tuple[bytes, dict]:
    """Assemble every (module key, Linked) unit and link them together at
    RUNTIME_BASE. Returns (raw image, symbols)."""
    work.mkdir(parents=True, exist_ok=True)
    objs = []
    for i, (key, u) in enumerate(units):
        obj = work / f"{i:02d}_{u.label}.o"
        _run(["m68k-elf-as", f"-mcpu={u.cpu}", "-o", obj, ROOT / u.source], work)
        objs.append(obj)
    elf, raw = work / "runtime.elf", work / "runtime.bin"
    _run(["m68k-elf-ld", f"-Ttext=0x{RUNTIME_BASE:x}",
          *[f"--defsym={n}=0x{v:x}" for n, v in defsyms.items()], "-o", elf, *objs], work)
    _run(["m68k-elf-objcopy", "-O", "binary", elf, raw], work)
    return raw.read_bytes(), _nm(elf, work)


def build(units, payloads, work: pathlib.Path):
    """units: [(module key, Linked)] with dram=True, in link order.
    payloads: [dict(name, blob, stage, dst, rawlen, rhash, backup)] for
    payloads built elsewhere (Octakit): `blob` = signature + GKA3 stream.
    Returns (append bytes, symbols of the octabam runtime, boot poke)."""
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    entries = list(payloads)
    symbols = {}
    if units:
        defs = {}
        for p in payloads:
            defs.update(p.get("symbols", {}))
        raw, symbols = link_runtime(units, work / "runtime", defs)
        packed = runtime_build.PACKED_MAGIC + len(raw).to_bytes(4, "big") + \
            runtime_build.pack(raw, MAX_CANDIDATES)
        stage_end = STAGE_BASE + 4 + len(packed)
        if stage_end > RUNTIME_BASE or RUNTIME_BASE + len(raw) > CEILING:
            sys.exit(f"platform build: the runtime does not fit the never-cleared window -- "
                     f"packed {len(packed):,} B (stage 0x{STAGE_BASE:08x}..0x{stage_end:08x}, "
                     f"must end by 0x{RUNTIME_BASE:08x}), raw {len(raw):,} B at "
                     f"0x{RUNTIME_BASE:08x} (ceiling 0x{CEILING:08x}). Bigger payloads need "
                     f"a cleared window plus a post-clear reload hook, as Octakit does "
                     f"(docs/remixer/PLACEMENT.md)")
        entries.append(dict(name="octabam", blob=SIGNATURE + packed,
                            stage=STAGE_BASE + UNCACHED, dst=RUNTIME_BASE + UNCACHED,
                            rawlen=len(raw), rhash=roll(raw), backup=0))
        (work / "runtime.raw").write_bytes(raw)
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
