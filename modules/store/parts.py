"""Optional native Part service: build-time fields, windows and lifecycle clients.

Offsets are relative to a native working Part (0x18b2 bytes). Register the
smallest read window that must remain coherent and only the bytes a client
writes. Saved layout and field meaning remain the client's responsibility.
"""
import re
from remix.schema import Claims, Detour, Gate, Linked, Poke

PART_SIZE = 0x18b2
MIDI_BASE, MIDI_SIZE = 0x4e2, 8 * 36
# key: (read windows (offset, size), writable offsets)
def midi_fields(*fields):
    return tuple(MIDI_BASE + 36*t + f for t in range(8) for f in fields)

PART_CLIENTS = {
    'MIDI FOLLOW': (((MIDI_BASE, MIDI_SIZE),), midi_fields(3, 12, 13, 15)),
    'MIDI LOOPBACK': (((MIDI_BASE, MIDI_SIZE),), midi_fields(12)),
    'MIDI HARMONY': (((MIDI_BASE, MIDI_SIZE),), midi_fields(5, 16, 18, 19)),
    'MIDI SRAM': ((), ()),
}
# Optional companions extend replacement handling without owning native hooks.
# snapshot_pre gets d0=bank address before publication; replace_pre gets
# d0=working Part address after publication. All registers may be clobbered.
PART_CALLBACKS = {
    'snapshot_pre': (('MIDI HARMONY', 'hd_scenes_before'),),
    'replace_pre': (('MIDI HARMONY', 'hd_part_before'),),
}


def layout(modules, clients=None):
    clients = PART_CLIENTS if clients is None else clients
    active, windows, writes = [], [], set()
    for key, (ranges, fields) in clients.items():
        if not key or len(set(fields)) != len(fields):
            raise ValueError(f'invalid STORE Part client {key!r}')
        for start, size in ranges:
            if type(start) is not int or type(size) is not int or start < 0 or size <= 0 or start+size > PART_SIZE:
                raise ValueError(f'invalid STORE Part window for {key}')
        for offset in fields:
            if type(offset) is not int or not any(a <= offset < a+n for a,n in ranges):
                raise ValueError(f'STORE Part write outside read windows: {key} {offset}')
        if key in modules:
            active.append(key); windows.extend(ranges); writes.update(fields)
    merged = []
    for start, size in sorted(windows):
        end = start+size
        if merged and start <= merged[-1][0]+merged[-1][1]:
            a,n = merged[-1]; merged[-1] = (a, max(a+n,end)-a)
        else:
            merged.append((start,size))
    return tuple(active), tuple(merged), tuple(sorted(writes))


