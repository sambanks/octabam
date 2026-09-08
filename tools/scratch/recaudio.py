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
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
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
ap.add_argument("--voice-probe", action="store_true", help="capture the track's 84-word record (DSP.md: the voice's audio, both ping sides) every frame")
ap.add_argument("--packer-probe", action="store_true", help="watch the packer's per-track dispatch (0x4000d472 bit4 test, 0x4000d47e arena lookup, 0x4000d484 null check) -- RTOS_FORK 10.34's next step")
ap.add_argument("--rec-write-probe", action="store_true", help="watch every write to the track's 84-word record (both ping sides) with its PC, near --rec-write-window")
ap.add_argument("--rec-write-window", type=int, nargs=2, default=(0, 10 ** 9), help="frame0 frame1: only log rec-write-probe hits in this frame range (default: all)")
ap.add_argument("--render-gate-probe", action="store_true", help="watch 0x40007960's silence-vs-render gate (a3@8/a3@16 early exits, a2@0 the zero-fill-vs-fetch flag) -- RTOS_FORK 10.34's 3rd probe")
ap.add_argument("--blocks", type=int, default=40, help="pool blocks to dump from the row")
ap.add_argument("--main-level", type=int, default=64, help="SET MAIN LEVEL to post after the load (0 = do not post; without it no voice renders, O9b)")
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

# -- packer per-track dispatch probe (RTOS_FORK 10.34's next step): the
# packer's bit4 test (0x4000d472: does this track's machine-type flag byte
# have bit4 set -- gates the whole audio-assembly block), the arena lookup
# (0x4000d47e: a0 = *(d6 + slot*4), the per-slot voice-render pointer) and
# its null check (0x4000d484: beqs skips assembly if the slot has no active
# voice registered). d3 is the packer's own track index (0-based) at every
# hook site.
from unicorn.m68k_const import UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D6
pack_ev = []
def pack_at(label, regs):
    def h(u, addr, size, user):
        d3 = rd(u, UC_M68K_REG_D3)
        if d3 != a.track:                     # only this track -- else the shared
            return                             # cap (4000) empties in ~170 frames
        if len(pack_ev) < 40000:
            pack_ev.append((label, rt.frame_count, d3,
                             {n: f"{rd(u,r):#x}" for n, r in regs}))
    return h
if a.packer_probe:
    uc.hook_add(UC_HOOK_CODE, pack_at("bit4_test", (("d0", UC_M68K_REG_D0), ("d1", UC_M68K_REG_D1))),
                begin=0x4000d472, end=0x4000d472)
    uc.hook_add(UC_HOOK_CODE, pack_at("arena_lookup", (("d4", UC_M68K_REG_D4), ("d6", UC_M68K_REG_D6))),
                begin=0x4000d47e, end=0x4000d47e)
    uc.hook_add(UC_HOOK_CODE, pack_at("null_check", (("a0", UC_M68K_REG_A0),)),
                begin=0x4000d484, end=0x4000d484)

# -- the per-frame render function's own silence-vs-fetch gate (0x40007960,
# called from the packer's unconditional 0x4000d52c jsr; found by disassembly
# after --rec-write-probe showed the sample-pair region is written ZERO every
# frame through pass 2 -- RTOS_FORK 10.34's 3rd probe). a2 = table[a5] (a5 =
# the LOW NIBBLE of the per-track flag byte, from d2 at the call site), a3 =
# a2@(4). Two early exits (a3@8 != 0, or a3@16 <= 0) bail via a shared tail
# with no write at all; past those, tstb a2@(0) at 0x400079b2 chooses ZERO-FILL
# (a2's byte clear) vs the real fetch path at 0x400079cc (a2's byte set).
from unicorn.m68k_const import UC_M68K_REG_A6
import collections
gate_ev = []
gate_hits = [0]
gate_track_args = collections.Counter()
_gate_track_ptrs = None
def _track_ptrs():
    global _gate_track_ptrs
    if _gate_track_ptrs is None:
        track = a.track + 1
        core = 0 if track >= 5 else 1
        pos = (track - 1) % 4
        base0, base1 = TRACKREC[core]
        _gate_track_ptrs = {base0 + pos * 84 * 4 + 0x20, base1 + pos * 84 * 4 + 0x20}
    return _gate_track_ptrs
