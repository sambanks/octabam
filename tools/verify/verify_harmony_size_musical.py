#!/usr/bin/env python3
"""Audit actual ColdFire pitches against explicit musical acceptance criteria.

The guide supplies principles, not numerical spacing limits. The low-register
limits below are our conservative product policy. MIDI/WAV files render the
captured firmware output; the simple audition synth is not Octatrack hardware.
"""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import subprocess
import wave
import verify_midi_harmony as h

GUIDE='https://viva.pressbooks.pub/openmusictheorycopy/chapter/jazz-voicings/'


class MusicalMachine(h.Machine):
    def __init__(self, out):
        nm=subprocess.check_output(['m68k-elf-nm',str(out/'platform/runtime/runtime.elf')],text=True)
        sym={f[2]:int(f[0],16) for line in nm.splitlines() if len(f:=line.split())==3}
        h.LinkedMidiMachine.__init__(self,lambda:sym,artifact_root=out)

    def configure(self,size,root=0,voic=1,spread=0,key=0,scale=0):
        self.setting(0,2,key,scale)
        for name,value in [('size',size-1),('root',root),('voic',voic),('sprd',spread)]:
            self.call('mh_'+name+'_set',0,value)

    def sound(self,root,quality):
        self.uc.mem_write(self.sym['ch_current'],bytes([quality]))
        raw=self.chord(0,root)
        self.uc.mem_write(self.scratch,bytes(raw))
        self.call('mh_voice',0,a0=self.scratch)
        return dict(root=raw[0],quality=quality,raw=raw,
                    notes=[p for p in self.uc.mem_read(self.scratch,4) if p<128])


def clear_spacing(notes):
    return all(b-a >= ((7 if i==0 else 5) if a<48 else 3 if a<60 else 1)
               for i,(a,b) in enumerate(zip(notes,notes[1:])))


