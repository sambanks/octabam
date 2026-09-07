// THE EMAC GATE. Run this before trusting anything this emulator computes.
//
// WHY IT EXISTS, and why it is the first test in the port rather than a later
// nicety: three defects in *Unicorn's* ColdFire EMAC cost a week this month
// (`docs/RTOS_FORK.md` §10.16). Each produced a confident wrong finding that
// was investigated as firmware behaviour for a day --
//
//   * fractional products came back HALVED (unsigned >> 32 where the chip does
//     signed >> 31), so the recorder wrote a length of 10,336 for Bryan's
//     20,672 and it was explained away as "2-sample units";
//   * `msac` ADDED where it must subtract (the MAC/MSAC bit was read from the
//     opcode word; the chip keeps it in the extension word), so every trig's
//     sub-frame offset came out 0;
//   * a harness trampoline was served stale, so a shimmed `msacl ..,%acc1` ran
//     as the previous `msacl ..,%acc0`.
//
// The firmware's own reciprocal tables (`0x80003c20` = 2^31 / block size) are
// what finally said which side was wrong. So: the expected values below are
// HARDWARE's, taken from `tools/emu_bringup.py::emac_selftest`, which is the
// same gate route A refuses to run without.
//
// ⚠️ EVERY ENCODING HERE CAME OUT OF `m68k-elf-as -mcpu=5475`, not out of a
// reading of the manual. The assembler listing is in the comments beside each
// program so a future reader can re-run it in one command.
#include <cstdio>
#include <cstring>
#include <vector>

#include "machine.h"

#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

namespace
{
	int g_failures = 0;

	// Build a machine whose "image" is a program at the load base, run it for
	// `_instructions`, and return D0.
	uint32_t runProgram(const std::vector<uint8_t>& _code, const uint32_t _d0, const uint32_t _d1,
		const uint32_t _instructions)
	{
		std::vector<uint8_t> image(_code);
		ot::Machine m(image);
		m68k_set_reg(m.getCpuState(), M68K_REG_D0, _d0);
		m68k_set_reg(m.getCpuState(), M68K_REG_D1, _d1);
		const auto stop = m.run(_instructions);
		if(stop != ot::Machine::Stop::Budget)
			std::printf("     (run stopped early: %s)\n", m.why().c_str());
		return m68k_get_reg(m.getCpuState(), M68K_REG_D0);
	}

	void check(const char* _what, const uint32_t _got, const uint32_t _want)
	{
		const bool ok = _got == _want;
		if(!ok)
			++g_failures;
		std::printf("  [%s] %-52s got %#010x want %#010x\n",
			ok ? "PASS" : "FAIL", _what, _got, _want);
	}
}

int main()
{
	std::printf("EMAC gate (hardware semantics, docs/RTOS_FORK.md section 10.16):\n");

	// The firmware's own block-walk idiom: position x (2^31 / blocksize), in
	// fractional mode. `movel #0x20,%macsr` selects fractional+signed.
	//
	//   7020            moveq #32,%d0        <- loaded by hand below instead
	//   a900            movel %d0,%macsr
	//   a200 0800       macl  %d0,%d1,%acc0
	//   a1c0            movclrl %acc0,%d0
	const std::vector<uint8_t> macl = {
		0x70, 0x20,					// moveq #32,%d0   (MACSR = fractional, signed)
		0xa9, 0x00,					// movel %d0,%macsr
		0x20, 0x3c, 0, 0, 0x0c, 0x00,	// movel #0xc00,%d0   -- the operands, so the
		0x22, 0x3c, 0, 0x20, 0, 0,	// movel #0x200000,%d1    program is self-contained
		0xa2, 0x00, 0x08, 0x00,		// macl %d0,%d1,%acc0
		0xa1, 0xc0,					// movclrl %acc0,%d0
		0x4e, 0x71,					// nop
	};
	auto negated = macl;
	negated[6] = 0xff; negated[7] = 0xff; negated[8] = 0xf4; negated[9] = 0x00;	// -0xc00

	//   a200 0900       msacl %d0,%d1,%acc0  -- the extension word's bit 8 is
	//                                           what makes it a SUBTRACT
	auto msacl = macl;
	msacl[18] = 0x09;

	check("macl fractional 0xc00 * 0x200000 (signed >> 31)",
		runProgram(macl, 0, 0, 32), 3);
	check("macl fractional -0xc00 * 0x200000",
		runProgram(negated, 0, 0, 32), 0xfffffffd);
	check("msacl SUBTRACTS (extension word bit 8)",
		runProgram(msacl, 0, 0, 32), 0xfffffffd);

	// ---- MOV3Q to MEMORY (the V4e layer, same dispatch path) -------------
	// ❌ Retracts v4e.cpp's "only Dn is reached by this firmware": the project
	// load runs eight `mov3ql #-1,%a0@+` at 0x4009d8d0 and the refusal was a
	// real line-A exception -- the firmware printed `EXCEPTION VEC:0A
	// ADDR:4009D8D0` and halted, and it looked like a stall at 1,407 of
	// 6,189 ATA commands (measured 8 Sep 2026). Route A never needed a shim
	// (Unicorn has MOV3Q natively), so this gate is the only one that holds
	// the port's version to the same semantics.
	//
	//   207c 4000 0500  moveal #0x40000500,%a0
	//   a158            mov3ql #-1,%a0@+
	//   a358            mov3ql #1,%a0@+
	//   then one of: 2039 4000 0500 movel 0x40000500,%d0
	//                2039 4000 0504 movel 0x40000504,%d0
	//                2008           movel %a0,%d0
	std::printf("MOV3Q gate (memory destinations, v4e.cpp):\n");
	const std::vector<uint8_t> mov3qHead = {
		0x20, 0x7c, 0x40, 0x00, 0x05, 0x00,	// moveal #0x40000500,%a0 (inside the image, past the code)
		0xa1, 0x58,							// mov3ql #-1,%a0@+
		0xa3, 0x58,							// mov3ql #1,%a0@+
	};
	auto readFirst = mov3qHead, readSecond = mov3qHead, readA0 = mov3qHead;
	for(const uint8_t b : {0x20, 0x39, 0x40, 0x00, 0x05, 0x00}) readFirst.push_back(b);
	for(const uint8_t b : {0x20, 0x39, 0x40, 0x00, 0x05, 0x04}) readSecond.push_back(b);
	for(const uint8_t b : {0x20, 0x08}) readA0.push_back(b);
	for(auto* prog : {&readFirst, &readSecond, &readA0})
	{
		prog->push_back(0x4e); prog->push_back(0x71);	// nop
		prog->resize(0x200, 0);							// room for the data at +0x100
	}
	check("mov3ql #-1,%a0@+ writes 0xffffffff", runProgram(readFirst, 0, 0, 4), 0xffffffff);
	check("mov3ql #1,%a0@+ writes 1 at the next long", runProgram(readSecond, 0, 0, 4), 1);
	check("(An)+ advanced a0 by 8 over the pair", runProgram(readA0, 0, 0, 4), 0x40000508);

	std::printf("%s\n", g_failures ? "EMAC GATE FAILED -- nothing this emulator computes can be trusted"
									: "EMAC gate passed.");
	return g_failures ? 1 : 0;
}
