// The ColdFire V4e instructions the vendored Musashi does not have.
//
// WHY TRAP-AND-EMULATE, and not new opcode handlers. Musashi's tables are
// GENERATED, and the generator checked into `vendor/mc68k/Musashi/m68kmake.c`
// is NOT the one that produced the checked-in `m68kops.c`: regenerating with
// it rewrites every handler signature (the upstream fork threads a
// `m68ki_cpu_core*` through them, the shipped generator does not), an 18,984
// line diff. So the tables are effectively frozen. ✅ Measured, not assumed --
// regenerate into a scratch tree and diff, it is two commands.
//
// Instead: `m68ki_exception_illegal` calls the illegal-instruction callback
// FIRST and takes no exception if it returns nonzero (`m68kcpu.h`). That makes
// the callback a legal extension point. On entry `REG_PPC` is the faulting
// instruction's own address and `REG_PC` already points past its opcode word,
// so a handler decodes, executes, advances `REG_PC` over its extension words
// and returns 1.
//
// The cost is an exception round trip per instruction. Fine for `mvs`/`mvz`,
// which are ordinary moves scattered through the code; watch it for the EMAC,
// which the frame builder runs in bulk. If it ever matters, these handlers are
// the reference an opcode-table implementation gets diffed against.
//
// ⚠️ EVERY ENCODING HERE IS VERIFIED AGAINST `m68k-elf-objdump -m m68k:cfv4e`
// ON THE REAL IMAGE, never against a reading of the manual alone. This
// project has been bitten twice by a plausible encoding that assembled and did
// the wrong thing (`CLAUDE.md`: the assembler's `mpysu` family, `tfr a,b` as
// `rnd b`), and the emulator half cost a week this month (three defects in
// Unicorn's EMAC, each producing a confident wrong finding). The boot's own
// first two are the worked example:
//
//     4000043e:  73c1        mvzw %d1,%d1
//     40000440:  71c0        mvzw %d0,%d0
//
// which is opcode 0111 rrr 1 oo eeeeee with oo = 11, i.e. the table below.
#include "v4e.h"

#include "machine.h"

#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

namespace ot::v4e
{
	namespace
	{
		constexpr uint32_t g_ccrN = 0x08, g_ccrZ = 0x04, g_ccrV = 0x02, g_ccrC = 0x01;

		uint32_t reg(Machine& _m, const m68k_register_t _r)
		{
			return m68k_get_reg(_m.getCpuState(), _r);
		}

		void setReg(Machine& _m, const m68k_register_t _r, const uint32_t _v)
		{
			m68k_set_reg(_m.getCpuState(), _r, _v);
		}

		m68k_register_t dReg(const uint32_t _i)
		{
			return static_cast<m68k_register_t>(M68K_REG_D0 + _i);
		}

		m68k_register_t aReg(const uint32_t _i)
		{
			return static_cast<m68k_register_t>(M68K_REG_A0 + _i);
		}

		// The PC, as the handler must see it: past the opcode word, pointing at
		// the first extension word. Musashi has already advanced it.
		uint32_t pc(Machine& _m)          { return reg(_m, M68K_REG_PC); }
		void     setPc(Machine& _m, uint32_t _v) { setReg(_m, M68K_REG_PC, _v); }

		uint16_t fetch16(Machine& _m)
		{
			const auto p = pc(_m);
			setPc(_m, p + 2);
			return _m.read16(p);
		}

		uint32_t fetch32(Machine& _m)
		{
			const uint32_t hi = fetch16(_m);
			return (hi << 16) | fetch16(_m);
		}

		// The brief extension word of (d8,An,Xn) / (d8,PC,Xn).
		uint32_t briefIndex(Machine& _m, const uint32_t _base)
		{
			const uint16_t ext = fetch16(_m);
			const uint32_t xn = (ext >> 12) & 7;
			const bool isA = (ext & 0x8000) != 0;
			uint32_t idx = isA ? reg(_m, aReg(xn)) : reg(_m, dReg(xn));
			if(!(ext & 0x0800))						// word index: sign-extended
				idx = static_cast<uint32_t>(static_cast<int32_t>(static_cast<int16_t>(idx)));
			idx <<= (ext >> 9) & 3;					// scale 1/2/4/8
			const auto disp = static_cast<int32_t>(static_cast<int8_t>(ext & 0xff));
			return _base + idx + static_cast<uint32_t>(disp);
		}
	}

