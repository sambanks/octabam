// Host-side test harness for the Octatrack's DSP56300 effect algorithms.
//
// The point of this is to make DSP work debuggable. Without it the loop is
// assemble -> repack -> flash -> listen, which is hopeless for tuning something
// like a reverb. With it we can run an effect on the desktop, feed it audio and
// write a WAV.
//
// It uses the emulator from the same project that gave us the disassembler
// (dsp56kEmu, built for the Access Virus), loads a payload's full memory image
// via tools/dsp_modmap.py --dumpmem, and calls an effect through the ABI we
// recovered:
//
//     r0 = audio block base (interleaved stereo, processed IN PLACE)
//     n7 = frame count
//     r6 = parameter block; x:(r6+0..5) page 1, values 0..127 << 16
//     rts to return
//
// MULTIPLE INSTANCES
//
// The reverb works on one track and hangs the moment a second one exists, so
// the harness runs N instances the way the hardware does: every instance's init
// runs first, then each block is handed to every instance in turn, each with its
// own r7 state block, its own buffer base and its own audio.
//
// The instance model is measured, not assumed. dsp/r7probe.asm returned r7 =
// 0x6200 for the first FX2 instance, and dsp/baseprobe.asm returned bases
// 0x4000 and 0x8000 for two of them -- table entries 1 and 3. Both pointers step
// by TWO per track because each track allocates an FX1 slot and an FX2 slot, and
// the FX1 one comes first:
//
//     track 1 FX1 -> alloc 0 (Y:0x1000, 3072 words)  r7 = 0x6100
//     track 1 FX2 -> alloc 1 (Y:0x4000, 16384 words) r7 = 0x6200   <- measured
//     track 2 FX1 -> alloc 2 (Y:0x1c00)              r7 = 0x6300
//     track 2 FX2 -> alloc 3 (Y:0x8000)              r7 = 0x6400   <- measured
//
// so FX2 instance k defaults to alloc index 1+2k and state block 0x6000+(2+2k).
//
// GUARD
//
// -guard shadows Y:0x0000..0xBFFF (all of real Y) and the loaded part of P, and
// after every proc call reports any word that changed outside the calling
// instance's own [base, base+0x3800). That catches the two things that hang this
// DSP without any symptom at the point of failure: a buffer overrun into another
// instance, and a stray write into loaded code.
//
// Usage:
//   dsp_host -mem out/dsp/mem_A.mem -init <hex> -proc <hex> [options]
//     -inst N               number of instances to run (default 1)
//     -alloc a,b,..         allocator table index per instance (default 1,3,5,..)
//     -r7 a,b,..            state block index per instance (default 2,4,6,..)
//     -allocproc MODE       what X:0x213 holds during proc, not init:
//                             perinst (default) this instance's entry
//                             end             left past the last instance
//                             keep            never rewritten after the inits
//     -params a,b,...       parameter values 0..127 (default 64); 6 fills page 1,
//                           8 also covers the page-2 slots. Repeat the option to
//                           give successive instances different values.
//     -split N              a=0 sub-block call of N frames, then a=1 for the rest
//                           (the post-trig state). Omitted = split 0, where the
//                           a=0 call is SKIPPED -- what the dispatcher does.
//     -guard [words]        police buffer bounds (default window 0x3800 words)
//     -frames N             frames per block (default 32)
//     -blocks N             blocks to run (default 256)
//     -in file.raw          24-bit mono raw input, else an impulse is used
//     -out file.raw         write instance 0; others go to file.raw.i1, .i2, ...
//     -trace N              log the first N instructions executed
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <fstream>
#include <iostream>

#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/memory.h"
#include "dsp56kEmu/peripherals.h"

using namespace dsp56k;

