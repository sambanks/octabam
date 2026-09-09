// Host-side test harness for the Octatrack's DSP56300 effect algorithms.
//
// The point of this is to make DSP work debuggable. Without it the loop is
// assemble -> repack -> flash -> listen, which is hopeless for tuning something
// like a reverb. With it we can run an effect on the desktop, feed it audio and
// write a WAV.
//
// It uses the emulator from the same project that gave us the disassembler
// (dsp56kEmu, built for the Access Virus), loads a payload's full memory image
// via tools/build/dsp_modmap.py --dumpmem, and calls an effect through the ABI we
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
//     track 2 FX1 -> alloc 2 (Y:0x1c00)              r7 = 0x6400   <- 8 Sep 2026: 0x6400, NOT 0x6300
//     track 2 FX2 -> alloc 3 (Y:0x8000)              r7 = 0x6500   <- 8 Sep 2026: 0x6500, NOT 0x6400
// ⚠️ r7 is 0x6100 + 0x300*pos + 0x100*(fx-1), THREE blocks per track: the
// stock dispatcher bumps its r7 counter after FX1 (P:0x4ae), after FX2
// (P:0x4e4) and a third time, unconditionally, after FX2 (P:0x51e). Measured
// 8 Sep 2026 on BOTH payloads with the firmware driving the DSP through the
// ColdFire port (COLDFIRE_PORT.md O11). The two-per-track table this comment
// carried (r7probe's "track 2 FX2 = 0x6400" reads as position 1's FX1 under
// the real stride) put every position >= 1 low, and the one-aux return's pin
// on position 3 matched only in this harness -- never on the unit. Callers
// (rig_render, verify_onebus, send_probe) pass -r7 1 + 3*pos + (fx-1).
//
// so FX2 instance k defaults to alloc index 1+2k and state block 0x6000+(2+2k).
//
// TWO CORES (7 Sep 2026)
//
// The DSP56721 is two cores sharing Y:0x30000-0x3FFFF, and the shipping image
// is SPECIALIZED: BusVerb exists only in payload A (core 0, tracks 5-8) and
// BusDelay only in payload B (core 1, tracks 1-4). Until now the harness booted
// one core, always payload A, so the real image's delay -- and everything that
// crosses the core boundary -- could only be exercised through the DEV hatch,
// which packs all three servers into one payload.
//
// -memB gives core 1 its own image; -core assigns each instance to a core.
// Each core is a complete DSP + memory + peripherals, boots its OWN setup
// routine (found by opcode pattern -- payload B's sits at P:0x17a where A's is
// at P:0x372, the same code relocated), and X/Y 0x30000-0x3FFFF of core 1 are
// REDIRECTED into core 0's arrays (a patch to the vendored Memory class,
// tools/patches/dsp56300.patch) so the shared window really is shared.
//
// Default scheduling is lock-step: core 0 runs its whole block, then core 1.
// That is exactly what one core used to see, so every existing render is
// bit-identical, and it is structurally blind to the cross-core race
// (docs/effects/XBUS.md) just as before. -skew N interleaves instead: core 0 runs N
// instructions ahead, then the two alternate instruction by instruction. That
// is not the hardware's timing -- it is a FUZZ of it. A green run proves
// nothing; a red one is a real defect.
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
//     -memB FILE            payload B's dump: boots core 1 (tracks 1-4)
//     -audioidx a,b,..      audio BUFFER per instance (default: its own, k).
//                           Two instances with the same index on one core
//                           share a buffer and run in instance order -- an
//                           FX1 insert followed by the same track's FX2. The
//                           first owner receives the input, the last owner's
//                           result is captured.
//     -core a,b,..          which core runs each instance (0 = payload A,
//                           1 = payload B; default 0). Positions on a core
//                           are counted per core, so the k-th instance on a
//                           core defaults to that core's alloc 1+2k / r7 2+2k.
//     -skew N               interleave the cores instruction by instruction,
//                           core 0 N instructions ahead (negative: behind).
//                           Without it the cores run lock-step, core 0 first.
//     -meter FILE           per-block instruction counts per core, one line
//                           per block: "block c0 c1". The block maximum is
//                           printed at the end either way.
//     -ctx lo,hi,exit       override the detected setup routine / dispatcher
//                           exit (hex) -- applies to core 0; -ctxB to core 1
//     -share lo,hi          the shared window (hex, default 30000,40000)
//     -init a[,b..]         entry points, hex, one per instance. A single value
//     -proc a[,b..]         runs the SAME effect on every instance (the original
//                           behaviour); a LIST runs a different effect per
//                           instance, which is the only way to put a real SEND
//                           and a real SERVER in one session and actually
//                           exercise the shared bus end to end.
//     -inmask BITS          which instances receive the input audio (default all).
//                           -inmask 2 feeds instance 1 only, so instance 0's
//                           output is purely what came in over the bus.
//     -inst N               number of instances to run (default 1)
//     -alloc a,b,..         allocator table index per instance (default 1,3,5,..)
//     -r7 a,b,..            state block index per instance (default 2,4,6,..)
//     -allocproc MODE       what X:0x213 holds during proc, not init:
//                             perinst (default) this instance's entry
//                             end             left past the last instance
//                             keep            never rewritten after the inits
//     -tempo BPM            publish tempo24 / clocks Q12.4 at r6+$6/$7 (the cave)
//     -params a,b,...       parameter values 0..127 (default 64); 6 fills page 1,
//                           8 also covers the page-2 slots. Repeat the option to
//                           give successive instances different values.
//     -split N[,M..]        a=0 sub-block call of N frames, then a=1 for the rest.
//                           A LIST gives each instance its OWN split, which is what
//                           hardware does -- tracks trig independently.
//                           (the post-trig state). Omitted = split 0, where the
//                           a=0 call is SKIPPED -- what the dispatcher does.
//     -guard [words]        police buffer bounds (default window 0x3800 words)
//     -frames N             frames per block (default 32)
//     -blocks N             blocks to run (default 256)
//     -in file.raw          24-bit mono raw input, else an impulse is used.
//                           A LIST gives each instance its own file; "-" is
//                           silence. (-inmask still gates it.)
//     -out file.raw         write instance 0; others go to file.raw.i1, .i2, ...
//     -track a,b,..         r7-relative X words (hex) dumped EVERY block, so a
//                           rate can be MEASURED by differencing -- -peekx only
//                           snapshots once, after the run
//     -trackout FILE        where -track writes (default /tmp/dsp_track.txt)
//     -trace N              log the first N instructions executed
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <memory>
#include <string>
#include <vector>
#include <fstream>
#include <iostream>
#include <algorithm>

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
    std::string mem, memB, out;
    std::vector<std::string> in;               // one per instance, or one for all
    TWord init = 0, proc = 0, audio = 0x000080, params = 0x000100, state = 0x010000;
    int frames = 32, blocks = 256, trace = 0, diff = 0, spray = 0;
    TWord flags = 0; int pingpong = -1;
    int inst = 1; TWord dirty = 0; bool noctl = false;
    bool dispatch = false; int fx2tracks = 0; TWord fxid = 0x16;
    int split = 0; TWord prevfx = 0;
    std::vector<int> splitList;            // split per instance
    std::vector<int> allocIdx, r7Idx, coreIdx, audioIdx;
    std::vector<TWord> initList, procList;     // entry points, one per instance
    unsigned inmask = ~0u;                     // which instances get the input
    std::vector<std::vector<int>> pv;          // one parameter set per instance
    std::string allocProc = "perinst";
    bool guard = false; TWord guardWords = 0x3800;
    std::vector<TWord> peekY, peekX;
    std::string dumpyFile; TWord dumpyLo = 0, dumpyHi = 0;
    std::vector<TWord> track;              // r7-relative X words, dumped EVERY block
    std::string trackOut;
    std::vector<std::pair<TWord, TWord>> pokeY;
    double tempo = 0;                      // -tempo BPM: publish r6+$6/$7 like the ColdFire cave
    long skew = 0; bool interleave = false;
    std::string meterFile;
    std::vector<TWord> ctx, ctxB;          // lo,hi,exit overrides
    TWord shareLo = 0x30000, shareHi = 0x40000;
};

