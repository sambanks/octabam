// Minimal DSP56300 assembler driver.
//
// dsp56kEmu's Assembler handles one instruction at a time and knows nothing about
// labels, so this adds a two-pass wrapper: pass 1 sizes every instruction and
// records label addresses, pass 2 assembles with labels resolved as P symbols.
//
// Output is a module blob in the same 24-bit little-endian packing the Octatrack
// payloads use, ready to be inserted by tools/dsp_patch.py.
//
//   dsp_asm -in src.asm -org <hex> [-out blob.bin] [-list]
//
// Source syntax: one instruction per line, ';' comments, "label:" on its own line
// or leading a line. Blank lines ignored.
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "dsp56kEmu/assembler.h"

using namespace dsp56k;

namespace {

std::string trim(std::string s) {
    const auto c = s.find(';');
    if (c != std::string::npos) s = s.substr(0, c);
    while (!s.empty() && isspace(static_cast<unsigned char>(s.front()))) s.erase(s.begin());
    while (!s.empty() && isspace(static_cast<unsigned char>(s.back()))) s.pop_back();
    return s;
}

const char* errName(AssembleError e) {
    switch (e) {
    case AssembleError::OK: return "OK";
    case AssembleError::InvalidInstruction: return "InvalidInstruction";
    case AssembleError::InvalidRegister: return "InvalidRegister";
    case AssembleError::InvalidAddressingMode: return "InvalidAddressingMode";
    case AssembleError::InvalidAddress: return "InvalidAddress";
    case AssembleError::ValueOutOfRange: return "ValueOutOfRange";
    case AssembleError::InvalidBitNumber: return "InvalidBitNumber";
    case AssembleError::InvalidConditionCode: return "InvalidConditionCode";
    case AssembleError::InvalidMemoryArea: return "InvalidMemoryArea";
    case AssembleError::InvalidImmediate: return "InvalidImmediate";
    case AssembleError::InvalidOperandCount: return "InvalidOperandCount";
    case AssembleError::InvalidSyntax: return "InvalidSyntax";
    case AssembleError::AmbiguousInstruction: return "AmbiguousInstruction";
    default: return "InternalError";
    }
}

} // namespace

int main(int argc, char** argv) {
    std::string in, out;
    TWord org = 0;
    bool list = false;
    for (int i = 1; i < argc; ++i) {
        std::string k = argv[i];
        if (k == "-in" && i + 1 < argc) in = argv[++i];
        else if (k == "-out" && i + 1 < argc) out = argv[++i];
        else if (k == "-org" && i + 1 < argc) org = strtoul(argv[++i], nullptr, 16);
        else if (k == "-list") list = true;
    }
    if (in.empty()) { std::cerr << "usage: dsp_asm -in src.asm -org <hex> [-out blob] [-list]\n"; return 2; }

    std::ifstream f(in);
    if (!f.is_open()) { std::cerr << "cannot open " << in << "\n"; return 1; }
    std::vector<std::pair<int, std::string>> lines;   // (source line no, text)
    std::string l;
    for (int n = 1; std::getline(f, l); ++n) {
        auto t = trim(l);
        if (!t.empty()) lines.emplace_back(n, t);
    }

    Assembler asmb;
    std::map<std::string, TWord> labels;

    // Pre-scan label names. The assembler's symbol table does not resolve these
    // in operands, so labels are substituted textually as $hex instead.
    for (auto& [n, text] : lines) {
        const auto colon = text.find(':');
        if (colon != std::string::npos && text.find(',') == std::string::npos)
            labels[text.substr(0, colon)] = 0;
    }

    // The assembler implements only the RELATIVE b-forms (bra/bsr/bcc); jmp and
    // jcc are not supported. So a branch operand is a DISPLACEMENT from the
    // instruction's own address, while everything else (do, immediates, memory
    // references) takes the label's absolute value. Getting this wrong is silent:
    // "beq $201f" at pc 0x200e branches to 0x402d, not 0x201f.
    auto isRelative = [](const std::string& t) {
        static const char* rel[] = {"bra","bsr","beq","bne","bcc","bcs","bhs","blo",
                                    "bgt","blt","bge","ble","bmi","bpl","bvc","bvs"};
        std::string m = t.substr(0, t.find_first_of(" \t"));
        for (auto& c : m) c = static_cast<char>(tolower(c));
        for (auto* r : rel) if (m == r) return true;
        return false;
    };

    auto substitute = [&](std::string t, bool real, TWord here) {
        const bool relative = isRelative(t);
        for (auto& [name, addr] : labels) {
            char buf[32];
            if (!real) {
                // pass 1: a high dummy so the LONG form is sized, matching pass 2
                std::snprintf(buf, sizeof buf, "$%x", 0x7ff000);
            } else if (relative) {
                const int32_t disp = static_cast<int32_t>(addr) - static_cast<int32_t>(here);
                std::snprintf(buf, sizeof buf, "%s$%x", disp < 0 ? "-" : "",
                              disp < 0 ? -disp : disp);
            } else {
                std::snprintf(buf, sizeof buf, "$%x", addr);
            }
            for (auto p2 = t.find(name); p2 != std::string::npos; p2 = t.find(name, p2 + 1))
                t.replace(p2, name.size(), buf);
        }
        return t;
    };

    // ---- pass 1: size instructions, fix label addresses -----------------------
    TWord pc = org;
    std::vector<std::pair<int, std::string>> code;
    for (auto& [n, text] : lines) {
        auto t = text;
        const auto colon = t.find(':');
        if (colon != std::string::npos && t.find(',') == std::string::npos) {
            labels[t.substr(0, colon)] = pc;
            t = trim(t.substr(colon + 1));
            if (t.empty()) continue;
        }
        const auto r = asmb.assemble(substitute(t, false, pc).c_str());
        code.emplace_back(n, t);
        pc += r.success() ? r.wordCount : 1;
    }

    // ---- pass 2: assemble with real addresses ---------------------------------
    std::vector<TWord> outWords;
    pc = org;
    int errors = 0;
    for (auto& [n, text] : code) {
        const auto resolved = substitute(text, true, pc);
        const auto r = asmb.assemble(resolved.c_str());
        if (!r.success()) {
            std::fprintf(stderr, "%s:%d: %s -- \"%s\"\n", in.c_str(), n, errName(r.error), resolved.c_str());
            ++errors;
            continue;
        }
        if (list) {
            std::printf("%06x: %-38s ; %06x", pc, resolved.c_str(), r.word[0]);
            if (r.wordCount > 1) std::printf(" %06x", r.word[1]);
            std::printf("\n");
        }
        for (uint32_t i = 0; i < r.wordCount; ++i) outWords.push_back(r.word[i]);
        pc += r.wordCount;
    }
    if (errors) { std::fprintf(stderr, "%d error(s)\n", errors); return 1; }

    std::printf("assembled %zu words, P:0x%05x..0x%05x\n", outWords.size(), org, pc - 1);
    if (!out.empty()) {
        std::ofstream o(out, std::ios::binary);
        for (auto w : outWords) {
            const uint8_t b[3] = {static_cast<uint8_t>(w & 0xff),
                                  static_cast<uint8_t>((w >> 8) & 0xff),
                                  static_cast<uint8_t>((w >> 16) & 0xff)};
            o.write(reinterpret_cast<const char*>(b), 3);   // 24-bit little-endian
        }
        std::printf("wrote %s\n", out.c_str());
    }
    return 0;
}
