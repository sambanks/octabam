// THE EMAC GATE. Run this before trusting anything this emulator computes.
//
// WHY IT EXISTS, and why it is the first test in the port rather than a later
// nicety: three defects in *Unicorn's* ColdFire EMAC cost a week this month
// (`docs/firmware/RTOS_FORK.md` §10.16). Each produced a confident wrong finding that
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
// HARDWARE's, taken from `tools/emu/emu_bringup.py::emac_selftest`, which is the
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
	std::printf("EMAC gate (hardware semantics, docs/firmware/RTOS_FORK.md section 10.16):\n");

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

	// ---- THE FOUR FIELDS THE FIRST DECODER GOT WRONG ---------------------
	// ⚠️ Every case above passes with all four defects in place, because each
	// uses acc0, two DATA registers, the long form and no parallel load --
	// the one combination in which none of them shows (found 8 Sep 2026 when
	// the frame handler's own MAC block stopped the port dead, O6). The
	// expected values below are ROUTE A's, measured by running the same
	// opcodes in its engine, except where noted.
	//
	//   .venv/bin/python3 -c "... macl %a2,%d1,%acc0 -> acc0 = 3 ..."
	std::printf("EMAC field gate (the four the first decoder got wrong):\n");
	{
		// A run that ends by draining all four accumulators into d4..d7:
		//   a1c4 a3c5 a5c6 a7c7   movclrl %acc0..3,%d4..%d7
		const auto runEmac = [](const uint32_t _macsr, const std::vector<uint8_t>& _instr,
			const std::vector<std::pair<m68k_register_t, uint32_t>>& _regs)
		{
			std::vector<uint8_t> image = {0xa9, 0x3c,
				static_cast<uint8_t>(_macsr >> 24), static_cast<uint8_t>(_macsr >> 16),
				static_cast<uint8_t>(_macsr >> 8), static_cast<uint8_t>(_macsr)};
			image.insert(image.end(), _instr.begin(), _instr.end());
			for(const uint8_t b : {0xa1, 0xc4, 0xa3, 0xc5, 0xa5, 0xc6, 0xa7, 0xc7, 0x4e, 0x71})
				image.push_back(b);
			const auto codeLen = image.size();
			image.resize(0x400, 0);				// room for the load forms' data
			image[0x201] = 0x11; image[0x202] = 0x22; image[0x203] = 0x33;	// at 0x40000600
			image[0x209] = 0x44; image[0x20a] = 0x55; image[0x20b] = 0x66;	// at 0x40000608
			ot::Machine m(image);
			for(const auto& [r, v] : _regs)
				m68k_set_reg(m.getCpuState(), r, v);
			const auto stop = m.run(static_cast<uint64_t>(codeLen));	// one per two bytes is plenty
			if(stop == ot::Machine::Stop::Illegal)
				std::printf("     (stopped: %s)\n", m.why().c_str());
			struct Out { uint32_t acc[4]; uint32_t d[8]; uint32_t a[4]; };
			Out o{};
			for(int i = 0; i < 4; ++i)
				o.acc[i] = static_cast<uint32_t>(m68k_get_reg(m.getCpuState(),
					static_cast<m68k_register_t>(M68K_REG_D4 + i)));
			for(int i = 0; i < 8; ++i)
				o.d[i] = static_cast<uint32_t>(m68k_get_reg(m.getCpuState(),
					static_cast<m68k_register_t>(M68K_REG_D0 + i)));
			for(int i = 0; i < 4; ++i)
				o.a[i] = static_cast<uint32_t>(m68k_get_reg(m.getCpuState(),
					static_cast<m68k_register_t>(M68K_REG_A0 + i)));
			return o;
		};

		// 1. AN ADDRESS REGISTER SOURCE. `a20a 0800 macl %a2,%d1,%acc0`: the
		//    first decoder multiplied d2. ✅ route A: acc0 = 3.
		check("macl %a2,%d1 multiplies a2, not d2",
			runEmac(0x20, {0xa2, 0x0a, 0x08, 0x00},
				{{M68K_REG_A2, 0xc00}, {M68K_REG_D1, 0x200000}}).acc[0], 3);

		// 2. THE ACCUMULATOR NUMBER. `a280 0810 macl %d0,%d1,%acc3` -- opcode
		//    bit 7 is the LOW bit and ext bit 4 the HIGH one. ✅ route A: the
		//    product lands in acc3 and acc0 stays zero.
		{
			const auto o = runEmac(0x20, {0xa2, 0x80, 0x08, 0x10},
				{{M68K_REG_D0, 0xc00}, {M68K_REG_D1, 0x200000}});
			check("macl ...,%acc3 lands in acc3", o.acc[3], 3);
			check("... and acc0 is untouched", o.acc[0], 0);
		}

		// 3. WHICH OPERAND'S HALF. In integer mode (MACSR 0) the product is
		//    accumulated whole, so 3 x 5 = 15 is readable. ✅ route A:
		//    `macw %d0u,%d1l` (ext 0x0040) = 15, `%d0l,%d1u` (0x0080) = 0,
		//    `%d0l,%d1l` (0x0000) = 0, with d0 = 0x00030000 and d1 = 5.
		const std::vector<std::pair<m68k_register_t, uint32_t>> halves =
			{{M68K_REG_D0, 0x00030000}, {M68K_REG_D1, 0x00000005}};
		check("macw %d0u,%d1l -- ext bit 6 is the FIRST operand's half",
			runEmac(0, {0xa2, 0x00, 0x00, 0x40}, halves).acc[0], 15);
		check("macw %d0l,%d1u -- and bit 7 the second's",
			runEmac(0, {0xa2, 0x00, 0x00, 0x80}, halves).acc[0], 0);
		check("macw %d0l,%d1l", runEmac(0, {0xa2, 0x00, 0x00, 0x00}, halves).acc[0], 0);

		// 4. THE PARALLEL LOAD, in the three modes the frame routine uses.
		//    ⚠️ Route A cannot run these natively -- Unicorn raises
		//    illegal-instruction and route A SHIMS them
		//    (`emu_bringup._emac_load_shim`) -- so the expectations here are
		//    that shim's semantics, which this decoder is a translation of,
		//    with values chosen so a wrong field is visible:
		//    the multiply is 3 x 5 in integer mode and the load is a longword
		//    from the image at 0x40000600 / 0x40000608.
		//
		//    `a490 1800  macl %d0,%d1,%a0@,%d2,%acc0`      -- (An)
		//    `a498 1800  macl %d0,%d1,%a0@+,%d2,%acc0`     -- (An)+
		//    `a4a8 1800 0008  macl %d0,%d1,%a0@(8),%d2,%acc0` -- (d16,An), SIX bytes
		const std::vector<std::pair<m68k_register_t, uint32_t>> loadRegs =
			{{M68K_REG_D0, 3}, {M68K_REG_D1, 5}, {M68K_REG_A0, 0x40000600}};
		{
			const auto o = runEmac(0, {0xa4, 0x90, 0x18, 0x00}, loadRegs);
			check("macl ...,%a0@,%d2 accumulates 3 x 5", o.acc[0], 15);
			check("... and loads the longword at (a0) into d2", o.d[2], 0x00112233);
			check("... leaving a0 alone", o.a[0], 0x40000600);
		}
		{
			const auto o = runEmac(0, {0xa4, 0x98, 0x18, 0x00}, loadRegs);
			check("macl ...,%a0@+,%d2 loads and advances a0 by 4", o.a[0], 0x40000604);
			check("... with d2 the longword that was at (a0)", o.d[2], 0x00112233);
		}
		{
			// ⚠️ THE SIX-BYTE FORM. Skipping the displacement word is what
			// desynchronised the stream and invented an opcode two
			// instructions later; the `movclrl` tail only runs if the PC came
			// out right, so acc0 reading 15 IS the length check.
			const auto o = runEmac(0, {0xa4, 0xa8, 0x18, 0x00, 0x00, 0x08}, loadRegs);
			check("macl ...,%a0@(8),%d2 accumulates (so the PC advanced 6)", o.acc[0], 15);
			check("... and loads the longword at (a0)+8", o.d[2], 0x00445566);
		}
		// 4b. THE ACCUMULATOR'S ALIGNMENT -- the one the M6c gate caught.
		//    A product whose low 24 bits are NOT zero, subtracted from a
		//    cleared accumulator. ✅ route A: `msacl %d0,%d1,%acc0` with
		//    d0 = 46080 and d1 = 745654 in fractional mode gives -16
		//    (0xfffffff0); `macl` with the same operands gives 15. A model
		//    that shifts each product to >>32 BEFORE accumulating gives -15
		//    for the msac -- one LSB, and it is what made the sequencer's
		//    live nibble read 0x09 where route A reads 0x08 on every frame.
		//    ⚠️ The two cases must both be here: the `macl` one agrees under
		//    either model, so only the `msacl` one is evidence.
		{
			const std::vector<std::pair<m68k_register_t, uint32_t>> off =
				{{M68K_REG_D0, 46080}, {M68K_REG_D1, 745654}};
			check("msacl fractional 46080 x 745654 -> -16, not -15",
				runEmac(0x20, {0xa2, 0x00, 0x09, 0x00}, off).acc[0], 0xfffffff0);
			check("macl with the same operands -> 15 (agrees either way)",
				runEmac(0x20, {0xa2, 0x00, 0x08, 0x00}, off).acc[0], 15);
		}

		// 5. `movel #imm,%macsr` (a93c) -- the frame handler's own at
		//    0x4000aeda. The whole runner depends on it: if it were mis-sized
		//    every case above would run in the wrong MACSR. Read it back with
		//    `a980 movel %macsr,%d0`.
		{
			std::vector<uint8_t> image = {0xa9, 0x3c, 0, 0, 0, 0x20, 0xa9, 0x80, 0x4e, 0x71};
			ot::Machine m(image);
			m.run(4);
			check("movel #32,%macsr then movel %macsr,%d0",
				static_cast<uint32_t>(m68k_get_reg(m.getCpuState(), M68K_REG_D0)), 0x20);
		}
	}

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

	// ---- SATS (the V4e layer, same dispatch path) ------------------------
	// ✅ The firmware reaches `satsl %d0` at 0x4000346a, inside the per-frame
	// EMAC routine the frame handler's state 5 calls -- so it is on the M6c
	// path and nowhere near the boot, which is why O1..O5 never met it. With
	// it unimplemented the port stopped there with "unimplemented opcode 4c80"
	// and delivered ZERO frames (measured 8 Sep 2026, O6).
	//
	// ✅ Encoding from `m68k-elf-as -mcpu=5475`: 4c80 / 4c81 / 4c87 for
	// %d0 / %d1 / %d7 -- `0x4c80 | Dn`.
	//
	// ✅ SEMANTICS MEASURED IN ROUTE A'S OWN ENGINE, not read from the manual
	// (the values below are what Unicorn returns for each case):
	//     V set,   d0 = 0x00000001 -> 0x80000000
	//     V set,   d0 = 0x80000001 -> 0x7fffffff
	//     V clear, d0 = 0x12345678 -> unchanged
	// i.e. a saturate that only fires on overflow, to the end of the range the
	// sign bit says the result WRAPPED away from.
	//
	// ⚠️ AND ONE MEASURED DISAGREEMENT WITH THE MANUAL, carried rather than
	// resolved. The CFPRM says SATS sets N and Z from the result and CLEARS V
	// and C. Route A's engine updates **N only**: a pre-set Z survives a
	// non-zero result, and V and C are left exactly as they were (measured
	// 8 Sep 2026, six cases). This port matches ROUTE A, because route A is
	// the oracle and the two emulators being comparable is the point of the
	// milestone -- and because at the only site the firmware reaches, the four
	// instructions after the `sats` are three `movclrl`s and a `movel`, with
	// no conditional branch between the `sats` and the next instruction that
	// redefines the flags. WHAT WOULD FALSIFY IT: a firmware site that
	// branches on Z or V after a SATS. If one turns up, the manual wins and
	// this is a defect in both emulators.
	std::printf("SATS gate (v4e.cpp; semantics measured in route A's engine):\n");
	const std::vector<uint8_t> satsBody = {
		0x4c, 0x80,					// satsl %d0
		0x4e, 0x71,					// nop
	};
	// The CCR cannot be set by a program here (`move #imm,%sr` is privileged
	// and route A's own probe could not run it either), so it is written into
	// the machine's SR before the run, the way D0 is.
	const auto runSats = [](const uint32_t _sr, const uint32_t _d0)
	{
		std::vector<uint8_t> image = {0x4c, 0x80, 0x4e, 0x71};
		ot::Machine m(image);
		m68k_set_reg(m.getCpuState(), M68K_REG_SR, _sr);
		m68k_set_reg(m.getCpuState(), M68K_REG_D0, _d0);
		m.run(2);
		return std::make_pair(static_cast<uint32_t>(m68k_get_reg(m.getCpuState(), M68K_REG_D0)),
			static_cast<uint32_t>(m68k_get_reg(m.getCpuState(), M68K_REG_SR)) & 0x1fu);
	};
	{
		constexpr uint32_t sup = 0x2700, V = 0x02, C = 0x01, Z = 0x04, N = 0x08;
		check("sats V set, positive-looking -> 0x80000000", runSats(sup | V, 1).first, 0x80000000);
		check("sats V set, negative-looking -> 0x7fffffff", runSats(sup | V, 0x80000001).first, 0x7fffffff);
		check("sats V clear leaves the value alone", runSats(sup, 0x12345678).first, 0x12345678);
		// The flags, exactly as route A's engine leaves them.
		check("sats sets N from the result", runSats(sup | V, 1).second, N | V);
		check("sats clears N from the result", runSats(sup | N, 5).second, 0u);
		check("sats leaves Z, V and C untouched (route A, NOT the CFPRM)",
			runSats(sup | N | Z | V | C, 1).second, N | Z | V | C);
	}

	std::printf("%s\n", g_failures ? "EMAC GATE FAILED -- nothing this emulator computes can be trusted"
									: "EMAC gate passed.");
	return g_failures ? 1 : 0;
}