// Everything the dispatcher would set up for one effect instance.
struct Instance {
    int   core  = 0;        // which DSP runs it
    int   pos   = 0;        // its position on that core (0 = the housekeeper)
    TWord alloc = 0;        // X address of its entry in the base table
    TWord base  = 0;        // Y base that entry holds
    TWord state = 0;        // r7
    TWord audio = 0;        // r0
    bool  fills = true;     // first owner of its audio buffer: receives the input
    bool  captures = true;  // last owner: its result is the track's output
    TWord init  = 0;        // this instance's entry points -- per-instance so a
    TWord proc  = 0;        // SEND and a SERVER can run in the same session
    bool  fed   = true;     // does this instance receive the input audio?
    int   split = 0;        // ITS OWN split -- every track trigs
                            // independently on hardware, so two tracks
                            // sharing the bus can be running different
                            // splits, and the bus frame offset is
                            // per-track (XBUS.md). One split for all
                            // instances cannot model that at all.
    std::vector<int> pv;
    std::ofstream out;
    std::vector<int32_t> input; size_t inPos = 0; bool hasInput = false;
    long nonzero = 0;
    long violations = 0;
    long clobbers = 0;
    long cycles = 0;
    long procCalls = 0;
};

// The frame-context addresses that differ between the two payloads: the setup
// routine the harness runs to derive the control words, the track loop it
// falls into, and where the dispatcher exits. Payload A's were read from the
// listing (P:0x372..0x39e, loop 0x385, exit 0x53e); payload B's are the same
// code relocated (P:0x17a..0x1a3, loop 0x18b, exit 0x333; measured 7 Sep 2026
// by matching the opcode sequence). Detected by pattern so a re-linked payload
// cannot silently run the wrong range -- which is what "cannot boot payload B"
// was for a year.
struct Ctx {
    TWord setupLo = 0, setupHi = 0, loop = 0, exit = 0;
    bool ok() const { return setupLo && setupHi && exit; }
};

// A shadow of the memory an effect must not touch. Y is only real up to 0xC000
// (measured with dsp/ymemprobe.asm); P is checked over the loaded image so a
// stray write into code shows up as itself rather than as a hang later.
struct Guard {
    static const TWord Y_HI = 0xC000;
    static const TWord P_HI = 0x20000;
    std::vector<TWord> y, p;
    bool armed = false;
    const std::vector<bool>* loadedY = nullptr;
    const std::vector<bool>* loadedP = nullptr;

    void arm(Memory& mem, const std::vector<bool>& ly, const std::vector<bool>& lp) {
        y.resize(Y_HI); p.resize(P_HI);
        loadedY = &ly; loadedP = &lp;
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
                if ((*loadedY)[ad]) runClob = true;
            } else flush(ad, "Y");
        }
        flush(Y_HI, "Y");
        for (TWord ad = 0; ad < P_HI; ++ad) {
            const TWord v = mem.get(MemArea_P, ad);
            if (v != p[ad]) {
                p[ad] = v;
                if (!inRun) { runLo = ad; inRun = true; }
                if ((*loadedP)[ad]) runClob = true;
            } else flush(ad, "P");
        }
        flush(P_HI, "P");
        return stray;
    }
};

// One DSP core: its own memory image, peripherals, frame context and guard.
struct Core {
    int id = 0;
    std::string path;
    AllowAll validator;
    std::unique_ptr<Memory> mem;
    std::unique_ptr<Peripherals56362> periphX;
    std::unique_ptr<Peripherals56367> periphY;
    std::unique_ptr<DSP> dsp;
    std::vector<bool> loadedY, loadedP;   // which words a loaded module occupies
    Ctx ctx;
    TWord pblock = 0, stateBase = 0, cnt = 0, ctlA = 0, ctlB = 0;
    Guard guard;
    std::vector<int> insts;               // global instance indices, dispatch order
    // the meter: instructions per block on this core
    long blockInstr = 0, maxBlockInstr = 0; int maxBlock = -1;
    long initInstr = 0;
    std::vector<long> meter;
};

// Which Y and P words a loaded module occupies. Writing over one of these is
// the bug that made the reverb hang on two tracks: the base stash was placed in
// a window that is free in payload A but holds a live 128-word coefficient table
// in payload B, so the effect corrupted another algorithm and then read that
// algorithm's data back as its own buffer base.
bool loadMem(Core& c, int& modules, long& words) {
    std::ifstream f(c.path, std::ios::binary);
    if (!f.is_open()) { std::cerr << "cannot open " << c.path << "\n"; return false; }
    modules = 0; words = 0;
    c.loadedY.assign(0xC000, false);
    c.loadedP.assign(0x20000, false);
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
                c.dsp->memWriteP(ad, w & 0xffffff);
                if (ad < c.loadedP.size()) c.loadedP[ad] = true;
            } else if (sp == 1) {
                c.dsp->memWrite(MemArea_X, ad, w & 0xffffff);
            } else {
                c.dsp->memWrite(MemArea_Y, ad, w & 0xffffff);
                if (ad < c.loadedY.size()) c.loadedY[ad] = true;
            }
        }
        ++modules; words += cnt;
    }
    return true;
}

// Find the frame-context setup routine and the dispatcher exit by opcode
// pattern. The anchor is `move #>$6000,x0 / move x0,x:>$20a` (44f400 006000
// 447000 00020a): the state-base seed no other code writes. The routine
// starts at the `move #$0,x0` (240000) that precedes the run of two-word
// `move x0,x:>$nnn` stores before it, and its last store is
// `move a,x:>$20e` (567000 00020e). The exit is the `move x:>$415,a`
// (56f000 000415) that follows the loop's `bne` (0d1042 ffxxxx).
Ctx detectCtx(Memory& mem) {
    Ctx c;
    auto P = [&](TWord a) { return mem.get(MemArea_P, a); };
    for (TWord a = 0; a + 4 < 0x2000; ++a) {
        if (P(a) == 0x44f400 && P(a + 1) == 0x006000 && P(a + 2) == 0x447000 && P(a + 3) == 0x00020a) {
            TWord s = a;
            while (s >= 2 && P(s - 2) == 0x447000) s -= 2;
            if (s >= 1 && P(s - 1) == 0x240000) c.setupLo = s - 1;
            for (TWord e = a; e < a + 0x40; ++e)
                if (P(e) == 0x567000 && P(e + 1) == 0x00020e) { c.setupHi = e + 1; break; }
            break;
        }
    }
    // The track loop: the first `move x:>$415,r2` (62f000 000415) after the setup start.
    if (c.setupLo)
        for (TWord a = c.setupLo; a < c.setupLo + 0x40; ++a)
            if (P(a) == 0x62f000 && P(a + 1) == 0x000415) { c.loop = a; break; }
    for (TWord a = 0; a + 3 < 0x2000; ++a)
        if (P(a) == 0x0d1042 && (P(a + 1) & 0xff0000) == 0xff0000 &&
            P(a + 2) == 0x56f000 && P(a + 3) == 0x000415) { c.exit = a + 2; break; }
    return c;
}

// Run from _pc until the matching rts pops back past the entry stack depth.
uint32_t g_lastCycles = 0;
const TWord SENTINEL = 0x03f000;   // must be a MAPPED P address -- an
                                   // out-of-range one faults as soon as the
                                   // rts returns to it
