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

		return Result::Unhandled;
	}
}
