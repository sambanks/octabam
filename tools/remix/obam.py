"""The OBAM container: the card store, the project store and a template file.

docs/proposals/STORE.md section 7 is the format; this is its reference
reader and writer, used by the build, tools/hw/ot_store.py and the gates.
Big-endian; CRC-32 is zlib's; padding is zero.

A file that fails a file-level check raises `Invalid` (the core then
tries the saved copy, STORE.md section 6.2). A newer container major
raises `Unreadable` (the core neither applies nor writes it). Inside a
valid file a record keeps its exact bytes until it is edited, and a value
keeps its exact bytes until it is replaced, so an absent module's record
and an unknown key survive a save byte for byte (section 7.7 rules 1, 2).
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

MAGIC = b"OBAM"
HEADER = 32
MAJOR = 1
MINOR = 0
RECORD_HEADER = 20

# file kinds (7.1)
CARD_WORK, CARD_STRD, PROJECT_WORK, PROJECT_STRD, TEMPLATE = range(5)
FILE_KINDS = {CARD_WORK: "card .work", CARD_STRD: "card .strd",
              PROJECT_WORK: "project .work", PROJECT_STRD: "project .strd",
              TEMPLATE: "template"}

# record kinds (7.3)
SETTINGS, DEFAULT, TEMPLATE_REC, PROJECT_RECORD, FIELD_BLOCK = 1, 2, 3, 4, 5
RECORD_KINDS = {SETTINGS: "settings", DEFAULT: "default", TEMPLATE_REC: "template",
                PROJECT_RECORD: "project record", FIELD_BLOCK: "field block"}
PREFIX = {SETTINGS: 0, DEFAULT: 8, TEMPLATE_REC: 16, PROJECT_RECORD: 0, FIELD_BLOCK: 4}
NO_MODE = 0xFFFF

# value types (7.4)
BINARY, OPTION, NUMBER, BLOB, BYTE, NAME = 1, 2, 3, 4, 5, 6
TYPE_NAMES = {BINARY: "binary", OPTION: "option", NUMBER: "number",
              BLOB: "blob", BYTE: "byte", NAME: "name"}
LONG = 255                       # the length byte that announces a u32 length (Blob only)


class Invalid(ValueError):
    """The whole file fails a check: magic, header size, length, CRC, a
    record boundary. The core tries the saved copy."""


class Unreadable(ValueError):
    """A newer container major: neither applied nor written."""


def align4(n: int) -> int:
    return (n + 3) & ~3


def crc(b: bytes) -> int:
    return zlib.crc32(b) & 0xFFFFFFFF


def _pad(b: bytes) -> bytes:
    return b + bytes(align4(len(b)) - len(b))


# ---- values ---------------------------------------------------------------

@dataclass
class Value:
    """One value. `raw` is its exact bytes as read (header, data, padding);
    a value built here has none and is serialised from its fields."""
    key: int
    type: int
    data: bytes
    raw: bytes | None = None

    def encode(self) -> bytes:
        if self.raw is not None:
            return self.raw
        n = len(self.data)
        if n >= LONG:
            if self.type != BLOB:
                raise ValueError(f"key {self.key}: {n} bytes; only a Blob takes the long form")
            head = struct.pack(">HBBI", self.key, self.type, LONG, n)
        else:
            head = struct.pack(">HBB", self.key, self.type, n)
        return head + _pad(self.data)


def parse_values(b: bytes) -> list[Value]:
    """The values of a payload after its prefix. Raises ValueError when one
    runs past the end or a non-Blob takes the long form."""
    out, i = [], 0
    while i < len(b):
        if i + 4 > len(b):
            raise ValueError(f"a value header at {i} runs past the payload")
        key, typ, n = struct.unpack_from(">HBB", b, i)
        head = 4
        if n == LONG:
            if typ != BLOB:
                raise ValueError(f"key {key}: type {typ} in the long form")
            if i + 8 > len(b):
                raise ValueError(f"key {key}: the long length runs past the payload")
            n, = struct.unpack_from(">I", b, i + 4)
            head = 8
        end = i + head + align4(n)
        if end > len(b):
            raise ValueError(f"key {key}: {n} bytes run past the payload")
        out.append(Value(key, typ, b[i + head:i + head + n], b[i:end]))
        i = end
    return out


def encode_value(kind, v) -> tuple[int, bytes]:
    """A schema kind and a Python value -> (OBAM type, data)."""
    from remix.schema import Binary, Blob, Number, Option
    if isinstance(kind, Binary):
        return BINARY, bytes([int(v)])
    if isinstance(kind, Option):
        return OPTION, bytes([kind.index(v)])
    if isinstance(kind, Number):
        return NUMBER, struct.pack(">h", v)
    if isinstance(kind, Blob):
        return BLOB, bytes(v)
    raise ValueError(f"{kind!r} is not stored")


def decode_value(typ: int, data: bytes):
    """(OBAM type, data) -> a Python value; ValueError on a wrong length."""
    want = {BINARY: 1, OPTION: 1, NUMBER: 2, BYTE: 1, NAME: 6}.get(typ)
    if want is not None and len(data) != want:
        raise ValueError(f"type {TYPE_NAMES.get(typ, typ)} takes {want} bytes, has {len(data)}")
    if typ in (BINARY, OPTION, BYTE):
        return data[0]
    if typ == NUMBER:
        return struct.unpack(">h", data)[0]
    if typ == NAME:
        if data[5] != 0:
            raise ValueError("a Name's sixth byte is not zero")
        return data.split(b"\0", 1)[0].decode("ascii")
    if typ == BLOB:
        return bytes(data)
    raise ValueError(f"unknown type {typ}")


def name_data(s: str) -> bytes:
    b = s.encode("ascii")
    if len(b) > 5:
        raise ValueError(f"name {s!r} is longer than 5 characters")
    return b.ljust(6, b"\0")


# ---- records --------------------------------------------------------------

@dataclass
class Entry:
    """A project record entry (7.5): which store an FX id named, and its layout."""
    fx_id: int
    store_id: str
    layout: int
    reserved: int = 0

    def encode(self) -> bytes:
        sid = self.store_id.encode("ascii")
        return struct.pack(">BBHI", self.fx_id, len(sid), self.reserved, self.layout) + _pad(sid)


def parse_entries(b: bytes) -> list[Entry]:
    out, i = [], 0
    while i < len(b):
        if i + 8 > len(b):
            raise ValueError(f"an entry header at {i} runs past the payload")
        fx, n, res, layout = struct.unpack_from(">BBHI", b, i)
        if not 1 <= n <= 63 or i + 8 + align4(n) > len(b):
            raise ValueError(f"entry for FX id 0x{fx:02x}: store id length {n}")
        out.append(Entry(fx, b[i + 8:i + 8 + n].decode("latin-1"), layout, res))
        i += 8 + align4(n)
    return out


@dataclass
class Record:
    """One record. `raw` is the exact bytes as read, written back unchanged
    until `edit` or `replace` clears it."""
    kind: int
    store_id: str
    major: int = 1
    minor: int = 0
    flags: int = 0
    payload: bytes = b""
    raw: bytes | None = None
    crc_ok: bool = True

    # -- the payload, read --------------------------------------------------
    @property
    def known_kind(self) -> bool:
        return self.kind in PREFIX

    @property
    def prefix(self) -> bytes:
        return self.payload[:PREFIX.get(self.kind, 0)]

    def target(self) -> tuple[int, int] | None:
        """(target, mode) for a default or template, (target, instance) for
        a field block, None otherwise."""
        if self.kind in (DEFAULT, TEMPLATE_REC, FIELD_BLOCK) and len(self.payload) >= 4:
            return struct.unpack_from(">HH", self.payload, 0)
        return None

    def layout(self) -> int | None:
        if self.kind in (DEFAULT, TEMPLATE_REC) and len(self.payload) >= 8:
            return struct.unpack_from(">I", self.payload, 4)[0]
        return None

    def name(self) -> str | None:
        if self.kind == TEMPLATE_REC and len(self.payload) >= 16:
            return self.payload[8:16].split(b"\0", 1)[0].decode("ascii", "replace")
        return None

    def values(self) -> list[Value]:
        """Raises ValueError for a malformed payload or a kind without values."""
        if self.kind not in PREFIX or self.kind == PROJECT_RECORD:
            raise ValueError(f"record kind {self.kind} carries no values")
        if len(self.payload) < PREFIX[self.kind]:
            raise ValueError(f"payload shorter than its {PREFIX[self.kind]}-byte prefix")
        return parse_values(self.payload[PREFIX[self.kind]:])

    def entries(self) -> list[Entry]:
        if self.kind != PROJECT_RECORD:
            raise ValueError(f"record kind {self.kind} carries no entries")
        return parse_entries(self.payload)

    def applicable(self) -> bool:
        """Structurally fit to apply: known kind, payload CRC good, payload
        parses. Whether the image carries the store id and its major is the
        caller's to add (7.7 rule 1)."""
        if not self.known_kind or not self.crc_ok:
            return False
        try:
            self.entries() if self.kind == PROJECT_RECORD else self.values()
        except ValueError:
            return False
        return True

    def ident(self) -> tuple:
        """What two records must not share (7.7 rule 5): kind, store id, prefix."""
        return (self.kind, self.store_id, self.prefix)

    # -- the payload, written -----------------------------------------------
    def replace(self, key: int, typ: int, data: bytes):
        """Set one value; every other value keeps its exact bytes (7.7 rule 2).
        A stored value of another type under the key is replaced: the caller
        decides, by rule 3, whether that is wanted."""
        vals = self.values()
        new = Value(key, typ, bytes(data))
        for i, v in enumerate(vals):
            if v.key == key:
                vals[i] = new
                break
        else:
            vals.append(new)
        self._set_values(vals)

    def remove(self, key: int):
        self._set_values([v for v in self.values() if v.key != key])

    def _set_values(self, vals: list[Value]):
        self.payload = self.prefix + b"".join(v.encode() for v in vals)
        self.raw = None
        self.crc_ok = True

    def encode(self) -> bytes:
        if self.raw is not None:
            return self.raw
        sid = self.store_id.encode("ascii")
        if not 1 <= len(sid) <= 63:
            raise ValueError(f"store id {self.store_id!r}: 1..63 bytes")
        size = RECORD_HEADER + align4(len(sid)) + align4(len(self.payload))
        return (struct.pack(">BBHHHIII", self.kind, len(sid), self.major, self.minor,
                            self.flags, len(self.payload), crc(self.payload), size)
                + _pad(sid) + _pad(self.payload))