bool runToRts(DSP& dsp, TWord pc, int trace, const char* what, uint32_t maxCycles = 50000000) {
    // Call through the emulator's own jsr so the return address is pushed the
    // way the hardware would.
    dsp.setPC(SENTINEL);
    dsp.jsr(pc);
    for (uint32_t i = 0; i < maxCycles; ++i) {
        const TWord cur = dsp.getPC().toWord();
        if (cur == SENTINEL) { g_lastCycles = i; return true; }
        if (trace && static_cast<int>(i) < trace)
            std::printf("  %s %6u  pc=%06x  a=%012llx r5=%06x n5=%06x m5=%06x x1=%06x n7=%06x\n", what, i, cur,
                        static_cast<unsigned long long>(dsp.regs().a.var & 0xffffffffffffull),
                        dsp.regs().r[5].var & 0xffffff, dsp.regs().n[5].var & 0xffffff,
                        dsp.regs().m[5].var & 0xffffff,
                        (unsigned)(dsp.regs().x.var >> 24) & 0xffffff,
                        dsp.regs().n[7].var);
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

void dumpRegs(DSP& dsp, Memory& mem) {
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
}

std::vector<int> parseList(const char* s) {
    std::vector<int> v;
    std::string t(s);
    for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ",")) v.push_back(atoi(p));
    return v;
}

// Same, but hex -- for the entry-point lists, which are quoted in hex
// everywhere else on the command line.
std::vector<TWord> parseHexList(const char* s) {
    std::vector<TWord> v;
    std::string t(s);
    for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ","))
        v.push_back(strtoul(p, nullptr, 16));
    return v;
}

std::vector<std::string> parseStrList(const char* s) {
    std::vector<std::string> v;
    std::string t(s);
    for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ",")) v.push_back(p);
    return v;
}

// One effect call as the dispatcher would make it, resumable one instruction
// at a time so two cores can be interleaved. `begin` sets the registers and
// pushes the return address through the emulator's own jsr, exactly as
// runToRts does; `step` executes one instruction and reports whether the
// sentinel came back.
struct Call {
    int inst = -1;
    bool ctl = false;       // the a=0 sub-block call
    uint32_t steps = 0;
};

} // namespace

