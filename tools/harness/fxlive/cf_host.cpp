// cf_host: the ColdFire's per-frame delay routine on one track, for listening.
//
// The CPU half of an effect whose sound is made on the ColdFire (the stock
// DELAY, id 0x08; TAPE ECHO, id 0x15, which rides the same routine). It runs
// what tools/harness/tapeecho_cpu_probe.cpp's benchmark runs -- the complete
// eight-track frame routine 0x400031a0 over a synchronous eDMA model -- one
// frame per 16-sample block, from a built image and its packed DRAM runtime:
//
//   1. the track's DSP voice record (0x80000110 + 0x200*ping + 64*track; the
//      knob words are r6's, halfword = DSP word >> 8 at r6 offset + 12) is
//      staged by stock's own producer copy 0x4000d0ea..0x4000d15a, as the
//      tapeecho probe's end-to-end test does;
//   2. the track's 16 stereo samples (DSP word << 8) go to the read-back block
//      0x80003190 + 1024*ping + 128*track;
//   3. 0x400031a0 runs all eight tracks; the block is processed in place.
//
// docs/firmware/COLDFIRE_DELAY.md is the map. What this is NOT: the rest of
// the firmware (sequencer, LFOs, the transfer state machine, the DSP), the
// cache and bus timing, or the CPU budget (the instruction count is a floor).
//
//   cf_host IMAGE [--runtime RAW BASE] --fxid HEX [--track N] [--tempo BPM] --stream
//   cf_host IMAGE [--runtime RAW BASE] --fxid HEX --selftest
//
// --stream speaks dsp_host -stream's protocol: per block in, 12 knob values
// (int32 0..127) then 16 interleaved L,R samples (int32, 24-bit); out, the 16
// processed samples then the instructions the routine ran.
#include <chrono>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include "machine.h"
#include "periph.h"
#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

namespace {
constexpr uint32_t STACK = 0x47100000, ENDPC = 0x47200000;
constexpr uint32_t ROUTINE = 0x400031a0, RESET = 0x40002f44;
constexpr uint32_t STAGE_LO = 0x4000d0ea, STAGE_HI = 0x4000d15a;
constexpr int FRAMES = 16, NPARAM = 12;

std::vector<uint8_t> readFile(const char* p) {
    std::ifstream f(p, std::ios::binary);
    if (!f) { std::fprintf(stderr, "cf_host: cannot read %s\n", p); std::exit(2); }
    return {std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>()};
}

uint64_t run(ot::Machine& m, uint32_t pc, uint32_t until, uint64_t max) {
    m68k_set_reg(m.getCpuState(), M68K_REG_PC, pc);
    uint64_t n = 0;
    while (m.pcFast() != until && n++ < max)
        if (!m.stepFast()) break;
    if (m.pcFast() != until) {
        std::fprintf(stderr, "cf_host: stopped at %08x, wanted %08x, after %llu instructions\n",
                     m.pcFast(), until, static_cast<unsigned long long>(n));
        std::exit(3);
    }
    return n;
}

uint64_t call(ot::Machine& m, uint32_t entry, uint64_t max) {
    m68k_set_reg(m.getCpuState(), M68K_REG_SP, STACK);
    m.write32(STACK, ENDPC);
    return run(m, entry, ENDPC, max);
}

struct Host {
    ot::Machine m;
    ot::Edma dma;
    int track = 0;
    uint32_t fxid = 0;
    uint32_t tempo24 = 120 * 24;
    unsigned frame = 0;

    Host(const std::vector<uint8_t>& image) : m(image) {
        m68k_set_reg(m.getCpuState(), M68K_REG_SR, 0x2700);
        // The probe's synchronous eDMA: a kick copies its whole major loop.
        m.setPeripheralHandlers(
            [this](uint32_t a, uint8_t n, uint32_t& v) {
                if (a < ot::Edma::g_base || a >= ot::Edma::g_tcd + 512) return false;
                v = dma.read(a, n); return true;
            },
            [this](uint32_t a, uint8_t n, uint32_t v) {
                if (a >= ot::Edma::g_base && a < ot::Edma::g_tcd + 512) dma.write(a, n, v, false);
            });
        dma.setDataHooks({}, [this](uint32_t ch) {
            const uint32_t src = dma.tcdField(ch, 0, 4), dst = dma.tcdField(ch, 16, 4);
            const uint32_t size = dma.tcdField(ch, 8, 4) * dma.minorLoops(ch);
            std::vector<uint8_t> b(size);
            for (uint32_t i = 0; i < size; ++i) b[i] = m.read8(src + i);
            for (uint32_t i = 0; i < size; ++i) m.write8(dst + i, b[i]);
        });
    }

    void reset() { call(m, RESET, 5000000); }

