"""Route A at AUDIO level (8 Sep 2026, after Bryan's seamtest flash falsified
the length-seam model, RTOS_FORK 10.18).

Every seam number before this came from POSITIONS (arm sample, length, end
post); the read-back block the recorder writes from was zeros, so no run ever
showed what the buffer holds or what the flex plays across an arm. This
driver injects a known signal into the read-back block -- the DSP's
per-track recorder input, 0x80003190 + ping*0x400, 8 tracks x 16 samples x
L/R, one 32-bit left-justified sample per long (DSP.md 6c, COLDFIRE_PORT
frame protocol) -- at the moment the paced eDMA chain (ch1 -> 6 -> 7) that
carries it completes, i.e. when "the DSP delivered this frame". That is a
live instrument at the inputs, which is what Bryan plays.

    L = (n & 0x7fff) << 16          n = 16 * frame + i, a sample counter (kept positive)
    R = ((track << 4) | i) << 16    a layout probe: which track/slot the
                                    recorder actually took

and captures, per frame, the 1024-byte audio block the host DMAs to each
DSP core (the flex playback the ColdFire computed), plus the arm/end events,
and at the end the recorder buffer's pool blocks (row track+2 of the block
table at 0x46c2e9c0, 6144-byte blocks at blk*6144 + 0x40A955E0). Analysis
is offline: recaudio_analyse.py.

    .venv/bin/python tools/scratch/recaudio.py --project out/_fx/r4_128 \
        --tree out/_ra_r4_128 --frames 12600 --out out/_ra_r4_128.pkl
"""
import argparse, sys, os, struct, json, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import emu_rtos as er, emu_card as ec, emu_bringup as eb
from unicorn.m68k_const import *
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE

POOL_ROWS = 0x46c2e9c0          # ten rows of 14,602 halfword block numbers (EXTERNAL.md 6, Bryan 12-14)
POOL_ROW_N = 14602
POOL_BASE = 0x40A955E0
POOL_BLOCK = 6144
REC_STATE = 0x80004f1c          # 16 x 84-byte recorder state records, two banks of 8 (RTOS_FORK 10.13)
REC_24BIT = 0x80000053

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--tree", required=True)
ap.add_argument("--name", default="RECT"); ap.add_argument("--frames", type=int, default=12600)
ap.add_argument("--image", default=None); ap.add_argument("--track", type=int, default=0)
ap.add_argument("--out", required=True)
ap.add_argument("--inject", default="counter", choices=("counter", "none", "burst"))
ap.add_argument("--burst-frames", type=int, default=5200, help="burst mode: inject the ramp for this many frames from the start, then silence")
ap.add_argument("--flex-probe", action="store_true", help="watch the FLEX voice bind 0x4000f450 / caller 0x4000d49e")
ap.add_argument("--blocks", type=int, default=40, help="pool blocks to dump from the row")
ap.add_argument("--field-probe", action="store_true", help="log every write to the track's recorder state record (+36..+83, both banks) with its PC")
ap.add_argument("--reg-probe", action="store_true", help="log the mix loops' source pointers and gains at loop entry (frames 323..326)")
ap.add_argument("--read-probe", action="store_true", help="log the write path's source reads (0x40007680..0x40007748) for the first recording frames")
a = ap.parse_args()

card, name = er.stage_project(a.project, "OCTABAM", a.name, tree=a.tree)
r, rt = er.attach(a.image, card)
uc = rt.uc

def rd(u, reg): return u.reg_read(reg) & 0xffffffff
def stack(u, n=6):
    sp = rd(u, UC_M68K_REG_A7); return struct.unpack(f">{n}I", u.mem_read(sp, 4 * n))

# -- events: arm caller, arm post, end post (as recloop.py) --------------------
ev = []
def at(label, nargs=5):
    def h(u, addr, size, user):
        if len(ev) < 4000:
            ev.append(dict(frame=rt.frame_count, sample=rt.sample, label=label,
                           stack=[f"{x:#x}" for x in stack(u, nargs + 1)]))
    return h