	// Read a source operand of `_size` bytes through effective address
	// `mode`/`reg`, advancing the PC over any extension words.
	//
	// ⚠️ `-(An)` and `(An)+` on a BYTE with An = A7 adjust by TWO on the 68000,
	// to keep the stack even. Kept here 🟡 INFERRED for ColdFire, which has no
	// odd-address stack either; nothing in this firmware has exercised it yet,
	// and the falsifier is a `mvs.b -(%sp)` whose stack pointer comes back odd.
	bool readEa(Machine& _m, const uint32_t _mode, const uint32_t _reg, const uint32_t _size,
		uint32_t& _out)
	{
		const auto load = [&](const uint32_t _addr)
		{
			return _size == 1 ? _m.read8(_addr) : _m.read16(_addr);
		};

		switch(_mode)
		{
		case 0:														// Dn
			_out = reg(_m, dReg(_reg));
			return true;
		case 2:														// (An)
			_out = load(reg(_m, aReg(_reg)));
			return true;
		case 3:														// (An)+
			{
				const auto a = reg(_m, aReg(_reg));
				const uint32_t step = (_size == 1 && _reg == 7) ? 2 : _size;
				_out = load(a);
				setReg(_m, aReg(_reg), a + step);
				return true;
			}
		case 4:														// -(An)
			{
				const uint32_t step = (_size == 1 && _reg == 7) ? 2 : _size;
				const auto a = reg(_m, aReg(_reg)) - step;
				setReg(_m, aReg(_reg), a);
				_out = load(a);
				return true;
			}
		case 5:														// (d16,An)
			{
				const auto disp = static_cast<int32_t>(static_cast<int16_t>(fetch16(_m)));
				_out = load(reg(_m, aReg(_reg)) + static_cast<uint32_t>(disp));
				return true;
			}
		case 6:														// (d8,An,Xn)
			_out = load(briefIndex(_m, reg(_m, aReg(_reg))));
			return true;
		case 7:
			switch(_reg)
			{
			case 0:													// (xxx).W
				{
					const auto a = static_cast<int32_t>(static_cast<int16_t>(fetch16(_m)));
					_out = load(static_cast<uint32_t>(a));
					return true;
				}
			case 1:													// (xxx).L
				_out = load(fetch32(_m));
				return true;
			case 2:													// (d16,PC)
				{
					const auto base = pc(_m);						// the extension word's own address
					const auto disp = static_cast<int32_t>(static_cast<int16_t>(fetch16(_m)));
					_out = load(base + static_cast<uint32_t>(disp));
					return true;
				}
			case 3:													// (d8,PC,Xn)
				{
					const auto base = pc(_m);
					_out = load(briefIndex(_m, base));
					return true;
				}
			case 4:													// #imm -- one word for .B and .W
				{
					const auto w = fetch16(_m);
					_out = _size == 1 ? (w & 0xff) : w;
					return true;
				}
			default:
				return false;
			}
		default:
			return false;
		}
	}

	// Set N and Z from a 32-bit result, clear V and C, leave X alone. This is
	// what MVS/MVZ do (CFPRM), and it is the shape every arithmetic addition
	// below will reuse.
	void setNZ(Machine& _m, const uint32_t _result)
	{
		auto sr = reg(_m, M68K_REG_SR);
		sr &= ~(g_ccrN | g_ccrZ | g_ccrV | g_ccrC);
		if(_result == 0)						sr |= g_ccrZ;
		if(static_cast<int32_t>(_result) < 0)	sr |= g_ccrN;
		setReg(_m, M68K_REG_SR, sr);
	}

