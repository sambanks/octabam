"""Build a loader-appended DRAM runtime from its recipe (schema.Runtime).

The recipe is emuyia/ems-octakit's `firmware.json` (interface_version 1),
read from a git submodule so the author keeps developing in her own repo.
This module re-implements the OS-image half of her `build.py` in the shape
octabam already speaks -- fixed-address writes asserted against stock
before they land, plus an append -- and re-derives every identity her
recipe pins. Nothing here needs her Rust patcher: it existed to apply this
same recipe in a browser, and octabam's own image pipeline
(`elektron-firmware-tool`) already packs and wraps a grown OS section.

Toolchain: m68k-elf-gcc/as/ld/objcopy (`make setup`, Homebrew bottle).
Her recipe pins gcc 16.1.0; the pin is not enforced here because the
rebuilt runtime's sha256 is the stronger check and 16.2.0 reproduces her
bytes exactly (measured 9 Sep 2026). A compiler that does NOT reproduce
them fails that check with both digests in the message.

What the build does, in order, each step verified against the recipe:
  1. slice Elektron's own routines out of the USER'S stock image (copied or
     PC-relative-relocated per `stock_operations`) into work/stock/NNNN.bin
     -- the `.S` sources `.incbin` them, so the repo carries none of them;
  2. assemble/compile every listed source, link with her linker script,
     extract `.runtime`  -> must match `append.runtime.raw`;
  3. pack it with the firmware's own aPLib variant (her encoder, ported
     below, deterministic)  -> must match `append.runtime.packed`;
  4. link again with the packed blob and its rolling hash, extract
     `.early`+`.stage`  -> must match `append` (loader + stage + runtime);
  5. hand the caller the sparse writes (each guard's sha256 checked against
     stock, each write's expect bytes taken FROM stock) and the append.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

TOOLS = ("m68k-elf-gcc", "m68k-elf-as", "m68k-elf-ld", "m68k-elf-objcopy")

# ---- her packer: the firmware's aPLib variant, ported from patcher/src/lib.rs
MAX_OFFSET_FOR_LEN2 = 0x0D00
MAX_MATCH_LEN = 0x8000
HASH3_BITS = 20
HASH3_SIZE = 1 << HASH3_BITS
HASH3_MASK = HASH3_SIZE - 1
HASH2_SIZE = 1 << 16
PACKED_MAGIC = b"GKA3"


def _hash3(b, i):
    key = (b[i] << 16) | (b[i + 1] << 8) | b[i + 2]
    return ((key * 2654435761) & 0xFFFFFFFF) >> (32 - HASH3_BITS) & HASH3_MASK


def _hash2(b, i):
    return (b[i] << 8) | b[i + 1]


def _match_length(data, cand, pos):
    offset = pos - cand
    limit = min(len(data) - pos, MAX_MATCH_LEN)
    direct = min(offset, limit)
    n = 0
    while n < direct and data[cand + n] == data[pos + n]:
        n += 1
    if n == direct and n < limit:
        while n < limit and data[cand + (n % offset)] == data[pos + n]:
            n += 1
    return n


def _greedy_parse(data, max_candidates):
    if not data:
        return []
    head3 = [-1] * HASH3_SIZE
    head2 = [-1] * HASH2_SIZE
    chain3 = [-1] * len(data)
    chain2 = [-1] * len(data)
    ops = []
    pos = 0
    n = len(data)
    while pos < n:
        best_off = best_len = 0
        if pos + 2 < n:
            cand = head3[_hash3(data, pos)]
            tried = 0
            while cand >= 0 and tried < max_candidates:
                off = pos - cand
                length = _match_length(data, cand, pos)
                minimum = 3 if off > MAX_OFFSET_FOR_LEN2 else 2
                if length >= minimum and length > best_len:
                    best_off, best_len = off, length
                    if best_len == MAX_MATCH_LEN:
                        break
                cand = chain3[cand]
                tried += 1
        if best_len < 2 and pos + 1 < n:
            cand = head2[_hash2(data, pos)]
            if cand >= 0 and pos - cand <= MAX_OFFSET_FOR_LEN2:
                best_off, best_len = pos - cand, 2
        if best_len >= 2:
            ops.append((best_off, best_len))
            advance = best_len
        else:
            ops.append(data[pos])
            advance = 1
        end = pos + advance
        while pos < end:
            if pos + 1 < n:
                k = _hash2(data, pos); chain2[pos] = head2[k]; head2[k] = pos
            if pos + 2 < n:
                k = _hash3(data, pos); chain3[pos] = head3[k]; head3[k] = pos
            pos += 1
    return ops


def _gamma_bits(value):
    assert value >= 2
    highest = value.bit_length() - 1
    bits = []
    for i in range(highest - 1, -1, -1):
        bits.append((value >> i) & 1)
        bits.append(1 if i == 0 else 0)
    return bits


def _length_bits(length_read):
    if length_read == 1:
        return [0, 1]
    if length_read == 2:
        return [1, 0]
    if length_read == 3:
        return [1, 1]
    assert length_read > 3
    return [0, 0] + _gamma_bits(length_read - 2)


def pack(data: bytes, max_candidates: int) -> bytes:
    """Deterministic aPLib-variant stream, bit-identical to her encoder."""
    tag_bits: list[int] = []
    emissions: list[tuple[int, int]] = []
    last_offset = None
    for op in _greedy_parse(data, max_candidates):
        if isinstance(op, int):
            tag_bits.append(1)
            emissions.append((len(tag_bits) - 1, op))
            continue
        offset, length = op
        tag_bits.append(0)
        if last_offset == offset:
            tag_bits.extend(_gamma_bits(2))
        else:
            raw = offset - 1
            tag_bits.extend(_gamma_bits((raw + 0x300) // 0x100))
            emissions.append((len(tag_bits) - 1, (raw + 0x300) % 0x100))
        tag_bits.extend(_length_bits(length - (2 if offset > MAX_OFFSET_FOR_LEN2 else 1)))
        last_offset = offset
    tag_bits.append(0)
    tag_bits.extend(_gamma_bits(0x01000002))
    emissions.append((len(tag_bits) - 1, 0xFF))
    while len(tag_bits) % 8:
        tag_bits.append(0)
    out = bytearray()
    ei = 0
    for g in range(0, len(tag_bits), 8):
        tag = 0
        for i in range(8):
            tag |= tag_bits[g + i] << (7 - i)
        out.append(tag)
        while ei < len(emissions) and emissions[ei][0] < g + 8:
            out.append(emissions[ei][1])
            ei += 1
    assert ei == len(emissions)
    return bytes(out)


# ---- the recipe ----------------------------------------------------------

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _verify(label: str, data: bytes, ident: dict) -> None:
    got = {"size": len(data), "sha256": _sha(data)}
    want = {"size": ident["size"], "sha256": ident["sha256"]}
    if got != want:
        sys.exit(f"runtime build: {label} differs from the recipe --\n"
                 f"  got  {got['size']} B {got['sha256']}\n"
                 f"  want {want['size']} B {want['sha256']}")


def extract_stock(stock: bytes, op: dict, load: int, runtime_load: int) -> bytes:
    """One of Elektron's own routines, copied or relocated into the runtime."""
    start, length = op["source_offset"], op["source_length"]
    src = stock[start:start + length]
    if op["kind"] == "stock-copy":
        out = src
    elif op["kind"] == "m68k-relocate":
        lengths = op["instruction_lengths"]
        policy = op["policy"]
        if sum(lengths) != length or any(n <= 0 or n % 2 for n in lengths):
            sys.exit("runtime build: invalid instruction relocation in recipe")
        buf = bytearray()
        cur = 0
        for n in lengths:
            ins = src[cur:cur + n]
            opcode = int.from_bytes(ins[:2], "big")
            if policy == "preserve-absolute-control-flow" and n == 4 and opcode in (0x4EBA, 0x4EFA):
                absolute = load + start + cur + 2 + int.from_bytes(ins[2:], "big", signed=True)
                disp = absolute - (runtime_load + op["target_offset"] + len(buf) + 2)
                if -32768 <= disp <= 32767:
                    buf += ins[:2] + disp.to_bytes(2, "big", signed=True)
                else:
                    buf += (0x4EB9 if opcode == 0x4EBA else 0x4EF9).to_bytes(2, "big")
                    buf += absolute.to_bytes(4, "big")
            else:
                buf += ins
            cur += n
        out = bytes(buf)
    else:
        sys.exit(f"runtime build: unsupported stock operation {op['kind']!r}")
    if len(out) != op["target_length"]:
        sys.exit("runtime build: stock extraction length differs from the recipe")
    return out


