#!/usr/bin/env python3
"""The OBAM byte corpus: one file per case and expect.json, the outcome a
reader must reach on each (docs/proposals/STORE.md section 7).

    python3 tools/verify/tests/make_obam_corpus.py          # rewrite the corpus
    python3 tools/verify/tests/make_obam_corpus.py --check  # refuse a stale copy

The files are built here from obam.py's writer plus hand-made damage, and
committed so the core's C reader (phase 2) runs against the same bytes.
test_obam.py checks the committed copy is current and every outcome.
"""
import json
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from remix import obam  # noqa: E402

OUT = HERE / "obam_corpus"
KNOWN = "octabam.example"        # the store the corpus treats as carried, major 1


def rec(kind, sid, values=(), prefix=b"", major=1, minor=0, flags=0):
    payload = prefix + b"".join(obam.Value(k, t, d).encode() for k, t, d in values)
    return obam.Record(kind, sid, major, minor, flags, payload)


SETTINGS = [(1, obam.BINARY, b"\x01"), (2, obam.OPTION, b"\x02"),
            (3, obam.NUMBER, struct.pack(">h", -300)), (4, obam.BLOB, b"abc")]


def cases():
    """name -> (bytes, expectation)."""
    c = {}

    def ok(name, kind, recs, **exp):
        c[name] = (obam.File(kind, recs, "CORPUS").encode(), {"outcome": "valid", **exp})

    ok("empty_card_work", obam.CARD_WORK, [], records=0)
    ok("settings_known", obam.CARD_WORK, [rec(obam.SETTINGS, KNOWN, SETTINGS)],
       records=1, applicable=[True],
       values={"0": {"1": 1, "2": 2, "3": -300, "4": "616263"}})
    ok("absent_module", obam.PROJECT_WORK,
       [rec(obam.SETTINGS, KNOWN, SETTINGS[:1]), rec(obam.SETTINGS, "org.other.mod", [(7, obam.NUMBER, b"\x00\x05")])],
       records=2, applicable=[True, True], carried=[True, False])
    ok("newer_minor_unknown_key", obam.CARD_WORK,
       [rec(obam.SETTINGS, KNOWN, SETTINGS[:2] + [(99, obam.NUMBER, b"\x12\x34")], minor=5)],
       records=1, applicable=[True], values={"0": {"1": 1, "2": 2, "99": 4660}})
    ok("unsupported_major", obam.CARD_WORK, [rec(obam.SETTINGS, KNOWN, SETTINGS[:1], major=2)],
       records=1, applicable=[True], carried=[False])
    ok("unknown_value_type", obam.CARD_WORK,
       [rec(obam.SETTINGS, KNOWN, SETTINGS[:1] + [(5, 9, b"\x01\x02\x03")])],
       records=1, applicable=[True], values={"0": {"1": 1, "5": "type 9"}})
    ok("unknown_record_kind", obam.CARD_WORK, [rec(9, KNOWN, SETTINGS[:1])],
       records=1, applicable=[False])
    ok("duplicate_records", obam.CARD_WORK,
       [rec(obam.SETTINGS, KNOWN, SETTINGS[:1]), rec(obam.SETTINGS, KNOWN, SETTINGS[1:2])],
       records=2, applicable=[True, True], duplicates=1)
    ok("long_blob", obam.CARD_WORK, [rec(obam.SETTINGS, KNOWN, [(4, obam.BLOB, bytes(range(256)) + bytes(44))])],
       records=1, applicable=[True])
    ok("flags_and_reserved", obam.CARD_WORK, [rec(obam.SETTINGS, KNOWN, SETTINGS[:1], flags=0x8001)],
       records=1, applicable=[True])
    pre_def = obam.prefix_bytes(obam.DEFAULT, target=0, mode=2, layout=0xDEADBEEF)
    pre_tpl = obam.prefix_bytes(obam.TEMPLATE_REC, target=0, layout=0xDEADBEEF, name="RYTM")
    pre_fld = obam.prefix_bytes(obam.FIELD_BLOCK, target=1, instance=9)
    proj = obam.Record(obam.PROJECT_RECORD, "stock",
                       payload=obam.Entry(0x06, "octabam.busdelay", 0x01020304).encode()
                       + obam.Entry(0x14, "stock.filter", 0x0A0B0C0D).encode())
    ok("every_record_kind", obam.PROJECT_WORK,
       [rec(obam.DEFAULT, KNOWN, [(1, obam.BYTE, b"\x40"), (2, obam.BYTE, b"\x7f")], pre_def),
        rec(obam.TEMPLATE_REC, KNOWN, [(1, obam.BYTE, b"\x10")], pre_tpl),
        rec(obam.FIELD_BLOCK, KNOWN, [(1, obam.NAME, obam.name_data("CUTOF"))], pre_fld),
        proj],
       records=4, applicable=[True, True, True, True],
       targets=[[0, 2], [0, 65535], [1, 9], None], template_name="RYTM")
    ok("template_file", obam.TEMPLATE,
       [rec(obam.TEMPLATE_REC, KNOWN, [(1, obam.BYTE, b"\x20")], pre_tpl)],
       records=1, applicable=[True])

    # record-level damage: the file is valid, the record is kept and not applied
    good = obam.File(obam.CARD_WORK, [rec(obam.SETTINGS, KNOWN, SETTINGS)], "CORPUS").encode()
    b = bytearray(good)
    b[obam.HEADER + 20 + 16 + 4] ^= 0xFF          # a payload byte; the record's own CRC now fails
    rest = bytes(b[20:])
    b[16:20] = struct.pack(">I", obam.crc(rest))  # the file CRC still holds
    c["bad_payload_crc"] = (bytes(b), {"outcome": "valid", "records": 1, "applicable": [False]})
    b = bytearray(good)
    vstart = obam.HEADER + 20 + 16
    b[vstart + 3] = 200                            # the first value claims 200 bytes
    b[obam.HEADER + 12:obam.HEADER + 16] = struct.pack(">I", obam.crc(bytes(b[vstart:vstart + len(rec(obam.SETTINGS, KNOWN, SETTINGS).payload)])))
    b[16:20] = struct.pack(">I", obam.crc(bytes(b[20:])))
    c["value_overrun"] = (bytes(b), {"outcome": "valid", "records": 1, "applicable": [False]})

    # file-level damage
    b = bytearray(good)
    b[-1] ^= 0x01
    c["bad_file_crc"] = (bytes(b), {"outcome": "invalid"})
    b = bytearray(good)
    b[12:16] = struct.pack(">I", len(good) + 4)
    b[16:20] = struct.pack(">I", obam.crc(bytes(b[20:])))
    c["bad_total"] = (bytes(b), {"outcome": "invalid"})
    b = bytearray(good)
    b[obam.HEADER + 16:obam.HEADER + 20] = struct.pack(">I", 999)
    b[16:20] = struct.pack(">I", obam.crc(bytes(b[20:])))
    c["bad_record_size"] = (bytes(b), {"outcome": "invalid"})
    c["torn"] = (good[:len(good) // 2], {"outcome": "invalid"})
    b = bytearray(good)
    b[0:4] = b"OBAN"
    c["bad_magic"] = (bytes(b), {"outcome": "invalid"})
    b = bytearray(good)
    b[6] = 2
    c["newer_container_major"] = (bytes(b), {"outcome": "unreadable"})
    return c


def write():
    OUT.mkdir(exist_ok=True)
    exp = {}
    for name, (data, e) in sorted(cases().items()):
        (OUT / f"{name}.obam").write_bytes(data)
        exp[name] = e
    (OUT / "expect.json").write_text(json.dumps(exp, indent=1, sort_keys=True) + "\n")


def stale() -> list[str]:
    exp = json.loads((OUT / "expect.json").read_text()) if (OUT / "expect.json").exists() else {}
    bad = []
    for name, (data, e) in sorted(cases().items()):
        f = OUT / f"{name}.obam"
        if not f.exists() or f.read_bytes() != data or exp.get(name) != e:
            bad.append(name)
    extra = {p.stem for p in OUT.glob("*.obam")} - set(cases())
    return bad + sorted(extra)


if __name__ == "__main__":
    if "--check" in sys.argv:
        s = stale()
        print("obam corpus: " + (f"stale: {', '.join(s)}" if s else "current"))
        sys.exit(1 if s else 0)
    write()
    print(f"wrote {len(cases())} files and expect.json to {OUT.relative_to(HERE.parents[2])}")
