#!/usr/bin/env python3
"""Exercise the linked GRANULAR renderer against synthetic FLEX pool pages."""
from __future__ import annotations

import pathlib
import struct
import subprocess
import sys

from unicorn import Uc, UC_ARCH_M68K, UC_HOOK_CODE, UC_MODE_BIG_ENDIAN
from unicorn.m68k_const import (
    UC_CPU_M68K_CFV4E,
    UC_M68K_REG_A0,
    UC_M68K_REG_A1,
    UC_M68K_REG_A7,
    UC_M68K_REG_D0,
    UC_M68K_REG_D1,
    UC_M68K_REG_D3,
    UC_M68K_REG_PC,
    UC_M68K_REG_SR,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "out/platform/runtime"
OS_BIN = ROOT / "out/raw/section_3_MAIN_OS.bin"

FLEX_PAGE = 0x400D31AE
STOCK_RENDER = 0x40004008
POOL_READ = 0x4009499C
VOICE_BASE, VOICE_STRIDE = 0x800049D8, 0xA8
CURSOR_AT, FP_PTR_AT, RS_PTR_AT = 0x80001C80, 0x800062A8, 0x800062A4
NIBBLE_BASE, PART_IDX_AT = 0x46104D0C, 0x100B14CF
BANK_PTR_AT, BANK = 0x46C82456, 0x42000000
SLOT_OFFSET, PART_SIZE = 0x8F04B, 6322
SETTINGS_BASE, SETTINGS_STRIDE = 0x100B14F0, 0x448
POOL_STATE, POOL_STATE_STRIDE = 0x46C922C4, 44
POOL_DATA_BASE = 0x42100000
HEADER, FP_REC, RS_REC = 0x80010000, 0x80011000, 0x80012000
STOP, STACK = 0x10000, 0x20000
TRACK_STATE_SIZE, TRACK_COUNT = 180, 8
POOL_PAGE_FRAMES = 8
PAGE_TABLE = 0x26000
instruction_count = [0]
max_render_instructions = [0]


def fail(message: str) -> None:
    print(f"  [FAIL] verify_granular: {message}", file=sys.stderr)
    raise SystemExit(1)


def check(label: str, ok: bool, detail: str = "") -> None:
    if not ok:
        fail(f"{label}" + (f" ({detail})" if detail else ""))
    print(f"  [PASS] {label}" + (f" — {detail}" if detail else ""))


def map_range(uc: Uc, address: int, size: int) -> None:
    base = address & ~0xFFF
    end = (address + size + 0xFFF) & ~0xFFF
    current = base
    while current < end:
        try:
            uc.mem_map(current, 0x1000)
        except Exception:
            pass
        current += 0x1000


def load_runtime():
    if not (RUNTIME / "runtime.bin").is_file() or not (RUNTIME / "runtime.elf").is_file():
        fail("missing out/platform/runtime; build with make bus REMIX=granular")
    if not OS_BIN.is_file():
        fail("missing out/raw/section_3_MAIN_OS.bin; run make os && make recon")

    raw_symbols = subprocess.check_output(
        ["m68k-elf-nm", str(RUNTIME / "runtime.elf")], text=True
    )
    symbols = {
        fields[2]: int(fields[0], 16)
        for fields in (line.split() for line in raw_symbols.splitlines())
        if len(fields) == 3
    }
    for symbol in ("gr_render", "gr_resolve_page", "gr_page", "gr_state",
                   "gr_page_descriptor"):
        if symbol not in symbols:
            fail(f"{symbol} missing from runtime.elf")

    headers = subprocess.check_output(
        ["m68k-elf-objdump", "-h", str(RUNTIME / "runtime.elf")], text=True
    )
    base = int(
        next(
            line.split()[3]
            for line in headers.splitlines()
            if len(line.split()) > 3 and line.split()[1] == ".text"
        ),
        16,
    )
    data = (RUNTIME / "runtime.bin").read_bytes()
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    map_range(uc, base, len(data) + 0x10000)
    uc.mem_write(base, data)

    os_bytes = OS_BIN.read_bytes()
    map_range(uc, 0x40000400, len(os_bytes))
    uc.mem_write(0x40000400, os_bytes)
    uc.mem_write(STOCK_RENDER, b"\x4e\x75")

    for address, size in (
        (0x10000, 0x20000),
        (0x100B0000, 0x30000),
        (BANK, 0xA0000),
        (POOL_DATA_BASE, 0x20000),
        (0x46104000, 0x2000),
        (0x46C82000, 0x3000),
        (0x46C92000, 0x2000),
        (0x80000000, 0x20000),
    ):
        map_range(uc, address, size)

    uc.reg_write(UC_M68K_REG_SR, 0x2000)
    uc.mem_write(0x46C82456, struct.pack(">I", BANK))
    uc.mem_write(PART_IDX_AT, b"\x00")
    return uc, symbols


def call(uc: Uc, symbols: dict[str, int], name: str, *args: int) -> int:
    uc.reg_write(UC_M68K_REG_A7, STACK)
    uc.mem_write(STACK, struct.pack(">" + "I" * (len(args) + 1), STOP, *args))
    try:
        uc.emu_start(symbols[name], STOP, count=500_000)
    except Exception as error:
        fail(f"{name} fault at pc={uc.reg_read(UC_M68K_REG_PC):#x}: {error}")
    if uc.reg_read(UC_M68K_REG_PC) != STOP:
        fail(f"{name} did not return (pc={uc.reg_read(UC_M68K_REG_PC):#x})")
    if uc.reg_read(UC_M68K_REG_A7) != STACK + 4:
        fail(f"{name} returned with an unbalanced stack")
    return uc.reg_read(UC_M68K_REG_D0)


def call_page_hook(uc: Uc, symbols: dict[str, int]) -> int:
    uc.reg_write(UC_M68K_REG_A7, STACK)
    uc.mem_write(STACK, struct.pack(">I", STOP))
    uc.mem_write(PAGE_TABLE, bytes(4) + struct.pack(">I", FLEX_PAGE))
    uc.mem_write(0x40031ED6, b"\x4e\x75")
    uc.reg_write(UC_M68K_REG_A0, PAGE_TABLE)
    uc.reg_write(UC_M68K_REG_A1, BANK)
    uc.reg_write(UC_M68K_REG_D0, 1)
    uc.reg_write(UC_M68K_REG_D1, 0)
    uc.reg_write(UC_M68K_REG_D3, 0)
    try:
        uc.emu_start(symbols["gr_page"], STOP, count=100_000)
    except Exception as error:
        fail(f"gr_page fault at pc={uc.reg_read(UC_M68K_REG_PC):#x}: {error}")
    if uc.reg_read(UC_M68K_REG_PC) != STOP or uc.reg_read(UC_M68K_REG_A7) != STACK + 4:
        fail("gr_page did not return through the stock resolver continuation")
    return uc.reg_read(UC_M68K_REG_D0)


def write_sample(uc: Uc, slot: int, track: int, name: bytes, flags: int,
                 frames: int, data: bytes, bytes_per_frame: int) -> None:
    slot_record = BANK + PART_SIZE * 0 + SLOT_OFFSET + track * 5
    uc.mem_write(slot_record, bytes([slot]))
    uc.mem_write(SETTINGS_BASE + slot * SETTINGS_STRIDE, name + b"\0")
    state = bytearray(POOL_STATE_STRIDE)
    struct.pack_into(">I", state, 0, flags)
    struct.pack_into(">I", state, 16, frames)
    uc.mem_write(POOL_STATE + slot * POOL_STATE_STRIDE, bytes(state))
    data_address = POOL_DATA_BASE + (slot - 2) * 0x10000
    uc.mem_write(data_address, data)
    pool_samples[slot] = (frames, bytes_per_frame, data_address)


pool_samples: dict[int, tuple[int, int, int]] = {}
pool_calls = [0]
pool_errors: list[str] = []


def emulate_pool_read(uc: Uc, address: int, _size: int, _data) -> None:
    if address != POOL_READ:
        return
    sp = uc.reg_read(UC_M68K_REG_A7)
    slot, frame, direction = struct.unpack(">III", uc.mem_read(sp + 4, 12))
    sample = pool_samples.get(slot)
    if sample is None or direction != 1:
        pool_errors.append(f"unexpected pool request slot={slot} direction={direction}")
        data_address, available = 0, 0
    else:
        frames, bytes_per_frame, data_address = sample
        if frame >= frames:
            data_address, available = 0, 0
        else:
            page_start = frame - frame % POOL_PAGE_FRAMES
            available = min(POOL_PAGE_FRAMES - frame % POOL_PAGE_FRAMES, frames - frame)
            data_address += frame * bytes_per_frame
            if page_start > frame:
                pool_errors.append("pool reader frame calculation underflowed")
        pool_calls[0] += 1
    uc.reg_write(UC_M68K_REG_D0, data_address)
    uc.reg_write(UC_M68K_REG_D1, available)


def signed24(word: int) -> int:
    value = word >> 8
    return value - 0x1000000 if value & 0x800000 else value


def sample24_at(uc: Uc, address: int) -> int:
    return signed24(struct.unpack(">I", uc.mem_read(address, 4))[0])


def set_controls(uc: Uc, values: list[int]) -> None:
    uc.mem_write(FP_REC, b"".join(struct.pack(">H", (value & 0x7F) << 8) for value in values))
    uc.mem_write(FP_PTR_AT, struct.pack(">I", FP_REC))
    uc.mem_write(RS_REC, bytes(64))
    uc.mem_write(RS_PTR_AT, struct.pack(">I", RS_REC))


def render(uc: Uc, symbols: dict[str, int], track: int, start: int = 0,
           end: int = 16, trigger: bool = False) -> None:
    uc.mem_write(0x80001C80, struct.pack(">I", HEADER))
    uc.mem_write(NIBBLE_BASE + track, b"\x10" if trigger else b"\x00")
    uc.mem_write(HEADER, bytes(16 + 16 * 8))
    instruction_count[0] = 0
    call(uc, symbols, "gr_render", track, 0, start, end)
    max_render_instructions[0] = max(max_render_instructions[0], instruction_count[0])


def count_instruction(_uc, _address, _size, _data) -> None:
    instruction_count[0] += 1


def check_page_descriptor(uc: Uc, symbols: dict[str, int]) -> None:
    write_sample(uc, 2, 0, b"folder/GrAnGate.wav", 2, 80, b"", 2)
    uc.mem_write(symbols["gr_page_ready"], bytes(4))
    uc.mem_write(symbols["gr_page_descriptor"], bytes(0x192))
    page = call(uc, symbols, "gr_resolve_page", FLEX_PAGE, BANK, 0, 0)
    clone = symbols["gr_page_descriptor"]
    check("GRAN basename selects the FLEX descriptor clone", page == clone)

    page_bytes = bytes(uc.mem_read(clone, 0x192))
    check("clone title is GRANULAR", page_bytes[9:18] == b"GRANULAR\0")
    names = (
        b"PTCH\0\0SCAN\0\0SIZE\0\0SPEED\0"
        b"DENS\0\0SCAT\0\0"
    )
    check("six six-byte control names occupy the parameter-name table",
          page_bytes[0x16:0x16 + 36] == names)
    minimums = struct.unpack_from(">6I", page_bytes, 0x6A)
    counts = struct.unpack_from(">6I", page_bytes, 0x9A)
    defaults = page_bytes[0x5E:0x64]
    formatters = struct.unpack_from(">6I", page_bytes, 0xCA)
    widgets = struct.unpack_from(">6I", page_bytes, 0xFA)
    check("control ranges are 0..127 with six matching defaults",
          minimums == (0,) * 6 and counts == (128,) * 6
          and defaults == bytes((64, 0, 48, 64, 80, 0)))
    check("all six controls use the plain knob formatter",
          formatters == (0,) * 6 and widgets == (0,) * 6)
    enabled = struct.unpack_from(">I", page_bytes, 0x18E)[0]
    check("the stock FLEX page keeps all six encoder enable bits",
          all(((enabled >> (index * 4)) & 1) for index in range(6)))
    check("assembly page hook returns the custom page through stock continuation",
          call_page_hook(uc, symbols) == clone)

    write_sample(uc, 3, 0, b"OTHER.wav", 2, 80, b"", 2)
    page = call(uc, symbols, "gr_resolve_page", FLEX_PAGE, BANK, 0, 0)
    check("ordinary sample keeps the stock FLEX page", page == FLEX_PAGE)
    check("assembly page hook preserves ordinary sample routing",
          call_page_hook(uc, symbols) == FLEX_PAGE)


def check_render(uc: Uc, symbols: dict[str, int]) -> None:
    uc.hook_add(UC_HOOK_CODE, emulate_pool_read)
    uc.hook_add(UC_HOOK_CODE, count_instruction)
    uc.mem_write(POOL_READ, b"\x4e\x75")
    mono = [-3000 + frame * 100 for frame in range(80)]
    mono_data = b"".join(struct.pack(">h", sample) for sample in mono)
    write_sample(uc, 2, 0, b"folder/GRANmono.wav", 2, 80, mono_data, 2)
    uc.mem_write(symbols["gr_state"], bytes(TRACK_STATE_SIZE * TRACK_COUNT))
    set_controls(uc, [64, 0, 0, 0, 127, 0])
    uc.mem_write(VOICE_BASE, b"\xff")
    uc.mem_write(RS_REC, bytes(64))
    uc.mem_write(RS_PTR_AT, struct.pack(">I", RS_REC))
    render(uc, symbols, 0, trigger=True)

    mono_output = [sample24_at(uc, HEADER + 16 + frame * 8) for frame in range(16)]
    check("mono 16-bit source renders across pool pages",
          mono_output[0] == 0
          and mono_output[1:] == [sample * 256 for sample in mono[1:16]],
          f"pool reads={pool_calls[0]}")
    check("the renderer consumes the pool's page-aware reader",
          pool_calls[0] >= 3 and not pool_errors,
          "; ".join(pool_errors) if pool_errors else f"{pool_calls[0]} page reads")
    state = symbols["gr_state"]
    density = struct.unpack(">I", uc.mem_read(state + 8 * 4, 4))[0]
    hop = struct.unpack(">I", uc.mem_read(state + 7 * 4, 4))[0]
    check("maximum density schedules four overlapping grains",
          density == 4 and hop == 16, f"density={density} hop={hop}")

    render(uc, symbols, 0)
    render(uc, symbols, 0)
    render(uc, symbols, 0, end=15)
    active_grains = [
        struct.unpack(">I", uc.mem_read(state + 13 * 4 + index * 32 + 16, 4))[0]
        for index in range(4)
    ]
    next_grain = struct.unpack(">I", uc.mem_read(state + 11 * 4, 4))[0]
    check("four grains overlap and the ring wraps", all(active_grains) and next_grain == 0)
    uc.mem_write(VOICE_BASE, b"\x00")
    remaining = sum(active_grains)
    render(uc, symbols, 0)
    after_voice_end = [
        struct.unpack(">I", uc.mem_read(state + 13 * 4 + index * 32 + 16, 4))[0]
        for index in range(4)
    ]
    check("active grains finish without spawning after the FLEX voice ends",
          sum(after_voice_end) < remaining and
          struct.unpack(">I", uc.mem_read(state + 11 * 4, 4))[0] == next_grain)

    uc.mem_write(state, bytes(TRACK_STATE_SIZE * TRACK_COUNT))
    set_controls(uc, [0, 0, 0, 64, 0, 0])
    uc.mem_write(VOICE_BASE, b"\xff")
    render(uc, symbols, 0, trigger=True)
    half_speed_sample = sample24_at(uc, HEADER + 16 + 8)
    scan_position = struct.unpack(">I", uc.mem_read(state + 4 * 4, 4))[0]
    check("PTCH changes grain rate independently of SPEED",
          half_speed_sample == (mono[0] + 50) * 256 and scan_position == 16 * 256,
          f"half-speed sample={half_speed_sample}, scan={scan_position >> 8}")

    set_controls(uc, [64, 127, 0, 0, 0, 0])
    uc.mem_write(state, bytes(TRACK_STATE_SIZE * TRACK_COUNT))
    uc.mem_write(VOICE_BASE, b"\xff")
    render(uc, symbols, 0, trigger=True)
    scan_position = struct.unpack(">I", uc.mem_read(state + 4 * 4, 4))[0]
    scan_sample = sample24_at(uc, HEADER + 16 + 8)
    check("SCAN spans the legal grain-start range",
          scan_position == 16 * 256 and scan_sample == mono[17] * 256,
          f"start={scan_position >> 8} frames")

    set_controls(uc, [64, 0, 0, 64, 0, 0])
    uc.mem_write(state, bytes(TRACK_STATE_SIZE * TRACK_COUNT))
    uc.mem_write(VOICE_BASE, b"\xff")
    render(uc, symbols, 0, trigger=True)
    for _ in range(4):
        render(uc, symbols, 0)
    second_grain_position = struct.unpack(
        ">I", uc.mem_read(state + 13 * 4 + 32, 4)
    )[0]
    check("SPEED advances the next grain independently of PTCH",
          second_grain_position == 32 * 256,
          f"second grain position={second_grain_position >> 8} frames")

    for track, slot, bits, channels in (
        (0, 2, 16, 1),
        (1, 3, 16, 2),
        (0, 2, 24, 1),
        (1, 3, 24, 2),
    ):
        expected_samples: list[tuple[int, int]] = []
        raw_data = bytearray()
        for frame in range(80):
            if bits == 16:
                left, right = -4000 + frame * 100, 3000 - frame * 50
                raw_data.extend(struct.pack(">h", left))
                if channels == 2:
                    raw_data.extend(struct.pack(">h", right))
                expected_samples.append((left * 256, right * 256))
            else:
                left, right = -0x200000 + frame * 0x1000, 0x100000 + frame * 0x1000
                raw_data.extend((left & 0xFFFFFF).to_bytes(3, "big"))
                if channels == 2:
                    raw_data.extend((right & 0xFFFFFF).to_bytes(3, "big"))
                expected_samples.append(((left >> 8) * 256, (right >> 8) * 256))
        flags = (2 if bits == 16 else 0) | (1 if channels == 2 else 0)
        bytes_per_sample = 2 if bits == 16 else 3
        write_sample(uc, slot, track, b"GRANformat.wav", flags, 80,
                     bytes(raw_data), bytes_per_sample * channels)
        uc.mem_write(state + track * TRACK_STATE_SIZE, bytes(TRACK_STATE_SIZE))
        set_controls(uc, [64, 0, 0, 0, 0, 0])
        uc.mem_write(VOICE_BASE + track * VOICE_STRIDE, b"\xff")
        pool_calls[0] = 0
        render(uc, symbols, track, trigger=True)
        matches = True
        for frame in range(1, 16):
            left = sample24_at(uc, HEADER + 16 + frame * 8)
            right = sample24_at(uc, HEADER + 20 + frame * 8)
            expected_left, expected_right = expected_samples[frame]
            if channels == 1:
                expected_right = expected_left
            matches &= left == expected_left and right == expected_right
        label = f"{'mono' if channels == 1 else 'stereo'} {bits}-bit"
        check(f"{label} source renders across pool pages",
              matches and pool_calls[0] >= 3, f"pool reads={pool_calls[0]}")

    write_sample(uc, 3, 1, b"OTHERstereo.wav", 3, 80, bytes(raw_data), 6)
    uc.mem_write(symbols["gr_state"] + TRACK_STATE_SIZE, bytes(TRACK_STATE_SIZE))
    set_controls(uc, [64, 0, 0, 0, 0, 0])
    uc.mem_write(VOICE_BASE + VOICE_STRIDE, b"\xff")
    render(uc, symbols, 1, trigger=True)
    check("ordinary sample remains stock audio", bytes(uc.mem_read(HEADER + 16, 8)) == bytes(8))
    print(f"  [INFO] max observed renderer cost: {max_render_instructions[0]} "
          "Unicorn instructions per call (not ColdFire cycles)")


def main() -> None:
    global pool_samples
    uc, symbols = load_runtime()
    pool_samples = {}
    check_page_descriptor(uc, symbols)
    check_render(uc, symbols)


if __name__ == "__main__":
    main()
