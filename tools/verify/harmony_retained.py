"""Inspection helpers for Harmony's own-step retained layout, not musical oracles."""
from verify_midi_sram import BASE, OFFSETS

def snapshot(m):
    data=bytes(m.uc.mem_read(BASE,16*0x8ed8))
    return bytes(data[o] for o in OFFSETS)

def install(m,data):
    assert len(data)==16384
    for i in range(0,len(data),2):
        m.uc.mem_write(BASE+OFFSETS[i],bytes(data[i:i+2]))

def committed(m):
    return int.from_bytes(m.uc.mem_read(BASE+OFFSETS[0],2),'big') & 0xc000 == 0x8000

def raw_p2(records, bank=0):
    """Independent upstream P2NV fixture; no compression implementation needed."""
    import struct
    entries=[(index<<7)|value for index,value in records]
    return struct.pack('>4sIII',b'P2NV',bank,len(entries),sum(entries)&0xffffffff)+b''.join(
        entry.to_bytes(3,'big') for entry in entries)