for pc, label in ((0x40005ff0, "armcall"), (0x40006b18, "armpost"), (0x40006edc, "endpost")):
    uc.hook_add(UC_HOOK_CODE, at(label), begin=pc, end=pc)

# -- FLEX playback bind probe (RTOS_FORK 10.13: 0x4000f450 binds a FLEX voice
# for a NOTE/play trig; 0x4000d49e calls it 3x). Log firing + registers to see
# whether the recorder-buffer play trig binds a voice and with what slot/ptr.
from unicorn.m68k_const import (UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2,
    UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2)
flex_ev = []
def flex_at(label):
    def h(u, addr, size, user):
        if len(flex_ev) < 400:
            flex_ev.append((label, rt.frame_count,
                [f"{rd(u,r):#x}" for r in (UC_M68K_REG_D0,UC_M68K_REG_D1,UC_M68K_REG_D2,
                                            UC_M68K_REG_A0,UC_M68K_REG_A1,UC_M68K_REG_A2)],
                [f"{x:#x}" for x in stack(u,4)]))
    return h
if getattr(a, "flex_probe", False):
    for pc,label in ((0x4000d49e,"caller_d49e"),(0x4000f450,"flexbind_f450")):
        uc.hook_add(UC_HOOK_CODE, flex_at(label), begin=pc, end=pc)