namespace {

class AllowAll : public IMemoryValidator {
public:
    bool memValidateAccess(EMemArea, TWord, bool) const override { return true; }
};

struct Args {
    std::string mem, in, out;
    TWord init = 0, proc = 0, audio = 0x000080, params = 0x000100, state = 0x010000;
    int frames = 32, blocks = 256, trace = 0, diff = 0, spray = 0;
    TWord flags = 0; int pingpong = -1;
    int inst = 1; TWord dirty = 0; bool noctl = false;
    bool dispatch = false; int fx2tracks = 0; TWord fxid = 0x16;
    int split = 0; TWord prevfx = 0;
    std::vector<int> allocIdx, r7Idx;
    std::vector<std::vector<int>> pv;          // one parameter set per instance
    std::string allocProc = "perinst";
    bool guard = false; TWord guardWords = 0x3800;
    std::vector<TWord> peekY, peekX;
    std::vector<std::pair<TWord, TWord>> pokeY;
};

// Everything the dispatcher would set up for one effect instance.
struct Instance {
    TWord alloc = 0;        // X address of its entry in the base table
    TWord base  = 0;        // Y base that entry holds
    TWord state = 0;        // r7
    TWord audio = 0;        // r0
    std::vector<int> pv;
    std::ofstream out;
    long nonzero = 0;
    long violations = 0;
    long clobbers = 0;
    long cycles = 0;
    long procCalls = 0;
};

// Which Y and P words a loaded module occupies. Writing over one of these is
// the bug that made the reverb hang on two tracks: the base stash was placed in
// a window that is free in payload A but holds a live 128-word coefficient table
// in payload B, so the effect corrupted another algorithm and then read that
// algorithm's data back as its own buffer base.
std::vector<bool> g_loadedY, g_loadedP;

bool loadMem(DSP& dsp, const std::string& path, int& modules, long& words) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) { std::cerr << "cannot open " << path << "\n"; return false; }
    modules = 0; words = 0;
    g_loadedY.assign(0xC000, false);
    g_loadedP.assign(0x20000, false);
    for (;;) {
        uint8_t sp; uint32_t addr, cnt;
        f.read(reinterpret_cast<char*>(&sp), 1);
        f.read(reinterpret_cast<char*>(&addr), 4);
        f.read(reinterpret_cast<char*>(&cnt), 4);
        if (!f || sp == 0xff) break;
        for (uint32_t i = 0; i < cnt; ++i) {
            uint32_t w; f.read(reinterpret_cast<char*>(&w), 4);
            const TWord ad = addr + i;
            if (sp == 0) {
                dsp.memWriteP(ad, w & 0xffffff);
                if (ad < g_loadedP.size()) g_loadedP[ad] = true;
            } else if (sp == 1) {
                dsp.memWrite(MemArea_X, ad, w & 0xffffff);
            } else {
                dsp.memWrite(MemArea_Y, ad, w & 0xffffff);
                if (ad < g_loadedY.size()) g_loadedY[ad] = true;
            }
        }
        ++modules; words += cnt;
    }
    return true;
}

// Run from _pc until the matching rts pops back past the entry stack depth.
uint32_t g_lastCycles = 0;
bool runToRts(DSP& dsp, TWord pc, int trace, const char* what, uint32_t maxCycles = 50000000) {
    // Call through the emulator's own jsr so the return address is pushed the
    // way the hardware would. The sentinel must be a MAPPED P address -- an
    // out-of-range one faults as soon as the rts returns to it.
    const TWord sentinel = 0x03f000;
    dsp.setPC(sentinel);
    dsp.jsr(pc);
    for (uint32_t i = 0; i < maxCycles; ++i) {
        const TWord cur = dsp.getPC().toWord();
        if (cur == sentinel) { g_lastCycles = i; return true; }
        if (trace && static_cast<int>(i) < trace)
            std::printf("  %s %6u  pc=%06x  a=%012llx r0=%06x r6=%06x n7=%06x lc=%06x\n", what, i, cur,
                        static_cast<unsigned long long>(dsp.regs().a.var & 0xffffffffffffull),
                        dsp.regs().r[0].var, dsp.regs().r[6].var,
                        dsp.regs().n[7].var, dsp.regs().lc.var);
        dsp.execInterpreter();   // single-step; exec() may JIT past the sentinel
    }
    std::cerr << what << ": did not return after " << maxCycles << " cycles (pc="
              << std::hex << dsp.getPC().toWord() << ")\n";
    return false;
}

// Run a straight-line range of P memory (used for the frame context setup).
void runRange(DSP& dsp, TWord lo, TWord hi) {
    dsp.setPC(lo);
    while (dsp.getPC().toWord() <= hi)
        dsp.execInterpreter();
}

// A shadow of the memory an effect must not touch. Y is only real up to 0xC000
// (measured with dsp/ymemprobe.asm); P is checked over the loaded image so a
// stray write into code shows up as itself rather than as a hang later.
struct Guard {
    static const TWord Y_HI = 0xC000;
    static const TWord P_HI = 0x20000;
    std::vector<TWord> y, p;
    bool armed = false;

    void arm(Memory& mem) {
        y.resize(Y_HI); p.resize(P_HI);
        snap(mem);
        armed = true;
    }
    void snap(Memory& mem) {
        for (TWord ad = 0; ad < Y_HI; ++ad) y[ad] = mem.get(MemArea_Y, ad);
        for (TWord ad = 0; ad < P_HI; ++ad) p[ad] = mem.get(MemArea_P, ad);
    }
    // Report anything that changed outside [lo, hi) in Y, or at all in P.
    // Returns the number of offending regions; resyncs the shadow either way.
    // Two separate questions, because they have different severities:
    //   stray   -- wrote outside [lo, hi), which for the stash is deliberate
    //   clobber -- wrote over a word a loaded module put there, which never is
    int check(Memory& mem, TWord lo, TWord hi, const char* who, const char* when,
              int block, bool quiet, int& clobber) {
        int stray = 0;
        TWord runLo = 0; bool inRun = false, runClob = false;
        auto flush = [&](TWord end, const char* area) {
            if (!inRun) return;
            if (runClob) ++clobber; else ++stray;
            if (!quiet && stray + clobber <= 12)
                std::printf("  %s %s %s block %d wrote %s:0x%05x..0x%05x (%u words)%s\n",
                            runClob ? "!! CLOBBER" : "   stray  ", who, when, block, area,
                            runLo, end - 1, end - runLo,
                            runClob ? " -- OVER A LOADED MODULE" : "");
            inRun = false; runClob = false;
        };
        for (TWord ad = 0; ad < Y_HI; ++ad) {
            const TWord v = mem.get(MemArea_Y, ad);
            const bool changed = v != y[ad];
            if (changed) y[ad] = v;
            const bool bad = changed && !(ad >= lo && ad < hi);
            if (bad) {
                if (!inRun) { runLo = ad; inRun = true; }
                if (g_loadedY[ad]) runClob = true;
            } else flush(ad, "Y");
        }
        flush(Y_HI, "Y");
        for (TWord ad = 0; ad < P_HI; ++ad) {
            const TWord v = mem.get(MemArea_P, ad);
            if (v != p[ad]) {
                p[ad] = v;
                if (!inRun) { runLo = ad; inRun = true; }
                if (g_loadedP[ad]) runClob = true;
            } else flush(ad, "P");
        }
        flush(P_HI, "P");
        return stray;
    }
};