	namespace
	{
		// MACSR bits that matter here (CFPRM 4.1): bit 5 F/I selects fractional
		// mode, bit 4 S/U selects signed, bit 0 is the product-independent
		// saturation flag this firmware never sets.
		constexpr uint32_t g_macsrFractional = 0x20;

		// One accumulator, 32 bits plus its 8-bit extensions. Musashi's
		// ColdFire state has no EMAC, so the port keeps its own -- four
		// accumulators and the two extension-byte registers.
		// Musashi's ColdFire state has no EMAC at all, so the whole unit lives
		// here: four accumulators, their extension bytes, and MACSR.
		struct Emac
		{
			uint32_t acc[4] = {};
			uint32_t ext[4] = {};	// the sign-extension byte per accumulator
			uint32_t macsr = 0;
		};
		Emac g_emac;

		uint32_t macsr(Machine&) { return g_emac.macsr; }
	}

	// The whole EMAC, as the MCF5445x does it and as the firmware's own
	// reciprocal tables prove (RTOS_FORK section 10.16): in FRACTIONAL mode a
	// signed product is taken and shifted LEFT ONE (the 2.62 product), and the
	// upper 40 bits are accumulated -- so `movclrl` of the result yields
	// (a * b) >> 31, not >> 32. `msac` SUBTRACTS, and which of the two it is
	// comes from bit 8 of the EXTENSION word, never from the opcode word.
	Result emac(Machine& _m, const uint32_t _opcode)
	{
		// movel %dn,%macsr  -- 1010 1001 0000 0rrr  (a900 = from d0)
		if((_opcode & 0xfff8) == 0xa900)
		{
			g_emac.macsr = reg(_m, dReg(_opcode & 7));
			return Result::Handled;
		}
		// movclrl %accN,%dn -- 1010 0rrr 11 00 00NN, clears the accumulator
		if((_opcode & 0xf1f0) == 0xa1c0)
		{
			const uint32_t dn = (_opcode >> 9) & 7;
			const uint32_t acc = _opcode & 3;
			setReg(_m, dReg(dn), g_emac.acc[acc]);
			g_emac.acc[acc] = 0;
			g_emac.ext[acc] = 0;
			return Result::Handled;
		}
		// movel %accN,%dn (no clear) -- a383 = acc1 -> d3
		if((_opcode & 0xf1f0) == 0xa180)
		{
			setReg(_m, dReg((_opcode >> 9) & 7), g_emac.acc[_opcode & 3]);
			return Result::Handled;
		}
		// movel %accext01,%dn / %accext23 -- ab84
		if((_opcode & 0xf1f0) == 0xa980 || (_opcode & 0xf1f0) == 0xab80)
		{
			const bool hi = (_opcode & 0x0200) != 0;
			const uint32_t v = hi
				? ((g_emac.ext[2] & 0xff) | ((g_emac.ext[3] & 0xff) << 8))
				: ((g_emac.ext[0] & 0xff) | ((g_emac.ext[1] & 0xff) << 8));
			setReg(_m, dReg((_opcode >> 9) & 7), v);
			return Result::Handled;
		}

		// MAC / MSAC, with or without a load. The opcode word carries the two
		// source registers and the addressing mode; the EXTENSION word carries
		// the accumulator, the subtract bit and the operand halves.
		const uint16_t ext = fetch16(_m);
		const uint32_t ry = (_opcode >> 9) & 7;
		const uint32_t rx = _opcode & 7;
		const bool subtract = (ext & 0x0100) != 0;			// ⚠️ EXTENSION word,
															// not the opcode word
		const uint32_t accN = ((ext >> 4) & 1) | ((ext >> 8) & 2);
		const bool wordOp = (ext & 0x0800) == 0;			// size: 0 = word, 1 = long
		const bool upperY = (ext & 0x0040) != 0;
		const bool upperX = (ext & 0x0080) != 0;

		const uint32_t rawY = reg(_m, dReg(ry));
		const uint32_t rawX = reg(_m, dReg(rx));

		int64_t product;
		if(wordOp)
		{
			const auto y = static_cast<int16_t>(upperY ? (rawY >> 16) : (rawY & 0xffff));
			const auto x = static_cast<int16_t>(upperX ? (rawX >> 16) : (rawX & 0xffff));
			product = static_cast<int64_t>(y) * static_cast<int64_t>(x);
		}
		else
		{
			product = static_cast<int64_t>(static_cast<int32_t>(rawY))
					* static_cast<int64_t>(static_cast<int32_t>(rawX));
		}

		// FRACTIONAL: the product is shifted left one into 2.62 and the upper
		// 40 bits accumulate, which is a signed >> 31 by the time `movclrl`
		// reads the low longword. INTEGER mode accumulates the product itself.
		// ⚠️ Getting this wrong by one bit is exactly the Unicorn defect that
		// halved every recorder length for a week.
		int64_t addend;
		if(macsr(_m) & g_macsrFractional)
			addend = (product << 1) >> 32;
		else
			addend = product;

		auto acc = static_cast<int64_t>(static_cast<int32_t>(g_emac.acc[accN]));
		acc = subtract ? acc - addend : acc + addend;
		g_emac.acc[accN] = static_cast<uint32_t>(acc);
		g_emac.ext[accN] = static_cast<uint32_t>((acc >> 32) & 0xff);

		// The load half of a `macl %d0,%d1,%a0@+,%d2,%acc1`: mode 3 in the
		// opcode word's bits 3-5, destination register in the extension word's
		// top nibble. Only post-increment appears in this firmware.
		const uint32_t mode = (_opcode >> 3) & 7;
		if(mode == 3)
		{
			const uint32_t an = rx;
			const uint32_t dst = (ext >> 12) & 7;
			const auto a = reg(_m, aReg(an));
			const uint32_t loaded = (static_cast<uint32_t>(_m.read16(a)) << 16) | _m.read16(a + 2);
			setReg(_m, aReg(an), a + 4);
			setReg(_m, dReg(dst), loaded);
		}
		return Result::Handled;
	}

