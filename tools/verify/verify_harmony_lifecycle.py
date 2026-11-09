#!/usr/bin/env python3
"""Bound initialized Harmony edits/copies; require deferred, recoverable retention."""
import json
from unicorn import UC_HOOK_CODE
from harmony_midi_machine import Machine, ROOT
from verify_midi_scale_provider import symbols

LIMIT = 20_000  # The native MIDI harness limit, unchanged for this composition.
B, PS = 0x400e21e0, 0x18b2
RETAINED_COMMIT = 0x1001614e + 0x4900 + 30


def main():
    m = Machine(symbols); u = m.uc; s = m.sym
    m.call('store_part_activate', stop=0x4000f938)
    m.call('mhc_lock_init')  # Boot initialization is outside the per-operation measurement.
    if 'scn_slot_ptr' in s:
        # A loaded project has initialized Scenes before interactive edits.
        # Run its real public initialization, including the 256 KiB fill;
        # never count cold boot as an interactive mode edit or raise LIMIT.
        m.call('scn_slot_ptr', 0, 0)
    # A loaded empty bank: mapped firmware bytes are not a native pattern.
    for pattern in range(16):
        u.mem_write(B+pattern*0x8ed8+0x8e57, b'\x00')
        for track in range(8):
            for step in range(64):
                u.mem_write(B+pattern*0x8ed8+0x4900+track*0x8b0+step*32, b'\xff')
    measured = {}; save_calls = []; accumulator_packs = []
    def observe(uc, pc, size, data):
        if pc == s['hd_nv_save_c']: save_calls.append(pc)
        if pc == s['ha_pack_c']: accumulator_packs.append(pc)
    u.hook_add(UC_HOOK_CODE, observe)
    def c(name, *args):
        u.mem_write(m.stack+4, b''.join((x & 0xffffffff).to_bytes(4, 'big') for x in args))
        return m.call(name)
    def bounded(label, name, *args):
        count = [0]
        def tick(*unused): count[0] += 1
        hook = u.hook_add(UC_HOOK_CODE, tick)
        try: result = m.call(name, *args, instruction_budget=LIMIT)
        finally: u.hook_del(hook)
        measured[label] = count[0]
        return result
    # All three mode transitions on initialized, valid retained data. The
    # control before the fix passes the incomplete Follow fixture only after
    # raising its limit; here its full bank save exceeds the unchanged bound.
    for mode in (1, 2, 0):
        assert bounded(f'empty_mode_{mode}', 'mh_set', 0, mode) == 1
    assert not save_calls and not accumulator_packs, 'mode edit serialized a bank synchronously'
    part = B+0x8ed80; source = m.scratch+0x1000
    u.mem_write(source, bytes(u.mem_read(part, PS)))
    for slot in (0, 3):
        u.mem_write(m.stack+4, b''.join(x.to_bytes(4, 'big') for x in (part+slot*PS, source, PS)))
        bounded(f'inactive_part_{slot}', 'store_part_native_copy')
    # Make a valid retained checkpoint, then edit again. Edits must invalidate
    # before returning, coalesce, and restore the latest degree after the poll.
    assert bounded('enter_note', 'mh_set', 0, 1) == 1
    c('hd_edit_step_c', 0, 0, 0, 0, 35)
    c('hd_nv_poll_c')
    assert len(save_calls) == 1 and len(accumulator_packs) == 1
    assert int.from_bytes(u.mem_read(RETAINED_COMMIT, 2), 'big') & 0xc000 == 0x8000
    for mode in (2, 1):
        assert bounded(f'attached_mode_{mode}', 'mh_set', 0, mode) == 1
    c('hd_edit_step_c', 0, 0, 0, 0, 39)
    assert len(save_calls) == 1 and len(accumulator_packs) == 1
    assert int.from_bytes(u.mem_read(RETAINED_COMMIT, 2), 'big') & 0xc000 == 0
    c('hd_nv_poll_c')
    assert len(save_calls) == 2 and len(accumulator_packs) == 2
    c('hd_nv_poll_c')
    assert len(save_calls) == 2, 'unchanged UI poll serialized the bank again'
    c('hd_bank_reset_c', 0)
    assert c('hd_nv_restore_c', 0) == 1
    result = c('hd_degree_c', 0, 0, 0, 0)
    assert result == 39, (result, bytes(u.mem_read(s['hd_banks'], 1)).hex(),
                          bytes(u.mem_read(s['hd_banks']+128, 3)).hex(),
                          bytes(u.mem_read(m.part_address(0, 5), 1)).hex())
    # Restored roots reattach through playback and must re-enter the index.
    u.mem_write(source, bytes(u.mem_read(part, PS)))
    u.mem_write(m.stack+4, b''.join(x.to_bytes(4, 'big') for x in (part, source, PS)))
    bounded('restored_part', 'store_part_native_copy')
    assert u.mem_read(s['hd_banks']+130, 1) == b'\xff'
    assert u.mem_read(s['hd_banks'], 1) == b'\x27'
    # Invalid roots must stop before the accumulator copy on both save paths.
    u.mem_write(s['hd_banks']+128, b'\xff')
    packs = len(accumulator_packs)
    c('hd_nv_save_c', 0)
    assert len(accumulator_packs) == packs
    assert c('hd_export_c', 0, m.scratch+0x1000) == 0
    assert len(accumulator_packs) == packs
    report = dict(instruction_limit=LIMIT, instructions=measured,
                  initialized_retention=True, deferred_save_and_restore='pass',
                  invalid_payload_short_circuit='pass', hardware_timing=False)
    (ROOT/'out/harmony-lifecycle.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