def writes(spec: dict, stock: bytes) -> list[tuple[int, bytes, bytes, str]]:
    """(vaddr, expect, write, name): every sparse write, with its guard's
    sha256 checked against STOCK and expect taken from stock -- the same
    assert-before-write discipline as a CavePatch poke."""
    base = spec["format"]["os_load_address"]
    out = []
    prev_end = 0
    for p in sorted(spec["patches"], key=lambda p: p["offset"]):
        s, e = p["offset"], p["offset"] + p["length"]
        if s < prev_end or e <= s or e > len(stock):
            sys.exit(f"runtime build: guard {p['name']} overlaps or exceeds the image")
        if _sha(stock[s:e]) != p["sha256"]:
            sys.exit(f"runtime build: guard {p['name']} at 0x{base + s:08x} is not stock")
        wend = s
        for w in p["writes"]:
            data = bytes.fromhex(w["data"])
            pos = w["offset"]
            if not data or pos < wend or pos + len(data) > e:
                sys.exit(f"runtime build: write in {p['name']} exceeds its guard")
            expect = stock[pos:pos + len(data)]
            if any(a == b for a, b in zip(expect, data)):
                sys.exit(f"runtime build: write in {p['name']} keeps an unchanged stock byte")
            out.append((base + pos, expect, data, p["name"]))
            wend = pos + len(data)
        prev_end = e
    return out


