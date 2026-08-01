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
//     -params a,b,c,d,e,f   page-1 parameter values 0..127 (default 64)
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
    int frames = 32, blocks = 256, trace = 0;
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
        else if (k == "-in") a.in = v();
        else if (k == "-out") a.out = v();
        else if (k == "-params") {
            a.pv.clear();
            char* s = argv[++i];
            for (char* t = strtok(s, ","); t; t = strtok(nullptr, ",")) a.pv.push_back(atoi(t));
            a.pv.resize(6, 64);
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

    // parameter block: page-1 values as 0..127 << 16
    for (int i = 0; i < 6; ++i)
        dsp.memWrite(MemArea_X, a.params + i, (static_cast<TWord>(a.pv[i]) & 0x7f) << 16);
    std::printf("params @X:0x%05x =", a.params);
    for (int i = 0; i < 6; ++i) std::printf(" %d", a.pv[i]);
    std::printf("\n");

    dsp.regs().r[6].var = a.params;
    dsp.regs().r[7].var = a.state;   // per-instance state block (dispatcher: r7 = x:>$20a + 0x100)
    std::printf("state block r7 = X:0x%05x\n", a.state);
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
        dsp.regs().r[0].var = a.audio;
        dsp.regs().r[6].var = a.params;
        dsp.regs().r[7].var = a.state;
        dsp.regs().n[7].var = a.frames;
        if (!runToRts(dsp, a.proc, b == 0 ? a.trace : 0, "proc")) return 1;

        for (int f = 0; f < a.frames; ++f) {
            for (int c = 0; c < 2; ++c) {
                TWord w = mem.get(MemArea_X, a.audio + f * 2 + c);
                int32_t s = static_cast<int32_t>(w << 8) >> 8;   // sign-extend 24 -> 32
                if (s) ++nonzero;
                if (outf.is_open()) outf.write(reinterpret_cast<char*>(&s), 4);
            }
        }
    }
    std::printf("ran %d blocks x %d frames; %ld non-zero output samples\n",
                a.blocks, a.frames, nonzero);
    if (!nonzero) std::printf("  (all silent -- the effect produced nothing)\n");
    return 0;
}
