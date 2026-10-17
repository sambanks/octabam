#!/usr/bin/env python3
"""Physical panel reports test MIDI detail-window ownership across track changes."""
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path
import midi_loopback_port as p
sys.path.insert(0, str(p.ROOT/'tools'))
from panel.panel_server import PortProc
from panel.panel_link import PanelLink


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', type=Path, required=True)
    ap.add_argument('--build-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--image', type=Path)
    ap.add_argument('--symbols', type=Path)
    ap.add_argument('--module', choices=['loopback','follow','harmony'], required=True)
    a=ap.parse_args(); root=a.build_root; p.OUT=a.out
    w=p.fixture(a.project,'panel')
    for path in (w/'project').glob('project.*'):
        data=re.sub(rb'MIDI_MODE=\d+',b'MIDI_MODE=0',path.read_bytes())
        if a.module=='loopback':
            # Internal note commands can select tracks through the native
            # receiver. Isolate physical track navigation from that separate
            # input source while changing DEST during sequencer playback.
            data=re.sub(rb'MIDI_AUDIO_TRK_NOTE_IN=\d+',b'MIDI_AUDIO_TRK_NOTE_IN=0',data)
        path.write_bytes(data)
    card,_=p.emu_card.stage_project(w/'project','OCTABAM','BASS',tree=w/'seed-tree')
    (w/'card.img').write_bytes(card)
    image=w/'candidate.bin'; image.write_bytes((a.image or root/'out/mainos_bus.bin').read_bytes())
    elf=root/'out/platform/runtime/runtime.elf'
    elf_hash=hashlib.sha256(elf.read_bytes()).hexdigest() if not a.symbols else None
    if a.symbols:
        sym=json.loads(a.symbols.read_text())
    else:
        raw=subprocess.check_output(['m68k-elf-nm',str(elf)],text=True)
        sym={n:int(h,16) for h,n in re.findall(r'^([0-9a-f]+) [A-Za-z] (\w+)$',raw,re.M)}
    (w/'symbols.json').write_text(json.dumps(sym,indent=2)+'\n')
    prefix,opener,knob,field,mask,shift={
        'loopback':('lb',0x38,0,12,12,2),
        'follow':('bf',0x3b,3,12,2,1),
        'harmony':('mh',0x3d,1,16,7,0)}[a.module]
    handle=sym[prefix+'_page_win']; owner=sym[prefix+'_page_track']; layer=sym[prefix+'_page_layer']
    windows=[sym[x+'_page_win'] for x in ('lb','bf','mh') if x+'_page_win' in sym]
    receipt=a.out/'receipt.json'; receipt.unlink(missing_ok=True)
    proc=PortProc([root/'out/emu/ot_emu','--image',image,'--card',w/'card.img',
        '--mount','--load-ms','90000','--set','OCTABAM','--project','BASS',
        '--mkii','--rtc','1800000000','--main-level','off','--internal-clock',
        '--interactive'])
    log=(w/'protocol.log').open('w'); rows=[0]*8; link=PanelLink(); results=[]; edits=0; commands=[]
    def cmd(s,e='ok'):
        commands.append(s)
        r=proc.command(s,e); log.write(s+'\n'+r+'\n'); log.flush(); return r
    def peek(addr,n=4): return bytes.fromhex(cmd(f'peek {addr:#x} {n}','peek').split()[1])
    def word(addr): return int.from_bytes(peek(addr),'big')
    def selected(): return peek(0x100b14cc,1)[0]
    def key(code,down=None,fast=False):
        for edge in ([True,False] if down is None else [down]):
            row,bit=code>>3,1<<(code&7)
            rows[row]=rows[row]|bit if edge else rows[row]&~bit
            cmd(f'key {0x20+row} {rows[row]}');cmd('run '+str((20 if fast else 80) if edge else (40 if fast else 220)))
    def layers():
        found=[]; addr=word(0x460d165c)
        while addr:
            assert addr not in found and len(found)<32,('bad input layer',found)
            found.append(addr);addr=word(addr)
        return found
    def settings():
        return b''.join(peek(0x40170f60+i*0x18b2+0x4e2,36*8) for i in range(4))
    def capture(name):
        link.feed(bytes.fromhex(cmd('tx','tx').partition(' ')[2]))
        (w/(name+'.png')).write_bytes(link.render_png(4))
    def opened(track):
        assert selected()==track,('selection',track,selected())
        assert word(handle) and word(owner)==track,('window ownership',track,word(owner))
        assert layers().count(layer)==1 and sum(bool(word(x)) for x in windows)==1
    def closed():
        assert not any(word(x) for x in windows) and layer not in layers(), 'stale window/layer'
    def edit(track):
        nonlocal edits
        opened(track); before=settings(); index=track*36+field
        old=(before[index]&mask)>>shift
        # Harmony's visible ROOT -> 1ST step is stored as 0 -> 2;
        # saved enum 1 is AUTO, which appears last in the UI.
        new=0 if old else (2 if a.module=='harmony' else 1)
        cmd(f'knob {0x30+knob} {4 if new else -4}');cmd('run 160')
        expected=bytearray(before);expected[index]=(expected[index]&~mask)|(new<<shift)
        actual=settings()
        diff=[(i,expected[i],actual[i]) for i in range(len(actual)) if actual[i]!=expected[i]]
        assert actual==expected,('wrong track/field edit',a.module,track,old,new,diff)
        edits+=1
    def transition(source,target,phase,fast=False,held=False):
        key(0x10+source);assert selected()==source
        before=settings();key(opener);opened(source)
        assert settings()==before,'opening changed settings'
        edit(source);before=settings()
        if held:
            before_layers=layers()
            key(0x10+target,True,fast);cmd('run 600')
            opened(source)
            assert layers()==before_layers+[0x400d164a], 'native track-hold layer missing'
            key(0x10+target,False,fast)
            opened(source)
            assert layers()==before_layers, 'held track did not restore its prior window'
            assert settings()==before, 'holding a track changed settings'
            # Stock treats a long hold as a modifier, not a selection. A
            # subsequent short tap closes the window and selects the track.
        key(0x10+target,fast=fast)
        closed();assert selected()==target,('first press must select like stock',source,target,selected())
        assert settings()==before,'closing changed settings'
        assert selected()==target,'track release selected a different track'
        assert settings()==before,'track selection changed settings'
        key(opener);opened(target);assert settings()==before
        edit(target)
        if source==0 and target==7 and phase=='stopped': capture('T8-details-after-T1')
        if source==7 and target==0 and phase=='stopped': capture('T1-details-after-T8')
        key(0x32);closed()
        assert not any(rows),'a physical key remains held'
        results.append(dict(phase=phase,source=source+1,target=target+1,fast=fast,held=held))
    try:
        proc.wait_ready(180);cmd('frame on');cmd('run 500');key(0x32)
        key(0x35);key(0x10);key(0x2d,True);key(0x22);key(0x2d,False)
        capture('note-setup')
        initial=settings(); baseline_layers=layers(); initial_commands=list(commands)
        for source in range(8):
            for target in range(8):transition(source,target,'stopped')
            print(f'{a.module}: source T{source+1}, all 8 destinations passed',flush=True)
        playback_start=len(commands)
        key(0x28);cmd('run 1000')
        for source in range(8):transition(source,(source+1)%8,'playing',fast=True,held=True)
        key(0x27);key(0x27);cmd('run 1000')
        assert layers()==baseline_layers,'input layers did not return to NOTE SETUP baseline'
        final=settings()
        assert final[288:]==initial[288:],'unrelated Part changed'
        capture('final-note-setup')
        playback_commands=initial_commands+commands[playback_start:]
        proc.quit()
        # Interactive mode exits before --midi-out is written. Replay the
        # same startup and playback gestures through the batch port to capture
        # UART0, rather than treating a missing recording as a product failure.
        script=[]; time=0; replay_rows=[0]*8
        for command in playback_commands:
            words=command.split()
            if words[0]=='run':time+=int(words[1])
            elif words[0]=='key':
                row=int(words[1],0)-0x20; value=int(words[2],0)
                for bit in range(8):
                    if (value^replay_rows[row])&(1<<bit):
                        edge='down' if value&(1<<bit) else 'up'
                        script.append(f'{time} key {row*8+bit:#x} {edge}')
                replay_rows[row]=value
            elif words[0]=='knob':script.append(f'{time} enc {int(words[1],0)-0x30} {words[2]}')
        script.append(f'{time+500} quit')
        live=w/'playback.txt';live.write_text('\n'.join(script)+'\n')
        batch=[str(root/'out/emu/ot_emu'),'--image',str(image),'--card',str(w/'card.img'),
               '--mount','--load-ms','90000','--set','OCTABAM','--project','BASS',
               '--mkii','--rtc','1800000000','--main-level','off','--internal-clock',
               '--live-script',str(live),'--midi-out',str(w/'output.midi')]
        with (w/'playback.log').open('w') as output:subprocess.run(batch,stdout=output,stderr=subprocess.STDOUT,check=True)
        assert 'ended on quit' in (w/'playback.log').read_text()
        events=p.follow.notes((w/'output.midi').read_bytes())
        assert any(e[0]=='on' for e in events),'playback positive control produced no MIDI notes'
        p.balanced(events)
        result=dict(status='pass',module=a.module,build_root=str(root),
          image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
          runtime_elf_sha256=elf_hash,
          test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          audio_note_receive_disabled=(a.module=='loopback'),
          transitions=results,exact_field_edits=edits,settings_checked_per_edit=1152,
          note_events=len(events),midi_balanced=True,other_parts_unchanged=True,
          final_layers=[hex(x) for x in baseline_layers],
          hardware_tested=False)
        receipt.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    finally:
        proc.quit();log.close()

if __name__=='__main__':main()