def on_gate(u, addr, size, x):
    gate_hits[0] += 1
    a2 = rd(u, UC_M68K_REG_A2)
    fp = rd(u, UC_M68K_REG_A6)
    try:
        # fp+8 is NOT a track index (found 9 Sep 2026: it's a raw pointer,
        # exactly track_base + 0x20 -- the destination for the sample-pair
        # write, not a track number). Match on that pointer instead.
        dest_ptr = struct.unpack(">I", u.mem_read(fp + 8, 4))[0]
    except Exception:
        return
    if gate_hits[0] <= 4000:
        gate_track_args[dest_ptr] += 1
    if dest_ptr not in _track_ptrs() or len(gate_ev) >= 20000:
        return
    track_arg = dest_ptr
    try:
        a3 = struct.unpack(">I", u.mem_read(a2 + 4, 4))[0]
        flag = u.mem_read(a2, 1)[0]
        a3_8 = struct.unpack(">i", u.mem_read(a3 + 8, 4))[0] if a3 else None
        a3_16 = struct.unpack(">i", u.mem_read(a3 + 16, 4))[0] if a3 else None
    except Exception as e:
        gate_ev.append((rt.frame_count, track_arg, "ERR", str(e))); return
    gate_ev.append((rt.frame_count, track_arg, a2, a3, flag, a3_8, a3_16))
if a.render_gate_probe:
    uc.hook_add(UC_HOOK_CODE, on_gate, begin=0x4000798a, end=0x4000798a)

# -- the fetch-availability call inside the format-converter (0x40008ca0's
# caller, found by disassembly past the a2@0 flag: even when the fetch branch
# is taken -- both trig frames -- it still writes zero, at 0x40008cfc's
# fallback, gated on this call's D1 return. 0x40008c9c calls through a2's own
# cached function pointer (fp@-68) with (a2, a2@(72)=the read position);
# D0/D1 come back as an (address, count) pair -- D1==0 forces the zero-fill.
from unicorn.m68k_const import UC_M68K_REG_D1, UC_M68K_REG_D5
fetch_ev = []
def on_fetch_call(u, addr, size, x):
    a2 = rd(u, UC_M68K_REG_A2)
    if a2 not in _track_ptrs_a2() or len(fetch_ev) >= 4000:
        return
    a0 = rd(u, UC_M68K_REG_A0)                      # the call target (about to jsr)
    pos = struct.unpack(">i", u.mem_read(a2 + 72, 4))[0]
    fetch_ev.append(("call", rt.frame_count, a2, a0, pos))
def on_fetch_ret(u, addr, size, x):
    a2 = rd(u, UC_M68K_REG_A2)
    if a2 not in _track_ptrs_a2() or len(fetch_ev) >= 4000:
        return
    d0 = rd(u, UC_M68K_REG_D0); d1 = rd(u, UC_M68K_REG_D1)
    fetch_ev.append(("ret", rt.frame_count, a2, d0, d1))
_track_ptrs_a2_cache = None
def _track_ptrs_a2():
    global _track_ptrs_a2_cache
    if _track_ptrs_a2_cache is None:
        _track_ptrs_a2_cache = {0x800049d8}    # a2 was constant here across both frames -- confirm/extend if not
    return _track_ptrs_a2_cache
