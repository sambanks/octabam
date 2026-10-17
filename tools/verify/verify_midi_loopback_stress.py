#!/usr/bin/env python3
"""Eight-producer floods with a stalled consumer, full native queue and recovery.

Executes linked module and stock queue code. No physical UART timing claim.
"""
import argparse
from collections import Counter
import hashlib
import json
import random
import verify_midi_loopback as lb


def machine(seed=20261008, rounds=48):
    rng=random.Random(seed)
    m=lb.Machine()
    active=Counter()
    delivered=0
    def consume():
        nonlocal delivered
        msg=m.next()
        delivered+=1
        status,n,v=msg
        if status&0xf0 in (0x80,0x90):
            key=(status&15,n)
            if status&0xf0==0x90 and v:
                assert active[key]==0,('duplicate internal on',key)
                active[key]+=1
            else:
                assert active[key]==1,('unmatched internal off',key)
                active[key]-=1
        return msg
    for t in range(8):m.put(m.sym['lb_routes']+t,1,1)
    for cycle in range(rounds):
        keys=[(t,16*t+n) for t in range(8) for n in range(16)]
        rng.shuffle(keys)
        # Hold 128 distinct voices while fully draining their note-ons.
        for t,n in keys:
            m.capture((0x90|t,n,100),track=t)
            assert consume()==bytes((0x90|t,n,100))
        assert m.get('lb_internal_held')==128
        assert lb.owned_counts(m)==[16]*8
        # Stalled consumer: admit 127 CCs; shed all further non-release work.
        expected=[]
        drops=m.get('lb_dropped')
        for i in range(1024):
            t=i%8;msg=bytes((0xb0|t,34,i%128))
            m.capture(msg,0x4009fef2,track=t)
            if i<127:expected.append(msg)
        assert m.get('lb_dropped')-drops==897
        # A rejected new note must not later manufacture an internal off.
        m.capture((0x9f,127,100),track=7)
        m.capture((0x8f,127,0),0x4009f8c2,track=7)
        assert m.get('lb_internal_held')==128
        if cycle%2:
            # Simultaneous route changes reserve every outstanding release.
            tracks=list(range(8));rng.shuffle(tracks)
            for t in tracks:
                m.call('lb_set_route',(t,0))
                expected.extend(bytes((0x80|t,n,0)) for n in sorted(n for tt,n in keys if tt==t))
            # Late stock releases are tombstoned and must be silent.
            before=m.get('lb_accepted')
            for t,n in keys:assert m.capture((0x80|t,n,0),0x4009f8c2,track=t)==0
            assert m.get('lb_accepted')==before
        else:
            rng.shuffle(keys)
            for t,n in keys:
                msg=bytes((0x80|t,n,0))
                m.capture(msg,0x4009f8c2,track=t);expected.append(msg)
        assert m.get('lb_internal_held')==0
        assert lb.owned_counts(m)==[0]*8
        assert (m.get('lb_head')-m.get('lb_tail'))%256==255
        assert m.get('lb_highwater')==255
        assert [consume() for _ in expected]==expected,(seed,cycle)
        assert not any(active.values())
        assert m.get('lb_head')==m.get('lb_tail')
        for t in range(8):m.call('lb_set_route',(t,1))
    assert m.get('lb_accepted')==m.get('lb_delivered')==delivered
    # Native receive queue saturation and alternating service. Independent
    # stable message storage is essential: a queue contains pointers.
    m=lb.Machine();m.put('lb_routes',1,1)
    native=[]
    for i in range(256):
        msg=bytes((0xb8,35,i%128));ptr=0x47006000+4*i
        m.u.mem_write(ptr,msg);m.call(0x40000c3c,(lb.Q,ptr));native.append(msg)
    for i in range(127):m.capture((0xb0,34,i),0x4009fef2)
    assert m.get(lb.Q+4)==256 and m.get('lb_wake_pending',1)==0
    for i in range(127):
        assert m.next()==bytes((0xb0,34,i))
        assert m.next()==native[i]
    assert [m.next() for _ in range(129)]==native[127:]
    assert m.get(lb.Q+4)==0
    m.capture((0xb0,34,99),0x4009fef2)
    assert m.next()==bytes((0xb0,34,99))
    print(f'[ok] seed {seed}: {rounds} eight-track floods, {delivered} delivered messages, 255-slot release reserve, full native queue fairness and recovery',flush=True)
    return dict(seed=seed,rounds=rounds,delivered=delivered,non_release_attempts=rounds*1024,highwater=255)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('remix',nargs='?')
    ap.add_argument('--seed',type=int,default=20261008);args=ap.parse_args()
    out=lb.ROOT/'out/loopback-stress';out.mkdir(parents=True,exist_ok=True)
    receipt=out/'result.json';receipt.unlink(missing_ok=True)
    result=machine(args.seed)
    result.update(status='pass',image_sha256=hashlib.sha256((lb.ROOT/'out/mainos_bus.bin').read_bytes()).hexdigest(),scope='linked module and stock queue; no hardware timing')
    receipt.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