SNAP_HEAD = 48                      # samples from position 0
SNAP_PERIODS = (20672, 22050)       # 4 steps at 128 / 120 BPM: the seam region [P-32, P+8)
snaps = []
def snap_chain():
    """the recorder buffer as it stands NOW: head samples and the samples around each period"""
    row_base = POOL_ROWS + (a.track + 2) * POOL_ROW_N * 2
    row = struct.unpack(">24H", uc.mem_read(row_base, 48))
    def rd_samples(s0, n):
        out = b""
        for smp in range(s0, s0 + n):
            blk = row[smp // 1024]
            out += bytes(uc.mem_read(POOL_BASE + blk * POOL_BLOCK + (smp % 1024) * 6, 6))
        return out
    d = {"head": rd_samples(0, SNAP_HEAD)}
    for P in SNAP_PERIODS:
        d[P] = rd_samples(P - 32, 40)
    return d
def on_arm_snap(u, addr, size, x):
    if len(snaps) < 64:
        snaps.append((rt.frame_count, rt.sample, snap_chain()))
uc.hook_add(UC_HOOK_CODE, on_arm_snap, begin=0x40005ff0, end=0x40005ff0)

# -- the core select (which DSP an outbound block is for) ----------------------
gpio = {"v": None}
def on_gpio(u, acc, addr, size, val, x): gpio["v"] = val & 0xff
uc.hook_add(UC_HOOK_MEM_WRITE, on_gpio, begin=er.DSP_SELECT, end=er.DSP_SELECT + 3)

# -- outbound blocks (host -> DSP): the 1024-byte one is the audio -------------
audio_out = []          # (frame, sample, gpio, saddr, bytes)
out_log = []            # first few of every outbound transfer, to see the protocol
def on_transfer(ch, paced, f):
    lo, hi = rt.edma.HOSTPORT
    src_host = lo <= f["saddr"] < hi
    dst_host = lo <= f["daddr"] < hi
    if not (src_host or dst_host):
        return
    if len(out_log) < 90:
        out_log.append(dict(frame=rt.frame_count, ch=ch, paced=paced, gpio=gpio["v"],
                            **{k: (f"{v:#x}" if isinstance(v, int) else v) for k, v in f.items()}))
    if dst_host:
        n = f["nbytes"] * max(1, f["biter"] & 0x1ff)
        if n == 1024 and len(audio_out) < 2 * a.frames + 64:
            audio_out.append((rt.frame_count, rt.sample, gpio["v"], f["saddr"],
                              bytes(uc.mem_read(f["saddr"], 1024))))
rt.edma.on_transfer = on_transfer

# -- per-frame recorder record fields, both banks, the track ------------------
rec_fields = []
def on_frame_edge():
    if len(rec_fields) >= a.frames + 64: return
    rows = []
    for bank in (0, 1):
        b = REC_STATE + bank * 672 + a.track * 84
        rows.append(bytes(uc.mem_read(b, 84)))
    rec_fields.append((rt.frame_count, rt.sample, rows[0], rows[1]))

# -- inbound (DSP -> host): fill the read-back at the paced chain's completion --
inj = {"seq": 0, "log": []}
orig_complete = rt.edma._complete
SPAN_TAG = {1: 1, 6: 4, 7: 8}     # R-channel tag: which DMA span the recorder took its input from
def fill(ch):
    """the DSP delivered this span: (frame, i) sample counter in L, a layout probe in R"""
    daddr = rt.edma._u(ch, 0x10, 4)
    n = rt.edma._u(ch, 8, 4) * max(1, rt.edma._u(ch, 0x1c, 2) & 0x1ff)
    nl = n // 4
    tag = SPAN_TAG[ch] | (2 if gpio["v"] else 0)      # +2 = the core-1 half
    words = [0] * nl
    for k in range(nl):
        t, i, c = (k // 32), (k // 2) % 16, k % 2
        smp = 16 * rt.frame_count + i
        # 15-bit counter: NON-NEGATIVE on purpose. Under MACSR 0xa0 (the
        # fade stage's saturating mode) this Unicorn returns 0 for any
        # negative msacl result (micro-test 8 Sep 2026: 0x80000000 x
        # 0xea700000 -> 0, hardware 0xea700000) -- a fourth EMAC defect,
        # in the fractional patch's saturation path, not yet fixed in the
        # library. A positive signal never meets it.
        words[k] = ((smp & 0x7fff) << 16) if c == 0 else (((tag << 8) | (t << 4) | i) << 16)
    if a.inject == "burst" and (rt.frame_count - frame0) >= a.burst_frames:
        for k in range(nl):
            if k % 2 == 0: words[k] = 0          # silence the audio (L) after the burst window; keep the R tag
    uc.mem_write(daddr, struct.pack(f">{nl}I", *words))
    return daddr, n
def complete(ch):
    orig_complete(ch)
    if ch not in SPAN_TAG:
        return
    if ch == 1:
        on_frame_edge()
    if a.inject == "none":
        return
    daddr, n = fill(ch)
    inj["seq"] += 1
    if len(inj["log"]) < 16:
        inj["log"].append(dict(frame=rt.frame_count, ch=ch, gpio=gpio["v"], daddr=f"{daddr:#x}", n=n))
rt.edma._complete = complete

# -- the mix stage's reads: where its four sources actually are -----------------
from unicorn import UC_HOOK_MEM_READ
rp = []
def on_read(u, acc, addr, size, val, x):
    pc = rd(u, UC_M68K_REG_PC)
    if 0x40007680 <= pc <= 0x40007748 and len(rp) < 600:
        rp.append((rt.frame_count, pc, addr, size, int.from_bytes(u.mem_read(addr, size), "big")))
if a.read_probe:
    uc.hook_add(UC_HOOK_MEM_READ, on_read, begin=0x80000000, end=0x8000ffff)

# -- record-field writes: who keeps (or resets) the gain smoother state ---------
fp = []
def on_field_write(u, acc, addr, size, val, x):
    if len(fp) < 2000:
        bank = 1 if addr >= REC_STATE + 672 else 0
        fp.append((rt.frame_count, bank, addr - (REC_STATE + bank * 672 + a.track * 84), size, val & 0xffffffff, rd(u, UC_M68K_REG_PC)))
if a.field_probe:
    for bank in (0, 1):
        b = REC_STATE + bank * 672 + a.track * 84
        uc.hook_add(UC_HOOK_MEM_WRITE, on_field_write, begin=b + 36, end=b + 83)

# -- mix-loop registers: the four sources and their gains ----------------------
regp = []
seen = {}
def on_loop(u, addr, size, x):
    if 323 <= rt.frame_count <= 326 and len(regp) < 400:
        key = (rt.frame_count, addr)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 2: return
        g = lambda r: u.reg_read(r) & 0xffffffff
        sp = g(UC_M68K_REG_A7)
        regs = [g(r) for r in (UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3, UC_M68K_REG_A4, UC_M68K_REG_A5,
                                UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7)]
        regp.append((rt.frame_count, addr, regs, int.from_bytes(u.mem_read(sp + 116, 4), "big")))
if a.reg_probe:
    for pc in (0x40007682, 0x400076f6, 0x400077de, 0x40007854):
        uc.hook_add(UC_HOOK_CODE, on_loop, begin=pc, end=pc)
    stg = []
    def on_pack(u, addr, size, x):
        if rt.frame_count == 324 and len(stg) < 2:
            stg.append((rt.frame_count, bytes(u.mem_read(0x800062cc, 0x200)), bytes(u.mem_read(0x80006344, 0x100)), bytes(u.mem_read(0x8000644c, 0x80))))
    uc.hook_add(UC_HOOK_CODE, on_pack, begin=0x40007854, end=0x40007854)

# -- pool writes: the pack loop's own addresses -------------------------------
pool_w = {"first": [], "blocks": set(), "per_frame": {}}
POOL_CLEAR_PC = 0x400209a4      # the load-time pool clear (every block, frame 0): not the recorder
def on_pool_write(u, acc, addr, size, val, x):
    pc = rd(u, UC_M68K_REG_PC)
    if pc == POOL_CLEAR_PC:
        return
    pool_w["blocks"].add((addr - POOL_BASE) // POOL_BLOCK)
    pf = pool_w["per_frame"]; pf[rt.frame_count] = pf.get(rt.frame_count, 0) + 1
    if len(pool_w["first"]) < 400:
        pool_w["first"].append((rt.frame_count, addr, size, val & 0xffffffff, pc))
uc.hook_add(UC_HOOK_MEM_WRITE, on_pool_write, begin=POOL_BASE, end=POOL_BASE + (POOL_ROW_N + 1) * POOL_BLOCK)

uc.ctl_flush_tb()
if not rt.gate_m6a()[0]:
    rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
mounted, posted, saved_bank, final_bank, _ = rt.load_project_live("OCTABAM", name, run_ms=20000)
if final_bank != saved_bank: final_bank = rt.select_bank_live(saved_bank)
pattern = uc.mem_read(er.CUR_PATTERN, 1)[0]
rt.seq_select_live(final_bank, pattern); rt.internal_clock()
rt.frame = True; rt.next_frame = rt.sample + er.FRAME_PERIOD; rt.exact_clock()
rt.start_transport_live()
rt.install_trig_log()
frame0 = rt.frame_count + 1; target = frame0 + a.frames
t0 = time.time(); last = frame0
print(f"run: {a.frames} frames from frame0={frame0}, RECORD_24BIT={uc.mem_read(REC_24BIT,1)[0]}", flush=True)
while rt.frame_count < target:
    step = min(500, target - rt.frame_count)
    rt.run(ms=step * er.FRAME_PERIOD / er.SAMPLE_HZ * 1000.0 * 5 + 200,
           until=lambda x: x.frame_count >= last + step)
    if rt.frame_count == last:
        print("no progress; stopping", flush=True); break
    last = rt.frame_count
    print(f"  frame {rt.frame_count - frame0}/{a.frames}  {time.time()-t0:.0f}s  events {len(ev)}  audio_out {len(audio_out)}  inj {inj['seq']}", flush=True)

# -- the recorder buffer: pool row for the track -------------------------------
row_base = POOL_ROWS + (a.track + 2) * POOL_ROW_N * 2
row = struct.unpack(f">{a.blocks}H", uc.mem_read(row_base, a.blocks * 2))
blocks = {}
for bi in sorted(pool_w["blocks"]):
    try:
        blocks[bi] = bytes(uc.mem_read(POOL_BASE + bi * POOL_BLOCK, POOL_BLOCK))
    except Exception as e:
        print(f"  block {bi} unreadable: {e}")
print(f"pool blocks written (absolute index): {sorted(pool_w['blocks'])}; frames with writes: {len(pool_w['per_frame'])}")
print(f"pool row T{a.track+1}: {row}")
if a.reg_probe:
    for f, st, mixo, exist in stg:
        w = struct.unpack(">128I", st)
        print(f"   staging 0x800062cc at pack entry, frame {f}: " + " ".join(f"{x:#x}" for x in w[:40]))
        w = struct.unpack(">64I", mixo)
        print(f"   0x80006344..: " + " ".join(f"{x:#x}" for x in w[:40]))
        w = struct.unpack(">32I", exist)
        print(f"   0x8000644c..: " + " ".join(f"{x:#x}" for x in w[:16]))
    names = "a0 a1 a2 a3 a4 a5 d0 d1 d2 d3 d4 d5 d6 d7".split()
    for f, pc, regs, n in regp:
        print(f"   f{f} pc {pc:#x} n={n} " + " ".join(f"{k}={v:#x}" for k, v in zip(names, regs)))
if a.field_probe:
    import collections
    print("record-field writes by (pc, off):", sorted(collections.Counter((hex(pc), off) for f, bk, off, sz, v, pc in fp).items()))
    for f, bk, off, sz, v, pc in fp:
        if f >= 322: print(f"   f{f} bank{bk} +{off} ({sz}) <- {v:#x}  pc {pc:#x}")
    for f, s_, r0, r1 in rec_fields:
        if 321 <= f <= 328: print(f"   f{f} b0 +36..+83 {r0[36:].hex()} | b1 {r1[36:].hex()}")
if a.read_probe:
    import collections
    print("mix-stage reads by (pc, size):", collections.Counter((hex(pc), sz) for f, pc, ad, sz, v in rp))
    for f, pc, ad, sz, v in rp[:200]:
        print(f"   f{f} pc {pc:#x} rd {ad:#x} ({sz}) = {v:#x}")
rec_setup = bytes(uc.mem_read(0x80000cf4 + 12 * a.track, 12))
print(f"live RECORDING SETUP T{a.track+1} (INAB INCD RLEN TRIG SRC3 LOOP FIN FOUT AB QREC QPL CD): {list(rec_setup)}")
print(f"trig words: {rt.trig_words_log[:16]}")
if getattr(a,"flex_probe",False):
    print(f"FLEX bind events: {len(flex_ev)}")
    for e in flex_ev[:30]: print("  ", e[0], "frame", e[1], "regs D0-2,A0-2", e[2], "stack", e[3])

import pickle
with open(a.out, "wb") as fh:
    pickle.dump(dict(
        frame0=frame0, frames=a.frames, track=a.track, record_24bit=uc.mem_read(REC_24BIT, 1)[0],
        events=ev, out_log=out_log, inj_log=inj["log"], trig_words=rt.trig_words_log[:200],
        audio_out=[(f, s, g, sa, d) for f, s, g, sa, d in audio_out],
        rec_fields=[(f, s, r0, r1) for f, s, r0, r1 in rec_fields],
        pool_row=list(row), pool_blocks=blocks, pool_first=pool_w['first'], pool_per_frame=pool_w['per_frame'], rec_setup=rec_setup, snaps=snaps), fh)
print(f"saved {a.out}: {len(audio_out)} audio blocks, {len(blocks)} pool blocks, {len(ev)} events")