if a.render_gate_probe:
    uc.hook_add(UC_HOOK_CODE, on_fetch_call, begin=0x40008c9c, end=0x40008c9c)
    uc.hook_add(UC_HOOK_CODE, on_fetch_ret, begin=0x40008ca0, end=0x40008ca0)

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
# ch1 (SPAN_TAG[1]) completes TWICE per rt.frame_count tick (once per ping/core
# side) -- found 9 Sep 2026 chasing a voice-probe dump that silently stopped at
# frame 5107 of a 10150-frame run: the a.frames+64 cap was counting CALLS, so it
# exhausted at half the real frame count. Dedupe by frame_count so the cap is on
# frames reached, not on_frame_edge invocations.
rec_fields = []
def on_frame_edge():
    if rec_fields and rec_fields[-1][0] == rt.frame_count: return
    if len(rec_fields) >= a.frames + 64: return
    rows = []
    for bank in (0, 1):
        b = REC_STATE + bank * 672 + a.track * 84
        rows.append(bytes(uc.mem_read(b, 84)))
    rec_fields.append((rt.frame_count, rt.sample, rows[0], rows[1]))
    if a.voice_probe and len(voice_rec) < a.frames + 64:
        track = a.track + 1
        core = 0 if track >= 5 else 1
        base0, base1 = TRACKREC[core]
        # capture the WHOLE 4-track (1344-byte) block on both ping sides --
        # not just the assumed pos=(track-1)%4 slot -- the pos->track mapping
        # is unverified here (this project's r7/track-core mappings have been
        # backwards before) and is worth checking directly rather than assumed.
        recs = tuple(bytes(uc.mem_read(base, 84 * 4 * 4)) for base in (base0, base1))
        voice_rec.append((rt.frame_count, rt.sample) + recs)

# -- the track's 84-word record (DSP.md: "four 84-word per-track records",
# 0x150 bytes each, ping/pong): the voice's OWN audio -- what O10 (under the
# port) found the FLEX-render's output actually travels in, as opposed to
# audio_out (the recorder INPUT block). Read directly from ColdFire host
# memory: each of the 84 words is a 24-bit value left-justified in a 4-byte
# big-endian long (top 3 bytes; DSP.md 6/O10's wire-halfword-pair decode of
# the same bytes gives the identical value, verified by construction).
TRACKREC = {1: (0x80001c90, 0x80002710), 0: (0x800021d0, 0x80002c50)}
voice_rec = []          # (frame, sample, ping0_bytes[336], ping1_bytes[336])

def voice_words(raw336):
    out = []
    for i in range(0, len(raw336), 4):
        v = int.from_bytes(raw336[i:i + 3], "big")
        out.append(v - (1 << 24) if v >= 1 << 23 else v)
    return out

def voice_segments(rec84):
    """16 (L,R) pairs from the segmented record (O10: 4-word header (count,0,
    0x40000,tag) + count pairs; a THRU voice ships two empty headers then the
    16 pairs, a FLEX voice splits them across several headers)."""
    pairs = []; i = 0
    while len(pairs) < 16 and i + 4 <= len(rec84):
        if rec84[i + 1] == 0 and rec84[i + 2] == 0x40000 and 0 <= rec84[i] <= 16:
            cnt = rec84[i]; i += 4
            if cnt:
                pairs += [(rec84[i + 2 * k], rec84[i + 2 * k + 1]) for k in range(cnt)]
                i += 2 * cnt
            continue
        take = 16 - len(pairs)
        pairs += [(rec84[i + 2 * k], rec84[i + 2 * k + 1]) for k in range(take)]
        i += 2 * take
    return pairs[:16]

# -- every write to the track's own 84-word record, with its PC -- RTOS_FORK
# 10.34's 2nd probe: --packer-probe found the bit4-gated block (0x4000d47a..
# 0x4000d4ce) is a ONE-FRAME pulse on the trig frame only, calling the SAME
# 0x4000f450 bind §10.13/10.33 already knew about (a1@(d4*4) is a small
# per-machine-type dispatch table, not a per-voice arena: a0 == 0x4000f450
# both times, d4==1==FLEX). So steady-state segment writing, if it happens,
# must be the UNCONDITIONAL per-frame call at 0x4000d52c instead. Rather than
# keep tracing control flow, watch the destination bytes directly: does
# anything, ever, write real (nonzero-beyond-header) content into this
# track's slot of either ping buffer?
rw_ev = []
def on_rec_write(u, acc, addr, size, val, x):
    if not (a.rec_write_window[0] <= rt.frame_count <= a.rec_write_window[1]):
        return
    if len(rw_ev) < 60000:
        rw_ev.append((rt.frame_count, addr, size, val & 0xffffffff, rd(u, UC_M68K_REG_PC)))
