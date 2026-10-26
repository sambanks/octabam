#!/usr/bin/env python3
"""Eight-track Follow graph churn, long chains, cycle and corrupt-state guards."""
import argparse
import hashlib
import itertools
import json
import random
from midi_machine import Machine, ROOT
from unicorn.m68k_const import *


def source(graph, track):
    seen = {track}
    node = track
    while graph[node]:
        node = graph[node]-1
        if node not in range(8) or node in seen:
            return None
        seen.add(node)
    return node


def machine(seed=20261008, steps=12000):
    m = Machine()
    u, s = m.uc, m.sym
    rng = random.Random(seed)
    lane = m.scratch+0x1000
    frame = m.scratch+0x3000
    graphs = [list(range(2,9))+[0], [0]+list(range(1,8))]
    # Every possible order of the longest acyclic chain: all track positions.
    count = 0
    for order in itertools.permutations(range(8)):
        graph = [0]*8
        for a,b in zip(order,order[1:]):
            graph[a] = b+1
        m.follow_write('source',bytes(graph),0)
        # Closing the eight-node chain must never be accepted by the selector.
        m.call('bf_select',order[-1],8)
        changed = list(m.follow_read('source',8,0))
        assert changed == graph, (seed,order,changed)
        count += 1
    graph = [0]*8
    m.follow_write('source',bytes(graph),0)
    for i in range(steps):
        t,delta = rng.randrange(8),rng.choice((-2147483648,-8,-1,0,1,8,2147483647))
        before = list(m.follow_read('source',8,0))
        m.call('bf_select',t,delta & 0xffffffff)
        graph = list(m.follow_read('source',8,0))
        assert all(source(graph,j) is not None for j in range(8)),(seed,i,graph)
        assert all(graph[j]==before[j] for j in range(8) if j!=t),(seed,i,graph)
        if i%8==0:
            graphs.append(graph)
    # Runtime must remain bounded even when volatile state is invalid.
    graphs += [[2,3,4,5,6,7,8,1],list(range(1,9)),[255]*8]
    graphs += [[rng.choice(tuple(range(9))+(9,127,255)) for _ in range(8)] for _ in range(2000)]
    outputs = 0
    for graph in graphs:
        roots = [rng.randrange(128) for _ in range(8)]
        roots[rng.randrange(8)] = 255
        m.follow_write('source',bytes(graph),0)
        u.mem_write(s['bf_pitches'],bytes(roots))
        u.mem_write(s['bf_roots'],bytes(36+n%12 if n<128 else 255 for n in roots))
        u.mem_write(s['bf_intervals'],bytes((0x80,))*24)
        modes = [rng.choice((0,2)) for _ in range(8)]
        fixed = [rng.randrange(11) for _ in range(8)]
        offsets = [rng.randrange(-2,3) for _ in range(8)]
        for name,values in [('mode',modes),('fixed',fixed),('offset',offsets)]:
            m.follow_write(name,bytes(v&255 for v in values))
        for t in range(8):
            ultimate = source(graph,t)
            if 'mh_source' in s:
                assert m.call('mh_source',t)==(t if ultimate is None else ultimate),(graph,t)
            for slot in (0,3):
                tran = rng.randrange(-64,64)
                original = rng.choice((0,60,127,255))
                expected = original
                if graph[t] and ultimate is not None and roots[ultimate]<128 and original<128:
                    root = roots[ultimate]
                    pitch = (root+12*offsets[t] if modes[t] else root%12+12*fixed[t])+tran
                    expected = pitch if slot==0 and 0<=pitch<128 else 255
                u.mem_write(m.scratch,bytes((original,)))
                u.mem_write(frame-4,bytes((original,))*4)
                u.mem_write(lane+0x22c,bytes((64+tran,)))
                m.call('bf_note',stop=0x4009fb86 if expected<128 else 0x4009fd2a,
                       regs={UC_M68K_REG_D7:t,UC_M68K_REG_D4:slot,
                             UC_M68K_REG_A2:m.scratch,UC_M68K_REG_A5:lane,
                             UC_M68K_REG_A6:frame})
                assert u.mem_read(m.scratch,1)[0]==expected,(seed,graph,t,slot,original,tran,expected)
                assert all(m.stack-192<=a and a+n<=m.stack+4 or a==m.scratch and n==1 or a==s['bf_scale_offsets']+t*4+slot and n==1 for a,n in m.writes),m.writes
                outputs += 1
        assert list(m.follow_read('source',8,0))==graph
    print(f'[ok] {count} full-chain permutations, {steps} live graph edits, {outputs} routed outputs; bounded cycles, register/TRAN and write guards',flush=True)
    return dict(seed=seed,chain_permutations=count,edits=steps,outputs=outputs)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix',nargs='?')
    ap.add_argument('--seed',type=int,default=20261008)
    args=ap.parse_args()
    out=ROOT/'out/follow-stress';out.mkdir(parents=True,exist_ok=True)
    receipt=out/'result.json';receipt.unlink(missing_ok=True)
    result=machine(args.seed)
    result.update(status='pass',image_sha256=hashlib.sha256((ROOT/'out/mainos_bus.bin').read_bytes()).hexdigest(),scope='linked ColdFire; no UART timing or hardware proof')
    receipt.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
