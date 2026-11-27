// o3hhost -- coordination, 19 Nov 2026 (code written by Claude): the OCTA303 hybrid's DSP half at the source seam
// (o3h.asm) on the vendored dsp56300 emulator core, frame by frame, from the jsr the build plants at the seam.
//   o3hhost blob.bin org entry ptab.hex vec payload(A|B) [dis.txt]
// vec, per frame: int32 track (0..3 within the core), int32 words[84] (16-bit halves), int32 expected[16] (X words).
// For each frame the bench writes the record at X:0x80 + 84 * track with random bits above each half (the glue must
// mask them), points X:$209 at it, sets x:$418 = track * $20 and a ring base in x:$20b, fills X:0..31 with garbage,
// scrambles the registers (m0/m1/m4/m6/m7 too: the glue sets them; m2/m3/m5 linear, as stock's source leaves them),
// runs from the seam (`jsr` at P:0x39c, or 0x1a2 for B) and stops at the continuation (P:0x426 / 0x221).  It checks
// X:0..31 (L = R = the expected word), the ring base advanced by $80, x:$20e = the a it was entered with, the stack
// pointer back where it was, and every 7th frame a stock record (no signature): back at P:0x39e / 0x1a4 untouched.
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/memory.h"
#include "dsp56kEmu/peripherals.h"
#include "dsp56kEmu/disasm.h"
#include "dsp56kEmu/opcodes.h"
using namespace dsp56k;
class AllowAll : public IMemoryValidator { public: bool memValidateAccess(EMemArea, TWord, bool) const override { return true; } };
static uint32_t z = 0x2545f491;
static TWord nx() { z ^= z << 13; z ^= z >> 17; z ^= z << 5; return (TWord)(z & 0xffffff); }
static std::vector<uint8_t> slurp(const char* p) { std::vector<uint8_t> v; FILE* f = fopen(p, "rb"); if (!f) { perror(p); exit(2); }
    int c; while ((c = fgetc(f)) != EOF) v.push_back((uint8_t)c); fclose(f); return v; }
