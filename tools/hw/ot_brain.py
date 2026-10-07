#!/usr/bin/env python3
"""brain files on the computer (docs/proposals/BRAIN.md section 10).

    python3 tools/hw/ot_brain.py dump FILE              a .work, .strd or .brain file as JSON
    python3 tools/hw/ot_brain.py build JSON OUT         JSON back to a file
    python3 tools/hw/ot_brain.py pair DIR [STEM]        what the brain does with DIR/STEM.work + .strd
    python3 tools/hw/ot_brain.py default FILE REMIX MODULE KNOB=VALUE ...
                                                        a card-layer default for MODULE's page in FILE
                                                        (a card .work, created when absent); KNOB by
                                                        the name the panel shows
    python3 tools/hw/ot_brain.py default FILE REMIX MODULE --mode MODE KNOB=VALUE ...
                                                        the same for one MODE's view (MODE by its label)
    python3 tools/hw/ot_brain.py default FILE REMIX MODULE [--mode MODE] --clear

A record that does not parse, or whose kind this tool does not know, is
shown as its exact bytes in hex and written back unchanged, so `dump` then
`build` reproduces any valid file byte for byte when no value was edited.
STEM is `card` in the card's BRAIN directory and `octabam` in a project
(the default).
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from remix import brainfile  # noqa: E402

KIND_OF = {v: k for k, v in brainfile.FILE_KINDS.items()}
REC_OF = {v: k for k, v in brainfile.RECORD_KINDS.items()}
TYPE_OF = {v: k for k, v in brainfile.TYPE_NAMES.items()}


def value_json(v: brainfile.Value) -> dict:
    try:
        shown = brainfile.decode_value(v.type, v.data)
    except ValueError:
        return {"key": v.key, "type": v.type, "hex": v.data.hex()}
    if isinstance(shown, bytes):
        shown = shown.hex()
    return {"key": v.key, "type": brainfile.TYPE_NAMES[v.type], "value": shown}


def record_json(r: brainfile.Record) -> dict:
    if not r.applicable():
        return {"raw": r.encode().hex(), "kind": brainfile.RECORD_KINDS.get(r.kind, r.kind),
                "store_id": r.store_id, "note": "kept as read: not applicable"}
    out = {"kind": brainfile.RECORD_KINDS[r.kind], "store_id": r.store_id,
           "major": r.major, "minor": r.minor}
    if r.flags:
        out["flags"] = r.flags
    t = r.target()
    if r.kind in (brainfile.DEFAULT, brainfile.TEMPLATE_REC):
        out.update(target=t[0], mode=None if t[1] == brainfile.NO_MODE else t[1],
                   layout=f"{r.layout():08x}")
        if r.kind == brainfile.TEMPLATE_REC:
            out["name"] = r.name()
    elif r.kind == brainfile.FIELD_BLOCK:
        out.update(target=t[0], instance=t[1])
    if r.kind == brainfile.PROJECT_RECORD:
        out["entries"] = [{"fx_id": f"0x{e.fx_id:02x}", "store_id": e.store_id,
                           "layout": f"{e.layout:08x}"} for e in r.entries()]
    else:
        out["values"] = [value_json(v) for v in r.values()]
    return out


def dump(data: bytes) -> dict:
    f = brainfile.parse(data)
    return {"file": brainfile.FILE_KINDS.get(f.kind, f.kind), "build_tag": f.build_tag,
            "minor": f.minor, "records": [record_json(r) for r in f.records]}


def value_from(j: dict) -> brainfile.Value:
    if "hex" in j:
        return brainfile.Value(j["key"], j["type"], bytes.fromhex(j["hex"]))
    typ = TYPE_OF[j["type"]]
    v = j["value"]
    if typ == brainfile.NUMBER:
        data = int(v).to_bytes(2, "big", signed=True)
    elif typ == brainfile.BLOB:
        data = bytes.fromhex(v)
    elif typ == brainfile.NAME:
        data = brainfile.name_data(v)
    else:
        data = bytes([int(v)])
    return brainfile.Value(j["key"], typ, data)


def record_from(j: dict) -> brainfile.Record:
    if "raw" in j:
        f = brainfile.parse(_wrap(bytes.fromhex(j["raw"])))
        return f.records[0]
    kind = REC_OF[j["kind"]]
    if kind == brainfile.PROJECT_RECORD:
        payload = b"".join(brainfile.Entry(int(e["fx_id"], 16), e["store_id"], int(e["layout"], 16)).encode()
                           for e in j["entries"])
    else:
        mode = j.get("mode")
        prefix = brainfile.prefix_bytes(kind, target=j.get("target", 0),
                                   mode=brainfile.NO_MODE if mode is None else mode,
                                   layout=int(j.get("layout", "0"), 16), name=j.get("name", ""),
                                   instance=j.get("instance", 0))
        payload = prefix + b"".join(value_from(v).encode() for v in j["values"])
    return brainfile.Record(kind, j["store_id"], j.get("major", 1), j.get("minor", 0),
                       j.get("flags", 0), payload)


def _wrap(raw: bytes) -> bytes:
    """One raw record inside a minimal file, so the reader can split it."""
    import struct
    rest = bytes(12) + raw
    head = struct.pack(">4sHBBBBHI", brainfile.MAGIC, brainfile.HEADER, brainfile.MAJOR, 0, 0, 0, 1,
                       brainfile.HEADER + len(raw))
    return head + struct.pack(">I", brainfile.crc(rest)) + rest


def build(j: dict) -> bytes:
    return brainfile.File(KIND_OF[j["file"]], [record_from(r) for r in j["records"]],
                     j.get("build_tag", ""), j.get("minor", brainfile.MINOR)).encode()


def set_default(data: bytes | None, m, knobs: dict[str, int] | None, mode=None) -> bytes:
    """A card .work with module m's default record (for one MODE label or
    value, or None for the knobs' own defaults) replaced by `knobs`
    ({panel name: byte}), or removed when `knobs` is None. Every other
    record keeps its bytes."""
    from remix import brain
    f = brainfile.parse(data) if data else brainfile.File(brainfile.CARD_WORK, [], "HOST")
    sid = brain.fx_store_id(m)
    mv = brainfile.NO_MODE
    if mode is not None:
        mv = brain._mode_value(m, mode)
        if mv is None:
            raise SystemExit(f"{m.key} has no MODE {mode!r}")
    pre = brainfile.prefix_bytes(brainfile.DEFAULT, target=0, mode=mv, layout=brain.fx_layout(m))
    f.records = [r for r in f.records if not (r.kind == brainfile.DEFAULT and r.store_id == sid
                                              and r.target() == (0, mv))]
    if knobs is not None:
        keys = brain.fx_keys(m)
        names = {p.name.decode("ascii"): i for i, p in enumerate(m.params) if p.name and keys[i]}
        view = next((v for v in m.mode_views if v.mode == mv), None) if mode is not None else None
        for i, nm in (view.names.items() if view else ()):
            if keys[i]:
                names[nm.decode("ascii")] = i
        vals = []
        for name, v in knobs.items():
            if name not in names:
                raise SystemExit(f"{m.key} has no knob {name!r} (has {', '.join(names)})")
            i = names[name]
            count = m.params[i].count or 128
            if not 0 <= v < count:
                raise SystemExit(f"{m.key} {name}: {v} is outside its {count} values")
            vals.append(brainfile.Value(keys[i], brainfile.BYTE, bytes([v])))
        f.records.append(brainfile.Record(brainfile.DEFAULT, sid, payload=pre + b"".join(v.encode() for v in vals)))
    return f.encode()


def main(argv):
    if len(argv) >= 2 and argv[1] == "default":
        if len(argv) < 6:
            print(__doc__.strip())
            return 2
        from remix import registry
        path, mods = pathlib.Path(argv[2]), registry.bound(registry.remix(argv[3]))
        if argv[4] not in mods:
            print(f"no module {argv[4]!r}")
            return 2
        rest, mode = argv[5:], None
        if rest[:1] == ["--mode"] and len(rest) >= 2:
            mode, rest = rest[1], rest[2:]
        knobs = None if rest == ["--clear"] else \
            {k: int(v, 0) for k, v in (a.split("=", 1) for a in rest)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(set_default(path.read_bytes() if path.exists() else None, mods[argv[4]], knobs, mode))
        print(f"wrote {path}")
        return 0
    if len(argv) < 3 or argv[1] not in ("dump", "build", "pair"):
        print(__doc__.strip())
        return 2
    if argv[1] == "dump":
        try:
            print(json.dumps(dump(pathlib.Path(argv[2]).read_bytes()), indent=1))
        except (brainfile.Invalid, brainfile.Unreadable) as e:
            print(f"{argv[2]}: {type(e).__name__.lower()}: {e}")
            return 1
        return 0
    if argv[1] == "build":
        if len(argv) < 4:
            print("ot_brain.py build JSON OUT")
            return 2
        data = build(json.loads(pathlib.Path(argv[2]).read_text()))
        pathlib.Path(argv[3]).write_bytes(data)
        print(f"wrote {argv[3]} ({len(data)} bytes)")
        return 0
    d = pathlib.Path(argv[2])
    stem = argv[3] if len(argv) > 3 else "octabam"
    files = [d / f"{stem}.work", d / f"{stem}.strd"]
    action, f, write = brainfile.pair(*(p.read_bytes() if p.exists() else None for p in files))
    for p in files:
        state, why = brainfile._state(p.read_bytes() if p.exists() else None)
        print(f"  {p.name:14s} {state}{': ' + str(why) if state == 'invalid' else ''}")
    print(f"{action}; {len(f.records) if f else 0} records; "
          f"{'writes allowed' if write else 'no write until a confirmed replace'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