int main(int argc, char** argv) {
    Args a;
    for (int i = 1; i < argc; ++i) {
        std::string k = argv[i];
        auto v = [&] { return std::string(argv[++i]); };
        if (k == "-mem") a.mem = v();
        else if (k == "-memB") a.memB = v();
        else if (k == "-init") { a.initList = parseHexList(argv[++i]); a.init = a.initList[0]; }
        else if (k == "-proc") { a.procList = parseHexList(argv[++i]); a.proc = a.procList[0]; }
        else if (k == "-inmask") a.inmask = strtoul(argv[++i], nullptr, 0);
        else if (k == "-audio") a.audio = strtoul(argv[++i], nullptr, 16);
        else if (k == "-pblock") a.params = strtoul(argv[++i], nullptr, 16);
        else if (k == "-tempo") a.tempo = atof(argv[++i]);
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
        else if (k == "-noctl") a.noctl = true;
        else if (k == "-in") a.in = parseStrList(argv[++i]);
        else if (k == "-out") a.out = v();
        else if (k == "-dispatch") a.fx2tracks = atoi(argv[++i]), a.dispatch = true;
        else if (k == "-fxid") a.fxid = strtoul(argv[++i], nullptr, 16);
        else if (k == "-split") { a.splitList = parseList(argv[++i]);
                                  a.split = a.splitList.empty() ? 0 : a.splitList[0]; }
        else if (k == "-prevfx") a.prevfx = strtoul(argv[++i], nullptr, 16);
        else if (k == "-alloc") a.allocIdx = parseList(argv[++i]);
        else if (k == "-r7") a.r7Idx = parseList(argv[++i]);
        else if (k == "-core") a.coreIdx = parseList(argv[++i]);
        else if (k == "-audioidx") a.audioIdx = parseList(argv[++i]);
        else if (k == "-skew") { a.skew = atol(argv[++i]); a.interleave = true; }
        else if (k == "-meter") a.meterFile = v();
        else if (k == "-ctx") a.ctx = parseHexList(argv[++i]);
        else if (k == "-ctxB") a.ctxB = parseHexList(argv[++i]);
        else if (k == "-share") { auto s = parseHexList(argv[++i]);
                                  if (s.size() == 2) { a.shareLo = s[0]; a.shareHi = s[1]; } }
        else if (k == "-allocproc") a.allocProc = v();
        else if (k == "-params") {
            auto p = parseList(argv[++i]);
            std::vector<int> pv(8, 64);
            for (size_t j = 0; j < p.size() && j < 12; ++j) {
                if (j >= pv.size()) pv.resize(j + 1, 0);
                pv[j] = p[j];
            }
            a.pv.push_back(pv);
        }
        else if (k == "-guard") {
            a.guard = true;
            if (i + 1 < argc && argv[i + 1][0] != '-')
                a.guardWords = strtoul(argv[++i], nullptr, 0);
        }
        else if (k == "-peeky") {
            std::string t(argv[++i]);
            for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ","))
                a.peekY.push_back(strtoul(p, nullptr, 16));
        }
        else if (k == "-track") a.track = parseHexList(argv[++i]);
        else if (k == "-trackout") a.trackOut = v();
        else if (k == "-peekx") {
            std::string t(argv[++i]);
            for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ","))
                a.peekX.push_back(strtoul(p, nullptr, 16));
        }
        else if (k == "-dumpy") {
            std::string t(argv[++i]);
            char* p = strtok(&t[0], ",");
            a.dumpyLo = strtoul(p, nullptr, 16);
            a.dumpyHi = strtoul(strtok(nullptr, ","), nullptr, 16);
            a.dumpyFile = strtok(nullptr, ",");
        }
        else if (k == "-pokey") {
            std::string t(argv[++i]);
            for (char* p = strtok(&t[0], ","); p; p = strtok(nullptr, ",")) {
                char* eq = strchr(p, '=');
                if (!eq) continue;
                *eq = 0;
                a.pokeY.push_back({static_cast<TWord>(strtoul(p, nullptr, 16)),
                                   static_cast<TWord>(strtoul(eq + 1, nullptr, 16))});
            }
        }
    }
    if (argc > 1 && std::string(argv[argc - 1]) == "-guard") a.guard = true;

    if (a.mem.empty() || !a.proc) {
        std::cerr << "usage: dsp_host -mem <file> -init <hex> -proc <hex> [-params a,b,..]\n"
                     "                [-memB <file>] [-core a,b] [-skew N] [-meter FILE]\n"
                     "                [-inst N] [-alloc a,b] [-r7 a,b] [-allocproc MODE] [-guard]\n"
                     "                [-frames N] [-blocks N] [-in raw[,raw..]] [-out raw] [-trace N]\n";
        return 2;
    }
    if (a.inst < 1) a.inst = 1;
    if (a.pv.empty()) a.pv.push_back(std::vector<int>(8, 64));

    setvbuf(stdout, nullptr, _IONBF, 0);

    // ---- the cores ----------------------------------------------------------
    const int ncores = a.memB.empty() ? 1 : 2;
    std::vector<std::unique_ptr<Core>> cores;
    for (int c = 0; c < ncores; ++c) {
        cores.emplace_back(new Core);
        Core& C = *cores.back();
        C.id = c;
        C.path = c ? a.memB : a.mem;
        std::printf("core %d: constructing DSP ...\n", c);
        C.mem.reset(new Memory(C.validator, 0x080000, 0x800000, 0x200000));   // sizes the library's own tests use
        C.periphX.reset(new Peripherals56362);
        C.periphY.reset(new Peripherals56367);
        C.dsp.reset(new DSP(*C.mem, C.periphX.get(), C.periphY.get()));
        if (c == 1) {
            // Core 1's shared window lives in core 0's arrays. Both X and Y:
            // on the chip P/X/Y all alias there (docs/firmware/CHIP.md), and the
            // emulator keeps each core's X and Y apart exactly as it did
            // before, so a single-core render is unchanged.
            Core& C0 = *cores[0];
            C.mem->setSharedWindow(a.shareLo, a.shareHi,
                                   C0.mem->getMemAreaPtr(MemArea_X) + a.shareLo,
                                   C0.mem->getMemAreaPtr(MemArea_Y) + a.shareLo);
            std::printf("core 1: X/Y 0x%05x..0x%05x shared with core 0\n", a.shareLo, a.shareHi - 1);
        }
        int modules = 0; long words = 0;
        if (!loadMem(C, modules, words)) return 1;
        std::printf("core %d: loaded %d modules, %ld words from %s\n", c, modules, words, C.path.c_str());

        // ---- frame context --------------------------------------------------
        // The effects depend on control words that no module initialises; the
        // DSP's own setup routine derives them from two loaded pointers
        // (x:0x415, x:0x416). Rather than reconstruct that by hand, run it --
        // at whichever address THIS payload keeps it.
        C.ctx = detectCtx(*C.mem);
        const std::vector<TWord>& ov = c ? a.ctxB : a.ctx;
        if (ov.size() == 3) { C.ctx.setupLo = ov[0]; C.ctx.setupHi = ov[1]; C.ctx.exit = ov[2]; }
        if (!C.ctx.ok()) {
            std::printf("core %d: !! could not find the frame-context setup routine in this dump "
                        "(pass -ctx%s lo,hi,exit)\n", c, c ? "B" : "");
            return 1;
        }
        std::printf("core %d: setup P:0x%05x..0x%05x, track loop P:0x%05x, dispatcher exit P:0x%05x\n",
                    c, C.ctx.setupLo, C.ctx.setupHi, C.ctx.loop, C.ctx.exit);
        // It reads the frame count out of x:(x:0x415 + 0x1e) as (w >> 8) & 0xf, so
        // seed that first. The count is capped at 15 frames by the & 0xf.
        // 9 Sep 2026 (COLDFIRE_PORT.md O12): under the firmware that nibble is
        // the track's SPLIT, and 0 means a whole 16-sample block (x:$20c = 0,
        // x:$20d = 16 at every unsplit dispatch, measured with the ColdFire
        // port); the cap at 15 had every harness render processing 15 samples
        // per block where the unit does 16, which is 16/15 on every per-block
        // rate (BusVerb's allpass modulator, any per-block LFO). -frames 16
        // seeds the field as 0 and moves 16 samples per block.
        if (a.frames > 16) { std::printf("frames capped to 16 (a whole block)\n"); a.frames = 16; }
        const TWord blkA = C.mem->get(MemArea_X, 0x415);
        C.mem->set(MemArea_X, blkA + 0x1e, (static_cast<TWord>(a.frames & 0xf) << 8) | a.flags);
        std::printf("core %d: seeded x:0x%05x+0x1e = frames %d\n", c, blkA, a.frames);

        runRange(*C.dsp, C.ctx.setupLo, C.ctx.setupHi);
        if (a.pingpong >= 0) { C.mem->set(MemArea_X, 0x41f, static_cast<TWord>(a.pingpong));
            std::printf("ping-pong selector x:0x41f = %d\n", a.pingpong); }

        C.ctlA = C.mem->get(MemArea_X, 0x419);
        C.ctlB = C.mem->get(MemArea_X, 0x208);
        // The per-block sample count is the a=0 sub-block's (x:$20c) when the
        // frame is split, else the a=1 call's (x:$20d): the stock dispatcher
        // skips the a=0 call at x:$20c == 0 and makes the a=1 call with n7 =
        // x:$20d = 16 (COLDFIRE_PORT.md O12, measured under the firmware).
        // At the legacy -frames 15 this still reads 15, so every existing
        // bit-identity gate is untouched; at -frames 16 it reads 16.
        C.cnt  = C.mem->get(MemArea_X, 0x20c) ? C.mem->get(MemArea_X, 0x20c) : C.mem->get(MemArea_X, 0x20d);
        std::printf("core %d: context: x:0x419=0x%05x  x:0x208=0x%05x  x:0x20c=%u (frames)  "
                    "x:0x20d=%u  x:0x20e=%u\n", c, C.ctlA, C.ctlB, C.cnt,
                    C.mem->get(MemArea_X, 0x20d), C.mem->get(MemArea_X, 0x20e));
        if (!C.cnt) { std::printf("  !! frame count is 0 -- the dispatcher would skip the effect\n"); }
        // The dispatcher hands the routine r6 = x:0x208 + 6 and r7 = a state block.
        C.pblock = C.ctlB + 6;
        C.stateBase = C.mem->get(MemArea_X, 0x20a);
    }
    Core& C0 = *cores[0];
    Memory& mem = *C0.mem;     // core 0's, for the single-core paths below
    DSP& dsp = *C0.dsp;

    // ---- instances --------------------------------------------------------
    // DSP_ALLOC_IDX is kept for the single-instance case that predates -inst.
    const char* ai = getenv("DSP_ALLOC_IDX");

    std::vector<Instance> inst(a.inst);
    for (int k = 0; k < a.inst; ++k) {
        Instance& I = inst[k];
        I.core = (k < static_cast<int>(a.coreIdx.size())) ? a.coreIdx[k] : 0;
        if (I.core < 0 || I.core >= ncores) {
            std::printf("instance %d: core %d does not exist (%s)\n", k, I.core,
                        ncores == 1 ? "pass -memB to boot core 1" : "cores are 0 and 1");
            return 2;
        }
        Core& C = *cores[I.core];
        I.pos = static_cast<int>(C.insts.size());
        C.insts.push_back(k);
        // Defaults count positions PER CORE: the k-th instance on a core is
        // that core's k-th FX2 slot. With one core that is the old k.
        int ia = (k < static_cast<int>(a.allocIdx.size())) ? a.allocIdx[k] : 1 + 2 * I.pos;
        int ir = (k < static_cast<int>(a.r7Idx.size()))    ? a.r7Idx[k]    : 2 + 2 * I.pos;
        if (ai && a.inst == 1 && a.allocIdx.empty()) { ia = strtoul(ai, nullptr, 0); ir = ia; }
        I.alloc = 0x255 + ia;
        I.base  = C.mem->get(MemArea_X, I.alloc);
        I.state = C.stateBase + ir * 0x100;
        const int aidx = (k < static_cast<int>(a.audioIdx.size())) ? a.audioIdx[k] : k;
        I.audio = a.audio + aidx * 0x40;            // 15 frames = 30 words, well clear
        // Buffer ownership on this core: the first instance on a buffer is
        // fed, the last one is captured, the ones between see the previous
        // instance's output -- the FX1 -> FX2 chain of one track.
        for (int j = 0; j < k; ++j)
            if (inst[j].core == I.core && inst[j].audio == I.audio) { I.fills = false; inst[j].captures = false; }
        I.pv    = a.pv[std::min<size_t>(k, a.pv.size() - 1)];
        // Entry points fall back to the LAST list entry, so a single -init/-proc
        // still runs one effect on every instance -- the behaviour every existing
        // caller depends on. A list runs a DIFFERENT effect per instance, which is
        // what a SEND feeding a SERVER needs: the two are separate modules in the
        // same payload, and until now the harness could only ever run one of them.
        I.init  = a.initList.empty() ? a.init
                : a.initList[std::min<size_t>(k, a.initList.size() - 1)];
        I.proc  = a.procList.empty() ? a.proc
                : a.procList[std::min<size_t>(k, a.procList.size() - 1)];
        I.fed   = (a.inmask >> k) & 1;
        I.split = a.splitList.empty() ? a.split
                : a.splitList[std::min<size_t>(k, a.splitList.size() - 1)];
        std::printf("instance %d: core %d pos %d, r7 = X:0x%05x (idx %d), base = Y:0x%05x (X:0x%03x idx %d), "
                    "audio X:0x%05x%s, init P:0x%05x proc P:0x%05x%s\n",
                    k, I.core, I.pos, I.state, ir, I.base, I.alloc, ia, I.audio,
                    I.fills ? "" : " (chained)", I.init, I.proc,
                    I.fed ? "" : "  [no input]");
        std::printf("            params");
        for (int p : I.pv) std::printf(" %d", p);
        std::printf("\n");
        if (!a.out.empty())
            I.out.open(k ? a.out + ".i" + std::to_string(k) : a.out, std::ios::binary);
        // -in: one file for everyone (the old behaviour) or one per instance.
        if (!a.in.empty()) {
            const std::string& f = a.in.size() == 1 ? a.in[0]
                                 : (k < static_cast<int>(a.in.size()) ? a.in[k] : std::string("-"));
            if (f != "-") {
                std::ifstream fi(f, std::ios::binary);
                if (!fi.is_open()) { std::cerr << "cannot open input " << f << "\n"; return 1; }
                int32_t s;
                while (fi.read(reinterpret_cast<char*>(&s), 4)) I.input.push_back(s);
            }
            I.hasInput = true;      // named input, even if "-" (silence, not the impulse)
        }
    }
    // Two instances landing on the same buffer or the same state block ON THE
    // SAME CORE is not a configuration the hardware produces; say so rather
    // than debug the result. (The same addresses on different cores are the
    // normal case -- each core has its own private X and Y.)
    for (int k = 1; k < a.inst; ++k)
        for (int j = 0; j < k; ++j) {
            if (inst[k].core != inst[j].core) continue;
            if (inst[k].base == inst[j].base)
                std::printf("  !! instances %d and %d share base Y:0x%05x\n", j, k, inst[k].base);
            if (inst[k].state == inst[j].state)
                std::printf("  !! instances %d and %d share r7 X:0x%05x\n", j, k, inst[k].state);
        }

    // Page 1 is pblock+0..5. Page 2 is THREE words, each carrying TWO
    // controls -- settled on hardware 17 Aug 2026 (docs/firmware/PARAM_PAGES.md):
    //
    //   slot 6 -> +$c KNOB (bits 16-23)     slot 7  -> +$c COMPANION (bits 8-15)
    //   slot 8 -> +$d KNOB                  slot 9  -> +$d COMPANION
    //   slot 10-> +$e KNOB                  slot 11 -> +$e COMPANION
    //
    // ⚠️ THE OLD MAP HERE WAS WRONG AND IT COST MONTHS. It sent slot 6 to +$b
    // (from dsp/pagemap_probe.asm) and wrote every slot as a KNOB field --
    // which is exactly why the delay's WOW always worked locally and never on
    // hardware, and why no companion select (MODE aside, which had a
    // build-time override) was ever exercisable in the emulator. +$b is not a
    // parameter word at all. The stock-DARK notes that used to live here
    // (its +$c pre-delay read, the +$e `btst #$8` flag) are in the file
    // history; the lesson they carried -- take a slot's MEANING from the
    // effect's own reads -- survives as the map above, which was taken from
    // exactly that.
    //
    // Params 0..5 are page 1; 6..11 follow the table. A companion value is
    // written to bits 8-15 of the SAME word as its slot's knob, so both are
    // composed together rather than the last write clobbering the word.
    auto setParams = [&](Core& C, const std::vector<int>& pv) {
        for (size_t i = 0; i < 6 && i < pv.size(); ++i)
            C.mem->set(MemArea_X, C.pblock + i, (static_cast<TWord>(pv[i]) & 0x7f) << 16);
        for (TWord w = 0; w < 3; ++w) {                    // +$c, +$d, +$e
            const size_t knob = 6 + 2 * w, comp = knob + 1;
            TWord v = 0;
            if (knob < pv.size()) v |= (static_cast<TWord>(pv[knob]) & 0x7f) << 16;
            if (comp < pv.size()) v |= (static_cast<TWord>(pv[comp]) & 0x7f) << 8;
            if (knob < pv.size() || comp < pv.size())
                C.mem->set(MemArea_X, C.pblock + 0xc + w, v);
        }
        // -tempo: what modules/tempo-sync/tempo_cave.s publishes on hardware (24 Aug 2026):
        // r6+$6 = BPM*24, r6+$7 = 42336000/tempo24 = samples per MIDI clock
        // in Q12.4 -- 16-bit halfwords, so <<8 like every published word.
        if (a.tempo > 0) {
            const TWord t24 = static_cast<TWord>(a.tempo * 24 + 0.5);
            const TWord ticks = 42336000u / t24;
            C.mem->set(MemArea_X, C.pblock + 6, (t24 & 0xffff) << 8);
            C.mem->set(MemArea_X, C.pblock + 7, (ticks & 0xffff) << 8);
        }
    };

    // X:0x213 points at an instance's entry in the base table at X:0x255. The
    // stock reverbs read it in INIT, where it is per-instance. Whether it is
    // still per-instance during PROC is the open question -- the dispatcher
    // advances it, so by the time blocks are running it may sit past the last
    // effect. -allocproc chooses which model to run.
    auto setAlloc = [&](Core& C, TWord v) { C.mem->set(MemArea_X, 0x213, v); };

    // Hardware does not hand an effect a zeroed buffer -- it holds whatever the
    // previous algorithm left. The emulator does, which can make a build look
    // fine here and behave differently on the device.
    if (a.dirty) {
        for (auto& Cp : cores) {
            TWord x = a.dirty;
            for (TWord ad = 0x1000; ad < 0xC000; ++ad) {
                x ^= x << 13; x ^= x >> 17; x ^= x << 5; x &= 0xffffff;
                Cp->mem->set(MemArea_Y, ad, x);
            }
        }
        std::printf("Y:0x1000..0xBFFF filled with garbage (seed 0x%x)\n", a.dirty);
    }

    // -pokey addr=val,... : seed arbitrary Y words before any block runs --
    // e.g. planting a fake "last block's bus accumulator" so a server can be
    // tested for whether it actually reads shared bus scratch, without a
    // second instance running the client code that would normally write it.
    for (auto& pv : a.pokeY) {
        mem.set(MemArea_Y, pv.first, pv.second);
        std::printf("poked Y:0x%05x = 0x%06x\n", pv.first, pv.second);
    }

    if (a.guard) {
        for (auto& Cp : cores) Cp->guard.arm(*Cp->mem, Cp->loadedY, Cp->loadedP);
        std::printf("guard armed: Y:0x0000..0x%05x + P:0x00000..0x%05x, "
                    "window %u words per instance\n", Guard::Y_HI - 1, Guard::P_HI - 1,
                    a.guardWords);
    }

    // ---- init, every instance, before any block ---------------------------
    for (int k = 0; k < a.inst; ++k) {
        Core& C = *cores[inst[k].core];
        setAlloc(C, inst[k].alloc);
        setParams(C, inst[k].pv);
        C.dsp->regs().r[6].var = C.pblock;
        C.dsp->regs().r[7].var = inst[k].state;
        if (inst[k].init) {
            std::printf("running init @P:0x%05x for instance %d (core %d) ...\n", inst[k].init, k, inst[k].core);
            const uint64_t i0 = C.dsp->getInstructionCounter();
            if (!runToRts(*C.dsp, inst[k].init, a.trace, "init")) return 1;
            C.initInstr += static_cast<long>(C.dsp->getInstructionCounter() - i0);
            if (C.guard.armed) {
                char who[32]; std::snprintf(who, sizeof who, "inst %d", k);
                int cl = 0;
                inst[k].violations += C.guard.check(*C.mem, inst[k].base,
                                                    inst[k].base + a.guardWords,
                                                    who, "init", 0, false, cl);
                inst[k].clobbers += cl;
            }
        }
    }
    if (a.init) std::printf("all inits returned ok\n");

    for (auto& Cp : cores) {
        Core& C = *Cp;
        if (C.insts.empty()) continue;
        const int last = C.insts.back();
        const TWord allocEnd = 0x255 + (a.allocIdx.empty() ? 1 + 2 * inst[last].pos + 1
                                                           : (last < static_cast<int>(a.allocIdx.size())
                                                              ? a.allocIdx[last] : a.allocIdx.back()) + 1);
        if (a.allocProc == "end") {
            setAlloc(C, allocEnd);
            std::printf("core %d: proc-time X:0x213 = 0x%03x for every instance (past the last effect)\n",
                        C.id, allocEnd);
        } else if (a.allocProc == "keep") {
            std::printf("core %d: proc-time X:0x213 left at 0x%03x from the last init\n",
                        C.id, C.mem->get(MemArea_X, 0x213));
        }
    }

    // ---- FAITHFUL MODE: run the host's own dispatcher (core 0 only) ---------
    // Everything above hand-rolls the calling convention from a reading of the
    // listing, and a mistake in that reading is invisible here -- which is how
    // the A-flag bug survived six builds and why r6 is still the FX1 block.
    //
    // The setup routine resets x:0x418/0x20a/0x213/0x20b/0x420 and falls into
    // the track loop, which runs four times (x:0x418 steps 0x20 to 0x80) and
    // exits to the dispatcher exit. Per track it dispatches FX1 then FX2,
    // advancing x:0x20a three times and x:0x213 twice -- exactly the measured
    // 0x6200/0x6500 and 0x4000/0x8000.
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
        // ---- drain the host transmit FIFO -------------------------------
        // FAITHFUL MODE RUNS THE FIRMWARE'S OWN HOST WRITES, and we model no
        // ColdFire to read them. HDI08's TX ring is 8192 words and BLOCKING:
        // once it fills, `movep a,x:<<M_HTX` parks inside HDI08::writeTX on a
        // condition variable and never returns. It is not a hang in the DSP
        // code and the 400,000-step ceiling below cannot catch it -- the
        // process sits at 0% CPU inside ONE instruction, which is why it
        // reads as a wedge rather than an error. Block 0 fits in the ring;
        // block 1 does not, so `-dispatch` looked broken on every image
        // (reported 2 Sep 2026 with the HELLO WORLD contribution, diagnosed
        // by stack sample). Reading the words back is what the hardware host
        // does, so this is more faithful than blocking, not less.
        // periphX is the 56362, which is the one carrying the HDI08 here;
        // the 56367 (periphY) has only the ESAI.
        //
        // Draining between instructions is NOT enough on its own: the stack
        // sample puts the writes inside DSP::do_exec, a hardware DO loop the
        // emulator runs to completion in ONE execInterpreter() call, so it
        // pushes past 8192 without ever giving the harness a turn. The flag
        // is what actually unblocks it -- with it clear, writeTX overwrites
        // the head and returns instead of calling waitNotFull(). We keep the
        // drain as well so `hasTX()` stays a useful thing to inspect.
        C0.periphX->getHDI08().setTransmitDataAlwaysEmpty(false);
        auto drainHostTX = [&]() {
            auto& h = C0.periphX->getHDI08();
            while (h.hasTX()) h.readTX();
        };
        for (int b = 0; b < a.blocks; ++b) {
            dsp.setPC(C0.ctx.setupLo);
            bool ok = false;
            std::vector<TWord> recent;
            const uint64_t i0 = dsp.getInstructionCounter();
            for (uint32_t i = 0; i < 400000; ++i) {
                const TWord pc = dsp.getPC().toWord();
                if (pc == C0.ctx.exit) { ok = true; break; }
                if (b == 0 && a.trace) {
                    recent.push_back(pc);
                    if (recent.size() > 40) recent.erase(recent.begin());
                }
                // Cheap enough at 1/1024 instructions, and it has to be
                // INSIDE the block: the ring can fill mid-block.
                if ((i & 0x3ff) == 0) drainHostTX();
                dsp.execInterpreter();
            }
            drainHostTX();
            const long n = static_cast<long>(dsp.getInstructionCounter() - i0);
            C0.meter.push_back(n);
            if (n > C0.maxBlockInstr) { C0.maxBlockInstr = n; C0.maxBlock = b; }
            if (!ok && a.trace && !recent.empty()) {
                std::printf("  last 40 PCs: ");
                for (TWord q : recent) std::printf("%05x ", q);
                std::printf("\n");
            }
            if (!ok) {
                std::printf("\nHANG in the dispatcher: block %d, pc=0x%06x\n",
                            b, dsp.getPC().toWord());
                dumpRegs(dsp, mem);
                return 1;
            }
            if (C0.guard.armed) {
                int cl = 0; char who[24]; std::snprintf(who, sizeof who, "dispatch");
                inst[0].violations += C0.guard.check(mem, 0x4000, 0x4000 + a.guardWords,
                                                     who, "blk", b, b > 2, cl);
                inst[0].clobbers += cl;
            }
        }
        std::printf("dispatcher completed %d blocks with %d FX2 track(s) on effect 0x%02x\n",
                    a.blocks, a.fx2tracks, a.fxid);
        std::printf("  meter: max %ld instructions in block %d (%.1f per frame of %d)\n",
                    C0.maxBlockInstr, C0.maxBlock, double(C0.maxBlockInstr) / a.frames, a.frames);
        if (C0.guard.armed)
            std::printf("  %ld stray regions, %ld CLOBBERING a loaded module\n",
                        inst[0].violations, inst[0].clobbers);
        return inst[0].clobbers ? 3 : 0;
    }

    std::ofstream trackFile;
    if (!a.track.empty()) {
        trackFile.open(a.trackOut.empty() ? "/tmp/dsp_track.txt" : a.trackOut);
        std::printf("tracking r7-relative X words every block ->  %s\n",
                    a.trackOut.empty() ? "/tmp/dsp_track.txt" : a.trackOut.c_str());
    }
    std::ofstream meterFile;
    if (!a.meterFile.empty()) meterFile.open(a.meterFile);

    // ---- the block loop -----------------------------------------------------
    // Per core, per block, the dispatcher's calls in order. Each call is made
    // exactly as runToRts made it -- the same register setup, the same jsr
    // through the emulator, the same sentinel -- but resumably, one
    // instruction per step, so the two cores can be interleaved.
    struct CoreRun {
        Core* C = nullptr;
        std::vector<Call> calls; size_t idx = 0;
        bool inCall = false; Call cur; uint64_t i0 = 0;
        int block = 0;
        bool done() const { return idx >= calls.size() && !inCall; }
    };
    std::vector<CoreRun> runs(ncores);
    for (int c = 0; c < ncores; ++c) runs[c].C = cores[c].get();

    const TWord DIFF_LO = 0x000, DIFF_HI = 0x8000;
    std::vector<TWord> snap;
    bool hung = false;

    // Start a call: what the dispatcher does before `jsr (r2)`.
    auto beginCall = [&](CoreRun& R, const Call& call) {
        Core& C = *R.C; Instance& I = inst[call.inst];
        if (a.allocProc == "perinst") setAlloc(C, I.alloc);
        setParams(C, I.pv);
        DSP& D = *C.dsp;
        D.regs().r[6].var = C.pblock;
        D.regs().r[7].var = I.state;
        const int sp = (I.split > 0 && I.split < a.frames) ? I.split : 0;
        if (call.ctl) {
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
            // whole engine against r0 = 0 -- which on hardware IS the audio
            // buffer, but here is unrelated low X memory. The engine read that
            // as input and fed it to the tank every block, so the reverb never
            // decayed and looked self-oscillating for hours of investigation,
            // while the hardware decayed perfectly. Model the dispatcher, not a
            // historical special case.
            D.regs().r[0].var = sp ? I.audio : 0;
            D.regs().a.var = 0;
            D.regs().n[7].var = sp ? sp : C.cnt;
        } else {
            D.regs().r[0].var = I.audio + 2 * sp;
            D.regs().n[7].var = C.cnt - sp;
            // The dispatcher raises the flag with `move #$1,a`, and a short
            // immediate to an accumulator is LEFT-ALIGNED: a1 = $010000, not
            // a0 = 1. The distinction is invisible to `tst a` (both are
            // nonzero) but not to `move a,x:..`, which transfers A1 -- an
            // effect that stores the flag and tests the copy reads 0 here if
            // the harness sets the raw var. stageprobe4's audio stage was
            // silently gated off by exactly this.
            D.regs().a.var = 0x010000000000ULL;
        }
        D.setPC(SENTINEL);
        D.jsr(I.proc);
        R.cur = call; R.cur.steps = 0; R.inCall = true;
        R.i0 = D.getInstructionCounter();
    };

    // Finish a call: what the harness does after the rts.
    auto endCall = [&](CoreRun& R) {
        Core& C = *R.C; Instance& I = inst[R.cur.inst]; DSP& D = *C.dsp;
        const int k = R.cur.inst, b = R.block;
        char who[32]; std::snprintf(who, sizeof who, "inst %d", k);
        R.inCall = false;
        if (R.cur.ctl) {
            // the a=0 call: nothing captured, the a=1 call follows
            return;
        }
        // -track: sample r7-relative state EVERY block. -peekx only snapshots
        // after the whole run, which cannot measure a RATE -- an LFO phase has
        // to be differenced block to block to get its increment.
        if (!a.track.empty() && k == 0) {
            if (trackFile.is_open()) {
                trackFile << b;
                for (TWord off : a.track)
                    trackFile << ' ' << C.mem->get(MemArea_X, I.state + off);
                trackFile << '\n';
            }
        }
        I.cycles += R.cur.steps; ++I.procCalls;
        if (C.guard.armed) {
            int cl = 0;
            I.violations += C.guard.check(*C.mem, I.base, I.base + a.guardWords, who,
                                          "proc", b, I.violations + I.clobbers > 12, cl);
            I.clobbers += cl;
        }
        if (a.diff && b == a.diff - 1 && k == 0) {
            std::printf("X writes during block %d (impulse block):\n", b);
            int n = 0; TWord runLo = 0; bool inRun = false;
            for (TWord ad = DIFF_LO; ad < DIFF_HI; ++ad) {
                const bool ch = C.mem->get(MemArea_X, ad) != snap[ad - DIFF_LO];
                if (ch && !inRun) { runLo = ad; inRun = true; }
                if (!ch && inRun) {
                    if (n < 40) std::printf("   X:0x%05x..0x%05x  (%u words)\n", runLo, ad - 1, ad - runLo);
                    ++n; inRun = false;
                }
            }
            if (inRun) std::printf("   X:0x%05x..0x%05x\n", runLo, DIFF_HI - 1);
            std::printf("   %d changed regions total\n", n);
            // values of every changed word (capped), so two runs can be
            // value-diffed, not just region-diffed
            int nv = 0;
            for (TWord ad = DIFF_LO; ad < DIFF_HI && nv < 400; ++ad) {
                if (C.mem->get(MemArea_X, ad) != snap[ad - DIFF_LO]) {
                    std::printf("   XVAL 0x%05x = 0x%06x\n", ad, C.mem->get(MemArea_X, ad));
                    ++nv;
                }
            }
        }
        if (getenv("DSP_DBG") && k == 0 && b < atoi(getenv("DSP_DBG")))
            std::printf("  dbg blk %3d: $82=%06x $83=%06x $3e=%06x $30=%06x n5=%06x\n", b,
                        C.mem->get(MemArea_X, I.state + 0x82),
                        C.mem->get(MemArea_X, I.state + 0x83),
                        C.mem->get(MemArea_X, I.state + 0x3e),
                        C.mem->get(MemArea_X, I.state + 0x30),
                        D.regs().n[5].var);
        if (!I.captures) return;                 // the next instance on this buffer finishes the track
        for (int f = 0; f < a.frames; ++f) {
            for (int ch = 0; ch < 2; ++ch) {
                TWord w = C.mem->get(MemArea_X, I.audio + f * 2 + ch);
                int32_t s = static_cast<int32_t>(w << 8) >> 8;   // sign-extend 24 -> 32
                if (s) ++I.nonzero;
                if (I.out.is_open()) I.out.write(reinterpret_cast<char*>(&s), 4);
            }
        }
    };

    // One instruction on a core. Returns false on a hang.
    auto stepCore = [&](CoreRun& R) -> bool {
        if (R.done()) return true;
        if (!R.inCall) beginCall(R, R.calls[R.idx++]);
        Core& C = *R.C; DSP& D = *C.dsp;
        const TWord cur = D.getPC().toWord();
        if (cur == SENTINEL) { endCall(R); return true; }
        if (R.cur.steps >= 50000000u) {
            std::printf("\nHANG%s: instance %d, block %d, pc=0x%06x (core %d)\n",
                        R.cur.ctl ? " in the a=0 call" : "", R.cur.inst, R.block, cur, C.id);
            dumpRegs(D, *C.mem);
            return false;
        }
        const bool tr = a.trace && (R.cur.inst == 0) && !R.cur.ctl &&
                        (R.block == 0 || (a.diff && R.block == a.diff - 1)) &&
                        static_cast<int>(R.cur.steps) < a.trace;
        if (tr)
            std::printf("  inst 0 %6u  pc=%06x  a=%012llx r5=%06x n5=%06x m5=%06x x1=%06x n7=%06x\n",
                        R.cur.steps, cur,
                        static_cast<unsigned long long>(D.regs().a.var & 0xffffffffffffull),
                        D.regs().r[5].var & 0xffffff, D.regs().n[5].var & 0xffffff,
                        D.regs().m[5].var & 0xffffff,
                        (unsigned)(D.regs().x.var >> 24) & 0xffffff,
                        D.regs().n[7].var);
        D.execInterpreter();
        ++R.cur.steps;
        return true;
    };
    // Run a core to the end of its block.
    auto runCore = [&](CoreRun& R) -> bool {
        while (!R.done()) if (!stepCore(R)) return false;
        return true;
    };

    for (int b = 0; b < a.blocks; ++b) {
        // fill every instance's block: impulse on the first frame unless an
        // input file is given. Without per-instance files all instances see
        // the same audio.
        for (int k = 0; k < a.inst; ++k) {
            Instance& I = inst[k];
            Core& C = *cores[I.core];
            if (!I.fills) continue;              // a chained instance sees its predecessor's output
            for (int f = 0; f < a.frames; ++f) {
                int32_t s = 0;
                if (I.hasInput) s = I.inPos < I.input.size() ? I.input[I.inPos++] : 0;
                else if (b == 0 && f == 0) s = 0x400000;             // 0.5 full scale
                // -inmask silences an instance's own input so its output is
                // ONLY what arrived through the shared bus. Feeding a server
                // dry audio as well would bury the bus contribution under it.
                const int32_t sk = I.fed ? s : 0;
                C.dsp->memWrite(MemArea_X, I.audio + f * 2 + 0, sk & 0xffffff);
                C.dsp->memWrite(MemArea_X, I.audio + f * 2 + 1, sk & 0xffffff);
            }
        }
        if (a.spray && b == 0) {
            // excite every candidate input word: if the effect reads audio from
            // anywhere in the low X region, this will find it
            for (TWord ad = 0; ad < static_cast<TWord>(a.spray); ++ad)
                dsp.memWrite(MemArea_X, ad, 0x400000);
        }
        if (a.pingpong >= 0)
            for (auto& Cp : cores) Cp->mem->set(MemArea_X, 0x41f, static_cast<TWord>(a.pingpong));
        if (a.diff && b == a.diff - 1) {
            snap.resize(DIFF_HI - DIFF_LO);
            Core& C = *cores[inst[0].core];
            for (TWord ad = DIFF_LO; ad < DIFF_HI; ++ad) snap[ad - DIFF_LO] = C.mem->get(MemArea_X, ad);
        }

        // the calls each core makes this block, in dispatch order
        for (int c = 0; c < ncores; ++c) {
            CoreRun& R = runs[c];
            R.calls.clear(); R.idx = 0; R.inCall = false; R.block = b;
            for (int k : cores[c]->insts) {
                Instance& I = inst[k];
                const int sp = (I.split > 0 && I.split < a.frames) ? I.split : 0;
                if (!a.noctl && sp) R.calls.push_back(Call{k, true, 0});
                R.calls.push_back(Call{k, false, 0});
            }
        }
        std::vector<uint64_t> i0(ncores);
        for (int c = 0; c < ncores; ++c) i0[c] = cores[c]->dsp->getInstructionCounter();

        if (!a.interleave || ncores == 1) {
            // LOCK-STEP: core 0's whole block, then core 1's. What a single
            // core always saw; blind to the race by construction.
            for (int c = 0; c < ncores && !hung; ++c)
                if (!runCore(runs[c])) hung = true;
        } else {
            // INTERLEAVED: the leader runs |skew| instructions alone, then
            // the two alternate one instruction at a time until both blocks
            // are done. Not the hardware's timing: a fuzz of it.
            CoreRun& lead = runs[a.skew >= 0 ? 0 : 1];
            CoreRun& lag  = runs[a.skew >= 0 ? 1 : 0];
            for (long i = 0; i < std::labs(a.skew) && !lead.done() && !hung; ++i)
                if (!stepCore(lead)) hung = true;
            while (!hung && !(lead.done() && lag.done())) {
                if (!stepCore(lead)) { hung = true; break; }
                if (!stepCore(lag))  { hung = true; break; }
            }
        }
        if (hung) return 1;

        for (int c = 0; c < ncores; ++c) {
            Core& C = *cores[c];
            const long n = static_cast<long>(C.dsp->getInstructionCounter() - i0[c]);
            C.meter.push_back(n);
            if (n > C.maxBlockInstr) { C.maxBlockInstr = n; C.maxBlock = b; }
        }
        if (meterFile.is_open()) {
            meterFile << b;
            for (int c = 0; c < ncores; ++c) meterFile << ' ' << cores[c]->meter.back();
            meterFile << '\n';
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

    {   // full register file at end of run, for cross-engine divergence hunts
        auto& R = dsp.regs();
        std::printf("REGS a=%012llx b=%012llx x=%012llx y=%012llx\n",
            (long long)R.a.var & 0xffffffffffffLL, (long long)R.b.var & 0xffffffffffffLL,
            (long long)R.x.var, (long long)R.y.var);
        for (int i = 0; i < 8; ++i)
            std::printf("REGS r%d=%06x n%d=%06x m%d=%06x\n", i, R.r[i].var & 0xffffff,
                        i, R.n[i].var & 0xffffff, i, R.m[i].var & 0xffffff);
        std::printf("REGS sr=%06x omr=%06x sp=%06x la=%06x lc=%06x\n",
                    R.sr.var & 0xffffff, R.omr.var & 0xffffff, R.sp.var & 0xffffff,
                    R.la.var & 0xffffff, R.lc.var & 0xffffff);
    }
    if (!a.dumpyFile.empty() && a.dumpyFile[0] == '@') {   // @file = X space
        std::ofstream df(a.dumpyFile.substr(1), std::ios::binary);
        for (TWord ad = a.dumpyLo; ad < a.dumpyHi; ++ad) {
            uint32_t w = mem.get(MemArea_X, ad);
            df.write(reinterpret_cast<const char*>(&w), 4);
        }
        std::printf("dumped X 0x%05x..0x%05x\n", a.dumpyLo, a.dumpyHi);
    }
    else if (!a.dumpyFile.empty()) {
        std::ofstream df(a.dumpyFile, std::ios::binary);
        for (TWord ad = a.dumpyLo; ad < a.dumpyHi; ++ad) {
            uint32_t w = mem.get(MemArea_Y, ad);
            df.write(reinterpret_cast<const char*>(&w), 4);
        }
        std::printf("dumped Y 0x%05x..0x%05x -> %s\n", a.dumpyLo, a.dumpyHi, a.dumpyFile.c_str());
    }
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

    std::printf("ran %d blocks x %d frames on %d instance(s), %d core(s)%s\n", a.blocks, a.frames,
                a.inst, ncores,
                ncores == 1 ? "" : (a.interleave ? " interleaved" : " lock-step"));
    // THE METER. Instructions, not cycles: the emulator counts executed
    // instructions and models no memory-contention stall, so this is a floor
    // on the chip's cycles in the same way tools/build/cycle_count.py is -- but
    // per BLOCK, for THIS layout, with every instance's real work (and any
    // init landing inside a block) rather than one composition's sample
    // loops. The wall is docs/firmware/CHIP.md's measured budget.
    for (auto& Cp : cores) {
        Core& C = *Cp;
        if (C.meter.empty()) continue;
        long sum = 0; for (long n : C.meter) sum += n;
        std::printf("  core %d meter: max %ld instructions in block %d, mean %.0f "
                    "(%.1f/sample max, %.1f/sample mean at %d frames); inits %ld\n",
                    C.id, C.maxBlockInstr, C.maxBlock, double(sum) / C.meter.size(),
                    double(C.maxBlockInstr) / a.frames, double(sum) / C.meter.size() / a.frames,
                    a.frames, C.initInstr);
    }
    long total = 0, bad = 0;
    bool anyGuard = false;
    for (auto& Cp : cores) anyGuard |= Cp->guard.armed;
    for (int k = 0; k < a.inst; ++k) {
        std::printf("  instance %d: %.1f instructions/sample (%ld calls)\n", k,
                    inst[k].procCalls ? double(inst[k].cycles) / inst[k].procCalls / a.frames : 0.0,
                    inst[k].procCalls);
        std::printf("  instance %d: %ld non-zero output samples", k, inst[k].nonzero);
        if (anyGuard)
            std::printf(", %ld stray write regions, %ld CLOBBERING a loaded module",
                        inst[k].violations, inst[k].clobbers);
        std::printf("\n");
        total += inst[k].nonzero; bad += inst[k].clobbers;
    }
    if (!total) std::printf("  (all silent -- the effect produced nothing)\n");
    if (anyGuard && !bad)
        std::printf("  guard clean: nothing written over a loaded module\n");
    return bad ? 3 : 0;
}