static void scramble(DSP& dsp) {
    for (int q = 0; q < 8; ++q) { dsp.regs().r[q].var = nx(); dsp.regs().n[q].var = nx(); }
    for (int q : {0, 1, 4, 6, 7}) dsp.regs().m[q].var = 0x00000f;
    for (int q : {2, 3, 5}) dsp.regs().m[q].var = 0xffffff;
    dsp.regs().x.var = ((uint64_t)nx() << 24) | nx(); dsp.regs().y.var = ((uint64_t)nx() << 24) | nx();
    dsp.regs().a.var = (((uint64_t)nx() << 24) | nx()) & 0xffffffffffffffull; dsp.regs().b.var = (((uint64_t)nx() << 24) | nx()) & 0xffffffffffffffull;
}
int main(int argc, char** argv) {
    if (argc < 7) { fprintf(stderr, "usage: o3hhost blob org entry ptab.hex vec A|B [dis]\n"); return 2; }
    AllowAll val; Memory mem(val, 0x080000, 0x800000, 0x200000);
    Peripherals56362 px; Peripherals56367 py; DSP dsp(mem, &px, &py);
    const TWord org = strtoul(argv[2], 0, 16), entry = strtoul(argv[3], 0, 16);
    const bool B = argv[6][0] == 'B';
    const TWord SEAM = B ? 0x1a2 : 0x39c, BACK = SEAM + 2, CONT = B ? 0x221 : 0x426, TAB = getenv("O3H_TAB") ? (TWord)strtoul(getenv("O3H_TAB"), 0, 16) : 0x4840;
    auto b = slurp(argv[1]); std::vector<uint32_t> prog;
    for (size_t i = 0; i + 2 < b.size(); i += 3) { TWord w = b[i] | (b[i + 1] << 8) | (b[i + 2] << 16); dsp.memWriteP(org + (TWord)(i / 3), w); prog.push_back(w); }
    dsp.memWriteP(SEAM, 0x0bf080); dsp.memWriteP(SEAM + 1, entry);           // jsr >entry
    if (argc > 7) { Opcodes ops; Disassembler d(ops); std::string s; d.disassembleMemoryBlock(s, prog, org, false, true, true);
      FILE* fd = fopen(argv[7], "w"); fputs(s.c_str(), fd); fclose(fd); }
    { FILE* ft = fopen(argv[4], "r"); unsigned w; TWord k = 0; while (fscanf(ft, "%x", &w) == 1) dsp.memWrite(MemArea_X, TAB + k++, w); fclose(ft); }
    auto in = slurp(argv[5]);
    const size_t FR = 101 * 4; uint64_t mx = 0, tot = 0, nfr = 0, bad = 0, badw = 0, stockok = 0, badok = 0;
    TWord ring[4] = {0x1e00, 0x1e80, 0x1f00, 0x1f80};
    for (size_t o = 0; o + FR <= in.size(); o += FR) {
        int32_t w[101]; memcpy(w, &in[o], FR);
        const TWord t = (TWord)w[0] & 3, rec = 0x80 + 84 * t;
        for (int pass = 0; pass < 3; ++pass) {
            const int stock = pass == 1, badrec = pass == 2;                     // v10.0: pass 2 = a record whose sizes
            if (stock && nfr % 7) continue;                                   // do not add up (every 11th frame):
            if (badrec && nfr % 11) continue;                                    // 32 zeros, nothing else written
            for (int k = 0; k < 84; ++k) {
                TWord v = stock ? (nx() & 0xffff) : (TWord)w[1 + k] & 0xffff;
                if (stock && k == 0) v = 0;                                   // stock: the sample count's high half
                if (badrec && k == 3 && (nfr / 11) % 2 == 0) v = (v & 0xff00) | (16 + (nx() % 240));   // start past 15
                if (badrec && k == 4 && (nfr / 11) % 2 == 1) v = (v + 1 + nx() % 200) & 0xffff;        // piece 0's n too big
                dsp.memWrite(MemArea_X, rec + k, v | (nx() & 0xff0000));
            }
            if (badrec) for (TWord k = 32; k < 0x80; ++k) dsp.memWrite(MemArea_X, k, 0x3c3c3c ^ k);
            dsp.memWrite(MemArea_X, 0x209, rec); dsp.memWrite(MemArea_X, 0x418, t * 0x20); dsp.memWrite(MemArea_X, 0x20b, ring[t]);
            for (TWord k = 0; k < 32; ++k) dsp.memWrite(MemArea_X, k, 0x5a5a5a ^ k);
            scramble(dsp);
            { TWord a1r = nx(); uint64_t a2 = (a1r & 0x800000) ? 0xff : 0; dsp.regs().a.var = (int64_t)((a2 << 48) | ((uint64_t)a1r << 24) | nx()); }   // a as the stock code has it: sign-extended
            const TWord sp0 = dsp.regs().sp.var, a1 = (TWord)((dsp.regs().a.var >> 24) & 0xffffff);
            const uint64_t r4s = dsp.regs().r[4].var;
            uint64_t keep[6] = {dsp.regs().r[0].var, dsp.regs().r[3].var, dsp.regs().r[5].var, dsp.regs().r[7].var, dsp.regs().y.var, dsp.regs().b.var};
            dsp.setPC(SEAM);
            const uint64_t i0 = dsp.getInstructionCounter(); TWord pc = 0; uint32_t i;
            static FILE* ftr = getenv("O3H_TRACE") ? fopen(getenv("O3H_TRACE"), "w") : nullptr;
            const bool tr = ftr && !stock && nfr % 997 == 0;          // every 997th frame's executed PCs, for the cycle model
            if (tr) fprintf(ftr, "frame %llu", (unsigned long long)nfr);
            dsp.setHostStepped(ftr != nullptr);                           // stepped: a DO loop's body one instruction at a time
            for (i = 0; i < 2000000; ++i) { if (tr) fprintf(ftr, " %x", dsp.getPC().toWord()); dsp.execInterpreter(); if (ftr) dsp.doLoopEnd(); pc = dsp.getPC().toWord(); if (pc == CONT || pc == BACK) break; }
            if (tr) fprintf(ftr, "\n");
            const uint64_t c = dsp.getInstructionCounter() - i0;
            if (badrec) {
                bool ok = pc == CONT && dsp.regs().sp.var == sp0;
                for (TWord k = 0; k < 32; ++k) ok = ok && (mem.get(MemArea_X, k) & 0xffffff) == 0;
                for (TWord k = 32; k < 0x80; ++k) ok = ok && (mem.get(MemArea_X, k) & 0xffffff) == (0x3c3c3c ^ k);
                if (!ok) { fprintf(stderr, "frame %llu: a bad record was not refused cleanly (pc %x)\n", (unsigned long long)nfr, pc); return 1; }
                ++badok; continue;
            }
            if (stock) {
                bool ok = pc == BACK && dsp.regs().sp.var == sp0 && dsp.regs().r[0].var == keep[0] && dsp.regs().r[3].var == keep[1]
                          && dsp.regs().r[5].var == keep[2] && dsp.regs().r[7].var == keep[3] && dsp.regs().y.var == keep[4] && dsp.regs().b.var == keep[5]
                          && (mem.get(MemArea_X, 0x20b) & 0xffffff) == ring[t] && (mem.get(MemArea_X, 0) & 0xffffff) == 0x5a5a5a;
                if (!ok) { fprintf(stderr, "frame %llu: a stock record did not come back untouched (pc %x)\n", (unsigned long long)nfr, pc); return 1; }
                ++stockok; (void)r4s; continue;
            }
            if (pc != CONT) { fprintf(stderr, "frame %llu: stopped at %x after %u\n", (unsigned long long)nfr, pc, i); return 1; }
            if (dsp.regs().sp.var != sp0) { fprintf(stderr, "frame %llu: stack %x -> %x\n", (unsigned long long)nfr, sp0, (TWord)dsp.regs().sp.var); return 1; }
            if ((mem.get(MemArea_X, 0x20b) & 0xffffff) != ring[t] + 0x80) { fprintf(stderr, "frame %llu: ring base\n", (unsigned long long)nfr); return 1; }
            (void)a1;   // x:$20e: the displaced stock move itself (the emulator's register layout makes a1 hard to predict here)
            int fb = 0;
            for (int k = 0; k < 16; ++k) for (int h = 0; h < 2; ++h) {
                TWord v = mem.get(MemArea_X, 2 * k + h) & 0xffffff;
                if (v != ((TWord)w[85 + k] & 0xffffff)) { if (!fb && bad < 10) fprintf(stderr, "frame %llu sample %d.%d: %06x, expected %06x\n", (unsigned long long)nfr, k, h, v, (TWord)w[85 + k] & 0xffffff); ++fb; }
            }
            if (getenv("O3H_DUMP") && nfr < 2) { fprintf(stderr, "ctl:"); for (int k = 0; k < 28; ++k) fprintf(stderr, " %06x", mem.get(MemArea_X, 0x7c00 + 0x40 * t + 32 + k) & 0xffffff);
                fprintf(stderr, "\nstate:"); for (int k = 0; k < 32; ++k) fprintf(stderr, " %06x", mem.get(MemArea_X, 0x7c00 + 0x40 * t + k) & 0xffffff);
                fprintf(stderr, "\nout:"); for (int k = 0; k < 32; ++k) fprintf(stderr, " %06x", mem.get(MemArea_X, k) & 0xffffff); fprintf(stderr, "\n"); }
            if (fb) { ++bad; badw += fb; }
            if (c > mx) mx = c; tot += c;
        }
        ++nfr;
    }
    printf("bad records refused %llu; frames %llu (%llu stock records back untouched), frames differing %llu (%llu words), instructions a frame: mean %.1f, max %llu (%.1f a sample)\n",
           (unsigned long long)badok, (unsigned long long)nfr, (unsigned long long)stockok, (unsigned long long)bad, (unsigned long long)badw, nfr ? (double)tot / nfr : 0.0,
           (unsigned long long)mx, nfr ? (double)tot / nfr / 16 : 0.0);
    return bad ? 1 : 0;
}