std::vector<int> parseList(const char* s) {
    std::vector<int> v;
    std::string t(s);
    for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ",")) v.push_back(atoi(p));
    return v;
}

} // namespace

int main(int argc, char** argv) {
    Args a;
    for (int i = 1; i < argc - 1; ++i) {
        std::string k = argv[i];
        auto v = [&] { return std::string(argv[++i]); };
        if (k == "-mem") a.mem = v();
        else if (k == "-init") a.init = strtoul(argv[++i], nullptr, 16);
        else if (k == "-proc") a.proc = strtoul(argv[++i], nullptr, 16);
        else if (k == "-audio") a.audio = strtoul(argv[++i], nullptr, 16);
        else if (k == "-pblock") a.params = strtoul(argv[++i], nullptr, 16);
        else if (k == "-state") a.state = strtoul(argv[++i], nullptr, 16);
        else if (k == "-frames") a.frames = atoi(argv[++i]);
        else if (k == "-blocks") a.blocks = atoi(argv[++i]);
        else if (k == "-trace") a.trace = atoi(argv[++i]);
        else if (k == "-flags") a.flags = strtoul(argv[++i], nullptr, 16);
        else if (k == "-diff") a.diff = atoi(argv[++i]);
        else if (k == "-spray") a.spray = atoi(argv[++i]);
        else if (k == "-pp") a.pingpong = atoi(argv[++i]);
        else if (k == "-inst") a.inst = atoi(argv[++i]);
        else if (k == "-dirty") a.dirty = strtoul(argv[++i], nullptr, 0);
        // no --i here: -noctl consumes nothing, and decrementing made the
        // parse loop re-read it forever -- the flag hung the harness since
        // the day it was added
        else if (k == "-noctl") { a.noctl = true; }
        else if (k == "-dispatch") a.fx2tracks = atoi(argv[++i]), a.dispatch = true;
        else if (k == "-fxid") a.fxid = strtoul(argv[++i], nullptr, 16);
        else if (k == "-split") a.split = atoi(argv[++i]);
        else if (k == "-prevfx") a.prevfx = strtoul(argv[++i], nullptr, 16);
        else if (k == "-alloc") a.allocIdx = parseList(argv[++i]);
        else if (k == "-r7") a.r7Idx = parseList(argv[++i]);
        else if (k == "-allocproc") a.allocProc = v();
        else if (k == "-in") a.in = v();
        else if (k == "-out") a.out = v();
        else if (k == "-params") {
            auto p = parseList(argv[++i]);
            if (p.size() < 8) p.resize(8, 64);         // page 2 lives at r6+$b..$e
            a.pv.push_back(p);
        }
        else if (k == "-guard") {
            a.guard = true;
            // the size is optional: only consume the next argument if it is one
            if (i + 1 < argc && argv[i + 1][0] != '-')
                a.guardWords = strtoul(argv[++i], nullptr, 0);
        }
        else if (k == "-peeky") {
            std::string t(argv[++i]);
            for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ","))
                a.peekY.push_back(strtoul(p, nullptr, 16));
        }
        else if (k == "-peekx") {
            std::string t(argv[++i]);
            for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ","))
                a.peekX.push_back(strtoul(p, nullptr, 16));
        }
        else if (k == "-pokey") {
            std::string t(argv[++i]);
            for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ",")) {
                char* eq = std::strchr(p, '=');
                if (!eq) continue;
                *eq = 0;
                a.pokeY.emplace_back(strtoul(p, nullptr, 16), strtoul(eq + 1, nullptr, 16));
            }
        }
    }
    // -guard may be the last argument, which the loop above cannot see
    if (argc > 1 && std::string(argv[argc - 1]) == "-guard") a.guard = true;

    if (a.mem.empty() || !a.proc) {
        std::cerr << "usage: dsp_host -mem <file> -init <hex> -proc <hex> [-params a,b,..]\n"
                     "                [-inst N] [-alloc a,b] [-r7 a,b] [-allocproc MODE] [-guard]\n"
                     "                [-frames N] [-blocks N] [-in raw] [-out raw] [-trace N]\n";
        return 2;
    }
    if (a.inst < 1) a.inst = 1;
    if (a.pv.empty()) a.pv.push_back(std::vector<int>(8, 64));

    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("constructing DSP ...\n");
    AllowAll validator;
    Memory mem(validator, 0x080000, 0x800000, 0x200000);   // sizes the library's own tests use
    Peripherals56362 periphX;
    Peripherals56367 periphY;
    DSP dsp(mem, &periphX, &periphY);

    std::printf("DSP constructed; loading memory ...\n");
    int modules = 0; long words = 0;
    if (!loadMem(dsp, a.mem, modules, words)) return 1;
    std::printf("loaded %d modules, %ld words from %s\n", modules, words, a.mem.c_str());

    // ---- frame context ----------------------------------------------------
    // The effects depend on control words that no module initialises; the DSP's
    // own setup routine at P:0x372..0x39e derives them from two loaded pointers
    // (x:0x415, x:0x416). Rather than reconstruct that by hand, run it.
    //
    // It reads the frame count out of x:(x:0x415 + 0x1e) as (w >> 8) & 0xf, so
    // seed that first. The count is capped at 15 frames by the & 0xf.
    if (a.frames > 15) { std::printf("frames capped to 15 (the & 0xf in setup)\n"); a.frames = 15; }
    const TWord blkA = mem.get(MemArea_X, 0x415);
    mem.set(MemArea_X, blkA + 0x1e, (static_cast<TWord>(a.frames) << 8) | a.flags);
    std::printf("seeded x:0x%05x+0x1e = frames %d\n", blkA, a.frames);

    runRange(dsp, 0x372, 0x39e);
    if (a.pingpong >= 0) { mem.set(MemArea_X, 0x41f, static_cast<TWord>(a.pingpong));
        std::printf("ping-pong selector x:0x41f = %d\n", a.pingpong); }

    const TWord ctlA = mem.get(MemArea_X, 0x419);
    const TWord ctlB = mem.get(MemArea_X, 0x208);
    const TWord cnt  = mem.get(MemArea_X, 0x20c);
    std::printf("context: x:0x419=0x%05x  x:0x208=0x%05x  x:0x20c=%u (frames)  "
                "x:0x20d=%u  x:0x20e=%u\n", ctlA, ctlB, cnt,
                mem.get(MemArea_X, 0x20d), mem.get(MemArea_X, 0x20e));
    if (!cnt) { std::printf("  !! frame count is 0 -- the dispatcher would skip the effect\n"); }

    // ---- instances --------------------------------------------------------
    // The dispatcher hands the routine r6 = x:0x208 + 6 and r7 = a state block.
    // DSP_ALLOC_IDX is kept for the single-instance case that predates -inst.
    const TWord pblock = ctlB + 6;
    const char* ai = getenv("DSP_ALLOC_IDX");
    const TWord stateBase = mem.get(MemArea_X, 0x20a);

    std::vector<Instance> inst(a.inst);
    for (int k = 0; k < a.inst; ++k) {
        Instance& I = inst[k];
        int ia = (k < static_cast<int>(a.allocIdx.size())) ? a.allocIdx[k] : 1 + 2 * k;
        int ir = (k < static_cast<int>(a.r7Idx.size()))    ? a.r7Idx[k]    : 2 + 2 * k;
        if (ai && a.inst == 1 && a.allocIdx.empty()) { ia = strtoul(ai, nullptr, 0); ir = ia; }
        I.alloc = 0x255 + ia;
        I.base  = mem.get(MemArea_X, I.alloc);
        I.state = stateBase + ir * 0x100;
        I.audio = a.audio + k * 0x40;               // 15 frames = 30 words, well clear
        I.pv    = a.pv[std::min<size_t>(k, a.pv.size() - 1)];
        std::printf("instance %d: r7 = X:0x%05x (idx %d), base = Y:0x%05x (X:0x%03x idx %d), "
                    "audio X:0x%05x\n", k, I.state, ir, I.base, I.alloc, ia, I.audio);
        std::printf("            params");
        for (int p : I.pv) std::printf(" %d", p);
        std::printf("\n");
        if (!a.out.empty())
            I.out.open(k ? a.out + ".i" + std::to_string(k) : a.out, std::ios::binary);
    }
    // Two instances landing on the same buffer or the same state block is not a
    // configuration the hardware produces; say so rather than debug the result.
    for (int k = 1; k < a.inst; ++k)
        for (int j = 0; j < k; ++j) {
            if (inst[k].base == inst[j].base)
                std::printf("  !! instances %d and %d share base Y:0x%05x\n", j, k, inst[k].base);
            if (inst[k].state == inst[j].state)
                std::printf("  !! instances %d and %d share r7 X:0x%05x\n", j, k, inst[k].state);
        }

    // Page 1 is pblock+0..5. Page 2 is neither contiguous with it nor in
    // display order; the knob names below came from dsp/pagemap_probe.asm:
    //   index 6 -> +$b (knob BAL)   7 -> +$c (MIXF)
    //   index 8 -> +$d (knob MONO)  9 -> +$e (knob PRE)
    //
    // WARNING: those NAMES are not reliable, and at least two are wrong for
    // DARK REV. Read from stock DARK's disassembly: +$c is its PRE-DELAY
    // (P:0x17d4 masks the knob field, scales it, sets m5 = $7ff and walks a
    // 2048-word delay buffer), while +$e is a FLAG word it only ever probes
    // with `btst #$8` (P:0x173c, P:0x1a0d). Reading PRE from +$e cost a
    // hardware flash: the pre-delay was inaudible and knob-deaf because a
    // knob arrives as value<<16, so bit 8 is always clear.
    //
    // The slot offsets here are still correct -- it is only the knob labels
    // that mislead. When a slot's MEANING matters, take it from the stock
    // effect's own reads, not from this comment.
    static const TWord page2[] = {0xb, 0xc, 0xd, 0xe};
    auto setParams = [&](const std::vector<int>& pv) {
        for (size_t i = 0; i < pv.size(); ++i) {
            const TWord off = (i < 6) ? i : page2[(i - 6) % 4];
            mem.set(MemArea_X, pblock + off, (static_cast<TWord>(pv[i]) & 0x7f) << 16);
        }
    };

    // X:0x213 points at an instance's entry in the base table at X:0x255. The
    // stock reverbs read it in INIT, where it is per-instance. Whether it is
    // still per-instance during PROC is the open question -- the dispatcher
    // advances it, so by the time blocks are running it may sit past the last
    // effect. -allocproc chooses which model to run.
    auto setAlloc = [&](TWord v) { mem.set(MemArea_X, 0x213, v); };

    // Hardware does not hand an effect a zeroed buffer -- it holds whatever the
    // previous algorithm left. The emulator does, which can make a build look
    // fine here and behave differently on the device.
    if (a.dirty) {
        TWord x = a.dirty;
        for (TWord ad = 0x1000; ad < 0xC000; ++ad) {
            x ^= x << 13; x ^= x >> 17; x ^= x << 5; x &= 0xffffff;
            mem.set(MemArea_Y, ad, x);
        }
        std::printf("Y:0x1000..0xBFFF filled with garbage (seed 0x%x)\n", a.dirty);
    }

    // -pokey addr=val,... : seed arbitrary Y words before any block runs --
    // e.g. planting a fake "last block's bus accumulator" so a server can be
    // tested for whether it actually reads shared bus scratch, without a
    // second instance running the client code that would normally write it
    // (the harness only supports one -init/-proc pair, so a true mixed-
    // effect multi-instance run isn't possible; this is the substitute).
    for (auto& pv : a.pokeY) {
        mem.set(MemArea_Y, pv.first, pv.second);
        std::printf("poked Y:0x%05x = 0x%06x\n", pv.first, pv.second);
    }

    Guard guard;
    if (a.guard) {
        guard.arm(mem);
        std::printf("guard armed: Y:0x0000..0x%05x + P:0x00000..0x%05x, "
                    "window %u words per instance\n", Guard::Y_HI - 1, Guard::P_HI - 1,
                    a.guardWords);
    }

    // ---- init, every instance, before any block ---------------------------
    for (int k = 0; k < a.inst; ++k) {
        setAlloc(inst[k].alloc);
        setParams(inst[k].pv);
        dsp.regs().r[6].var = pblock;
        dsp.regs().r[7].var = inst[k].state;
        if (a.init) {
            std::printf("running init @P:0x%05x for instance %d ...\n", a.init, k);
            if (!runToRts(dsp, a.init, a.trace, "init")) return 1;
            if (guard.armed) {
                char who[32]; std::snprintf(who, sizeof who, "inst %d", k);
                int cl = 0;
                inst[k].violations += guard.check(mem, inst[k].base,
                                                  inst[k].base + a.guardWords,
                                                  who, "init", 0, false, cl);
                inst[k].clobbers += cl;
            }
        }
    }
    if (a.init) std::printf("all inits returned ok\n");

    const TWord allocEnd = 0x255 + (a.allocIdx.empty() ? 1 + 2 * (a.inst - 1) + 1
                                                       : a.allocIdx.back() + 1);
    if (a.allocProc == "end") {
        setAlloc(allocEnd);
        std::printf("proc-time X:0x213 = 0x%03x for every instance (past the last effect)\n",
                    allocEnd);
    } else if (a.allocProc == "keep") {
        std::printf("proc-time X:0x213 left at 0x%03x from the last init\n",
                    mem.get(MemArea_X, 0x213));
    }

    std::vector<int32_t> input;
    if (!a.in.empty()) {
        std::ifstream f(a.in, std::ios::binary);
        int32_t s;
        while (f.read(reinterpret_cast<char*>(&s), 4)) input.push_back(s);
    }

    // ---- FAITHFUL MODE: run the host's own dispatcher ---------------------
    // Everything above hand-rolls the calling convention from a reading of the
    // listing, and a mistake in that reading is invisible here -- which is how
    // the A-flag bug survived six builds and why r6 is still the FX1 block.
    //
    // P:0x372 resets x:0x418/0x20a/0x213/0x20b/0x420 and falls into the track
    // loop at P:0x385, which runs four times (x:0x418 steps 0x20 to 0x80) and
    // exits to P:0x53e. Per track it dispatches FX1 then FX2, advancing x:0x20a
    // three times and x:0x213 twice -- exactly the measured 0x6200/0x6500 and
    // 0x4000/0x8000.
    //
    // Each track's config is a 0x20-word block: x:0x416 + t*0x20 is current,
    // x:0x415 + t*0x20 is pending, the FX1 id sits at +$1b and the FX2 id at
    // +$1c as value<<8, and +$1e's bits 8..11 are the effect-change split point.
    // Setting the split to 0 is steady state: the outgoing call is skipped and
    // the effect gets the whole 16-frame block at r0 = 0.
    if (a.dispatch) {
        const TWord pend = mem.get(MemArea_X, 0x415);
        const TWord curr = mem.get(MemArea_X, 0x416);
        std::printf("dispatch mode: pending blocks at X:0x%05x, current at X:0x%05x\n",
                    pend, curr);
        // -split models the moment the effect is ADDED to the LAST enabled track,
        // which is the only thing the hardware has ever been observed to die on.
        // That track's CURRENT id stays the old effect and its PENDING id becomes
        // ours, so the dispatcher runs the outgoing effect over [0, split), calls
        // our init because the ids differ, then calls US over [split, 16) at
        // r0 = split*2. Steady state (split 0) never exercises any of that.
        for (int t = 0; t < 4; ++t) {
            const bool on = t < a.fx2tracks;
            const bool incoming = on && a.split && (t == a.fx2tracks - 1);
            if (on) {
                mem.set(MemArea_X, pend + t * 0x20 + 0x1c, a.fxid << 8);
                mem.set(MemArea_X, curr + t * 0x20 + 0x1c,
                        (incoming ? a.prevfx : a.fxid) << 8);
            }
            const TWord sp = incoming ? (static_cast<TWord>(a.split) & 0xf) << 8 : 0;
            mem.set(MemArea_X, pend + t * 0x20 + 0x1e, sp);
            mem.set(MemArea_X, curr + t * 0x20 + 0x1e, sp);
            if (on)
                std::printf("  track %d: FX2 pending 0x%02x, current 0x%02x, split %d%s\n",
                            t, a.fxid, incoming ? a.prevfx : a.fxid,
                            incoming ? a.split : 0, incoming ? "   <- BEING ADDED" : "");
        }
        for (int b = 0; b < a.blocks; ++b) {
            dsp.setPC(0x372);
            bool ok = false;
            std::vector<TWord> recent;
            for (uint32_t i = 0; i < 400000; ++i) {
                const TWord pc = dsp.getPC().toWord();
                if (pc == 0x53e) { ok = true; break; }
                if (b == 0 && a.trace) {
                    recent.push_back(pc);
                    if (recent.size() > 40) recent.erase(recent.begin());
                }
                dsp.execInterpreter();
            }
            if (!ok && a.trace && !recent.empty()) {
                std::printf("  last 40 PCs: ");
                for (TWord q : recent) std::printf("%05x ", q);
                std::printf("\n");
            }
            if (!ok) {
                std::printf("\nHANG in the dispatcher: block %d, pc=0x%06x\n",
                            b, dsp.getPC().toWord());
                std::printf("  r0=%06x r1=%06x r2=%06x r3=%06x r4=%06x r5=%06x r6=%06x r7=%06x\n",
                            dsp.regs().r[0].var, dsp.regs().r[1].var, dsp.regs().r[2].var,
                            dsp.regs().r[3].var, dsp.regs().r[4].var, dsp.regs().r[5].var,
                            dsp.regs().r[6].var, dsp.regs().r[7].var);
                std::printf("  m0=%06x m1=%06x m2=%06x m3=%06x m4=%06x m5=%06x n7=%06x\n",
                            dsp.regs().m[0].var, dsp.regs().m[1].var, dsp.regs().m[2].var,
                            dsp.regs().m[3].var, dsp.regs().m[4].var, dsp.regs().m[5].var,
                            dsp.regs().n[7].var);
                std::printf("  x:0x20a=%06x x:0x213=%06x x:0x418=%06x\n",
                            mem.get(MemArea_X, 0x20a), mem.get(MemArea_X, 0x213),
                            mem.get(MemArea_X, 0x418));
                return 1;
            }
            if (guard.armed) {
                int cl = 0; char who[24]; std::snprintf(who, sizeof who, "dispatch");
                inst[0].violations += guard.check(mem, 0x4000, 0x4000 + a.guardWords,
                                                  who, "blk", b, b > 2, cl);
                inst[0].clobbers += cl;
            }
        }
        std::printf("dispatcher completed %d blocks with %d FX2 track(s) on effect 0x%02x\n",
                    a.blocks, a.fx2tracks, a.fxid);
        if (guard.armed)
            std::printf("  %ld stray regions, %ld CLOBBERING a loaded module\n",
                        inst[0].violations, inst[0].clobbers);
        return inst[0].clobbers ? 3 : 0;
    }

    size_t inPos = 0;
    for (int b = 0; b < a.blocks; ++b) {
        // fill every instance's block: impulse on the first frame unless an
        // input file is given. All instances see the same audio.
        for (int f = 0; f < a.frames; ++f) {
            int32_t s = 0;
            if (!input.empty()) s = inPos < input.size() ? input[inPos++] : 0;
            else if (b == 0 && f == 0) s = 0x400000;             // 0.5 full scale
            for (int k = 0; k < a.inst; ++k) {
                dsp.memWrite(MemArea_X, inst[k].audio + f * 2 + 0, s & 0xffffff);
                dsp.memWrite(MemArea_X, inst[k].audio + f * 2 + 1, s & 0xffffff);
            }
        }
        if (a.spray && b == 0) {
            // excite every candidate input word: if the effect reads audio from
            // anywhere in the low X region, this will find it
            for (TWord ad = 0; ad < static_cast<TWord>(a.spray); ++ad)
                dsp.memWrite(MemArea_X, ad, 0x400000);
        }
        if (a.pingpong >= 0) mem.set(MemArea_X, 0x41f, static_cast<TWord>(a.pingpong));

        for (int k = 0; k < a.inst; ++k) {
            Instance& I = inst[k];
            if (a.allocProc == "perinst") setAlloc(I.alloc);
            setParams(I.pv);
            dsp.regs().r[0].var = I.audio;
            dsp.regs().r[6].var = pblock;
            dsp.regs().r[7].var = I.state;
            dsp.regs().n[7].var = cnt;

            std::vector<TWord> snap;
            const TWord DIFF_LO = 0x000, DIFF_HI = 0x8000;
            if (a.diff && b == a.diff - 1 && k == 0) {
                snap.resize(DIFF_HI - DIFF_LO);
                for (TWord ad = DIFF_LO; ad < DIFF_HI; ++ad) snap[ad - DIFF_LO] = mem.get(MemArea_X, ad);
            }

            // The dispatcher's two calls per block (P:0x4b8..0x4d7, read from
            // the listing): when the track's SPLIT is nonzero it first calls
            // with a = 0, r0 = 0, n7 = split -- the FIRST SUB-BLOCK, frames
            // [0,split) of the same buffer -- then always calls with a = 1,
            // r0 = split*2, n7 = 16-split for [split,16). At split = 0 the
            // first call is skipped and the a=1 call gets the whole block.
            // Every trig sets the split to its landing offset inside the
            // block and it persists until the next trig.
            //
            // -split N models the post-trig steady state: the block's frames
            // are tiled across the two calls. WITHOUT -split the a=0 call is
            // SKIPPED, because that is what the hardware does at split = 0.
            //
            // It used to be made anyway, at r0 = 0 with n7 = cnt, to model what
            // an a=0-rts effect sees. That is now a trap: since v57 the reverb
            // runs its body on BOTH calls, so the harness was executing the
            // whole engine against r0 = 0 — which on hardware IS the audio
            // buffer, but here is unrelated low X memory. The engine read that
            // as input and fed it to the tank every block, so the reverb never
            // decayed and looked self-oscillating for hours of investigation,
            // while the hardware decayed perfectly. Model the dispatcher, not a
            // historical special case.
            char who[32]; std::snprintf(who, sizeof who, "inst %d", k);
            const int sp = (a.split > 0 && a.split < a.frames) ? a.split : 0;
            if (!a.noctl && sp) {
                dsp.regs().r[0].var = sp ? I.audio : 0;
                dsp.regs().a.var = 0;
                dsp.regs().n[7].var = sp ? sp : cnt;
                char cw[40]; std::snprintf(cw, sizeof cw, "inst %d ctl", k);
                if (!runToRts(dsp, a.proc, 0, cw)) {
                    std::printf("\nHANG in the a=0 call: instance %d, block %d\n", k, b);
                    return 1;
                }
                dsp.regs().r[6].var = pblock;
                dsp.regs().r[7].var = I.state;
            }
            dsp.regs().r[0].var = I.audio + 2 * sp;
            dsp.regs().n[7].var = cnt - sp;
            // The dispatcher raises the flag with `move #$1,a`, and a short
            // immediate to an accumulator is LEFT-ALIGNED: a1 = $010000, not
            // a0 = 1. The distinction is invisible to `tst a` (both are
            // nonzero) but not to `move a,x:..`, which transfers A1 -- an
            // effect that stores the flag and tests the copy reads 0 here if
            // the harness sets the raw var. stageprobe4's audio stage was
            // silently gated off by exactly this.
            dsp.regs().a.var = 0x010000000000ULL;
            if (!runToRts(dsp, a.proc, (b == 0 && k == 0) ? a.trace : 0, who)) {
                std::printf("\nHANG: instance %d, block %d, pc=0x%06x\n", k, b,
                            dsp.getPC().toWord());
                std::printf("  r0=%06x r1=%06x r2=%06x r3=%06x r4=%06x r5=%06x r6=%06x r7=%06x\n",
                            dsp.regs().r[0].var, dsp.regs().r[1].var, dsp.regs().r[2].var,
                            dsp.regs().r[3].var, dsp.regs().r[4].var, dsp.regs().r[5].var,
                            dsp.regs().r[6].var, dsp.regs().r[7].var);
                std::printf("  m0=%06x m1=%06x m2=%06x m3=%06x m4=%06x m5=%06x\n",
                            dsp.regs().m[0].var, dsp.regs().m[1].var, dsp.regs().m[2].var,
                            dsp.regs().m[3].var, dsp.regs().m[4].var, dsp.regs().m[5].var);
                return 1;
            }

            I.cycles += g_lastCycles; ++I.procCalls;
            if (guard.armed) {
                int cl = 0;
                I.violations += guard.check(mem, I.base, I.base + a.guardWords, who,
                                            "proc", b, I.violations + I.clobbers > 12, cl);
                I.clobbers += cl;
            }

            if (a.diff && b == a.diff - 1 && k == 0) {
                std::printf("X writes during block %d (impulse block):\n", b);
                int n = 0; TWord runLo = 0; bool inRun = false;
                for (TWord ad = DIFF_LO; ad < DIFF_HI; ++ad) {
                    const bool ch = mem.get(MemArea_X, ad) != snap[ad - DIFF_LO];
                    if (ch && !inRun) { runLo = ad; inRun = true; }
                    if (!ch && inRun) {
                        if (n < 40) std::printf("   X:0x%05x..0x%05x  (%u words)\n", runLo, ad - 1, ad - runLo);
                        ++n; inRun = false;
                    }
                }
                if (inRun) std::printf("   X:0x%05x..0x%05x\n", runLo, DIFF_HI - 1);
                std::printf("   %d changed regions total\n", n);
            }

            if (getenv("DSP_DBG") && k == 0 && b < atoi(getenv("DSP_DBG")))
                std::printf("  dbg blk %3d: $82=%06x $83=%06x $3e=%06x $30=%06x n5=%06x\n", b,
                            mem.get(MemArea_X, I.state + 0x82),
                            mem.get(MemArea_X, I.state + 0x83),
                            mem.get(MemArea_X, I.state + 0x3e),
                            mem.get(MemArea_X, I.state + 0x30),
                            dsp.regs().n[5].var);

            for (int f = 0; f < a.frames; ++f) {
                for (int c = 0; c < 2; ++c) {
                    TWord w = mem.get(MemArea_X, I.audio + f * 2 + c);
                    int32_t s = static_cast<int32_t>(w << 8) >> 8;   // sign-extend 24 -> 32
                    if (s) ++I.nonzero;
                    if (I.out.is_open()) I.out.write(reinterpret_cast<char*>(&s), 4);
                }
            }
        }

        if (a.spray) {
            TWord acc = 0;
            for (TWord ad = 0xa0; ad <= 0xa1; ++ad) acc |= mem.get(MemArea_X, ad);
            for (TWord ad = 0x130; ad <= 0x133; ++ad) acc |= mem.get(MemArea_X, ad);
            if (acc && (b % 40 == 0 || b < 6))
                std::printf("  block %4d: X:0xa0=%06x %06x  X:0x130=%06x %06x %06x %06x\n", b,
                            mem.get(MemArea_X,0xa0), mem.get(MemArea_X,0xa1),
                            mem.get(MemArea_X,0x130), mem.get(MemArea_X,0x131),
                            mem.get(MemArea_X,0x132), mem.get(MemArea_X,0x133));
        }
    }

    // where did anything actually land? scan the low X region for non-zero words
    std::printf("non-zero X words in 0x000..0x0ff after the run:\n");
    int shown = 0;
    for (TWord ad = 0; ad < 0x100; ++ad) {
        TWord w = mem.get(MemArea_X, ad);
        if (w && shown < 24) { std::printf("   X:0x%03x = 0x%06x\n", ad, w); ++shown; }
    }
    if (!shown) std::printf("   (none)\n");

    if (!a.peekY.empty()) {
        std::printf("peek Y memory after the run:\n");
        for (TWord ad : a.peekY)
            std::printf("   Y:0x%05x = 0x%06x\n", ad, mem.get(MemArea_Y, ad));
    }
    if (!a.peekX.empty()) {
        std::printf("peek X memory after the run:\n");
        for (TWord ad : a.peekX)
            std::printf("   X:0x%05x = 0x%06x\n", ad, mem.get(MemArea_X, ad));
    }

    std::printf("ran %d blocks x %d frames on %d instance(s)\n", a.blocks, a.frames, a.inst);
    long total = 0, bad = 0;
    for (int k = 0; k < a.inst; ++k) {
        std::printf("  instance %d: %.1f instructions/sample (%ld calls)\n", k,
                    inst[k].procCalls ? double(inst[k].cycles) / inst[k].procCalls / a.frames : 0.0,
                    inst[k].procCalls);
        std::printf("  instance %d: %ld non-zero output samples", k, inst[k].nonzero);
        if (guard.armed)
            std::printf(", %ld stray write regions, %ld CLOBBERING a loaded module",
                        inst[k].violations, inst[k].clobbers);
        std::printf("\n");
        total += inst[k].nonzero; bad += inst[k].clobbers;
    }
    if (!total) std::printf("  (all silent -- the effect produced nothing)\n");
    if (guard.armed && !bad)
        std::printf("  guard clean: nothing written over a loaded module\n");
    return bad ? 3 : 0;
}