def prefix_bytes(kind: int, target: int = 0, mode: int = NO_MODE, layout: int = 0,
                 name: str = "", instance: int = 0) -> bytes:
    """The prefix a new record of `kind` starts its payload with (7.3)."""
    if kind == DEFAULT:
        return struct.pack(">HHI", target, mode, layout)
    if kind == TEMPLATE_REC:
        nb = name.encode("ascii")
        if not 1 <= len(nb) <= 8:
            raise ValueError(f"template name {name!r}: 1..8 ASCII characters")
        return struct.pack(">HHI", target, mode, layout) + nb.ljust(8, b"\0")
    if kind == FIELD_BLOCK:
        return struct.pack(">HH", target, instance)
    return b""


# ---- files ----------------------------------------------------------------

@dataclass
class File:
    kind: int
    records: list[Record] = field(default_factory=list)
    build_tag: str = ""
    minor: int = MINOR
    reserved9: int = 0
    reserved28: int = 0

    def duplicates(self) -> set[tuple]:
        """Idents carried by more than one record: none of them is applied."""
        seen, dup = set(), set()
        for r in self.records:
            k = r.ident()
            (dup if k in seen else seen).add(k)
        return dup

    def find(self, kind: int, store_id: str, prefix: bytes = b"") -> Record | None:
        hits = [r for r in self.records if r.ident() == (kind, store_id, prefix)]
        return hits[0] if len(hits) == 1 else None

    def encode(self) -> bytes:
        body = b"".join(r.encode() for r in self.records)
        tag = self.build_tag.encode("ascii")[:8].ljust(8, b"\0")
        total = HEADER + len(body)
        rest = tag + struct.pack(">I", self.reserved28) + body
        head = struct.pack(">4sHBBBBHI", MAGIC, HEADER, MAJOR, self.minor, self.kind,
                           self.reserved9, len(self.records), total)
        return head + struct.pack(">I", crc(rest)) + rest