def part_inc(modules, remix=None):
    active, windows, writes = layout(modules)
    stride = max(1, sum(n for _,n in windows))
    out = [f'.set STORE_PART_STRIDE,{stride}', '.macro STORE_PART_READ_GUARD bad']
    for i,(start,size) in enumerate(windows):
        out += [f'    cmpi.l #{start},%d0', f'    bcs.w .Lread_next{i}\\@',
                f'    cmpi.l #{start+size},%d0', '    bcs.w .Lread_ok\\@', f'.Lread_next{i}\\@:']
    out += ['    bra.w \\bad', '.Lread_ok\\@:', '.endm', '.macro STORE_PART_WRITE_GUARD bad']
    # A byte table avoids generating one comparison for every track's field.
    out += ['    lea store_part_writable,%a0', '    move.l %d0,%d5',
            '    lsr.l #3,%d5', '    adda.l %d5,%a0', '    btst %d0,(%a0)',
            '    beq.w \\bad', '.endm']
    out += ['.macro STORE_PART_SNAPSHOT_INDEX']
    packed = 0
    for i,(start,size) in enumerate(windows):
        out += [f'    cmpi.l #{start+size},%d5', f'    bcc.w .Lindex_next{i}\\@',
                f'    addi.l #{packed-start},%d5', '    bra.w .Lindex_done\\@', f'.Lindex_next{i}\\@:']
        packed += size
    out += ['.Lindex_done\\@:', '.endm', '.macro STORE_PART_SNAPSHOT_COPY']
    packed = 0
    for i,(start,size) in enumerate(windows):
        out += ['    move.l %a0,%a2', f'    adda.l #{start},%a2']
        longs = size//4 if start%2 == 0 and packed%2 == 0 and stride%2 == 0 else 0
        if longs:
            out += [f'    move.l #{longs},%d4', f'.Lsnap{i}\\@:',
                    '    move.l (%a2)+,(%a1)+', '    subq.l #1,%d4', f'    bne.w .Lsnap{i}\\@']
        tail = size-4*longs
        if tail:
            out += [f'    move.l #{tail},%d4', f'.Ltail{i}\\@:',
                    '    move.b (%a2)+,(%a1)+', '    subq.l #1,%d4', f'    bne.w .Ltail{i}\\@']
        packed += size
    out += ['.endm']
    for event, clients in PART_CALLBACKS.items():
        out += [f'.macro STORE_PART_{event.upper()}']
        for key,symbol in clients:
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',symbol):
                raise ValueError(f'invalid STORE Part callback {symbol}')
            if key in modules:
                out += ['    lea -60(%sp),%sp', '    movem.l %d0-%d7/%a0-%a6,(%sp)',
                        f'    jsr {symbol}', '    movem.l (%sp),%d0-%d7/%a0-%a6', '    lea 60(%sp),%sp']
        out += ['.endm']
    out += ['.macro STORE_PART_COPY_OVERRIDE']
    if 'MIDI SRAM' in active:
        out += ['    jmp rp_store_copy']
    out += ['.endm', '.macro STORE_PART_NOTE_REFRESH']
    # NOTE SETUP stages the first six bytes as longs. Only live module fields
    # declared writable are refreshed; stock CHAN/BANK/PROG/SBNK stay staged.
    for field in (3,5):
        if MIDI_BASE+field in writes:
            out += ['    moveq #0,%d0', '    move.b 0x100b14cc,%d0', f'    moveq #{field},%d2',
                    '    jsr store_part_midi_read', '    tst.l %d0', f'    bmi.w .Lconfirm{field}\\@',
                    f'    move.l %d0,{hex(0x460d5cb4+field*4)}', f'.Lconfirm{field}\\@:']
    out += ['.endm', '.macro STORE_PART_WRITE_TABLE', '.balign 4', 'store_part_writable:']
    bits=bytearray((PART_SIZE+7)//8)
    for offset in writes: bits[offset//8] |= 1 << (offset%8)
    out += ['    .byte '+','.join(map(str,bits[i:i+32])) for i in range(0,len(bits),32)]
    out += ['.endm']
    return '\n'.join(out)+'\n'


def additions(modules):
    active, windows, writes = layout(modules)
    if not active:
        return dict(linked=(), detours=(), pokes=(), claims=None, gates=())
    stride = max(1, sum(n for _,n in windows))
    linked = (
        Linked('storepartentry','modules/store/part-entry.s',
               reference=(0x400d6b80,'c7a3725b8e7b3ba4f830795b198e6800b2fbf9490bbd52e26e70c88252ec9b88'),
               defsyms=(('store_part_native_copy',0x40a9582e),('store_part_native_init',0x40a95860)),
               runtime_refs=(('store_part_native_copy','storepartcopy','store_part_native_copy'),
                             ('store_part_native_init','storepartcopy','store_part_native_init'))),
        Linked('storepart','modules/store/part.s',dram=True,include=part_inc),
        Linked('storepartcopy','modules/store/part-copy.s',dram=True,include=part_inc,
               defsyms=(('store_part_copy_target',0),('store_part_init_target',0)),
               boot_mutable=(('store_part_snapshot',4*stride),('store_part_epochs',64*4))),
    )
    hooks = (
        Detour(0x40000512,bytes.fromhex('4eb94000f938'),'storepartentry','store_part_resident_activate','activate native Part service',kind='jsr'),
        Detour(0x40020898,bytes.fromhex('2f02226f0008'),'storepartentry','store_part_copy_entry','coherent native Part copy'),
        Detour(0x40005638,bytes.fromhex('4fefffa848d77cfc'),'storepartentry','store_part_init_entry','coherent native Part initialization',pad_to=8),
    )
    if any(MIDI_BASE+f in writes for f in (3,5)):
        linked += (Linked('storepartsetup','modules/store/part-setup.s',dram=True,include=part_inc),)
        hooks += (Detour(0x4004af20,bytes.fromhex('4fefffd448d77cfc'),'storepartsetup','store_part_note_confirm','preserve live native Part settings on NOTE SETUP YES',pad_to=8),)
    flags = any(MIDI_BASE+36*t+12 in writes for t in range(8))
    return dict(linked=linked,detours=hooks,
                pokes=(Poke(0x400d4082,bytes.fromhex('00000001'),bytes.fromhex('00000010'),'native MIDI SETUP shared flags range'),) if flags else (),
                claims=Claims(part_window=tuple((MIDI_BASE+36*t+12,1,'shared MIDI SETUP flags') for t in range(8))) if flags else Claims(),
                gates=tuple(Gate(f'tools/verify/verify_store_part{suffix}.py',stage='image',venv=True)
                            for suffix in ('','_copy','_boot','_activation','_settings','_selection')))
