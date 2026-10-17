#!/usr/bin/env python3
"""Physical live keys and native arpeggiator through Loopback and the real MIDI task."""
import argparse
import hashlib
import json
from pathlib import Path
import midi_loopback_port as p
import verify_midi_loopback as lb


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix')
    ap.add_argument('--project',type=Path,required=True)
    a=ap.parse_args()
    p.OUT=p.ROOT/'out'/f'{a.remix}-producers-port'
    image=p.freeze_candidate(p.OUT)
    sym=lb.symbols()
    results={}
    for arp in (False,True):
        w=p.fixture(a.project,'arp' if arp else 'live',{0:2},arp=arp)
        script=w/'keys.txt'
        script.write_text('100 key 0x31 down\n200 key 0x31 up\n1000 key 0 down\n1800 key 4 down\n2600 key 0 up\n3400 key 4 up\n4300 quit\n')
        results[w.name]={}
        for route in range(3):
            name=f'dest-{route}'
            stats=w/f'{name}-stats.bin'
            held=w/f'{name}-held.bin'
            extra=['--step','-:poke:0x80000015=1','--step','-:poke:0x460d16f3=1',
                   '--step','-:poke:0x100b14cc=0',
                   '--step',f'-:call:{sym["lb_dest_write"]:#x},0,{route}',
                   '--internal-clock','--live-script',script,
                   '--mem-dump',f'{sym["lb_accepted"]:#x},8={stats};{sym["lb_internal_held"]:#x},4={held}']
            events=p.run(w,name,extra,physical_panel=True)
            p.balanced(events)
            accepted,delivered=(int.from_bytes(stats.read_bytes()[i:i+4],'big') for i in (0,4))
            assert accepted==delivered,(name,accepted,delivered)
            assert held.read_bytes()==bytes(4),(name,'held internal notes')
            assert bool(events)==(route!=1),(w.name,name,events)
            assert bool(accepted)==(route!=0),(w.name,name,accepted)
            results[w.name][route]={'notes':events,'internal_messages':accepted}
            print(f'[ok] physical keys {w.name} DEST {route}: {len(events)} external notes, {accepted} internal messages; balanced',flush=True)
        assert results[w.name][0]['notes']==results[w.name][2]['notes']
        assert results[w.name][1]['internal_messages']==results[w.name][2]['internal_messages']
    (p.OUT/'result.json').write_text(json.dumps({'status':'pass','image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
        'cases':results,'hardware_tested':False},indent=2)+'\n')


if __name__=='__main__':main()
