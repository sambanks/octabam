#!/usr/bin/env python3
"""Run the real degree-bank/transition code in ColdFire memory.

Independent host assertions cover native NOTE and retained mirrors, Part key
scope, inheritance and every byte outside the authorized root/dirty writes.
This is a component gate, not the later UI/file/port acceptance gate.
"""
from harmony_midi_machine import HARMONY_SOURCE
import json
import pathlib
import re
import runpy
import subprocess
import sys
import tempfile
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import *
from verify_harmony_degree_codec import MODES

ROOT = pathlib.Path(__file__).resolve().parents[2]
BANK = 0x9b340
PAT = 0x8ed8
PART = 0x18b2
BASE = 0x400e21e0
HDSIZE = 16768
LANE = 131


def main():
    subprocess.run(['python3', str(HARMONY_SOURCE/'generate.py'), '--check'], check=True)
    with tempfile.TemporaryDirectory(prefix='harmony-degree-core-') as tmp:
        out = pathlib.Path(tmp)
        scales = '--without-scales' not in sys.argv
        sys.path.insert(0,str(ROOT/'tools'))
        part_inc=runpy.run_path(str(ROOT/'modules/store/parts.py'))['part_inc']
        selected = {'MIDI HARMONY', 'MIDI FOLLOW'} | ({'MIDI SCALES'} if scales else set())
        integration = HARMONY_SOURCE.parents[1]/'integration'
        provider = runpy.run_path(str(integration/'scale_provider.py'))
        (out/'remix.inc').write_text(part_inc(selected) + provider['scale_inc'](selected)
                                    + provider['_reader_inc'](selected)
                                    + '.set HD_FOLLOW,1\n.set HD_SCENES,0\n')
        (out/'stub.s').write_text("""
.data
.global ch_lock_table,ch_nv_bank,ch_lock_status
ch_nv_bank: .long -1
ch_lock_status: .space 16
.bss
ch_lock_table: .space 131072
.global ch_messages,store_part_snapshot_bank,store_part_snapshot_parts,store_part_snapshot,store_part_epochs
ch_messages: .space 4096
store_part_snapshot_bank: .space 4
store_part_snapshot_parts: .space 4
store_part_snapshot: .space 1152
store_part_epochs: .space 256
""")
        objects = []
        for name, source in [('codec', HARMONY_SOURCE/'codec.s'),
                             ('accumulator', HARMONY_SOURCE/'accumulator.s'),
                             ('roots', HARMONY_SOURCE/'roots.s'),
                             ('core', HARMONY_SOURCE/'core.s'),
                             ('access', HARMONY_SOURCE/'part-access.s'),
                             ('scale-key', integration/'scale_key.s'),
                             ('scale-math', integration/'scale_math.s'),
                             ('part', ROOT/'modules/store/part.s'),
                             ('events', HARMONY_SOURCE/'events.s'),
                             ('scenes', HARMONY_SOURCE/'scenes.s'),
                             ('ui', HARMONY_SOURCE/'ui.s'),
                             ('scene_access', HARMONY_SOURCE/'scene-access.s'),
                             ('recording', HARMONY_SOURCE/'recording.s'),
                             ('packed', HARMONY_SOURCE/'packed.s'),
                             ('storage', HARMONY_SOURCE/'storage.s'),
                             ('track-retention', HARMONY_SOURCE/'track-retention.s'),
                             ('stub', out/'stub.s')]:
            obj = out/f'{name}.o'
            subprocess.run(['m68k-elf-as', '-mcpu=54455', '-I', str(out), '-o', str(obj), str(source)], check=True)
            objects.append(str(obj))
        subprocess.run(['m68k-elf-ld', '-Ttext=0x47000000', '-e', 'hd_reset_c',
                        '-o', str(out/'core.elf'), *objects], check=True)
        subprocess.run(['m68k-elf-objcopy', '-O', 'binary', str(out/'core.elf'), str(out/'core.bin')], check=True)
        nm = subprocess.check_output(['m68k-elf-nm', str(out/'core.elf')], text=True)
        sym = {n: int(a, 16) for a, n in re.findall(r'^([0-9a-f]+) [TtBbDd] ((?:hd|ch|store_part)_\w+)$', nm, re.M)}
        u = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        for a, n in ((0x47000000, 0x100000), (0x40000000, 0x1000000),
                     (0x10000000, 0x100000), (0x80000000, 0x10000), (0x46c70000, 0x20000)):
            u.mem_map(a, n)
        u.mem_write(0x47000000, (out/'core.bin').read_bytes())
        stack, done = 0x470f0000, 0x470ffff0
        reached = []
        def hook(u, pc, n, data):
            if pc == done:
                reached.append(True)
                u.emu_stop()
        u.hook_add(UC_HOOK_CODE, hook)
        def call(name, *args):
            reached.clear()
            u.reg_write(UC_M68K_REG_SR, 0x2700)
            u.reg_write(UC_M68K_REG_A7, stack)
            u.mem_write(stack, b''.join((v & 0xffffffff).to_bytes(4, 'big') for v in (done, *args)))
            u.emu_start(sym[name], 0, count=30000000)
            assert reached, (name, args, hex(u.reg_read(UC_M68K_REG_PC)))
            value = u.reg_read(UC_M68K_REG_D0)
            return value if value < 0x80000000 else value-0x100000000
        def byte(a): return u.mem_read(a, 1)[0]
        def put(a, v): u.mem_write(a, bytes((v,)))
        def po(part): return (0x8ed80 + part*PART) if part < 4 else (0x9504a+(part-4)*PART)
        def note(b, p, t, s): return BASE+b*BANK+p*PAT+0x4900+t*0x8b0+s*32
        def base(b, part, t): return BASE+b*BANK+po(part)+0x3e2+t*32
        def key(b, part, t): return BASE+b*BANK+po(part)+0x4e2+t*36+17
        def degree(b,p,t,s): return sym['hd_banks']+b*HDSIZE+(p*8+t)*LANE+s
        def field(b,part,t,slot): return BASE+b*BANK+po(part)+0x4e2+t*36+slot
        def mode(b,part,t,value):
            put(field(b,part,t,5),value)
            put(sym['hd_busy']+t,0)
        def ui(b,part,p=0):
            u.mem_write(0x46c82456,(BASE+b*BANK).to_bytes(4,'big'))
            put(0x100b14cf,part)
            put(0x100b14d0,p)
        call('hd_reset_c')
        before=[]
        for b in range(16):
            data=bytearray(b'\x55'*BANK)
            for p in range(16):
                data[p*PAT+0x8e57]=p%4
                for t in range(8):
                    for step in range(64):
                        data[p*PAT+0x4900+t*0x8b0+step*32]=48 if step%4==0 else 255
            for part in range(8):
                for t in range(8):
                    data[po(part)+0x3e2+t*32]=48
                    data[po(part)+0x4e2+t*36+3]=0
                    data[po(part)+0x4e2+t*36+5]=0
                    data[po(part)+0x4e2+t*36+17]=2
                    data[po(part)+0x4e2+t*36+19]=35
            u.mem_write(BASE+b*BANK,bytes(data))
            before.append(bytes(data))
            call('hd_bank_loaded_c',b)
        ui(0,0)
        # Native KEY decoding agrees with the selected module vocabulary;
        # undefined extended IDs cannot activate unavailable scale modes.
        for raw in range(256):
            put(key(0,0,0),raw)
            expected = 0
            if 1 <= raw <= 24:
                expected = ((raw-1)//2)*4+((raw-1)%2)*320
            elif scales and 25 <= raw <= 84:
                expected = ((raw-25)//5)*4+(1,2,3,4,6)[(raw-25)%5]*64
            assert call('hd_scale_c',0,0,0)==expected, (raw,scales)
        put(key(0,0,0),2)
        # OFF access never converts pitches, creates degrees or dirties banks.
        for b in range(16):
            for p in range(16): assert call('hd_sync_c',b,p,0)==0
            assert bytes(u.mem_read(BASE+b*BANK,BANK))==before[b]
        # Explicit HARM entry edits one selected Part default and current
        # pattern. Unrelated Parts, banks, saved copies and tracks stay stock.
        call('hd_mode_c',0,2)
        mode(0,0,0,2)  # publish through the shared setter's storage position
        assert call('hd_degree_c',0,0,0,0)==35
        assert call('hd_degree_c',0,0,0,1)==35
        assert call('hd_degree_c',0,1,0,0)==-1
        assert call('hd_degree_c',1,0,0,0)==-1
        for b in range(1,16): assert bytes(u.mem_read(BASE+b*BANK,BANK))==before[b]
        # An explicit OFF edit freezes inactive patterns still attached to
        # this same Part before KEY can change while OFF. No stale degree
        # identity survives an OFF->HARM round trip that has no intervening trig.
        assert call('hd_degree_c',0,4,0,0)==35
        put(key(0,0,0),6)
        call('hd_mode_c',0,0); mode(0,0,0,0)
        assert byte(note(0,4,0,0))==50
        put(key(0,0,0),10)
        call('hd_mode_c',0,1); mode(0,0,0,1)
        assert call('hd_degree_c',0,4,0,0)==34
        put(key(0,0,0),2)
        call('hd_edit_step_c',0,0,0,0,35)
        # Base editing is a native Part write, with CS1 and dirty flags; it is
        # not a field in the degree companion and cannot shadow an incoming Kit.
        call('hd_edit_base_c',0,0,0,39)
        assert byte(field(0,0,0,19))==39
        assert byte(0x100a4ece+0x4e2+19)==39
        assert call('hd_degree_c',0,0,0,1)==39
        assert call('hd_degree_c',0,0,0,0)==35
        put(field(0,0,0,19),37)
        assert call('hd_degree_c',0,0,0,1)==37
        # HARM to HARM preserves degree when a pattern uses a different Part.
        mode(0,1,0,1); put(key(0,1,0),6)
        put(BASE+0x8e57,1)
        assert call('hd_resolve_c',0,0,0,0)==50
        assert byte(degree(0,0,0,0))==35
        assert call('hd_degree_c',0,0,0,1)==35
        # Repoint to OFF preserves outgoing D3, while that Part's native
        # unlocked default is left completely untouched.
        mode(0,2,0,0); put(key(0,2,0),10); put(base(0,2,0),67)
        put(BASE+0x8e57,2)
        assert call('hd_sync_c',0,0,0)==0
        assert byte(note(0,0,0,0))==50
        assert byte(note(0,0,0,1))==255 and byte(base(0,2,0))==67
        # Same physical slot: C minor HARM -> D minor OFF commits C3.
        put(BASE+0x8e57,0); mode(0,0,0,2); put(key(0,0,0),2)
        put(note(0,0,0,0),48)
        assert call('hd_degree_c',0,0,0,0)==35
        snapshot=bytes(u.mem_read(sym['hd_banks'],16*HDSIZE))
        call('hd_part_before_c',BASE+po(0))
        assert byte(degree(0,0,0,130))==255
        mode(0,0,0,0); put(key(0,0,0),6); put(base(0,0,0),65)
        assert call('hd_sync_c',0,0,0)==0
        assert byte(note(0,0,0,0))==48
        assert byte(note(0,0,0,1))==255 and byte(base(0,0,0))==65
        assert bytes(u.mem_read(sym['hd_banks']+HDSIZE,15*HDSIZE))==snapshot[HDSIZE:]
        # A later reuse cannot replace already-detached outgoing scale.
        mode(0,0,0,2); put(key(0,0,0),2)
        assert call('hd_degree_c',0,0,0,0)==35
        call('hd_part_before_c',BASE+po(0))
        put(key(0,0,0),10)
        ui(0,0,4)  # this detached record is inactive during the second reuse
        call('hd_part_before_c',BASE+po(0))
        ui(0,0)
        mode(0,0,0,0)
        assert call('hd_sync_c',0,0,0)==0 and byte(note(0,0,0,0))==48
        # OFF note editing and a KEY change produce a new degree on entry.
        put(note(0,0,0,0),50)
        mode(0,0,0,1)
        assert call('hd_degree_c',0,0,0,0)==34
        # Native edits and identical-pitch replacement after clear.
        put(note(0,0,0,0),55)
        assert call('hd_degree_c',0,0,0,0)==37
        call('hd_forget_c',0,0,0,0)
        assert byte(note(0,0,0,0))==255
        put(note(0,0,0,0),55)
        assert call('hd_degree_c',0,0,0,0)==37
        # Follow source uses that source track's playing context, never UI.
        put(field(0,0,1,3),1)
        put(0x8000666e,7); put(0x80006676,3)
        put(key(7,3,0),6)
        put(key(0,0,0),10)
        assert call('hd_scale_c',0,0,1)==328
        mode(0,0,1,2)
        call('hd_degree_c',0,0,1,0)
        call('hd_part_before_c',BASE+7*BANK+po(3))
        assert byte(degree(0,0,1,130))==255
        # Multi-hop Follow uses the ultimate source and detaches when an
        # intermediate Part's RFOL is replaced. Cycles fall back to own KEY.
        put(field(0,0,2,3),2)
        put(0x8000182b,0); put(0x80001833,0)
        assert call('hd_scale_c',0,0,2)==328
        assert call('hd_context_depends_c',0,2,31)==1
        put(field(7,3,0,3),3)
        put(0x8000182c,0); put(0x80001834,0)
        assert call('hd_scale_c',0,0,2)==320
        put(field(7,3,0,3),0)
        # An interruption during snapshot publication cannot reattach roots.
        # Unaffected Parts keep their association, so later KEY edits matter.
        ui(0,0); mode(0,0,0,2); put(key(0,0,0),2); put(BASE+0x8e57,0)
        call('hd_edit_step_c',0,0,0,0,35)
        mode(0,1,0,2); put(key(0,1,0),6)
        call('hd_degree_c',0,1,0,0)
        for part in range(4):
            u.mem_write(sym['store_part_snapshot']+part*288,bytes(u.mem_read(BASE+po(part)+0x4e2,288)))
        u.mem_write(sym['store_part_snapshot_parts'],(1).to_bytes(4,'big'))
        u.mem_write(sym['store_part_snapshot_bank'],BASE.to_bytes(4,'big'))
        call('hd_part_before_c',BASE+po(0))
        assert byte(degree(0,1,0,130))==1
        for _ in range(3):
            assert call('hd_resolve_c',0,0,0,0)==48
            assert byte(degree(0,0,0,130))==255
        mode(0,0,0,0); put(key(0,0,0),6)
        assert call('hd_resolve_c',0,0,0,0)==48
        u.mem_write(sym['store_part_snapshot_bank'],bytes(4))
        u.mem_write(sym['store_part_snapshot_parts'],bytes(4))
        assert call('hd_sync_c',0,0,0)==0 and byte(note(0,0,0,0))==48
        # A stopped rapid HARM -> OFF -> HARM recall observes the outgoing
        # OFF representation before replacing it again, without any trig.
        mode(0,0,0,2); put(key(0,0,0),2)
        call('hd_edit_step_c',0,0,0,0,35)
        call('hd_part_before_c',BASE+po(0))
        mode(0,0,0,0); put(key(0,0,0),6)
        call('hd_part_before_c',BASE+po(0))
        assert byte(note(0,0,0,0))==48
        mode(0,0,0,2)
        assert call('hd_degree_c',0,0,0,0)==34  # C3 is degree 7:2 in D minor
        # All pending slots retain outgoing C3 through same-slot OFF recall;
        # a mode edit in another Part never converts their representation.
        call('hd_events_reset_c')
        put(key(0,0,0),2); call('hd_edit_step_c',0,0,0,0,35)
        for slot in range(4): call('hd_event_stage_c',0,0,0,0,slot)
        ui(0,1,1); call('hd_events_mode_c',0,0); ui(0,0)
        call('hd_part_before_c',BASE+po(0))
        mode(0,0,0,0); put(key(0,0,0),6)
        for slot in range(4): assert call('hd_event_fire_c',slot*8,0)==48
        # Queued physical pitch remains intact; only captured representation
        # crosses HARM/OFF. A different UI Part's edit cannot convert it.
        msg=sym['ch_messages']
        u.mem_write(msg,bytes((70,8,48,100))+bytes(9)+bytes((0,1,0)))
        mode(0,0,0,2); put(key(0,0,0),2)
        captured=call('hd_capture_message_c',msg,48,0); put(msg+15,captured)
        assert captured==35
        ui(0,1,1); call('hd_record_modes_c',0,0)
        assert byte(msg+15)==35
        ui(0,0); call('hd_part_before_c',BASE+po(0))
        mode(0,0,0,0); put(key(0,0,0),6)
        call('hd_record_consume_c',msg)
        assert byte(msg+15)==176 and byte(msg+2)==48
        # Fingerprints ignore Part assignments/defaults. Native pattern hash
        # is supplied by the file layer and remains unchanged here.
        assert call('hd_native_hash_c',0,0x12345678)==0x12345678
        put(field(0,0,0,19),55); put(base(0,0,0),99); put(BASE+0x8e57,3)
        assert call('hd_native_hash_c',0,0x12345678)==0x12345678
        # Dense retention: all qualities and pattern lanes, no Part defaults.
        from verify_midi_sram import BASE as SRAM_BASE, OFFSETS
        payload_len=15104
        chord=sym['ch_lock_table']
        def snapshot():
            bank=bytes(u.mem_read(SRAM_BASE,16*0x8ed8))
            return bytes(bank[o] for o in OFFSETS)
        def install(data):
            for i in range(0,len(data),2):u.mem_write(SRAM_BASE+OFFSETS[i],data[i:i+2])
        u.mem_write(chord,bytes(i%8 for i in range(8192)))
        call('hd_nv_save_c',0)
        saved=snapshot()
        assert len(saved)==16384 and int.from_bytes(saved[:2],'big')&0xc000==0x8000
        h_before=bytearray(u.mem_read(sym['hd_banks'],HDSIZE))
        for lane in range(128): h_before[lane*LANE+130]=255
        q_before=bytes(u.mem_read(chord,8192))
        call('hd_bank_reset_c',0); u.mem_write(chord,b'\xff'*8192)
        put(field(0,0,0,19),42)
        assert call('hd_nv_restore_c',0)==1
        assert bytes(u.mem_read(sym['hd_banks'],HDSIZE))==h_before
        assert bytes(u.mem_read(chord,8192))==q_before
        assert byte(field(0,0,0,19))==42, 'companion overwrote incoming Part default'
        corrupt_positions=(0,4,8,12,16,24,28,32,8223,8224,8352,8353,8354,len(saved)-1)
        for pos in corrupt_positions:
            broken=bytearray(saved); broken[pos]^=0x80
            install(bytes(broken))
            assert call('hd_nv_restore_c',0)==0,pos
            assert bytes(u.mem_read(sym['hd_banks'],HDSIZE))==h_before
            assert bytes(u.mem_read(chord,8192))==q_before
        install(saved)
        assert call('hd_nv_restore_c',1)==0
        assert call('hd_validate_c',sym['hd_banks'])==1
        print(json.dumps({'banks':16,'patterns':256,'scales_module':scales,'native_key_values':256,'part_default_authority':'passed',
                          'off_stock_and_unrelated_banks':'byte comparisons passed',
                          'same_slot_outgoing_c3_follow_and_new_entry':'passed',
                'snapshot_no_reattachment_and_unaffected_part':'passed',
                'follow_chain_cycle_and_source_replacement':'passed',
                'rapid_stopped_mode_recall':'passed',
                'queued_sequence_and_physical_recording_c3':'passed',
                          'retained_payload_bytes':payload_len,'corruption_rejected':len(corrupt_positions)+1,
                          'evidence':'ColdFire core with shared Part access','hardware_tested':False}))


if __name__ == '__main__':
    main()