	Result execute(Machine& _m, const uint32_t _opcode)
	{
		// ---- MVS / MVZ ---------------------------------------------------
		// 0111 rrr 1 oo eeeeee, oo = 00 MVS.B, 01 MVS.W, 10 MVZ.B, 11 MVZ.W.
		// ✅ The two the boot reaches at 0x4000043e/0x40000440 disassemble as
		// `mvzw %d1,%d1` and `mvzw %d0,%d0` under m68k:cfv4e, which pins the
		// field layout; the sizes and the sign/zero split are CFPRM's.
		if((_opcode & 0xf100) == 0x7100)
		{
			const uint32_t dx     = (_opcode >> 9) & 7;
			const uint32_t opmode = (_opcode >> 6) & 3;
			const uint32_t mode   = (_opcode >> 3) & 7;
			const uint32_t rn     = _opcode & 7;
			const uint32_t size   = (opmode == 0 || opmode == 2) ? 1 : 2;

			uint32_t src = 0;
			if(!readEa(_m, mode, rn, size, src))
				return Result::Unhandled;

			uint32_t v;
			if(opmode < 2)		// MVS: sign-extend
				v = size == 1
					? static_cast<uint32_t>(static_cast<int32_t>(static_cast<int8_t>(src)))
					: static_cast<uint32_t>(static_cast<int32_t>(static_cast<int16_t>(src)));
			else				// MVZ: zero-extend
				v = size == 1 ? (src & 0xff) : (src & 0xffff);

			setReg(_m, dReg(dx), v);
			setNZ(_m, v);
			return Result::Handled;
		}

		// ---- MOV3Q ---------------------------------------------------------
		// 1010 iii 1 01 eeeeee -- a 3-bit immediate (0 encodes -1) to a
		// longword destination. ✅ `a340` assembles as `mov3ql #1,%d0`.
		if((_opcode & 0xf1c0) == 0xa140)
		{
			const uint32_t imm3 = (_opcode >> 9) & 7;
			const auto v = static_cast<uint32_t>(imm3 == 0 ? -1 : static_cast<int32_t>(imm3));
			const uint32_t mode = (_opcode >> 3) & 7;
			const uint32_t rn   = _opcode & 7;
			if(mode != 0)					// only Dn is reached by this firmware
				return Result::Unhandled;
			setReg(_m, dReg(rn), v);
			setNZ(_m, v);
			return Result::Handled;
		}

		// ---- ISA_C: BITREV / BYTEREV / FF1 ---------------------------------
		// `0000 0ooo 1100 0rrr`: 0x00C0 bitrev, 0x02C0 byterev, 0x04C0 ff1,
		// each ORed with the data register.
		//
		// ❌ THIS RETRACTS O2's NOTE that "byterev and ff1 are not V4e ...
		// nothing needs them". The assembler does refuse them for -mcpu=5475
		// and objdump prints `.short 0x04c2` rather than decoding it -- but
		// the FIRMWARE CONTAINS THEM and reaches one at 0x4004098e, in the
		// task-creation path, which is where the O4 run loop stopped
		// (measured 7 Sep 2026). A toolchain that will not assemble an opcode
		// is not evidence the part lacks it; the image is.
		//
		// ✅ The semantics are route A's `emu_bringup._isa_c_shim`, which is
		// the oracle: ff1 counts LEADING ZEROS and sets N and Z from the
		// SOURCE (not the result) with V and C cleared; bitrev and byterev
		// leave the condition codes alone.
		if((_opcode & 0xfff8) == 0x00c0 || (_opcode & 0xfff8) == 0x02c0 || (_opcode & 0xfff8) == 0x04c0)
		{
			const uint32_t rn = _opcode & 7;
			uint32_t v = reg(_m, dReg(rn));
			switch(_opcode & 0xfff8)
			{
			case 0x00c0:					// bitrev: reverse all 32 bits
				{
					uint32_t out = 0;
					for(uint32_t i = 0; i < 32; ++i)
						out |= ((v >> i) & 1u) << (31 - i);
					v = out;
				}
				break;
			case 0x02c0:					// byterev: reverse the four bytes
				v = ((v & 0x000000ffu) << 24) | ((v & 0x0000ff00u) << 8)
				  | ((v & 0x00ff0000u) >> 8) | ((v & 0xff000000u) >> 24);
				break;
			default:						// ff1: leading-zero count
				{
					auto sr = reg(_m, M68K_REG_SR) & ~0x0fu;
					if(v & 0x80000000u)		// N and Z from the SOURCE
						sr |= g_ccrN;
					if(v == 0)
						sr |= g_ccrZ;
					setReg(_m, M68K_REG_SR, sr);
					uint32_t bits = 0;
					for(uint32_t t = v; t; t >>= 1)
						++bits;
					v = 32 - bits;
				}
				break;
			}
			setReg(_m, dReg(rn), v);
			return Result::Handled;
		}

		// ---- the EMAC ------------------------------------------------------
		// The gate this port must pass before anything it computes is
		// trusted: `tools/ot_emu/test_emac.cpp`, and the hardware semantics it
		// encodes are docs/RTOS_FORK.md section 10.16 -- a week lost to three
		// defects in Unicorn's version of exactly this.
		//
		// ✅ Encodings from `m68k-elf-as -mcpu=5475`:
		//     a900            movel %d0,%macsr
		//     a1c0            movclrl %acc0,%d0
		//     a383            movel %acc1,%d3
		//     ab84            movel %accext01,%d4
		//     a200 0800       macl  %d0,%d1,%acc0
		//     a200 0900       msacl %d0,%d1,%acc0        (ext bit 8 = subtract)
		//     a418 1800       macl  %d0,%d1,%a0@+,%d2,%acc1
		//     a200 0080       macw  %d0l,%d1u,%acc0
		//     a200 0250       macw  %d0u,%d1l,<<,%acc2
		if((_opcode & 0xf000) == 0xa000)
			return emac(_m, _opcode);

		return Result::Unhandled;
	}
}
