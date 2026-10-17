#!/usr/bin/env python3
"""Measure native track selection from MIDI setup pages and the stock TEMPO popup."""
import argparse
from pathlib import Path
import sys,re,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--project',type=Path,required=True)
ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args()
sys.path.insert(0,str(ROOT/'tools/verify'))
import midi_loopback_port as p
sys.path.insert(0,str(ROOT/'tools'))
from panel.panel_server import PortProc
from panel.panel_link import PanelLink
out=a.out;p.OUT=out
w=p.fixture(a.project,'panel')
for path in (w/'project').glob('project.*'):path.write_bytes(re.sub(rb'MIDI_MODE=\d+',b'MIDI_MODE=0',path.read_bytes()))
card,_=p.emu_card.stage_project(w/'project','OCTABAM','BASS',tree=w/'seed-tree');(w/'card.img').write_bytes(card)
image=w/'stock.bin';image.write_bytes((ROOT/'out/raw/section_3_MAIN_OS.bin').read_bytes())
proc=PortProc([ROOT/'out/emu/ot_emu','--image',image,'--card',w/'card.img','--mount','--load-ms','90000','--set','OCTABAM','--project','BASS','--mkii','--rtc','1800000000','--main-level','off','--internal-clock','--interactive'])
log=(w/'protocol.log').open('w');rows=[0]*8;link=PanelLink();results={}
def cmd(s,e='ok'):
 r=proc.command(s,e);log.write(s+'\n'+r+'\n');log.flush();return r
def peek(a,n=4):return bytes.fromhex(cmd(f'peek {a:#x} {n}','peek').split()[1])
def key(c,d=None):
 for edge in ([True,False] if d is None else [d]):
  row,bit=c>>3,1<<(c&7);rows[row]=rows[row]|bit if edge else rows[row]&~bit
  cmd(f'key {0x20+row} {rows[row]}');cmd('run 80' if edge else 'run 220')
def capture(name):
 link.feed(bytes.fromhex(cmd('tx','tx').partition(' ')[2]));(w/(name+'.png')).write_bytes(link.render_png(4))
 layers=[];a=int.from_bytes(peek(0x460d165c),'big')
 while a:
  assert a not in layers and len(layers)<32
  layers.append(a);a=int.from_bytes(peek(a),'big')
 results[name]=dict(track=peek(0x100b14cc,1)[0]+1,layers=[hex(x) for x in layers],track_press_handler=peek(0x46c7d8de+0x17*24,24).hex())
 print(name,results[name],flush=True)
def setup(c):key(0x2d,True);key(c);key(0x2d,False)
try:
 proc.wait_ready(180);cmd('frame on');cmd('run 500');key(0x32);key(0x35);key(0x10);setup(0x22)
 capture('note-setup-T1');key(0x17);capture('note-setup-first-T8');key(0x17);capture('note-setup-second-T8')
 key(0x10);key(0x18);capture('tempo-T1');key(0x17);capture('tempo-first-T8');key(0x17);capture('tempo-second-T8');key(0x32)
 key(0x10);setup(0x24);capture('lfo-setup-T1');key(0x17);capture('lfo-setup-first-T8');key(0x10);key(0x38);capture('lfo-setup-push-A');key(0x17);capture('lfo-details-first-T8');key(0x32)
 key(0x10);setup(0x23);capture('arp-setup-T1');key(0x17);capture('arp-setup-first-T8');key(0x32)
 key(0x10);setup(0x25);capture('cc-setup-T1');key(0x38);capture('cc-setup-push-A');key(0x17);capture('cc-details-first-T8')
 key(0x32);key(0x10);setup(0x22)
 for phase in ['stopped','playing']:
  if phase=='playing':key(0x28)
  key(0x10);key(0x18);capture(phase+'-tempo-before-hold')
  key(0x17,True);cmd('run 600');capture(phase+'-tempo-T8-held')
  key(0x17,False);capture(phase+'-tempo-T8-released')
  assert results[phase+'-tempo-T8-held']['track']==1
  assert results[phase+'-tempo-T8-held']['layers']==results[phase+'-tempo-before-hold']['layers']+['0x400d164a']
  assert results[phase+'-tempo-T8-released']['track']==1
  assert results[phase+'-tempo-T8-released']['layers']==results[phase+'-tempo-before-hold']['layers']
  key(0x17,True);key(0x17,False);capture(phase+'-tempo-after-tap')
  assert results[phase+'-tempo-after-tap']['track']==8
  assert results[phase+'-tempo-after-tap']['layers']==results['note-setup-T1']['layers']
 key(0x27)
 for name in ['note-setup-first-T8','tempo-first-T8','lfo-setup-first-T8','arp-setup-first-T8','cc-details-first-T8']:
  assert results[name]['track']==8, (name,results[name])
 assert len(results['tempo-T1']['layers'])==3
 assert results['tempo-first-T8']['layers']==results['note-setup-T1']['layers']
 (out/'receipt.json').write_text(json.dumps(dict(status='pass',test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),observations=results,hardware_tested=False),indent=2)+'\n')
finally:proc.quit();log.close()