def parse(data: bytes) -> File:
    """A whole file. Raises Invalid or Unreadable; never returns a file that
    fails a file-level check."""
    if len(data) < HEADER:
        raise Invalid(f"{len(data)} bytes, shorter than the {HEADER}-byte header")
    magic, hsize, major, minor, kind, res9, count, total, fcrc = \
        struct.unpack_from(">4sHBBBBHII", data, 0)
    if magic != MAGIC:
        raise Invalid(f"magic {magic!r}")
    if major > MAJOR:
        raise Unreadable(f"container major {major}; this reader is {MAJOR}")
    if major < 1:
        raise Invalid(f"container major {major}")
    if hsize != HEADER:
        raise Invalid(f"header size {hsize}")
    if total != len(data):
        raise Invalid(f"header says {total} bytes, the file has {len(data)}")
    if crc(data[20:]) != fcrc:
        raise Invalid("file CRC")
    tag = data[20:28].split(b"\0", 1)[0].decode("ascii", "replace")
    res28, = struct.unpack_from(">I", data, 28)
    f = File(kind, [], tag, minor, res9, res28)
    i = HEADER
    for n in range(count):
        if i + RECORD_HEADER > total:
            raise Invalid(f"record {n} header runs past the file")
        rk, idlen, rmaj, rmin, flags, plen, pcrc, size = \
            struct.unpack_from(">BBHHHIII", data, i)
        if not 1 <= idlen <= 63:
            raise Invalid(f"record {n}: store id length {idlen}")
        if size != RECORD_HEADER + align4(idlen) + align4(plen):
            raise Invalid(f"record {n}: size {size} disagrees with its lengths")
        if i + size > total:
            raise Invalid(f"record {n} runs past the file")
        sid = data[i + RECORD_HEADER:i + RECORD_HEADER + idlen].decode("latin-1")
        p0 = i + RECORD_HEADER + align4(idlen)
        payload = data[p0:p0 + plen]
        f.records.append(Record(rk, sid, rmaj, rmin, flags, payload,
                                raw=data[i:i + size], crc_ok=crc(payload) == pcrc))
        i += size
    if i != total:
        raise Invalid(f"records end at {i}, the file at {total}")
    return f