if a.rec_write_probe:
    track = a.track + 1
    core = 0 if track >= 5 else 1
    pos = (track - 1) % 4
    base0, base1 = TRACKREC[core]
    for base in (base0, base1):
        lo = base + pos * 84 * 4
        uc.hook_add(UC_HOOK_MEM_WRITE, on_rec_write, begin=lo, end=lo + 84 * 4 - 1)

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
if a.main_level:
    print(f"main level {a.main_level}: gain table[0] = {rt.set_main_level_live(a.main_level):#x}", flush=True)
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
if a.voice_probe:
    print(f"voice_rec: {len(voice_rec)} frames captured (track {a.track+1}, ping bases {TRACKREC[0 if a.track+1>=5 else 1]})")
    # find every play trig (armpost/endpost aren't it -- trig_words_log carries the raw pattern trigs)
    # and print the record around the frames near each of the arm/end events, both ping sides
    of_interest = set()
    for e in ev:                                    # armcall/armpost/endpost
        for d in range(-1, 4): of_interest.add(e["frame"] + d)
    for lbl, fr, regs, stk in flex_ev:               # the play-trig FLEX bind (10.33)
        for d in range(-1, 4): of_interest.add(fr + d)
    if not of_interest:                              # nothing hooked -- dump the tail
        of_interest = {fr for fr, *_ in voice_rec[-8:]}
    of_interest |= {fr for fr, *_ in voice_rec if fr % 20 == 0}   # a periodic sample too
    for fr, sm, p0, p1 in voice_rec:
        if fr not in of_interest:
            continue
        for tag, raw in (("ping0", p0), ("ping1", p1)):
            for pos in range(4):
                slot = raw[pos * 84 * 4: (pos + 1) * 84 * 4]
                words84 = voice_words(slot)
                nz = sum(1 for w in words84 if w)
                if nz <= 4:      # skeleton-only (skip the near-static header noise)
                    continue
                segs = voice_segments(words84)
                print(f"  frame {fr} {tag} pos{pos}: nonzero {nz}/84  segs(L)={[l for l,r in segs]}")
if a.packer_probe:
    print(f"packer dispatch events (track {a.track+1}): {len(pack_ev)}")
    poi = set()
    for e in ev: poi |= {e["frame"] + d for d in range(-1, 4)}
    for lbl, fr, d3, regs in pack_ev:
        if fr % 200 == 0: poi.add(fr)
    for lbl, fr, d3, regs in pack_ev:
        if fr in poi:
            print(f"  frame {fr} {lbl}: {regs}")
    nulls = [e for e in pack_ev if e[0] == "null_check"]
    zero = sum(1 for e in nulls if e[3]["a0"] == "0x0")
    print(f"  null_check reached {len(nulls)}x, a0==0 (skip) {zero}x, a0!=0 (assemble) {len(nulls)-zero}x")
    if nulls:
        nz = [e for e in nulls if e[3]["a0"] != "0x0"]
        print(f"  first a0!=0 at frame {nz[0][1]}" if nz else "  a0 is NEVER nonzero in this run")