def audition(cases,out):
    """Portable standard MIDI plus a neutral harmonic-pluck WAV, same pitches."""
    def vlq(n):
        data=[n&127]
        while n>>7:
            n>>=7;data.insert(0,128|(n&127))
        return bytes(data)
    midi=bytearray(b'\0\xff\x51\x03\x07\xa1\x20\0\xc0\0')
    samples=array.array('h');rate=16000
    for case in cases:
        label=case['name'].encode()
        midi+=b'\0\xff\x06'+vlq(len(label))+label
        for row in case['rows']:
            notes=row['notes']
            for i,pitch in enumerate(notes):midi+=vlq(240 if i==0 else 0)+bytes((0x90,pitch,80))
            for i,pitch in enumerate(notes):midi+=vlq(720 if i==0 else 0)+bytes((0x80,pitch,0))
            samples.extend([0]*(rate//4))
            frequencies=[440*2**((p-69)/12) for p in notes]
            for i in range(rate*3//4):
                t=i/rate
                envelope=min(1,t/.01)*min(1,(.75-t)/.12)*math.exp(-2.2*t)
                value=sum(sum(weight*math.sin(2*math.pi*f*harmonic*t)
                              for harmonic,weight in ((1,.78),(2,.15),(3,.07)))
                          for f in frequencies)*envelope/max(1,len(notes))
                samples.append(round(24000*value))
    midi+=b'\0\xff\x2f\0'
    (out/'audition.mid').write_bytes(b'MThd\0\0\0\x06\0\0\0\x01\x01\xe0MTrk'+len(midi).to_bytes(4,'big')+midi)
    with wave.open(str(out/'audition.wav'),'wb') as wav:
        wav.setparams((1,2,rate,0,'NONE','not compressed'))
        import sys
        if sys.byteorder!='little':samples.byteswap()
        wav.writeframes(samples.tobytes())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix',nargs='?')
    ap.add_argument('--artifacts',type=Path,default=h.ROOT/'out')
    ap.add_argument('--out',type=Path,default=h.ROOT/'out/harmony-size-musical')
    ap.add_argument('--record-only',action='store_true')
    ap.add_argument('--examples-only',action='store_true')
    ap.add_argument('--audio',action='store_true')
    args=ap.parse_args();m=MusicalMachine(args.artifacts)
    cases=[];issues=[];checks=0
    def check(ok,criterion,case,row=None):
        nonlocal checks
        checks+=1
        if not ok:issues.append(dict(criterion=criterion,case=case,row=row))
    def progression(name,size,root,sequence,voic=1,scale=0):
        m.configure(size,root,voic,scale=scale)
        rows=[m.sound(*pair) for pair in sequence]
        cases.append(dict(name=name,size=size,root_mode=root,voic=voic,rows=rows))
        return rows
    rows=progression('Low C to Cmaj7',2,0,[(48,0),(48,1)])
    for row in rows:check(clear_spacing(row['notes']),'low-register clarity',cases[-1]['name'],row)
    rows=progression('Dropped-root triad to seventh',4,2,[(60,0),(60,1),(65,0),(60,0)])
    check(rows[0]['notes']==[48,60,64,67],'double the actual bass/root',cases[-1]['name'],rows[0])
    check(rows[1]['notes']==[48,59,64,67],'triad to seventh moves only the doubled root by a semitone',cases[-1]['name'],rows[1])
    progression('ii-V-I with bass',3,2,[(62,1),(67,1),(60,1)])
    progression('ii-V-I rootless',2,1,[(62,1),(67,1),(60,1)])
    rows=progression('Minor ii-half-diminished-V7-i7',3,2,[(62,1),(67,7),(60,1)],scale=5)
    check([r['notes'] for r in rows]==[[50,68,72],[55,65,71],[48,63,70]],
          'retain the altered fifth and chromatic upper line in minor',cases[-1]['name'],rows)
    rows=progression('Rootless ADD9',3,1,[(60,2),(65,2),(67,2),(60,2)])
    for row in rows:check(row['notes'][0]%12!=row['raw'][3]%12,'ninth stays out of the automatic bass',cases[-1]['name'],row)
    rows=progression('Low four-voice triads',4,0,[(36,0),(41,0),(43,0),(36,0)])
    for row in rows:check(clear_spacing(row['notes']),'low-register clarity',cases[-1]['name'],row)
    # The source's third/seventh pattern, in every key, with/without a bass.
    for key in range(12):
        for size,root_mode in ((3,2),(2,1)):
            m.configure(size,root_mode,key=key)
            rows=[m.sound(p+key,1) for p in (62,67,60)]
            upper=[r['notes'][1:] if root_mode==2 else r['notes'] for r in rows]
            for row,voices in zip(rows,upper):
                check({p%12 for p in voices}=={row['raw'][1]%12,row['raw'][3]%12},
                      'retain third and seventh',f'ii-V-I key {key}',row)
            check(all(abs(a-b)<=2 for before,after in zip(upper,upper[1:])
                      for a,b in zip(before,after)),'smooth independent guide-tone lines',f'ii-V-I key {key}',rows)
    # Explicit inversions retain the player's choice and double their bass.
    for inv,want in ((0,[60,64,67,72]),(2,[64,67,72,76]),(3,[67,72,76,79])):
        m.configure(4,voic=inv);row=m.sound(60,0)
        check(row['notes']==want,'literal inversion and bass doubling',f'inversion {inv}',row)
    matrix=0
    if not args.examples_only:
        for key in range(12):
            for size in (2,3,4):
                for root_mode in range(4):
                    for spread in range(3):
                        m.configure(size,root_mode,spread=spread,key=key)
                        for pitch in (36,48,60,72):
                            for quality in range(8):
                                row=m.sound(pitch+key,quality);notes=row['notes'];matrix+=1
                                name=f'key={key} size={size} root={root_mode} spread={spread}'
                                check(len(notes)==len(set(notes))==size,'requested distinct voices',name,row)
                                check(clear_spacing(notes),'low-register clarity',name,row)
                                if quality==2:
                                    check(notes[0]%12!=row['raw'][3]%12,'ninth stays out of the automatic bass',name,row)
    args.out.mkdir(parents=True,exist_ok=True)
    report=dict(guide=GUIDE,policy='AUTO minimum adjacent gaps: below MIDI 48, 7 semitones above the bass and 5 for inner voices; below MIDI 60, 3 semitones; manual inversions remain literal',
                image_sha256=hashlib.sha256((args.artifacts/'mainos_bus.bin').read_bytes()).hexdigest(),
                cases=cases,checks=checks,matrix_voicings=matrix,issue_count=len(issues),issues=issues[:40],
                deliberate_tradeoffs=['Two total voices with ROOT KEEP cannot retain root, third and seventh together; ROOT OMIT assumes a separate bass.',
                                      'Altered-fifth three-note reductions preserve the alteration and seventh at the expense of the third.',
                                      'Manual inversions remain literal; WIDE may separate upper voices more than the guide normally recommends.'],
                evidence='Executed linked ColdFire; audio is a neutral offline rendition of captured pitches',hardware_tested=False)
    (args.out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.audio:audition(cases,args.out)
    for case in cases:print(case['name'],[r['notes'] for r in case['rows']],flush=True)
    print(f'Musical audit: {checks} checks, {matrix} matrix voicings, {len(issues)} issues',flush=True)
    if not args.record_only:assert not issues,issues[:4]


if __name__=='__main__':main()