# ---- layout hash (7.6) ----------------------------------------------------

def layout_hash(slots, mode_slot: int | None) -> int:
    """CRC-32 over 49 bytes: (key, count) per slot 0..11, then the MODE
    slot. `slots` is twelve (key, count) pairs, (0, 0) for a slot that is
    not drawn."""
    slots = list(slots)
    if len(slots) != 12:
        raise ValueError(f"{len(slots)} slots; a page has 12")
    b = b"".join(struct.pack(">HH", k, c) for k, c in slots)
    return crc(b + bytes([0xFF if mode_slot is None else mode_slot]))


# ---- the .work / .strd pair (STORE.md section 6.2) ------------------------

FRESH, USE_WORK, WORK_STRD_DAMAGED, RECOVER, DAMAGED = (
    "fresh", "use .work", "use .work, .strd damaged", "recover from .strd", "damaged")


def _state(data: bytes | None):
    """'absent', 'valid' with the File, or 'invalid' with the reason. A newer
    container major counts as invalid here: it is neither applied nor written."""
    if data is None:
        return "absent", None
    try:
        return "valid", parse(data)
    except (Invalid, Unreadable) as e:
        return "invalid", e


def pair(work: bytes | None, strd: bytes | None):
    """(action, File or None, write allowed) for the files on the card.
    `write allowed` False means no automatic write until the user confirms a
    replace."""
    (ws, wf), (ss, sf) = _state(work), _state(strd)
    if ws == "valid":
        return (USE_WORK if ss != "invalid" else WORK_STRD_DAMAGED), wf, True
    if ss == "valid":
        return RECOVER, sf, True
    if ws == "absent" and ss == "absent":
        return FRESH, None, True
    return DAMAGED, None, False
