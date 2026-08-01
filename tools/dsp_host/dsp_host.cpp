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
// Usage:
//   dsp_host -mem out/dsp/mem_A.mem -init <hex> -proc <hex> [options]
//     -params a,b,...       parameter values 0..127 (default 64); 6 fills page 1,
//                           8 also covers the page-2 slots at r6+6..7
//     -frames N             frames per block (default 32)
//     -blocks N             blocks to run (default 256)
//     -in file.raw          24-bit mono raw input, else an impulse is used
//     -out file.raw         write the output block stream
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
    TWord init = 0, proc = 0, audio = 0x000000, params = 0x000100, state = 0x010000;
    int frames = 32, blocks = 256, trace = 0, diff = 0, spray = 0; TWord flags = 0; int pingpong = -1;
    std::vector<int> pv{64, 64, 64, 64, 64, 64};
};

bool loadMem(DSP& dsp, const std::string& path, int& modules, long& words) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) { std::cerr << "cannot open " << path << "\n"; return false; }
    modules = 0; words = 0;
    for (;;) {
        uint8_t sp; uint32_t addr, cnt;
        f.read(reinterpret_cast<char*>(&sp), 1);
        f.read(reinterpret_cast<char*>(&addr), 4);
        f.read(reinterpret_cast<char*>(&cnt), 4);
        if (!f || sp == 0xff) break;
        for (uint32_t i = 0; i < cnt; ++i) {
            uint32_t w; f.read(reinterpret_cast<char*>(&w), 4);
            if (sp == 0)      dsp.memWriteP(addr + i, w & 0xffffff);
            else if (sp == 1) dsp.memWrite(MemArea_X, addr + i, w & 0xffffff);
            else              dsp.memWrite(MemArea_Y, addr + i, w & 0xffffff);
        }
        ++modules; words += cnt;
    }
    return true;
}

// Run from _pc until the matching rts pops back past the entry stack depth.
bool runToRts(DSP& dsp, TWord pc, int trace, const char* what, uint32_t maxCycles = 50000000) {
    // Call through the emulator's own jsr so the return address is pushed the
    // way the hardware would. The sentinel must be a MAPPED P address -- an
    // out-of-range one faults as soon as the rts returns to it.
    const TWord sentinel = 0x03f000;
    dsp.setPC(sentinel);
    dsp.jsr(pc);
    for (uint32_t i = 0; i < maxCycles; ++i) {
        const TWord cur = dsp.getPC().toWord();
        if (cur == sentinel) return true;
        if (trace && static_cast<int>(i) < trace)
            std::printf("  %s %6u  pc=%06x  a=%012llx r0=%06x r6=%06x\n", what, i, cur,
                        static_cast<unsigned long long>(dsp.regs().a.var & 0xffffffffffffull),
                        dsp.regs().r[0].var, dsp.regs().r[6].var);
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
        else if (k == "-in") a.in = v();
        else if (k == "-out") a.out = v();
        else if (k == "-params") {
            a.pv.clear();
            char* s = argv[++i];
            for (char* t = strtok(s, ","); t; t = strtok(nullptr, ",")) a.pv.push_back(atoi(t));
            if (a.pv.size() < 8) a.pv.resize(8, 64);   // page 2 lives at r6+6..8
        }
    }
    if (a.mem.empty() || !a.proc) {
        std::cerr << "usage: dsp_host -mem <file> -init <hex> -proc <hex> [-params a,b,..]\n"
                     "                [-frames N] [-blocks N] [-in raw] [-out raw] [-trace N]\n";
        return 2;
    }

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

    // The dispatcher hands the routine r6 = x:0x208 + 6 (FX1) and
    // r7 = x:0x20a + 0x100.
    const TWord pblock = ctlB + 6;
    const TWord state  = mem.get(MemArea_X, 0x20a) + 0x100;
    for (size_t i = 0; i < a.pv.size(); ++i)
        mem.set(MemArea_X, pblock + i, (static_cast<TWord>(a.pv[i]) & 0x7f) << 16);
    std::printf("params @X:0x%05x =", pblock);
    for (size_t i = 0; i < a.pv.size(); ++i) std::printf(" %d", a.pv[i]);
    std::printf("   state r7 = X:0x%05x\n", state);

    dsp.regs().r[6].var = pblock;
    dsp.regs().r[7].var = state;
    if (a.init) {
        std::printf("running init @P:0x%05x ...\n", a.init);
        if (!runToRts(dsp, a.init, a.trace, "init")) return 1;
        std::printf("init returned ok\n");
    }

    std::vector<int32_t> input;
    if (!a.in.empty()) {
        std::ifstream f(a.in, std::ios::binary);
        int32_t s;
        while (f.read(reinterpret_cast<char*>(&s), 4)) input.push_back(s);
    }

    std::ofstream outf;
    if (!a.out.empty()) outf.open(a.out, std::ios::binary);

    long nonzero = 0;
    size_t inPos = 0;
    for (int b = 0; b < a.blocks; ++b) {
        // fill the block: impulse on the first frame unless an input file is given
        for (int f = 0; f < a.frames; ++f) {
            int32_t s = 0;
            if (!input.empty()) s = inPos < input.size() ? input[inPos++] : 0;
            else if (b == 0 && f == 0) s = 0x400000;             // 0.5 full scale
            dsp.memWrite(MemArea_X, a.audio + f * 2 + 0, s & 0xffffff);
            dsp.memWrite(MemArea_X, a.audio + f * 2 + 1, s & 0xffffff);
        }
        if (a.spray && b == 0) {
            // excite every candidate input word: if the effect reads audio from
            // anywhere in the low X region, this will find it
            for (TWord ad = 0; ad < static_cast<TWord>(a.spray); ++ad)
                dsp.memWrite(MemArea_X, ad, 0x400000);
        }
        if (a.pingpong >= 0) mem.set(MemArea_X, 0x41f, static_cast<TWord>(a.pingpong));
        dsp.regs().r[0].var = a.audio;
        dsp.regs().r[6].var = pblock;
        dsp.regs().r[7].var = state;
        dsp.regs().n[7].var = cnt;
        std::vector<TWord> snap;
        const TWord DIFF_LO = 0x000, DIFF_HI = 0x8000;
        if (a.diff && b == a.diff - 1) {
            snap.resize(DIFF_HI - DIFF_LO);
            for (TWord ad = DIFF_LO; ad < DIFF_HI; ++ad) snap[ad - DIFF_LO] = mem.get(MemArea_X, ad);
        }
        if (!runToRts(dsp, a.proc, b == 0 ? a.trace : 0, "proc")) return 1;
        if (a.diff && b == a.diff - 1) {
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
        for (int f = 0; f < a.frames; ++f) {
            for (int c = 0; c < 2; ++c) {
                TWord w = mem.get(MemArea_X, a.audio + f * 2 + c);
                int32_t s = static_cast<int32_t>(w << 8) >> 8;   // sign-extend 24 -> 32
                if (s) ++nonzero;
                if (outf.is_open()) outf.write(reinterpret_cast<char*>(&s), 4);
            }
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
    std::printf("ran %d blocks x %d frames; %ld non-zero output samples\n",
                a.blocks, a.frames, nonzero);
    if (!nonzero) std::printf("  (all silent -- the effect produced nothing)\n");
    return 0;
}
