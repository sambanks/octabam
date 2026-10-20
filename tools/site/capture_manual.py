#!/usr/bin/env python3
"""Capture manual screens through the emulator's actual panel UART.

Uses the existing MenuPort/PanelLink capture tooling. Builds are isolated
in this worktree; project changes are confined to out/manual-captures/.
    python3 tools/site/capture_manual.py core features inserts bus extras
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath  # noqa: E402,F401
from stems_panel import MenuPort  # noqa: E402
from panel_server import setup_window_open, popup_geometry  # noqa: E402
import ot_project as otp  # noqa: E402
from remix import registry  # noqa: E402

OUT=ROOT/'out/manual-captures'
IMG=ROOT/'docs/site/img'
RECORDS=ROOT/'docs/site/screenshots.json'


def shot(p, module, name, caption, remix):
    path=IMG/module/(name+'.png')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(p.link.render_png(scale=4,dark=0,light=255))
    records=json.loads(RECORDS.read_text()) if RECORDS.exists() else {}
    records.setdefault(module,{})[name]={'image':f'{module}/{name}.png','caption':caption,
        'remix':remix,'source':'emulator panel UART',
        'firmware_sha256':hashlib.sha256((OUT/remix/'image.bin').read_bytes()).hexdigest()}
    RECORDS.write_text(json.dumps(records,indent=2)+'\n')
    print(f'Captured {module}/{name}: {caption}',flush=True)


def press(p, name, n=1):
    for _ in range(n): p.press(name,settle=80)


def enc(p,n,delta):
    while delta:
        step=max(-7,min(7,delta))
        p.proc.command(f'knob {0x30+n:#x} {step}', 'ok')
        p.run(60)
        delta-=step


def menu(p,section,row):
    if popup_geometry(p.rt.uc) != (5, 0, 0xf6, 0x40):
        p.open_menu()
    press(p,'left')  # MAIN MENU retains its previous submenu focus.
    press(p,'up',5)
    press(p,'down',section)
    press(p,'right')
    press(p,'up',15)
    press(p,'down',row)
    press(p,'yes')


def close(p):
    press(p,'no')


def capture_core(p,r):
    # Concrete status messages and pages, beyond effects and BRAIN.
    p.chord('t1','no')
    shot(p,'rec-trig-mute','muted','Recorder trigs muted on track 1.',r)
    p.chord('t1','yes')
    p.chord('rec','play')
    shot(p,'quantize-live-rec-toggle','status','Quantize live recording status shown by REC + PLAY.',r)
    # Redraw the base screen to dismiss transient overlays.
    press(p,'mixer',2)
    menu(p,1,3)
    shot(p,'mute-modes','personalize','MUTE MODE in the PERSONALIZE settings.',r)
    close(p)
    menu(p,2,2)
    press(p,'down',5)
    shot(p,'quantizer','settings','SCALE, ROOT, and GLIDE in sequencer settings.',r)
    close(p)
    # Recorder length extension (RLEN is encoder C).
    p.chord('func','recab')
    enc(p,2,127)
    close(p)
    p.chord('func','recab')
    shot(p,'rlen-plen','setup','RLEN set to PLEN in RECORDING SETUP 1.',r)
    close(p)
    press(p,'midi');press(p,'pg_playback')
    p.key('scene_a',True);p.run(200)
    shot(p,'midi-scenes','lock','MIDI track NOTE page while scene A is held.',r)
    p.key('scene_a',False);p.run(100)
    press(p,'midi')
    press(p,'pg_fx2')
    if not setup_window_open(p.rt.uc):
        p.chord('func','pg_fx2')
    p.key('scene_a',True);p.run(200)
    shot(p,'scenes-p2','lock','FX2 setup page with scene A held.',r)
    p.key('scene_a',False);p.run(100)
    close(p)
    press(p,'rec');p.key('trig1',True);p.run(100)
    press(p,'pg_fx2')
    if not setup_window_open(p.rt.uc):
        p.chord('func','pg_fx2')
    shot(p,'plocks-p2','lock','FX2 setup page with trig 1 held for parameter locking.',r)
    p.key('trig1',False);p.run(100)
    close(p);press(p,'rec')
    p.key('pattern',True);p.run(100);press(p,'yes')
    shot(p,'direct-jump-kyoti','status','DIRECT JUMP toggled with PTN + YES.',r)
    p.key('pattern',False);p.run(100)
    p.chord('pattern','t1')
    shot(p,'reload-from-project','status','Track 1 sequence reload from the saved project.',r)


def capture_plocks(p,r):
    """PLATE REV slot A: a held lock and the normal Part value on release."""
    press(p,'t1');p.press('pg_fx2',hold=180,settle=180)
    if not setup_window_open(p.rt.uc):
        p.press('pg_fx2',hold=30,settle=30)
        p.press('pg_fx2',hold=180,settle=180)
    assert setup_window_open(p.rt.uc), 'PLOCKS capture did not reach FX2 SETUP'
    # Establish a visible Part value through the encoder, regardless of defaults.
    enc(p,0,-127);enc(p,0,20)
    press(p,'rec');press(p,'trig1')
    p.key('trig1',True);p.run(180);enc(p,0,30)
    shot(p,'plocks-p2','lock','Trig 1 held: GVOL is locked to 50 with the value area highlighted.',r)
    p.key('trig1',False);p.run(350)
    shot(p,'plocks-p2','released','Trig released: GVOL shows the Part value 20; the step keeps its lock.',r)


def capture_features(p,r):
    p.chord('t1','page')
    shot(p,'euclid-fill','fill','Euclidean trig fill: STEPS, PULSE, ROT, RAND VEL, RAND PTCH.',r)
    close(p)
    p.chord('func','recab');enc(p,3,12);close(p)
    p.chord('func','recab')
    shot(p,'rec-threshold','trigger','TRIG set to THR in RECORDING SETUP 1.',r)
    close(p);p.chord('func','reccd')
    shot(p,'rec-threshold','level','Threshold LEV and live IN meter in RECORDING SETUP 2.',r)
    close(p)
    p.chord('up','rec')
    shot(p,'stems','recorder','The STEM REC recording window.',r)
    close(p)
    # Existing name-editor gate's measured path through PROJECT > CHANGE.
    p.open_menu();press(p,'left');press(p,'up',5);press(p,'yes',2);p.run(3000);press(p,'up');press(p,'yes');p.run(3000)
    p.chord('func','cue')
    shot(p,'rnd-name','name','Random project name after FUNC + CUE.',r)


def capture_buffer_saver(p,r):
    # TRIG to HOLD in RECORDING SETUP 1 (two steps of encoder D), a one-second
    # take on track 1 (TRACK 1 + REC AB held), then FUNC + PROJ: the module asks
    # before stock's SAVE runs.
    p.chord('func','recab');enc(p,3,8);close(p)
    p.key('t1',True);p.run(60);p.key('recab',True);p.run(1000)
    p.key('recab',False);p.run(60);p.key('t1',False);p.run(3000)
    p.chord('func','proj');p.run(3000)
    shot(p,'buffer-saver','ask','After a take, SAVE PROJECT asks SAVE SAMPLES? first.',r)
    close(p)


def capture_fx(p,r,assignments):
    for track,slot,key in assignments:
        m=registry.modules()[key]
        press(p,f't{track}')
        press(p,'pg_'+slot)
        p.chord('func','pg_'+slot)
        shot(p,m.name,'setup',f'{key}: effect selection and setup parameters.',r)
        close(p)
        shot(p,m.name,'main',f'{key}: main parameter page.',r)


def capture_bus(p,r):
    capture_fx(p,r,[(2,'fx2','SEND')])
    # The servers draw DEL and REV on their host track's FX2 page; the rest is in the TEMPO window,
    # a scrolling list per box: the top rows, then the bottom rows.
    for track,key,box,last in ((1,'DELAY SERVER','DELAY',5),(5,'REVERB SERVER','REVERB',9)):
        m=registry.modules()[key]
        press(p,f't{track}');press(p,'pg_fx2')
        shot(p,m.name,'fx2',f'{key} on track {track}: the FX2 page (DEL and REV).',r)
        press(p,'tempo')
        if box=='REVERB':press(p,'right')
        shot(p,m.name,'main',f'{key}: the {box} box in the TEMPO window, first rows.',r)
        press(p,'down',last)
        shot(p,m.name,'tempo-bottom',f'{key}: the {box} box in the TEMPO window, last rows.',r)
        close(p)
    press(p,'t1');p.chord('func','pg_fx2')
    shot(p,'fx2-lock','chooser','Locked FX2 selection on the delay host.',r)
    close(p)
    press(p,'tempo')
    shot(p,'tempo-bus','tempo','Delay and reverb controls in the TEMPO window.',r)
    close(p)
    p.open_menu();press(p,'up',5);press(p,'down',4);press(p,'right');press(p,'down',3);press(p,'yes')
    shot(p,'load-meter','load','BRAIN performance: load display.',r)
    press(p,'right',2)
    shot(p,'load-meter','dsp','BRAIN performance: DSP display.',r)
    press(p,'right')
    shot(p,'memory','memory','BRAIN performance: sample and recorder memory.',r)
    press(p,'right',3)
    shot(p,'usb','performance','BRAIN performance: USB counters.',r)


def capture_usb(p,r):
    # PROJ > BRAIN > SETTINGS; the list is BRAIN, APPLY DEFAULTS, then the USB group
    # (CUE, IN, MAIN, MASTER, MIDI, TRACKS). YES changes the selected value.
    p.open_menu();press(p,'up',5);press(p,'down',4);press(p,'right');press(p,'down',2);press(p,'yes')
    press(p,'down',3)
    shot(p,'usb','settings','BRAIN > SETTINGS, the USB group: CUE, IN and MAIN. A value that ends in * takes effect at the next boot.',r)
    press(p,'down',7)
    shot(p,'usb','settings-end','The end of the USB group: TRACKS, with * AT NEXT BOOT under the list.',r)


def capture_analog(p,r):
    press(p,'t1')
    p.chord('func','pg_playback')
    press(p,'down',6)
    press(p,'yes')
    close(p)
    press(p,'pg_playback')
    shot(p,'analog-bassdrum','source','Analog BD source controls.',r)
    p.chord('func','pg_playback')
    shot(p,'analog-bassdrum','setup','Analog BD source setup.',r)


def capture_blackpyramids(p,r):
    # BLKPYRAMD is the sixth row of the machine list (STATIC + 5).
    press(p,'t1')
    p.chord('func','pg_playback')
    press(p,'down',5)
    press(p,'yes')
    close(p)
    press(p,'pg_playback')
    shot(p,'blackpyramids-303','source','BLKPYRAMD source controls: PTCH, CUT, RES, ENV, DEC, ACC.',r)
    p.chord('func','pg_playback')
    shot(p,'blackpyramids-303','setup','SRC SETUP with BLKPYRAMD: WAVE, TUNE, SLID, GATE, VOL.',r)


def capture_synth(p,r):
    press(p,'t1');press(p,'pg_playback')
    shot(p,'synth','source','FM synth source page on a FLEX track assigned FMSYNTH.WAV.',r)
    press(p,'pg_lfo')
    shot(p,'synth','voices','Synth voice and chord controls on the LFO page.',r)
    menu(p,2,2)
    enc(p,6,-127)
    while p.peek(0x8000004e,1) != b'\x01':
        current=p.peek(0x8000004e,1)[0]
        enc(p,6,-1 if current > 1 else 1)
    shot(p,'direct-jump','settings','CHAIN AFTER set to DIRECT in sequencer settings.',r)


def capture_varispeed(p,r):
    # Track 1 to FLEX (the machine list on SRC SETUP), TSTR to VARI: a 5-position
    # select, so a long turn of encoder E lands on the last position.
    press(p,'t1')
    p.chord('func','pg_playback')
    press(p,'down')
    press(p,'yes')
    enc(p,4,40)
    shot(p,'varispeed','setup','SRC SETUP on a FLEX track: TSTR set to VARI.',r)
    close(p)
    press(p,'pg_playback')
    enc(p,0,3)  # one detent a ratio: 1/1 -> 5/4 -> 4/3 -> 3/2
    shot(p,'varispeed','quan','The SRC page of a VARI track: PTCH is QUAN, here 3/2.',r)


def press_encoder(p, n):
    # Encoder push switches are panel matrix row 0x27, A-F = bits 0-5.
    p.proc.command(f'key 0x27 {1 << n:#x}', 'ok');p.run(40)
    p.proc.command('key 0x27 0', 'ok');p.run(80)


def capture_midi_loopback(p,r):
    # Sample-free fixture starts in audio mode, with MIDI channel 1, DEST EXT.
    press(p,'midi');press(p,'t1');p.chord('func','pg_playback')
    shot(p,'midi-loopback','channel-ext','MIDI NOTE SETUP: CHAN 1 uses external output.',r)
    press_encoder(p,0)
    shot(p,'midi-loopback','routing-ext','ROUTING: EXT sends to external MIDI.',r)
    enc(p,0,4)
    shot(p,'midi-loopback','routing-int','ROUTING: INT sends to the internal MIDI receiver.',r)
    press_encoder(p,0)
    shot(p,'midi-loopback','channel-int','MIDI NOTE SETUP: CHAN 1I indicates internal routing.',r)
    press_encoder(p,0);enc(p,0,4)
    shot(p,'midi-loopback','routing-both','ROUTING: BOTH sends internally and externally.',r)
    press_encoder(p,0)
    shot(p,'midi-loopback','channel-both','MIDI NOTE SETUP: CHAN 1B indicates both destinations.',r)


def capture_midi_scales(p,r):
    # Sample-free fixture starts in audio mode with MIDI KEY OFF.
    press(p,'midi');press(p,'t1');p.chord('func','pg_amp')
    shot(p,'midi-scales','key-off','MIDI ARP SETUP: KEY OFF bypasses scale correction.',r)
    press_encoder(p,5)
    enc(p,5,4)
    shot(p,'midi-scales','c-major','MIDI ARP SETUP: C Major selected with encoder F.',r)
    enc(p,5,4)
    shot(p,'midi-scales','c-dorian','MIDI ARP SETUP: C Dorian selected with encoder F.',r)
    for _ in range(3): enc(p,5,4)
    shot(p,'midi-scales','c-mixolydian','MIDI ARP SETUP: C Mixolydian selected with encoder F.',r)


def capture_midi_follow(p,r):
    press(p,'midi');press(p,'t2');p.chord('func','pg_playback')
    shot(p,'midi-follow','source-off','MIDI NOTE SETUP: RFOL OFF uses native notes.',r)
    enc(p,3,4)
    shot(p,'midi-follow','source-t1','MIDI NOTE SETUP: RFOL T1 follows MIDI track 1.',r)
    press_encoder(p,3)
    shot(p,'midi-follow','fixed','FOLLOW: FIXED octave 3 and TRIG update.',r)


def prepare(remix,project,assignments):
    label='manual-features' if remix.startswith('../') else remix
    work=OUT/label;work.mkdir(parents=True,exist_ok=True)
    print('Building '+remix,flush=True)
    env=dict(os.environ,REMIX=remix,XBUS='1',SPEC='1',BUILD='91')
    with (work/'build.log').open('w') as f:
        subprocess.run([sys.executable,'tools/build/build_bus.py'],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    shutil.copy2(ROOT/'out/mainos_bus.bin',work/'image.bin')
    fixture=work/'project'
    shutil.copytree(project,fixture,dirs_exist_ok=True)
    if remix=='octabam-core':
        values=otp.module_defaults(registry.modules()['DELAY'])
        otp.set_fx(fixture,'fx2',1,'DELAY',page=values[:6],page2=values[6:],guard=False)
    if remix=='octabam-bus':
        otp.host_rig(fixture,remix,guard=False)
    for track,slot,key in assignments:
        m=registry.modules()[key]
        values=otp.module_defaults(m)
        otp.set_fx(fixture,slot,track,key,page=values[:6],page2=values[6:],guard=False)
    audio=[]
    if remix=='octatrick':
        import re,wave
        marker=fixture/'FMSYNTH.WAV'
        with wave.open(str(marker),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100)
            wav.writeframes(bytes(44100*4*2))
        for pw in (fixture/'project.work',fixture/'project.strd'):
            if not pw.exists():continue
            raw=pw.read_bytes()
            raw=re.sub(rb'\[SAMPLE\]\r\nTYPE=FLEX\r\nSLOT=001\r\n.*?\[/SAMPLE\]\r\n\r\n',b'',raw,flags=re.S)
            block=b'[SAMPLE]\r\nTYPE=FLEX\r\nSLOT=001\r\nPATH=FMSYNTH.WAV\r\nTRIM_BARSx100=100\r\nLOOP_BARSx100=100\r\nBPMx24=2880\r\nTSMODE=0\r\nLOOPMODE=0\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n'
            at=raw.index(b'[SAMPLE]');pw.write_bytes(raw[:at]+block+raw[at:])
        for bank in fixture.glob('bank*.work'):
            def mut(data):
                for i in range(otp.NPARTS_ALL):
                    base=otp.PART_BASE+i*otp.PART_STRIDE
                    data[base+otp.MTYPE_OFF]=1
                    data[base+0x2d3+otp.SLOT_KIND['flex']]=0
            otp._bank_write(fixture,int(bank.stem[4:]),mut,guard=False)
        audio=['--audio',str(marker)+':FMSYNTH.WAV']
    # A saved bank is needed for the reload gesture demonstration.
    for bank in fixture.glob('bank*.work'):
        shutil.copy2(bank,bank.with_suffix('.strd'))
    with (work/'stage.log').open('w') as f:
        subprocess.run([str(ROOT/'.venv/bin/python3'),'tools/emu/ot_emu/stage_card.py',str(fixture),'MANUAL','SCREENS','--tree',str(work/'tree'),'--out',str(work/'card.img'),*audio],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
    return work


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('groups',nargs='+',choices=['core','plocks','features','inserts','bus','extras','machines','probes','midi-scales','midi-loopback','midi-follow','utilities','varispeed','usb'])
    cfg=Path.home()/'.octabam_project'
    ap.add_argument('--project',default=os.environ.get('OT_PROJECT') or (cfg.read_text().strip() if cfg.is_file() else ''))
    a=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    for group in a.groups:
        assignments=[]
        if group=='core': jobs=[('octabam-core',capture_core,[])]
        elif group=='midi-loopback':jobs=[('midi-loopback',capture_midi_loopback,[])]
        elif group=='midi-follow':jobs=[('midi-follow',capture_midi_follow,[])]
        elif group=='plocks': jobs=[('octabam-core',capture_plocks,[(1,'fx2','PLATE REV')])]
        elif group=='midi-scales':jobs=[('midi-scales',capture_midi_scales,[])]
        elif group=='features':
            # A scratch selection: THR and REC_TRIG_MUTE share a hook and cannot coexist.
            scratch=OUT/'features.py'
            scratch.write_text('import dataclasses,runpy\nbase=runpy.run_path("remixes/octabam-core/remix.py")["REMIX"]\nREMIX=dataclasses.replace(base,name="manual-features",modules=tuple(k for k in base.modules if k!="REC_TRIG_MUTE")+("REC THRESHOLD","EUCLID FILL","RND NAME","STEM REC"))\n')
            jobs=[('../out/manual-captures/features',capture_features,[])]
        elif group=='inserts':
            assignments=[(i+1,'fx1' if i<5 else 'fx2',key) for i,key in enumerate(('SPECTRUM','CHARACTER','MODULATION','TRANSIENT','EUCLID','LOFI2','GATE VERB','DELAY'))]
            jobs=[('octabam-inserts',capture_fx,assignments)]
        elif group=='bus':jobs=[('octabam-bus',capture_bus,[])]
        elif group=='usb':jobs=[('octabam-bus',capture_usb,[])]
        elif group=='machines':jobs=[('analog-bassdrum',capture_analog,[]),('octatrick',capture_synth,[]),('blackpyramids-303',capture_blackpyramids,[])]
        elif group=='probes':jobs=[('cfmeter',capture_fx,[(8,'fx2','CF METER')])]
        elif group=='utilities':jobs=[('buffer-saver',capture_buffer_saver,[])]
        elif group=='varispeed':jobs=[('varispeed',capture_varispeed,[])]
        else:
            jobs=[(r,capture_fx,[(2,'fx1' if r in ('character-txtr','testgen') else 'fx2',k)]) for r,k in [('character-txtr','CHARACTER TXTR'),('testgen','TESTGEN'),('sidechain-compressor','SIDECHAIN_COMPRESSOR'),('miniverb','MINIVERB'),('bbd','BBD'),('tapeecho','TAPE ECHO'),('vocoder','VOCODER'),('wave','WAVE')]]
        for remix,fn,assignments in jobs:
            # Paths use a separate stable label even when registry selects a scratch file.
            label='manual-features' if remix.startswith('../') else remix
            work=prepare(remix,Path(a.project),assignments)
            print('Booting '+label,flush=True)
            with MenuPort((work/'image.bin').resolve(),(work/'card.img').resolve(),'MANUAL','SCREENS',True,log_path=work/'port.log') as p:
                p.settle()
                if fn==capture_fx: fn(p,label,assignments)
                else: fn(p,label)


if __name__=='__main__':main()