    // One 16-sample block through the routine. io: 32 int32, 24-bit, in place.
    uint64_t block(const int32_t* knobs, int32_t* io) {
        const unsigned ping = frame & 1, slot = frame & 3;
        m.write32(0x800000e0, ping);
        m.write32(0x80004800, slot);
        m.write32(0x80004804, slot);
        m.write8(0x8000184b, 0);
        // The tempo words (docs/firmware/DSP.md "Tempo"): 0x80001814 = BPM x 24,
        // latched into 0x8000181c, and the sync multiplier the frame code
        // derives at 0x4000ac9a, 0x80001820 = -2^31 / tempo24, which the
        // delay's TIME uses when SYNC is on (0x4000324a/0x40003280).
        m.write32(0x80001814, tempo24);
        m.write32(0x8000181c, tempo24);
        m.write32(0x80001820, static_cast<uint32_t>(static_cast<int32_t>(INT32_MIN / static_cast<int64_t>(tempo24))));
        for (int t = 0; t < 8; ++t) {
            const uint32_t rec = 0x80000110 + ping * 0x200 + t * 64;
            const bool ours = t == track;
            for (int i = 0; i < 6; ++i)
                m.write16(rec + 24 + 2 * i, ours ? static_cast<uint16_t>((knobs[i] & 0x7f) << 8) : 0);
            for (int w = 0; w < 3; ++w) {          // page 2: r6+$c..$e, knob | companion
                const uint16_t h = ours ? static_cast<uint16_t>(((knobs[6 + 2 * w] & 0x7f) << 8)
                                                                | (knobs[7 + 2 * w] & 0x7f)) : 0;
                m.write16(rec + 48 + 2 * w, h);
            }
            m.write16(rec + 56, ours ? fxid : 0);
            m.write8(0x80000eb4 + ping * 8 + t, ours ? 1 : 0);
        }
        // stock's producer copy: all eight records into snapshot [0x80004800]
        run(m, STAGE_LO, STAGE_HI, 10000);
        const uint32_t audio = 0x80003190 + ping * 1024 + track * 128;
        for (int i = 0; i < 2 * FRAMES; ++i)
            m.write32(audio + 4 * i, static_cast<uint32_t>(io[i]) << 8);
        const uint64_t n = call(m, ROUTINE, 2000000);
        for (int i = 0; i < 2 * FRAMES; ++i)
            io[i] = static_cast<int32_t>(m.read32(audio + 4 * i)) >> 8;
        ++frame;
        return n;
    }
};

const char* USAGE =
    "cf_host IMAGE [--runtime RAW BASE] --fxid HEX [--track N] [--tempo BPM] --stream\n"
    "cf_host IMAGE [--runtime RAW BASE] --fxid HEX [--track N] [--knobs a,b,..] --selftest\n";
}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) { std::fputs(USAGE, stderr); return 2; }
    const auto image = readFile(argv[1]);
    std::vector<uint8_t> runtime; uint32_t base = 0;
    int track = 0; long fxid = -1; double bpm = 120; bool stream = false, selftest = false;
    int32_t knobs[NPARAM] = {};
    for (int i = 2; i < argc; ++i) {
        const std::string k = argv[i];
        auto next = [&]() -> const char* {
            if (i + 1 >= argc) { std::fprintf(stderr, "cf_host: %s needs a value\n", k.c_str()); std::exit(2); }
            return argv[++i];
        };
        if (k == "--runtime") { runtime = readFile(next()); base = std::strtoul(next(), nullptr, 16); }
        else if (k == "--fxid") fxid = std::strtol(next(), nullptr, 16);
        else if (k == "--track") track = std::atoi(next());
        else if (k == "--tempo") bpm = std::atof(next());
        else if (k == "--knobs") {
            std::string v = next(); size_t pos = 0; int j = 0;
            while (j < NPARAM && pos <= v.size()) {
                const size_t c = v.find(',', pos);
                knobs[j++] = std::atoi(v.substr(pos, c - pos).c_str());
                if (c == std::string::npos) break;
                pos = c + 1;
            }
        }
        else if (k == "--stream") stream = true;
        else if (k == "--selftest") selftest = true;
        else { std::fprintf(stderr, "cf_host: unknown option %s\n%s", k.c_str(), USAGE); return 2; }
    }
    if (fxid < 0 || track < 0 || track > 7 || stream == selftest) { std::fputs(USAGE, stderr); return 2; }

    Host h(image);
    h.track = track; h.fxid = static_cast<uint32_t>(fxid);
    h.tempo24 = static_cast<uint32_t>(bpm * 24 + 0.5);
    for (size_t i = 0; i < runtime.size(); ++i) h.m.write8(base + static_cast<uint32_t>(i), runtime[i]);
    h.reset();

    if (stream) {
        std::vector<int32_t> pk(NPARAM + 2 * FRAMES);
        while (std::fread(pk.data(), 4, pk.size(), stdin) == pk.size()) {
            const uint64_t n = h.block(pk.data(), pk.data() + NPARAM);
            const int32_t ins = static_cast<int32_t>(n);
            std::fwrite(pk.data() + NPARAM, 4, 2 * FRAMES, stdout);
            std::fwrite(&ins, 4, 1, stdout);
            if (std::fflush(stdout) != 0) break;
        }
        return 0;
    }

    // --selftest: an impulse at block 10 into silence; where does it come out,
    // and how fast does a block run?
    int32_t io[2 * FRAMES];
    int first = -1, nonzero = 0;
    uint64_t ins = 0;
    const int blocks = 6000;
    const auto t0 = std::chrono::steady_clock::now();
    for (int b = 0; b < blocks; ++b) {
        std::memset(io, 0, sizeof io);
        if (b == 10) io[0] = io[1] = 0x400000;
        ins += h.block(knobs, io);
        bool any = false;
        for (int i = 0; i < 2 * FRAMES; ++i) any |= io[i] != 0;
        if (any) { ++nonzero; if (first < 0 || (b > 10 && first == 10)) first = b; }
        if (any && nonzero <= 12)
            std::printf("  block %5d: L[0..3] %d %d %d %d  R[0] %d\n", b, io[0], io[2], io[4], io[6], io[1]);
    }
    const double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    std::printf("%d blocks, %d with output; %.0f instructions/block; %.1fx real time (%.0f blocks/s)\n",
                blocks, nonzero, double(ins) / blocks, blocks * FRAMES / 44100.0 / s, blocks / s);
    return 0;
}