if a.rec_write_probe:
    import collections
    print(f"rec-write-probe: {len(rw_ev)} writes to T{a.track+1}'s record in frames {a.rec_write_window}")
    by_pc = collections.Counter(pc for f, addr, sz, v, pc in rw_ev)
    print("  by PC:", {f"{pc:#x}": n for pc, n in by_pc.most_common(20)})
    nz_writes = [e for e in rw_ev if e[3] != 0]
    print(f"  {len(nz_writes)} of them wrote a NONZERO value")
    for f, addr, sz, v, pc in rw_ev[:60]:
        print(f"   f{f} {addr:#x} ({sz}) <- {v:#x}  pc {pc:#x}")
if a.render_gate_probe:
    print(f"render-gate: hook fired {gate_hits[0]}x total; track_arg distribution (first 4000 hits): {dict(gate_track_args)}")
    t1 = [e for e in gate_ev if e[2] != "ERR"]
    print(f"render-gate: {len(gate_ev)} calls captured for track {a.track+1} ({len(gate_ev)-len(t1)} errored)")
    early1 = sum(1 for e in t1 if e[3] is None or (e[5] is not None and e[5] != 0))
    early2 = sum(1 for e in t1 if e[3] and e[5] == 0 and (e[6] is None or e[6] <= 0))
    flagset = sum(1 for e in t1 if e[3] and e[5] == 0 and e[6] is not None and e[6] > 0 and e[4] != 0)
    flagclear = sum(1 for e in t1 if e[3] and e[5] == 0 and e[6] is not None and e[6] > 0 and e[4] == 0)
    print(f"  early-exit-1 (a3 null or a3@8!=0): {early1}")
    print(f"  early-exit-2 (a3@16<=0): {early2}")
    print(f"  reached tstb: flag(a2@0)==0 [ZERO-FILL] {flagclear}x, flag!=0 [FETCH] {flagset}x")
    poi = set()
    for e in ev: poi |= {e["frame"] + d for d in range(-1, 4)}
    seen = set()
    for e in t1:
        f = e[0]
        if f in poi and f not in seen:
            seen.add(f)
            a3_str = f"{e[3]:#x}" if e[3] else "NULL"
            print(f"   f{f} track_arg={e[1]} a2={e[2]:#x} a3={a3_str} flag(a2@0)={e[4]} a3@8={e[5]} a3@16={e[6]}")
    print(f"fetch-call/ret events: {len(fetch_ev)}")
    for e in fetch_ev:
        if e[0] == "call":
            print(f"   f{e[1]} CALL a2={e[2]:#x} target={e[3]:#x} pos(a2@72)={e[4]}")
        else:
            print(f"   f{e[1]} RET  a2={e[2]:#x} d0={e[3]:#x} d1={e[4]:#x}")

import pickle
with open(a.out, "wb") as fh:
    pickle.dump(dict(
        frame0=frame0, frames=a.frames, track=a.track, record_24bit=uc.mem_read(REC_24BIT, 1)[0],
        events=ev, out_log=out_log, inj_log=inj["log"], trig_words=rt.trig_words_log[:200],
        audio_out=[(f, s, g, sa, d) for f, s, g, sa, d in audio_out],
        rec_fields=[(f, s, r0, r1) for f, s, r0, r1 in rec_fields],
        pool_row=list(row), pool_blocks=blocks, pool_first=pool_w['first'], pool_per_frame=pool_w['per_frame'], rec_setup=rec_setup, snaps=snaps,
        voice_rec=voice_rec, flex_ev=flex_ev if getattr(a, "flex_probe", False) else None,
        pack_ev=pack_ev if a.packer_probe else None,
        rw_ev=rw_ev if a.rec_write_probe else None,
        gate_ev=gate_ev if a.render_gate_probe else None,
        fetch_ev=fetch_ev if a.render_gate_probe else None), fh)
print(f"voice record 0x80000510 + 48*t, ping 0, after the run: " + " ".join(f"T{t+1}={int.from_bytes(uc.mem_read(0x80000510 + 48 * t, 4), 'big'):#010x}" for t in range(8)))
print(f"saved {a.out}: {len(audio_out)} audio blocks, {len(blocks)} pool blocks, {len(ev)} events, {len(voice_rec)} voice_rec frames")