def _run(args, cwd):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"runtime build: {args[0]} failed on {args[-1]}\n{r.stderr[-3000:]}")
    return r.stdout


def _regenerate(ws, old: dict, new: dict):
    """The host's OS-resident helpers bake five constants derived from the
    built runtime (schema.RuntimeExt): substitute the host's values for the
    composite's in the recipe's writes. Each value occurs exactly once in
    her recipe (measured), so a count other than one is an error."""
    out = []
    counts = {k: 0 for k in old}
    for va, expect, write, name in ws:
        w = bytearray(write)
        for k in old:
            o, n = old[k].to_bytes(4, "big"), new[k].to_bytes(4, "big")
            i = w.find(o)
            while i >= 0:
                w[i:i + 4] = n
                counts[k] += 1
                i = w.find(o, i + 4)
        out.append((va, expect, bytes(w), name))
    bad = {k: c for k, c in counts.items() if c != {"raw_size": 2}.get(k, 1)}
    if bad:
        sys.exit(f"runtime build: helper constants found {bad} times, not once "
                 f"(raw_size twice) -- the host's recipe changed shape; refusing")
    return out


def build(rt, stock: bytes, work: pathlib.Path, extensions=()) -> tuple[list, bytes, dict]:
    """Returns (writes, append, info). `info` carries the identities and
    the gcc version actually used, for the build report. `extensions` =
    (module key, schema.RuntimeExt) pairs linked into this runtime."""
    missing = [t for t in TOOLS if not shutil.which(t)]
    if missing:
        sys.exit(f"runtime build: missing {', '.join(missing)} -- run `make setup` "
                 f"(Homebrew: brew install m68k-elf-gcc)")
    recipe = ROOT / rt.recipe
    srcdir = ROOT / rt.sources
    spec = json.loads(recipe.read_text())
    if spec.get("interface_version") != 1:
        sys.exit(f"runtime build: {recipe} interface_version "
                 f"{spec.get('interface_version')!r}, this builder speaks 1")
    _verify("stock OS", stock, spec["source"]["os"])
    load = spec["format"]["os_load_address"]
    runtime_spec = spec["append"]["runtime"]
    runtime_load = runtime_spec["load_address"]

    work = work.resolve()          # every tool runs with cwd=work
    work.mkdir(parents=True, exist_ok=True)
    (work / "stock").mkdir(exist_ok=True)
    for i, op in enumerate(runtime_spec["stock_operations"]):
        (work / "stock" / f"{i:04d}.bin").write_bytes(extract_stock(stock, op, load, runtime_load))

    gcc_version = _run(["m68k-elf-gcc", "-dumpfullversion"], work).strip()

    def compile_one(src, obj):
        if src.suffix == ".c":
            _run(["m68k-elf-gcc", *spec["compiler"]["cflags"], "-c", "-o", obj, src], work)
        else:
            _run(["m68k-elf-as", "-march=cfv4e", "-I", srcdir, "-I", src.parent, "-o", obj, src], work)

    objects = []
    for name in spec["sources"]:
        src = srcdir / name
        if pathlib.Path(name).name != name or src.suffix not in (".S", ".c") or not src.exists():
            sys.exit(f"runtime build: bad source {name!r} in {recipe}")
        obj = work / (src.stem + ".o")
        compile_one(src, obj)
        objects.append(obj)
    # ---- extensions: other modules' sources, into THIS runtime ------------
    ext_keys = []
    budget = None
    for key, ext in extensions:
        ext_keys.append(key)
        if ext.code_budget is not None:
            budget = max(budget or 0, ext.code_budget)
        for i, name in enumerate(ext.sources):
            src = ROOT / name
            if not src.exists() or src.suffix not in (".S", ".s", ".c"):
                sys.exit(f"runtime build: {key}: bad extension source {name!r}")
            obj = work / f"ext_{key.replace(' ', '_')}_{i}_{src.stem}.o"
            compile_one(src, obj)
            objects.append(obj)
    ldscript = srcdir / "link.ld"
    if budget is not None:
        # The host's code budget is one assignment in her linker script and
        # is not PROVIDE()d, so it cannot be overridden from the command
        # line; rewrite that line in a scratch copy. Until the host makes it
        # overridable upstream, this is the seam -- and it is printed.
        text = ldscript.read_text()
        import re
        new_text, n = re.subn(r"RUNTIME_CODE_BUDGET = 1\n(?:.*\n)*?.*?;\n",
                              f"RUNTIME_CODE_BUDGET = 0x{budget:x};\n", text, count=1)
        if n != 1:
            sys.exit("runtime build: could not find RUNTIME_CODE_BUDGET in the host's link.ld")
        ldscript = work / "link.ld"
        ldscript.write_text(new_text)
    ld = ["m68k-elf-ld", "-T", ldscript]
    elf, raw = work / "runtime.elf", work / "runtime.bin"
    _run([*ld, "--defsym", "GK_PACKED_RUNTIME_HASH=0", "-o", elf, *objects], work)
    _run(["m68k-elf-objcopy", "-O", "binary", "-j", ".runtime", elf, raw], work)
    runtime = raw.read_bytes()
    extended = bool(ext_keys)
    if not extended:
        _verify(f"rebuilt runtime (m68k-elf-gcc {gcc_version}, recipe pins "
                f"{spec['compiler']['gcc_version']})", runtime, runtime_spec["raw"])
    for op in runtime_spec["stock_operations"]:
        s = op["target_offset"]
        if runtime[s:s + op["target_length"]] != extract_stock(stock, op, load, runtime_load):
            sys.exit("runtime build: a stock routine inside the runtime differs from its slice")

    packed = PACKED_MAGIC + len(runtime).to_bytes(4, "big") + pack(runtime, spec["build"]["max_candidates"])
    if not extended:
        _verify("packed runtime", packed, runtime_spec["packed"])
    packed_path = work / "packed.bin"
    packed_path.write_bytes(packed)
    packed_obj = work / "packed.o"
    _run(["m68k-elf-objcopy", "-I", "binary", "-O", "elf32-m68k", "-B", "m68k",
          "--rename-section", ".data=.stage.packed,alloc,load,readonly,data,contents",
          packed_path, packed_obj], work)
    rolling = 0
    for b in packed:
        rolling = (rolling * 33 + b) & 0xFFFFFFFF
    _run([*ld, "--defsym", f"GK_PACKED_RUNTIME_HASH={rolling}", "-o", elf, *objects, packed_obj], work)
    append_path = work / "append.bin"
    _run(["m68k-elf-objcopy", "-O", "binary", "-j", ".early", "-j", ".stage", elf, append_path], work)
    append = append_path.read_bytes()
    if not extended:
        _verify("append (loader + stage + packed runtime)", append,
                {"size": spec["append"]["length"], "sha256": spec["append"]["sha256"]})
    if spec["append"]["offset"] != len(stock):
        sys.exit("runtime build: the recipe appends somewhere other than the end of the image")

    symbols = {}
    for line in _run(["m68k-elf-nm", "--defined-only", elf], work).splitlines():
        f = line.split()
        if len(f) == 3 and not f[2].startswith(".L"):
            symbols[f[2]] = int(f[0], 16)
    ws = writes(spec, stock)
    if extended:
        # The host's OS-resident helpers bake five constants derived from HER
        # runtime; the composite has its own. Measured against her recipe:
        # raw size (twice: hash helper + repair helper), raw rolling hash,
        # packed size, packed hash (post-clear relocation wrapper), backup
        # address (RUNTIME_END - raw size, repair helper). Same ×33 hash as
        # the loader's GK_PACKED_RUNTIME_HASH.
        def roll(b):
            h = 0
            for x in b:
                h = (h * 33 + x) & 0xFFFFFFFF
            return h
        # Her values: the recipe pins her raw/packed bytes by sha256, not by
        # rolling hash, so link HER sources alone once more (her script, no
        # extensions), verify against her identities, and roll those bytes.
        host_only = work / "host_only"
        host_only.mkdir(exist_ok=True)
        elf0, raw0 = host_only / "runtime.elf", host_only / "runtime.bin"
        _run(["m68k-elf-ld", "-T", srcdir / "link.ld", "--defsym", "GK_PACKED_RUNTIME_HASH=0",
              "-o", elf0, *objects[:len(spec["sources"])]], work)
        _run(["m68k-elf-objcopy", "-O", "binary", "-j", ".runtime", elf0, raw0], work)
        runtime0 = raw0.read_bytes()
        _verify("host runtime, unextended", runtime0, runtime_spec["raw"])
        packed0 = PACKED_MAGIC + len(runtime0).to_bytes(4, "big") + pack(runtime0, spec["build"]["max_candidates"])
        _verify("host packed runtime, unextended", packed0, runtime_spec["packed"])
        # backup = the UNCACHED alias of RUNTIME_END minus the runtime size
        # (her repair helper bakes 0x4e00154b = 0x4e025de0 - 0x24895)
        uncached_end = symbols["__gk_runtime_backup_uncached_start"] + len(runtime)
        old = dict(raw_size=len(runtime0), raw_hash=roll(runtime0), packed_size=len(packed0),
                   packed_hash=roll(packed0), backup=uncached_end - len(runtime0))
        new = dict(raw_size=len(runtime), raw_hash=roll(runtime), packed_size=len(packed),
                   packed_hash=roll(packed), backup=uncached_end - len(runtime))
        ws = _regenerate(ws, old, new)
    def _roll(b):
        h = 0
        for x in b:
            h = (h * 33 + x) & 0xFFFFFFFF
        return h
    info = dict(gcc=gcc_version, gcc_pinned=spec["compiler"]["gcc_version"],
                runtime_size=len(runtime), packed_size=len(packed), append_size=len(append),
                runtime_load=runtime_load, memory=spec.get("memory"), symbols=symbols,
                output_os=spec["output"]["os"], id=spec["id"], version=spec["build"]["version"],
                extended=ext_keys, code_budget=budget,
                # what octabam's loader needs to carry this runtime as a PAYLOAD:
                # her stage (signature + GKA3 stream, exactly her .stage section,
                # where her post-clear relocation re-depacks from), her window,
                # her backup, and the x33 hashes her OS-resident helpers gate on
                payload=dict(name=spec["id"],
                             blob=append[len(append) - len(packed) - 4:],
                             stage=symbols["__gk_stage_uncached_start"],
                             dst=symbols["__gk_runtime_uncached_start"],
                             rawlen=len(runtime), rhash=_roll(runtime),
                             backup=symbols["__gk_runtime_backup_uncached_start"],
                             symbols=symbols))
    return ws, append, info
